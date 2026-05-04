# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Panama - Withholding Taxes',
    'version': '19.0.1.0.1',
    'countries': ['pa'],
    'category': 'Accounting/Localizations',
    'summary': 'DGI ITBMS and ISR retentions for Panama',
    'description': """
Panama withholding tax templates for credit-card processor settlements,
government counterparties, and other DGI-mandated retention scenarios.

This module wires up the framework. The actual withholding rates and the
list of counterparty types that trigger withholding-agent status must be
configured by a Panama-licensed CPA. See ``DECISIONS_DEFERRED.md`` in the
repo root.

Depends on the Enterprise withholding-on-payment framework
(``l10n_account_withholding_tax``) and the Panama base localization
(``l10n_pa``).
""",
    'author': 'Go Beyond Inc, Community',
    'website': 'https://github.com/gobeyondpty/odoo-panama',
    'license': 'LGPL-3',
    'depends': [
        'l10n_pa',
        'l10n_account_withholding_tax',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'wizard/form_4331_wizard_views.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'post_init_hook': '_l10n_pa_withholding_post_init',
}
