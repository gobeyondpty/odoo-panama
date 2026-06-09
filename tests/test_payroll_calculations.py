"""Pure-Python verification of the Panama payroll formulas.

Each test asserts a *primary-source* expected value. When you change any
constant or formula, the corresponding test must fail against the old
value and pass against the statute. If a test value is *derived* (e.g.
0.003269230769 = 3.4 × (3/13) ÷ 12 × 0.05), the derivation appears in
the test docstring next to the citation.
"""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "l10n_pa_hr_payroll"))

from lib.calculations import (
    CSS_EMPLOYEE_RATE_DECIMO,
    CSS_EMPLOYER_RATE_DECIMO,
    CESANTIA_INDEMNIZATION_AFTER_TEN_RATE,
    CESANTIA_INDEMNIZATION_FIRST_TEN_RATE,
    MONTHLY_TO_WEEKLY,
    PRIMA_ANTIGUEDAD_MONTHLY_RATE,
    StatutoryRates,
    annual_income_tax,
    annual_representation_tax,
    calculate_decimo_lines,
    calculate_monthly_income_tax,
    calculate_period_income_tax,
    calculate_statutory_lines,
    cesantia_indemnization_accrual,
    combined_surcharge_pay,
    css_employee,
    css_employee_decimo,
    css_employer,
    css_employer_decimo,
    css_employer_rate_for_date,
    decimo_accrual,
    educational_insurance_employee,
    educational_insurance_employee_decimo,
    educational_insurance_employer,
    educational_insurance_employer_decimo,
    holiday_pay,
    hourly_rate,
    indemnization_payout,
    liquidation_isr,
    monthly_representation_tax,
    overtime_excess_pay,
    overtime_pay,
    periods_per_month_for_schedule,
    prima_antiguedad_payout,
    professional_risk_employer,
    professional_risk_employer_from_grade,
    professional_risk_rate_from_grade,
    rest_day_pay,
    seniority_premium_accrual,
    subsidio_enfermedad_diario,
    subsidio_maternidad_semanal,
    subsidio_maternidad_total,
    vacation_accrual,
    vacation_base,
    vacation_pay,
)


class TestCSS(unittest.TestCase):
    """Ley 51/2005 art. 96 (texto único modificado por Ley 462/2025)."""

    def test_employee_rate(self):
        # Numeral 1: 9.75 %.
        self.assertEqual(css_employee(1000), 97.5)

    def test_employer_rate_default(self):
        # Default reflects current rate (numeral 2 lit. a after Ley 462).
        self.assertEqual(css_employer(1000), 132.5)

    def test_employer_rate_schedule(self):
        # Numeral 2 lits. a-c: 13.25 / 14.25 / 15.25.
        self.assertEqual(css_employer_rate_for_date("2024-08-31"), 0.1225)
        self.assertEqual(css_employer_rate_for_date("2025-03-31"), 0.1225)
        self.assertEqual(css_employer_rate_for_date("2025-04-01"), 0.1325)
        self.assertEqual(css_employer_rate_for_date("2027-02-28"), 0.1325)
        self.assertEqual(css_employer_rate_for_date("2027-03-01"), 0.1425)
        self.assertEqual(css_employer_rate_for_date("2029-02-28"), 0.1425)
        self.assertEqual(css_employer_rate_for_date("2029-03-01"), 0.1525)

    def test_2024_css_notice_aggregate_pattern(self):
        # CSS notice aggregate shape (fictional base): employee 9.75% +
        # employer 12.25% (pre-reform Aug 2024 rate) = 22.00% combined.
        taxable_base = 3200.0
        employee = css_employee(taxable_base)
        employer = css_employer(taxable_base, css_employer_rate_for_date("2024-08-31"))
        self.assertEqual(employee, 312.0)
        self.assertEqual(employer, 392.0)
        self.assertEqual(employee + employer, 704.0)

    def test_decimo_special_rates(self):
        # Numeral 4: 10.75 % patronal; numeral 5: 7.25 % obrera.
        self.assertEqual(CSS_EMPLOYEE_RATE_DECIMO, 0.0725)
        self.assertEqual(CSS_EMPLOYER_RATE_DECIMO, 0.1075)
        self.assertEqual(css_employee_decimo(1000), 72.5)
        self.assertEqual(css_employer_decimo(1000), 107.5)


