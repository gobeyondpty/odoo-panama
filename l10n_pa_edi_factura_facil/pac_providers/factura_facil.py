# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Factura Fácil S.A. concrete PAC implementation.

Implements the abstract `l10n_pa_edi.PACProvider` interface against the
Factura Fácil REST API documented in `Documentacion API FF V1.pdf`
(version v1) and exposed at:

* `https://backend-qa-api.facturafacil.com.pa/swagger/` (QA)
* `https://backend-api.facturafacil.com.pa/swagger/` (Prod)

Authentication uses three HTTP headers per request:

* ``X-FF-Company`` — emisor UUID (Factura Fácil tenant id of the
  contribuyente).
* ``X-FF-Branch`` — sucursal UUID (optional; can also be declared in the
  request body).
* ``X-FF-API-Key`` — API key issued by Factura Fácil.

Endpoints implemented (per the live Swagger at
``/swagger/?format=openapi``; the v1 PDF mislabels some paths):

* ``POST /api/pac/reception_fe/detailed/`` — emit a document and obtain
  a CUFE (``DocumentResult``).
* ``GET  /api/pac/reception_fe/find_by_cufe_or_id/?cufe_or_id=…`` —
  status lookup by CUFE or document UUID (``DocumentStatus``).
* ``POST /api/pac/event/issue/`` — register an Anulación (``type='AN'``)
  or modification (``type='MF'``) event against an authorized CUFE.

RUC validation is not exposed by the Factura Fácil API;
:meth:`validate_ruc` falls back to local DV recomputation via the
:mod:`l10n_pa` ``calculate_dv`` helper.

Credentials live on ``res.company`` (each contribuyente is a separate
Factura Fácil tenant). Endpoint URLs and HTTP timeouts come from
``ir.config_parameter`` (one Factura Fácil deployment per Odoo instance).
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from odoo import _

try:
    import requests
except ImportError:  # pragma: no cover - declared in __manifest__.external_dependencies
    requests = None  # type: ignore

from odoo.addons.l10n_pa.models.res_partner import calculate_dv
from odoo.addons.l10n_pa_edi.models import dgi_xml
from odoo.addons.l10n_pa_edi.models.account_move import _move_type_to_dgi_doc
from odoo.addons.l10n_pa_edi.models.pac_provider import (
    PACAPIError,
    PACAuthError,
    PACConnectionError,
    PACError,
    PACProvider,
    PACResponse,
    PACStatus,
)

_logger = logging.getLogger(__name__)

DEFAULT_QA_BASE_URL = 'https://backend-qa-api.facturafacil.com.pa'
DEFAULT_PROD_BASE_URL = 'https://backend-api.facturafacil.com.pa'

DEFAULT_TIMEOUT_SECONDS = 30
RETRY_BACKOFF_SCHEDULE = (1.0, 2.0, 4.0)

# Endpoint paths (per the live Swagger; the v1 PDF mislabels these).
ENDPOINT_SEND = '/api/pac/reception_fe/detailed/'
ENDPOINT_FIND = '/api/pac/reception_fe/find_by_cufe_or_id/'
ENDPOINT_EVENT_ISSUE = '/api/pac/event/issue/'

# Factura Fácil header.environment values (DGI iAmb in JSON form).
FF_ENV_PROD = '1'
FF_ENV_TEST = '2'

_REDACT_PATTERNS = [
    re.compile(
        r'("(?:api_key|apikey|token|access_token|password|authorization)"\s*:\s*")[^"]*(")',
        re.IGNORECASE,
    ),
    re.compile(r'(X-FF-API-Key\s*:\s*)\S+', re.IGNORECASE),
    re.compile(r'(Bearer\s+)[A-Za-z0-9\-_.~+/=]+', re.IGNORECASE),
]


def _sanitize_for_log(s: str) -> str:
    """Replace credential-like tokens with ``***REDACTED***``."""
    if not s:
        return s
    for pat in _REDACT_PATTERNS:
        s = pat.sub(
            lambda m: m.group(1) + '***REDACTED***'
            + (m.group(2) if m.lastindex and m.lastindex >= 2 else ''),
            s,
        )
    return s


