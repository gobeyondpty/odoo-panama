{
    "name": "Panama - SIPE Planilla Export",
    "summary": "Generate the CSS SIPE bulk-upload XLSX from Odoo payslips",
    "description": """
Panama CSS SIPE Planilla Export
================================

Generates the bulk-upload XLSX file accepted by the Caja de Seguro Social
(CSS) SIPE web portal at https://sipe.css.gob.pa/. The 25-column format
follows the official `Manual de Carga Masiva de Planilla V2`.

Each Panama salary rule can be tagged with the SIPE column it contributes
to via the `l10n_pa_sipe_column` Selection on `hr.salary.rule`. The
wizard aggregates posted payslips for the period and writes one row per
employee.
""",
    "version": "19.0.0.1.0",
    "category": "Human Resources/Payroll",
    "license": "LGPL-3",
    "author": "Odoo Panama Localization Contributors",
    "website": "https://github.com/gobeyondpty/odoo-panama",
    "depends": [
        "l10n_pa_hr_payroll",
    ],
    "external_dependencies": {
        "python": ["openpyxl"],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/hr_employee_views.xml",
        "views/hr_salary_rule_views.xml",
        "wizard/sipe_export_wizard_views.xml",
        "data/sipe_rule_mapping_data.xml",
    ],
    "installable": True,
    "application": False,
}
