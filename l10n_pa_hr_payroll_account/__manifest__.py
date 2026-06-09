{
    "name": "Panama - Payroll Accounting",
    "summary": "Accounting mappings for Panama payroll rules",
    "description": """
Maps the Panama salary rules from `l10n_pa_hr_payroll` to the `l10n_pa`
chart of accounts: salary/social-security expense, CSS/SE/ISR payables,
and the decimo / vacation / seniority-premium / cesantia provisions.

The mapping is a CPA-reviewable reference default. Two payroll-specific
provision accounts (245 Provision para Vacaciones, 246 Provision para
Prima de Antiguedad) are added to the `pa` chart template; companies
whose chart predates this module get them created on install.
""",
    "version": "19.0.0.2.0",
    "category": "Human Resources/Payroll",
    "license": "LGPL-3",
    "author": "Odoo Panama Payroll Contributors",
    "website": "https://github.com/gobeyondpty/odoo-panama",
    "depends": [
        "l10n_pa_hr_payroll",
        "hr_payroll_account",
        "l10n_pa",
    ],
    "data": [
        "data/account_chart_template_data.xml",
    ],
    "installable": True,
    "application": False,
}
