# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Panama - Factura Fácil S.A. PAC',
    'icon': '/account/static/description/l10n.png',
    'countries': ['pa'],
    'version': '19.0.1.1.0',
    'category': 'Accounting/Localizations/EDI',
    'description': """
Panama Electronic Invoicing — Factura Fácil S.A. Provider
=========================================================

Concrete implementation of the `l10n_pa_edi.PACProvider` interface for
Factura Fácil S.A. (DGI registered PAC, RUC 155723374-2-2022,
Resolución 201-2167).

Implemented against the Factura Fácil REST API v1 documented at
`https://backend-qa-api.facturafacil.com.pa/swagger/`:

* `send_invoice(move)` — POST `/pac/reception_fe/detailed/`; obtains
  CUFE, document UUID, authorized XML, QR payload, and PDF URL.
* `get_status(cufe)`   — GET `/pac/reception_fe/find_by_cufe_or_id/`
  by CUFE or document UUID.
* `cancel_invoice(move, reason)` — POST `/pac/event/issue/` with an
  Anulación (`type='AN'`) event against the authorized CUFE.
* `validate_ruc(ruc, dv)` — local DV recomputation (no PAC endpoint).

Authentication uses three HTTP headers (`X-FF-Company`, `X-FF-Branch`,
`X-FF-API-Key`), stored per `res.company` since each contribuyente is
a separate Factura Fácil tenant. Endpoint URLs and HTTP timeout come
from `ir.config_parameter`.

The HTTP client has a 30s timeout, exponential-backoff retries on 5xx
and connection errors, and sanitized request/response logging.

Configuration UI lives at:
**Settings → Accounting → Fiscal Localization → Factura Fácil (PAC Panamá)**.
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
