# Panama Payroll Assumptions

Updated: 2026-05-04

This module is not production-ready until the formulas are matched against
accountant-generated payslips and reviewed by a qualified Panama
payroll/accounting professional.

Every formula in `l10n_pa_hr_payroll/lib/calculations.py` carries a
docstring citing the primary statute. Each rule parameter in
`data/hr_rule_parameter_data.xml` carries the same citation in its
`description` field.

## Implemented As Date-Effective Parameters

These rates are stored as Odoo `hr.rule.parameter` values so they can
change by date:

| Parameter code | Default | Source |
| --- | ---: | --- |
| `l10n_pa_css_employee_rate` | 0.0975 | Ley 51/2005 art. 96 num. 1 |
| `l10n_pa_css_employer_rate` | stepped | Ley 51/2005 art. 96 num. 2 (Ley 462/2025) |
| `l10n_pa_css_employee_rate_decimo` | 0.0725 | Ley 51/2005 art. 96 num. 5 |
| `l10n_pa_css_employer_rate_decimo` | 0.1075 | Ley 51/2005 art. 96 num. 4 |
| `l10n_pa_educational_employee_rate` | 0.0125 | Ley 13/1987 |
| `l10n_pa_educational_employer_rate` | 0.015 | Ley 13/1987 |
| `l10n_pa_professional_risk_employer_rate` | 0.0 | DG 68/1970 art. 51 |
| `l10n_pa_income_tax_months` | 13 | DGI eTax2 (Privado), see ÷12 vs ÷13 note below |
| `l10n_pa_isr_spouse_deduction` | 800 | Cód. Fiscal art. 709 num. 1 |
| `l10n_pa_decimo_accrual_rate` | 0.0833 | Ley 8/1981 |
| `l10n_pa_vacation_accrual_rate` | 0.0909 | CT art. 54 num. 1 |
| `l10n_pa_seniority_accrual_rate` | 0.01923077 (= 1/52) | CT art. 224 + Ley 44/1995 art. 229-B |
| `l10n_pa_cesantia_indem_first_ten_rate` | 0.003269… | Ley 44/1995 art. 229-B + CT art. 225 lit. C |
| `l10n_pa_cesantia_indem_after_ten_rate` | 0.000962… | Ley 44/1995 art. 229-B + CT art. 225 lit. C |

Professional risk is company-specific and must be configured. The helper
library can convert a CSS professional-risk grade into a payroll rate
using `grade × 0.0007` (Decreto Gabinete 68/1970 art. 51); the employer's
assigned grade still has to come from CSS classification records.

CSS employer-rate parameter values currently included:

| Effective date | Employer rate | Source |
| --- | ---: | --- |
| 2025-04-01 | 0.1325 | Ley 462/2025 → art. 96 num. 2 lit. a |
| 2027-03-01 | 0.1425 | Ley 462/2025 → art. 96 num. 2 lit. b |
| 2029-03-01 | 0.1525 | Ley 462/2025 → art. 96 num. 2 lit. c |

## Payroll Structures

| Structure | Code | Purpose |
| --- | --- | --- |
| Regular Pay | `PA_REGULAR` | Salario mensual con CSS, SE, ISR, RP, accruals. |
| Décimo Tercer Mes | `PA_DECIMO` | Cada partida del XIII mes con CSS reducida 7.25/10.75 % y SE 0 %. |
| Liquidación Laboral | `PA_LIQUIDACION` | Preaviso, prima art. 224, indemnización art. 225, ISR art. 701-j. |

## Current Formula Assumptions

