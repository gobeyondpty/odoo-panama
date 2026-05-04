# Panama — Factura Fácil S.A. PAC (`l10n_pa_edi_factura_facil`)

Concrete implementation of the
[`l10n_pa_edi`](../l10n_pa_edi/) abstract PAC interface for
**Factura Fácil S.A.** (DGI registered PAC, RUC `155723374-2-2022`,
Resolución 201-2167).

## Status

**Skeleton with `TODO[INTEGRATION]` markers.** All four PAC operations
have working HTTP plumbing (timeout, retry, sanitized logging) and
educated-guess request/response mappings, but the exact endpoint paths
and DTO field names need to be confirmed against Factura Fácil's
authenticated Swagger before production use.

See [`../INTEGRATION_CHECKLIST.md`](../INTEGRATION_CHECKLIST.md) for
the punch list.

## Dependencies

- [`l10n_pa_edi`](../l10n_pa_edi/) (which pulls
  [`l10n_pa`](../l10n_pa/))
- Python: `requests`

## Configuration

**Settings → Accounting → Fiscal Localization → Factura Fácil (PAC Panamá)**:

| Field | Default | Notes |
|---|---|---|
| URL Base (QA) | `https://backend-qa-api.facturafacil.com.pa` | Override only on vendor instruction |
| URL Base (Producción) | `https://backend-api.facturafacil.com.pa` | Override only on vendor instruction |
| API Key | _(blank)_ | Bearer token from Factura Fácil; password-masked, redacted in logs |
| Timeout HTTP | `30` | Seconds; HTTP timeout per request |

Then in **Settings → Companies → <your company> → Factura Electrónica
Panamá**, set **PAC = `Factura Fácil S.A.`** and choose the
ambiente (`Pruebas / Sandbox` until your prod credentials are
validated).

## Operational Behavior

- **Timeout**: 30s per request (configurable).
- **Retries**: 3 attempts with exponential backoff (1s, 2s, 4s) on
  `5xx` responses and connection errors. No retry on `4xx`.
- **Auth failures** (401/403) raise `PACAuthError` immediately.
- **Logging**: requests/responses are logged at `DEBUG` with API keys
  and `Authorization: Bearer …` tokens replaced by `***REDACTED***`.
- **Rejection persistence**: when DGI/PAC rejects a document, the move
  flips to `Rechazado` and the raw response, error codes, and
  human-readable message are stored on the move (regression covered by
  `test_wizard_send_persists_rejection_status`).

## Integration Steps

1. Sign Factura Fácil **Corporativo** plan; obtain QA credentials.
2. Pull the authoritative Swagger from
   `https://backend-qa-api.facturafacil.com.pa/swagger/`.
3. Walk the `TODO[INTEGRATION]` markers in
   [`pac_providers/factura_facil.py`](pac_providers/factura_facil.py)
   and replace endpoint paths + DTO field names per the Swagger.
4. Configure the Settings UI with the QA API key.
5. Test against a sandbox invoice. Move should flip to `Autorizada`
   and the CAFÉ PDF should render with a scannable QR code.
6. Switch the company to **Producción** ambiente once validated.

## Testing

```bash
odoo-bin -d test_ff -i l10n_pa_edi_factura_facil \
    --test-enable --test-tags=/l10n_pa_edi_factura_facil \
    --stop-after-init
```

18 tests cover:

- credential sanitization (api_key, Bearer header)
- provider registration (selection + class registry)
- HTTP success / 4xx rejection / 401 auth / 5xx-with-retry
- status query (authorized + rejected)
- cancel and validate_ruc happy paths
- request payload structure including the embedded unsigned XML

All HTTP is mocked at the `requests.request` level; the test suite
never touches the network.

## License

LGPL-3.
