# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestForm43Wizard(TransactionCase):
    """Smoke tests for the DGI Form 43 (Informe de Compras) wizard.

    Verifies that the TXT export contains rows in the expected
    tab-separated layout and skips moves that are missing the F43
    concept classification.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.country_pa = cls.env.ref('base.pa')
        cls.id_ruc = cls.env.ref('l10n_pa.ruc')

        cls.company = cls.env['res.company'].create({
            'name': 'Test PA F43 Co',
            'country_id': cls.country_pa.id,
            'currency_id': cls.env.ref('base.USD').id,
            'vat': '155718881-2-2018',
        })
        cls.env['account.chart.template'].try_loading('pa', company=cls.company, install_demo=False)
        cls.company.partner_id.l10n_latam_identification_type_id = cls.id_ruc

        cls.supplier = cls.env['res.partner'].create({
            'name': 'Proveedor SA',
            'country_id': cls.country_pa.id,
            'vat': '8-442-445',
            'l10n_latam_identification_type_id': cls.id_ruc.id,
            'is_company': True,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Servicio',
            'list_price': 100.0,
            'type': 'service',
        })

    def _create_bill(self, *, with_concept=True, amount=100.0):
        purchase_tax = self.env['account.tax'].with_company(self.company).search([
            ('company_id', '=', self.company.id),
            ('amount', '=', 7.0),
            ('type_tax_use', '=', 'purchase'),
        ], limit=1)
        vals = {
            'move_type': 'in_invoice',
            'partner_id': self.supplier.id,
            'company_id': self.company.id,
            'invoice_date': date(2026, 4, 15),
            'ref': 'F-001',
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'name': 'Servicio',
                'quantity': 1,
                'price_unit': amount,
                'tax_ids': [(6, 0, purchase_tax.ids)],
            })],
        }
        if with_concept:
            vals['l10n_pa_f43_concept'] = '3'  # Servicios (honorarios, etc.)
            vals['l10n_pa_f43_purchase_source'] = '1'  # Locales
        bill = self.env['account.move'].with_company(self.company).create(vals)
        bill.action_post()
        return bill

    def test_empty_when_no_bills(self):
        wiz = self.env['l10n_pa.form43.wizard'].with_company(self.company).create({
            'company_id': self.company.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
        })
        wiz.action_generate()
        self.assertEqual(wiz.state, 'empty')
        self.assertFalse(wiz.file_data)

    def test_export_skips_bills_without_concept(self):
        self._create_bill(with_concept=False)
        wiz = self.env['l10n_pa.form43.wizard'].with_company(self.company).create({
            'company_id': self.company.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
        })
        wiz.action_generate()
        self.assertEqual(wiz.missing_concept_count, 1)
        self.assertEqual(wiz.state, 'empty')

    def test_export_produces_tab_separated_row(self):
        self._create_bill()
        wiz = self.env['l10n_pa.form43.wizard'].with_company(self.company).create({
            'company_id': self.company.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
        })
        wiz.action_generate()
        self.assertEqual(wiz.state, 'done')
        self.assertEqual(wiz.invoice_count, 1)
        self.assertEqual(wiz.missing_concept_count, 0)

        decoded = base64.b64decode(wiz.file_data).decode('utf-8')
        self.assertEqual(decoded.count('\n'), 1)
        cells = decoded.rstrip('\n').split('\t')
        self.assertEqual(len(cells), 10, "F43 row must have 10 tab-separated columns")
        self.assertEqual(cells[0], 'J')  # entity
        self.assertEqual(cells[3], 'Proveedor SA')  # name
        self.assertEqual(cells[5], '20260415')  # date AAAAMMDD
        self.assertEqual(cells[6], '3')  # concept
        self.assertEqual(cells[7], '1')  # type=Locales
        self.assertEqual(cells[8], '100.00')  # subtotal
        self.assertEqual(cells[9], '7.00')  # tax

    def test_export_filename_includes_ruc_and_period(self):
        self._create_bill()
        wiz = self.env['l10n_pa.form43.wizard'].with_company(self.company).create({
            'company_id': self.company.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
        })
        wiz.action_generate()
        self.assertIn('Informe43', wiz.file_name)
        self.assertIn('202604', wiz.file_name)
        self.assertTrue(wiz.file_name.endswith('.txt'))

    def test_export_negates_refund_amounts(self):
        """Vendor refunds (in_refund) reduce the period's purchases and
        must export with negative subtotal/tax.
        """
        bill = self._create_bill()
        # Reverse it, mark the reversal with the same F43 concept, post.
        reversal_wiz = self.env['account.move.reversal'].with_context(
            active_model='account.move', active_ids=bill.ids,
        ).create({
            'reason': 'devolución parcial',
            'date': date(2026, 4, 20),
            'journal_id': bill.journal_id.id,
        })
        action = reversal_wiz.refund_moves()
        refund = self.env['account.move'].browse(action['res_id'])
        refund.l10n_pa_f43_concept = '3'
        refund.l10n_pa_f43_purchase_source = '1'
        refund.action_post()

        wiz = self.env['l10n_pa.form43.wizard'].with_company(self.company).create({
            'company_id': self.company.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
        })
        wiz.action_generate()
        decoded = base64.b64decode(wiz.file_data).decode('utf-8')
        rows = [r.split('\t') for r in decoded.rstrip('\n').split('\n')]
        self.assertEqual(len(rows), 2)
        # The refund row's subtotal/tax must be negative.
        refund_rows = [r for r in rows if r[8].startswith('-')]
        self.assertEqual(len(refund_rows), 1)
        self.assertEqual(refund_rows[0][8], '-100.00')
        self.assertEqual(refund_rows[0][9], '-7.00')

    def test_default_date_range_is_previous_month(self):
        """The wizard must default to the prior month's full range,
        not collapse to the first day of the current month.
        """
        from odoo.addons.l10n_pa_reports.wizard.form_43_wizard import _previous_month_range
        first, last = _previous_month_range(today=date(2026, 5, 4))
        self.assertEqual(first, date(2026, 4, 1))
        self.assertEqual(last, date(2026, 4, 30))
        # Year boundary
        first, last = _previous_month_range(today=date(2026, 1, 15))
        self.assertEqual(first, date(2025, 12, 1))
        self.assertEqual(last, date(2025, 12, 31))

    def test_invalid_date_range_raises(self):
        with self.assertRaises(UserError):
            self.env['l10n_pa.form43.wizard'].create({
                'company_id': self.company.id,
                'date_from': date(2026, 5, 1),
                'date_to': date(2026, 4, 1),
            })
