# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Partner extensions for Panama electronic invoicing.

Adds the receiver-type classification (`iTipoRec` per DGI Ficha Técnica)
that the XML generator uses to populate the `<gDatRec>` block.
"""
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_pa_receiver_type = fields.Selection(
        [
            ('01', "Contribuyente"),
            ('02', "Consumidor Final"),
            ('03', "Gobierno"),
            ('04', "Extranjero"),
        ],
        string="Tipo de Receptor (DGI)",
        compute='_compute_l10n_pa_receiver_type',
        store=True,
        readonly=False,
        help="Clasificación del receptor según DGI (campo iTipoRec).",
    )

    @api.depends('country_id', 'is_company', 'l10n_latam_identification_type_id', 'vat')
    def _compute_l10n_pa_receiver_type(self):
        """Default the receiver type from country, ID type, and VAT.

        Detection rules:
          - Foreign country → Extranjero ('04')
          - Panama with NT (Número Tributario) ID type → Gobierno ('03')
          - Panama with RUC + matching identification type → Contribuyente ('01')
          - Otherwise → Consumidor Final ('02')

        The field is ``readonly=False`` so users can override the computed
        value manually, but the compute fully drives the value whenever
        any dependency changes. Manual overrides are not sticky across
        dependency edits — duplicate the partner or correct the data
        instead. For non-NT government partners, set the identification
        type to NT (or extend this method) rather than overriding the
        receiver type by hand.
        """
        ruc_type = self.env.ref('l10n_pa.ruc', raise_if_not_found=False)
        nt_type = self.env.ref('l10n_pa.nt', raise_if_not_found=False)
        for partner in self:
            if partner.country_id and partner.country_id.code != 'PA':
                partner.l10n_pa_receiver_type = '04'  # Extranjero
                continue
            if nt_type and partner.l10n_latam_identification_type_id == nt_type:
                partner.l10n_pa_receiver_type = '03'  # Gobierno
                continue
            if not partner.vat:
                partner.l10n_pa_receiver_type = '02'  # Consumidor Final
                continue
            if ruc_type and partner.l10n_latam_identification_type_id == ruc_type:
                partner.l10n_pa_receiver_type = '01'  # Contribuyente
            else:
                partner.l10n_pa_receiver_type = '02'  # default to Consumo Final
