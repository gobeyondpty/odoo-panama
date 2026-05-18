# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo import api, fields, models


class HrLeave(models.Model):
    _inherit = "hr.leave"

    l10n_pa_legal_vacation_days = fields.Float(
        string="Panama Legal Vacation Days",
        compute="_compute_l10n_pa_legal_vacation_days",
        store=True,
        help="Calendar days consumed for Panama legal vacation compliance.",
    )
    l10n_pa_vacation_compliance_warning = fields.Text(
        string="Panama Vacation Compliance Warning",
        compute="_compute_l10n_pa_vacation_compliance_warning",
    )

    @api.depends("request_date_from", "request_date_to", "holiday_status_id.l10n_pa_is_legal_vacation")
    def _compute_l10n_pa_legal_vacation_days(self):
        for leave in self:
            if leave.holiday_status_id.l10n_pa_is_legal_vacation:
                leave.l10n_pa_legal_vacation_days = leave._l10n_pa_get_calendar_days()
            else:
                leave.l10n_pa_legal_vacation_days = 0.0

    @api.depends(
        "date_from",
        "employee_id",
        "holiday_status_id.l10n_pa_is_legal_vacation",
        "l10n_pa_legal_vacation_days",
        "state",
    )
    def _compute_l10n_pa_vacation_compliance_warning(self):
        today = fields.Date.context_today(self)
        for leave in self:
            warnings = []
            if leave.holiday_status_id.l10n_pa_is_legal_vacation:
                if leave.l10n_pa_legal_vacation_days > 30:
                    warnings.append(
                        self.env._(
                            "This request consumes %(days).2f calendar days. Panama vacation is normally taken as "
                            "30 continuous days, with limited splitting rules.",
                            days=leave.l10n_pa_legal_vacation_days,
                        )
                    )
                if leave.request_date_from:
                    days_until_start = (leave.request_date_from - today).days
                    if 0 <= days_until_start < 3:
                        warnings.append(
                            self.env._(
                                "Panama vacation pay must be liquidated and paid at least 3 days before vacation starts."
                            )
                        )
                if leave.employee_id and leave.state in ("confirm", "validate1", "validate"):
                    remaining = leave.employee_id._l10n_pa_get_vacation_remaining_days(leave.holiday_status_id)
                    if remaining > 60:
                        warnings.append(
                            self.env._(
                                "This employee has more than two Panama vacation periods available. Review accumulation "
                                "and scheduling compliance."
                            )
                        )
            leave.l10n_pa_vacation_compliance_warning = "\n".join(warnings)

    def _l10n_pa_get_calendar_days(self):
        self.ensure_one()
        date_from = self.request_date_from or (self.date_from and self.date_from.date())
        date_to = self.request_date_to or (self.date_to and self.date_to.date())
        if not date_from or not date_to:
            return 0.0
        if isinstance(date_from, str):
            date_from = fields.Date.to_date(date_from)
        if isinstance(date_to, str):
            date_to = fields.Date.to_date(date_to)
        if not isinstance(date_from, date) or not isinstance(date_to, date) or date_to < date_from:
            return 0.0
        return float((date_to - date_from).days + 1)

    def _get_durations(self, check_leave_type=True, resource_calendar=None):
        durations = super()._get_durations(check_leave_type=check_leave_type, resource_calendar=resource_calendar)
        for leave in self.filtered(lambda rec: rec.holiday_status_id.l10n_pa_is_legal_vacation):
            days, hours = durations.get(leave.id, (0.0, 0.0))
            durations[leave.id] = (leave._l10n_pa_get_calendar_days(), hours)
        return durations
