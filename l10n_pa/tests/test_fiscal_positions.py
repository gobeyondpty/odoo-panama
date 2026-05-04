# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Tests for the six Panama fiscal positions."""
from odoo.tests.common import TransactionCase, tagged


@tagged('-at_install', 'post_install', 'l10n_pa')
class TestFiscalPositions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.country_pa = cls.env.ref('base.pa')

    def _company_with_pa_chart(self):
        """Helper: return a company with the PA chart loaded."""
        company = self.env['res.company'].create({
            'name': 'Test PA Co',
            'country_id': self.country_pa.id,
            'currency_id': self.env.ref('base.USD').id,
        })
        self.env['account.chart.template'].try_loading('pa', company=company, install_demo=False)
        return company

    def test_six_fiscal_positions_loaded(self):
        company = self._company_with_pa_chart()
        FiscalPosition = self.env['account.fiscal.position'].with_company(company)
        positions = FiscalPosition.search([('company_id', '=', company.id)])
        names = sorted(positions.mapped('name'))
        # The six positions defined by the plan, by name fragment.
        for fragment in (
            'Contribuyente Inscrito',
            'Consumo Final',
            'Zona Libre',
            'Exento de ITBMS',
            'Gobierno',
            'Extranjero',
        ):
            matched = [n for n in names if fragment in n]
            self.assertTrue(
                matched,
                f"Fiscal position matching {fragment!r} should exist; got {names}",
            )

    def test_fiscal_positions_have_country_pa(self):
        """All PA fiscal positions are scoped to Panama (or worldwide for
        the export one)."""
        company = self._company_with_pa_chart()
        FiscalPosition = self.env['account.fiscal.position'].with_company(company)
        positions = FiscalPosition.search([('company_id', '=', company.id)])
        for fp in positions:
            # 'Extranjero' is intentionally country_id=False (worldwide).
            if 'Extranjero' in fp.name:
                self.assertFalse(fp.country_id)
            else:
                self.assertEqual(fp.country_id, self.country_pa)

    def test_fiscal_positions_auto_apply(self):
        company = self._company_with_pa_chart()
        FiscalPosition = self.env['account.fiscal.position'].with_company(company)
        positions = FiscalPosition.search([('company_id', '=', company.id)])
        for fp in positions:
            self.assertTrue(
                fp.auto_apply,
                f"Fiscal position {fp.name!r} should be auto_apply=True",
            )
