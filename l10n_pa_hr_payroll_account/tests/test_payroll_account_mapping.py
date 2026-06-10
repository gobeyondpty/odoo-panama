# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests.common import TransactionCase, tagged


@tagged('-at_install', 'post_install', 'l10n_pa_payroll')
class TestPaPayrollAccountMapping(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'PA Payroll Acct Co',
            'country_id': cls.env.ref('base.pa').id,
        })
        cls.env['account.chart.template'].try_loading(
            'pa', company=cls.company, install_demo=False)

    def _rule(self, xmlid):
        return self.env.ref('l10n_pa_hr_payroll.%s' % xmlid).with_company(self.company)

    def test_provision_accounts_created(self):
        for code in ('245', '246'):
            account = self.env['account.account'].with_company(self.company).search([
                ('code', '=like', code + '%'),
                ('company_ids', 'in', self.company.ids),
            ])
            self.assertEqual(len(account), 1, "Missing payroll provision account %s" % code)
            self.assertEqual(account.account_type, 'liability_current')

    def test_regular_structure_mapping(self):
        self.assertEqual(self._rule('l10n_pa_rule_basic').account_debit.code[:3], '514')
        self.assertEqual(self._rule('l10n_pa_rule_net').account_credit.code[:3], '241')
        employer = self._rule('l10n_pa_rule_css_employer')
        self.assertEqual(employer.account_debit.code[:3], '515')
        self.assertEqual(employer.account_credit.code[:3], '242')

    def test_deductions_mapped_on_debit_side(self):
        # Deduction rules compute negative totals; hr_payroll_account
        # flips sides for negative amounts, so the liability account
        # must sit on account_debit (and account_credit must stay
        # empty, or the entry self-cancels on the same account).
        for xmlid, payable in (
            ('l10n_pa_rule_css_employee', '242'),
            ('l10n_pa_rule_educational_employee', '242'),
            ('l10n_pa_rule_income_tax_employee', '244'),
            ('l10n_pa_rule_isr_representation', '244'),
            ('l10n_pa_rule_decimo_css_employee', '242'),
            ('l10n_pa_rule_liq_isr', '244'),
        ):
            deduction = self._rule(xmlid)
            self.assertEqual(deduction.account_debit.code[:3], payable, xmlid)
            self.assertFalse(deduction.account_credit, xmlid)

    def test_accrual_provisions(self):
        for xmlid, provision in (
            ('l10n_pa_rule_decimo_accrual', '243'),
            ('l10n_pa_rule_vacation_accrual', '245'),
            ('l10n_pa_rule_seniority_accrual', '246'),
            ('l10n_pa_rule_cesantia_indem_accrual', '261'),
        ):
            rule = self._rule(xmlid)
            self.assertEqual(rule.account_debit.code[:3], '514', xmlid)
            self.assertEqual(rule.account_credit.code[:3], provision, xmlid)

    def test_decimo_and_liquidacion_structures(self):
        self.assertEqual(self._rule('l10n_pa_rule_decimo_basic').account_debit.code[:3], '243')
        self.assertEqual(self._rule('l10n_pa_rule_decimo_net').account_credit.code[:3], '241')
        self.assertEqual(self._rule('l10n_pa_rule_liq_prima_antiguedad').account_debit.code[:3], '246')
        self.assertEqual(self._rule('l10n_pa_rule_liq_indemnizacion').account_debit.code[:3], '261')
        self.assertEqual(self._rule('l10n_pa_rule_liq_net').account_credit.code[:3], '241')

    def test_structures_journal_assigned(self):
        for xmlid in (
            'l10n_pa_payroll_structure_regular',
            'l10n_pa_payroll_structure_decimo',
            'l10n_pa_payroll_structure_liquidacion',
        ):
            structure = self.env.ref('l10n_pa_hr_payroll.%s' % xmlid).with_company(self.company)
            self.assertTrue(structure.journal_id, "No payroll journal on %s" % xmlid)
            self.assertEqual(structure.journal_id.code, 'SLR')
