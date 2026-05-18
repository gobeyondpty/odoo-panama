# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Panama - Time Off",
    "summary": "Panama legal vacation configuration for Odoo Time Off",
    "version": "19.0.1.0.0",
    "category": "Human Resources/Time Off",
    "license": "LGPL-3",
    "author": "Odoo Panama Localization Contributors",
    "website": "https://github.com/gobeyondpty/odoo-panama",
    "depends": [
        "hr_holidays",
        "hr_work_entry_holidays",
        "l10n_pa_hr_payroll",
    ],
    "data": [
        "data/hr_leave_type_data.xml",
        "data/hr_leave_accrual_plan_data.xml",
        "data/ir_cron_data.xml",
        "views/hr_leave_type_views.xml",
        "views/hr_leave_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
