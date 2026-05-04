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

    def test_groups_loaded(self):
        groups = self.env['account.tax.group'].browse([
            self.env.ref('l10n_pa_account_withholding.tax_group_pa_wht_itbms').id,
            self.env.ref('l10n_pa_account_withholding.tax_group_pa_wht_isr').id,
        ])
        self.assertEqual(len(groups), 2)

    def test_all_taxes_loaded_with_correct_amounts(self):
        for xmlid, expected_amount, expected_type in EXPECTED_TAXES:
            tax = self.env.ref(f'l10n_pa_account_withholding.{xmlid}')
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
            tax = self.env.ref(f'l10n_pa_account_withholding.{xmlid}')
            self.assertTrue(
                tax.is_withholding_tax_on_payment,
                f"{xmlid} must defer until payment via the framework flag",
            )

    def test_all_taxes_negative(self):
        for xmlid, _amount, _type in EXPECTED_TAXES:
            tax = self.env.ref(f'l10n_pa_account_withholding.{xmlid}')
            self.assertLess(
                tax.amount, 0,
                f"{xmlid} must have a negative amount (withholding reduces payment)",
            )

    def test_all_taxes_country_panama(self):
        for xmlid, _amount, _type in EXPECTED_TAXES:
            tax = self.env.ref(f'l10n_pa_account_withholding.{xmlid}')
            self.assertEqual(
                tax.country_id.code, 'PA',
                f"{xmlid} must be country-scoped to Panama",
            )

    def test_no_domiciliado_coefficient(self):
        """The DGI coefficient 0.065421 is exact and matches Decreto Ejec 91/2010 art 13.

        The presentation gives a worked example: B/.100,000.00 paid → B/.6,542.10
        ITBMS retained, which confirms the percentage as 6.5421% applied to gross.
        """
        tax = self.env.ref('l10n_pa_account_withholding.tax_pa_wht_itbms_b_no_domiciliado')
        self.assertEqual(tax.amount, -6.5421)
