# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.constrains('withholding_line_ids')
    def _check_l10n_pa_withholding_needs_outstanding_account(self):
        """Block withholding payments that would never post the retention.

        With Odoo 19's "payment without journal entry" flow (no outstanding
        account on the journal's payment method line), the payment stores
        its withholding lines but never turns them into journal items: at
        bank reconciliation the retained amount lands in the Bank Suspense
        account and the withholding data is silently dropped. Fail loudly
        at payment creation instead, so the operator configures the journal
        before any retention goes missing from the books.
        """
        for payment in self:
            if payment.company_id.account_fiscal_country_id.code != 'PA':
                continue
            if not payment.withholding_line_ids or payment.move_id:
                continue
            if not payment.outstanding_account_id:
                raise ValidationError(_(
                    "Withholding taxes cannot be recorded on this payment "
                    "because journal '%(journal)s' uses the flow without a "
                    "journal entry: the retained amount would end up in the "
                    "bank suspense account instead of the withholding "
                    "account.\n\nSet an outstanding account on the "
                    "'%(method)s' payment method line of that journal "
                    "(Accounting → Configuration → Journals → Incoming/"
                    "Outgoing Payments) and try again.",
                    journal=payment.journal_id.display_name,
                    method=payment.payment_method_line_id.display_name,
                ))
