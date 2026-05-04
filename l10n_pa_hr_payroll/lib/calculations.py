"""Pure-Python Panama payroll calculation helpers.

Every constant and formula in this module is traced to a primary statutory
source. Cite the source in the function docstring; if a value is not directly
supported by primary text, it must be expressed as a parameter and validated
out-of-band, not hard-coded.

Primary sources used:

- Texto Único Ley 51 de 2005 (Caja de Seguro Social), modificada por Ley 462
  de 18 de marzo de 2025. Article 96 (cuotas) numerals 1, 2, 4, 5.
- Decreto Ejecutivo 170 de 1993 (Reglamento ISR), modificado por DE 98/2010,
  procedimiento de Periodo Provisional de Cálculo (PPC).
- Código Fiscal de Panamá, artículo 700 (tarifa personas naturales,
  modificado por Ley 8 de 2010), artículo 701 literal j (liquidación
  laboral), artículo 701 literal l (gastos de representación), artículo 709
  numeral 1 (deducción por cónyuge).
- Decreto de Gabinete 68 de 1970 (Riesgos Profesionales), artículo 51.
- Código de Trabajo (DG 252 de 1971): artículos 33 (horas extras), 36
  (límites), 48 (recargo dominical), 49 (recargo fiesta o duelo nacional),
  50 (recargos combinados), 54 (vacaciones), 224 (prima de antigüedad),
  225 (indemnización por despido injustificado).
- Ley 44 de 12 de agosto de 1995 (Fondo de Cesantía), artículo 229-B.
- Ley 8 de 1981 (Décimo Tercer Mes).
- Ley 13 de 1987 (Seguro Educativo).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


PROFESSIONAL_RISK_GRADE_FACTOR = 0.0007
PROFESSIONAL_RISK_CLASS_GRADES = {
    "I": (6, 8, 10),
    "II": (9, 14, 19),
    "III": (17, 30, 43),
    "IV": (37, 52, 67),
    "V": (62, 81, 100),
}

# Conversion factors used by the Código de Trabajo and MITRADEL prestaciones
# calculator. A month is taken as 4 + 1/3 weeks (= 13/3) for liquidación and
# vacation calculations. CT art. 54 numeral 2 uses this same "cuatro semanas
# y un tercio" wording.
WEEKS_PER_MONTH = 13.0 / 3.0  # = 4.333...
MONTHLY_TO_WEEKLY = 1.0 / WEEKS_PER_MONTH

# Statutory legal hours: 8 horas/día × 6 días/semana × (52/12) semanas/mes
# ≈ 208 horas/mes ordinarias. Used to derive an hourly rate for overtime.
LEGAL_HOURS_PER_MONTH = 208.0


def money(value: float) -> float:
    """Round to cents, with a tiny epsilon to absorb binary float drift."""
    return round(float(value or 0.0) + 0.000000001, 2)


# ---------------------------------------------------------------------------
# CSS (Caja de Seguro Social) — Ley 51/2005 art. 96
# ---------------------------------------------------------------------------

def css_employee(taxable_salary: float, rate: float = 0.0975) -> float:
    """Employee CSS deduction. Ley 51/2005 art. 96 numeral 1: 9.75 %."""
    return money(taxable_salary * rate)


def css_employer(taxable_salary: float, rate: float = 0.1325) -> float:
    """Employer CSS contribution.

    Ley 51/2005 art. 96 numeral 2 as modified by Ley 462/2025:
    13.25 % desde 2025-04-01, 14.25 % desde 2027-03-01, 15.25 % desde
    2029-03-01. The default reflects the rate in force at module
    publication; callers should resolve the rate by date.
    """
    return money(taxable_salary * rate)


def css_employer_rate_for_date(pay_date: date | str | None) -> float:
    """Return the employer CSS rate effective at ``pay_date``.

    Schedule per Ley 51/2005 art. 96 numeral 2 lits. a–c, as introduced by
    Ley 462 de 18 de marzo de 2025:

    - 12.25 % hasta el 31 de marzo de 2025 (ley pre-reforma)
    - 13.25 % desde el 1 de abril de 2025 hasta el 28 de febrero de 2027
    - 14.25 % desde el 1 de marzo de 2027 hasta el 28 de febrero de 2029
    - 15.25 % desde el 1 de marzo de 2029 en adelante
    """
    if isinstance(pay_date, str):
        pay_date = date.fromisoformat(pay_date)
    pay_date = pay_date or date.today()

    if pay_date >= date(2029, 3, 1):
        return 0.1525
    if pay_date >= date(2027, 3, 1):
        return 0.1425
    if pay_date >= date(2025, 4, 1):
        return 0.1325
    return 0.1225


# Décimo tercer mes — special CSS rates per Ley 51/2005 art. 96 numerales
# 4 y 5. These are NOT modified by Ley 462/2025; they remain 10.75 % /
# 7.25 % regardless of the regular employer rate schedule.

CSS_EMPLOYEE_RATE_DECIMO = 0.0725
CSS_EMPLOYER_RATE_DECIMO = 0.1075


def css_employee_decimo(decimo_amount: float, rate: float = CSS_EMPLOYEE_RATE_DECIMO) -> float:
    """Employee CSS contribution on a décimo cuota.

    Ley 51/2005 art. 96 numeral 5: contribución especial del empleado sobre
    cada partida del decimotercer mes equivalente a 7.25 %.
    """
    return money(decimo_amount * rate)


def css_employer_decimo(decimo_amount: float, rate: float = CSS_EMPLOYER_RATE_DECIMO) -> float:
    """Employer CSS contribution on a décimo cuota.

    Ley 51/2005 art. 96 numeral 4: contribución especial del empleador sobre
    cada partida del decimotercer mes equivalente a 10.75 %.
    """
    return money(decimo_amount * rate)


# ---------------------------------------------------------------------------
# Seguro Educativo — Ley 13/1987
# ---------------------------------------------------------------------------

def educational_insurance_employee(taxable_salary: float, rate: float = 0.0125) -> float:
    """Employee Seguro Educativo. Ley 13/1987: 1.25 %."""
    return money(taxable_salary * rate)


def educational_insurance_employer(taxable_salary: float, rate: float = 0.015) -> float:
    """Employer Seguro Educativo. Ley 13/1987: 1.50 %."""
    return money(taxable_salary * rate)


# Seguro Educativo does NOT apply to décimo. DGI Instructivo F03 §16 and
# Ley 13/1987 base of contribution. Provided as explicit zero helpers so
# callers do not silently apply the wrong rate.

def educational_insurance_employee_decimo(decimo_amount: float) -> float:
    """SE on décimo cuota. Always 0 — décimo is excluded from the SE base."""
    return 0.0


def educational_insurance_employer_decimo(decimo_amount: float) -> float:
    """SE employer on décimo cuota. Always 0 — décimo excluded from SE base."""
    return 0.0


# ---------------------------------------------------------------------------
# Riesgos Profesionales — Decreto de Gabinete 68/1970
# ---------------------------------------------------------------------------

def professional_risk_employer(taxable_salary: float, risk_rate: float = 0.0) -> float:
    """Employer professional-risk premium. DG 68/1970 art. 51."""
    return money(taxable_salary * risk_rate)


def professional_risk_rate_from_grade(risk_grade: int | float) -> float:
    """Return the employer risk premium rate from a CSS-assigned grade.

    DG 68/1970 art. 51: Tasa = grado × 0.07 % (siete centésimos por ciento).
    Grado 8 ⇒ 0.56 %, grado 30 ⇒ 2.10 %, etc.
    """
    grade = float(risk_grade or 0.0)
    if grade < 0:
        raise ValueError("risk_grade must be non-negative")
    return round(grade * PROFESSIONAL_RISK_GRADE_FACTOR, 6)


def professional_risk_employer_from_grade(taxable_salary: float, risk_grade: int | float) -> float:
    return professional_risk_employer(taxable_salary, professional_risk_rate_from_grade(risk_grade))


# ---------------------------------------------------------------------------
# ISR (Impuesto sobre la Renta) — Cód. Fiscal art. 700 (Ley 8/2010)
# ---------------------------------------------------------------------------

# Bracket structure as parameters. Cód. Fiscal art. 700 reformado por Ley 8
# de 15 de marzo de 2010, ratificado por DGI Instructivo F03 §26.
ISR_BRACKET_LOW_THRESHOLD = 11000.0
ISR_BRACKET_HIGH_THRESHOLD = 50000.0
ISR_RATE_LOW = 0.15
ISR_RATE_HIGH = 0.25
ISR_FIXED_AT_HIGH = 5850.0  # 0.15 × (50000 - 11000)


def annual_income_tax(taxable_annual_income: float) -> float:
    """Annual ISR for natural persons.

    Cód. Fiscal art. 700 (Ley 8/2010):
    - hasta B/.11,000 → 0
    - de más de B/.11,000 hasta B/.50,000 → 15 % sobre el excedente de B/.11,000
    - de más de B/.50,000 → B/.5,850 + 25 % sobre el excedente de B/.50,000
    """
    annual = float(taxable_annual_income or 0.0)
    if annual <= ISR_BRACKET_LOW_THRESHOLD:
        return 0.0
    if annual <= ISR_BRACKET_HIGH_THRESHOLD:
        return money((annual - ISR_BRACKET_LOW_THRESHOLD) * ISR_RATE_LOW)
    return money(
        ISR_FIXED_AT_HIGH + (annual - ISR_BRACKET_HIGH_THRESHOLD) * ISR_RATE_HIGH
    )


def calculate_monthly_income_tax(
    monthly_taxable_income: float,
    months: int = 13,
    annual_deductions: float = 0.0,
) -> float:
    """Monthly ISR retention (MRM) for a Panama private-sector salaried worker.

    The default implementation matches DGI's official eTax2 calculator
    for Privado sector employees:

    - annual_taxable = monthly × months − annual_deductions
    - ISR_annual    = bracket(art. 700)
    - MRM           = ISR_annual ÷ months

    For a full fiscal year, ``months = 13`` — DGI counts 12 monthly
    paychecks plus one décimo (paid in three cuotas) as 13 distinct
    retention events. This is the "Privado" interpretation.

    Empirical reference (DGI eTax2 probe, ``tools/etax2_probe.py``):

    ============  ==============  ==================
    monthly       no spouse        with spouse ($800)
    ============  ==============  ==================
    $1,000        $23.08          $13.85
    $1,500        $98.08          $88.85
    $2,000        $173.08         $163.85
    $4,000        $488.46         $473.08
    $6,000        $988.46         $973.08
    $10,000       $1,988.46       $1,973.08
    ============  ==============  ==================

    Discrepancy with DE 170/1993 step 7
    -----------------------------------
    The Reglamento ISR step 7 reads "el Monto del Impuesto lo divide
    entre el número de meses del periodo provisional de cálculo." A
    plain reading suggests N = 12 for a full year. DGI's calculator
    treats N = 13 by counting the décimo as a 13th retention event.
    We follow the calculator (the empirical authority that audits will
    enforce) and document the divergence here. See ASSUMPTIONS.md.

    Public sector
    -------------
    DGI eTax2 implements a different formula for ``Sector = Público``
    (× 12 + 400 fixed annual adjustment, ÷ 12). That sector is NOT
    modelled here — pass ``months = 12`` and adjust ``annual_deductions``
    only after a CPA verification matches eTax2 for the specific
    employer. See ASSUMPTIONS.md.
    """
    monthly = float(monthly_taxable_income or 0.0)
    if months <= 0:
        return 0.0
    annual_taxable = max(monthly * months - float(annual_deductions or 0.0), 0.0)
    return money(annual_income_tax(annual_taxable) / months)


# ---------------------------------------------------------------------------
# ISR on liquidación laboral — Cód. Fiscal art. 701 literal j
# ---------------------------------------------------------------------------

LIQUIDATION_BASE_DEDUCTION = 5000.0
LIQUIDATION_PER_YEAR_DEDUCTION_RATE = 0.01


def liquidation_isr(payout_total: float, complete_years_of_service: int) -> float:
    """ISR on a liquidación payout (preaviso + prima + indemnización + bonif.).

    Cód. Fiscal art. 701 literal j, ratificado por DGI Instructivo F03 §30:

    - Excluye sumas pagadas en concepto de vacaciones y/o décimo (esas se
      gravan dentro del flujo regular).
    - El trabajador tiene derecho a:
        deducción = payout × 1 % × años completos
                    + B/.5,000.00 sobre el saldo restante.
    - Sobre el remanente se aplica la tarifa del art. 700.
    - **Esta liquidación no es acumulable con el salario regular del año.**

    ``complete_years_of_service`` debe ser el número de períodos completos
    de doce meses, no fracciones.
    """
    payout = max(float(payout_total or 0.0), 0.0)
    years = max(int(complete_years_of_service or 0), 0)

    after_per_year = payout * (1.0 - LIQUIDATION_PER_YEAR_DEDUCTION_RATE * years)
    if after_per_year <= 0.0:
        return 0.0
    after_fixed = after_per_year - LIQUIDATION_BASE_DEDUCTION
    if after_fixed <= 0.0:
        return 0.0
    return money(annual_income_tax(after_fixed))


# ---------------------------------------------------------------------------
# Gastos de Representación — Cód. Fiscal art. 701 literal l (Ley 8/2010)
# ---------------------------------------------------------------------------

REP_BRACKET_THRESHOLD = 25000.0
REP_RATE_LOW = 0.10
REP_RATE_HIGH = 0.15
REP_FIXED_AT_HIGH = 2500.0  # 0.10 × 25000


def annual_representation_tax(annual_rep_income: float) -> float:
    """Annual ISR on gastos de representación (separate tariff).

    Cód. Fiscal art. 701 lit. l (introducido por Ley 8/2010):
    - hasta B/.25,000.00 → 10 %
    - de más de B/.25,000.00 → B/.2,500 + 15 % sobre el excedente

    No acumulable con salario u otros ingresos (DGI Instructivo F03 §27).
    No genera CSS ni Seguro Educativo.
    """
    annual = max(float(annual_rep_income or 0.0), 0.0)
    if annual <= REP_BRACKET_THRESHOLD:
        return money(annual * REP_RATE_LOW)
    return money(REP_FIXED_AT_HIGH + (annual - REP_BRACKET_THRESHOLD) * REP_RATE_HIGH)


def monthly_representation_tax(monthly_rep_income: float, months: int = 12) -> float:
    """Monthly retention on gastos de representación (annualised, then ÷N).

    Mirrors the salary procedure: project annual amount, apply the
    art. 701-l tariff, divide by the PPC. ``months`` defaults to 12.
    """
    if months <= 0:
        return 0.0
    monthly = max(float(monthly_rep_income or 0.0), 0.0)
    annual = monthly * months
    return money(annual_representation_tax(annual) / months)


# ---------------------------------------------------------------------------
# Décimo Tercer Mes — Ley 8/1981
# ---------------------------------------------------------------------------

def decimo_accrual(gross_salary: float, accrual_rate: float = 1 / 12) -> float:
    """Monthly accrual of décimo tercer mes.

    Ley 8/1981: total anual = un mes de salario, pagado en tres partidas
    iguales (15 abr, 15 ago, 15 dic). Accrual mensual = 1/12 de la base
    de cálculo de cada partida.

    Per DGI Instructivo F03 §16, the base of each cuota is the average of
    salario base + horas extras + comisiones + permisos remunerados +
    riesgos profesionales + bonificaciones during the cuota period. The
    helper takes the caller's chosen base; pass the appropriate average
    from the salary rule.
    """
    return money(gross_salary * accrual_rate)


# ---------------------------------------------------------------------------
# Vacaciones — Código de Trabajo art. 54
# ---------------------------------------------------------------------------

def vacation_accrual(gross_salary: float, accrual_rate: float = 1 / 11) -> float:
    """Monthly vacation reserve accrual.

    CT art. 54 numeral 1: 30 días por cada 11 meses continuos. As an
    accrual on a monthly payroll this is ``salario / 11``.

    The base passed in must be the *vacation base* — i.e. the average of
    salarios ordinarios y extraordinarios devengados en los últimos 11
    meses, o el último salario base si resulta más favorable (CT art. 54
    numeral 2). Use ``vacation_base()`` to compute that base before
    invoking this helper.
    """
    return money(gross_salary * accrual_rate)


def vacation_base(avg_ordinary_extraordinary: float, last_base_salary: float) -> float:
    """Vacation base per CT art. 54 numeral 2.

    Returns the larger of:
    - el promedio de salarios ordinarios y extraordinarios devengados
      durante los últimos once meses, o
    - el último salario base.
    """
    return max(float(avg_ordinary_extraordinary or 0.0), float(last_base_salary or 0.0))


def vacation_pay(monthly_base: float, days: float = 30.0) -> float:
    """Vacation payout for ``days`` days off.

    CT art. 54 numeral 2: 30 días continuos equivalen a un mes de salario,
    o cuatro semanas y un tercio si la remuneración se pactó por semana.
    Para fracciones de vacaciones se prorrate por días: ``base × días/30``.

    ``monthly_base`` debe ser el resultado de ``vacation_base()`` (el mayor
    entre el promedio de salarios ordinarios y extraordinarios de los
    últimos 11 meses y el último salario base).
    """
    base = max(float(monthly_base or 0.0), 0.0)
    d = max(float(days or 0.0), 0.0)
    return money(base * d / 30.0)


# ---------------------------------------------------------------------------
# Prima de Antigüedad — CT art. 224 + Ley 44/1995
# ---------------------------------------------------------------------------

# 1 semana por año = 1/52 of annual salary = (1/52) × 12 monthly salaries
# per year. Expressed as a fraction of monthly pay accrued each month:
#   (1 semana / 52) × (12 meses) ÷ 12 meses = 1/52 of monthly salary.
PRIMA_ANTIGUEDAD_MONTHLY_RATE = 1.0 / 52.0  # = 0.01923076923...


def seniority_premium_accrual(gross_salary: float, accrual_rate: float = PRIMA_ANTIGUEDAD_MONTHLY_RATE) -> float:
    """Monthly prima de antigüedad accrual.

    CT art. 224: una semana de salario por cada año laborado. The monthly
    accrual to fund this future obligation is exactly ``salario / 52``.

    This is the "cuotaparte relativa a la prima de antigüedad" used by the
    Fondo de Cesantía (Ley 44/1995 art. 229-B), expressed as a monthly
    rate; the law requires deposits trimestralmente.
    """
    return money(gross_salary * accrual_rate)


def prima_antiguedad_payout(monthly_salary: float, years_of_service: float) -> float:
    """Lump-sum prima de antigüedad on termination.

    CT art. 224: una semana de salario por cada año laborado, prorrateado
    para fracciones. Una semana = monthly / (13/3) = monthly × 3 / 13.
    """
    weekly = float(monthly_salary or 0.0) * MONTHLY_TO_WEEKLY
    return money(weekly * max(float(years_of_service or 0.0), 0.0))


# ---------------------------------------------------------------------------
# Indemnización por Despido Injustificado — CT art. 225 lit. C
# ---------------------------------------------------------------------------

INDEMNIZATION_WEEKS_PER_YEAR_FIRST_TEN = 3.4
INDEMNIZATION_WEEKS_PER_YEAR_AFTER_TEN = 1.0


def indemnization_payout(monthly_salary: float, years_of_service: float) -> float:
    """Indemnización por despido injustificado, contratos modernos.

    CT art. 225 literal C (relaciones iniciadas a partir de la vigencia
    de la Ley 44/1995):

    - 3.4 semanas de salario por cada año de los primeros 10
    - 1 semana de salario por cada año posterior al décimo
    - Fracciones se pagan proporcionalmente.

    "Esta escala no se combinará con ninguna otra" (CT art. 225 lit. C).
    """
    years = max(float(years_of_service or 0.0), 0.0)
    weekly = float(monthly_salary or 0.0) * MONTHLY_TO_WEEKLY

    first_ten = min(years, 10.0)
    beyond_ten = max(years - 10.0, 0.0)

    weeks = (
        first_ten * INDEMNIZATION_WEEKS_PER_YEAR_FIRST_TEN
        + beyond_ten * INDEMNIZATION_WEEKS_PER_YEAR_AFTER_TEN
    )
    return money(weekly * weeks)


# ---------------------------------------------------------------------------
# Fondo de Cesantía — Ley 44/1995 art. 229-B + DE 106/1995
# ---------------------------------------------------------------------------

# Per Ley 44/1995 art. 229-B the employer cotiza trimestralmente:
#   (a) la cuotaparte relativa a la prima de antigüedad del trabajador
#       → already exposed via ``seniority_premium_accrual`` (1/52 of monthly).
#   (b) el cinco por ciento (5 %) de la cuotaparte mensual de la
#       indemnización a que pudiese tener derecho.
#
# Cuotaparte mensual de indemnización (CT art. 225 lit. C):
#   - Primeros 10 años:
#     (3.4 semanas / año ÷ 12 meses) × monthly × MONTHLY_TO_WEEKLY
#     = 3.4 × monthly × (3/13) ÷ 12
#     ≈ 0.06538 × monthly per month
#     5 % de eso ≈ 0.003269 × monthly  (≈ 0.327 %)
#   - Después de 10 años:
#     (1 semana / año ÷ 12 meses) × monthly × MONTHLY_TO_WEEKLY
#     = 1 × monthly × (3/13) ÷ 12
#     ≈ 0.01923 × monthly per month
#     5 % de eso ≈ 0.000962 × monthly  (≈ 0.0962 %)

CESANTIA_INDEMNIZATION_FIRST_TEN_RATE = (
    INDEMNIZATION_WEEKS_PER_YEAR_FIRST_TEN * MONTHLY_TO_WEEKLY / 12.0 * 0.05
)
CESANTIA_INDEMNIZATION_AFTER_TEN_RATE = (
    INDEMNIZATION_WEEKS_PER_YEAR_AFTER_TEN * MONTHLY_TO_WEEKLY / 12.0 * 0.05
)


# ---------------------------------------------------------------------------
# Subsidios CSS — Ley 51/2005 arts. 143, 146
# ---------------------------------------------------------------------------
#
# Subsidios are paid by the Caja de Seguro Social, not the employer. The
# employer's payroll obligation is simply to NOT pay salary for the days
# the worker is on subsidy, except for the first days of incapacidad
# that may remain at the employer's charge under labor regulations.
#
# Per Ley 51/2005 art. 96 numeral 7, the worker's 9.75 % CSS quota is
# still levied on the subsidy itself — CSS withholds it directly. The
# employer side does not appear in the worker's regular payroll.
#
# These helpers compute the statutory subsidy amounts so HR can reconcile
# expected CSS payments and produce total-compensation reports. They are
# NOT salary rule outputs; the actual payment flows through CSS.

SUBSIDIO_ENFERMEDAD_RATE = 0.70  # 70 % del salario medio diario de los últimos 2 meses
SUBSIDIO_ENFERMEDAD_RATE_BANANERO = 0.80  # 80 % para trabajadores bananeros (art. 144)
SUBSIDIO_MATERNIDAD_WEEKS = 14  # 6 antes + 8 después (art. 146)


def subsidio_enfermedad_diario(avg_daily_salary_last_two_months: float, bananero: bool = False) -> float:
    """Daily subsidy amount for incapacidad por enfermedad no profesional.

    Ley 51/2005 art. 143: 70 % del salario medio diario de los dos últimos
    meses cuyas cuotas hayan sido pagadas a la CSS al momento de la
    incapacidad. Art. 144: 80 % para trabajadores bananeros.

    The CSS pays the subsidy AFTER the days at the employer's charge are
    exhausted, capped at 364 días para una misma enfermedad.
    """
    rate = SUBSIDIO_ENFERMEDAD_RATE_BANANERO if bananero else SUBSIDIO_ENFERMEDAD_RATE
    return money(float(avg_daily_salary_last_two_months or 0.0) * rate)


def subsidio_maternidad_semanal(avg_weekly_salary_last_nine_months: float) -> float:
    """Weekly subsidy amount for maternidad.

    Ley 51/2005 art. 146: el monto del subsidio semanal corresponde al
    sueldo medio semanal sobre el cual la asegurada hubiera cotizado en
    los últimos nueve meses. Cubre 6 semanas antes + 8 semanas después
    del parto (14 semanas en total).
    """
    return money(float(avg_weekly_salary_last_nine_months or 0.0))


def subsidio_maternidad_total(avg_weekly_salary_last_nine_months: float, weeks: int = SUBSIDIO_MATERNIDAD_WEEKS) -> float:
    """Total CSS-paid amount over the maternity leave period.

    Defaults to the 14-week statutory window (Ley 51/2005 art. 146).
    """
    weekly = subsidio_maternidad_semanal(avg_weekly_salary_last_nine_months)
    return money(weekly * max(int(weeks or 0), 0))


def cesantia_indemnization_accrual(monthly_salary: float, years_of_service: float) -> float:
    """Monthly Fondo de Cesantía deposit for the indemnización contingency.

    Ley 44/1995 art. 229-B: 5 % de la cuotaparte mensual de la
    indemnización que pudiera corresponder bajo CT art. 225.

    Steps at the 10-year boundary because the indemnización formula itself
    drops from 3.4 → 1 semana/año after the tenth year of service.
    """
    years = max(float(years_of_service or 0.0), 0.0)
    if years <= 10.0:
        rate = CESANTIA_INDEMNIZATION_FIRST_TEN_RATE
    else:
        rate = CESANTIA_INDEMNIZATION_AFTER_TEN_RATE
    return money(float(monthly_salary or 0.0) * rate)


# ---------------------------------------------------------------------------
# Horas Extras y Recargos — CT arts. 33, 36, 48, 49, 50
# ---------------------------------------------------------------------------

OVERTIME_RATE_DAY = 0.25       # CT art. 33 numeral 1: jornada diurna
OVERTIME_RATE_NIGHT_OR_MIXED_DAY = 0.50  # CT art. 33 numeral 2
OVERTIME_RATE_NIGHT = 0.75     # CT art. 33 numeral 3
OVERTIME_RATE_EXCESS = 0.75    # CT art. 36 numeral 4: recargo adicional sobre el exceso

SURCHARGE_REST_DAY = 0.50      # CT art. 48: dominical / día descanso semanal
SURCHARGE_HOLIDAY = 1.50       # CT art. 49: día de fiesta o duelo nacional


def hourly_rate(monthly_salary: float, hours_per_month: float = LEGAL_HOURS_PER_MONTH) -> float:
    """Hourly base rate for overtime calculations.

    Defaults to 208 horas/mes ordinarias (8 hrs × 6 días × 52/12 semanas).
    Use a contract-specific value when the schedule differs from the legal
    maximum.
    """
    if hours_per_month <= 0:
        return 0.0
    return money(float(monthly_salary or 0.0) / float(hours_per_month))


def overtime_pay(monthly_salary: float, hours: float, recargo: float, hours_per_month: float = LEGAL_HOURS_PER_MONTH) -> float:
    """Pay for ``hours`` of overtime at the given recargo rate.

    CT art. 33: salario_base_hora × hours × (1 + recargo). The recargo
    must be one of OVERTIME_RATE_DAY (0.25), OVERTIME_RATE_NIGHT_OR_MIXED_DAY
    (0.50), or OVERTIME_RATE_NIGHT (0.75). Excess beyond the daily/weekly
    cap of art. 36 numeral 4 carries OVERTIME_RATE_EXCESS (0.75) added on
    top — see ``overtime_excess_pay`` for the combined form.
    """
    h = max(float(hours or 0.0), 0.0)
    rate = hourly_rate(monthly_salary, hours_per_month)
    return money(rate * h * (1.0 + max(float(recargo or 0.0), 0.0)))


def overtime_excess_pay(monthly_salary: float, hours: float, base_recargo: float, hours_per_month: float = LEGAL_HOURS_PER_MONTH) -> float:
    """Pay for overtime hours beyond the legal cap (CT art. 36 numeral 4).

    El excedente de la jornada extraordinaria por encima de los límites
    diarios (3 hrs/día) o semanales (9 hrs/semana) se paga con un 75 %
    adicional sobre el recargo ordinario.
    """
    h = max(float(hours or 0.0), 0.0)
    rate = hourly_rate(monthly_salary, hours_per_month)
    total_recargo = max(float(base_recargo or 0.0), 0.0) + OVERTIME_RATE_EXCESS
    return money(rate * h * (1.0 + total_recargo))


def rest_day_pay(monthly_salary: float, hours: float, hours_per_month: float = LEGAL_HOURS_PER_MONTH) -> float:
    """Trabajo en domingo o día de descanso semanal. CT art. 48: recargo 50 %."""
    rate = hourly_rate(monthly_salary, hours_per_month)
    return money(rate * max(float(hours or 0.0), 0.0) * (1.0 + SURCHARGE_REST_DAY))


def holiday_pay(monthly_salary: float, hours: float, hours_per_month: float = LEGAL_HOURS_PER_MONTH) -> float:
    """Trabajo en día de fiesta o duelo nacional. CT art. 49: recargo 150 %."""
    rate = hourly_rate(monthly_salary, hours_per_month)
    return money(rate * max(float(hours or 0.0), 0.0) * (1.0 + SURCHARGE_HOLIDAY))


def combined_surcharge_pay(monthly_salary: float, hours: float, day_surcharge: float, overtime_recargo: float, hours_per_month: float = LEGAL_HOURS_PER_MONTH) -> float:
    """Combined surcharge per CT art. 50.

    "Cuando el trabajo en los días domingos, de fiesta o de duelo nacional
    se hiciere en exceso de los límites legales, para el cálculo de los
    recargos, primero se aplicará al salario el recargo por trabajo en
    domingos, día de fiesta o duelo nacional, y al resultado se agregará
    entonces el recargo que corresponda por las horas excedentes."

    Implementation: base × (1 + day_surcharge) × (1 + overtime_recargo).
    """
    rate = hourly_rate(monthly_salary, hours_per_month)
    h = max(float(hours or 0.0), 0.0)
    return money(
        rate * h * (1.0 + max(float(day_surcharge or 0.0), 0.0)) * (1.0 + max(float(overtime_recargo or 0.0), 0.0))
    )


# ---------------------------------------------------------------------------
# Compatibility/aggregate helpers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StatutoryRates:
    """Snapshot of statutory rates used by the regular-payslip aggregator."""

    css_employee_rate: float = 0.0975
    css_employer_rate: float = 0.1325
    educational_employee_rate: float = 0.0125
    educational_employer_rate: float = 0.015
    professional_risk_rate: float = 0.0
    monthly_income_tax: float = 0.0


def calculate_statutory_lines(gross_salary: float, rates: StatutoryRates | None = None) -> dict[str, float]:
    """Return a dict of statutory line items for a regular monthly payslip."""
    rates = rates or StatutoryRates()
    return {
        "CSS_EMP": -css_employee(gross_salary, rates.css_employee_rate),
        "SE_EMP": -educational_insurance_employee(gross_salary, rates.educational_employee_rate),
        "ISR_EMP": -money(rates.monthly_income_tax),
        "CSS_COMP": css_employer(gross_salary, rates.css_employer_rate),
        "SE_COMP": educational_insurance_employer(gross_salary, rates.educational_employer_rate),
        "RP_COMP": professional_risk_employer(gross_salary, rates.professional_risk_rate),
    }


def calculate_decimo_lines(decimo_amount: float) -> dict[str, float]:
    """Return statutory line items for a décimo cuota payment.

    Per Ley 51/2005 art. 96 numerales 4 y 5 the décimo carries reduced CSS
    rates (10.75 % empleador, 7.25 % empleado) and is exempt from Seguro
    Educativo. ISR is not retained on the cuota itself: it has already
    been projected into the monthly retention via DE 170/1993, so the
    cuota issues no separate ISR line.
    """
    return {
        "CSS_EMP_DEC": -css_employee_decimo(decimo_amount),
        "SE_EMP_DEC": -educational_insurance_employee_decimo(decimo_amount),
        "CSS_COMP_DEC": css_employer_decimo(decimo_amount),
        "SE_COMP_DEC": educational_insurance_employer_decimo(decimo_amount),
    }
