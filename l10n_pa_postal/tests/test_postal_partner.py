# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase


class TestPanamaPostalPartner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pa = cls.env.ref('base.pa')
        cls.us = cls.env.ref('base.us')

    def test_partner_decodes_full_panama_postal_code(self):
        partner = self.env['res.partner'].create({
            'name': 'Synthetic Postal Partner',
            'country_id': self.pa.id,
            'zip': 'ACC99-PJ42W',
        })

        self.assertTrue(partner.l10n_pa_postal_valid)
        self.assertEqual(partner.l10n_pa_postal_level, 'PICO')
        self.assertEqual(partner.l10n_pa_postal_estafeta_prefix, 'AC')
        self.assertAlmostEqual(partner.l10n_pa_postal_latitude, 8.94444609375)
        self.assertAlmostEqual(partner.l10n_pa_postal_longitude, -79.56167109375)

    def test_partner_legacy_zip_is_left_unvalidated(self):
        partner = self.env['res.partner'].create({
            'name': 'Synthetic Legacy ZIP Partner',
            'country_id': self.pa.id,
            'zip': '0801',
        })

        self.assertFalse(partner.l10n_pa_postal_valid)
        self.assertFalse(partner.l10n_pa_postal_level)

    def test_foreign_partner_zip_is_ignored(self):
        partner = self.env['res.partner'].create({
            'name': 'Synthetic Foreign Partner',
            'country_id': self.us.id,
            'zip': 'ACC99-PJ42W',
        })

        self.assertFalse(partner.l10n_pa_postal_valid)
