# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPanamaVacation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vacation_type = cls.env.ref("l10n_pa_hr_holidays.l10n_pa_leave_type_vacation")
        cls.employee = cls.env["hr.employee"].create({
            "name": "Synthetic Panama Employee",
            "company_id": cls.env.company.id,
        })

    def test_vacation_duration_uses_calendar_days(self):
        leave = self.env["hr.leave"].new({
            "employee_id": self.employee.id,
            "holiday_status_id": self.vacation_type.id,
            "request_date_from": datetime(2026, 1, 2).date(),
            "request_date_to": datetime(2026, 1, 5).date(),
        })
        leave._compute_date_from_to()
        leave._compute_l10n_pa_legal_vacation_days()
        durations = leave._get_durations()

        self.assertEqual(leave.l10n_pa_legal_vacation_days, 4.0)
        self.assertEqual(durations[leave.id][0], 4.0)

    def test_ensure_vacation_allocation(self):
        allocations = self.employee._l10n_pa_ensure_vacation_allocations()

        self.assertEqual(len(allocations), 1)
        self.assertEqual(allocations.holiday_status_id, self.vacation_type)
        self.assertEqual(allocations.allocation_type, "accrual")
        self.assertEqual(allocations.state, "validate")

    def test_existing_empty_allocation_realigns_to_imported_start_date(self):
        allocations = self.employee._l10n_pa_ensure_vacation_allocations()
        self.employee.contract_date_start = date(2024, 1, 1)

        second_call = self.employee._l10n_pa_ensure_vacation_allocations()

        self.assertFalse(second_call)
        self.assertEqual(allocations.date_from, date(2024, 1, 1))
        if "nextcall" in allocations._fields:
            self.assertFalse(allocations.nextcall)
