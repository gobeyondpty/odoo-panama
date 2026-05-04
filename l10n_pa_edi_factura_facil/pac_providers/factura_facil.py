# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Factura Fácil S.A. concrete PAC implementation.

Implements the abstract `l10n_pa_edi.PACProvider` interface. The HTTP
client is functional (timeout, retry, sanitized logging); the request
and response DTO mappings raise `NotImplementedError` where they
require fields documented only in the Factura Fácil OpenAPI/Swagger
that ships behind their authenticated portal.

Each `NotImplementedError` is also recorded in
`INTEGRATION_CHECKLIST.md` at the repo root so a single document tells
the integrator exactly what to fill in once sandbox credentials arrive.

Public references (no auth required):
- Vendor site:  https://facturafacil.com.pa/
- DGI registration: RUC 155723374-2-2022, Resolución 201-2167
- Swagger (auth):  https://backend-qa-api.facturafacil.com.pa/swagger/

Configuration keys (`ir.config_parameter`):
- `l10n_pa_edi.factura_facil.base_url` (default to QA URL)
- `l10n_pa_edi.factura_facil.api_key`  (bearer token)
- `l10n_pa_edi.factura_facil.timeout`  (default 30s)
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover - declared in __manifest__.external_dependencies
    requests = None  # type: ignore

from odoo.addons.l10n_pa_edi.models.pac_provider import (
    PACProvider,
    PACResponse,
    PACStatus,
    PACAPIError,
    PACAuthError,
    PACConnectionError,
    PACError,
    PACValidationError,
)

_logger = logging.getLogger(__name__)

# Default endpoints. Override via ir.config_parameter at the deployment
# level. Keep the QA endpoint as the safe default to avoid accidental
# production submissions before credentials are validated.
DEFAULT_QA_BASE_URL = 'https://backend-qa-api.facturafacil.com.pa'
DEFAULT_PROD_BASE_URL = 'https://backend-api.facturafacil.com.pa'

# HTTP behavior tuning per Section 8.5 of the development plan.
DEFAULT_TIMEOUT_SECONDS = 30
RETRY_BACKOFF_SCHEDULE = (1.0, 2.0, 4.0)  # exponential backoff in seconds

# Sanitization regex: hide bearer tokens / API keys in any logged JSON.
_REDACT_PATTERNS = [
    re.compile(r'("(?:api_key|apikey|token|access_token|password|authorization)"\s*:\s*")[^"]*(")', re.IGNORECASE),
    re.compile(r'(Bearer\s+)[A-Za-z0-9\-_.~+/=]+', re.IGNORECASE),
]


def _sanitize_for_log(s: str) -> str:
    """Replace credential-like tokens with `***REDACTED***`."""
    if not s:
        return s
    for pat in _REDACT_PATTERNS:
        s = pat.sub(lambda m: m.group(1) + '***REDACTED***' + (m.group(2) if m.lastindex and m.lastindex >= 2 else ''), s)
    return s


