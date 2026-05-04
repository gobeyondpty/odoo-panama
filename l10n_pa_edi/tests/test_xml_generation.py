# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Tests for the unsigned DGI XML builder.

Validates well-formedness, namespace, document tree structure, and
field-level correctness against the DGI Ficha Técnica field names.
DGI does not publish XSDs publicly (they ship with PAC contracts),
so structural validation is asserted with field presence and ordering
checks rather than schema validation. See TECH_DEBT.md.
"""
from datetime import datetime

from lxml import etree

from odoo.tests.common import BaseCase, tagged

from odoo.addons.l10n_pa_edi.models import dgi_xml


@tagged('-at_install', 'post_install', 'l10n_pa_edi')
class TestDgiXmlGeneration(BaseCase):

    def _base_payload(self, **overrides):
        payload = {
            'cufe': '0120155718881-2-201862000120260504000000012300101212345678901',
            'general': {
                'iAmb': '2',
                'iTpEmis': '01',
                'iDoc': '01',
                'dNroDF': '0000000001',
                'dPtoFacDF': '001',
                'dSeg': '123456789',
                'dFechaEm': datetime(2026, 5, 4, 10, 0, 0),
                'iNatOp': '01',
                'iTipoOp': '1',
                'iDest': '1',
                'iFormCafe': '1',
                'iEntCafe': '2',
                'dEnvFe': '1',
                'iProGen': '1',
                'iTipoTranVenta': '1',
                'iTipoSuc': '1',
            },
            'emisor': {
                'dRuc': '155718881-2-2018',
                'dDV': '62',
                'dTipoRuc': '2',
                'dNombEm': 'PA Demo Co.',
                'dSucEm': '0001',
                'dDirecEm': 'Avenida Balboa, Panamá',
                'dCorElecEmi': ['info@pademoco.example.com'],
                'dTfnEm': ['+507 200-0000'],
                'dCodAct': '741000',
            },
            'receptor': {
                'iTipoRec': '01',
                'dNombRec': 'Cliente S.A.',
                'cPaisRec': 'PAN',
                'dRuc': '8-442-445',
                'dDV': '08',
                'dTipoRuc': '1',
                'dDirecRec': 'Calle 50',
            },
            'items': [
                {
                    'dSecItem': 1,
                    'dDescProd': 'Servicio de consultoría',
                    'dCantCodInt': 1.0,
                    'dUnidadMedida': 'UN',
                    'dPrUnit': 100.00,
                    'dPrItem': 100.00,
                    'dValTotItem': 107.00,
                    'tasa_itbms': '01',
                    'valor_itbms': 7.00,
                },
            ],
            'totales': {
                'dTotNeto': 100.00,
                'dTotITBMS': 7.00,
                'dVTot': 107.00,
                'dTotRec': 107.00,
                'dNroItems': 1,
                'dVTotItems': 107.00,
                'forma_pago': [{'iFormaPago': '02', 'dVlrCuota': 107.00}],
            },
        }
        for k, v in overrides.items():
            payload[k] = v
        return payload

    def test_render_well_formed(self):
        xml = dgi_xml.render_rfe(self._base_payload())
        # Re-parse to confirm well-formedness.
        root = etree.fromstring(xml)
        self.assertEqual(root.tag, f"{{{dgi_xml.DGI_NAMESPACE}}}rFE")

    def test_xml_declaration_and_namespace(self):
        xml = dgi_xml.render_rfe(self._base_payload())
        self.assertTrue(xml.startswith(b"<?xml"))
        self.assertIn(dgi_xml.DGI_NAMESPACE.encode(), xml)

    def test_root_has_required_top_level_children(self):
        root = etree.fromstring(dgi_xml.render_rfe(self._base_payload()))
        ns = {'r': dgi_xml.DGI_NAMESPACE}
        self.assertIsNotNone(root.find('r:dVerForm', ns))
        self.assertIsNotNone(root.find('r:dId', ns))
        self.assertIsNotNone(root.find('r:gDGen', ns))
        self.assertIsNotNone(root.find('r:gItem', ns))
        self.assertIsNotNone(root.find('r:gTot', ns))

    def test_dgen_includes_emisor(self):
        root = etree.fromstring(dgi_xml.render_rfe(self._base_payload()))
        ns = {'r': dgi_xml.DGI_NAMESPACE}
        emisor = root.find('r:gDGen/r:gEmis', ns)
        self.assertIsNotNone(emisor)
        ruc = emisor.find('r:gRucEmi', ns)
        self.assertIsNotNone(ruc)
        self.assertEqual(ruc.findtext('r:dRuc', namespaces=ns), '155718881-2-2018')
        self.assertEqual(ruc.findtext('r:dDV', namespaces=ns), '62')

    def test_dgen_includes_receptor_for_contribuyente(self):
        root = etree.fromstring(dgi_xml.render_rfe(self._base_payload()))
        ns = {'r': dgi_xml.DGI_NAMESPACE}
        receptor = root.find('r:gDGen/r:gDatRec', ns)
        self.assertIsNotNone(receptor)
        self.assertEqual(receptor.findtext('r:iTipoRec', namespaces=ns), '01')
        self.assertEqual(receptor.findtext('r:dNombRec', namespaces=ns), 'Cliente S.A.')

    def test_consumo_final_skips_receptor_block(self):
        payload = self._base_payload()
        payload['receptor'] = {
            'iTipoRec': '02',
            'dNombRec': 'Consumidor Final',
        }
        root = etree.fromstring(dgi_xml.render_rfe(payload))
        ns = {'r': dgi_xml.DGI_NAMESPACE}
        # iTipoRec=02 omits the gDatRec block entirely (Ficha Técnica B401).
        self.assertIsNone(root.find('r:gDGen/r:gDatRec', ns))

    def test_item_block_quantities_and_money_format(self):
        root = etree.fromstring(dgi_xml.render_rfe(self._base_payload()))
        ns = {'r': dgi_xml.DGI_NAMESPACE}
        item = root.find('r:gItem', ns)
        self.assertEqual(item.findtext('r:dCantCodInt', namespaces=ns), '1.0000')
        precios = item.find('r:gPrecios', ns)
        self.assertEqual(precios.findtext('r:dPrUnit', namespaces=ns), '100.00')
        self.assertEqual(precios.findtext('r:dPrItem', namespaces=ns), '100.00')
        self.assertEqual(precios.findtext('r:dValTotItem', namespaces=ns), '107.00')
        itbms = item.find('r:gITBMSItem', ns)
        self.assertEqual(itbms.findtext('r:dTasaITBMS', namespaces=ns), '01')
        self.assertEqual(itbms.findtext('r:dValITBMS', namespaces=ns), '7.00')

    def test_totales_block(self):
        root = etree.fromstring(dgi_xml.render_rfe(self._base_payload()))
        ns = {'r': dgi_xml.DGI_NAMESPACE}
        tot = root.find('r:gTot', ns)
        self.assertEqual(tot.findtext('r:dTotNeto', namespaces=ns), '100.00')
        self.assertEqual(tot.findtext('r:dTotITBMS', namespaces=ns), '7.00')
        self.assertEqual(tot.findtext('r:dVTot', namespaces=ns), '107.00')
        self.assertEqual(tot.findtext('r:dNroItems', namespaces=ns), '1')

    def test_origin_cufe_appears_for_credit_notes(self):
        payload = self._base_payload()
        payload['general']['iDoc'] = '04'
        payload['general']['origin_cufe'] = 'origin-cufe-xyz'
        root = etree.fromstring(dgi_xml.render_rfe(payload))
        ns = {'r': dgi_xml.DGI_NAMESPACE}
        self.assertEqual(
            root.findtext('r:gDGen/r:dCufeFEReferencia', namespaces=ns),
            'origin-cufe-xyz',
        )

    def test_itbms_rate_to_code(self):
        self.assertEqual(dgi_xml.itbms_rate_to_code(0.0), '00')
        self.assertEqual(dgi_xml.itbms_rate_to_code(7.0), '01')
        self.assertEqual(dgi_xml.itbms_rate_to_code(10.0), '02')
        self.assertEqual(dgi_xml.itbms_rate_to_code(15.0), '03')
        with self.assertRaises(ValueError):
            dgi_xml.itbms_rate_to_code(5.0)

    def test_no_empty_optional_fields_emitted(self):
        """Optional fields (e.g. dCoordEm) should be omitted when value is None/empty."""
        payload = self._base_payload()
        payload['emisor'].pop('dCoordEm', None)
        xml = dgi_xml.render_rfe(payload)
        self.assertNotIn(b'<dCoordEm', xml)

    def test_multiple_items_serialize(self):
        payload = self._base_payload()
        payload['items'].append({
            'dSecItem': 2,
            'dDescProd': 'Otro servicio',
            'dCantCodInt': 2.0,
            'dPrUnit': 50.00,
            'dPrItem': 100.00,
            'dValTotItem': 100.00,
            'tasa_itbms': '00',
            'valor_itbms': 0.00,
        })
        root = etree.fromstring(dgi_xml.render_rfe(payload))
        ns = {'r': dgi_xml.DGI_NAMESPACE}
        items = root.findall('r:gItem', ns)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[1].findtext('r:dSecItem', namespaces=ns), '2')