class TestSeguroEducativo(unittest.TestCase):
    """Ley 13/1987."""

    def test_employee_employer(self):
        self.assertEqual(educational_insurance_employee(1000), 12.5)
        self.assertEqual(educational_insurance_employer(1000), 15.0)

    def test_decimo_exempt(self):
        # SE no aplica sobre décimo (DGI Instructivo F03 §16; Ley 13/1987).
        self.assertEqual(educational_insurance_employee_decimo(1000), 0.0)
        self.assertEqual(educational_insurance_employer_decimo(1000), 0.0)


class TestRiesgosProfesionales(unittest.TestCase):
    """Decreto Gabinete 68/1970 art. 51."""

    def test_grade_to_rate(self):
        # Tasa = grado × 0.07 % (siete centésimos por ciento).
        self.assertEqual(professional_risk_rate_from_grade(6), 0.0042)
        self.assertEqual(professional_risk_rate_from_grade(8), 0.0056)
        self.assertEqual(professional_risk_rate_from_grade(100), 0.07)

    def test_grade_negative_raises(self):
        with self.assertRaises(ValueError):
            professional_risk_rate_from_grade(-1)

    def test_premium(self):
        self.assertEqual(professional_risk_employer(1000, 0.0098), 9.8)
        self.assertEqual(professional_risk_employer_from_grade(1000, 8), 5.6)

    def test_2024_css_notice_risk_pattern(self):
        # CSS notice risk shape (fictional base): risk rate 0.98% × 3,200.00.
        self.assertEqual(professional_risk_employer(3200, 0.0098), 31.36)


class TestISRBrackets(unittest.TestCase):
    """Cód. Fiscal art. 700 (modificado por Ley 8/2010), DGI Instructivo F03 §26."""

    def test_zero_under_threshold(self):
        self.assertEqual(annual_income_tax(11000), 0.0)
        self.assertEqual(annual_income_tax(0), 0.0)

    def test_low_bracket(self):
        # 15 % sobre el excedente de 11,000.
        self.assertEqual(annual_income_tax(20000), (20000 - 11000) * 0.15)
        self.assertEqual(annual_income_tax(50000), (50000 - 11000) * 0.15)

    def test_high_bracket(self):
        # 5,850 fijo + 25 % sobre el excedente de 50,000.
        self.assertEqual(annual_income_tax(60000), 5850 + (60000 - 50000) * 0.25)
        self.assertEqual(annual_income_tax(100000), 5850 + (100000 - 50000) * 0.25)


class TestISRMonthlyRetention(unittest.TestCase):
    """DGI eTax2 Privado method (verified empirically; see tools/etax2_probe.py).

    For Panama private-sector full-year employees:
        annual_taxable = monthly × 13
        ISR_annual    = bracket(annual_taxable)
        MRM           = ISR_annual ÷ 13

    DGI counts the décimo as a 13th retention event. DE 170/1993 step 7
    has a plainer reading of "÷ N where N = months in PPC" but the
    operational authority is the eTax2 calculator output. See
    ASSUMPTIONS.md for the divergence note.
    """

    def test_monthly_default_matches_etax2(self):
        # $1,000 × 13 = $13,000 annual. ISR = (13,000−11,000)×15 % = $300.
        # ÷ 13 = $23.077 → $23.08. Matches DGI eTax2 Privado.
        self.assertEqual(calculate_monthly_income_tax(1000), 23.08)

    def test_under_threshold_is_zero(self):
        # $800 × 13 = $10,400 < $11,000 threshold.
        self.assertEqual(calculate_monthly_income_tax(800), 0.0)

    def test_high_bracket_matches_etax2(self):
        # $4,000 × 13 = $52,000 annual. ISR = 5,850 + 2,000×25 % = $6,350.
        # ÷ 13 = $488.46. Matches DGI eTax2 Privado.
        self.assertEqual(calculate_monthly_income_tax(4000), 488.46)

    def test_explicit_partial_period(self):
        # New-hire scenario: PPC = 8 months. Pure annualization at × 8.
        # $1,000 × 8 = $8,000 < $11,000 threshold → $0.
        self.assertEqual(calculate_monthly_income_tax(1000, months=8), 0.0)

    def test_with_spouse_deduction_matches_etax2(self):
        # $1,000 × 13 − $800 = $12,200. ISR = 1,200 × 15 % = $180.
        # ÷ 13 = $13.846 → $13.85. Matches DGI eTax2 Privado, spouse=ON.
        self.assertEqual(calculate_monthly_income_tax(1000, annual_deductions=800), 13.85)


