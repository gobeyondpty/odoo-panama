# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Panama - Accounting',
    'icon': '/account/static/description/l10n.png',
    'countries': ['pa'],
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations/Account Charts',
    'description': """
Panama Accounting Localization

Base localization for Panama (PA): RUC/cédula/pasaporte/NT/E/PI/AV
identification types, RUC + Dígito Verificador (DV) computation per
DGI algorithm, ITBMS tax rates (7/10/15/0%), six fiscal positions
(Contribuyente, Consumo Final, Zona Libre, Exento, Gobierno,
Extranjero), and account groups in NIC/NIIF structure.

Electronic invoicing to DGI via PAC providers is implemented
separately by `l10n_pa_edi` and provider-specific modules such as
`l10n_pa_edi_factura_facil`.
""",
    'author': 'Go Beyond Inc, Community',
    'website': 'https://github.com/gobeyondpty/odoo-panama',
    'depends': [
        'account',
        'l10n_latam_base',
    ],
    'auto_install': ['account'],
    'data': [
        'data/l10n_latam.identification.type.csv',
        'data/res_bank_data.xml',
        'data/account_chart_template_data.xml',
    ],
    'demo': [
        'demo/demo_company.xml',
    ],
    'license': 'LGPL-3',
}
