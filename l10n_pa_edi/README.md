# Panama — Electronic Invoicing, PAC-agnostic core (`l10n_pa_edi`)

Implements DGI Resolución 201-6299 electronic invoicing for Panama.
Provides the abstract PAC interface, the DGI XML generator, the CUFE
algorithm, the CAFÉ PDF report, and hooks the Panama submission into
Odoo 19's `account_move_send` framework.

This module is **PAC-agnostic**. To actually send to DGI, install a
provider module (e.g.
[`l10n_pa_edi_factura_facil`](../l10n_pa_edi_factura_facil/)) that
implements the abstract interface.

## Dependencies

- [`l10n_pa`](../l10n_pa/)
- `account`
- `account_debit_note` (for credit/debit note lifecycle)
- Python: `lxml`, `qrcode`

## What you get

| Feature | Detail |
|---|---|
| Abstract PAC interface | `PACProvider` (ABC) with 4 operations + `PACResponse`/`PACStatus` dataclasses + 5-class exception hierarchy |
| DGI XML generator | Per Ficha Técnica PAC v1.00 (April 2025), namespace `http://dgi-fep.mef.gob.pa` |
| CUFE algorithm | Asciify + Luhn check digit, deterministic |
| Send method | Registers `pa_dgi` extra-EDI in Odoo 19's `account_move_send` |
| CAFÉ PDF | QWeb report with QR code via Odoo's `/report/barcode/` controller |
| Credit/debit notes | Original CUFE linkage via `l10n_pa_origin_cufe` |
| Anulación events | `action_l10n_pa_cancel_with_pac()` |
| Contingency mode | `l10n_pa_contingency` flag flips `iTpEmis = 02` |
| DGI error catalog | 11 common codes preloaded with Spanish messages; resolver for unknown codes |

## Configuration

**Settings → Companies → <your company> → Factura Electrónica Panamá**:

- **PAC**: pick a registered provider (`Sin PAC` until you install one)
- **Ambiente**: `Pruebas / Sandbox` or `Producción`
- **Sucursal SFEP** / **Punto de Emisión** / **Tipo de Emisión**
- **Formato CAFE** / **Entrega CAFE**
- **Código de Actividad Económica**
- **Certificado de Firma Electrónica (.p12)** + password (for PACs that
  require contributor-held certs)

## How it Plugs Into the Send Wizard

When a user posts a Panama sale invoice and opens **Send & Print**,
"**Enviar a DGI vía PAC**" appears as an **Extra EDI** option. Selecting
it triggers the configured provider's `send_invoice()` from inside the
send-flow hook. On success the move flips to `Autorizada`, the CUFE is
populated, and the authorized XML attaches to the move.

For ad-hoc submission outside the wizard, the form view exposes:

- **Enviar a DGI vía PAC** (button) — when posted and not yet authorized
- **Consultar estado DGI** — refresh from PAC for a sent/rejected move
- **Anular en DGI** — register an Anulación event for an authorized move

## Writing a New Provider Module

Create a new module that depends on `l10n_pa_edi`:

```python
# my_pac/pac_providers/my_pac.py
from odoo.addons.l10n_pa_edi.models.pac_provider import PACProvider, PACResponse, PACStatus

class MyPacProvider(PACProvider):
    code = 'my_pac'
    name = 'My PAC S.A.'

    def send_invoice(self, move) -> PACResponse: ...
    def get_status(self, cufe: str) -> PACStatus: ...
    def cancel_invoice(self, move, reason: str) -> PACResponse: ...
    def validate_ruc(self, ruc: str, dv: str) -> bool: ...
```

Register the provider on `account.move` and `res.company`:

```python
# my_pac/models/res_config_settings.py
class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model
    def _l10n_pa_pac_provider_selection(self):
        return super()._l10n_pa_pac_provider_selection() + [('my_pac', "My PAC S.A.")]


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _l10n_pa_provider_registry(self):
        registry = super()._l10n_pa_provider_registry()
        registry['my_pac'] = MyPacProvider
        return registry
```

That's it. The send wizard, form buttons, status query, and cancel
flow all work without further code.

## Testing

```bash
odoo-bin -d test_pa_edi -i l10n_pa_edi --test-enable --test-tags=/l10n_pa,/l10n_pa_edi --stop-after-init
```

48 tests cover CUFE generation, XML well-formedness and field-level
correctness, account.move integration, the send method hook with a
fake in-process provider, error code resolution, and the doc-type
mapping for credit/debit notes.

## Known Limitations

- **DGI XSDs are not bundled.** They ship with PAC contracts and are
  not publicly downloadable. Tests assert structural correctness and
  field formatting but not full schema compliance. Once you have the
  XSDs, drop them into `l10n_pa_edi/data/xsd/` and validate via
  `lxml.etree.XMLSchema`.
- **XAdES signing is delegated to the PAC.** This module emits unsigned
  XML. PACs that require contributor-signed XML need an additional
  signing module (`xmlsec`-backed) — out of scope for the initial
  release.
- See [`../TECH_DEBT.md`](../TECH_DEBT.md) for the full list.

## License

LGPL-3.
