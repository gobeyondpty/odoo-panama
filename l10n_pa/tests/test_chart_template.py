# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Tests for the Panama chart template loading and tax structure."""
from odoo.tests.common import TransactionCase, tagged


@tagged('-at_install', 'post_install', 'l10n_pa')
class TestChartTemplate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.country_pa = cls.env.ref('base.pa')

    def _company_with_pa_chart(self):
        company = self.env['res.company'].create({
            'name': 'Test PA Chart Co',
            'country_id': self.country_pa.id,
            'currency_id': self.env.ref('base.USD').id,
        })
        self.env['account.chart.template'].try_loading('pa', company=company, install_demo=False)
        return company

    def test_chart_template_loads(self):
        """`try_loading('pa')` succeeds and creates accounts."""
        company = self._company_with_pa_chart()
        accounts = self.env['account.account'].with_company(company).search([
            ('company_ids', 'in', company.id),
        ])
        self.assertTrue(accounts, "Loading PA chart should create accounts")

    def test_four_itbms_rates_present(self):
        """The four ITBMS rates (0%, 7%, 10%, 15%) load on both sides."""
        company = self._company_with_pa_chart()
        Tax = self.env['account.tax'].with_company(company)
        rates_seen = set()
        for tax in Tax.search([('company_id', '=', company.id)]):
            if 'ITBMS' in (tax.name or ''):
                rates_seen.add((tax.amount, tax.type_tax_use))
        for rate in (0.0, 7.0, 10.0, 15.0):
            self.assertIn(
                (rate, 'sale'), rates_seen,
                f"Sale tax for ITBMS {rate}% should be loaded",
            )
            self.assertIn(
                (rate, 'purchase'), rates_seen,
                f"Purchase tax for ITBMS {rate}% should be loaded",
            )

    def test_company_default_taxes_are_set(self):
        """Newly-loaded company has default sale/purchase taxes set to 7%."""
        company = self._company_with_pa_chart()
        company = company.with_company(company)
        self.assertTrue(company.account_sale_tax_id)
        self.assertTrue(company.account_purchase_tax_id)
        self.assertEqual(company.account_sale_tax_id.amount, 7.0)
        self.assertEqual(company.account_purchase_tax_id.amount, 7.0)

    def test_business_activity_code_field_exists(self):
        """The DGI business-activity-code field is on res.company."""
        self.assertIn('l10n_pa_business_activity_code', self.env['res.company']._fields)
