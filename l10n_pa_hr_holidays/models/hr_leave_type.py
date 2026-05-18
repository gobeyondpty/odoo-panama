# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrLeaveType(models.Model):
    _inherit = "hr.leave.type"

    l10n_pa_is_legal_vacation = fields.Boolean(
        string="Panama Legal Vacation",
        help="Use Panama calendar-day vacation balance rules for this time off type.",
    )
