# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pa_business_activity_code = fields.Char(
        string="Código de Actividad Económica (DGI)",
        size=6,
        help="Código de actividad económica asignado por DGI a la "
             "empresa, usado en la Ficha Técnica de la Factura "
             "Electrónica (CIIU/CAE).",
    )
