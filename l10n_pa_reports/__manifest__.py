# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Panama - Accounting Reports',
    'version': '19.0.1.0.0',
    'countries': ['pa'],
    'category': 'Accounting/Localizations/Reporting',
    'summary': 'DGI Form 430 (ITBMS monthly) and annual rentas reports for Panama',
    'description': """
DGI tax reports for Panama:

- Form 430 — monthly ITBMS declaration (skeleton; line mapping awaits CPA review)
- Annual Declaración Jurada de Rentas (planned)

This module ships the report engine definitions. The detailed casilla-to-tag
mapping per the DGI Instructivo must be populated by a Panama-licensed CPA
before production filing. See ``DECISIONS_DEFERRED.md`` in the repo root.

Depends on Enterprise ``account_reports`` and the Panama base localization
(``l10n_pa``).
""",
    'author': 'Go Beyond Inc, Community',
    'website': 'https://github.com/gobeyondpty/odoo-panama',
    'license': 'LGPL-3',
    'depends': [
        'l10n_pa',
        'l10n_pa_account_withholding',
        'account_reports',
    ],
    'data': [
        'security/ir.model.access.csv',
        # itbms_form_430.xml must load first because menuitems.xml's
        # client action references the report xmlid via ref().
        'data/itbms_form_430.xml',
        'data/menuitems.xml',
        'wizard/form_43_wizard_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}
