# Government Calculators And Validation Sources

Updated: 2026-05-04

This module should use official calculators and government systems as validation references where practical. These tools should not be treated as stable APIs unless an official API is documented.

## DGI Income Tax Calculator

Official DGI/eTax calculator:

```text
https://etax2.mef.gob.pa/etax2web/Ccc/CalculoSobreRenta.aspx
```

Use for:

- Cross-checking monthly income tax withholding from salary.
- Testing private-sector vs public-sector behavior if the calculator differs.
- Testing dependent spouse behavior.

Current module state:

- Implements the annual natural-person brackets from DGI tariff guidance.
- Does not yet fully match the eTax salary calculator options.

Future work:

- Add a local comparison table with synthetic salaries checked manually against the DGI calculator.
- If technically stable and legally acceptable, add an optional script that queries the calculator for test values. Do not make production payroll depend on a web scrape.

## MITRADEL Labor Benefits Calculator

Official MITRADEL prestaciones calculator:

```text
https://appstrabajo.mitradel.gob.pa/prestaciones/
```

The calculator states it is limited to private labor contracts governed by the Labor Code and includes assumptions about contract type and termination cases.

Use for:

- Cross-checking termination/liquidation calculations.
- Validating vacation, decimo, seniority premium, and indemnity behavior.

Current module state:

- Has placeholder accrual helpers for decimo, vacation, and seniority premium.
- Does not implement termination/liquidation scenarios yet.

Future work:

- Create synthetic termination cases and compare them manually against MITRADEL.
- Implement liquidation helpers after expected values are documented.

## CSS / SIPE

CSS SIPE information:

```text
https://www.css.gob.pa/sipe/
https://www.css.gob.pa/sipe/planilla.html
```

CSS employer-rate change source anchor:

```text
https://prensa.css.gob.pa/2025/03/21/aumento-en-el-pago-de-la-cuota-de-los-empleadores-se-pagara-a-partir-de-abril-de-2025/
```

Use for:

- Confirming employer registration/reporting workflow.
- Confirming SIPE concepts and payroll declaration behavior.
- Confirming employer-rate effective periods.
- Confirming professional-risk class and grade assignments.

Current module state:

- Includes the stepped employer CSS rate schedule starting with 13.25% from April 2025.
- Includes a professional-risk helper that converts a CSS risk grade to a payroll rate using `grade * 0.0007`.
- Does not implement SIPE export.

Future work:

- Add SIPE export mapping after sample SIPE upload/entry requirements are documented.
- Configure professional-risk grade/rate from employer CSS classification records.

## CSS Professional Risk Law

CSS professional-risk source anchor:

```text
https://www.css.gob.pa/wp-content/uploads/2025/04/DECRETO-DE-GABINETE-NO-68-DE-31-DE-MARZO-DE-1970-v2025.pdf
```

Articles 48-51 describe professional-risk premium classification. The source groups employers into five risk classes with grade ranges and states that the premium is calculated from salaries, the assigned risk grade, and a constant factor.

Current module state:

- Encodes the grade-to-rate helper as `risk_grade * 0.0007`.
- Does not choose the employer's grade automatically.

Future work:

- Store the assigned CSS risk grade on the company or payroll configuration.
- Add tests using the employer's actual CSS risk classification once available.

## Non-Government Calculators

Third-party Panama payroll calculators can be useful sanity checks but should not be used as legal authority.

Examples:

- `https://salariopanama.com/`
- `https://www.calculadoras.com.pa/laboral/salario-neto`
- `https://pagly.clau.com.pa/`

Use these only to catch obvious mistakes or compare common interpretations.
