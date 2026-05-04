# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests.common import TransactionCase, tagged


# All withholding tax xmlids in this module, with the expected effective
# rate (negative percent) and the type_tax_use direction.
EXPECTED_TAXES = [
    # literal a — Estado bienes/servicios (50% del ITBMS)
    ('tax_pa_wht_itbms_a_bs_07', -3.5, 'purchase'),
    ('tax_pa_wht_itbms_a_bs_10', -5.0, 'purchase'),
    ('tax_pa_wht_itbms_a_bs_15', -7.5, 'purchase'),
    # literal a — Estado servicios profesionales (100% del ITBMS)
    ('tax_pa_wht_itbms_a_sp_07', -7.0, 'purchase'),
    ('tax_pa_wht_itbms_a_sp_10', -10.0, 'purchase'),
    ('tax_pa_wht_itbms_a_sp_15', -15.0, 'purchase'),
    # literal b — no domiciliados (coeficiente 0.065421)
    ('tax_pa_wht_itbms_b_no_domiciliado', -6.5421, 'purchase'),
    # literal c — sociedad sin personería (50% del ITBMS)
    ('tax_pa_wht_itbms_c_bs_07', -3.5, 'purchase'),
    ('tax_pa_wht_itbms_c_bs_10', -5.0, 'purchase'),
    ('tax_pa_wht_itbms_c_bs_15', -7.5, 'purchase'),
    # literal d — gran comprador (50% del ITBMS)
    ('tax_pa_wht_itbms_d_07', -3.5, 'purchase'),
    ('tax_pa_wht_itbms_d_10', -5.0, 'purchase'),
    ('tax_pa_wht_itbms_d_15', -7.5, 'purchase'),
    # literal e — administrador de tarjetas DB/CR (50% del ITBMS)
    ('tax_pa_wht_itbms_e_07', -3.5, 'sale'),
    ('tax_pa_wht_itbms_e_10', -5.0, 'sale'),
    ('tax_pa_wht_itbms_e_15', -7.5, 'sale'),
]


@tagged('post_install', '-at_install')
class TestPanamaWithholdingTaxes(TransactionCase):
    """Verify the DGI ITBMS withholding tax data loads correctly.

    Rates are sourced from the official DGI presentation
    "Retenciones ITBMS — Ampliación de los mecanismos de retención"
    (Decreto Ejecutivo 84/2005 art 19, vigente desde 01/01/2017).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Test PA Withholding Co',
            'country_id': cls.env.ref('base.pa').id,
            'currency_id': cls.env.ref('base.USD').id,
        })
        cls.env['account.chart.template'].try_loading(
            'pa',
            company=cls.company,
            install_demo=False,
        )
        cls.company.l10n_pa_wh_agent_type = 'd'
        cls.partner = cls.env['res.partner'].create({
            'name': 'Proveedor PA',
            'country_id': cls.env.ref('base.pa').id,
            'vat': '8-442-445',
            'is_company': True,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Servicio retención',
            'type': 'service',
        })

    def _chart_ref(self, xmlid):
        return self.env['account.chart.template'].with_company(self.company).ref(xmlid)

    def test_groups_loaded(self):
        groups = self.env['account.tax.group'].browse([
            self._chart_ref('tax_group_pa_wht_itbms').id,
            self._chart_ref('tax_group_pa_wht_isr').id,
        ])
        self.assertEqual(len(groups), 2)

    def test_all_taxes_loaded_with_correct_amounts(self):
        for xmlid, expected_amount, expected_type in EXPECTED_TAXES:
            tax = self._chart_ref(xmlid)
            self.assertAlmostEqual(
                tax.amount, expected_amount, places=4,
                msg=f"{xmlid}: expected {expected_amount}, got {tax.amount}",
            )
            self.assertEqual(
                tax.type_tax_use, expected_type,
                msg=f"{xmlid}: expected type_tax_use={expected_type}, got {tax.type_tax_use}",
            )

    def test_all_taxes_marked_withholding_on_payment(self):
        for xmlid, _amount, _type in EXPECTED_TAXES:
            tax = self._chart_ref(xmlid)
            self.assertTrue(
                tax.is_withholding_tax_on_payment,
                f"{xmlid} must defer until payment via the framework flag",
            )

    def test_all_taxes_negative(self):
        for xmlid, _amount, _type in EXPECTED_TAXES:
            tax = self._chart_ref(xmlid)
            self.assertLess(
                tax.amount, 0,
                f"{xmlid} must have a negative amount (withholding reduces payment)",
            )

    def test_all_taxes_country_panama(self):
        for xmlid, _amount, _type in EXPECTED_TAXES:
            tax = self._chart_ref(xmlid)
            self.assertEqual(
                tax.country_id.code, 'PA',
                f"{xmlid} must be country-scoped to Panama",
            )

    def test_no_domiciliado_coefficient(self):
        """The DGI coefficient 0.065421 is exact and matches Decreto Ejec 91/2010 art 13.

        The presentation gives a worked example: B/.100,000.00 paid → B/.6,542.10
        ITBMS retained, which confirms the percentage as 6.5421% applied to gross.
        """
        tax = self._chart_ref('tax_pa_wht_itbms_b_no_domiciliado')
        self.assertEqual(tax.amount, -6.5421)

    def _create_bill(self):
        purchase_tax = self.env['account.tax'].with_company(self.company).search([
            ('company_id', '=', self.company.id),
            ('amount', '=', 7.0),
            ('type_tax_use', '=', 'purchase'),
        ], limit=1)
        return self.env['account.move'].with_company(self.company).create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'invoice_date': '2026-04-15',
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'name': 'Servicio',
                'quantity': 1,
                'price_unit': 100.0,
                'tax_ids': [(6, 0, purchase_tax.ids)],
            })],
        })

    def test_suggests_withholding_tax_from_company_agent_and_itbms_rate(self):
        bill = self._create_bill()
        self.assertEqual(bill.l10n_pa_wh_subject, 'd_bs')
        self.assertEqual(
            bill.l10n_pa_suggested_wh_tax_id,
            self._chart_ref('tax_pa_wht_itbms_d_07'),
        )

    def test_apply_suggested_withholding_tax_to_invoice_lines(self):
        bill = self._create_bill()
        bill.action_l10n_pa_apply_suggested_wh_tax()
        self.assertIn(
            self._chart_ref('tax_pa_wht_itbms_d_07'),
            bill.invoice_line_ids.tax_ids,
        )

    def test_form4331_export_uses_applied_withholding_taxes(self):
        bill = self._create_bill()
        bill.action_l10n_pa_apply_suggested_wh_tax()
        bill.action_post()
        wizard = self.env['l10n.pa.form4331.wizard'].with_company(self.company).create({
            'company_id': self.company.id,
            'date_from': '2026-04-01',
            'date_to': '2026-04-30',
        })
        wizard.action_generate()
        self.assertEqual(wizard.state, 'done')
        self.assertEqual(wizard.line_count, 1)
        self.assertEqual(wizard.total_base, 100.0)
        self.assertEqual(wizard.total_withheld, 3.5)
