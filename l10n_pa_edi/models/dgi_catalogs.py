# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""DGI catalog models used by Panama electronic invoicing."""
from odoo import api, fields, models


class L10nPaEdiLocation(models.Model):
    _name = 'l10n_pa_edi.location'
    _description = 'Panama DGI Location Code'
    _rec_name = 'complete_name'
    _order = 'code'

    code = fields.Char(
        string="Código",
        required=True,
        index=True,
        help="Código unificado Provincia-Distrito-Corregimiento usado por DGI.",
    )
    province = fields.Char(string="Provincia", required=True)
    district = fields.Char(string="Distrito", required=True)
    township = fields.Char(string="Corregimiento", required=True)
    active = fields.Boolean(default=True)
    complete_name = fields.Char(compute='_compute_complete_name', store=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'El código de ubicación DGI debe ser único.',
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
        string="Código CPBS",
        required=True,
        index=True,
        help="Codificación Panameña de Bienes y Servicios usada en factura electrónica.",
    )
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    complete_name = fields.Char(compute='_compute_complete_name', store=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'El código CPBS debe ser único.',
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
        string="Código",
        required=True,
        index=True,
        help="Código de unidad de medida usado en factura electrónica.",
    )
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    complete_name = fields.Char(compute='_compute_complete_name', store=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'El código de unidad de medida DGI debe ser único.',
    )

    @api.depends('code', 'name')
    def _compute_complete_name(self):
        for rec in self:
            rec.complete_name = f"{rec.code} - {rec.name}" if rec.name else rec.code
