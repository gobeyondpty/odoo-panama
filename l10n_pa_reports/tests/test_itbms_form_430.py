# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPanamaItbmsForm430(TransactionCase):
    """Smoke tests for the Form 430 report skeleton.

    These verify the report and its line tree load. They do NOT validate
    casilla totals — the tag mappings are intentionally absent until CPA
    review of the DGI Instructivo (see DECISIONS_DEFERRED.md).
    """

    def test_report_loaded(self):
        report = self.env.ref('l10n_pa_reports.itbms_form_430')
        self.assertEqual(report.country_id.code, 'PA')
        self.assertTrue(report.line_ids)

    def test_top_level_sections(self):
        report = self.env.ref('l10n_pa_reports.itbms_form_430')
        section_ids = report.line_ids.filtered(lambda l: l.hierarchy_level == 0).mapped('id')
        expected = {
            self.env.ref('l10n_pa_reports.itbms_form_430_section_a').id,
            self.env.ref('l10n_pa_reports.itbms_form_430_section_b').id,
            self.env.ref('l10n_pa_reports.itbms_form_430_section_c').id,
            self.env.ref('l10n_pa_reports.itbms_form_430_section_d').id,
        }
        self.assertEqual(set(section_ids), expected)

    def test_menu_action_loaded(self):
        action = self.env.ref('l10n_pa_reports.action_l10n_pa_itbms_form_430')
        self.assertEqual(action.tag, 'account_report')