class TestISRPeriodRetention(unittest.TestCase):
    """Payroll-period ISR allocation from private semimonthly receipts."""

    def test_monthly_default_matches_monthly_helper(self):
        self.assertEqual(calculate_period_income_tax(1000), 23.08)

    def test_semimonthly_taxable_salary(self):
        # Fictional B/.1,500 monthly salary paid as B/.750 quincena.
        # Monthly ISR = B/.98.08, split across two pay periods.
        self.assertEqual(calculate_period_income_tax(750, periods_per_month=2), 49.04)

    def test_semimonthly_under_threshold_is_zero(self):
        # Fictional B/.700 monthly salary paid as B/.350 quincena remains
        # below the annual ISR threshold.
        self.assertEqual(calculate_period_income_tax(350, periods_per_month=2), 0.0)


class TestISRMatchesEtax2Probe(unittest.TestCase):
    """Golden master against DGI eTax2 calculator output for Privado sector.

    The values below were captured by ``tools/etax2_probe.py`` against
    https://etax2.mef.gob.pa/etax2web/Ccc/CalculoSobreRenta.aspx on
    2026-05-04. If a future probe diverges from these, either the law
    changed or DGI updated their calculator — investigate before
    changing the expected values.

    Each tuple: (monthly_salary, spouse_joint, expected_monthly_isr).
    """

    PROBE_VALUES = (
        (800, False, 0.0),
        (800, True, 0.0),
        (1000, False, 23.08),
        (1000, True, 13.85),
        (1500, False, 98.08),
        (1500, True, 88.85),
        (2000, False, 173.08),
        (2000, True, 163.85),
        (4000, False, 488.46),
        (4000, True, 473.08),
        (6000, False, 988.46),
        (6000, True, 973.08),
        (10000, False, 1988.46),
        (10000, True, 1973.08),
    )

    def test_all_probe_values(self):
        SPOUSE_DEDUCTION = 800.0
        for monthly, spouse, expected in self.PROBE_VALUES:
            with self.subTest(monthly=monthly, spouse=spouse):
                ded = SPOUSE_DEDUCTION if spouse else 0.0
                got = calculate_monthly_income_tax(monthly, annual_deductions=ded)
                self.assertEqual(got, expected, f"${monthly}, spouse={spouse}: got ${got}, expected ${expected}")


