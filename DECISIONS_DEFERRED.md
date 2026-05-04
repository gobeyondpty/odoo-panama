# Decisions Deferred

Items in this repo that need outside input (Panama CPA, DGI documentation, processor settlement data, PAC vendor) before the modules can be trusted in production. Each item: status, reason, suggested next step, what it blocks.

---

## Upstream `l10n_pa` already exists in Odoo 19

- **Status:** Resolved during factura Phase 2; documented here for the user to confirm before publishing.
- **Reason:** Odoo 19 ships an `l10n_pa` module (author: Cubic ERP) containing chart of accounts, the 7% ITBMS sale/purchase taxes, and `template_pa.py`. It does NOT contain identification types, the DV algorithm, the other ITBMS rates (0/10/15%), fiscal positions, or account groups.
- **Decision taken:** This module supersedes the upstream one. The chart of accounts (105 accounts) and account-code prefixes were copied verbatim from upstream so existing customers can upgrade in place. Tax IDs were renamed (`tax_pa_itbms_07_sale` instead of `ITAX_19`) to make rate-specific naming consistent across all four ITBMS rates.
- **Suggested next step:** When PR'ing to `odoo/odoo` master, do so as a refactor of the existing `l10n_pa` rather than a new module. Coordinate with `localization@odoo.com`. Existing tax IDs may need to remain as aliases for one release for backward compatibility.
- **Blocks:** Nothing in this repo. Affects upstream PR strategy only.

## Chart of Accounts — accountant review

- **Status:** Inherited verbatim from upstream Odoo 19 `l10n_pa` (Cubic ERP, AHMNET CORP attribution). 105 accounts following a Panamanian PUC-style code structure.
- **Reason:** The plan called for "empty headers only" with the expectation that an accountant would populate them. Since upstream ships a chart, we use it as a baseline rather than ship empty.
- **Suggested next step:** Sit with a Panama-licensed accountant to review whether: (a) every account is still relevant, (b) the "Sales - Product Category 01..05" placeholders match the operator's business model, (c) NIC/NIIF code groupings (`account.group-pa.csv`) are correct.
- **Blocks:** Nothing structurally. May need adjustment for specific industries (e.g. travel agencies need commission and pass-through revenue accounts not in the upstream chart).

## Default sale/purchase tax for new PA companies

- **Status:** Set to ITBMS 7% sale/purchase via `template_pa.py`.
- **Reason:** 7% is the standard rate and matches DGI defaults.
- **Suggested next step:** For travel agencies, the company may want the default sale tax to be "ITBMS Exento" per Article 1057-V parágrafo 4 of the Código Fiscal. This is a per-company override and not changed at the chart-template level.
- **Blocks:** Nothing.

## ITBMS withholding rates — encoded from DGI primary source

- **Status:** Encoded in `l10n_pa_account_withholding/data/account_tax_data.xml` from the official DGI presentation "Retenciones ITBMS — Ampliación de los mecanismos de retención" (`dgi.mef.gob.pa/itbms/Pdf-Retencion/PRESENTACIÓN-RETENCION-ITBMS-PRIVADA.pdf`).
- **Rates currently in force (vigentes desde 01/01/2017):** Estado 50% sobre bienes/servicios; Estado 100% sobre servicios profesionales; No domiciliados 100% calculado con coeficiente 0.065421 sobre monto pagado (Decreto Ejecutivo 91/2010 art 13); Sociedades sin personería 50%; Gran comprador (literal d) 50%; Tarjetas DB/CR 50% del ITBMS.
- **Open follow-up:** The DGI publishes the annual list of literal-d agentes de retención before September 1 each year (Resolución 201-XXXX). Verify the operator's company is or is not on the list each year and update `res.company.l10n_pa_wh_agent_type` accordingly.
- **Blocks:** Nothing for the framework. Production posting should still be CPA-reviewed, particularly the no-domiciliado 6.5421% coefficient applied as `account.tax.amount=-6.5421` against the gross-paid base — verify the computation matches DGI eTax2 outputs in a few real cases before relying on it.

## Per-acquirer credit-card retention details

- **Status:** Generic "Tarjeta DB/CR 50%" tax encoded. Per-acquirer behavior (PROCESA, Telered, Banistmo Acquiring, Credomatic, Visanet, Banco General, Caja de Ahorros, etc.) not differentiated.
- **Reason:** All acquirers retain 50% del ITBMS uniformly per the post-2017 regime. Per-acquirer differences appear in the Forms 23/44 reporting flow (which is the acquirer's obligation, not the merchant's).
- **Suggested next step:** Use real merchant settlement statements to confirm each acquirer is applying 50% del ITBMS as expected. Keep statements in `private/` only.
- **Blocks:** Nothing.

## DGI Form 430 line definitions

- **Status:** `l10n_pa_reports` ships the report skeleton with conceptual sections (Operaciones Gravadas / Exentas / ITBMS Causado / Créditos) but no `tag_name` expressions binding casillas to underlying `account.tax` records.
- **Reason:** Form 430 (ITBMS monthly declaration) groups operations into specific casillas keyed to ITBMS rate, exempt operations, foreign operations, and credits. A wrong casilla mapping will fail DGI validation. The exact casilla numbering changes between revisions.
- **Suggested next step:** Pull the current Form 430 instructivo from `dgi.mef.gob.pa/_7Itbms` and map each casilla to the corresponding tax/account groups in `l10n_pa`. Build the report incrementally and cross-check against an accountant-prepared declaration.
- **Blocks:** Filing automation.

## Annual income tax form (Declaración Jurada de Rentas)

- **Status:** Not started.
- **Reason:** Different forms for natural vs juridical persons; structure depends on whether the company is a regular contributor, ATP/IATA travel agency, Zona Libre, or other special regime.
- **Suggested next step:** Confirm with CPA which form variant applies per company. Then build the report definition under `l10n_pa_reports`.
- **Blocks:** Annual filing automation.
