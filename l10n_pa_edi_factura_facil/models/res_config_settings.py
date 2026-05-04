# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Settings UI for the Factura Fácil PAC integration.

Exposes the credentials and endpoint overrides as `res.config.settings`
fields backed by `ir.config_parameter` records (per Section 8.5 of the
plan). Also extends the company-level PAC selection to include
`'factura_facil'` and registers the provider class on
`account.move._l10n_pa_provider_registry()`.
"""
from odoo import api, fields, models

from ..pac_providers.factura_facil import (
    DEFAULT_QA_BASE_URL,
    DEFAULT_PROD_BASE_URL,
    FacturaFacilProvider,
)


class ResCompany(models.Model):
    _inherit = 'res.company'

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
        string="Factura Fácil — URL Base (QA)",
        config_parameter='l10n_pa_edi.factura_facil.base_url',
        default=DEFAULT_QA_BASE_URL,
        help="URL base del backend QA de Factura Fácil. Cambie sólo si "
             "el proveedor le indica un endpoint específico.",
    )
    l10n_pa_factura_facil_base_url_prod = fields.Char(
        string="Factura Fácil — URL Base (Producción)",
        config_parameter='l10n_pa_edi.factura_facil.base_url_prod',
        default=DEFAULT_PROD_BASE_URL,
        help="URL base del backend de producción de Factura Fácil.",
    )
    l10n_pa_factura_facil_api_key = fields.Char(
        string="Factura Fácil — API Key",
        config_parameter='l10n_pa_edi.factura_facil.api_key',
        help="Token Bearer asignado por Factura Fácil al contribuyente. "
             "No se imprime en logs ni en respuestas API.",
    )
    l10n_pa_factura_facil_timeout = fields.Integer(
        string="Factura Fácil — Timeout HTTP (s)",
        config_parameter='l10n_pa_edi.factura_facil.timeout',
        default=30,
        help="Tiempo de espera HTTP en segundos para llamadas al PAC.",
    )