def _fmt_decimal(value: float) -> str:
    """Format an FF decimal string with at least 2 and up to 6 decimals.

    The FF examples use 2 decimals, but quantities and unit prices may
    carry more precision in Odoo (Decimal Accuracy); truncating them to 2
    decimals would break the qty × price arithmetic against `total`.
    """
    text = f"{float(value or 0.0):.6f}".rstrip('0')
    integer, _sep, fraction = text.partition('.')
    return f"{integer}.{fraction.ljust(2, '0')}"


# DGI document-type code → FF `document.type` enum. FF accepts both the
# numeric DGI codes (01..10) and the FAC/NTC/NTD aliases; we send the
# unambiguous numeric form.
DGI_DOC_TO_FF_TYPE: dict[str, str] = {
    '01': '01',  # Factura de operación
    '02': '02',  # Importación
    '03': '03',  # Exportación
    '04': '04',  # Nota de Crédito con referencia
    '05': '05',  # Nota de Débito con referencia
    '06': '06',  # Nota de Crédito genérica
    '07': '07',  # Nota de Débito genérica
    '08': '08',  # Reembolso
    '09': '09',  # Factura zona franca
}

# DocumentStatus.status → normalized PACStatus.state. The Swagger lists
# the enum as `[0, 1, 3, 10, 20, 50, -100]` without labels; the live FF
# responses' `status_display` reveal the meaning:
#   3  → "Finalizado" (authorized + closed)
#   50 → "Anulado"
# Only those two and the DGI-rejection codes are mapped to terminal
# states. Code `1` is most likely "in process"; until a live response
# confirms its meaning it stays `pending` so a status refresh can never
# flip an unconfirmed document to Authorized.
_FF_STATUS_TO_STATE: dict[str, str] = {
    '0': 'pending',          # initial — submitted, not yet routed to DGI
    '1': 'pending',          # in process at DGI (meaning unconfirmed)
    '3': 'authorized',       # "Finalizado" — closed authorization
    '10': 'rejected',        # rejected by DGI
    '20': 'pending',         # warning / waiting state
    '50': 'cancelled',       # "Anulado"
    '-100': 'rejected',      # PAC-side error
}


