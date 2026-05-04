# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    # Reserved for future Panama-specific withholding extensions: e.g. a
    # field linking a withholding tax to its DGI resolución number, or a
    # selection identifying the counterparty type that triggers it. The
    # framework fields (``is_withholding_tax_on_payment``, withholding
    # sequence) come from ``l10n_account_withholding_tax``.
