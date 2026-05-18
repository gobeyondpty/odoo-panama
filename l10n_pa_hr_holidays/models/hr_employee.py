# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _l10n_pa_get_vacation_remaining_days(self, vacation_type):
        self.ensure_one()
        if not vacation_type:
            return 0.0
        consumed = self._get_consumed_leaves(leave_types=vacation_type, ignore_future=True)[0]
        by_type = consumed.get(self, {}).get(vacation_type, {})
        return sum(values.get("virtual_remaining_leaves", 0.0) for values in by_type.values())

    def _l10n_pa_get_vacation_allocation_start_date(self):
        self.ensure_one()
        return (
            self._get_first_contract_date(no_gap=False)
            or self._get_first_version_date(no_gap=False)
            or self.contract_date_start
            or self.date_start
            or fields.Date.context_today(self)
        )

    def _l10n_pa_ensure_vacation_allocations(self):
        vacation_type = self.env.ref("l10n_pa_hr_holidays.l10n_pa_leave_type_vacation", raise_if_not_found=False)
        accrual_plan = self.env.ref("l10n_pa_hr_holidays.l10n_pa_vacation_accrual_plan", raise_if_not_found=False)
        if not vacation_type or not accrual_plan:
            return self.env["hr.leave.allocation"]

        employees = self
        if not employees:
            employees = self.search([("active", "=", True)]).filtered(lambda employee: employee.company_id.country_id.code == "PA")

        existing = self.env["hr.leave.allocation"].search([
            ("employee_id", "in", employees.ids),
            ("holiday_status_id", "=", vacation_type.id),
            ("allocation_type", "=", "accrual"),
            ("state", "in", ("confirm", "validate1", "validate")),
        ])
        for allocation in existing.filtered(lambda allocation: not allocation.number_of_days):
            start_date = allocation.employee_id._l10n_pa_get_vacation_allocation_start_date()
            if allocation.date_from != start_date:
                vals = {"date_from": start_date}
                for field_name in ("lastcall", "actual_lastcall"):
                    if field_name in allocation._fields:
                        vals[field_name] = start_date
                if "nextcall" in allocation._fields:
                    vals["nextcall"] = False
                allocation.write(vals)
        allocated_employees = existing.employee_id

        allocations = self.env["hr.leave.allocation"]
        for employee in employees - allocated_employees:
            allocation = self.env["hr.leave.allocation"].create({
                "name": self.env._("Panama Legal Vacation Accrual"),
                "employee_id": employee.id,
                "holiday_status_id": vacation_type.id,
                "allocation_type": "accrual",
                "accrual_plan_id": accrual_plan.id,
                "date_from": employee._l10n_pa_get_vacation_allocation_start_date(),
                "number_of_days": 0.0,
            })
            allocation._action_validate()
            allocations |= allocation
        return allocations

    def _cron_l10n_pa_ensure_vacation_allocations(self):
        self._l10n_pa_ensure_vacation_allocations()
