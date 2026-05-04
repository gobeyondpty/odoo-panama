{
    "name": "Panama - Payroll",
    "summary": "Panama payroll structures and statutory calculation helpers",
    "version": "19.0.0.2.0",
    "category": "Human Resources/Payroll",
    "license": "LGPL-3",
    "author": "Odoo Panama Payroll Contributors",
    "website": "https://github.com/gobeyondpty/odoo-panama-payroll",
    "depends": [
        "hr_payroll",
        "hr_work_entry",
        "l10n_pa",
    ],
    "data": [
        "data/hr_rule_parameter_data.xml",
        "data/hr_payroll_structure_data.xml",
        "data/hr_payslip_input_type_data.xml",
        "data/hr_salary_rule_data.xml",
        "views/res_company_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
