# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Product extensions for Panama electronic invoicing catalogs."""
from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    l10n_pa_edi_cpbs_id = fields.Many2one(
        'l10n_pa_edi.cpbs',
        string="Default CPBS",
        help="CPBS code used as a fallback for products in this category.",
    )


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    l10n_pa_edi_cpbs_id = fields.Many2one(
        'l10n_pa_edi.cpbs',
        string="CPBS",
        help="Panama Goods and Services Coding code for electronic invoicing.",
    )
    l10n_pa_edi_uom_id = fields.Many2one(
        'l10n_pa_edi.uom',
        string="Electronic Invoice Unit",
        help="Unit of measure approved for electronic invoicing.",
    )
