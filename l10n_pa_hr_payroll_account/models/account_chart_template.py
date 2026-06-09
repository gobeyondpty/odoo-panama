# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict

from odoo import models
from odoo.addons.account.models.chart_template import template

# Payroll-specific provision accounts layered on top of the base
# `l10n_pa` chart. 243 (decimo), 261 (severance) already ship there.
_PA_PAYROLL_ACCOUNTS = {
    '245': {
        'name': "Wages Payable / Provision for Vacations",
        'name@es': "Salarios por Pagar / Provisión para Vacaciones",
        'code': '245',
        'reconcile': False,
        'account_type': 'liability_current',
    },
    '246': {
        'name': "Wages Payable / Provision for Seniority Premium",
        'name@es': "Salarios por Pagar / Provisión para Prima de Antigüedad",
        'code': '246',
        'reconcile': False,
        'account_type': 'liability_current',
    },
}


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('pa', 'account.account')
    def _get_pa_payroll_account_account(self):
        return dict(_PA_PAYROLL_ACCOUNTS)

    def _configure_payroll_account_pa(self, companies):
        # Reference mapping between the Panama salary rules
        # (l10n_pa_hr_payroll) and the l10n_pa chart. A Panama CPA must
        # review these defaults before production posting is trusted —
        # see DECISIONS_DEFERRED.md in the repo root.
        account_codes = [
            '241',  # Salaries Payable (net)
            '242',  # Social Security Expenses Payable (CSS + SE + RP)
            '243',  # Provision for Supplemental Annual Salaries (decimo)
            '244',  # Withholdings to be Deposited (ISR retained)
            '245',  # Provision for Vacations
            '246',  # Provision for Seniority Premium
            '261',  # Provision for Severance Payments (cesantia/indemnizacion)
            '514',  # Salary Expenses
            '515',  # Social Security Expenses (employer contributions)
        ]
        default_account = '514'
        self._l10n_pa_ensure_payroll_accounts(companies)
        rules_mapping = defaultdict(dict)

        def rule(xmlid):
            return self.env.ref('l10n_pa_hr_payroll.%s' % xmlid)

        # --- Panama: Regular Pay -----------------------------------
        salary_expense_rules = [
            'l10n_pa_rule_basic',
            'l10n_pa_rule_overtime_day',
            'l10n_pa_rule_overtime_mixed',
            'l10n_pa_rule_overtime_night',
            'l10n_pa_rule_rest_day',
            'l10n_pa_rule_holiday',
            'l10n_pa_rule_vacation_pay',
            'l10n_pa_rule_bonifications',
            'l10n_pa_rule_commissions',
            'l10n_pa_rule_combustible',
            'l10n_pa_rule_dieta',
            'l10n_pa_rule_salario_especie',
            'l10n_pa_rule_viaticos',
            'l10n_pa_rule_decimo_gastos_rep',
            'l10n_pa_rule_primas_produccion',
            'l10n_pa_rule_dividendo',
            'l10n_pa_rule_participacion_beneficio',
            'l10n_pa_rule_gratificacion_aguinaldo',
            'l10n_pa_rule_representation',
        ]
        for xmlid in salary_expense_rules:
            rules_mapping[rule(xmlid)]['debit'] = '514'

        # Employee deductions withheld by the employer.
        for xmlid in ('l10n_pa_rule_css_employee', 'l10n_pa_rule_educational_employee'):
            rules_mapping[rule(xmlid)]['credit'] = '242'
        for xmlid in ('l10n_pa_rule_income_tax_employee', 'l10n_pa_rule_isr_representation'):
            rules_mapping[rule(xmlid)]['credit'] = '244'

        # Employer contributions: expense against CSS payable.
        for xmlid in (
            'l10n_pa_rule_css_employer',
            'l10n_pa_rule_educational_employer',
            'l10n_pa_rule_professional_risk_employer',
        ):
            rules_mapping[rule(xmlid)]['debit'] = '515'
            rules_mapping[rule(xmlid)]['credit'] = '242'

        # Statutory accruals: expense against the matching provision.
        for xmlid, provision in (
            ('l10n_pa_rule_decimo_accrual', '243'),
            ('l10n_pa_rule_vacation_accrual', '245'),
            ('l10n_pa_rule_seniority_accrual', '246'),
            ('l10n_pa_rule_cesantia_indem_accrual', '261'),
        ):
            rules_mapping[rule(xmlid)]['debit'] = '514'
            rules_mapping[rule(xmlid)]['credit'] = provision

        rules_mapping[rule('l10n_pa_rule_net')]['credit'] = '241'

        # --- Panama: Decimo Tercer Mes -----------------------------
        # The payout consumes the provision built up by DECIMO_ACCR.
        rules_mapping[rule('l10n_pa_rule_decimo_basic')]['debit'] = '243'
        rules_mapping[rule('l10n_pa_rule_decimo_css_employee')]['credit'] = '242'
        rules_mapping[rule('l10n_pa_rule_decimo_css_employer')]['debit'] = '515'
        rules_mapping[rule('l10n_pa_rule_decimo_css_employer')]['credit'] = '242'
        rules_mapping[rule('l10n_pa_rule_decimo_net')]['credit'] = '241'

        # --- Panama: Liquidacion Laboral ---------------------------
        # Prima de antiguedad and indemnizacion consume their
        # provisions; preaviso and pending salary hit expense directly.
        rules_mapping[rule('l10n_pa_rule_liq_basic')]['debit'] = '514'
        rules_mapping[rule('l10n_pa_rule_liq_preaviso')]['debit'] = '514'
        rules_mapping[rule('l10n_pa_rule_liq_bonif')]['debit'] = '514'
        rules_mapping[rule('l10n_pa_rule_liq_prima_antiguedad')]['debit'] = '246'
        rules_mapping[rule('l10n_pa_rule_liq_indemnizacion')]['debit'] = '261'
        rules_mapping[rule('l10n_pa_rule_liq_isr')]['credit'] = '244'
        rules_mapping[rule('l10n_pa_rule_liq_net')]['credit'] = '241'

        self._configure_payroll_account(
            companies,
            "PA",
            account_codes=account_codes,
            rules_mapping=rules_mapping,
            default_account=default_account,
        )

    def _l10n_pa_ensure_payroll_accounts(self, companies):
        """Create 245/246 for companies whose `pa` chart was loaded
        before this module was installed (template data only applies on
        chart load). Registers the chart-style xmlid so a later template
        reload updates instead of duplicating."""
        AccountAccount = self.env['account.account']
        for company in companies or self.env['res.company']:
            # The pa template pads numeric codes to `code_digits` (7),
            # e.g. '241' → '2410000'. Mirror that by sizing new codes
            # after an existing chart account.
            reference = AccountAccount.with_company(company).search([
                *AccountAccount._check_company_domain(company),
                ('code', '=like', '241%'),
            ], limit=1)
            code_length = len(reference.code) if reference else 7
            for xmlid, vals in _PA_PAYROLL_ACCOUNTS.items():
                existing = AccountAccount.with_company(company).search([
                    *AccountAccount._check_company_domain(company),
                    ('code', '=like', '%s%%' % vals['code']),
                ], limit=1)
                if existing:
                    record = existing
                else:
                    record = AccountAccount.with_company(company).create({
                        'name': vals['name@es'],
                        'code': vals['code'].ljust(code_length, '0'),
                        'reconcile': vals['reconcile'],
                        'account_type': vals['account_type'],
                    })
                self.env['ir.model.data']._update_xmlids([{
                    'xml_id': 'account.%s_%s' % (company.id, xmlid),
                    'record': record,
                    'noupdate': True,
                }])
