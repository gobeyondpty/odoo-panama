# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Invoice extensions for Panama electronic invoicing.

Adds CUFE, PAC status, and the helpers that build the unsigned DGI XML
from invoice data. Also exposes the Spanish error-message resolver and
the linkage to the original CUFE for credit/debit notes.
"""
from __future__ import annotations

import logging

from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .cufe import build_cufe, generate_security_code
from . import dgi_xml

_logger = logging.getLogger(__name__)


# Minimal ISO 3166-1 alpha-2 → alpha-3 map for the countries the
# operator routinely transacts with. The DGI XML expects alpha-3
# (`cPaisRec`); upstream `res.country` only stores alpha-2. Extend as
# needed; falls back to the alpha-2 code padded if not found.
_COUNTRY_ALPHA3 = {
    'PA': 'PAN', 'US': 'USA', 'CA': 'CAN', 'MX': 'MEX', 'GT': 'GTM',
    'CO': 'COL', 'CR': 'CRI', 'NI': 'NIC', 'HN': 'HND', 'SV': 'SLV',
    'EC': 'ECU', 'PE': 'PER', 'CL': 'CHL', 'AR': 'ARG', 'BR': 'BRA',
    'UY': 'URY', 'VE': 'VEN', 'DO': 'DOM', 'CU': 'CUB', 'BO': 'BOL',
    'PY': 'PRY', 'ES': 'ESP', 'GB': 'GBR', 'FR': 'FRA', 'DE': 'DEU',
    'IT': 'ITA', 'CN': 'CHN', 'JP': 'JPN', 'KR': 'KOR', 'IL': 'ISR',
}


def _country_alpha3(country, default: str = '') -> str:
    """Map a `res.country` to its DGI alpha-3 code, with sensible default."""
    if not country:
        return default
    code = (country.code or '').upper()
    return _COUNTRY_ALPHA3.get(code, code.ljust(3, 'X') if code else default)


# Map from Odoo move_type / refund linkage → DGI document type.
def _move_type_to_dgi_doc(
    move_type: str,
    has_origin_cufe: bool,
    is_debit_note: bool = False,
) -> str:
    if move_type == 'out_invoice':
        # Customer debit notes (Enterprise account_debit_note flow) are
        # also stored as out_invoice with debit_origin_id set. Distinguish
        # them so they map to the DGI debit-note document types instead
        # of an ordinary factura.
        if is_debit_note:
            return (
                dgi_xml.DGI_DOC_NOTA_DEBITO_REF
                if has_origin_cufe
                else dgi_xml.DGI_DOC_NOTA_DEBITO_GENERICA
            )
        return dgi_xml.DGI_DOC_FACTURA
    if move_type == 'out_refund':
        return (
            dgi_xml.DGI_DOC_NOTA_CREDITO_REF
            if has_origin_cufe
            else dgi_xml.DGI_DOC_NOTA_CREDITO_GENERICA
        )
    if move_type == 'in_refund':  # vendor credit note flows are out of scope by plan
        return dgi_xml.DGI_DOC_NOTA_CREDITO_GENERICA
    raise UserError(_(
        "El tipo de documento %(move_type)s no es soportado por el "
        "módulo de Factura Electrónica de Panamá.",
        move_type=move_type,
    ))


class AccountMove(models.Model):
    _inherit = 'account.move'

    # ---- DGI fields ----------------------------------------------------

    l10n_pa_cufe = fields.Char(
        string="CUFE",
        copy=False,
        readonly=True,
        tracking=True,
        help="Código Único de Factura Electrónica asignado por DGI a través del PAC.",
    )
    l10n_pa_security_code = fields.Char(
        string="Código de Seguridad (dSeg)",
        copy=False,
        readonly=True,
        size=9,
        help="Código aleatorio de 9 dígitos usado en el cálculo del CUFE.",
    )
    l10n_pa_pac_status = fields.Selection(
        [
            ('draft', "Borrador"),
            ('sent', "Enviado al PAC"),
            ('authorized', "Autorizado por DGI"),
            ('rejected', "Rechazado"),
            ('cancelled', "Anulado"),
        ],
        default='draft',
        copy=False,
        tracking=True,
        string="Estado PAC",
    )
    l10n_pa_pac_response = fields.Text(
        string="Respuesta cruda del PAC",
        copy=False,
        readonly=True,
        help="Respuesta sin procesar devuelta por el PAC. Útil para depuración.",
    )
    l10n_pa_pac_error_codes = fields.Char(
        string="Códigos de error DGI/PAC",
        copy=False,
        readonly=True,
    )
    l10n_pa_origin_cufe = fields.Char(
        string="CUFE referenciado (Nota de Crédito/Débito)",
        copy=False,
        compute='_compute_l10n_pa_origin_cufe',
        store=True,
        readonly=False,
        help="CUFE de la factura electrónica original referenciada por esta "
             "nota de crédito o débito. Se autocompleta del CUFE de la "
             "factura origen cuando la nota se crea desde una reversión "
             "(Nota de Crédito) o vía account_debit_note (Nota de Débito); "
             "puede sobreescribirse manualmente.",
    )

    @api.depends(
        'reversed_entry_id.l10n_pa_cufe',
        'debit_origin_id.l10n_pa_cufe',
    )
    def _compute_l10n_pa_origin_cufe(self):
        """Auto-derive the origin CUFE from the source invoice.

        - Credit notes (out_refund) created via account.move.reversal have
          ``reversed_entry_id`` set to the original invoice.
        - Debit notes (out_invoice + debit_origin_id) created via
          account_debit_note have ``debit_origin_id`` set to the original
          invoice.

        Both source invoices carry ``l10n_pa_cufe`` once the PAC has
        authorized them. Without this auto-derivation, debit/credit
        notes default to the generic DGI document type (06/07) instead
        of the referenced types (04/05), which is wrong per DGI rules.
        """
        for move in self:
            origin = move.reversed_entry_id or move.debit_origin_id
            if origin and origin.l10n_pa_cufe and not move.l10n_pa_origin_cufe:
                move.l10n_pa_origin_cufe = origin.l10n_pa_cufe
            elif not move.l10n_pa_origin_cufe:
                move.l10n_pa_origin_cufe = False
    l10n_pa_contingency = fields.Boolean(
        string="Contingencia",
        copy=False,
        help="Marcar si esta factura se emite bajo modalidad de contingencia "
             "(iTpEmis = 02).",
    )
    l10n_pa_contingency_reason = fields.Char(
        string="Motivo de Contingencia",
        copy=False,
    )
    l10n_pa_operation_nature = fields.Selection(
        [
            ('01', "Venta"),
            ('02', "Exportación"),
            ('03', "Re-exportación"),
            ('04', "Venta de fuente extranjera"),
            ('05', "Servicio de fuente extranjera"),
            ('10', "Transferencia / Traspaso"),
            ('11', "Devolución"),
            ('12', "Consignación"),
            ('13', "Remesa"),
            ('14', "Entrega gratuita"),
            ('20', "Compra"),
            ('21', "Importación"),
        ],
        string="Naturaleza de la Operación DGI",
        compute='_compute_l10n_pa_dgi_operation_defaults',
        store=True,
        readonly=False,
        copy=False,
        help="Campo iNatOp de la Ficha Técnica DGI PAC v1.00.",
    )
    l10n_pa_operation_type = fields.Selection(
        [
            ('1', "Salida o venta"),
            ('2', "Entrada o compra"),
        ],
        string="Tipo de Operación DGI",
        compute='_compute_l10n_pa_dgi_operation_defaults',
        store=True,
        readonly=False,
        copy=False,
        help="Campo iTipoOp de la Ficha Técnica DGI PAC v1.00.",
    )
    l10n_pa_operation_destination = fields.Selection(
        [
            ('1', "Panamá"),
            ('2', "Extranjero"),
        ],
        string="Destino de la Operación DGI",
        compute='_compute_l10n_pa_dgi_operation_defaults',
        store=True,
        readonly=False,
        copy=False,
        help="Campo iDest de la Ficha Técnica DGI PAC v1.00.",
    )
    l10n_pa_xml_attachment_id = fields.Many2one(
        'ir.attachment',
        string="XML DGI",
        copy=False,
        readonly=True,
    )
    l10n_pa_qr_payload = fields.Char(
        string="Carga del Código QR",
        copy=False,
        readonly=True,
        help="Cadena codificada en el código QR del CAFE.",
    )

    @api.depends('move_type', 'commercial_partner_id.country_id', 'debit_origin_id')
    def _compute_l10n_pa_dgi_operation_defaults(self):
        for move in self:
            partner = move.commercial_partner_id
            is_foreign = bool(partner.country_id and partner.country_id.code != 'PA')
            is_refund = move.move_type in ('out_refund', 'in_refund')
            is_purchase = move.move_type in ('in_invoice', 'in_refund')
            if is_refund:
                move.l10n_pa_operation_nature = '11'
            elif is_purchase:
                move.l10n_pa_operation_nature = '21' if is_foreign else '20'
            else:
                move.l10n_pa_operation_nature = '02' if is_foreign else '01'
            move.l10n_pa_operation_type = '2' if is_purchase else '1'
            move.l10n_pa_operation_destination = '2' if is_foreign else '1'

    # -------------------------------------------------------------------
    # Provider plumbing
    # -------------------------------------------------------------------

    def _l10n_pa_get_pac_provider(self):
        """Instantiate the company's configured PAC provider, or None."""
        self.ensure_one()
        code = self.company_id.l10n_pa_pac_provider
        if not code or code == 'none':
            return None
        provider_cls = self.env['account.move']._l10n_pa_provider_registry().get(code)
        if not provider_cls:
            raise UserError(_(
                "No se encontró un proveedor PAC registrado con el código '%(code)s'. "
                "Verifique que el módulo correspondiente esté instalado.",
                code=code,
            ))
        return provider_cls(self.company_id)

    @api.model
    def _l10n_pa_provider_registry(self):
        """Concrete provider modules override this to register their class.

        Return a dict `{code: ProviderClass}`. Each subclass module
        appends its entry by calling super().
        """
        return {}

    # -------------------------------------------------------------------
    # XML generation
    # -------------------------------------------------------------------

    def _l10n_pa_compute_cufe(self) -> str:
        """Build the CUFE for this move and return it as a string."""
        self.ensure_one()
        company = self.company_id

        if not company.vat or not company.partner_id.l10n_pa_dv:
            raise UserError(_(
                "La compañía '%(company)s' debe tener RUC y DV configurados.",
                company=company.name,
            ))
        if not self.l10n_pa_security_code:
            self.l10n_pa_security_code = generate_security_code()

        ambiente = (
            dgi_xml.DGI_AMBIENTE_PROD
            if company.l10n_pa_pac_environment == 'prod'
            else dgi_xml.DGI_AMBIENTE_TEST
        )
        tipo_ruc = (
            dgi_xml.DGI_TIPO_RUC_JURIDICO
            if company.partner_id.is_company
            else dgi_xml.DGI_TIPO_RUC_NATURAL
        )
        doc_type = _move_type_to_dgi_doc(
            self.move_type,
            has_origin_cufe=bool(self.l10n_pa_origin_cufe),
            is_debit_note=bool(self.debit_origin_id),
        )
        return build_cufe(
            tipo_documento=doc_type,
            tipo_ruc=tipo_ruc,
            ruc=company.vat,
            dv=company.partner_id.l10n_pa_dv,
            sucursal=company.l10n_pa_sfep_branch or '0001',
            fecha_emision=self.invoice_date or fields.Date.context_today(self),
            nro_df=self._l10n_pa_get_doc_number(),
            pto_fac_df=company.l10n_pa_sfep_emission_point or '001',
            tipo_emision=(
                '02' if self.l10n_pa_contingency
                else company.l10n_pa_sfep_emission_type or '01'
            ),
            ambiente=ambiente,
            security_code=self.l10n_pa_security_code,
        )

    def _l10n_pa_get_doc_number(self) -> str:
        """Numeric sequence portion of the document number, padded to 10.

        Strategy: take the digits of the *last* slash-separated segment
        of `name` (e.g. `INV/2026/00007` → `00007`), so the year prefix
        in `INV/2026/...` doesn't pollute the sequence number.
        """
        self.ensure_one()
        if not self.name:
            return '0' * 10
        last_segment = self.name.rsplit('/', 1)[-1]
        digits = ''.join(c for c in last_segment if c.isdigit())
        if not digits:
            # Fall back to all digits of the name if the last segment
            # has none (rare, e.g. legacy custom sequences).
            digits = ''.join(c for c in self.name if c.isdigit())
        if not digits:
            return '0' * 10
        return digits[-10:].rjust(10, '0')

    def _l10n_pa_build_xml_payload(self) -> dict:
        """Build the dgi_xml.build_rfe payload dict for this move."""
        self.ensure_one()
        company = self.company_id
        partner = self.commercial_partner_id
        cufe = self.l10n_pa_cufe or self._l10n_pa_compute_cufe()

        ambiente = (
            dgi_xml.DGI_AMBIENTE_PROD
            if company.l10n_pa_pac_environment == 'prod'
            else dgi_xml.DGI_AMBIENTE_TEST
        )
        doc_type = _move_type_to_dgi_doc(
            self.move_type,
            has_origin_cufe=bool(self.l10n_pa_origin_cufe),
            is_debit_note=bool(self.debit_origin_id),
        )
        # The CUFE is hashed over the emission *date*; the XML must
        # carry a `dFechaEm` whose date portion matches, otherwise
        # DGI/PAC rejects the document. Resolve the date once and
        # reuse it. `_l10n_pa_compute_cufe` uses the same expression.
        emission_date = self.invoice_date or fields.Date.context_today(self)
        general = {
            'iAmb': ambiente,
            'iTpEmis': '02' if self.l10n_pa_contingency else company.l10n_pa_sfep_emission_type or '01',
            'iDoc': doc_type,
            'dNroDF': self._l10n_pa_get_doc_number(),
            'dPtoFacDF': (company.l10n_pa_sfep_emission_point or '001').rjust(3, '0'),
            'dSeg': self.l10n_pa_security_code or generate_security_code(),
            'dFechaEm': fields.Datetime.to_datetime(emission_date),
            'iNatOp': self.l10n_pa_operation_nature or ('02' if partner.country_id.code != 'PA' else '01'),
            'iTipoOp': self.l10n_pa_operation_type or '1',
            'iDest': self.l10n_pa_operation_destination or ('2' if partner.country_id.code != 'PA' else '1'),
            'iFormCafe': company.l10n_pa_sfep_form_cafe or '1',
            'iEntCafe': company.l10n_pa_sfep_delivery_cafe or '2',
            'dEnvFe': '1',
            'iProGen': '1',
            'iTipoTranVenta': '1',
            'iTipoSuc': '1',
        }
        if self.l10n_pa_contingency:
            general['dMotCont'] = self.l10n_pa_contingency_reason or ''
        if self.l10n_pa_origin_cufe:
            general['origin_cufe'] = self.l10n_pa_origin_cufe
        if self.narration:
            general['dIntEmFe'] = self._l10n_pa_strip_html(self.narration)[:300]

        emisor = {
            'dRuc': company.vat or '',
            'dDV': company.partner_id.l10n_pa_dv or '',
            'dTipoRuc': dgi_xml.DGI_TIPO_RUC_JURIDICO if company.partner_id.is_company else dgi_xml.DGI_TIPO_RUC_NATURAL,
            'dNombEm': company.name,
            'dSucEm': (company.l10n_pa_sfep_branch or '0001').rjust(4, '0'),
            'dDirecEm': company.partner_id.contact_address_inline or '',
            'dCorElecEmi': [company.email] if company.email else [],
            'dTfnEm': [company.phone] if company.phone else [],
            'dCodAct': company.l10n_pa_business_activity_code or '',
        }
        if company.partner_id.l10n_pa_edi_location_id:
            emisor['gUbiEm'] = self._l10n_pa_location_dict(company.partner_id.l10n_pa_edi_location_id)

        receptor = self._l10n_pa_build_receptor_dict(partner)

        product_lines = self.invoice_line_ids.filtered(
            lambda line: line.display_type == 'product'
        )
        items = [
            self._l10n_pa_build_item_dict(line, idx)
            for idx, line in enumerate(product_lines, start=1)
        ]
        if not items:
            raise UserError(_(
                "La factura debe tener al menos una línea de producto/servicio "
                "para generar el XML DGI."
            ))

        totales = self._l10n_pa_build_totales_dict()

        return {
            'cufe': cufe,
            'general': general,
            'emisor': emisor,
            'receptor': receptor,
            'items': items,
            'totales': totales,
        }

    def _l10n_pa_build_receptor_dict(self, partner) -> dict:
        receptor = {
            'iTipoRec': partner.l10n_pa_receiver_type or '02',
            'dNombRec': partner.name or 'Consumidor Final',
            'cPaisRec': _country_alpha3(partner.country_id, 'PAN'),
            'dDirecRec': partner.contact_address_inline or '',
            'dCorElecRec': [partner.email] if partner.email else [],
            'dTfnRec': [partner.phone] if partner.phone else [],
        }
        if partner.vat and partner.country_id and partner.country_id.code == 'PA':
            receptor.update({
                'dRuc': partner.vat,
                'dDV': partner.l10n_pa_dv or '',
                'dTipoRuc': dgi_xml.DGI_TIPO_RUC_JURIDICO if partner.is_company else dgi_xml.DGI_TIPO_RUC_NATURAL,
            })
        elif partner.vat:
            receptor['gIdExtType'] = {
                'dIdExt': partner.vat,
                'dPaisExt': _country_alpha3(partner.country_id, ''),
            }
        return receptor

    @staticmethod
    def _l10n_pa_location_dict(location) -> dict:
        return {
            'dCodUbi': location.code or '',
            'dCorreg': location.township or '',
            'dDistr': location.district or '',
            'dProv': location.province or '',
        }

    def _l10n_pa_build_item_dict(self, line, sec_item: int) -> dict:
        # Resolve the ITBMS rate from the line's taxes. Take the first
        # tax in the ITBMS family.
        itbms_tax = line.tax_ids.filtered(
            lambda t: t.tax_group_id and 'ITBMS' in (t.tax_group_id.name or '')
        )[:1]
        rate = itbms_tax.amount if itbms_tax else 0.0
        product = line.product_id
        template = product.product_tmpl_id if product else False
        cpbs = template and (
            template.l10n_pa_edi_cpbs_id or template.categ_id.l10n_pa_edi_cpbs_id
        )
        edi_uom = template.l10n_pa_edi_uom_id if template else False
        item = {
            'dSecItem': sec_item,
            'dDescProd': line.name or line.product_id.display_name or '',
            'dCantCodInt': line.quantity,
            'dUnidadMedida': (edi_uom.code if edi_uom else line.product_uom_id.name or '')[:20],
            'dPrUnit': line.price_unit,
            'dPrItem': line.price_subtotal,
            'dValTotItem': line.price_total,
            'tasa_itbms': dgi_xml.itbms_rate_to_code(rate),
            'valor_itbms': line.price_total - line.price_subtotal,
        }
        if cpbs:
            item['dCodCPBSAbr'] = cpbs.code
        return item

    def _l10n_pa_build_totales_dict(self) -> dict:
        product_lines = self.invoice_line_ids.filtered(
            lambda line: line.display_type == 'product'
        )
        n_items = len(product_lines)
        return {
            'dTotNeto': self.amount_untaxed,
            'dTotITBMS': self.amount_tax,
            'dVTot': self.amount_total,
            'dTotRec': self.amount_residual or self.amount_total,
            'dNroItems': n_items,
            'dVTotItems': sum(product_lines.mapped('price_total')),
            'forma_pago': [{
                'iFormaPago': '02',  # Contado as default; concrete provider may refine
                'dVlrCuota': self.amount_total,
            }],
        }

    def _l10n_pa_generate_xml(self) -> bytes:
        """Build the unsigned DGI XML for this invoice and return UTF-8 bytes."""
        self.ensure_one()
        payload = self._l10n_pa_build_xml_payload()
        return dgi_xml.render_rfe(payload, pretty=False)

    @staticmethod
    def _l10n_pa_strip_html(s: str) -> str:
        if not s:
            return ''
        try:
            return etree.HTML(s).text_content().strip()  # type: ignore[union-attr]
        except Exception:
            return s

    # -------------------------------------------------------------------
    # PAC operations
    # -------------------------------------------------------------------

    def action_l10n_pa_send_to_pac(self):
        """User-facing button: submit this invoice to the configured PAC."""
        self.ensure_one()
        if self.l10n_pa_pac_status == 'authorized':
            raise UserError(_("La factura ya fue autorizada por DGI."))
        provider = self._l10n_pa_get_pac_provider()
        if not provider:
            raise UserError(_(
                "La compañía '%(company)s' no tiene un PAC configurado.",
                company=self.company_id.name,
            ))
        if not self.l10n_pa_cufe:
            self.l10n_pa_cufe = self._l10n_pa_compute_cufe()
        self.l10n_pa_pac_status = 'sent'
        response = provider.send_invoice(self)
        self._l10n_pa_apply_pac_response(response)
        return True

    def _l10n_pa_apply_pac_response(self, response):
        """Persist a PACResponse onto this move."""
        self.ensure_one()
        self.l10n_pa_pac_response = response.raw_response or ''
        if response.success:
            self.l10n_pa_pac_status = 'authorized'
            if response.cufe:
                self.l10n_pa_cufe = response.cufe
            if response.qr_payload:
                self.l10n_pa_qr_payload = response.qr_payload
            if response.authorized_xml:
                self._l10n_pa_store_xml_attachment(response.authorized_xml)
        else:
            self.l10n_pa_pac_status = 'rejected'
            self.l10n_pa_pac_error_codes = ', '.join(
                e.get('code', '') for e in (response.errors or []) if e.get('code')
            )
            messages = []
            for e in response.errors or []:
                if e.get('message'):
                    messages.append(f"{e.get('code', '')}: {e['message']}")
                elif e.get('code'):
                    messages.append(self.env['l10n_pa_edi.dgi.error.code'].resolve(e['code']))
            raise UserError(_(
                "El PAC rechazó la factura:\n%(errors)s",
                errors='\n'.join(messages) if messages else _("Sin mensaje de error específico."),
            ))

    def _l10n_pa_store_xml_attachment(self, xml_string: str):
        """Save the (signed/authorized) XML as an ir.attachment on this move."""
        self.ensure_one()
        attachment = self.env['ir.attachment'].create({
            'name': f"{(self.name or 'factura').replace('/', '_')}.xml",
            'type': 'binary',
            'raw': xml_string.encode('utf-8') if isinstance(xml_string, str) else xml_string,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/xml',
        })
        self.l10n_pa_xml_attachment_id = attachment.id
        return attachment

    def action_l10n_pa_query_status(self):
        """Refresh PAC status by querying the provider."""
        self.ensure_one()
        provider = self._l10n_pa_get_pac_provider()
        if not provider:
            raise UserError(_("No hay PAC configurado."))
        if not self.l10n_pa_cufe:
            raise UserError(_("Esta factura no tiene un CUFE para consultar."))
        status = provider.get_status(self.l10n_pa_cufe)
        self.l10n_pa_pac_response = status.raw_response or ''
        if status.state in ('authorized', 'rejected', 'cancelled'):
            self.l10n_pa_pac_status = status.state
        return True

    def action_l10n_pa_cancel_with_pac(self):
        """Register an Anulación event with the PAC."""
        self.ensure_one()
        if self.l10n_pa_pac_status != 'authorized':
            raise UserError(_("Solo facturas autorizadas pueden ser anuladas en DGI."))
        provider = self._l10n_pa_get_pac_provider()
        if not provider:
            raise UserError(_("No hay PAC configurado."))
        reason = self.env.context.get('l10n_pa_cancel_reason') or _("Anulación solicitada por el contribuyente")
        response = provider.cancel_invoice(self, reason)
        if response.success:
            self.l10n_pa_pac_status = 'cancelled'
        else:
            raise UserError(_(
                "DGI rechazó la anulación: %(msg)s",
                msg=response.pac_status_message or _("sin detalles"),
            ))
        return True
