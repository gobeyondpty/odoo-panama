# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""DGI catalog models used by Panama electronic invoicing."""
from odoo import api, fields, models


class L10nPaEdiLocation(models.Model):
    _name = 'l10n_pa_edi.location'
    _description = 'Panama DGI Location Code'
    _rec_name = 'complete_name'
    _order = 'code'

    code = fields.Char(
        string="Code",
        required=True,
        index=True,
        help="Unified Province-District-Township code used by DGI.",
    )
    province = fields.Char(string="Province", required=True)
    district = fields.Char(string="District", required=True)
    township = fields.Char(string="Township", required=True)
    active = fields.Boolean(default=True)
    complete_name = fields.Char(compute='_compute_complete_name', store=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'The DGI location code must be unique.',
    )

    @api.depends('code', 'province', 'district', 'township')
    def _compute_complete_name(self):
        for rec in self:
            parts = [p for p in (rec.province, rec.district, rec.township) if p]
            rec.complete_name = f"{rec.code} - {' / '.join(parts)}" if parts else rec.code


class L10nPaEdiCpbs(models.Model):
    _name = 'l10n_pa_edi.cpbs'
    _description = 'Panama CPBS Code'
    _rec_name = 'complete_name'
    _order = 'code'

    code = fields.Char(
        string="CPBS Code",
        required=True,
        index=True,
        help="Panama Goods and Services Coding used in electronic invoicing.",
    )
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    complete_name = fields.Char(compute='_compute_complete_name', store=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'The CPBS code must be unique.',
    )

    @api.depends('code', 'name')
    def _compute_complete_name(self):
        for rec in self:
            rec.complete_name = f"{rec.code} - {rec.name}" if rec.name else rec.code


class L10nPaEdiUom(models.Model):
    _name = 'l10n_pa_edi.uom'
    _description = 'Panama DGI Unit of Measure Code'
    _rec_name = 'complete_name'
    _order = 'code'

    code = fields.Char(
        string="Code",
        required=True,
        index=True,
        help="Unit of measure code used in electronic invoicing.",
    )
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    complete_name = fields.Char(compute='_compute_complete_name', store=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'The DGI unit of measure code must be unique.',
    )

    @api.depends('code', 'name')
    def _compute_complete_name(self):
        for rec in self:
            rec.complete_name = f"{rec.code} - {rec.name}" if rec.name else rec.code
