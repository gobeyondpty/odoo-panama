# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Panama - Postal Codes',
    'icon': '/account/static/description/l10n.png',
    'countries': ['pa'],
    'version': '19.0.1.0.0',
    'category': 'Hidden/Localization',
    'summary': 'Panama postal code validation and coordinate decoding',
    'description': """
Panama Postal Codes

Adds support for Panama's geospatial postal-code scheme on partner
addresses. Full postal codes are decoded locally, without calling an
external service, to expose approximate latitude, longitude, precision,
and validation status.

The postal-code algorithm is ported from the MIT-licensed
`kass507/panama-postal` project and relicensed for this Odoo module under
LGPL-3, preserving the upstream copyright notice.
""",
    'author': 'Go Beyond Inc, Community',
    'website': 'https://github.com/gobeyondpty/odoo-panama',
    'depends': [
        'l10n_pa',
    ],
    'data': [
        'views/res_partner_views.xml',
    ],
    'license': 'LGPL-3',
}
