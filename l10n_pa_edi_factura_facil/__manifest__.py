# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Panama - Factura Fácil S.A. PAC',
    'icon': '/account/static/description/l10n.png',
    'countries': ['pa'],
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations/EDI',
    'description': """
Panama Electronic Invoicing — Factura Fácil S.A. Provider
=========================================================

Concrete implementation of the `l10n_pa_edi.PACProvider` interface for
Factura Fácil S.A. (DGI registered PAC, RUC 155723374-2-2022,
Resolución 201-2167).

Implements the four PAC operations:

* `send_invoice(move)` — submit a DGI XML and obtain a CUFE
* `get_status(cufe)`   — query authorization status
* `cancel_invoice(move, reason)` — register an Anulación event
* `validate_ruc(ruc, dv)` — RUC + DV validation through the PAC

HTTP integration is implemented using `requests` with a 30s timeout,
exponential-backoff retries on 5xx and connection errors, and
sanitized request/response logging.

Stub methods that depend on Factura Fácil's full OpenAPI schema raise
`NotImplementedError` with a TODO and are documented in
`INTEGRATION_CHECKLIST.md` at the repo root. Filling these in is the
sole remaining task once sandbox credentials are available.

Configuration UI lives at:
**Settings → Accounting → Panama Electronic Invoicing → Factura Fácil**.
""",
    'author': 'Go Beyond Inc, Community',
    'website': 'https://github.com/gobeyondpty/odoo-panama',
    'depends': [
        'l10n_pa_edi',
    ],
    'data': [
        'data/pac_provider_data.xml',
        'views/res_config_settings_views.xml',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'license': 'LGPL-3',
}
