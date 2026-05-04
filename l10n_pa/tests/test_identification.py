# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Tests for partner-level Panama identification handling."""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('-at_install', 'post_install', 'l10n_pa')
class TestPartnerIdentification(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.country_pa = cls.env.ref('base.pa')
        cls.id_ruc = cls.env.ref('l10n_pa.ruc')
        cls.id_cedula = cls.env.ref('l10n_pa.cedula')
        cls.id_pasaporte = cls.env.ref('l10n_pa.pasaporte')

    def _make_partner(self, **vals):
        defaults = {
            'name': 'Test Partner',
            'country_id': self.country_pa.id,
        }
        defaults.update(vals)
        return self.env['res.partner'].create(defaults)

    def test_identification_types_loaded(self):
        """All seven Panama identification types are present."""
        codes = ('ruc', 'cedula', 'pasaporte', 'nt', 'extranjero', 'pi', 'av')
        for code in codes:
            ref = self.env.ref(f'l10n_pa.{code}', raise_if_not_found=False)
            self.assertTrue(ref, f"Identification type 'l10n_pa.{code}' should be loaded")
            self.assertEqual(ref.country_id, self.country_pa)

    def test_dv_computed_for_cedula(self):
        partner = self._make_partner(
            vat='8-442-445',
            l10n_latam_identification_type_id=self.id_cedula.id,
        )
        self.assertEqual(partner.l10n_pa_dv, '08')

    def test_dv_computed_for_juridical_ruc(self):
        partner = self._make_partner(
            vat='11947-1027-0229562',
            l10n_latam_identification_type_id=self.id_ruc.id,
        )
        self.assertEqual(partner.l10n_pa_dv, '71')

    def test_dv_recomputes_when_vat_changes(self):
        partner = self._make_partner(
            vat='8-442-445',
            l10n_latam_identification_type_id=self.id_cedula.id,
        )
        self.assertEqual(partner.l10n_pa_dv, '08')
        # Switch to a juridical RUC. Both fields must change together so
        # the format constraint is evaluated against the new ID type.
        partner.write({
            'l10n_latam_identification_type_id': self.id_ruc.id,
            'vat': '11947-1-0229562',
        })
        self.assertEqual(partner.l10n_pa_dv, '42')

    def test_dv_empty_for_passport(self):
        """Passports cannot be DV-computed."""
        partner = self._make_partner(
            vat='PAS1311723564',
            l10n_latam_identification_type_id=self.id_pasaporte.id,
        )
        self.assertFalse(partner.l10n_pa_dv)

    def test_dv_empty_when_no_vat(self):
        partner = self._make_partner(
            l10n_latam_identification_type_id=self.id_cedula.id,
        )
        self.assertFalse(partner.l10n_pa_dv)

    def test_invalid_format_raises(self):
        with self.assertRaises(ValidationError):
            self._make_partner(
                vat='not-a-ruc!',
                l10n_latam_identification_type_id=self.id_ruc.id,
            )

    def test_format_constraint_skipped_for_non_pa_country(self):
        """A partner with country=US is not subject to PA format checks
        even if the identification type is left dangling."""
        country_us = self.env.ref('base.us')
        partner = self.env['res.partner'].create({
            'name': 'US Partner',
            'country_id': country_us.id,
            'vat': 'free-text-not-a-ruc',
        })
        self.assertEqual(partner.country_id, country_us)