class FacturaFacilProvider(PACProvider):
    """PAC implementation for Factura Fácil S.A."""

    code = 'factura_facil'
    name = 'Factura Fácil S.A.'

    # ---- HTTP plumbing ------------------------------------------------

    def _config_param(self, key: str, default: str = '') -> str:
        return self.env['ir.config_parameter'].sudo().get_param(key, default)

    @property
    def base_url(self) -> str:
        if self.company.l10n_pa_pac_environment == 'prod':
            return self._config_param('l10n_pa_edi.factura_facil.base_url_prod', DEFAULT_PROD_BASE_URL).rstrip('/')
        return self._config_param('l10n_pa_edi.factura_facil.base_url', DEFAULT_QA_BASE_URL).rstrip('/')

    @property
    def api_key(self) -> str:
        return self._config_param('l10n_pa_edi.factura_facil.api_key', '')

    @property
    def timeout(self) -> int:
        return int(self._config_param('l10n_pa_edi.factura_facil.timeout', DEFAULT_TIMEOUT_SECONDS))

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_payload: dict | None = None,
        params: dict | None = None,
    ) -> 'requests.Response':
        """Send an HTTP request with retries on 5xx and connection errors.

        Raises one of the `PACError` subclasses. Caller maps the
        response to a `PACResponse`.
        """
        if requests is None:
            raise PACError("Python `requests` library is not installed.")
        url = f"{self.base_url}{path}"
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'

        body = json.dumps(json_payload) if json_payload is not None else None
        last_exc: Exception | None = None
        for attempt, backoff in enumerate(RETRY_BACKOFF_SCHEDULE, start=1):
            try:
                _logger.debug(
                    "FacturaFacil %s %s (attempt %s) payload=%s",
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
                    "FacturaFacil response %s body=%s",
                    resp.status_code, _sanitize_for_log(resp.text or '')[:2000],
                )
                if resp.status_code in (401, 403):
                    raise PACAuthError(
                        f"Factura Fácil rejected credentials: HTTP {resp.status_code}"
                    )
                if 500 <= resp.status_code < 600:
                    last_exc = PACAPIError(
                        f"Factura Fácil returned HTTP {resp.status_code}: "
                        f"{_sanitize_for_log(resp.text or '')[:300]}"
                    )
                    if attempt < len(RETRY_BACKOFF_SCHEDULE):
                        _logger.warning(
                            "FacturaFacil 5xx; retrying in %ss (attempt %s/%s)",
                            backoff, attempt, len(RETRY_BACKOFF_SCHEDULE),
                        )
                        time.sleep(backoff)
                        continue
                    raise last_exc
                # 2xx and 4xx (other than auth) bubble up to the caller.
                return resp
            except requests.Timeout as e:
                last_exc = PACConnectionError(f"Factura Fácil request timed out: {e}")
            except requests.ConnectionError as e:
                last_exc = PACConnectionError(f"Factura Fácil connection error: {e}")
            except PACError:
                raise
            except Exception as e:
                last_exc = PACAPIError(f"Factura Fácil request failed: {e!r}")
            if attempt < len(RETRY_BACKOFF_SCHEDULE):
                _logger.warning(
                    "FacturaFacil transport error; retrying in %ss (attempt %s/%s): %s",
                    backoff, attempt, len(RETRY_BACKOFF_SCHEDULE), last_exc,
                )
                time.sleep(backoff)
                continue
            raise last_exc  # type: ignore[misc]

        # Exhausted retries
        if last_exc:
            raise last_exc
        raise PACAPIError("Factura Fácil request exhausted retries with no exception")

    # ---- Mapping helpers (request / response DTOs) ---------------------

    def _build_send_payload(self, move) -> dict:
        """Build the Factura Fácil submission payload from an account.move.

        TODO[INTEGRATION]: The exact request shape is documented in the
        Factura Fácil Swagger which requires authentication to fetch.
        Once obtained, replace the body of this method to map the move
        into the vendor's expected schema. The unsigned DGI XML built
        by `move._l10n_pa_generate_xml()` is one of the inputs the
        vendor accepts (some PACs accept the DGI rFE document directly,
        others wrap it in their own envelope).
        """
        xml_bytes = move._l10n_pa_generate_xml()
        # Educated guess based on Factura Fácil's "Fácil Connect" public
        # marketing material. Treat as a placeholder until the Swagger
        # confirms the shape.
        return {
            'ruc_emisor': move.company_id.vat,
            'dv_emisor': move.company_id.partner_id.l10n_pa_dv,
            'cufe_local': move.l10n_pa_cufe,
            'xml_dgi_base64': xml_bytes.decode('utf-8'),
        }

    def _parse_send_response(self, response: 'requests.Response') -> PACResponse:
        """Parse a Factura Fácil submit response into a PACResponse.

        TODO[INTEGRATION]: Verify field names against the production
        Swagger. Current implementation expects:
            {
                "success": true|false,
                "cufe": "...",
                "xml_autorizado": "...",
                "qr": "...",
                "errores": [{"codigo":"B201","mensaje":"..."}],
                "estado": {"codigo":"00","mensaje":"Autorizada"}
            }
        """
        try:
            payload: dict[str, Any] = response.json()
        except ValueError:
            return PACResponse(
                success=False,
                raw_response=response.text or '',
                pac_status_code=str(response.status_code),
                errors=[{'code': 'PARSE_ERROR', 'message': 'Respuesta no JSON'}],
            )
        success = bool(payload.get('success')) and response.status_code < 400
        errors = []
        for e in payload.get('errores') or payload.get('errors') or []:
            errors.append({
                'code': e.get('codigo') or e.get('code') or '',
                'message': e.get('mensaje') or e.get('message') or '',
            })
        estado = payload.get('estado') or {}
        return PACResponse(
            success=success,
            cufe=payload.get('cufe') or '',
            authorized_xml=payload.get('xml_autorizado') or payload.get('xml') or '',
            qr_payload=payload.get('qr') or payload.get('qr_payload') or '',
            raw_response=_sanitize_for_log(response.text or ''),
            pac_status_code=str(estado.get('codigo') or ''),
            pac_status_message=estado.get('mensaje') or '',
            errors=errors,
        )

    # ---- Required PACProvider operations ------------------------------

    def send_invoice(self, move) -> PACResponse:
        if not self.api_key:
            raise PACAuthError(
                "Factura Fácil API key is not configured. Set "
                "`l10n_pa_edi.factura_facil.api_key` in System Parameters."
            )
        try:
            payload = self._build_send_payload(move)
            # TODO[INTEGRATION]: Verify the actual endpoint path against
            # Factura Fácil Swagger. '/api/v1/documents' is a placeholder.
            response = self._request('POST', '/api/v1/documents', json_payload=payload)
            return self._parse_send_response(response)
        except PACError as e:
            return PACResponse(
                success=False,
                raw_response=str(e),
                errors=[{'code': type(e).__name__, 'message': str(e)}],
            )

    def get_status(self, cufe: str) -> PACStatus:
        if not self.api_key:
            raise PACAuthError(
                "Factura Fácil API key is not configured."
            )
        # TODO[INTEGRATION]: Verify endpoint path; '/api/v1/documents/{cufe}/status' is a placeholder.
        try:
            response = self._request('GET', f'/api/v1/documents/{cufe}/status')
            payload = response.json() if response.text else {}
            estado = payload.get('estado') or {}
            state_code = (estado.get('codigo') or '').upper()
            state_map = {
                '00': 'authorized',
                '01': 'pending',
                '99': 'rejected',
                'ANUL': 'cancelled',
            }
            return PACStatus(
                cufe=cufe,
                state=state_map.get(state_code, 'unknown'),
                pac_status_code=state_code,
                pac_status_message=estado.get('mensaje') or '',
                raw_response=_sanitize_for_log(response.text or ''),
            )
        except PACError as e:
            return PACStatus(
                cufe=cufe,
                state='unknown',
                pac_status_message=str(e),
                raw_response=str(e),
            )

    def cancel_invoice(self, move, reason: str) -> PACResponse:
        if not self.api_key:
            raise PACAuthError("Factura Fácil API key is not configured.")
        if not move.l10n_pa_cufe:
            raise PACValidationError("La factura no tiene CUFE; no puede anularse.")
        # TODO[INTEGRATION]: The Anulación event has its own DGI schema
        # (Ficha Técnica feRecepEventoFEDGI_v1.00). Build the cancellation
        # XML once the schema is confirmed; fall back to JSON metadata for now.
        body = {
            'cufe': move.l10n_pa_cufe,
            'motivo': reason,
            'ruc_emisor': move.company_id.vat,
        }
        try:
            response = self._request('POST', f'/api/v1/documents/{move.l10n_pa_cufe}/cancel', json_payload=body)
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            success = bool(payload.get('success')) and response.status_code < 400
            return PACResponse(
                success=success,
                raw_response=_sanitize_for_log(response.text or ''),
                pac_status_code=str(payload.get('estado', {}).get('codigo') or ''),
                pac_status_message=payload.get('estado', {}).get('mensaje') or '',
                errors=[{'code': e.get('codigo', ''), 'message': e.get('mensaje', '')}
                        for e in payload.get('errores') or []],
            )
        except PACError as e:
            return PACResponse(
                success=False,
                raw_response=str(e),
                errors=[{'code': type(e).__name__, 'message': str(e)}],
            )

    def validate_ruc(self, ruc: str, dv: str) -> bool:
        # TODO[INTEGRATION]: Verify endpoint path against Swagger. The
        # public DGI also exposes a free RUC lookup (PADRON), which is
        # an acceptable fallback when Factura Fácil does not expose one.
        if not self.api_key:
            raise PACAuthError("Factura Fácil API key is not configured.")
        try:
            response = self._request('GET', '/api/v1/ruc/validate', params={'ruc': ruc, 'dv': dv})
            try:
                return bool(response.json().get('valido'))
            except ValueError:
                return False
        except PACError:
            return False
