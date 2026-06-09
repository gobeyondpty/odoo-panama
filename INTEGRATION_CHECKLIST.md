# Factura Fácil S.A. — Integration Checklist

The `l10n_pa_edi_factura_facil` module is implemented against the
Factura Fácil REST API v1 (October 2024 / `Documentacion API FF V1.pdf`).
See [`l10n_pa_edi_factura_facil/README.md`](l10n_pa_edi_factura_facil/README.md)
for the endpoint mapping and configuration steps.

## Status

| Operation | State |
|---|---|
| `send_invoice(move)` | Implemented — `POST /api/pac/reception_fe/detailed/`. |
| `get_status(cufe)` | Implemented — `GET /api/pac/reception_fe/find_by_cufe_or_id/`. |
| `cancel_invoice(move, reason)` | Implemented — `POST /api/pac/event/issue/` with `type='AN'`. |
| `validate_ruc(ruc, dv)` | Local DV recomputation (FF v1 has no RUC endpoint). |

## Sandbox validation (recommended before production)

1. Configure credentials in **Settings → Accounting → Fiscal
   Localization → Factura Fácil (PAC Panamá)**. Required: `X-FF-Company`,
   `X-FF-API-Key`; optional but recommended: `X-FF-Branch`.
2. Set the company to ambiente `Pruebas / Sandbox`.
3. Create a customer invoice for a Panama partner with a valid RUC and DV.
4. Click **Enviar a DGI vía PAC**.
5. Verify the move flips to `Autorizado por DGI`, the CUFE field is
   populated, the QR payload is stored, and the XML attachment is created.
6. Print the CAFÉ via the report action and confirm the QR scans to
   the CUFE.
7. Cross-check the issued document in the FF demo panel:
   [https://demo-panel.facturafacil.com.pa/](https://demo-panel.facturafacil.com.pa/).

## Out of band

- **XAdES signing**: Factura Fácil signs on the contributor's behalf
  via their PAC certificate; this module emits an unsigned JSON
  document and the PAC handles the XAdES wrapping. No contributor
  certificate needs to live in Odoo for the FF integration.
- **CUFE source**: Factura Fácil computes the CUFE from the submitted
  document. The local `l10n_pa_edi` CUFE algorithm is preserved for
  pre-flight display and for PACs that delegate CUFE generation to the
  contribuyente; for FF, prefer the CUFE returned in the response.
