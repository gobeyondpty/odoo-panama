# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""DGI error code lookup with Spanish user-facing messages.

Codes are sourced from DGI Ficha Técnica PAC v1.00 (April 2025) and
the field-level error catalog. Loaded as `l10n_pa_edi.dgi.error.code`
records via `data/dgi_error_code_data.xml`. This module exposes a
helper to resolve a code to its localized message.
"""
from odoo import _, api, fields, models


class L10nPaEdiDgiErrorCode(models.Model):
    _name = 'l10n_pa_edi.dgi.error.code'
    _description = "DGI Error Code"
    _rec_name = 'code'

    code = fields.Char(string="Código DGI", required=True, index=True)
    severity = fields.Selection(
        [
            ('error', "Error"),
            ('warning', "Advertencia"),
            ('info', "Información"),
        ],
        default='error',
        required=True,
    )
    short_message = fields.Char(string="Mensaje corto", translate=True)
    description = fields.Text(string="Descripción", translate=True)

    _code_unique = models.Constraint(
        'unique(code)',
        "El código DGI debe ser único.",
    )

    @api.model
    def resolve(self, code: str) -> str:
        """Return the localized Spanish message for `code`, or the raw code."""
        if not code:
            return ''
        rec = self.search([('code', '=', code)], limit=1)
        if not rec:
            return _("DGI %(code)s (sin descripción local)", code=code)
        return f"DGI {rec.code}: {rec.short_message or rec.description or ''}"
