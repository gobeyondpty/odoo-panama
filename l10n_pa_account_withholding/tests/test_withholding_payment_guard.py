# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWithholdingPaymentGuard(TransactionCase):
    """A payment carrying withholding lines must not be allowed on a
    journal whose payment method has no outstanding account: in that
    flow the payment never generates a journal entry and the retention
    silently ends up in the bank suspense account at reconciliation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Test PA WH Guard Co',
            'country_id': cls.env.ref('base.pa').id,
            'currency_id': cls.env.ref('base.USD').id,
        })
        cls.env['account.chart.template'].try_loading(
            'pa', company=cls.company, install_demo=False)
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente PA',
            'country_id': cls.env.ref('base.pa').id,
            'is_company': True,
        })
        ChartTemplate = cls.env['account.chart.template'].with_company(cls.company)
        cls.tax_itbms_7 = ChartTemplate.ref('tax_pa_itbms_07_sale')
        cls.tax_tarjeta = ChartTemplate.ref('tax_pa_wht_itbms_e_07')
        cls.account_itbms_payable = ChartTemplate.ref('231')
        cls.journal = cls.env['account.journal'].search([
            *cls.env['account.journal']._check_company_domain(cls.company),
            ('type', '=', 'bank'),
        ], limit=1)
        cls.method_line = cls.journal.inbound_payment_method_line_ids.filtered(
            lambda line: line.code == 'manual')

        invoice = cls.env['account.move'].with_company(cls.company).create({
            'move_type': 'out_invoice',
            'partner_id': cls.partner.id,
            'company_id': cls.company.id,
            'invoice_line_ids': [Command.create({
                'name': 'Venta gravada cobrada con tarjeta',
                'quantity': 1,
                'price_unit': 100.0,
                'tax_ids': [Command.set(cls.tax_itbms_7.ids)],
            })],
        })
        invoice.action_post()
        cls.invoice = invoice

    def _make_register_wizard(self):
        wizard = self.env['account.payment.register'].with_company(self.company).with_context(
            active_model='account.move',
            active_ids=self.invoice.ids,
        ).create({'journal_id': self.journal.id})
        wizard.withholding_line_ids = [Command.create({
            'tax_id': self.tax_tarjeta.id,
            'base_amount': 100.0,
            'account_id': self.account_itbms_payable.id,
            'name': 'LIQ-TEST-001',
        })]
        return wizard

    def test_payment_without_outstanding_account_is_blocked(self):
        self.method_line.payment_account_id = False
        wizard = self._make_register_wizard()
        with self.assertRaises(ValidationError):
            wizard.action_create_payments()

    def test_payment_with_outstanding_account_posts_withholding(self):
        outstanding = self.env['account.account'].with_company(self.company).create({
            'name': 'Outstanding Receipts (test)',
            'code': '111.090',
            'account_type': 'asset_current',
            'reconcile': True,
        })
        self.method_line.payment_account_id = outstanding
        wizard = self._make_register_wizard()
        wizard.action_create_payments()
        payment = self.env['account.payment'].search([
            ('partner_id', '=', self.partner.id),
            ('company_id', '=', self.company.id),
        ], order='id desc', limit=1)
        self.assertTrue(payment.move_id, "Payment must generate a journal entry")
        retention_lines = payment.move_id.line_ids.filtered(
            lambda line: line.account_id == self.account_itbms_payable and line.debit == 3.5)
        self.assertEqual(
            len(retention_lines), 1,
            "The 3.50 retention (50%% of the 7.00 ITBMS) must hit the withholding account",
        )
        self.assertIn(self.invoice.payment_state, ('in_payment', 'paid'))
        self.assertEqual(self.invoice.amount_residual, 0.0)
