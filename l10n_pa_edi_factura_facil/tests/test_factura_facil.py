# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Tests for the Factura Fácil PAC implementation.

All HTTP is mocked. The tests cover: provider registration, request
DTO mapping, response DTO mapping (success / error / parse failure),
authentication failures, retry behavior on 5xx, sanitized logging.
"""
from datetime import date
from unittest.mock import MagicMock, patch

from odoo.tests.common import BaseCase, TransactionCase, tagged

from odoo.addons.l10n_pa_edi.models.pac_provider import PACAuthError
from odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil import (
    FacturaFacilProvider,
    _sanitize_for_log,
)


def _mock_response(status: int = 200, body: str | dict = '', headers: dict | None = None):
    """Build a `requests.Response`-like MagicMock."""
    import json as _json
    if isinstance(body, dict):
        body = _json.dumps(body)
    resp = MagicMock()
    resp.status_code = status
    resp.text = body
    resp.json = lambda: _json.loads(body) if body else {}
    resp.headers = headers or {}
    return resp


@tagged('-at_install', 'post_install', 'l10n_pa_edi_factura_facil')
class TestSanitizer(BaseCase):

    def test_sanitize_redacts_api_key(self):
        s = '{"api_key": "abcd1234secret", "value": 7}'
        out = _sanitize_for_log(s)
        self.assertNotIn('abcd1234secret', out)
        self.assertIn('REDACTED', out)
        self.assertIn('"value": 7', out)

    def test_sanitize_redacts_authorization_header(self):
        s = 'Authorization: Bearer eyJabc.def.ghi'
        out = _sanitize_for_log(s)
        self.assertNotIn('eyJabc.def.ghi', out)
        self.assertIn('REDACTED', out)

    def test_sanitize_passes_clean_strings(self):
        self.assertEqual(_sanitize_for_log(''), '')
        self.assertEqual(_sanitize_for_log('hello world'), 'hello world')


@tagged('-at_install', 'post_install', 'l10n_pa_edi_factura_facil')
class TestProviderRegistration(TransactionCase):

    def test_factura_facil_in_provider_selection(self):
        choices = self.env['res.company']._l10n_pa_pac_provider_selection()
        codes = [c[0] for c in choices]
        self.assertIn('factura_facil', codes)
        self.assertIn('none', codes)  # base option still present

    def test_factura_facil_in_registry(self):
        registry = self.env['account.move']._l10n_pa_provider_registry()
        self.assertIn('factura_facil', registry)
        self.assertIs(registry['factura_facil'], FacturaFacilProvider)


@tagged('-at_install', 'post_install', 'l10n_pa_edi_factura_facil')
class TestFacturaFacilProvider(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.country_pa = cls.env.ref('base.pa')
        cls.id_ruc = cls.env.ref('l10n_pa.ruc')
        cls.company = cls.env['res.company'].create({
            'name': 'Test Factura Facil Co',
            'country_id': cls.country_pa.id,
            'currency_id': cls.env.ref('base.USD').id,
            'vat': '155718881-2-2018',
            'l10n_pa_pac_provider': 'factura_facil',
            'l10n_pa_pac_environment': 'test',
        })
        cls.env['account.chart.template'].try_loading('pa', company=cls.company, install_demo=False)
        cls.company.partner_id.l10n_latam_identification_type_id = cls.id_ruc
        cls.env.user.write({'company_ids': [(4, cls.company.id)], 'company_id': cls.company.id})
        # Set credentials so provider methods don't bail at the auth gate.
        cls.env['ir.config_parameter'].sudo().set_param(
            'l10n_pa_edi.factura_facil.api_key', 'test-bearer-key',
        )
        cls.partner = cls.env['res.partner'].with_company(cls.company).create({
            'name': 'Cliente Test',
            'country_id': cls.country_pa.id,
            'vat': '8-442-445',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pa.cedula').id,
            'l10n_pa_receiver_type': '01',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Servicio test FF',
            'list_price': 100.0,
            'type': 'service',
        })

    def _make_invoice(self):
        sale_tax = self.env['account.tax'].with_company(self.company).search([
            ('company_id', '=', self.company.id),
            ('amount', '=', 7.0),
            ('type_tax_use', '=', 'sale'),
        ], limit=1)
        inv = self.env['account.move'].with_company(self.company).create({
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
        inv.action_post()
        return inv

    def test_default_qa_base_url(self):
        provider = FacturaFacilProvider(self.company)
        self.assertEqual(provider.base_url, 'https://backend-qa-api.facturafacil.com.pa')

    def test_prod_url_when_environment_prod(self):
        self.company.l10n_pa_pac_environment = 'prod'
        try:
            provider = FacturaFacilProvider(self.company)
            self.assertEqual(provider.base_url, 'https://backend-api.facturafacil.com.pa')
        finally:
            self.company.l10n_pa_pac_environment = 'test'

    def test_send_invoice_success(self):
        provider = FacturaFacilProvider(self.company)
        inv = self._make_invoice()
        inv.l10n_pa_cufe = inv._l10n_pa_compute_cufe()
        success_body = {
            'success': True,
            'cufe': inv.l10n_pa_cufe,
            'xml_autorizado': '<rFE>signed</rFE>',
            'qr': f'cufe:{inv.l10n_pa_cufe}',
            'estado': {'codigo': '00', 'mensaje': 'Autorizada'},
        }
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            return_value=_mock_response(200, success_body),
        ):
            result = provider.send_invoice(inv)
        self.assertTrue(result.success)
        self.assertEqual(result.cufe, inv.l10n_pa_cufe)
        self.assertEqual(result.pac_status_code, '00')
        self.assertIn('signed', result.authorized_xml)

    def test_send_invoice_dgi_rejection(self):
        provider = FacturaFacilProvider(self.company)
        inv = self._make_invoice()
        inv.l10n_pa_cufe = inv._l10n_pa_compute_cufe()
        rejected_body = {
            'success': False,
            'errores': [{'codigo': 'B201', 'mensaje': 'RUC del emisor no autorizado'}],
            'estado': {'codigo': 'B201', 'mensaje': 'Rechazada'},
        }
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            return_value=_mock_response(400, rejected_body),
        ):
            result = provider.send_invoice(inv)
        self.assertFalse(result.success)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0]['code'], 'B201')

    def test_send_invoice_auth_failure(self):
        provider = FacturaFacilProvider(self.company)
        inv = self._make_invoice()
        inv.l10n_pa_cufe = inv._l10n_pa_compute_cufe()
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            return_value=_mock_response(401, '{"error":"Invalid token"}'),
        ):
            result = provider.send_invoice(inv)
        self.assertFalse(result.success)
        # Auth errors get wrapped into the failure response with PACAuthError name.
        self.assertEqual(result.errors[0]['code'], 'PACAuthError')

    def test_send_invoice_no_api_key_raises(self):
        self.env['ir.config_parameter'].sudo().set_param('l10n_pa_edi.factura_facil.api_key', '')
        try:
            provider = FacturaFacilProvider(self.company)
            inv = self._make_invoice()
            inv.l10n_pa_cufe = inv._l10n_pa_compute_cufe()
            with self.assertRaises(PACAuthError):
                provider.send_invoice(inv)
        finally:
            self.env['ir.config_parameter'].sudo().set_param(
                'l10n_pa_edi.factura_facil.api_key', 'test-bearer-key',
            )

    def test_send_invoice_5xx_retries_then_succeeds(self):
        provider = FacturaFacilProvider(self.company)
        inv = self._make_invoice()
        inv.l10n_pa_cufe = inv._l10n_pa_compute_cufe()
        success_body = {'success': True, 'cufe': inv.l10n_pa_cufe, 'estado': {'codigo': '00'}}
        responses = [
            _mock_response(503, 'Service Unavailable'),
            _mock_response(503, 'Service Unavailable'),
            _mock_response(200, success_body),
        ]
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            side_effect=responses,
        ), patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.time.sleep',
            return_value=None,
        ):
            result = provider.send_invoice(inv)
        self.assertTrue(result.success)

    def test_get_status_authorized(self):
        provider = FacturaFacilProvider(self.company)
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            return_value=_mock_response(200, {'estado': {'codigo': '00', 'mensaje': 'Autorizada'}}),
        ):
            status = provider.get_status('cufe-xyz')
        self.assertEqual(status.cufe, 'cufe-xyz')
        self.assertEqual(status.state, 'authorized')

    def test_get_status_rejected(self):
        provider = FacturaFacilProvider(self.company)
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            return_value=_mock_response(200, {'estado': {'codigo': '99', 'mensaje': 'Rechazada'}}),
        ):
            status = provider.get_status('cufe-xyz')
        self.assertEqual(status.state, 'rejected')

    def test_cancel_invoice_success(self):
        provider = FacturaFacilProvider(self.company)
        inv = self._make_invoice()
        inv.l10n_pa_cufe = 'cufe-canceltest'
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            return_value=_mock_response(200, {'success': True, 'estado': {'codigo': 'ANUL'}}),
        ):
            result = provider.cancel_invoice(inv, 'Error de captura')
        self.assertTrue(result.success)

    def test_validate_ruc_success(self):
        provider = FacturaFacilProvider(self.company)
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            return_value=_mock_response(200, {'valido': True}),
        ):
            self.assertTrue(provider.validate_ruc('155718881-2-2018', '62'))

    def test_validate_ruc_failure(self):
        provider = FacturaFacilProvider(self.company)
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            return_value=_mock_response(200, {'valido': False}),
        ):
            self.assertFalse(provider.validate_ruc('999-999-999', '99'))

    def test_send_payload_includes_unsigned_xml(self):
        provider = FacturaFacilProvider(self.company)
        inv = self._make_invoice()
        inv.l10n_pa_cufe = inv._l10n_pa_compute_cufe()
        payload = provider._build_send_payload(inv)
        self.assertEqual(payload['ruc_emisor'], inv.company_id.vat)
        self.assertEqual(payload['cufe_local'], inv.l10n_pa_cufe)
        self.assertIn('<rFE', payload['xml_dgi_base64'])
