# Odoo Panama Localization

Generic Panama localization modules for Odoo 19, structured to follow
the OCA `l10n-{country}` convention so the repo can be contributed
upstream as `OCA/l10n-panama` later.

## Modules in this repo

| Module | Purpose | License | Status |
| --- | --- | --- | --- |
| [`l10n_pa`](l10n_pa/) | Base accounting localization (taxes, fiscal positions, ID types, RUC + DV validation) | LGPL-3 | tested, 32 tests green |
| [`l10n_pa_postal`](l10n_pa_postal/) | Panama postal-code validation, coordinate decoding, and local GeoJSON lookup helpers | LGPL-3 | tested |
| [`l10n_pa_edi`](l10n_pa_edi/) | PAC-agnostic e-invoicing layer (CUFE, DGI XML, CAFÉ PDF, send method) | LGPL-3 | tested, 64 tests green |
| [`l10n_pa_edi_factura_facil`](l10n_pa_edi_factura_facil/) | Concrete Factura Fácil S.A. PAC implementation | LGPL-3 | skeleton + mocked tests, see [`INTEGRATION_CHECKLIST.md`](INTEGRATION_CHECKLIST.md) |
| [`l10n_pa_account_withholding`](l10n_pa_account_withholding/) | DGI ITBMS / ISR retentions for processor settlements and government counterparties | LGPL-3 | scaffold |
| [`l10n_pa_reports`](l10n_pa_reports/) | DGI Form 430 (ITBMS monthly) and annual Declaración Jurada de Rentas | LGPL-3 | scaffold |
| [`l10n_pa_hr_payroll`](l10n_pa_hr_payroll/) | Panama payroll structures, parameters, rules, and pure-Python helper calculations | LGPL-3 | early scaffold |
| [`l10n_pa_hr_holidays`](l10n_pa_hr_holidays/) | Panama Time Off defaults for legal vacation accrual and calendar-day consumption | LGPL-3 | early scaffold |
| [`l10n_pa_hr_payroll_account`](l10n_pa_hr_payroll_account/) | Accounting mappings for Panama payroll rules | LGPL-3 | early scaffold |

`l10n_pa_postal`, `l10n_pa_account_withholding`, and `l10n_pa_reports` depend on `l10n_pa`. `l10n_pa_hr_holidays` depends on `l10n_pa_hr_payroll`. `l10n_pa_hr_payroll_account` depends on `l10n_pa_hr_payroll`. The planned `l10n_pa_hr_payroll_sipe` will land here too.

## Quick Start

Install all modules in dependency order against a fresh Odoo 19 database:

```bash
odoo-bin -d <db> \
    -i l10n_pa,l10n_pa_postal,l10n_pa_edi,l10n_pa_edi_factura_facil,l10n_pa_account_withholding,l10n_pa_reports,l10n_pa_hr_payroll,l10n_pa_hr_holidays,l10n_pa_hr_payroll_account \
    --stop-after-init
```

Then configure the PAC under **Settings → Accounting → Panama Electronic
Invoicing** and the withholding rules per the relevant DGI resoluciones.

## Build State

- [`PROGRESS.md`](PROGRESS.md) — timestamped phase-by-phase work log for
  the factura modules (six phases plus a codex review fix-up).
- [`CHANGELOG.md`](CHANGELOG.md) — release notes per version.
- [`DECISIONS_DEFERRED.md`](DECISIONS_DEFERRED.md) — items that need
  outside input (CPA, processor data, PAC credentials).
- [`TECH_DEBT.md`](TECH_DEBT.md) — known shortcuts with justification.
- [`INTEGRATION_CHECKLIST.md`](INTEGRATION_CHECKLIST.md) — punch list of
  Factura Fácil PAC stubs awaiting credentials.

## Dependencies

- `l10n_pa` depends only on Community modules (`account` + `l10n_latam_base`).
- `l10n_pa_postal` depends on `l10n_pa`.
- `l10n_pa_edi` depends on `l10n_pa`, `account`, `account_debit_note`.
- `l10n_pa_edi_factura_facil` depends on `l10n_pa_edi`.
- `l10n_pa_account_withholding` depends on `l10n_pa` and Enterprise
  `l10n_account_withholding_tax`.
- `l10n_pa_reports` depends on `l10n_pa` and Enterprise `account_reports`.
- `l10n_pa_hr_payroll` depends on Enterprise `hr_payroll`.
- `l10n_pa_hr_holidays` depends on `l10n_pa_hr_payroll`, Odoo Time Off, and Time Off work entries.
- `l10n_pa_hr_payroll_account` depends on `l10n_pa_hr_payroll` and Enterprise `hr_payroll_account`.

## Payroll Validation

Pure-Python statutory checks (run from repo root):

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests
.venv/bin/python tools/validate_payslip_fixtures.py fixtures/synthetic
```

Public synthetic fixtures live in `fixtures/synthetic/`. Private
accountant payslip fixtures must stay outside Git (`private/` or
`fixtures/private/`). See [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md),
[`docs/VALIDATION.md`](docs/VALIDATION.md),
[`docs/ACCOUNTING.md`](docs/ACCOUNTING.md), and
[`docs/GOVERNMENT_CALCULATORS.md`](docs/GOVERNMENT_CALCULATORS.md).

The upstream Odoo 19 `l10n_pa` (Cubic ERP) lacks the four ITBMS rates,
identification types, and DV validation that this repo's `l10n_pa`
provides; this module is meant to supersede the upstream version. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the addons-path workaround.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Compliance Notice

These modules are reference implementations. Tax reports, withholding
rates, and DGI/MEF technical specs change. Before production use:

- Have a Panama-licensed CPA review the report layouts and withholding rules.
- Cross-check withholding amounts against actual processor settlement
  statements and DGI eTax2 outputs.
- Track the Gaceta Oficial for rate or threshold changes; encode rates
  as date-effective parameters.

## Private Data Policy

Never commit:

- real RUCs of operating companies
- customer/vendor names
- processor settlement statements
- eTax2 session data
- PAC credentials
- bank account numbers

Use `private/` for local validation data; the path is gitignored.

## License

LGPL-3. See [`LICENSE`](LICENSE).
