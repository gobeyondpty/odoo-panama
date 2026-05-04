# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('pa', 'account.tax.group')
    def _get_pa_withholding_account_tax_group(self):
        return self._parse_csv(
            'pa',
            'account.tax.group',
            module='l10n_pa_account_withholding',
        )

    @template('pa', 'account.tax')
    def _get_pa_withholding_account_tax(self):
        return self._parse_csv(
            'pa',
            'account.tax',
            module='l10n_pa_account_withholding',
        )
