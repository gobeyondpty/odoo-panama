# Panama - Time Off

This module adds Panama legal vacation defaults for Odoo Time Off.

It creates:

- `Vacaciones (Panama)` as a Panama-specific paid time off type.
- A Panama vacation work entry type (`PA_VAC`) for payroll integration.
- A default accrual plan for Código de Trabajo art. 54: `1/11` vacation day per service day, capped at two legal periods for compliance review.
- A daily cron/post-init helper that ensures active Panama employees have an accrual allocation.

Panama vacation balance is consumed in calendar days for this leave type. This is intentional: a Friday-to-Monday vacation request consumes 4 Panama legal vacation days, even though Odoo's default work-calendar duration would normally count only working days.

The module does not replace payroll calculation. Vacation pay is still calculated by `l10n_pa_hr_payroll` through the `VAC_PAY` rule using the statutory vacation base.