class TestPeriodsPerMonthForSchedule(unittest.TestCase):
    """ISR projection factor derived from the contract's pay frequency.

    Keys mirror Odoo's hr.payroll.structure.type schedule_pay selection.
    A monthly contract pays once a month; a quincenal (semi-monthly) one
    pays twice. Deriving this per contract is what lets a monthly and a
    quincenal employee be calculated correctly in the same period.
    """

    def test_monthly_is_one(self):
        self.assertEqual(periods_per_month_for_schedule("monthly"), 1.0)

    def test_semi_monthly_is_two(self):
        self.assertEqual(periods_per_month_for_schedule("semi-monthly"), 2.0)

    def test_weekly_and_biweekly(self):
        self.assertAlmostEqual(periods_per_month_for_schedule("weekly"), 52.0 / 12.0)
        self.assertAlmostEqual(periods_per_month_for_schedule("bi-weekly"), 26.0 / 12.0)

    def test_unknown_falls_back_to_default(self):
        # Blank/None/unrecognised → caller-provided fallback (the global param).
        self.assertEqual(periods_per_month_for_schedule(None, default=2.0), 2.0)
        self.assertEqual(periods_per_month_for_schedule("", default=1.0), 1.0)
        self.assertEqual(periods_per_month_for_schedule("fortnightly", default=2.0), 2.0)

    def test_low_wage_quincenal_under_threshold_is_zero(self):
        # The bug this fixes (fictional amounts): $700/mo employee paid
        # quincenally. Each quincena GROSS = $350; periods derived from
        # "semi-monthly" = 2. $350 × 2 × 13 = $9,100 ≤ $11,000 → $0, not
        # the $41.54 a monthly slip mis-read through a quincenal lens
        # produced.
        periods = periods_per_month_for_schedule("semi-monthly")
        from lib.calculations import calculate_period_income_tax
        self.assertEqual(calculate_period_income_tax(350, periods_per_month=periods), 0.0)


class TestLiquidationISR(unittest.TestCase):
    """Cód. Fiscal art. 701 lit. j; DGI Instructivo F03 §30."""

    def test_under_deductions_is_zero(self):
        # $4,000 payout, 5 years: deduct 5 % × $4,000 = $200, then $5,000.
        # 4000 - 200 - 5000 < 0 → ISR = 0.
        self.assertEqual(liquidation_isr(4000, 5), 0.0)

    def test_after_deductions_within_low_bracket(self):
        # $20,000 payout, 5 years: deduct 5 % × 20,000 = $1,000, then $5,000.
        # Remainder $14,000. Tarifa: (14,000 - 11,000) × 15 % = $450.
        self.assertEqual(liquidation_isr(20000, 5), 450.0)

    def test_after_deductions_high_bracket(self):
        # $80,000 payout, 10 years: deduct 10 % × 80,000 = $8,000, then $5,000.
        # Remainder $67,000. Tarifa: 5,850 + (67,000 - 50,000) × 25 % = $10,100.
        self.assertEqual(liquidation_isr(80000, 10), 10100.0)


class TestRepresentationTax(unittest.TestCase):
    """Cód. Fiscal art. 701 lit. l (Ley 8/2010); DGI Instructivo F03 §27."""

    def test_low_bracket(self):
        # 10 % hasta 25,000.
        self.assertEqual(annual_representation_tax(20000), 2000.0)
        self.assertEqual(annual_representation_tax(25000), 2500.0)

    def test_high_bracket(self):
        # 2,500 + 15 % sobre el excedente de 25,000.
        self.assertEqual(annual_representation_tax(40000), 2500 + (40000 - 25000) * 0.15)
        self.assertEqual(annual_representation_tax(60000), 2500 + (60000 - 25000) * 0.15)

    def test_monthly_retention(self):
        # $2,000/mo × 12 = $24,000 annual → 10 % = $2,400 → ÷ 12 = $200.
        self.assertEqual(monthly_representation_tax(2000), 200.0)


class TestAccruals(unittest.TestCase):

    def test_decimo_accrual(self):
        # Ley 8/1981: 1/12 of base.
        self.assertEqual(decimo_accrual(1200), 100.0)

    def test_vacation_accrual(self):
        # CT art. 54 numeral 1: 1/11 of base.
        self.assertEqual(vacation_accrual(1100), 100.0)

    def test_vacation_base(self):
        # CT art. 54 numeral 2: greater of avg(11mo ord+extra) or last base.
        self.assertEqual(vacation_base(900, 1000), 1000)
        self.assertEqual(vacation_base(1100, 1000), 1100)

    def test_vacation_pay_full_month(self):
        # CT art. 54: 30 días = un mes de salario base.
        self.assertEqual(vacation_pay(1000, 30), 1000.0)

    def test_vacation_pay_partial(self):
        # 15 días = medio salario base.
        self.assertEqual(vacation_pay(1000, 15), 500.0)
        # 1 día = salario / 30.
        self.assertAlmostEqual(vacation_pay(1500, 1), 50.0, places=2)

    def test_prima_antiguedad_rate(self):
        # CT art. 224: una semana × año. Monthly accrual = 1/52 of monthly.
        self.assertAlmostEqual(PRIMA_ANTIGUEDAD_MONTHLY_RATE, 1.0 / 52.0, places=10)

    def test_prima_antiguedad_accrual_value(self):
        # $1,000 × (1/52) = $19.230769... → rounded to $19.23.
        self.assertEqual(seniority_premium_accrual(1000), 19.23)
        self.assertEqual(seniority_premium_accrual(2080), 40.0)  # 2080 / 52 = 40 exact


