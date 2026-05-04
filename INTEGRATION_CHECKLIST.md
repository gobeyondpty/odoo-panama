# Factura Fácil S.A. — Integration Checklist

Filling in these `TODO[INTEGRATION]` markers is the only remaining
work to take `l10n_pa_edi_factura_facil` from a tested skeleton to a
production-ready PAC client.

All items live in
[`l10n_pa_edi_factura_facil/pac_providers/factura_facil.py`](l10n_pa_edi_factura_facil/pac_providers/factura_facil.py).

## Prerequisites

- [ ] Sign Factura Fácil contract for the **Corporativo** plan
      (the only plan that exposes the API + Swagger).
- [ ] Obtain QA credentials (bearer API key for
      `https://backend-qa-api.facturafacil.com.pa`).
- [ ] Pull the authoritative Swagger from
      `https://backend-qa-api.facturafacil.com.pa/swagger/`
      and save as `docs/factura_facil_openapi.yaml` (NOT committed if
      it contains internal endpoints).

## Mapping to the OpenAPI spec

| File:Line | Method | What's stubbed | What to verify |
|---|---|---|---|
| `factura_facil.py` `_build_send_payload` | `send_invoice` | Request body shape | Confirm field names (`ruc_emisor`, `cufe_local`, `xml_dgi_base64`) match Swagger; some PACs accept the XML as multipart/form-data. |
| `factura_facil.py` `_parse_send_response` | `send_invoice` | Response field names | Verify keys: `success`/`cufe`/`xml_autorizado`/`qr`/`errores`/`estado`. Adjust `_parse_send_response` accordingly. |
| `factura_facil.py` `send_invoice` | `send_invoice` | Endpoint path | `'/api/v1/documents'` is a placeholder. Replace with the actual path. |
| `factura_facil.py` `get_status` | `get_status` | Endpoint path + state mapping | `'/api/v1/documents/{cufe}/status'` is a placeholder. Update `state_map` if Factura Fácil uses different state codes. |
| `factura_facil.py` `cancel_invoice` | `cancel_invoice` | Endpoint path + payload shape | `'/api/v1/documents/{cufe}/cancel'` is a placeholder. The DGI Anulación schema (`feRecepEventoFEDGI_v1.00`) may need to be sent; build it via `dgi_xml` if so. |
| `factura_facil.py` `validate_ruc` | `validate_ruc` | Endpoint path + payload | `'/api/v1/ruc/validate'` is a placeholder. Either replace with the Factura Fácil endpoint or fall back to DGI's PADRON. |

## Testing the integration

1. Configure credentials in **Settings → Accounting → Factura Fácil
   (PAC Panamá)**.
2. Set company to environment `Pruebas / Sandbox`.
3. Create a customer invoice for a Panama partner with a valid RUC.
4. Click **Enviar a DGI vía PAC**.
5. Verify the move flips to `Autorizado por DGI`, the CUFE field is
   populated, and the XML attachment is created.
6. Print the CAFÉ via the report action and confirm the QR scans to
   the CUFE.

## Out of band

- **XAdES signing**: confirm whether Factura Fácil signs on the
  contributor's behalf (delegated certificate) or expects a
  contributor-signed XML. If the latter, see `TECH_DEBT.md` for the
  follow-up signing module.
