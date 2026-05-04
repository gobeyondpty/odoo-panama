# Payslip Validation Workflow

The module should be validated against historical accountant-generated payslips before being trusted.

## Public Synthetic Fixtures

Run:

```bash
python tools/validate_payslip_fixtures.py fixtures/synthetic
python -m unittest discover -s tests
```

## Private Accountant Fixtures

Place redacted JSON files under:

```text
private/
```

Then run:

```bash
python tools/validate_payslip_fixtures.py private
```

The `private/` directory is ignored by Git except for `private/README.md`.

## Fixture Format

### PA_REGULAR fixture

```json
{
  "employee": "Redacted Employee A",
  "period": "2026-01",
  "gross_salary": 1000.0,
  "structure": "PA_REGULAR",
  "rates": {
    "css_employee_rate": 0.0975,
    "css_employer_rate": 0.1325,
    "educational_employee_rate": 0.0125,
    "educational_employer_rate": 0.015,
    "professional_risk_rate": 0.0,
    "monthly_income_tax": 25.0
  },
  "expected_lines": {
    "CSS_EMP": -97.5,
    "SE_EMP": -12.5,
    "ISR_EMP": -25.0,
    "CSS_COMP": 132.5,
    "SE_COMP": 15.0,
    "RP_COMP": 0.0
  }
}
```

### PA_DECIMO fixture

```json
{
  "employee": "Redacted Employee A",
  "period": "2026-04",
  "gross_salary": 1000.0,
  "structure": "PA_DECIMO",
  "expected_lines": {
    "CSS_EMP_DEC": -72.5,
    "SE_EMP_DEC": 0.0,
    "CSS_COMP_DEC": 107.5,
    "SE_COMP_DEC": 0.0
  }
}
```

`PA_DECIMO` does not consume `rates`: the special CSS rates (Ley 51/2005
art. 96 num. 4 y 5) and the SE exemption are statute-fixed.

Future harness work should compare full Odoo-generated payslips, not only the pure helper functions.