class TestPrimaAntiguedadPayout(unittest.TestCase):
    """CT art. 224: una semana de salario por cada año laborado."""

    def test_one_year(self):
        # Una semana = monthly × 3/13 ≈ 230.77 for $1,000.
        self.assertEqual(prima_antiguedad_payout(1000, 1), round(1000 * 3 / 13 + 0.000000001, 2))

    def test_partial_year(self):
        # Prorrateo CT art. 224 segundo párrafo.
        self.assertAlmostEqual(prima_antiguedad_payout(1000, 5.5), round(1000 * 3 / 13 * 5.5 + 0.000000001, 2))


class TestIndemnization(unittest.TestCase):
    """CT art. 225 lit. C (relaciones desde Ley 44/1995)."""

    def test_under_ten_years(self):
        # 5 años × 3.4 semanas/año × salario_semanal.
        # Salario semanal de $1,000/mo = $1,000 × 3/13.
        weekly = 1000 * MONTHLY_TO_WEEKLY
        expected = round(5 * 3.4 * weekly + 0.000000001, 2)
        self.assertEqual(indemnization_payout(1000, 5), expected)

    def test_exactly_ten_years(self):
        # 10 × 3.4 = 34 semanas.
        weekly = 1000 * MONTHLY_TO_WEEKLY
        expected = round(34 * weekly + 0.000000001, 2)
        self.assertEqual(indemnization_payout(1000, 10), expected)

    def test_beyond_ten_years(self):
        # 15 años: 10 × 3.4 + 5 × 1 = 39 semanas.
        weekly = 1000 * MONTHLY_TO_WEEKLY
        expected = round(39 * weekly + 0.000000001, 2)
        self.assertEqual(indemnization_payout(1000, 15), expected)


class TestCesantiaIndemnization(unittest.TestCase):
    """Ley 44/1995 art. 229-B: 5 % de la cuotaparte mensual de indemnización."""

    def test_first_ten_rate_derivation(self):
        # Primeros 10 años: indemnización = 3.4 sem/año.
        # Cuotaparte mensual = (3.4/12) × (3/13) of monthly = 3.4 × 3 / (12 × 13) of monthly.
        # 5 % de eso = 3.4 × 3 / (12 × 13 × 20) of monthly.
        expected = 3.4 * 3 / (12 * 13 * 20)
        self.assertAlmostEqual(CESANTIA_INDEMNIZATION_FIRST_TEN_RATE, expected, places=10)

    def test_after_ten_rate_derivation(self):
        # Después de 10 años: 1 sem/año. Mismo derivado con coeficiente 1.
        expected = 1.0 * 3 / (12 * 13 * 20)
        self.assertAlmostEqual(CESANTIA_INDEMNIZATION_AFTER_TEN_RATE, expected, places=10)

    def test_step_at_ten_years(self):
        # En 10 años exactos, debemos seguir en la tasa de los primeros 10 años.
        first = cesantia_indemnization_accrual(1000, 10)
        after = cesantia_indemnization_accrual(1000, 10.001)
        self.assertGreater(first, after)
        # En 11 años, la tasa debe estar en el tramo posterior.
        self.assertEqual(cesantia_indemnization_accrual(1000, 11), after)


