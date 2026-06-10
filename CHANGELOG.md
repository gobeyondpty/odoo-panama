# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to semantic versioning per Odoo conventions
(`<odoo>.<major>.<minor>.<patch>`).

## [Unreleased]

### Added

#### `l10n_pa_hr_payroll_account`

- The module now actually maps accounts (it was an empty shell):
  `_configure_payroll_account_pa` wires every Panama salary rule to the
  `l10n_pa` chart — salary expense (514), employer social-security
  expense (515), net salaries payable (241), CSS/SE payable (242), ISR
  withheld (244), and the decimo (243) / vacation (245) / seniority
  premium (246) / cesantia (261) provisions. Decimo payouts and
  liquidacion prima/indemnizacion consume their provisions. Employee
  deduction rules (negative totals) are mapped on `account_debit`
  because `hr_payroll_account` flips sides for negative amounts — a
  `codex review` finding; mapping them on credit would have debited
  the payables.
- Two payroll provision accounts (`245` Provisión para Vacaciones,
  `246` Provisión para Prima de Antigüedad) are added to the `pa`
  chart template; companies whose chart predates the module get them
  created (and chart-style xmlids registered) on install.
- Existing `pa`-chart companies are configured at install time via the
  `_load_payroll_accounts` function-call data record, matching the
  upstream Enterprise `l10n_*_hr_payroll_account` pattern.
- 5 integration tests covering account creation, rule mappings, and
  journal assignment on a fresh `pa` chart load.
- The mapping is a CPA-reviewable reference default; see
  `DECISIONS_DEFERRED.md`.

#### `l10n_pa_account_withholding` (19.0.1.1.0)

- New guard on `account.payment`: creating a payment with withholding
  lines on a journal whose payment method line has no outstanding
  account now raises a `ValidationError` with setup instructions.
  Without it, Odoo 19's "payment without journal entry" flow stores
  the withholding lines but never posts them — the retained amount
  silently lands in the bank suspense account at reconciliation.
  2 regression tests cover the blocked and the posting flow.

### Changed

#### `l10n_pa_edi`

- `_COUNTRY_ALPHA3` extended from 35 hand-picked countries to the full
  ISO 3166-1 table (249 entries, sourced from the Debian `iso-codes`
  dataset) plus Odoo's non-ISO `XK` (Kosovo → `XKX`) and `XI`
  (Northern Ireland → `GBR`). A new test asserts every `res.country`
  record resolves to a real alpha-3 code.

### Fixed

#### `l10n_pa_edi_factura_facil`

- `_build_item` now reports each tax's own amount (via
  `account.tax.compute_all`) instead of duplicating the line's combined
  tax delta into every `taxes[]` entry — a line with ITBMS + ISC
  previously declared double tax to the PAC.
- `items[].discount` is now sent as the per-unit amount in Balboas as
  required by FF v1 §1.1 ("no en porcentaje"); it previously sent
  Odoo's percentage value.
- Unknown ITBMS rates now fail loudly via the shared
  `dgi_xml.itbms_rate_to_code` (PACError) instead of being silently
  declared Exento (`00`).
- `quantity`/`price`/`discount` keep up to 6 decimals instead of being
  truncated to 2, so qty × price arithmetic matches the document total.
- FF `DocumentStatus.status` code `1` (meaning unconfirmed) now maps to
  `pending` instead of `authorized`; only the live-confirmed `3`
  ("Finalizado") authorizes a document on status refresh.
- The provider falls back to the legacy
  `l10n_pa_edi.factura_facil.api_key` system parameter when the
  company-level API key is empty, so pre-19.0.1.1.0 configurations keep
  working after upgrade.
- The company API-key field is now restricted to Settings users
  (`groups='base.group_system'`); the provider reads it with `sudo()`.
- Manifest/README/test docs updated to describe the implemented
  `find_by_cufe_or_id` status lookup and `/api/pac/event/issue/`
  cancellation flow.

#### `l10n_pa_edi`

- Seeded DGI error catalog records for PAC codes `1002` (Documento
  duplicado) and `1513` (Número del documento fiscal duplicado) so
  code-only rejections resolve to a readable message.
- Removed the unused `_l10n_pa_get_or_create_cafe_attachment` helper
  (the CAFE block is embedded in the standard invoice PDF; the cached
  attachment was never invalidated and had no callers) and an
  unreachable branch in `_l10n_pa_format_pac_error`.
- Fixed `test_send_method` asserting a CAFE heading string that the
  reworded template no longer renders.

## [19.0.1.1.0] — 2026-05-19

### Changed

#### `l10n_pa_edi_factura_facil`

- Replaced the placeholder Factura Fácil REST client with the v1 API
  per the live Swagger at
  `https://backend-qa-api.facturafacil.com.pa/swagger/?format=openapi`.
  The PDF `Documentacion API FF V1.pdf` (October 2024) mislabels some
  paths (drops the `/api/` prefix; mislabels CSV as a JSON listing).
  This implementation follows the live spec.
- `send_invoice` POSTs `/api/pac/reception_fe/detailed/` with the
  `{header, document}` envelope and parses the `DocumentResult`
  response (`cufe`, `document_uuid`, `xml`, `qr_code_data`, `pdf_url`,
  `messages[]`, `rejected`).
- `get_status` calls
  `GET /api/pac/reception_fe/find_by_cufe_or_id/?cufe_or_id=<cufe>` and
  maps the `DocumentStatus.status` enum (`0`/`1`/`3`/`10`/`20`/`50`/
  `-100`) to `pending`/`authorized`/`rejected`/`cancelled`.
