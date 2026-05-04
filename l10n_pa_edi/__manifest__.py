# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Panama - Electronic Invoicing (PAC-agnostic)',
    'icon': '/account/static/description/l10n.png',
    'countries': ['pa'],
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations/EDI',
    'description': """
Panama Electronic Invoicing — PAC-agnostic Layer
================================================

Implements DGI Resolución 201-6299 electronic invoicing for Panama.

This module is PAC-agnostic. It provides:

* Abstract `PACProvider` interface (`l10n_pa_edi.pac_provider.abstract`)
* DGI-compliant XML generator per Ficha Técnica
* CUFE (Código Único de Factura Electrónica) generator
* CAFÉ (Constancia de Autorización de Factura Electrónica) PDF report
  with QR code
* Credit Note (Nota de Crédito) and Debit Note (Nota de Débito) flows
  carrying the original CUFE reference
* Cancellation / Anulación event registration
* Hooks into Odoo 19's `account_move_send` framework as a delivery
  method ("Enviar a DGI vía PAC")
* Spanish-localized DGI error code mapping
* Contingency mode (`l10n_pa_contingency`) flag on invoices

Concrete PAC providers (Factura Fácil, HKA, eFacturaPTY, etc.) ship in
their own modules and register themselves as a Selection value on
`res.company.l10n_pa_pac_provider`.
""",
    'author': 'Go Beyond Inc, Community',
    'website': 'https://github.com/gobeyondpty/odoo-panama',
    'depends': [
        'l10n_pa',
        'account',
        'account_debit_note',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/dgi_document_type_data.xml',
        'data/dgi_error_code_data.xml',
        'views/account_move_views.xml',
        'views/res_company_views.xml',
        'views/res_partner_views.xml',
        'report/cafe_report.xml',
        'report/cafe_report_template.xml',
    ],
    'external_dependencies': {
        'python': ['lxml', 'qrcode'],
    },
    'license': 'LGPL-3',
}
