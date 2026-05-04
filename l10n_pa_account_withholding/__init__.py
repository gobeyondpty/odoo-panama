# Part of Odoo. See LICENSE file for full copyright and licensing details.
from . import models
from . import wizard


def _l10n_pa_withholding_post_init(env):
    """Load withholding chart data for existing Panama companies."""
    companies = env['res.company'].search([
        ('chart_template', '=', 'pa'),
        ('parent_id', '=', False),
    ])
    for company in companies:
        ChartTemplate = env['account.chart.template'].with_company(company)
        data = {
            model: ChartTemplate._parse_csv('pa', model, module='l10n_pa_account_withholding')
            for model in (
                'account.tax.group',
                'account.tax',
            )
        }
        ChartTemplate._pre_reload_data(company, {}, data)
        ChartTemplate._load_data(data)
