# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to semantic versioning per Odoo conventions
(`<odoo>.<major>.<minor>.<patch>`).

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
