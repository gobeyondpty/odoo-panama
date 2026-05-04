# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class L10nPaEdiPacEvent(models.Model):
    _name = 'l10n_pa_edi.pac.event'
    _description = 'Panama PAC Event'
    _order = 'create_date desc, id desc'

    move_id = fields.Many2one(
        'account.move',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        index=True,
    )
    operation = fields.Selection(
        [
            ('send', 'Envío'),
            ('status', 'Consulta'),
            ('cancel', 'Anulación'),
        ],
        required=True,
    )
    state = fields.Selection(
        [
            ('sent', 'Enviado'),
            ('authorized', 'Autorizado'),
            ('rejected', 'Rechazado'),
            ('cancelled', 'Anulado'),
            ('pending', 'Pendiente'),
            ('unknown', 'Desconocido'),
            ('error', 'Error'),
        ],
        required=True,
    )
    pac_status_code = fields.Char()
    pac_status_message = fields.Char()
    error_codes = fields.Char()
    raw_response = fields.Text()