class FacturaFacilProvider(PACProvider):
    """PAC implementation for Factura Fácil S.A."""

    code = 'factura_facil'
    name = 'Factura Fácil S.A.'

    # ---- Configuration accessors --------------------------------------

    def _config_param(self, key: str, default: str = '') -> str:
        return self.env['ir.config_parameter'].sudo().get_param(key, default)

    @property
    def base_url(self) -> str:
        if self.company.l10n_pa_pac_environment == 'prod':
            return self._config_param(
                'l10n_pa_edi.factura_facil.base_url_prod', DEFAULT_PROD_BASE_URL,
            ).rstrip('/')
        return self._config_param(
            'l10n_pa_edi.factura_facil.base_url', DEFAULT_QA_BASE_URL,
        ).rstrip('/')

    @property
    def company_uuid(self) -> str:
        return (self.company.l10n_pa_factura_facil_company_uuid or '').strip()

    @property
    def branch_uuid(self) -> str:
        return (self.company.l10n_pa_factura_facil_branch_uuid or '').strip()

    @property
    def api_key(self) -> str:
        # sudo: the field is restricted to Settings users; invoices are
        # sent by regular accounting users. The key never reaches the UI
        # or the logs from here.
        key = (self.company.sudo().l10n_pa_factura_facil_api_key or '').strip()
        if key:
            return key
        # Legacy storage (releases before 19.0.1.1.0 kept the key in an
        # instance-wide system parameter): keep old installs working.
        return self._config_param('l10n_pa_edi.factura_facil.api_key', '').strip()

    @property
    def timeout(self) -> int:
        try:
            return int(self._config_param(
                'l10n_pa_edi.factura_facil.timeout', DEFAULT_TIMEOUT_SECONDS,
            ))
        except (TypeError, ValueError):
            return DEFAULT_TIMEOUT_SECONDS

    @property
    def ff_environment(self) -> str:
        return FF_ENV_PROD if self.company.l10n_pa_pac_environment == 'prod' else FF_ENV_TEST

    def _require_credentials(self) -> None:
        missing = [
            label for label, value in (
                ('X-FF-Company', self.company_uuid),
                ('X-FF-API-Key', self.api_key),
            ) if not value
        ]
        if missing:
            raise PACAuthError(
                _(
                    "Incomplete Factura Fácil credentials: missing %(missing)s. "
                    "Configure them on the company record.",
                    missing=', '.join(missing),
                )
            )

    # ---- HTTP plumbing -------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_payload: dict | None = None,
        params: dict | None = None,
    ) -> 'requests.Response':
        """Send an HTTP request with retries on 5xx and connection errors."""
        if requests is None:
            raise PACError(_("The Python `requests` library is not installed."))
        url = f"{self.base_url}{path}"
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-FF-Company': self.company_uuid,
            'X-FF-API-Key': self.api_key,
        }
        if self.branch_uuid:
            headers['X-FF-Branch'] = self.branch_uuid

        body = json.dumps(json_payload) if json_payload is not None else None
        last_exc: Exception | None = None
        for attempt, backoff in enumerate(RETRY_BACKOFF_SCHEDULE, start=1):
            try:
                _logger.debug(
                    "FacturaFacil %s %s (intento %s) payload=%s",
                    method, url, attempt, _sanitize_for_log(body or ''),
                )
                resp = requests.request(
                    method,
                    url,
                    headers=headers,
                    data=body,
                    params=params,
                    timeout=self.timeout,
                )
                _logger.debug(
                    "FacturaFacil respuesta %s body=%s",
                    resp.status_code,
                    _sanitize_for_log(resp.text or '')[:2000],
                )
                if resp.status_code in (401, 403):
                    raise PACAuthError(
                        _("Factura Fácil rejected the credentials: HTTP %(status)s", status=resp.status_code)
                    )
                if 500 <= resp.status_code < 600:
                    last_exc = PACAPIError(
                        _(
                            "Factura Fácil returned HTTP %(status)s: %(body)s",
                            status=resp.status_code,
                            body=_sanitize_for_log(resp.text or '')[:300],
                        )
                    )
                    if attempt < len(RETRY_BACKOFF_SCHEDULE):
                        _logger.warning(
                            "FacturaFacil 5xx; reintentando en %ss (intento %s/%s)",
                            backoff, attempt, len(RETRY_BACKOFF_SCHEDULE),
                        )
                        time.sleep(backoff)
                        continue
                    raise last_exc
                return resp
            except requests.Timeout as e:
                last_exc = PACConnectionError(_("Factura Fácil timeout: %(error)s", error=e))
            except requests.ConnectionError as e:
                last_exc = PACConnectionError(_("Factura Fácil connection error: %(error)s", error=e))
            except PACError:
                raise
            except Exception as e:
                last_exc = PACAPIError(_("Factura Fácil request failed: %(error)r", error=e))
            if attempt < len(RETRY_BACKOFF_SCHEDULE):
                _logger.warning(
                    "FacturaFacil error de transporte; reintentando en %ss (intento %s/%s): %s",
                    backoff, attempt, len(RETRY_BACKOFF_SCHEDULE), last_exc,
                )
                time.sleep(backoff)
                continue
            raise last_exc  # type: ignore[misc]

        if last_exc:
            raise last_exc
        raise PACAPIError(_("Factura Fácil exhausted retries without an exception."))

    # ---- Payload builders ---------------------------------------------

    def _build_send_payload(self, move) -> dict:
        """Build the `POST /pac/reception_fe/detailed/` request body."""
        partner = move.commercial_partner_id

        dgi_doc = _move_type_to_dgi_doc(
            move.move_type,
            has_origin_cufe=bool(move.l10n_pa_origin_cufe),
            is_debit_note=bool(move.debit_origin_id),
        )
        ff_type = DGI_DOC_TO_FF_TYPE.get(dgi_doc, dgi_doc)

        header = {
            'id': str(move.id),
            'environment': self.ff_environment,
        }

        product_lines = move.invoice_line_ids.filtered(
            lambda line: line.display_type == 'product',
        )
        document: dict[str, Any] = {
            'fd_number': int(move._l10n_pa_get_doc_number() or '0'),
            'type': ff_type,
            'receptor': self._build_receptor(partner),
            'items': [
                self._build_item(line, idx)
                for idx, line in enumerate(product_lines, start=1)
            ],
            'payments': self._build_payments(move),
            'total': f"{move.amount_total:.2f}",
        }

        if move.narration:
            info = move._l10n_pa_strip_html(move.narration)
            if info:
                document['info'] = info[:5000]

        if move.l10n_pa_origin_cufe:
            document['referred'] = self._build_referred(move)

        if partner.country_id and partner.country_id.code and partner.country_id.code != 'PA':
            document['dest_country'] = partner.country_id.code

        return {'header': header, 'document': document}

    def _build_receptor(self, partner) -> dict:
        receiver_type = partner.l10n_pa_receiver_type or '02'
        rec: dict[str, Any] = {
            'type': receiver_type,
            'name': (partner.name or 'Consumidor Final')[:100],
            'ruc_type': '2' if partner.is_company else '1',
        }
        if partner.contact_address_inline:
            rec['address'] = partner.contact_address_inline[:100]
        if partner.email:
            rec['email'] = partner.email
        if partner.vat:
            rec['ruc'] = partner.vat[:20]
        if partner.l10n_pa_dv and receiver_type in ('01', '03'):
            rec['dv'] = partner.l10n_pa_dv[:2]
        location = getattr(partner, 'l10n_pa_edi_location_id', False)
        if location and location.code:
            rec['location'] = location.code[:8]
        if receiver_type == '04' and partner.country_id and partner.country_id.code:
            rec['country'] = partner.country_id.code
        return rec

    def _build_item(self, line, sequence: int) -> dict:
        product = line.product_id
        template = product.product_tmpl_id if product else False
        edi_uom = template.l10n_pa_edi_uom_id if template else False
        cpbs = False
        if template:
            cpbs = template.l10n_pa_edi_cpbs_id or template.categ_id.l10n_pa_edi_cpbs_id

        # FF `discount` is a per-unit amount in Balboas, NOT a percentage
        # (Documentacion API FF V1 §1.1: "Informar valor del descuento en
        # Balboas, no en porcentaje").
        discount_amount = line.price_unit * (line.discount or 0.0) / 100.0
        price_after_discount = line.price_unit - discount_amount

        # Per-tax amounts: a line can carry several taxes (e.g. ITBMS +
        # ISC), so each entry must report its own share, not the line's
        # combined tax delta.
        amount_by_tax: dict[int, float] = {}
        if line.tax_ids:
            computed = line.tax_ids.compute_all(
                price_after_discount,
                currency=line.currency_id,
                quantity=line.quantity,
                product=line.product_id,
                partner=line.move_id.partner_id,
                is_refund=line.move_id.move_type in ('out_refund', 'in_refund'),
            )
            for tax_data in computed['taxes']:
                amount_by_tax[tax_data['id']] = (
                    amount_by_tax.get(tax_data['id'], 0.0) + tax_data['amount']
                )

        taxes = []
        for tax in line.tax_ids:
            group_name = (tax.tax_group_id.name or '').upper() if tax.tax_group_id else ''
            amount = amount_by_tax.get(tax.id, 0.0)
            if 'ITBMS' in group_name:
                try:
                    code = dgi_xml.itbms_rate_to_code(tax.amount)
                except ValueError:
                    raise PACError(_(
                        "Tax '%(tax)s' has rate %(rate)s%% which has no DGI "
                        "ITBMS code (allowed: 0%%, 7%%, 10%%, 15%%).",
                        tax=tax.display_name, rate=tax.amount,
                    ))
                taxes.append({
                    'type': '01',
                    'amount': f"{amount:.2f}",
                    'code': code,
                })
            elif 'ISC' in group_name:
                taxes.append({
                    'type': '03',
                    'amount': f"{amount:.2f}",
                    'code': '',
                    'rate': f"{tax.amount:.2f}",
                })
            # OTI and other special taxes are not mapped here; extend as needed.

        if not taxes:
            taxes = [{'type': '01', 'amount': '0.00', 'code': '00'}]

        item: dict[str, Any] = {
            'line': sequence,
            'price': _fmt_decimal(line.price_unit),
            'quantity': _fmt_decimal(line.quantity),
            'description': (line.name or (line.product_id.display_name if line.product_id else '') or '')[:500],
            'taxes': taxes,
            'discount': _fmt_decimal(discount_amount),
        }
        if product and product.default_code:
            item['internal_code'] = product.default_code[:20]
        if edi_uom and edi_uom.code:
            item['mu'] = edi_uom.code[:20]
        if cpbs and cpbs.code:
            item['gns'] = cpbs.code[:4]
        return item

    def _build_payments(self, move) -> list[dict]:
        """Default to a single credit-term payment (FF type 01).

        Reconciliation-aware payment mapping is an extension point: a
        subclass can override this once `account.payment` integration is
        wired up.
        """
        return [{
            'type': '01',
            'amount': f"{move.amount_total:.2f}",
        }]

    def _build_referred(self, move) -> dict:
        origin = move.reversed_entry_id or move.debit_origin_id
        ref_date = (origin.invoice_date if origin else False) or move.invoice_date
        return {
            'fd_number': (move.l10n_pa_origin_cufe or '')[:66],
            'fd_date': ref_date.strftime('%Y-%m-%d') if ref_date else '',
        }

    # ---- Response parsing ---------------------------------------------

    def _parse_send_response(self, response: 'requests.Response') -> PACResponse:
        """Map a `POST /pac/reception_fe/detailed/` response to PACResponse."""
        try:
            payload: dict[str, Any] = response.json() or {}
        except ValueError:
            return PACResponse(
                success=False,
                raw_response=_sanitize_for_log(response.text or '')[:5000],
                pac_status_code=str(response.status_code),
                errors=[{'code': 'PARSE_ERROR', 'message': 'Respuesta no JSON'}],
            )

        rejected = bool(payload.get('rejected'))
        http_ok = 200 <= response.status_code < 300
        cufe = payload.get('cufe') or ''
        success = http_ok and not rejected and bool(cufe)

        # Split DGI messages into Rejections (type='R') and Notifications
        # (type='N'). Errors are only the rejection-class messages so the
        # base move handler does not surface harmless notifications as errors.
        errors: list[dict[str, str]] = []
        notifications: list[dict[str, str]] = []
        for msg in payload.get('messages') or []:
            entry = {
                'code': str(msg.get('code') or ''),
                'message': msg.get('message') or '',
                'type': msg.get('type') or '',
                'field': msg.get('field_name') or msg.get('path') or '',
            }
            if entry['type'] == 'N':
                notifications.append(entry)
            else:
                errors.append(entry)

        if success:
            status_code = payload.get('authorization_number') or '00'
            # The first DGI notification carries the human-readable status
            # string (e.g. "Autorizado el uso de la FE"); `service_response`
            # is the full SOAP envelope which is too verbose for UI.
            status_msg = (
                (notifications[0]['message'] if notifications else '')
                or 'Autorizada'
            )
        else:
            status_code = errors[0]['code'] if errors else str(response.status_code)
            status_msg = errors[0]['message'] if errors else 'Documento rechazado'

        return PACResponse(
            success=success,
            cufe=cufe,
            authorized_xml=payload.get('xml') or '',
            qr_payload=payload.get('qr_code_data') or '',
            raw_response=_sanitize_for_log(response.text or '')[:10000],
            pac_status_code=str(status_code),
            pac_status_message=status_msg,
            errors=errors,
            extra={
                'document_uuid': payload.get('document_uuid') or '',
                'did': payload.get('did') or '',
                'pdf_url': payload.get('pdf_url') or '',
                'qr_image_b64': payload.get('qr_image_b64') or '',
                'authorization_number': payload.get('authorization_number') or '',
                'process_date': payload.get('process_date') or '',
                'notifications': notifications,
            },
        )

    # ---- PACProvider operations ---------------------------------------

    def send_invoice(self, move) -> PACResponse:
        try:
            self._require_credentials()
            payload = self._build_send_payload(move)
            response = self._request('POST', ENDPOINT_SEND, json_payload=payload)
            return self._parse_send_response(response)
        except PACError as e:
            return PACResponse(
                success=False,
                raw_response=str(e),
                errors=[{'code': type(e).__name__, 'message': str(e)}],
            )

    def get_status(self, cufe: str) -> PACStatus:
        """Look up the current PAC state of a previously-emitted document.

        Uses ``GET /api/pac/reception_fe/find_by_cufe_or_id/`` which
        accepts either a 66-char CUFE or a document UUID in the
        ``cufe_or_id`` query parameter and returns a ``DocumentStatus``
        (``{id, cufe, status, status_display, created_at, updated_at,
        xml_data}``).
        """
        if not cufe:
            return PACStatus(cufe='', state='unknown', pac_status_message=_("Empty CUFE"))
        try:
            self._require_credentials()
        except PACError as e:
            return PACStatus(cufe=cufe, state='unknown', pac_status_message=str(e))

        try:
            response = self._request(
                'GET', ENDPOINT_FIND, params={'cufe_or_id': cufe},
            )
        except PACError as e:
            return PACStatus(
                cufe=cufe, state='unknown',
                pac_status_message=str(e), raw_response=str(e),
            )

        raw = _sanitize_for_log(response.text or '')[:5000]
        if response.status_code == 404:
            return PACStatus(
                cufe=cufe, state='unknown',
                pac_status_message=_("CUFE not found in the PAC."),
                raw_response=raw,
            )
        if response.status_code >= 400:
            return PACStatus(
                cufe=cufe, state='unknown',
                pac_status_code=str(response.status_code),
                pac_status_message=raw[:300],
                raw_response=raw,
            )
        try:
            payload = response.json() or {}
        except ValueError:
            return PACStatus(
                cufe=cufe, state='unknown',
                pac_status_message=_("Non-JSON response"), raw_response=raw,
            )
        ff_status = str(payload.get('status'))
        return PACStatus(
            cufe=payload.get('cufe') or cufe,
            state=_FF_STATUS_TO_STATE.get(ff_status, 'unknown'),
            pac_status_code=ff_status,
            pac_status_message=payload.get('status_display') or '',
            raw_response=raw,
        )

    def cancel_invoice(self, move, reason: str) -> PACResponse:
        """Register a cancellation event (``type='AN'``) against the move.

        Uses ``POST /api/pac/event/issue/`` with body
        ``{type: 'AN', cufe, reason}``. The endpoint returns the created
        ``EventoPACIssue`` with the PAC/DGI response payload.
        """
        if not move.l10n_pa_cufe:
            return PACResponse(
                success=False,
                raw_response='',
                errors=[{
                    'code': 'NO_CUFE',
                    'message': _("The invoice has no CUFE and cannot be cancelled."),
                }],
            )
        try:
            self._require_credentials()
            body = {
                'type': 'AN',
                'cufe': move.l10n_pa_cufe,
                'reason': (reason or '')[:500],
            }
            response = self._request('POST', ENDPOINT_EVENT_ISSUE, json_payload=body)
        except PACError as e:
            return PACResponse(
                success=False,
                raw_response=str(e),
                errors=[{'code': type(e).__name__, 'message': str(e)}],
            )

        raw = _sanitize_for_log(response.text or '')[:5000]
        try:
            payload = response.json() or {}
        except ValueError:
            payload = {}
        http_ok = 200 <= response.status_code < 300
        rejected = bool(payload.get('rejected'))
        success = http_ok and not rejected
        # Live FF responds with `{rejected, message, response, auth_date}`;
        # the Swagger `EventoPACIssue` also lists `id`/`code`/`response_ff`/
        # `response_dgi`. Read both shapes.
        msg = (
            payload.get('message')
            or payload.get('response_dgi') or payload.get('response_ff')
            or (_("Cancelled") if success else _("Cancellation rejected"))
        )
        code = str(payload.get('code') or response.status_code)
        return PACResponse(
            success=success,
            cufe=move.l10n_pa_cufe,
            raw_response=raw,
            pac_status_code=code,
            pac_status_message=msg,
            errors=[] if success else [{'code': code, 'message': msg}],
            extra={
                'event_id': payload.get('id') or '',
                'auth_date': payload.get('auth_date') or '',
                'response': payload.get('response') or '',
            },
        )

    def validate_ruc(self, ruc: str, dv: str) -> bool:
        """Local DV recomputation (FF v1 API has no RUC lookup endpoint).

        Returns False whenever the input does not match a DV-computable
        Panama identifier; ``calculate_dv`` returns the empty string for
        unparseable inputs and that is treated as a mismatch.
        """
        if not ruc or not dv:
            return False
        try:
            computed = calculate_dv(ruc.strip())
        except Exception:
            return False
        if not computed:
            return False
        return str(dv).zfill(2) == str(computed).zfill(2)
