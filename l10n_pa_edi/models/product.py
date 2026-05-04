# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Product extensions for Panama electronic invoicing catalogs."""
from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    l10n_pa_edi_cpbs_id = fields.Many2one(
        'l10n_pa_edi.cpbs',
        string="CPBS por defecto",
        help="Código CPBS usado como fallback para productos de esta categoría.",
    )


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    l10n_pa_edi_cpbs_id = fields.Many2one(
        'l10n_pa_edi.cpbs',
        string="CPBS",
        help="Código de la Codificación Panameña de Bienes y Servicios para FE.",
    )
    l10n_pa_edi_uom_id = fields.Many2one(
        'l10n_pa_edi.uom',
        string="Unidad FE",
        help="Unidad de medida homologada para factura electrónica.",
    )
