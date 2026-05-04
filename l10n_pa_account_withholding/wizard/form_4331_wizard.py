# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
from datetime import timedelta

from odoo import _, fields, models
from odoo.exceptions import UserError


def _previous_month_range(today=None):
    today = today or fields.Date.today()
    first_this_month = today.replace(day=1)
    last_previous = first_this_month - timedelta(days=1)
    return last_previous.replace(day=1), last_previous


class L10nPaForm4331Wizard(models.TransientModel):
    _name = 'l10n.pa.form4331.wizard'
    _description = 'Exportar Formulario 4331 Retenciones ITBMS'

    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(
        required=True,
        default=lambda self: _previous_month_range()[0],
    )
    date_to = fields.Date(
        required=True,
        default=lambda self: _previous_month_range()[1],
    )
    state = fields.Selection(
        [('draft', 'Borrador'), ('empty', 'Sin datos'), ('done', 'Generado')],
        default='draft',
        readonly=True,
    )
    file_data = fields.Binary(readonly=True)
    file_name = fields.Char(readonly=True)
    line_count = fields.Integer(readonly=True)
    total_base = fields.Monetary(currency_field='currency_id', readonly=True)
    total_withheld = fields.Monetary(currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one(related='company_id.currency_id')

    def _withholding_tax_domain(self):
        return [
            *self.env['account.tax']._check_company_domain(self.company_id),
            ('is_withholding_tax_on_payment', '=', True),
            ('country_id.code', '=', 'PA'),
        ]

    def _iter_rows(self):
        self.ensure_one()
        moves = self.env['account.move'].with_company(self.company_id).search([
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
            ('move_type', 'in', ('in_invoice', 'in_refund', 'out_invoice', 'out_refund')),
        ], order='invoice_date, name, id')
        withholding_taxes = self.env['account.tax'].search(self._withholding_tax_domain())
        withholding_tax_ids = set(withholding_taxes.ids)
        for move in moves:
            for line in move.invoice_line_ids.filtered(lambda aml: aml.display_type == 'product'):
                taxes = line.tax_ids.filtered(lambda tax: tax.id in withholding_tax_ids)
                for tax in taxes:
                    base = line.price_subtotal
                    amount = round(base * abs(tax.amount) / 100.0, 2)
                    if move.move_type in ('in_refund', 'out_refund'):
                        base = -base
                        amount = -amount
                    yield {
                        'date': move.invoice_date,
                        'move': move,
                        'partner': move.commercial_partner_id,
                        'tax': tax,
                        'base': base,
                        'amount': amount,
                    }

    def _serialize_rows(self, rows):
        lines = []
        for row in rows:
            partner = row['partner']
            move = row['move']
            tax = row['tax']
            lines.append('\t'.join((
                row['date'].strftime('%Y%m%d'),
                partner.l10n_pa_entity_type or ('E' if partner.country_id.code != 'PA' else 'J'),
                partner.vat or '',
                partner.l10n_pa_dv or '',
                partner.name or '',
                move.name or move.ref or '',
                tax.description or tax.name or '',
                f"{row['base']:.2f}",
                f"{row['amount']:.2f}",
            )))
        return ('\n'.join(lines) + ('\n' if lines else '')).encode('utf-8')

    def action_generate(self):
        self.ensure_one()
        if self.date_to < self.date_from:
            raise UserError(_("Fecha hasta no puede ser anterior a fecha desde."))
        rows = list(self._iter_rows())
        if not rows:
            self.write({
                'state': 'empty',
                'file_data': False,
                'file_name': False,
                'line_count': 0,
                'total_base': 0.0,
                'total_withheld': 0.0,
            })
            return True
        payload = self._serialize_rows(rows)
        period_tag = self.date_from.strftime('%Y%m')
        self.write({
            'state': 'done',
            'file_data': base64.b64encode(payload),
            'file_name': f"Formulario4331_{self.company_id.vat or self.company_id.id}_{period_tag}.txt",
            'line_count': len(rows),
            'total_base': sum(row['base'] for row in rows),
            'total_withheld': sum(row['amount'] for row in rows),
        })
        return True
