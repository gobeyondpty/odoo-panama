# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Partner postal-code helpers for Panama."""

from odoo import api, fields, models

from ..lib.postal import decode, is_in_panama


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_pa_postal_valid = fields.Boolean(
        string="Código postal PA válido",
        compute='_compute_l10n_pa_postal',
        store=True,
        help="Indica si el ZIP contiene un código postal panameño geoespacial válido.",
    )
    l10n_pa_postal_level = fields.Selection(
        [
            ('MACRO', "Macro"),
            ('MICRO', "Micro"),
            ('NANO', "Nano"),
            ('PICO', "Pico"),
        ],
        string="Precisión postal PA",
        compute='_compute_l10n_pa_postal',
        store=True,
    )
    l10n_pa_postal_precision_meters = fields.Float(
        string="Precisión postal PA (m)",
        compute='_compute_l10n_pa_postal',
        store=True,
    )
    l10n_pa_postal_latitude = fields.Float(
        string="Latitud postal PA",
        compute='_compute_l10n_pa_postal',
        store=True,
        digits=(10, 8),
    )
    l10n_pa_postal_longitude = fields.Float(
        string="Longitud postal PA",
        compute='_compute_l10n_pa_postal',
        store=True,
        digits=(11, 8),
    )
    l10n_pa_postal_estafeta_prefix = fields.Char(
        string="Prefijo estafeta PA",
        compute='_compute_l10n_pa_postal',
        store=True,
    )

    @api.depends('zip', 'country_id')
    def _compute_l10n_pa_postal(self):
        for partner in self:
            decoded = False
            if (
                partner.zip
                and (not partner.country_id or partner.country_id.code == 'PA')
            ):
                decoded = decode(partner.zip)
                if decoded and not is_in_panama(decoded.lat, decoded.lng):
                    decoded = False

            partner.l10n_pa_postal_valid = bool(decoded)
            partner.l10n_pa_postal_level = decoded.level if decoded else False
            partner.l10n_pa_postal_precision_meters = (
                decoded.precision_meters if decoded else 0.0
            )
            partner.l10n_pa_postal_latitude = decoded.lat if decoded else 0.0
            partner.l10n_pa_postal_longitude = decoded.lng if decoded else 0.0
            partner.l10n_pa_postal_estafeta_prefix = (
                decoded.estafeta_prefix if decoded else False
            )
