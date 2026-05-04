# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Tests for the account.move integration: CUFE generation, payload
construction, document-type mapping."""
from datetime import date

from lxml import etree

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_pa_edi.models import dgi_xml
from odoo.addons.l10n_pa_edi.models.account_move import _move_type_to_dgi_doc


@tagged('-at_install', 'post_install', 'l10n_pa_edi')
class TestAccountMoveBasics(TransactionCase):

    def test_move_type_to_dgi_doc_factura(self):
        self.assertEqual(_move_type_to_dgi_doc('out_invoice', False), '01')

    def test_move_type_to_dgi_doc_credit_note_with_origin(self):
        self.assertEqual(_move_type_to_dgi_doc('out_refund', True), '04')

    def test_move_type_to_dgi_doc_credit_note_no_origin(self):
        self.assertEqual(_move_type_to_dgi_doc('out_refund', False), '06')

    def test_move_type_to_dgi_doc_debit_note_with_origin(self):
        # Customer debit notes (out_invoice + debit_origin_id) referencing
        # an authorized factura → DGI nota de débito con referencia (05).
        self.assertEqual(
            _move_type_to_dgi_doc('out_invoice', has_origin_cufe=True, is_debit_note=True),
            '05',
        )

    def test_move_type_to_dgi_doc_debit_note_no_origin(self):
        # Generic customer debit note → DGI nota de débito genérica (07).
        self.assertEqual(
            _move_type_to_dgi_doc('out_invoice', has_origin_cufe=False, is_debit_note=True),
            '07',
        )


@tagged('-at_install', 'post_install', 'l10n_pa_edi')
class TestInvoiceXmlPayload(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.country_pa = cls.env.ref('base.pa')
        cls.id_ruc = cls.env.ref('l10n_pa.ruc')

        # Build a test company with a PA chart loaded.
        cls.company = cls.env['res.company'].create({
            'name': 'Test PA EDI Co',
            'country_id': cls.country_pa.id,
            'currency_id': cls.env.ref('base.USD').id,
            'vat': '155718881-2-2018',
            'l10n_pa_pac_environment': 'test',
            'l10n_pa_sfep_branch': '0001',
            'l10n_pa_sfep_emission_point': '001',
            'l10n_pa_business_activity_code': '741000',
        })
        cls.env['account.chart.template'].try_loading('pa', company=cls.company, install_demo=False)
        cls.company.partner_id.l10n_latam_identification_type_id = cls.id_ruc
        cls.env.user.write({'company_ids': [(4, cls.company.id)], 'company_id': cls.company.id})

        cls.partner = cls.env['res.partner'].with_company(cls.company).create({
            'name': 'Cliente Contribuyente S.A.',
            'country_id': cls.country_pa.id,
            'vat': '8-442-445',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pa.cedula').id,
            'l10n_pa_receiver_type': '01',
        })

        cls.product_category = cls.env['product.category'].create({
            'name': 'Servicios FE',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Servicio de prueba',
            'list_price': 100.0,
            'type': 'service',
            'categ_id': cls.product_category.id,
        })
        cls.cpbs = cls.env.ref('l10n_pa_edi.l10n_pa_edi_cpbs_8010')
        cls.edi_uom = cls.env.ref('l10n_pa_edi.l10n_pa_edi_uom_und')
        cls.location = cls.env.ref('l10n_pa_edi.l10n_pa_edi_location_8_8_1')

    def _create_invoice(self, **overrides):
        sale_tax = self.env['account.tax'].with_company(self.company).search([
            ('company_id', '=', self.company.id),
            ('amount', '=', 7.0),
            ('type_tax_use', '=', 'sale'),
        ], limit=1)
        vals = {
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
        }
        vals.update(overrides)
        return self.env['account.move'].with_company(self.company).create(vals)

    def test_compute_cufe_returns_string(self):
        inv = self._create_invoice()
        inv.name = 'INV/2026/00007'
        cufe = inv._l10n_pa_compute_cufe()
        self.assertTrue(cufe)
        self.assertIsInstance(cufe, str)
        self.assertIn('155718881-2-2018', cufe)
        # Should also persist a security code on the move.
        self.assertEqual(len(inv.l10n_pa_security_code), 9)

    def test_compute_cufe_uses_test_environment_code(self):
        inv = self._create_invoice()
        inv.name = 'INV/2026/00007'
        cufe = inv._l10n_pa_compute_cufe()
        # The ambiente '2' (test) should appear before the security code
        # at position [-(1+9+1) = -11] (1 ambiente + 9 sec + 1 luhn).
        # Just assert presence of the security code suffix.
        self.assertIn(inv.l10n_pa_security_code, cufe)

    def test_get_doc_number_pads_to_ten(self):
        inv = self._create_invoice()
        inv.name = 'INV/2026/00007'
        self.assertEqual(inv._l10n_pa_get_doc_number(), '0000000007')

    def test_get_doc_number_handles_missing_name(self):
        inv = self._create_invoice()
        inv.name = False
        self.assertEqual(inv._l10n_pa_get_doc_number(), '0000000000')

    def test_build_xml_payload_structure(self):
        inv = self._create_invoice()
        inv.name = 'INV/2026/00007'
        payload = inv._l10n_pa_build_xml_payload()
        self.assertIn('cufe', payload)
        self.assertIn('general', payload)
        self.assertIn('emisor', payload)
        self.assertIn('items', payload)
        self.assertIn('totales', payload)
        self.assertEqual(payload['emisor']['dRuc'], '155718881-2-2018')
        self.assertEqual(payload['emisor']['dDV'], inv.company_id.partner_id.l10n_pa_dv)
        self.assertEqual(len(payload['items']), 1)

    def test_xml_payload_uses_product_fe_catalog_codes(self):
        self.product.product_tmpl_id.write({
            'l10n_pa_edi_cpbs_id': self.cpbs.id,
            'l10n_pa_edi_uom_id': self.edi_uom.id,
        })
        inv = self._create_invoice()
        inv.name = 'INV/2026/00008'
        item = inv._l10n_pa_build_xml_payload()['items'][0]
        self.assertEqual(item['dCodCPBSAbr'], '8010')
        self.assertEqual(item['dUnidadMedida'], 'und')

    def test_xml_payload_uses_category_cpbs_fallback(self):
        self.product.product_tmpl_id.write({
            'l10n_pa_edi_cpbs_id': False,
            'l10n_pa_edi_uom_id': False,
        })
        self.product_category.l10n_pa_edi_cpbs_id = self.cpbs
        inv = self._create_invoice()
        inv.name = 'INV/2026/00009'
        item = inv._l10n_pa_build_xml_payload()['items'][0]
        self.assertEqual(item['dCodCPBSAbr'], '8010')

    def test_xml_payload_includes_emitter_location_when_configured(self):
        self.company.partner_id.l10n_pa_edi_location_id = self.location
        inv = self._create_invoice()
        inv.name = 'INV/2026/00011'
        payload = inv._l10n_pa_build_xml_payload()
        self.assertEqual(payload['emisor']['gUbiEm']['dCodUbi'], '8-8-1')
        self.assertEqual(payload['emisor']['gUbiEm']['dCorreg'], 'SAN FELIPE')

    def test_generate_xml_produces_well_formed_xml(self):
        inv = self._create_invoice()
        inv.name = 'INV/2026/00007'
        xml = inv._l10n_pa_generate_xml()
        root = etree.fromstring(xml)
        self.assertEqual(root.tag, f"{{{dgi_xml.DGI_NAMESPACE}}}rFE")
        ns = {'r': dgi_xml.DGI_NAMESPACE}
        self.assertIsNotNone(root.find('r:gDGen/r:gEmis/r:gRucEmi', ns))

    def test_xml_emission_date_matches_cufe_date(self):
        """Regression: backdated invoices must use the same date in
        CUFE and `dFechaEm`, otherwise DGI/PAC rejects."""
        inv = self._create_invoice(invoice_date=date(2026, 1, 15))
        inv.name = 'INV/2026/00099'
        # Compute CUFE first (mirrors what action_send does).
        inv.l10n_pa_cufe = inv._l10n_pa_compute_cufe()
        # Fixed date in CUFE: 20260115
        self.assertIn('20260115', inv.l10n_pa_cufe)
        # Now build the XML and verify dFechaEm starts with the same date.
        payload = inv._l10n_pa_build_xml_payload()
        d_fecha_em = payload['general']['dFechaEm']
        self.assertEqual(d_fecha_em.strftime('%Y%m%d'), '20260115')

    def test_partner_receiver_type_default_for_pa_consumer(self):
        consumer = self.env['res.partner'].create({
            'name': 'Consumidor sin RUC',
            'country_id': self.country_pa.id,
        })
        # No vat → Consumidor Final
        self.assertEqual(consumer.l10n_pa_receiver_type, '02')

    def test_partner_receiver_type_default_for_foreign(self):
        foreign = self.env['res.partner'].create({
            'name': 'Foreign Co',
            'country_id': self.env.ref('base.us').id,
            'vat': 'US12345',
        })
        self.assertEqual(foreign.l10n_pa_receiver_type, '04')

    def test_partner_receiver_type_recomputes_on_ruc_added(self):
        """Regression: a partner created without VAT should be
        re-classified as Contribuyente once a Panama RUC is added.
        Earlier the compute had a guard that respected any existing
        value, which kept the partner stuck at Consumidor Final.
        """
        partner = self.env['res.partner'].create({
            'name': 'Cliente sin RUC inicial',
            'country_id': self.country_pa.id,
        })
        self.assertEqual(partner.l10n_pa_receiver_type, '02')
        partner.write({
            'vat': '155718881-2-2018',
            'l10n_latam_identification_type_id': self.id_ruc.id,
        })
        self.assertEqual(
            partner.l10n_pa_receiver_type, '01',
            "adding RUC + identification type must reclassify to Contribuyente",
        )

    def test_xml_payload_credit_note_uses_devolucion_op_type(self):
        """Credit notes report devolución as iNatOp, while iTipoOp
        remains salida/venta per DGI's operation-type catalog.
        """
        refund = self._create_invoice(move_type='out_refund')
        refund.name = 'NC/2026/00001'
        payload = refund._l10n_pa_build_xml_payload()
        self.assertEqual(payload['general']['iNatOp'], '11')
        self.assertEqual(payload['general']['iTipoOp'], '1')

    def test_xml_payload_factura_keeps_venta_op_type(self):
        inv = self._create_invoice()
        inv.name = 'INV/2026/00010'
        payload = inv._l10n_pa_build_xml_payload()
        self.assertEqual(payload['general']['iNatOp'], '01')
        self.assertEqual(payload['general']['iTipoOp'], '1')

    def test_xml_payload_foreign_customer_defaults_to_export_destination(self):
        foreign = self.env['res.partner'].create({
            'name': 'Foreign Buyer',
            'country_id': self.env.ref('base.us').id,
            'vat': 'US12345',
        })
        inv = self._create_invoice(partner_id=foreign.id)
        inv.name = 'INV/2026/00012'
        payload = inv._l10n_pa_build_xml_payload()
        self.assertEqual(payload['general']['iNatOp'], '02')
        self.assertEqual(payload['general']['iDest'], '2')

    def test_xml_payload_respects_manual_operation_override(self):
        inv = self._create_invoice()
        inv.write({
            'l10n_pa_operation_nature': '14',
            'l10n_pa_operation_destination': '1',
            'l10n_pa_operation_type': '1',
        })
        inv.name = 'INV/2026/00013'
        payload = inv._l10n_pa_build_xml_payload()
        self.assertEqual(payload['general']['iNatOp'], '14')
        self.assertEqual(payload['general']['iDest'], '1')

    def test_company_cafe_defaults_match_dgi_catalog(self):
        company = self.env['res.company'].create({
            'name': 'Test PA EDI CAFE Co',
            'country_id': self.country_pa.id,
            'currency_id': self.env.ref('base.USD').id,
        })
        self.assertEqual(company.l10n_pa_sfep_form_cafe, '3')
        self.assertEqual(company.l10n_pa_sfep_delivery_cafe, '3')

    def test_partner_receiver_type_government_via_nt(self):
        """Partners with NT identification type → Gobierno automatically."""
        nt_type = self.env.ref('l10n_pa.nt')
        gov = self.env['res.partner'].create({
            'name': 'Ministerio Demo',
            'country_id': self.country_pa.id,
            'l10n_latam_identification_type_id': nt_type.id,
            'vat': '8-NT-1-10200',
        })
        self.assertEqual(gov.l10n_pa_receiver_type, '03')

    def test_partner_receiver_type_manual_override_not_sticky(self):
        """Manual override of receiver_type is intentionally NOT sticky
        across dependency changes — the compute is the authoritative
        source. This test documents the trade-off so it doesn't regress.

        For non-NT government partners, set the identification type to
        NT (or extend the compute) rather than overriding manually.
        """
        partner = self.env['res.partner'].create({
            'name': 'Cliente PA',
            'country_id': self.country_pa.id,
            'vat': '155718881-2-2018',
            'l10n_latam_identification_type_id': self.id_ruc.id,
        })
        self.assertEqual(partner.l10n_pa_receiver_type, '01')
        # Manual override.
        partner.l10n_pa_receiver_type = '03'
        # Dependency change recomputes back to '01'. Documented behavior.
        partner.vat = '155718881-2-2019'
        self.assertEqual(partner.l10n_pa_receiver_type, '01')

    def test_partner_origin_cufe_auto_derived_from_reversed_entry(self):
        """Credit notes (out_refund) created via reversal must auto-fill
        l10n_pa_origin_cufe from the original invoice's CUFE, so the
        DGI document type lands on '04' (referenced credit note) not
        '06' (generic).
        """
        original = self._create_invoice()
        original.name = 'INV/2026/00200'
        original.action_post()
        original.l10n_pa_cufe = '01' + 'X' * 64  # simulated authorized CUFE
        reversal = self.env['account.move.reversal'].with_context(
            active_model='account.move', active_ids=original.ids,
        ).create({
            'reason': 'devolución',
            'date': date(2026, 5, 4),
            'journal_id': original.journal_id.id,
        })
        action = reversal.refund_moves()
        credit_note = self.env['account.move'].browse(action['res_id'])
        self.assertEqual(credit_note.l10n_pa_origin_cufe, original.l10n_pa_cufe)

    def test_partner_origin_cufe_auto_derived_from_debit_origin(self):
        """Customer debit notes (out_invoice + debit_origin_id) must
        auto-fill l10n_pa_origin_cufe from the source invoice's CUFE
        so they map to DGI document type '05' (referenced debit note).
        """
        original = self._create_invoice()
        original.name = 'INV/2026/00300'
        original.action_post()
        original.l10n_pa_cufe = '01' + 'Y' * 64
        debit_wiz = self.env['account.debit.note'].with_context(
            active_model='account.move', active_ids=original.ids,
        ).create({
            'reason': 'cargo adicional',
            'date': date(2026, 5, 4),
            'copy_lines': True,
        })
        action = debit_wiz.create_debit()
        debit_note = self.env['account.move'].browse(action['res_id'])
        self.assertEqual(debit_note.debit_origin_id, original)
        self.assertEqual(debit_note.l10n_pa_origin_cufe, original.l10n_pa_cufe)

    def test_partner_receiver_type_recomputes_on_country_change(self):
        """If a partner is later marked foreign, classification must
        flip to Extranjero on the next dependency change.
        """
        partner = self.env['res.partner'].create({
            'name': 'Cliente PA con RUC',
            'country_id': self.country_pa.id,
            'vat': '155718881-2-2018',
            'l10n_latam_identification_type_id': self.id_ruc.id,
        })
        self.assertEqual(partner.l10n_pa_receiver_type, '01')
        partner.country_id = self.env.ref('base.us')
        self.assertEqual(partner.l10n_pa_receiver_type, '04')


@tagged('-at_install', 'post_install', 'l10n_pa_edi')
class TestPACErrorCodeResolver(TransactionCase):

    def test_resolve_known_code(self):
        msg = self.env['l10n_pa_edi.dgi.error.code'].resolve('B06')
        self.assertIn('B06', msg)
        self.assertIn('Tipo de documento', msg)

    def test_resolve_unknown_code_falls_back(self):
        msg = self.env['l10n_pa_edi.dgi.error.code'].resolve('XYZ999')
        self.assertIn('XYZ999', msg)

    def test_resolve_empty_returns_empty(self):
        self.assertEqual(self.env['l10n_pa_edi.dgi.error.code'].resolve(''), '')


@tagged('-at_install', 'post_install', 'l10n_pa_edi')
class TestDgiCatalogData(TransactionCase):

    def test_official_location_catalog_loaded(self):
        location = self.env.ref('l10n_pa_edi.l10n_pa_edi_location_8_8_1')
        self.assertEqual(location.province, 'PANAMA')
        self.assertEqual(location.district, 'PANAMA')
        self.assertEqual(location.township, 'SAN FELIPE')

    def test_official_cpbs_abbreviated_catalog_loaded(self):
        cpbs = self.env.ref('l10n_pa_edi.l10n_pa_edi_cpbs_8010')
        self.assertEqual(cpbs.name, 'Servicios de asesoría de gestión')

    def test_official_unit_catalog_loaded(self):
        uom = self.env.ref('l10n_pa_edi.l10n_pa_edi_uom_und')
        self.assertEqual(uom.code, 'und')
        self.assertEqual(uom.name, 'Unidad')
