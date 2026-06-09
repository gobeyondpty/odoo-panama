# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Hook the Panama PAC delivery into Odoo 19's `account.move.send` framework.

Registers the `pa_dgi` extra-EDI key. When an Odoo user sends an invoice
and the partner's company-country is Panama with a configured PAC,
"Send to DGI" appears as an option in the send wizard.

Reference: <https://www.odoo.com/documentation/19.0/applications/finance/accounting/customer_invoices/electronic_invoicing.html>
"""
from __future__ import annotations

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    @api.model
    def _is_pa_dgi_applicable(self, move) -> bool:
        """Check whether DGI submission applies to this move.

        Applicable when the move's company is in Panama, has a PAC
        configured, and the move is a sale-side invoice or refund.
        """
        if move.country_code != 'PA':
            return False
        if move.move_type not in ('out_invoice', 'out_refund'):
            return False
        provider = move.company_id.l10n_pa_pac_provider
        return bool(provider) and provider != 'none'

    def _get_all_extra_edis(self) -> dict:
        # EXTENDS 'account'
        res = super()._get_all_extra_edis()
        res['pa_dgi'] = {
            'label': _("Send to DGI"),
            'is_applicable': self._is_pa_dgi_applicable,
            'help': _(
                "Send this invoice to the configured PAC to obtain its "
                "DGI Unique Electronic Invoice Code (CUFE)."
            ),
        }
        return res

    @api.model
    def _get_alerts(self, moves, moves_data):
        # EXTENDS 'account'
        alerts = super()._get_alerts(moves, moves_data)
        pa_moves = moves.filtered(
            lambda m: 'pa_dgi' in moves_data[m].get('extra_edis', set())
        )
        if not pa_moves:
            return alerts
        # Pre-flight checks: company RUC/DV, partner RUC if non-final-consumer.
        problems = []
        for m in pa_moves:
            if not m.company_id.vat:
                problems.append(_(
                    "%(name)s: company %(co)s has no RUC.",
                    name=m.display_name, co=m.company_id.name,
                ))
            if m.company_id.vat and not m.company_id.partner_id.l10n_pa_dv:
                problems.append(_(
                    "%(name)s: company %(co)s has a RUC without a calculated DV.",
                    name=m.display_name, co=m.company_id.name,
                ))
            partner = m.commercial_partner_id
            if partner.l10n_pa_receiver_type in ('01', '03') and not partner.vat:
                problems.append(_(
                    "%(name)s: recipient '%(p)s' is classified as Taxpayer/Government and requires a RUC.",
                    name=m.display_name, p=partner.name,
                ))
        if problems:
            alerts['l10n_pa_edi_preflight'] = {
                'message': _(
                    "The following invoices cannot be sent to DGI until they are corrected:\n%(items)s",
                    items='\n'.join(f"- {p}" for p in problems),
                ),
                'level': 'danger',
            }
        return alerts

    def _hook_invoice_document_before_pdf_report_render(self, invoice, invoice_data):
        # EXTENDS 'account'
        super()._hook_invoice_document_before_pdf_report_render(invoice, invoice_data)
        if 'pa_dgi' not in invoice_data.get('extra_edis', set()):
            return
        if invoice.l10n_pa_pac_status == 'authorized':
            # Already authorized; just attach the existing XML to the email.
            return
        provider = invoice._l10n_pa_get_pac_provider()
        if not provider:
            invoice_data['error'] = {
                'error_title': _("PAC Not Configured"),
                'errors': [_("The company has no PAC provider selected.")],
            }
            return
        try:
            if not invoice.l10n_pa_cufe:
                invoice.l10n_pa_cufe = invoice._l10n_pa_compute_cufe()
            invoice.l10n_pa_pac_status = 'sent'
            invoice.l10n_pa_pac_send_count += 1
            invoice.l10n_pa_pac_last_attempt = fields.Datetime.now()
            invoice._l10n_pa_log_pac_event('send', 'sent')
            response = provider.send_invoice(invoice)
            if response.success:
                invoice._l10n_pa_apply_pac_response(response, operation='send')
            else:
                # Persist the rejection on the move so the form mirrors
                # what the wizard reports. Otherwise the move stays at
                # 'sent' and the user has no record of the failure.
                invoice.l10n_pa_pac_status = 'rejected'
                invoice.l10n_pa_pac_response = response.raw_response or ''
                invoice.l10n_pa_pac_error_codes = ', '.join(
                    e.get('code', '') for e in (response.errors or []) if e.get('code')
                )
                invoice._l10n_pa_log_pac_event('send', 'rejected', response=response)
                error_lines = [
                    line for line in (
                        invoice._l10n_pa_format_pac_error(e)
                        for e in (response.errors or [])
                    ) if line
                ]
                invoice_data['error'] = {
                    'error_title': _("DGI rejected the invoice"),
                    'errors': error_lines or [_("No PAC details.")],
                }
        except UserError as e:
            invoice.l10n_pa_pac_status = 'rejected'
            invoice._l10n_pa_log_pac_event('send', 'error', message=e.args[0])
            invoice_data['error'] = {
                'error_title': _("Error sending to the PAC"),
                'errors': [e.args[0]],
            }
            _logger.warning("Pa DGI send failed for %s: %s", invoice.name, e)

    def _get_invoice_extra_attachments(self, move):
        # EXTENDS 'account'
        # Keep the authorized DGI XML on the invoice for internal audit
        # purposes, but do not expose it through customer-facing invoice
        # email attachments or portal downloads. The customer receives the
        # standard invoice PDF with the embedded CAFE/QR validation block.
        return super()._get_invoice_extra_attachments(move)
