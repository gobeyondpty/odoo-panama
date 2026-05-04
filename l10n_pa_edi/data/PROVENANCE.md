# Panama EDI Catalog Data Provenance

These catalog files are generated from public Dirección General de Ingresos
(DGI) technical material, not from FE_ETS or any other proprietary module.

Generated on: 2026-05-04

## Locations

File: `l10n_pa_edi.location.csv`

Source: DGI Factura Electrónica technical page, "Tabla con códigos de
ubicaciones (.xls)".

URL:
`https://dgi.mef.gob.pa/_7FacturaElectronica/source/Tabla%20con%20c%C3%B3digo%20de%20ubicaciones.xls`

The XLS columns `CODIGO_UBICACION`, `PROVINCIA`, `DISTRITO`, and
`CORREGIMIENTO` were normalized into the module fields `code`, `province`,
`district`, and `township`.

## CPBS Abbreviated Codes

File: `l10n_pa_edi.cpbs.csv`

Source: DGI "Ficha Técnica de la Factura Electrónica", version 1.10,
Table 28, "Codificación Panameña de Bienes y Servicios de Segmentos y
Familias".

URL:
`https://dgi.mef.gob.pa/_7FacturaElectronica/source/Ficha-T%C3%A9cnica-Factura-Electr%C3%B3nica-Plan%20Piloto%20Versi%C3%B3n%201.10-agosto%202019.pdf`

This file contains the two- and four-digit CPBS segment/family codes used
for the abbreviated item field. It does not contain the full eight-digit
government-purchase item catalog.

## Units Of Measure

File: `l10n_pa_edi.uom.csv`

Source: DGI "Ficha Técnica de la Factura Electrónica", version 1.10,
Table 29, "Unidades de Medida".

URL:
`https://dgi.mef.gob.pa/_7FacturaElectronica/source/Ficha-T%C3%A9cnica-Factura-Electr%C3%B3nica-Plan%20Piloto%20Versi%C3%B3n%201.10-agosto%202019.pdf`

The table columns `Nombre` and `Símbolo` were normalized into the module
fields `name` and `code`.

