# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Settings UI and company fields for the Factura Fácil PAC integration.

* Per-company credentials (``X-FF-Company`` / ``X-FF-Branch`` /
  ``X-FF-API-Key``) live on ``res.company`` — each contribuyente is a
  separate Factura Fácil tenant.
* Endpoint URLs and HTTP timeout live in ``ir.config_parameter`` — one
  Factura Fácil deployment per Odoo instance.
"""
from odoo import api, fields, models

from ..pac_providers.factura_facil import (
    DEFAULT_PROD_BASE_URL,
    DEFAULT_QA_BASE_URL,
    FacturaFacilProvider,
)


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pa_factura_facil_company_uuid = fields.Char(
        string="Factura Fácil — Company UUID",
        help="Issuer UUID in Factura Fácil (HTTP X-FF-Company header).",
    )
    l10n_pa_factura_facil_branch_uuid = fields.Char(
        string="Factura Fácil — Branch UUID",
        help="Branch UUID in Factura Fácil (HTTP X-FF-Branch header). "
             "Optional if the API key is associated with a single branch.",
    )
    l10n_pa_factura_facil_api_key = fields.Char(
        string="Factura Fácil — API Key",
        groups='base.group_system',
        help="Factura Fácil API key (HTTP X-FF-API-Key header). "
             "It is not printed in logs.",
    )

    @api.model
    def _l10n_pa_pac_provider_selection(self):
        # EXTENDS l10n_pa_edi
        return super()._l10n_pa_pac_provider_selection() + [
            ('factura_facil', "Factura Fácil S.A."),
        ]


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _l10n_pa_provider_registry(self):
        # EXTENDS l10n_pa_edi
        registry = super()._l10n_pa_provider_registry()
        registry['factura_facil'] = FacturaFacilProvider
        return registry


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pa_factura_facil_base_url = fields.Char(
        string="Factura Fácil — Base URL (QA)",
        config_parameter='l10n_pa_edi.factura_facil.base_url',
        default=DEFAULT_QA_BASE_URL,
        help="Base URL of the Factura Fácil QA backend.",
    )
    l10n_pa_factura_facil_base_url_prod = fields.Char(
        string="Factura Fácil — Base URL (Production)",
        config_parameter='l10n_pa_edi.factura_facil.base_url_prod',
        default=DEFAULT_PROD_BASE_URL,
        help="Base URL of the Factura Fácil production backend.",
    )
    l10n_pa_factura_facil_timeout = fields.Integer(
        string="Factura Fácil — Timeout HTTP (s)",
        config_parameter='l10n_pa_edi.factura_facil.timeout',
        default=30,
        help="HTTP timeout in seconds for PAC calls.",
    )
    l10n_pa_factura_facil_company_uuid = fields.Char(
        related='company_id.l10n_pa_factura_facil_company_uuid',
        readonly=False,
        string="Factura Fácil — Company UUID",
    )
    l10n_pa_factura_facil_branch_uuid = fields.Char(
        related='company_id.l10n_pa_factura_facil_branch_uuid',
        readonly=False,
        string="Factura Fácil — Branch UUID",
    )
    l10n_pa_factura_facil_api_key = fields.Char(
        related='company_id.l10n_pa_factura_facil_api_key',
        readonly=False,
        string="Factura Fácil — API Key",
        groups='base.group_system',
    )
