from odoo import api, models

from ..lib import calculations


class HrPayrollPanamaMixin(models.AbstractModel):
    """Panama payroll calculation helpers exposed to ``hr.salary.rule``.

    Every default rate routes to a statute-cited constant in
    ``..lib.calculations``. Keep rule-side code thin: pass in the right
    inputs and trust the helper. Date-effective values must come from
    ``rule_parameter('l10n_pa_*')`` so that statutory changes are applied
    by date, not by code release.
    """

    _name = "l10n.pa.hr.payroll.mixin"
    _description = "Panama Payroll Calculation Helpers"

    # -------- CSS regular --------
    @api.model
    def css_employee(self, taxable_salary, rate=0.0975):
        return calculations.css_employee(taxable_salary, rate)

    @api.model
    def css_employer(self, taxable_salary, rate=0.1325):
        return calculations.css_employer(taxable_salary, rate)

    @api.model
    def css_employer_rate_for_date(self, pay_date=None):
        return calculations.css_employer_rate_for_date(pay_date)

    # -------- CSS décimo (Ley 51/2005 art. 96 numerales 4 y 5) --------
    @api.model
    def css_employee_decimo(self, decimo_amount, rate=calculations.CSS_EMPLOYEE_RATE_DECIMO):
        return calculations.css_employee_decimo(decimo_amount, rate)

    @api.model
    def css_employer_decimo(self, decimo_amount, rate=calculations.CSS_EMPLOYER_RATE_DECIMO):
        return calculations.css_employer_decimo(decimo_amount, rate)

    # -------- Seguro Educativo (Ley 13/1987) --------
    @api.model
    def educational_insurance_employee(self, taxable_salary, rate=0.0125):
        return calculations.educational_insurance_employee(taxable_salary, rate)

    @api.model
    def educational_insurance_employer(self, taxable_salary, rate=0.015):
        return calculations.educational_insurance_employer(taxable_salary, rate)

    @api.model
    def educational_insurance_employee_decimo(self, decimo_amount):
        return calculations.educational_insurance_employee_decimo(decimo_amount)

    @api.model
    def educational_insurance_employer_decimo(self, decimo_amount):
        return calculations.educational_insurance_employer_decimo(decimo_amount)

    # -------- Riesgos Profesionales (DG 68/1970) --------
    @api.model
    def professional_risk_employer(self, taxable_salary, risk_rate):
        return calculations.professional_risk_employer(taxable_salary, risk_rate)

    @api.model
    def professional_risk_rate_from_grade(self, risk_grade):
        return calculations.professional_risk_rate_from_grade(risk_grade)

    @api.model
    def professional_risk_employer_from_grade(self, taxable_salary, risk_grade):
        return calculations.professional_risk_employer_from_grade(taxable_salary, risk_grade)

    # -------- ISR mensual (DGI eTax2 Privado, Cód. Fiscal art. 700) --------
    @api.model
    def monthly_income_tax(self, monthly_taxable_income, months=13, annual_deductions=0.0):
        return calculations.calculate_monthly_income_tax(
            monthly_taxable_income, months, annual_deductions
        )

    @api.model
    def annual_income_tax(self, taxable_annual_income):
        return calculations.annual_income_tax(taxable_annual_income)

    # -------- ISR liquidación laboral (Cód. Fiscal art. 701-j) --------
    @api.model
    def liquidation_isr(self, payout_total, complete_years_of_service):
        return calculations.liquidation_isr(payout_total, complete_years_of_service)

    # -------- Gastos de representación (Cód. Fiscal art. 701-l) --------
    @api.model
    def annual_representation_tax(self, annual_rep_income):
        return calculations.annual_representation_tax(annual_rep_income)

    @api.model
    def monthly_representation_tax(self, monthly_rep_income, months=12):
        return calculations.monthly_representation_tax(monthly_rep_income, months)

    # -------- Décimo accrual (Ley 8/1981) --------
    @api.model
    def decimo_accrual(self, gross_salary, accrual_rate=1 / 12):
        return calculations.decimo_accrual(gross_salary, accrual_rate)

    # -------- Vacaciones (CT art. 54) --------
    @api.model
    def vacation_accrual(self, gross_salary, accrual_rate=1 / 11):
        return calculations.vacation_accrual(gross_salary, accrual_rate)

    @api.model
    def vacation_base(self, avg_ordinary_extraordinary, last_base_salary):
        return calculations.vacation_base(avg_ordinary_extraordinary, last_base_salary)

    @api.model
    def vacation_pay(self, monthly_base, days=30.0):
        return calculations.vacation_pay(monthly_base, days)

    # -------- Prima de antigüedad (CT art. 224) --------
    @api.model
    def seniority_premium_accrual(self, gross_salary, accrual_rate=calculations.PRIMA_ANTIGUEDAD_MONTHLY_RATE):
        return calculations.seniority_premium_accrual(gross_salary, accrual_rate)

    @api.model
    def prima_antiguedad_payout(self, monthly_salary, years_of_service):
        return calculations.prima_antiguedad_payout(monthly_salary, years_of_service)

    # -------- Indemnización (CT art. 225) --------
    @api.model
    def indemnization_payout(self, monthly_salary, years_of_service):
        return calculations.indemnization_payout(monthly_salary, years_of_service)

    # -------- Fondo de Cesantía (Ley 44/1995 art. 229-B) --------
    @api.model
    def cesantia_indemnization_accrual(self, monthly_salary, years_of_service):
        return calculations.cesantia_indemnization_accrual(monthly_salary, years_of_service)

    # -------- Subsidios CSS (Ley 51/2005 arts. 143, 146) --------
    @api.model
    def subsidio_enfermedad_diario(self, avg_daily_salary_last_two_months, bananero=False):
        return calculations.subsidio_enfermedad_diario(avg_daily_salary_last_two_months, bananero)

    @api.model
    def subsidio_maternidad_semanal(self, avg_weekly_salary_last_nine_months):
        return calculations.subsidio_maternidad_semanal(avg_weekly_salary_last_nine_months)

    @api.model
    def subsidio_maternidad_total(self, avg_weekly_salary_last_nine_months, weeks=14):
        return calculations.subsidio_maternidad_total(avg_weekly_salary_last_nine_months, weeks)

    # -------- Horas extras y recargos (CT arts. 33, 36, 48, 49, 50) --------
    @api.model
    def hourly_rate(self, monthly_salary, hours_per_month=calculations.LEGAL_HOURS_PER_MONTH):
        return calculations.hourly_rate(monthly_salary, hours_per_month)

    @api.model
    def overtime_pay(self, monthly_salary, hours, recargo, hours_per_month=calculations.LEGAL_HOURS_PER_MONTH):
        return calculations.overtime_pay(monthly_salary, hours, recargo, hours_per_month)

    @api.model
    def overtime_excess_pay(self, monthly_salary, hours, base_recargo, hours_per_month=calculations.LEGAL_HOURS_PER_MONTH):
        return calculations.overtime_excess_pay(monthly_salary, hours, base_recargo, hours_per_month)

    @api.model
    def rest_day_pay(self, monthly_salary, hours, hours_per_month=calculations.LEGAL_HOURS_PER_MONTH):
        return calculations.rest_day_pay(monthly_salary, hours, hours_per_month)

    @api.model
    def holiday_pay(self, monthly_salary, hours, hours_per_month=calculations.LEGAL_HOURS_PER_MONTH):
        return calculations.holiday_pay(monthly_salary, hours, hours_per_month)

    @api.model
    def combined_surcharge_pay(self, monthly_salary, hours, day_surcharge, overtime_recargo, hours_per_month=calculations.LEGAL_HOURS_PER_MONTH):
        return calculations.combined_surcharge_pay(
            monthly_salary, hours, day_surcharge, overtime_recargo, hours_per_month
        )