- **CSS employee deduction**: `gross taxable salary × employee rate` (Ley 51/2005 art. 96 num. 1).
- **CSS employer contribution**: `gross taxable salary × employer rate` (Ley 51/2005 art. 96 num. 2; date-effective).
- **CSS sobre décimo**: `cuota × 7.25 %` empleado y `cuota × 10.75 %` empleador (art. 96 num. 4 y 5). NO modificadas por Ley 462.
- **Seguro Educativo**: `gross taxable salary × 1.25 %` empleado, `× 1.50 %` empleador. **No aplica al décimo** (Ley 13/1987 + DGI Instructivo F03 §16).
- **Riesgos Profesionales**: `gross taxable salary × risk_rate`, donde `risk_rate = grado × 0.07 %` per DG 68/1970 art. 51.
- **ISR mensual (Privado)**: anualiza `sueldo × 13`, aplica tarifa art. 700, divide entre 13. Verificado contra el calculador oficial DGI eTax2 (`tools/etax2_probe.py`); ver nota de divergencia con DE 170/1993 más abajo.
- **Liquidación ISR**: `ISR(payout − payout × 1 % × años − B/.5,000)` con la tarifa art. 700. Cód. Fiscal art. 701 lit. j.
- **Gastos de representación**: 10 % hasta B/.25,000 anuales, B/.2,500 + 15 % sobre el excedente. Sin CSS, sin SE, no acumulable con salario. Cód. Fiscal art. 701 lit. l.
- **Décimo accrual** mensual: `1/12` de la base. Ley 8/1981.
- **Vacaciones accrual** mensual: `1/11` de la base. Base = max(promedio sal. ord. y extraord. últimos 11 meses, último salario base) per CT art. 54 num. 2.
- **Prima de antigüedad accrual** mensual: `1/52` (= 0.019230769). CT art. 224 + Ley 44/1995 art. 229-B.
- **Cesantía – componente indemnización** mensual: `0.003269` × salario (primeros 10 años) o `0.000962` × salario (posteriores). Ley 44/1995 art. 229-B + CT art. 225 lit. C.
- **Indemnización art. 225 lit. C**: 3.4 semanas/año primeros 10 + 1 semana/año posteriores; semana = monthly × 3/13.
- **Prima de antigüedad payout art. 224**: una semana/año, prorrateado.
- **Horas extras**: +25 % diurna, +50 % nocturna o mixta diurna, +75 % nocturna o mixta nocturna; +75 % adicional sobre el exceso de los límites del art. 36. CT art. 33.
- **Domingo / día descanso semanal**: +50 %. CT art. 48.
- **Día de fiesta o duelo nacional**: +150 % (incluye remuneración del día de descanso). CT art. 49.
- **Recargos combinados**: primero recargo de día (50 % o 150 %), luego recargo de OT, multiplicativo. CT art. 50.
- **Vacation pay**: `VAC_PAY` rule. Pago efectivo de vacaciones tomadas: base × días/30. Base = `vacation_base()`. Sujeto a CSS, SE e ISR. CT art. 54.
- **Time Off vacation balance**: `l10n_pa_hr_holidays` consumes Panama legal vacation in calendar days, not Odoo working days. The default Time Off accrual plan grants `1/11` day per service day and caps available balance at 60 days as a compliance-review threshold, not as a statutory forfeiture rule. CT art. 54.
- **Subsidios CSS**: helpers `subsidio_enfermedad_diario(70 %)`, `subsidio_maternidad_semanal()` per Ley 51/2005 arts. 143, 146. Estos NO se pagan por el empleador; CSS los liquida directamente. La reducción de salario en planilla durante el subsidio se modela vía work entry types impagados (estándar Odoo).
- **Riesgos profesionales por compañía**: el campo `l10n_pa_css_risk_grade` en `res.company` toma precedencia sobre el parámetro global. Si el grado es 0 se usa el parámetro `l10n_pa_professional_risk_employer_rate`. DG 68/1970 art. 51.
- **DGI Planilla 03**: aggregator en `l10n.pa.hr.payroll.planilla_03`. Devuelve un dict con las 33 columnas documentadas en el Instructivo F03 V5-6.

## ISR ÷ 12 vs ÷ 13 (Privado vs Público) — Empirical vs Statute

DE 170/1993 step 7 reads "el Monto del Impuesto lo divide entre el
número de meses del periodo provisional de cálculo." A plain reading
gives N = 12 for a full fiscal year. Secondary sources are split:
WalletPTY says ÷ 12, decimotercermes.com and tiempoz.com say ÷ 13.

