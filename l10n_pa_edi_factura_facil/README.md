# Panama — Factura Fácil S.A. PAC (`l10n_pa_edi_factura_facil`)

Concrete implementation of the
[`l10n_pa_edi`](../l10n_pa_edi/) abstract PAC interface for
**Factura Fácil S.A.** (DGI registered PAC, RUC `155723374-2-2022`,
Resolución 201-2167).

Implemented against the Factura Fácil REST API v1 documented at
[`https://backend-qa-api.facturafacil.com.pa/swagger/`](https://backend-qa-api.facturafacil.com.pa/swagger/)
(also `Documentacion API FF V1.pdf`, October 2024).

## Status

Functional. All four `PACProvider` operations have been wired against
the real endpoints. The integration was implemented from the
documented v1 schema; live QA validation against an issued API key is
still recommended before flipping any company to `Producción`.

## Dependencies

- [`l10n_pa_edi`](../l10n_pa_edi/) (which pulls
  [`l10n_pa`](../l10n_pa/))
- Python: `requests`

## Configuration

### Per-company credentials (`res.company`)

Each Panama company is a separate Factura Fácil tenant, so credentials
live on the company record:

| Field | Header | Notes |
|---|---|---|
| `l10n_pa_factura_facil_company_uuid` | `X-FF-Company` | Required. UUID issued by Factura Fácil. |
| `l10n_pa_factura_facil_branch_uuid` | `X-FF-Branch` | Optional if the API key is scoped to a single branch. |
| `l10n_pa_factura_facil_api_key` | `X-FF-API-Key` | Required. Password-masked, redacted in logs. |

### Instance-wide settings (`ir.config_parameter`)

| Key | Default | Notes |
|---|---|---|
| `l10n_pa_edi.factura_facil.base_url` | `https://backend-qa-api.facturafacil.com.pa` | QA backend |
| `l10n_pa_edi.factura_facil.base_url_prod` | `https://backend-api.facturafacil.com.pa` | Production backend |
| `l10n_pa_edi.factura_facil.timeout` | `30` | HTTP timeout (seconds) |

The Settings UI lives under
**Settings → Accounting → Fiscal Localization → Factura Fácil (PAC Panamá)**
and exposes all six fields.

Then in **Settings → Companies → _your company_ → Factura Electrónica
Panamá**, set **PAC = `Factura Fácil S.A.`** and pick **Ambiente =
`Pruebas / Sandbox`** until your prod credentials are validated.

## Endpoint mapping

Paths come from the live Swagger at
`https://backend-qa-api.facturafacil.com.pa/swagger/?format=openapi`.
The v1 PDF (October 2024) drops the `/api/` segment and points to the
wrong CSV endpoint; this module follows the live spec, not the PDF.

| `PACProvider` method | Factura Fácil endpoint | Notes |
|---|---|---|
| `send_invoice(move)` | `POST /api/pac/reception_fe/detailed/` | Body = `{header, document}` (`Document`). Returns `DocumentResult`: `cufe`, `document_uuid`, `xml`, `qr_code_data`, `pdf_url`, `messages[]`, `rejected`. |
| `get_status(cufe)` | `GET /api/pac/reception_fe/find_by_cufe_or_id/?cufe_or_id=<cufe>` | Returns `DocumentStatus`: `{id, cufe, status, status_display, …}`. `status` enum mapped to `pending`/`authorized`/`rejected`/`cancelled`. `404` → `unknown`. |
| `cancel_invoice(move, reason)` | `POST /api/pac/event/issue/` | Body = `{type: 'AN', cufe, reason}` (`EventoPACIssue`). `type='AN'` = Anulación, `'MF'` = Modificación. |
| `validate_ruc(ruc, dv)` | (not exposed) | Falls back to local DV recomputation via `l10n_pa.calculate_dv`. |

## Request schema (POST /pac/reception_fe/detailed/)

```jsonc
{
  "header": {
    "id": "<move.id>",
    "environment": "1" | "2"        // 1=Producción, 2=Pruebas
  },
  "document": {
    "fd_number": <int>,             // Numeric portion of move.name
    "type": "01" | "04" | "05" | "06" | "07" | "08",
    "receptor": { type, name, ruc_type, address, email, ruc, dv,
                  location, country },
    "items": [{ line, price, quantity, description, taxes[], discount,
                internal_code, mu, gns }],
    "payments": [{ type, amount, description }],
    "total": "<amount_total>",
    "info": "<narration>",
    "referred": { fd_number, fd_date },  // for credit/debit notes
    "dest_country": "..."                // when partner is foreign
  }
}
```

## Operational behavior

- **Timeout**: 30s per request (configurable).
- **Retries**: 3 attempts with exponential backoff (1s, 2s, 4s) on
  `5xx` responses and connection errors. No retry on `4xx`.
- **Auth failures** (`401`/`403`) raise `PACAuthError` immediately
  (wrapped into `PACResponse(success=False, …)` by `send_invoice`).
- **Logging**: requests/responses are logged at `DEBUG` with API keys
  and `Bearer` tokens replaced by `***REDACTED***`.
- **Rejection persistence**: when DGI/PAC rejects a document, the move
  flips to `Rechazado` and the raw response, error codes, and
  human-readable message are stored on the move.

## Testing

```bash
odoo-bin -d test_ff -i l10n_pa_edi_factura_facil \
    --test-enable --test-tags=/l10n_pa_edi_factura_facil \
    --stop-after-init
```

The suite covers credential sanitization, provider registration,
request payload conformance to the FF v1 schema (basic invoice,
consumidor final, credit-note-with-referred), response parsing
(success / DGI rejection / parse failure), auth failure, 5xx retry,
the `find_by_cufe_or_id` status lookup, the Anulación event flow of
`cancel_invoice`, and local DV validation. All HTTP is mocked at
`requests.request`.

## License

LGPL-3.
