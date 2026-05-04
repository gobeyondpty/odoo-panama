# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Tests for the account.move.send EDI hook and PAC provider plumbing.

A fake provider is registered to validate the call path without
hitting any real network."""
from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_pa_edi.models.pac_provider import PACProvider, PACResponse, PACStatus


class _FakeProvider(PACProvider):
    """In-process PAC for tests; records what it received and returns a canned response."""
    code = 'fake'
    name = 'Fake PAC'
    last_call = None
    next_send_response = None  # tests can override to a PACResponse

    def send_invoice(self, move):
        type(self).last_call = ('send', move.id, move._l10n_pa_generate_xml())
        if type(self).next_send_response is not None:
            response = type(self).next_send_response
            type(self).next_send_response = None
            return response
        return PACResponse(
            success=True,
            cufe=move.l10n_pa_cufe,
            authorized_xml='<rFE>signed-stub</rFE>',
            qr_payload=f'cufe:{move.l10n_pa_cufe}',
            raw_response='{"status":"OK"}',
            pac_status_code='00',
            pac_status_message='Autorizada',
        )

    def get_status(self, cufe):
        return PACStatus(cufe=cufe, state='authorized', pac_status_code='00')

    def cancel_invoice(self, move, reason):
        return PACResponse(success=True, raw_response='{"status":"CANCELLED"}',
                           pac_status_code='00', pac_status_message='Anulada')

    def validate_ruc(self, ruc, dv):
        return True


@tagged('-at_install', 'post_install', 'l10n_pa_edi')
class TestSendMethod(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Inject 'fake' into the PAC provider Selection for the duration
        # of this test class. We patch _l10n_pa_pac_provider_selection so
        # that creating a company with provider='fake' is valid.
        Company = cls.env['res.company']
        original = Company.__class__._l10n_pa_pac_provider_selection
        cls.addClassCleanup(setattr, Company.__class__, '_l10n_pa_pac_provider_selection', original)
        Company.__class__._l10n_pa_pac_provider_selection = lambda self: [
            ('none', "Sin PAC"), ('fake', "Fake PAC"),
        ]
        # Patch the registry to surface the fake provider.
        Move = cls.env['account.move']
        original_reg = Move.__class__._l10n_pa_provider_registry
        cls.addClassCleanup(setattr, Move.__class__, '_l10n_pa_provider_registry', original_reg)
        Move.__class__._l10n_pa_provider_registry = lambda self: {'fake': _FakeProvider}

        cls.country_pa = cls.env.ref('base.pa')
        cls.id_ruc = cls.env.ref('l10n_pa.ruc')

        cls.company = cls.env['res.company'].create({
            'name': 'Test Send Co',
            'country_id': cls.country_pa.id,
            'currency_id': cls.env.ref('base.USD').id,
            'vat': '155718881-2-2018',
            'l10n_pa_pac_provider': 'fake',
            'l10n_pa_pac_environment': 'test',
        })
        cls.env['account.chart.template'].try_loading('pa', company=cls.company, install_demo=False)
        cls.company.partner_id.l10n_latam_identification_type_id = cls.id_ruc
        cls.env.user.write({'company_ids': [(4, cls.company.id)], 'company_id': cls.company.id})

        cls.partner = cls.env['res.partner'].with_company(cls.company).create({
            'name': 'Cliente Test',
            'country_id': cls.country_pa.id,
            'vat': '8-442-445',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pa.cedula').id,
            'l10n_pa_receiver_type': '01',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Servicio test send',
            'list_price': 100.0,
            'type': 'service',
        })

    def _make_invoice(self):
        sale_tax = self.env['account.tax'].with_company(self.company).search([
            ('company_id', '=', self.company.id),
            ('amount', '=', 7.0),
            ('type_tax_use', '=', 'sale'),
        ], limit=1)
        return self.env['account.move'].with_company(self.company).create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'invoice_date': date(2026, 5, 4),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'name': 'Servicio',
                'quantity': 1,
                'price_unit': 100.0,
                'tax_ids': [(6, 0, sale_tax.ids)],
            })],
        })

    def test_pa_dgi_listed_in_extra_edis(self):
        edis = self.env['account.move.send']._get_all_extra_edis()
        self.assertIn('pa_dgi', edis)
        self.assertEqual(edis['pa_dgi']['label'], 'Enviar a DGI vía PAC')

    def test_pa_dgi_applicable_for_panama_sale_invoice(self):
        inv = self._make_invoice()
        applicable = self.env['account.move.send']._is_pa_dgi_applicable(inv)
        self.assertTrue(applicable)

    def test_pa_dgi_not_applicable_without_pac(self):
        self.company.l10n_pa_pac_provider = 'none'
        inv = self._make_invoice()
        self.assertFalse(self.env['account.move.send']._is_pa_dgi_applicable(inv))
        # restore for next tests
        self.company.l10n_pa_pac_provider = 'fake'

    def test_pa_dgi_not_applicable_for_non_pa_move(self):
        """Build a move whose country_code != PA and verify it's filtered out."""
        # Use a US company that has no PA chart loaded, so the move's
        # related country_code resolves to 'US'.
        us_company = self.env['res.company'].create({
            'name': 'US Co',
            'country_id': self.env.ref('base.us').id,
            'account_fiscal_country_id': self.env.ref('base.us').id,
            'currency_id': self.env.ref('base.USD').id,
        })
        partner = self.env['res.partner'].create({
            'name': 'US Customer',
            'country_id': self.env.ref('base.us').id,
        })
        # Stub the move via search default values; we don't need a saved
        # record because _is_pa_dgi_applicable only reads attributes.
        inv = self.env['account.move'].new({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'company_id': us_company.id,
        })
        self.assertEqual(inv.country_code, 'US')
        self.assertFalse(self.env['account.move.send']._is_pa_dgi_applicable(inv))

    def test_action_send_to_pac_through_fake_provider(self):
        inv = self._make_invoice()
        inv.action_post()
        # Patch the registry to register our fake provider class.
        with (
            patch.object(
                type(self.env['account.move']),
                '_l10n_pa_provider_registry',
                return_value={'fake': _FakeProvider},
            ),
            patch.object(
                type(self.env['res.company']),
                '_l10n_pa_pac_provider_selection',
                return_value=[('none', "Sin PAC"), ('fake', "Fake PAC")],
            ),
        ):
            inv.action_l10n_pa_send_to_pac()
        self.assertEqual(inv.l10n_pa_pac_status, 'authorized')
        self.assertTrue(inv.l10n_pa_cufe)
        self.assertTrue(inv.l10n_pa_qr_payload)
        self.assertTrue(inv.l10n_pa_xml_attachment_id)
        self.assertEqual(_FakeProvider.last_call[0], 'send')

    def test_action_send_raises_when_no_provider(self):
        inv = self._make_invoice()
        inv.action_post()
        self.company.l10n_pa_pac_provider = 'none'
        with self.assertRaises(UserError):
            inv.action_l10n_pa_send_to_pac()
        self.company.l10n_pa_pac_provider = 'fake'

    def test_wizard_send_persists_rejection_status(self):
        """Regression: a PAC rejection through the wizard hook must
        flip the move status to 'rejected', not leave it at 'sent'."""
        inv = self._make_invoice()
        inv.action_post()
        # Arrange the fake PAC to return a rejection on next call.
        _FakeProvider.next_send_response = PACResponse(
            success=False,
            errors=[{'code': 'B201', 'message': 'RUC del emisor no autorizado'}],
            raw_response='{"status":"REJECTED","code":"B201"}',
            pac_status_code='B201',
            pac_status_message='RUC del emisor no autorizado',
        )
        send = self.env['account.move.send']
        invoice_data = {'extra_edis': {'pa_dgi'}, 'invoice_edi_format': False}
        send._hook_invoice_document_before_pdf_report_render(inv, invoice_data)
        # Status must reflect rejection, not 'sent'.
        self.assertEqual(inv.l10n_pa_pac_status, 'rejected')
        self.assertIn('B201', inv.l10n_pa_pac_error_codes or '')
        self.assertIn('REJECTED', inv.l10n_pa_pac_response or '')
        # invoice_data['error'] is also set so the UI surfaces it.
        self.assertIn('error', invoice_data)

    def test_alerts_flag_missing_company_dv(self):
        inv = self._make_invoice()
        inv.action_post()
        # Force-clear company VAT to trigger the preflight alert.
        old_vat = self.company.vat
        self.company.vat = False
        try:
            send = self.env['account.move.send']
            data = {inv: {
                'extra_edis': {'pa_dgi'},
                'sending_methods': set(),
                'invoice_edi_format': False,
            }}
            alerts = send._get_alerts(inv, data)
            self.assertIn('l10n_pa_edi_preflight', alerts)
            self.assertIn('RUC', alerts['l10n_pa_edi_preflight']['message'])
        finally:
            self.company.vat = old_vat
