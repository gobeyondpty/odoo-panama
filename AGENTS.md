# Agent Handoff

This repository is the long-term home for Panama Odoo localization modules. It owns `l10n_pa`, `l10n_pa_postal`, `l10n_pa_edi`, `l10n_pa_edi_factura_facil`, `l10n_pa_account_withholding`, `l10n_pa_reports`, `l10n_pa_hr_payroll`, `l10n_pa_hr_holidays`, and `l10n_pa_hr_payroll_account`. The planned `l10n_pa_hr_payroll_sipe` will land here as well.

## Scope rules

Keep this repo strictly generic, public, LGPL-3 Panama localization. Do not commit:

- real RUCs of operating companies
- employee names, salaries, payslips, ID numbers, CSS numbers, bank accounts
- customer/vendor records, settlement statements
- PAC credentials, eTax2 session data

Use `private/` for any local validation data and operator-specific scope
rules; the directory is gitignored.

## Current modules

- `l10n_pa` — base accounting localization (RUC/DV, identification types, four ITBMS rates, six fiscal positions, NIC/NIIF chart)
- `l10n_pa_postal` — Panama postal-code validation, coordinate decoding, and local GeoJSON lookup helpers
- `l10n_pa_edi` — DGI Factura Electrónica, PAC-agnostic (CUFE, DGI XML, CAFÉ PDF, send method)
- `l10n_pa_edi_factura_facil` — concrete Factura Fácil S.A. PAC implementation (skeleton + mocked tests pending real credentials)
- `l10n_pa_account_withholding` — DGI ITBMS / ISR retentions on processor settlements + government counterparties
- `l10n_pa_reports` — DGI Form 430 ITBMS monthly + annual rentas
- `l10n_pa_hr_payroll` — Panama payroll structures, parameters, rules, and pure-Python helper calculations
- `l10n_pa_hr_holidays` — Panama Time Off defaults for legal vacation accrual and calendar-day consumption
- `l10n_pa_hr_payroll_account` — accounting mappings for Panama payroll rules

`l10n_pa_postal`, `l10n_pa_account_withholding`, and `l10n_pa_reports` depend on `l10n_pa` (now in-repo, no longer cross-repo). `l10n_pa_hr_holidays` and `l10n_pa_hr_payroll_account` depend on `l10n_pa_hr_payroll`.

## Payroll validation tooling

- Public synthetic fixtures live in `fixtures/synthetic/`.
- Private accountant payslip fixtures belong in ignored `private/` or `fixtures/private/`.
- Run `python -m unittest discover -s tests` for pure-Python statutory checks.
- Run `python tools/validate_payslip_fixtures.py fixtures/synthetic` to validate fixtures against the helpers in `l10n_pa_hr_payroll/lib/calculations.py`.
- Cross-check with `docs/GOVERNMENT_CALCULATORS.md` before encoding new payroll rates.

## Validation strategy

Statutory formulas should live in pure Python helpers under `<module>/models/` so they can be unit-tested independently, then called from Odoo records (taxes, account.move logic, report engines).

Cross-check sources:

- DGI Form 430 instructions and eTax2 calculator: `https://etax2.mef.gob.pa/`
- Withholding agent obligations under the Código Fiscal and DGI resoluciones; cite the resolución number in the rule definition.
- Real settlement statements from Visa/Mastercard acquirers and ACH processors operating in Panama (PROCESA, Telered, Banistmo Acquiring, Credomatic, etc.) — privately held in `private/`.

## Conventions

- Module name: `l10n_pa_*`.
- Manifest: `'license': 'LGPL-3'`, `'version': '19.0.1.0.0'`.
- Copyright header on every Python file:

  ```python
  # Part of Odoo. See LICENSE file for full copyright and licensing details.
  ```

- Tests use `odoo.tests.common.TransactionCase` and live under `<module>/tests/`.
- All rates and thresholds must be date-effective so they can change without a code release.