**The DGI eTax2 calculator is the empirical authority.** Probed via
`tools/etax2_probe.py` against
`https://etax2.mef.gob.pa/etax2web/Ccc/CalculoSobreRenta.aspx`:

- **Sector PRIVADO**: `annual = monthly × 13 − (800 if spouse else 0)`,
  `MRM = ISR_annual ÷ 13`. DGI counts the décimo as a 13th retention
  event. This module implements this formula by default.
- **Sector PÚBLICO**: `annual = monthly × 12 + 400 − (800 if spouse else 0)`,
  `MRM = ISR_annual ÷ 12`. The fixed `+ 400` is a public-sector-specific
  annual adjustment; its origin in primary text was not located. **This
  formula is NOT implemented**; payroll for public-sector employees
  must be hand-verified against eTax2.

For private-sector ATP/IATA travel agencies, the Privado formula
applies. Run `python3 tools/etax2_probe.py` before any fiscal year
cutover to catch DGI calculator changes.

The 14-tuple golden master in
`tests/test_calculations.py::TestISRMatchesEtax2Probe` pins all probe
values; if a future probe diverges, the test fails loudly.

## Known Gaps

- ISR retention follows DGI's algorithmic procedure (DE 170/1993). DGI also publishes lookup tables; bit-exact match against eTax2 should be confirmed for representative salaries before production payroll.
- Vacation pay (`VAC_PAY`) and the accrual (`VAC_ACCR`) require the caller to supply the avg-of-last-11-months ordinary+extraordinary base via inputs. Without that input the rule falls back to the contracted wage; for employees with overtime or commissions this will under-pay (CT art. 54 num. 2). Compute the average externally and pass it through `VAC_PAY_AVG_11M`.
- Cesantía deposits must be made through an authorized fiduciario (Ley 44/1995 art. 229-C). The accrual is computed here; the deposit posting requires accounting integration with the trust company.
- Subsidios CSS (Ley 51/2005 arts. 143, 146) are paid by CSS, not the employer. This module provides the helper formulas for reporting/reconciliation. The actual payslip salary reduction during a subsidio period must be modelled via unpaid `hr.work.entry.type` records that the HR team enters as time-off; the standard `paid_amount` machinery then reduces BASIC correctly. Note that art. 96 numeral 7 levies the worker's 9.75 % CSS quota on the subsidio itself, withheld directly by CSS.
- DGI Planilla 03 row aggregation is implemented in `models/dgi_planilla_03.py`; the actual XLS/CSV file rendering is intentionally caller-specific because DGI publishes the template format per fiscal year.
- DV (dígito verificador) for Tribunal Electoral cédulas is not auto-computed; the helper returns an empty string and expects the caller to populate from the official Tribunal Electoral algorithm.
- SIPE export is not implemented; the rule outputs are positioned to feed an export module without further refactor.

## Source Anchors

- CSS resources: `css.gob.pa`, particularly the SIPE planilla and the Texto Único de la Ley 51 de 2005.
- Texto Único Ley 51/2005 (con modificaciones por Ley 462/2025): `https://www.css.gob.pa/wp-content/uploads/2025/05/TEXTO-UNICO-DE-LA-LEY-51-DE-2005-CSS-GACETA-OFICIAL-22-5-25.pdf`.
- DGI eTax: `https://etax2.mef.gob.pa/etax2web/Ccc/CalculoSobreRenta.aspx`.
- DGI Instructivo F03 (Planilla 03): `https://dgi.mef.gob.pa/TI/PL03/INSTRUCTIVO_F03_V5-6.pdf`.
- Decreto Ejecutivo 170/1993 (Reglamento ISR, consolidado al 2010): `https://www.impuestospanama.com/images/docs/decretos_ejecutivos_fiscales/Decreto_Ejecutivo_Fiscal_170_de_1993_Actualizado_al_2010.pdf`.
- Decreto Gabinete 68/1970 (Riesgos Profesionales).
- Código de Trabajo (DG 252/1971), MITRADEL.
- Ley 44/1995 (Fondo de Cesantía): `https://www.superbancos.gob.pa/documentos/fiduciarias/leyes/ley44_1995.pdf`.
