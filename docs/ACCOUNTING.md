# Payroll Accounting Design

This module includes `l10n_pa_hr_payroll_account` as the place for payroll accounting mappings.

## Recommended Accounts

The account codes below are placeholders. Production deployments should map rules to the local chart of accounts.

| Purpose | Account type |
| --- | --- |
| Salary expense | Expense |
| Employer CSS expense | Expense |
| Employer educational insurance expense | Expense |
| Professional risk expense | Expense |
| Decimo expense/accrual | Expense/liability |
| Vacation expense/accrual | Expense/liability |
| Seniority premium expense/accrual | Expense/liability |
| Payroll payable | Current liability |
| CSS payable | Current liability |
| Educational insurance payable | Current liability |
| Income tax withholding payable | Current liability |

## Current State

The accounting addon is installable but intentionally does not create chart accounts yet. Account creation and rule mapping should happen after the Panama chart account codes are agreed for each implementation.
