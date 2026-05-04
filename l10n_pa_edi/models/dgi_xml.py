# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Generate DGI Factura Electrónica XML from an `account.move`.

The XML structure follows DGI Ficha Técnica PAC v1.00 (April 2025) and
the field naming used by `Electronic-Signatures-Industries/dgi-fe`
(`src/fe/`). Reproduces the document tree:

    <rFE xmlns="http://dgi-fep.mef.gob.pa">
      <dVerForm>1.00</dVerForm>
      <dId>{CUFE}</dId>
      <gDGen>          <!-- B-block: general -->
        ...
      </gDGen>
      <gItem>          <!-- E-block: line items, repeated -->
        ...
      </gItem>
      <gTot>           <!-- F-block: totals -->
        ...
      </gTot>
    </rFE>

This module is provider-agnostic and emits an unsigned document. The
PAC layer wraps it in their submission envelope and adds the XAdES
signature.
"""
from __future__ import annotations

import logging
from datetime import datetime, date

from lxml import etree

_logger = logging.getLogger(__name__)

DGI_NAMESPACE = 'http://dgi-fep.mef.gob.pa'
DGI_VERSION = '1.00'

# DGI tipo-documento codes (Ficha Técnica B06). Subset relevant for
# operator workflows; expand as additional document types are needed.
DGI_DOC_FACTURA = '01'
DGI_DOC_IMPORTACION = '02'
DGI_DOC_EXPORTACION = '03'
DGI_DOC_NOTA_CREDITO_REF = '04'
DGI_DOC_NOTA_DEBITO_REF = '05'
DGI_DOC_NOTA_CREDITO_GENERICA = '06'
DGI_DOC_NOTA_DEBITO_GENERICA = '07'
DGI_DOC_REEMBOLSO = '08'
DGI_DOC_FACTURA_ZONA_FRANCA = '09'

# DGI ITBMS rate codes (Item.TasaITBMS).
DGI_TASA_ITBMS_EXENTO = '00'
DGI_TASA_ITBMS_07 = '01'
DGI_TASA_ITBMS_10 = '02'
DGI_TASA_ITBMS_15 = '03'

DGI_AMBIENTE_PROD = '1'
DGI_AMBIENTE_TEST = '2'

DGI_TIPO_RUC_NATURAL = '1'
DGI_TIPO_RUC_JURIDICO = '2'

# Map a tax rate (float) to the ITBMS DGI code.
def itbms_rate_to_code(rate: float) -> str:
    if rate == 0.0:
        return DGI_TASA_ITBMS_EXENTO
    if rate == 7.0:
        return DGI_TASA_ITBMS_07
    if rate == 10.0:
        return DGI_TASA_ITBMS_10
    if rate == 15.0:
        return DGI_TASA_ITBMS_15
    raise ValueError(f"No DGI ITBMS code for rate {rate!r}")


# ---------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------


def _el(parent, tag: str, text=None, **attrib):
    """Create a sub-element. Skip if `text` is None or empty string."""
    if text is None or text == '':
        if attrib:
            return etree.SubElement(parent, tag, **attrib)
        return None
    el = etree.SubElement(parent, tag, **attrib)
    if isinstance(text, (date, datetime)):
        el.text = text.strftime('%Y-%m-%dT%H:%M:%S-05:00')  # Panama is UTC-5
    elif isinstance(text, float):
        el.text = f"{text:.2f}"
    else:
        el.text = str(text)
    return el


def _fmt_qty(qty: float) -> str:
    """Quantities to 4 decimals per DGI standard."""
    return f"{qty:.4f}"


def _fmt_money(amount: float) -> str:
    """Monetary values to 2 decimals per DGI standard."""
    return f"{amount:.2f}"


# ---------------------------------------------------------------------
# Top-level builder
# ---------------------------------------------------------------------


def build_rfe(payload: dict) -> etree._Element:
    """Build the full <rFE> tree from a normalized payload dict.

    `payload` shape (mandatory keys marked *):

        {
            'cufe': str,                   # *  CUFE id (also goes in dId)
            'general': {                   # *  B-block
                'dFechaEm': datetime,      # *
                'dPtoFacDF': str,          # *
                'dNroDF': str,             # *
                'dSeg': str,               # *  9-digit security code
                'iAmb': '1'|'2',           # *
                'iDoc': str,               # *  '01' factura, …
                'iTpEmis': '01'..'04',     # *
                'iTipoOp': '1'|'2',        # *  1=venta 2=devolucion
                'iDest': '1'|'2',          # *  1=Panama 2=Exterior
                'iNatOp': '01'|'02'…,      # *
                'iProGen': '1'..'5',
                'iFormCafe': '1'|'2'|'3',
                'iEntCafe': '1'|'2'|'3',
                'iTipoTranVenta': '1'..'4',
                'iTipoSuc': '1'|'2',
                'dEnvFe': '1'|'2',
                'dIntEmFe': str,
                'origin_cufe': str,        #   for NC/ND, links to original
            },
            'emisor': {                    # *  Emitter
                'dRuc': str, 'dDV': str, 'dTipoRuc': '1'|'2',
                'dNombEm': str, 'dSucEm': str,
                'dCoordEm': str, 'dDirecEm': str,
                'dCorElecEmi': [str], 'dTfnEm': [str],
                'dCodAct': str,            #   business activity code
                'gUbiEm': {'dCodUbi': str, 'dCorreg': str, 'dDistr': str, 'dProv': str},
            },
            'receptor': {                  #    Receiver
                'iTipoRec': '01'|'02'|'03'|'04',
                'dNombRec': str,
                'dRuc': str, 'dDV': str, 'dTipoRuc': '1'|'2',
                'cPaisRec': 'PAN' or other ISO-3166 alpha-3,
                'dDirecRec': str, 'dCorElecRec': [str], 'dTfnRec': [str],
                'gIdExtType': {'dIdExt': str, 'dPaisExt': str},
            },
            'items': [                     # *  ≥1 line item
                {
                    'dSecItem': int,          # *  sequence
                    'dDescProd': str,         # *  product description
                    'dCodCPBSAbr': str,       #    sub-product category
                    'dCantCodInt': float,     # *  quantity
                    'dUnidadMedida': str,
                    'dPrUnit': float,         # *  unit price
                    'dPrItem': float,         # *  line total before tax
                    'dValTotItem': float,     # *  line total
                    'tasa_itbms': '00'|'01'|'02'|'03',  # *
                    'valor_itbms': float,     # *
                },
                ...
            ],
            'totales': {                   # *  F-block
                'dTotNeto': float,            # *  subtotal w/o ITBMS
                'dTotITBMS': float,           # *
                'dVTot': float,               # *  grand total
                'dTotRec': float,             # *  amount due from receiver
                'dNroItems': int,             # *
                'dVTotItems': float,          # *
                'forma_pago': [
                    {'iFormaPago': '02', 'dVlrCuota': 100.00, 'dFormaPagoDesc': str?},
                ],
                'dTotDesc': float?,            #   total discounts
                'dTotISC': float?,             #   total ISC
                'dTotOTI': float?,             #   total other taxes
            },
        }

    Returns the lxml `<rFE>` Element.
    """
    nsmap = {None: DGI_NAMESPACE}
    rfe = etree.Element('rFE', nsmap=nsmap)

    _el(rfe, 'dVerForm', DGI_VERSION)
    _el(rfe, 'dId', payload['cufe'])

    _build_dgen(rfe, payload['general'], payload['emisor'], payload.get('receptor'))
    for item in payload['items']:
        _build_item(rfe, item)
    _build_totales(rfe, payload['totales'])

    return rfe


def render_rfe(payload: dict, *, pretty: bool = False) -> bytes:
    """Build and serialize the <rFE> document to UTF-8 bytes."""
    rfe = build_rfe(payload)
    return etree.tostring(rfe, encoding='utf-8', xml_declaration=True, pretty_print=pretty)


# ---------------------------------------------------------------------
# Block builders
# ---------------------------------------------------------------------


def _build_dgen(parent, gen: dict, emisor: dict, receptor: dict | None):
    g = etree.SubElement(parent, 'gDGen')
    # Sequence per the DGI spec (B-block ordering matters for canonical XML).
    _el(g, 'iAmb', gen['iAmb'])
    _el(g, 'iTpEmis', gen.get('iTpEmis', '01'))
    if gen.get('dFechaCont'):
        _el(g, 'dFechaCont', gen['dFechaCont'])
    if gen.get('dMotCont'):
        _el(g, 'dMotCont', gen['dMotCont'])
    _el(g, 'iDoc', gen['iDoc'])
    _el(g, 'dNroDF', gen['dNroDF'])
    _el(g, 'dPtoFacDF', gen['dPtoFacDF'])
    _el(g, 'dSeg', gen['dSeg'])
    _el(g, 'dFechaEm', gen['dFechaEm'])
    if gen.get('dFechaSalida'):
        _el(g, 'dFechaSalida', gen['dFechaSalida'])
    _el(g, 'iNatOp', gen.get('iNatOp', '01'))
    _el(g, 'iTipoOp', gen.get('iTipoOp', '1'))
    _el(g, 'iDest', gen.get('iDest', '1'))
    _el(g, 'iFormCafe', gen.get('iFormCafe', '1'))
    _el(g, 'iEntCafe', gen.get('iEntCafe', '1'))
    _el(g, 'dEnvFe', gen.get('dEnvFe', '1'))
    _el(g, 'iProGen', gen.get('iProGen', '1'))
    _el(g, 'iTipoTranVenta', gen.get('iTipoTranVenta', '1'))
    _el(g, 'iTipoSuc', gen.get('iTipoSuc', '1'))
    if gen.get('dIntEmFe'):
        _el(g, 'dIntEmFe', gen['dIntEmFe'])
    if gen.get('origin_cufe'):
        _el(g, 'dCufeFEReferencia', gen['origin_cufe'])
    _build_emisor(g, emisor)
    if receptor and receptor.get('iTipoRec') != '02':
        # Consumo Final (02) often skips the receptor block; otherwise emit it.
        _build_receptor(g, receptor)


def _build_emisor(parent, e: dict):
    g = etree.SubElement(parent, 'gEmis')
    ruc = etree.SubElement(g, 'gRucEmi')
    _el(ruc, 'dTipoRuc', e['dTipoRuc'])
    _el(ruc, 'dRuc', e['dRuc'])
    _el(ruc, 'dDV', e['dDV'])
    _el(g, 'dNombEm', e['dNombEm'])
    _el(g, 'dSucEm', e.get('dSucEm', '0001'))
    if e.get('dCoordEm'):
        _el(g, 'dCoordEm', e['dCoordEm'])
    if e.get('dDirecEm'):
        _el(g, 'dDirecEm', e['dDirecEm'])
    if e.get('gUbiEm'):
        u = etree.SubElement(g, 'gUbiEm')
        _el(u, 'dCodUbi', e['gUbiEm'].get('dCodUbi', ''))
        _el(u, 'dCorreg', e['gUbiEm'].get('dCorreg', ''))
        _el(u, 'dDistr', e['gUbiEm'].get('dDistr', ''))
        _el(u, 'dProv', e['gUbiEm'].get('dProv', ''))
    for tel in e.get('dTfnEm') or []:
        _el(g, 'dTfnEm', tel)
    for mail in e.get('dCorElecEmi') or []:
        _el(g, 'dCorElecEmi', mail)
    if e.get('dCodAct'):
        _el(g, 'dCodAct', e['dCodAct'])


def _build_receptor(parent, r: dict):
    g = etree.SubElement(parent, 'gDatRec')
    _el(g, 'iTipoRec', r['iTipoRec'])
    _el(g, 'cPaisRec', r.get('cPaisRec', 'PAN'))
    if r.get('cPaisRecDesc'):
        _el(g, 'cPaisRecDesc', r['cPaisRecDesc'])
    _el(g, 'dNombRec', r['dNombRec'])
    if r.get('dRuc'):
        ruc = etree.SubElement(g, 'gRucRec')
        _el(ruc, 'dTipoRuc', r['dTipoRuc'])
        _el(ruc, 'dRuc', r['dRuc'])
        _el(ruc, 'dDV', r['dDV'])
    elif r.get('gIdExtType'):
        ext = etree.SubElement(g, 'gIdExtType')
        _el(ext, 'dIdExt', r['gIdExtType']['dIdExt'])
        _el(ext, 'dPaisExt', r['gIdExtType'].get('dPaisExt', ''))
    if r.get('dDirecRec'):
        _el(g, 'dDirecRec', r['dDirecRec'])
    for tel in r.get('dTfnRec') or []:
        _el(g, 'dTfnRec', tel)
    for mail in r.get('dCorElecRec') or []:
        _el(g, 'dCorElecRec', mail)


def _build_item(parent, it: dict):
    g = etree.SubElement(parent, 'gItem')
    _el(g, 'dSecItem', it.get('dSecItem', 1))
    _el(g, 'dDescProd', it['dDescProd'])
    if it.get('dCodCPBSAbr'):
        _el(g, 'dCodCPBSAbr', it['dCodCPBSAbr'])
    _el(g, 'dCantCodInt', _fmt_qty(it['dCantCodInt']))
    if it.get('dUnidadMedida'):
        _el(g, 'dUnidadMedida', it['dUnidadMedida'])
    # Precio block
    p = etree.SubElement(g, 'gPrecios')
    _el(p, 'dPrUnit', _fmt_money(it['dPrUnit']))
    if it.get('dPrUnitDesc'):
        _el(p, 'dPrUnitDesc', _fmt_money(it['dPrUnitDesc']))
    _el(p, 'dPrItem', _fmt_money(it['dPrItem']))
    _el(p, 'dValTotItem', _fmt_money(it['dValTotItem']))
    # ITBMS
    if 'tasa_itbms' in it:
        t = etree.SubElement(g, 'gITBMSItem')
        _el(t, 'dTasaITBMS', it['tasa_itbms'])
        _el(t, 'dValITBMS', _fmt_money(it['valor_itbms']))


def _build_totales(parent, tot: dict):
    g = etree.SubElement(parent, 'gTot')
    _el(g, 'dTotNeto', _fmt_money(tot['dTotNeto']))
    _el(g, 'dTotITBMS', _fmt_money(tot['dTotITBMS']))
    if tot.get('dTotISC'):
        _el(g, 'dTotISC', _fmt_money(tot['dTotISC']))
    if tot.get('dTotOTI'):
        _el(g, 'dTotOTI', _fmt_money(tot['dTotOTI']))
    _el(g, 'dVTot', _fmt_money(tot['dVTot']))
    _el(g, 'dTotRec', _fmt_money(tot['dTotRec']))
    if tot.get('dTotDesc'):
        _el(g, 'dTotDesc', _fmt_money(tot['dTotDesc']))
    _el(g, 'dNroItems', tot['dNroItems'])
    _el(g, 'dVTotItems', _fmt_money(tot['dVTotItems']))
    for fp in tot.get('forma_pago') or []:
        f = etree.SubElement(g, 'gFormaPago')
        _el(f, 'iFormaPago', fp['iFormaPago'])
        _el(f, 'dVlrCuota', _fmt_money(fp['dVlrCuota']))
        if fp.get('dFormaPagoDesc'):
            _el(f, 'dFormaPagoDesc', fp['dFormaPagoDesc'])
