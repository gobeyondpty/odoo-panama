# Technical Debt

Shortcuts taken during the autonomous build, with justification and the
fix that should follow. Each item: what, why, risk, future fix.

---

## DGI XSD validation is structural, not schema-based

- **What:** XML generation tests verify well-formedness, namespace,
  element presence, and value formatting, but do NOT validate against
  the official DGI XSDs.
- **Why:** DGI does not publish the XSDs publicly. They ship with PAC
  contracts (e.g. `feRecepLoteFEDGI_v1.00.xsd`,
  `feRecepEventoFeDGI_v1.00.xsd`, `xmldsig-core-schema_v1.00.xsd`).
  The Ficha Técnica PAC v1.00 PDF is public and was used as the spec.
- **Risk:** A schema-violating field (e.g. wrong cardinality, wrong
  enum value) might generate well-formed XML that the PAC rejects. We
  cover the common shapes via `dgi-fe` reference but cannot
  exhaustively assert XSD compliance offline.
- **Future fix:** Once Factura Fácil sandbox credentials arrive, drop
  the XSD bundle into `l10n_pa_edi/data/xsd/` and add
  `lxml.etree.XMLSchema` validation in `_l10n_pa_generate_xml()` (debug
  mode) and in `tests/test_xml_generation.py`.

## Country alpha-3 mapping is hand-rolled — RESOLVED 2026-06-09

- **What:** `_country_alpha3` in `account_move.py` originally shipped a
  35-country hardcoded alpha-2 → alpha-3 map for the `cPaisRec` field.
- **Resolution:** The map now carries the full ISO 3166-1 table (249
  entries, generated from the Debian `iso-codes` dataset) plus Odoo's
  two non-ISO codes (`XK` → `XKX`, `XI` → `GBR`).
  `TestCountryAlpha3.test_every_res_country_resolves` asserts every
  `res.country` code resolves, so a future Odoo country addition that
  is missing from the map fails the suite instead of emitting a padded
  alpha-2 the PAC would reject.

## Synchronous PAC submission

- **What:** `action_l10n_pa_send_to_pac` and the
  `_hook_invoice_document_before_pdf_report_render` hook call the PAC
  inline on user click rather than via a queue.
- **Why:** Avoids adding `OCA/queue_job` as a dependency. Factura
  Fácil response time is documented at <5s under normal conditions.
- **Risk:** A slow PAC response blocks the user UI; a network hiccup
  forces a retry from the wizard.
- **Future fix:** Wrap PAC calls in a `queue.job` Job once the
  installation site has the OCA queue stack, or rebuild atop Odoo's
  own batch sending wizard.

## XAdES signing is delegated to the PAC

- **What:** This module emits unsigned XML; the XAdES enveloped
  signature is added by the PAC after submission.
- **Why:** DGI accepts both contributor-signed XML and PAC-signed XML;
  most PACs (including Factura Fácil per their documentation) sign on
  the contributor's behalf using a delegated certificate. Implementing
  XAdES locally requires `xmlsec` and a tested keyring path that
  raises the dependency surface significantly.
- **Risk:** Any PAC that requires contributor-signed XML will not work
  out of the box. Switching certificates from delegated-PAC to
  contributor-held requires this work.
- **Future fix:** Add an optional `l10n_pa_edi_signing` module that
  signs XML locally with `xmlsec` and a `.p12` from
  `res.company.l10n_pa_certificate_id`.

## CUFE security code (`dSeg`) is non-cryptographic

- **What:** `generate_security_code()` uses Python's `random` (Mersenne
  Twister), not `secrets`.
- **Why:** DGI does not require cryptographic randomness for `dSeg`;
  it requires uniqueness within the emitter's series. Mersenne is
  fine for that.
- **Risk:** None for DGI compliance. Auditors who insist on
  cryptographic-grade randomness for every secret-looking code may
  flag it.
- **Future fix:** Switch to `secrets.choice` if the operator requires.
