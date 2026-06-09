# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Tests for the Factura Fácil PAC implementation.

All HTTP is mocked at the ``requests.request`` level. The suite covers
provider registration, request DTO mapping against the JSON shape
documented in ``Documentacion API FF V1.pdf``, response DTO mapping
(success / rejection / parse failure), authentication failures, retry
behavior on 5xx, sanitized logging, the CUFE-keyed status lookup over
``find_by_cufe_or_id``, the Anulación event flow of ``cancel_invoice``,
and the local-DV ``validate_ruc``.
"""
import json as _json
from datetime import date
from unittest.mock import MagicMock, patch

from odoo.tests.common import BaseCase, TransactionCase, tagged

from odoo.addons.l10n_pa_edi.models.pac_provider import PACAuthError
from odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil import (
    DEFAULT_PROD_BASE_URL,
    DEFAULT_QA_BASE_URL,
    ENDPOINT_EVENT_ISSUE,
    ENDPOINT_FIND,
    ENDPOINT_SEND,
    FacturaFacilProvider,
    _sanitize_for_log,
)


_DEMO_COMPANY_UUID = '98e3a5be-5699-48ab-a04c-fa6d5a560838'
_DEMO_BRANCH_UUID = 'c5cac240-e818-41bc-9e5f-141e8092d056'
_DEMO_API_KEY = 'test-api-key-do-not-use-in-prod'


def _mock_response(status: int = 200, body='', headers: dict | None = None):
    """Build a ``requests.Response``-like MagicMock."""
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

    def test_sanitize_redacts_api_key_in_json(self):
        out = _sanitize_for_log('{"api_key": "abcd1234secret", "value": 7}')
        self.assertNotIn('abcd1234secret', out)
        self.assertIn('REDACTED', out)
        self.assertIn('"value": 7', out)

    def test_sanitize_redacts_x_ff_api_key_header(self):
        out = _sanitize_for_log('X-FF-API-Key: SBD44oT1aH7epw2Khop8AGm')
        self.assertNotIn('SBD44oT1aH7epw2Khop8AGm', out)
        self.assertIn('REDACTED', out)

    def test_sanitize_redacts_bearer(self):
        out = _sanitize_for_log('Authorization: Bearer eyJabc.def.ghi')
        self.assertNotIn('eyJabc.def.ghi', out)
        self.assertIn('REDACTED', out)

    def test_sanitize_passes_clean_strings(self):
        self.assertEqual(_sanitize_for_log(''), '')
        self.assertEqual(_sanitize_for_log('hello world'), 'hello world')


@tagged('-at_install', 'post_install', 'l10n_pa_edi_factura_facil')
class TestProviderRegistration(TransactionCase):

    def test_factura_facil_in_provider_selection(self):
        codes = [c[0] for c in self.env['res.company']._l10n_pa_pac_provider_selection()]
        self.assertIn('factura_facil', codes)
        self.assertIn('none', codes)

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
            'l10n_pa_factura_facil_company_uuid': _DEMO_COMPANY_UUID,
            'l10n_pa_factura_facil_branch_uuid': _DEMO_BRANCH_UUID,
            'l10n_pa_factura_facil_api_key': _DEMO_API_KEY,
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
            'name': 'Servicio test FF',
            'list_price': 100.0,
            'type': 'service',
            'default_code': 'TEST-FF',
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

    # ---- Configuration accessors -------------------------------------

    def test_default_qa_base_url(self):
        provider = FacturaFacilProvider(self.company)
        self.assertEqual(provider.base_url, DEFAULT_QA_BASE_URL)
        self.assertEqual(provider.ff_environment, '2')

    def test_prod_base_url_and_env_code(self):
        self.company.l10n_pa_pac_environment = 'prod'
        try:
            provider = FacturaFacilProvider(self.company)
            self.assertEqual(provider.base_url, DEFAULT_PROD_BASE_URL)
            self.assertEqual(provider.ff_environment, '1')
        finally:
            self.company.l10n_pa_pac_environment = 'test'

    def test_missing_credentials_raises_auth_error(self):
        self.company.l10n_pa_factura_facil_api_key = False
        try:
            with self.assertRaises(PACAuthError):
                FacturaFacilProvider(self.company)._require_credentials()
        finally:
            self.company.l10n_pa_factura_facil_api_key = _DEMO_API_KEY

    # ---- send_invoice payload shape ----------------------------------

    def test_send_payload_matches_ff_schema(self):
        provider = FacturaFacilProvider(self.company)
        inv = self._make_invoice()
        inv.l10n_pa_cufe = inv._l10n_pa_compute_cufe()
        payload = provider._build_send_payload(inv)

        # Top-level shape per `Documentacion API FF V1.pdf §1.1`.
        self.assertEqual(set(payload.keys()), {'header', 'document'})
        self.assertEqual(payload['header']['environment'], '2')

        doc = payload['document']
        self.assertEqual(doc['type'], '01')  # Factura
        self.assertIsInstance(doc['fd_number'], int)
        self.assertGreaterEqual(doc['fd_number'], 1)

        rec = doc['receptor']
        self.assertEqual(rec['type'], '01')
        self.assertEqual(rec['ruc_type'], '1')
        self.assertEqual(rec['ruc'], '8-442-445')
        # DV is required for Contribuyente and Gobierno (type 01/03).
        self.assertIn('dv', rec)

        self.assertEqual(len(doc['items']), 1)
        item = doc['items'][0]
        self.assertEqual(item['line'], 1)
        self.assertEqual(item['price'], '100.00')
        self.assertEqual(item['quantity'], '1.00')
        self.assertEqual(item['internal_code'], 'TEST-FF')
        self.assertEqual(len(item['taxes']), 1)
        self.assertEqual(item['taxes'][0]['type'], '01')
        self.assertEqual(item['taxes'][0]['code'], '01')  # 7% ITBMS

        # `payments[]` is required by the schema.
        self.assertEqual(len(doc['payments']), 1)
        self.assertEqual(doc['payments'][0]['type'], '01')
        self.assertEqual(doc['payments'][0]['amount'], '107.00')
        self.assertEqual(doc['total'], '107.00')

    def test_send_payload_consumidor_final_omits_dv(self):
        consumer = self.env['res.partner'].with_company(self.company).create({
            'name': 'Consumidor Final',
            'country_id': self.country_pa.id,
            'l10n_pa_receiver_type': '02',
        })
        sale_tax = self.env['account.tax'].with_company(self.company).search([
            ('company_id', '=', self.company.id),
            ('amount', '=', 7.0),
            ('type_tax_use', '=', 'sale'),
        ], limit=1)
        inv = self.env['account.move'].with_company(self.company).create({
            'move_type': 'out_invoice',
            'partner_id': consumer.id,
            'company_id': self.company.id,
            'invoice_date': date(2026, 5, 4),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'name': 'Servicio',
                'quantity': 1,
                'price_unit': 50.0,
                'tax_ids': [(6, 0, sale_tax.ids)],
            })],
        })
        inv.action_post()

        rec = FacturaFacilProvider(self.company)._build_send_payload(inv)['document']['receptor']
        self.assertEqual(rec['type'], '02')
        self.assertNotIn('dv', rec)

    def test_send_payload_includes_cpbs_uom_and_default_code(self):
        """When a product carries CPBS + EDI UoM + default_code, those
        propagate to the FF item as `gns`, `mu`, and `internal_code`.
        Regression for the DGI 2007 notification ('CPBS code missing')."""
        cpbs = self.env['l10n_pa_edi.cpbs'].search([('code', '=', '9012')], limit=1)
        uom = self.env['l10n_pa_edi.uom'].search([('code', '=', 'und')], limit=1)
        self.assertTrue(cpbs and uom, "Test depends on the seeded DGI catalog")
        self.product.product_tmpl_id.write({
            'l10n_pa_edi_cpbs_id': cpbs.id,
            'l10n_pa_edi_uom_id': uom.id,
        })
        inv = self._make_invoice()
        inv.l10n_pa_cufe = inv._l10n_pa_compute_cufe()
        item = FacturaFacilProvider(self.company)._build_send_payload(inv)['document']['items'][0]
        self.assertEqual(item['gns'], '9012')
        self.assertEqual(item['mu'], 'und')
        self.assertEqual(item['internal_code'], 'TEST-FF')

    def test_send_payload_discount_is_balboa_amount_per_unit(self):
        """FF §1.1 items.discount: 'valor del descuento en Balboas, no en
        porcentaje'. A 10% discount on a B/.100.00 unit price is '10.00',
        and the ITBMS amount is computed on the discounted base."""
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
                'quantity': 2,
                'price_unit': 100.0,
                'discount': 10.0,
                'tax_ids': [(6, 0, sale_tax.ids)],
            })],
        })
        inv.action_post()
        inv.l10n_pa_cufe = inv._l10n_pa_compute_cufe()

        item = FacturaFacilProvider(self.company)._build_send_payload(inv)['document']['items'][0]
        self.assertEqual(item['price'], '100.00')
        self.assertEqual(item['quantity'], '2.00')
        self.assertEqual(item['discount'], '10.00')
        # 7% × (2 × B/.90.00) = B/.12.60 — not the percentage, not doubled.
        self.assertEqual(item['taxes'][0]['amount'], '12.60')

    def test_send_payload_multi_tax_line_reports_per_tax_amounts(self):
        """A line with ITBMS + ISC must report each tax's own share, not
        the line's combined tax delta duplicated into every entry."""
        sale_tax = self.env['account.tax'].with_company(self.company).search([
            ('company_id', '=', self.company.id),
            ('amount', '=', 7.0),
            ('type_tax_use', '=', 'sale'),
        ], limit=1)
        isc_group = self.env['account.tax.group'].with_company(self.company).create({
            'name': 'ISC',
            'country_id': self.country_pa.id,
        })
        isc_tax = self.env['account.tax'].with_company(self.company).create({
            'name': 'ISC 5%',
            'amount': 5.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'tax_group_id': isc_group.id,
            'country_id': self.country_pa.id,
        })
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
                'tax_ids': [(6, 0, (sale_tax + isc_tax).ids)],
            })],
        })
        inv.action_post()
        inv.l10n_pa_cufe = inv._l10n_pa_compute_cufe()

        taxes = FacturaFacilProvider(self.company)._build_send_payload(inv)['document']['items'][0]['taxes']
        by_type = {t['type']: t for t in taxes}
        self.assertEqual(set(by_type), {'01', '03'})
        self.assertEqual(by_type['01']['amount'], '7.00')
        self.assertEqual(by_type['03']['amount'], '5.00')
        self.assertEqual(by_type['03']['rate'], '5.00')

    def test_send_payload_credit_note_includes_referred(self):
        sale_tax = self.env['account.tax'].with_company(self.company).search([
            ('company_id', '=', self.company.id),
            ('amount', '=', 7.0),
            ('type_tax_use', '=', 'sale'),
        ], limit=1)
        origin = self.env['account.move'].with_company(self.company).create({
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
        origin.action_post()
        origin.l10n_pa_cufe = (
            'FE0120002155718881-2-2018000010000010'
            '20260504010000001234567890ABCDEFGH'
        )[:66]

        reversal_wizard = self.env['account.move.reversal'].with_company(self.company).create({
            'move_ids': [(6, 0, origin.ids)],
            'journal_id': origin.journal_id.id,
        })
        action = reversal_wizard.reverse_moves()
        refund = self.env['account.move'].browse(action['res_id'])

        payload = FacturaFacilProvider(self.company)._build_send_payload(refund)
        self.assertEqual(payload['document']['type'], '04')
        self.assertIn('referred', payload['document'])
        self.assertEqual(payload['document']['referred']['fd_number'], origin.l10n_pa_cufe)

    # ---- HTTP success / error / retry --------------------------------

    def test_send_invoice_success(self):
        provider = FacturaFacilProvider(self.company)
        inv = self._make_invoice()
        inv.l10n_pa_cufe = inv._l10n_pa_compute_cufe()
        body = {
            'service_response': 'OK',
            'cufe': inv.l10n_pa_cufe,
            'document_uuid': 'doc-uuid-1',
            'authorization_number': '0001-2026',
            'process_date': '2026-05-04T10:00:00',
            'qr_code_data': f'cufe:{inv.l10n_pa_cufe}',
            'xml': '<rFE>signed</rFE>',
            'rejected': False,
            'messages': [],
        }
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            return_value=_mock_response(201, body),
        ) as mock_req:
            result = provider.send_invoice(inv)

        self.assertTrue(result.success)
        self.assertEqual(result.cufe, inv.l10n_pa_cufe)
        self.assertEqual(result.pac_status_code, '0001-2026')
        self.assertEqual(result.extra['document_uuid'], 'doc-uuid-1')
        self.assertIn('signed', result.authorized_xml)

        # The call must hit /api/pac/reception_fe/detailed/ (not /pac/...).
        called_url = mock_req.call_args.args[1]
        self.assertTrue(called_url.endswith(ENDPOINT_SEND), called_url)

        # FF-specific auth headers are sent.
        sent_headers = mock_req.call_args.kwargs['headers']
        self.assertEqual(sent_headers['X-FF-Company'], _DEMO_COMPANY_UUID)
        self.assertEqual(sent_headers['X-FF-Branch'], _DEMO_BRANCH_UUID)
        self.assertEqual(sent_headers['X-FF-API-Key'], _DEMO_API_KEY)
        self.assertNotIn('Authorization', sent_headers)

    def test_send_invoice_rejected_by_dgi(self):
        provider = FacturaFacilProvider(self.company)
        inv = self._make_invoice()
        inv.l10n_pa_cufe = inv._l10n_pa_compute_cufe()
        body = {
            'rejected': True,
            'cufe': '',
            'messages': [
                {'code': 'B201', 'message': 'RUC del emisor no autorizado', 'type': 'R'},
            ],
        }
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            return_value=_mock_response(201, body),
        ):
            result = provider.send_invoice(inv)
        self.assertFalse(result.success)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0]['code'], 'B201')

    def test_send_invoice_auth_failure_wrapped(self):
        provider = FacturaFacilProvider(self.company)
        inv = self._make_invoice()
        inv.l10n_pa_cufe = inv._l10n_pa_compute_cufe()
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            return_value=_mock_response(401, '{"detail":"Invalid token"}'),
        ):
            result = provider.send_invoice(inv)
        self.assertFalse(result.success)
        self.assertEqual(result.errors[0]['code'], 'PACAuthError')

    def test_send_invoice_no_api_key_returns_failure(self):
        self.company.l10n_pa_factura_facil_api_key = False
        try:
            provider = FacturaFacilProvider(self.company)
            inv = self._make_invoice()
            inv.l10n_pa_cufe = inv._l10n_pa_compute_cufe()
            result = provider.send_invoice(inv)
            self.assertFalse(result.success)
            self.assertEqual(result.errors[0]['code'], 'PACAuthError')
        finally:
            self.company.l10n_pa_factura_facil_api_key = _DEMO_API_KEY

    def test_send_invoice_5xx_then_success(self):
        provider = FacturaFacilProvider(self.company)
        inv = self._make_invoice()
        inv.l10n_pa_cufe = inv._l10n_pa_compute_cufe()
        success_body = {
            'cufe': inv.l10n_pa_cufe,
            'rejected': False,
            'authorization_number': '0001-2026',
        }
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            side_effect=[
                _mock_response(503, 'Service Unavailable'),
                _mock_response(503, 'Service Unavailable'),
                _mock_response(201, success_body),
            ],
        ), patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.time.sleep',
            return_value=None,
        ):
            result = provider.send_invoice(inv)
        self.assertTrue(result.success)

    # ---- get_status via find_by_cufe_or_id ---------------------------

    def test_get_status_in_process_is_pending(self):
        # FF status `1` has no confirmed live meaning; it must never flip
        # a document to Authorized — only 3 ("Finalizado") does.
        provider = FacturaFacilProvider(self.company)
        body = {
            'id': 'doc-uuid-1',
            'cufe': 'target-cufe',
            'status': 1,
            'status_display': 'En proceso',
            'created_at': '2026-05-04T10:00:00',
            'updated_at': '2026-05-04T10:00:00',
        }
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            return_value=_mock_response(200, body),
        ) as mock_req:
            status = provider.get_status('target-cufe')

        self.assertEqual(status.state, 'pending')
        self.assertEqual(status.pac_status_code, '1')
        self.assertEqual(status.pac_status_message, 'En proceso')

        # Endpoint + query param.
        self.assertTrue(mock_req.call_args.args[1].endswith(ENDPOINT_FIND))
        self.assertEqual(mock_req.call_args.kwargs['params'], {'cufe_or_id': 'target-cufe'})

    def test_get_status_rejected(self):
        provider = FacturaFacilProvider(self.company)
        body = {'id': 'x', 'cufe': 'reject-cufe', 'status': 10, 'status_display': 'Rechazada'}
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            return_value=_mock_response(200, body),
        ):
            status = provider.get_status('reject-cufe')
        self.assertEqual(status.state, 'rejected')

    def test_get_status_finalized_is_authorized(self):
        provider = FacturaFacilProvider(self.company)
        body = {'id': 'x', 'cufe': 'fin-cufe', 'status': 3, 'status_display': 'Finalizado'}
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            return_value=_mock_response(200, body),
        ):
            status = provider.get_status('fin-cufe')
        self.assertEqual(status.state, 'authorized')

    def test_get_status_anulado_is_cancelled(self):
        provider = FacturaFacilProvider(self.company)
        body = {'id': 'x', 'cufe': 'anul-cufe', 'status': 50, 'status_display': 'Anulado'}
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            return_value=_mock_response(200, body),
        ):
            status = provider.get_status('anul-cufe')
        self.assertEqual(status.state, 'cancelled')

    def test_get_status_404_returns_unknown(self):
        provider = FacturaFacilProvider(self.company)
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            return_value=_mock_response(404, '{"detail":"Not found"}'),
        ):
            status = provider.get_status('missing-cufe')
        self.assertEqual(status.state, 'unknown')

    def test_get_status_empty_cufe(self):
        status = FacturaFacilProvider(self.company).get_status('')
        self.assertEqual(status.state, 'unknown')

    # ---- cancel_invoice + validate_ruc -------------------------------

    def test_cancel_invoice_success(self):
        provider = FacturaFacilProvider(self.company)
        inv = self._make_invoice()
        inv.l10n_pa_cufe = 'cufe-canceltest'
        body = {
            'id': 'evt-1',
            'type': 'AN',
            'cufe': inv.l10n_pa_cufe,
            'response_ff': 'OK',
            'response_dgi': 'Anulada',
            'rejected': False,
            'auth_date': '2026-05-19T10:00:00',
        }
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            return_value=_mock_response(201, body),
        ) as mock_req:
            result = provider.cancel_invoice(inv, 'Error de captura del operador')

        self.assertTrue(result.success)
        self.assertEqual(result.extra['event_id'], 'evt-1')
        self.assertTrue(mock_req.call_args.args[1].endswith(ENDPOINT_EVENT_ISSUE))
        sent_body = _json.loads(mock_req.call_args.kwargs['data'])
        self.assertEqual(sent_body['type'], 'AN')
        self.assertEqual(sent_body['cufe'], 'cufe-canceltest')
        self.assertEqual(sent_body['reason'], 'Error de captura del operador')

    def test_cancel_invoice_no_cufe(self):
        provider = FacturaFacilProvider(self.company)
        inv = self._make_invoice()
        inv.l10n_pa_cufe = False
        result = provider.cancel_invoice(inv, 'whatever')
        self.assertFalse(result.success)
        self.assertEqual(result.errors[0]['code'], 'NO_CUFE')

    def test_cancel_invoice_rejected(self):
        provider = FacturaFacilProvider(self.company)
        inv = self._make_invoice()
        inv.l10n_pa_cufe = 'cufe-rejtest'
        body = {
            'id': 'evt-2', 'type': 'AN', 'cufe': inv.l10n_pa_cufe,
            'rejected': True, 'code': 'X99', 'message': 'Plazo vencido',
        }
        with patch(
            'odoo.addons.l10n_pa_edi_factura_facil.pac_providers.factura_facil.requests.request',
            return_value=_mock_response(201, body),
        ):
            result = provider.cancel_invoice(inv, 'tarde')
        self.assertFalse(result.success)
        self.assertEqual(result.errors[0]['code'], 'X99')

    def test_validate_ruc_matches_local_dv(self):
        provider = FacturaFacilProvider(self.company)
        # `8-442-445` was used for cls.partner with DV computable locally.
        partner_dv = self.partner.l10n_pa_dv
        self.assertTrue(partner_dv)
        self.assertTrue(provider.validate_ruc('8-442-445', partner_dv))
        self.assertFalse(provider.validate_ruc('8-442-445', '99'))

    def test_validate_ruc_handles_garbage(self):
        provider = FacturaFacilProvider(self.company)
        self.assertFalse(provider.validate_ruc('', '00'))
        self.assertFalse(provider.validate_ruc('not-a-ruc', '00'))