- `cancel_invoice` POSTs `/api/pac/event/issue/` with
  `{type: 'AN', cufe, reason}` (the v1 PDF omits this endpoint
  entirely; Swagger documents it as `EventoPACIssue`).
- `validate_ruc` falls back to local DV recomputation via
  `l10n_pa.calculate_dv` (FF v1 has no RUC lookup).
- Authentication moved from `Authorization: Bearer …` to the FF
  triplet `X-FF-Company` / `X-FF-Branch` / `X-FF-API-Key`. Credentials
  now live per `res.company` instead of `ir.config_parameter`, since
  each contribuyente is a separate FF tenant.
- Log sanitization extended to redact `X-FF-API-Key` header values.

## [19.0.1.0.0] — 2026-05-04

Initial release of the three-module Panama localization suite.

### Added

#### `l10n_pa`
- Seven `l10n_latam.identification.type` records (RUC, Cédula,
  Pasaporte, NT, E, PI, AV).
- DGI Dígito Verificador (DV) computation per ANIP `DV_RUC.pdf` for all
  seven identifier formats; exposed as `res.partner.l10n_pa_dv`.
- Format constraint on Panama partners (`_check_l10n_pa_ruc_format`).
- Four ITBMS rates (0%/7%/10%/15%) for sale and purchase, in four
  dedicated tax groups.
- Six fiscal positions (Contribuyente Inscrito, Consumo Final, Zona
  Libre, Exento de ITBMS, Gobierno, Extranjero), all `auto_apply`.
- 22 NIC/NIIF account groups.
- 105-account chart of accounts (preserved from upstream Odoo 19
  `l10n_pa` for migration compatibility).
- `res.company.l10n_pa_business_activity_code` field for DGI.
- `PA Demo Co.` demo company with valid RUC.
- 24 unit tests covering DV vectors, identification loading, fiscal
  positions, and chart-template installation.

#### `l10n_pa_edi`
- Abstract `PACProvider` interface with `send_invoice`, `get_status`,
  `cancel_invoice`, `validate_ruc`.
- `PACResponse` and `PACStatus` dataclasses; five-class exception
  hierarchy (`PACError → PACAPIError`/`PACValidationError`/`PACAuthError`/`PACConnectionError`).
- DGI XML generator (`models/dgi_xml.py`) per Ficha Técnica PAC v1.00
  (April 2025), namespace `http://dgi-fep.mef.gob.pa`.
- CUFE algorithm (`models/cufe.py`) ported from
  `Electronic-Signatures-Industries/dgi-fe` (MIT).
- `account.move` extensions: `l10n_pa_cufe`,
  `l10n_pa_security_code`, `l10n_pa_pac_status`, `l10n_pa_pac_response`,
  `l10n_pa_pac_error_codes`, `l10n_pa_origin_cufe`, `l10n_pa_contingency`,
  `l10n_pa_contingency_reason`, `l10n_pa_xml_attachment_id`,
  `l10n_pa_qr_payload`.
- Form-level actions: `action_l10n_pa_send_to_pac`,
  `action_l10n_pa_query_status`, `action_l10n_pa_cancel_with_pac`.
- Hook into Odoo 19's `account_move_send` framework as the
  `pa_dgi` extra-EDI delivery method, with preflight alerts that block
  submission when company RUC/DV are missing.
- `res.company` extensions: PAC selection (extension hook), sandbox/prod
  toggle, SFEP config (branch / emission point / type / form CAFE /
  delivery CAFE), PKCS#12 certificate storage.
- `res.partner.l10n_pa_receiver_type` (DGI iTipoRec) with computed
  default per partner profile.
- 11 preloaded DGI error codes with Spanish messages and a resolver
  helper.
- CAFÉ QWeb PDF report with QR code via Odoo's `/report/barcode/`
  controller.
- 48 unit tests (CUFE end-to-end, XML well-formedness and field-level
  correctness, account.move integration, send method hook with a fake
  in-process PAC).

#### `l10n_pa_edi_factura_facil`
- `FacturaFacilProvider` implementing the abstract PAC interface.
- HTTP client with 30s timeout, exponential-backoff retries on 5xx and
  connection errors, sanitized debug logging (api_key / Bearer tokens
  redacted).
- Settings UI under **Settings → Accounting → Fiscal Localization →
  Factura Fácil (PAC Panamá)** for QA URL, prod URL, API key, timeout.
- Default endpoint configuration via `ir.config_parameter` (API key
  intentionally not bundled).
- 18 unit tests (mocked HTTP) for credential sanitization, provider
  registration, success/4xx-rejection/401-auth/5xx-with-retry, status
  queries, cancel, and validate_ruc.

### Fixed (during initial development, after `codex review`)

- **CUFE/XML date mismatch on backdated invoices.** The CUFE was hashed
  over `invoice_date` but the XML emitted `dFechaEm = datetime.now()`,
  causing DGI rejections for backdated documents. Both paths now use
  the same date expression.
- **Wizard PAC rejections silently leaving the move at `'sent'` status.**
  The send-wizard hook now persists `l10n_pa_pac_status='rejected'` plus
  the raw response and error codes when the PAC returns failure.

### Known Limitations

- DGI XSDs are not bundled (PAC-only resource); XML validation is
  structural and field-level, not full schema. See `TECH_DEBT.md`.
- XAdES signing is delegated to the PAC; this module emits unsigned XML.
- Country alpha-3 mapping is hand-rolled for ~35 LATAM/EU/major
  countries; extend `_COUNTRY_ALPHA3` for additional jurisdictions.
- Factura Fácil endpoint paths and DTO field names are educated guesses
  awaiting authenticated Swagger access. See `INTEGRATION_CHECKLIST.md`.
