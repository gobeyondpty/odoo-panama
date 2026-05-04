# Panama — Accounting (`l10n_pa`)

Base accounting localization for Panama. Installs automatically when a
company is created with `country = Panama`. Has zero EDI dependencies
and runs on Odoo Community.

## What you get

| Feature | Detail |
|---|---|
| Identification types | RUC, Cédula, Pasaporte, NT, E, PI, AV (`l10n_latam.identification.type`) |
| RUC validation | Format constraint + Dígito Verificador (DV) computation per ANIP `DV_RUC.pdf` |
| ITBMS taxes | 7% (standard), 10% (alcohol/tobacco/hotels), 15% (cigarettes), 0% (exempt) — sale + purchase |
| Fiscal positions | Contribuyente Inscrito, Consumo Final, Zona Libre, Exento, Gobierno, Extranjero |
| Chart of accounts | NIC/NIIF-style structure, 105 accounts (inherited from upstream) |
| Account groups | 22 NIC/NIIF group prefixes (Activo/Pasivo/Patrimonio/etc.) |
| Demo company | `PA Demo Co.` with valid RUC `155718881-2-2018` |

## Dependencies

- `account` (Community)
- `l10n_latam_base` (LATAM identification framework)

## Installation

Either install through the Apps menu (filter by **Panamá**) or:

```bash
odoo-bin -d <db> -i l10n_pa --stop-after-init
```

The chart template is loaded automatically when a Panama company is
created or when you call `try_loading('pa', company)` programmatically.

## Configuration

After install:

1. **Settings → Companies → <your company>** — set **Tax ID (RUC)** in
   the format expected by the chosen identification type. The DV is
   computed automatically.
2. The default sale/purchase tax is `ITBMS 7%`. Change it to
   `ITBMS Exento` (or any other) per company if your operation is
   exempt (e.g. travel agencies under Article 1057-V).

## DV (Dígito Verificador) Computation

The DV is exposed as a stored, computed `Char` on `res.partner`:

```python
partner = env['res.partner'].create({
    'name': 'Empresa S.A.',
    'country_id': env.ref('base.pa').id,
    'vat': '155718881-2-2018',
    'l10n_latam_identification_type_id': env.ref('l10n_pa.ruc').id,
})
partner.l10n_pa_dv  # → '62'
```

The algorithm covers all 7 ANIP-documented formats (cédula, PE, N, E,
AV, PI, juridical, NT).

## Testing

```bash
# In a fresh Odoo 19 container with this module on the addons path:
odoo-bin -d test_pa -i l10n_pa --test-enable --test-tags=/l10n_pa --stop-after-init
```

24 tests cover the DV vectors from ANIP, identification-type loading,
fiscal-position auto-apply, and chart-template installation.

## License

LGPL-3.

## See Also

- [`l10n_pa_edi`](../l10n_pa_edi/) — DGI Factura Electrónica, PAC-agnostic
- [`l10n_pa_edi_factura_facil`](../l10n_pa_edi_factura_facil/) — Factura Fácil PAC
