# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""DGI Form 43 — Informe de Compras e Importaciones.

Generates the tab-separated TXT file that the DGI eTax2 portal accepts
for the monthly purchases/imports declaration. Per the official Form 43
help reference (`etax2.mef.gob.pa/etax2web/microayudas/Ayuda_Informes/F43hlp.htm`)
the columns are: entity type, vat (RUC), DV, name, supplier invoice
number, date (AAAAMMDD), concept (1-7), purchase source (1=Locales,
2=Importaciones), subtotal, tax.

Filing window: monthly, before the last day of the following month.
Threshold: ITBMS contributors with prior-year gross income >= B/.1,000,000
or total assets >= B/.3,000,000.
"""
import base64
import calendar
import csv
import io
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError


def _previous_month_range(today=None):
    """Return (first_day, last_day) of the calendar month before ``today``.

    Form 43 is filed monthly for the *prior* period, so this is the
    expected default range when the wizard opens.
    """
    today = today or date.today()
    if today.month == 1:
        year, month = today.year - 1, 12
    else:
        year, month = today.year, today.month - 1
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


F43_COLUMNS = (
    'entity', 'vat', 'dv', 'name', 'supplier_invoice_number',
    'date', 'concept', 'type', 'subtotal', 'tax',
)


def _entity_from_partner(partner):
    """Map a partner to the DGI Form 43 entity classification.

    Order of resolution:
      1. Explicit `l10n_pa_entity_type` on the partner if set
         (provided by `l10n_pa_account_withholding`).
      2. Country-based fallback: foreign partners → 'E'.
      3. ID-type fallback: companies with RUC → 'J'; otherwise 'N'.
    """
    explicit = getattr(partner, 'l10n_pa_entity_type', False)
    if explicit:
        return explicit
    if partner.country_id and partner.country_id.code != 'PA':
        return 'E'
    if partner.is_company:
        return 'J'
    return 'N'


class L10nPaForm43Wizard(models.TransientModel):
    _name = 'l10n_pa.form43.wizard'
    _description = 'Asistente Formulario 43 (Informe de Compras e Importaciones)'

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
        [('draft', 'Borrador'), ('done', 'Generado'), ('empty', 'Sin movimientos')],
        default='draft',
    )
    file_data = fields.Binary(readonly=True)
    file_name = fields.Char(readonly=True)
    invoice_count = fields.Integer(readonly=True)
    missing_concept_count = fields.Integer(
        readonly=True,
        help="Facturas en el rango sin concepto F43 asignado. "
             "Se omiten del informe.",
    )

    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        for wiz in self:
            if wiz.date_from and wiz.date_to and wiz.date_from > wiz.date_to:
                raise UserError(_("La fecha inicial debe ser anterior o igual a la fecha final."))

    def action_generate(self):
        self.ensure_one()
        moves = self._collect_moves()
        if not moves:
            self.state = 'empty'
            return self._return_form()

        rows, missing = self._build_rows(moves)
        self.missing_concept_count = missing
        if not rows:
            self.state = 'empty'
            return self._return_form()

        ruc = (self.company_id.vat or 'sin-ruc').replace('-', '').replace(' ', '')
        period = self.date_from.strftime('%Y%m')
        self.file_name = f"Informe43_{ruc}_{period}.txt"
        self.file_data = self._encode_tsv(rows)
        self.invoice_count = len(rows)
        self.state = 'done'
        return self._return_form()

    def _collect_moves(self):
        """Posted vendor bills/refunds for the company in the date range."""
        return self.env['account.move'].search([
            ('company_id', '=', self.company_id.id),
            ('move_type', 'in', ('in_invoice', 'in_refund')),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
        ])

    def _build_rows(self, moves):
        rows = []
        missing = 0
        for move in moves:
            concept = getattr(move, 'l10n_pa_f43_concept', False)
            if not concept:
                missing += 1
                continue
            partner = move.commercial_partner_id
            subtotal, tax = self._move_amounts(move)
            rows.append({
                'entity': _entity_from_partner(partner),
                'vat': (partner.vat or '').replace('-', '').replace(' ', ''),
                'dv': getattr(partner, 'l10n_pa_dv', '') or '',
                'name': partner.name or '',
                'supplier_invoice_number': move.ref or move.name or '',
                'date': fields.Date.to_date(move.invoice_date).strftime('%Y%m%d'),
                'concept': concept,
                'type': getattr(move, 'l10n_pa_f43_purchase_source', '1') or '1',
                'subtotal': f"{subtotal:.2f}",
                'tax': f"{tax:.2f}",
            })
        return rows, missing

    def _is_itbms_tax(self, tax):
        """Return whether ``tax`` is one of the Panama ITBMS purchase taxes.

        Chart-template loading creates company-specific tax groups, so the
        template XMLIDs are not reliable on posted move lines. Match the
        statutory ITBMS purchase taxes by country, use, and current rates.
        """
        return (
            tax
            and tax.country_id.code == 'PA'
            and tax.type_tax_use == 'purchase'
            and tax.amount_type == 'percent'
            and tax.amount in (0.0, 7.0, 10.0, 15.0)
        )

    def _move_amounts(self, move):
        """Return (subtotal, itbms) for a move in company currency.

        - Subtotal uses ``amount_untaxed_signed`` so foreign-currency bills
          are reported at the posted company-currency value. The accounting
          sign is then flipped so ordinary purchases (in_invoice) appear
          positive and refunds (in_refund) appear negative — matching what
          DGI Form 43 expects for the period total.
        - ITBMS sums tax lines whose tax_group is one of the four Panama
          ITBMS groups (0/7/10/15). Other purchase taxes — import duties,
          custom levies, and the withholding taxes added by
          ``l10n_pa_account_withholding`` — are excluded so they don't
          inflate the ITBMS column.
        """
        subtotal = -move.amount_untaxed_signed
        itbms = sum(
            line.balance
            for line in move.line_ids
            if line.tax_line_id
            and self._is_itbms_tax(line.tax_line_id)
        )
        return subtotal, itbms

    def _encode_tsv(self, rows):
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer, fieldnames=F43_COLUMNS, delimiter='\t', lineterminator='\n',
        )
        writer.writerows(rows)
        return base64.b64encode(buffer.getvalue().encode('utf-8'))

    def _return_form(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
