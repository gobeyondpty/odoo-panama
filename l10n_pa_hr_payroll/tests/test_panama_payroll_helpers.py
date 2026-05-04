"""Smoke tests for the Odoo-side mixin. Each call is a thin pass-through;
the math is exercised in tests/test_calculations.py against primary text.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPanamaPayrollHelpers(TransactionCase):
    def test_regular_helpers(self):
        helper = self.env["l10n.pa.hr.payroll.mixin"]

        # CSS regular — Ley 51/2005 art. 96 num. 1, 2.
        self.assertEqual(helper.css_employee(1000.0), 97.5)
        self.assertEqual(helper.css_employer(1000.0), 132.5)
        self.assertEqual(helper.css_employer_rate_for_date("2026-01-01"), 0.1325)

        # CSS décimo — art. 96 num. 4, 5.
        self.assertEqual(helper.css_employee_decimo(1000.0), 72.5)
        self.assertEqual(helper.css_employer_decimo(1000.0), 107.5)

        # Seguro Educativo — Ley 13/1987.
        self.assertEqual(helper.educational_insurance_employee(1000.0), 12.5)
        self.assertEqual(helper.educational_insurance_employer(1000.0), 15.0)
        self.assertEqual(helper.educational_insurance_employee_decimo(1000.0), 0.0)
        self.assertEqual(helper.educational_insurance_employer_decimo(1000.0), 0.0)

        # Riesgos Profesionales — DG 68/1970 art. 51.
        self.assertEqual(helper.professional_risk_rate_from_grade(8), 0.0056)
        self.assertEqual(helper.professional_risk_employer_from_grade(1000.0, 8), 5.6)
        self.assertEqual(helper.professional_risk_employer(1000.0, 0.0098), 9.8)

    def test_isr_and_liquidation(self):
        helper = self.env["l10n.pa.hr.payroll.mixin"]

        # DGI eTax2 Privado: ×13 / ÷13. $1,000 → $23.08.
        self.assertEqual(helper.monthly_income_tax(1000.0), 23.08)
        self.assertEqual(helper.annual_income_tax(20000.0), 1350.0)

        # Cód. Fiscal art. 701 lit. j.
        self.assertEqual(helper.liquidation_isr(20000, 5), 450.0)

        # Cód. Fiscal art. 701 lit. l.
        self.assertEqual(helper.annual_representation_tax(20000), 2000.0)
        self.assertEqual(helper.monthly_representation_tax(2000), 200.0)

    def test_accruals_and_payouts(self):
        helper = self.env["l10n.pa.hr.payroll.mixin"]

        # Ley 8/1981.
        self.assertEqual(helper.decimo_accrual(1200.0), 100.0)

        # CT art. 54.
        self.assertEqual(helper.vacation_accrual(1100.0), 100.0)
        self.assertEqual(helper.vacation_base(900.0, 1000.0), 1000.0)

        # CT art. 224 + Ley 44/1995 art. 229-B.
        self.assertEqual(helper.seniority_premium_accrual(2080.0), 40.0)
        self.assertAlmostEqual(helper.prima_antiguedad_payout(1000.0, 1), 230.77, places=2)

        # CT art. 225 lit. C.
        self.assertAlmostEqual(helper.indemnization_payout(1000.0, 5), 5 * 3.4 * (1000 * 3 / 13), places=2)

        # Ley 44/1995 art. 229-B (componente indemnización).
        first = helper.cesantia_indemnization_accrual(1000.0, 5)
        after = helper.cesantia_indemnization_accrual(1000.0, 11)
        self.assertGreater(first, after)

    def test_overtime_and_surcharges(self):
        helper = self.env["l10n.pa.hr.payroll.mixin"]

        # CT arts. 33, 48, 49, 50.
        self.assertAlmostEqual(helper.hourly_rate(2080.0), 10.0)
        self.assertEqual(helper.overtime_pay(2080.0, 1, 0.25), 12.50)
        self.assertEqual(helper.overtime_pay(2080.0, 1, 0.50), 15.00)
        self.assertEqual(helper.overtime_pay(2080.0, 1, 0.75), 17.50)
        self.assertEqual(helper.rest_day_pay(2080.0, 1), 15.00)
        self.assertEqual(helper.holiday_pay(2080.0, 1), 25.00)
        self.assertEqual(helper.combined_surcharge_pay(2080.0, 1, 0.50, 0.25), 18.75)