class TestOvertimeAndSurcharges(unittest.TestCase):
    """CT arts. 33, 36, 48, 49, 50."""

    def test_hourly_rate_default(self):
        # 208 horas/mes legales.
        self.assertAlmostEqual(hourly_rate(2080), 10.0)

    def test_overtime_day(self):
        # CT art. 33 num. 1: +25 %. 1 hora a $10/h × 1.25 = $12.50.
        self.assertEqual(overtime_pay(2080, 1, 0.25), 12.50)

    def test_overtime_mixed_day(self):
        # CT art. 33 num. 2: +50 %. 1 hora a $10/h × 1.50 = $15.00.
        self.assertEqual(overtime_pay(2080, 1, 0.50), 15.00)

    def test_overtime_night(self):
        # CT art. 33 num. 3: +75 %. 1 hora a $10/h × 1.75 = $17.50.
        self.assertEqual(overtime_pay(2080, 1, 0.75), 17.50)

    def test_overtime_excess_legal_cap(self):
        # CT art. 36 num. 4: +75 % adicional. Diurna excedente: 1.25 + 0.75 = 2.00.
        self.assertEqual(overtime_excess_pay(2080, 1, 0.25), 20.00)

    def test_rest_day_pay(self):
        # CT art. 48: +50 %. 1 hora a $10/h × 1.50 = $15.00.
        self.assertEqual(rest_day_pay(2080, 1), 15.00)

    def test_holiday_pay(self):
        # CT art. 49: +150 %. 1 hora a $10/h × 2.50 = $25.00.
        self.assertEqual(holiday_pay(2080, 1), 25.00)

    def test_combined_sunday_overtime(self):
        # CT art. 50: primero recargo de día (50 %), luego recargo OT (25 %).
        # Base $10 × 1.50 × 1.25 = $18.75.
        self.assertEqual(combined_surcharge_pay(2080, 1, 0.50, 0.25), 18.75)


class TestSubsidiosCSS(unittest.TestCase):
    """Ley 51/2005 arts. 143, 144, 146."""

    def test_subsidio_enfermedad_70_percent(self):
        # Art. 143: 70 % del salario medio diario.
        self.assertEqual(subsidio_enfermedad_diario(50.0), 35.0)

    def test_subsidio_enfermedad_bananero_80_percent(self):
        # Art. 144: 80 % para trabajadores bananeros.
        self.assertEqual(subsidio_enfermedad_diario(50.0, bananero=True), 40.0)

    def test_subsidio_maternidad_weekly(self):
        # Art. 146: sueldo medio semanal sobre el cual hubiera cotizado.
        self.assertEqual(subsidio_maternidad_semanal(250.0), 250.0)

    def test_subsidio_maternidad_total_14_weeks(self):
        # 6 semanas antes + 8 semanas después del parto = 14.
        self.assertEqual(subsidio_maternidad_total(250.0), 14 * 250.0)


class TestStatutoryLineAggregator(unittest.TestCase):
    """Defensive aggregate for the regular monthly payslip."""

    def test_regular_lines(self):
        lines = calculate_statutory_lines(
            1000,
            StatutoryRates(professional_risk_rate=0.01, monthly_income_tax=23.08),
        )
        self.assertEqual(lines["CSS_EMP"], -97.5)
        self.assertEqual(lines["SE_EMP"], -12.5)
        self.assertEqual(lines["ISR_EMP"], -23.08)
        self.assertEqual(lines["CSS_COMP"], 132.5)
        self.assertEqual(lines["SE_COMP"], 15.0)
        self.assertEqual(lines["RP_COMP"], 10.0)

    def test_decimo_lines(self):
        # $1,000 cuota: 7.25 % obrera, 10.75 % patronal, sin SE.
        lines = calculate_decimo_lines(1000)
        self.assertEqual(lines["CSS_EMP_DEC"], -72.5)
        self.assertEqual(lines["SE_EMP_DEC"], 0.0)
        self.assertEqual(lines["CSS_COMP_DEC"], 107.5)
        self.assertEqual(lines["SE_COMP_DEC"], 0.0)


if __name__ == "__main__":
    unittest.main()
