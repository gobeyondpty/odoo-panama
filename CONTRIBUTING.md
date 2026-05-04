# Contributing to `odoo-panama`

Thanks for considering a contribution. This document covers the
development workflow for the modules in this repo.

## Repository Layout

```
odoo-panama/
├── l10n_pa/                      # Base accounting localization (LGPL-3)
├── l10n_pa_edi/                  # PAC-agnostic EDI core (LGPL-3)
├── l10n_pa_edi_factura_facil/    # Factura Fácil PAC implementation (LGPL-3)
├── l10n_pa_account_withholding/  # DGI ITBMS/ISR withholding (LGPL-3)
├── l10n_pa_reports/              # DGI Form 430 + rentas reports (LGPL-3)
├── PROGRESS.md                   # Build timeline
├── DECISIONS_DEFERRED.md         # Items needing outside input
├── TECH_DEBT.md                  # Known shortcuts with justification
└── INTEGRATION_CHECKLIST.md      # PAC integration punch list
```

## Prerequisites

- **Odoo 19.0** (Community or Enterprise)
- **PostgreSQL 16** (any v15+ should work)
- **Python 3.11+** with `lxml`, `qrcode`, `requests`
- **Docker** (recommended for repeatable test environments)

## Local Setup (with Docker)

```bash
git clone https://github.com/gobeyondpty/odoo-panama.git
cd odoo-panama

# Run the test suite against a fresh DB, with the upstream l10n_pa
# removed so this repo's version takes precedence in the namespace
# package lookup. See "Why we delete upstream l10n_pa" below.
./run-tests.sh
```

(`run-tests.sh` is a convenience wrapper that the maintainer keeps in
the repo root; if it isn't present, replicate what's in
`PROGRESS.md` Phase 6 — same docker-run command shape.)

## Why we delete upstream `l10n_pa`

Odoo 19 ships an `l10n_pa` module from Cubic ERP (`Panama -
Accounting`) that has only the basic chart of accounts and a single
ITBMS rate. Our `l10n_pa` supersedes it. Because Odoo's
`odoo.addons` namespace is initialized from the system-installed path
*first*, a custom `l10n_pa` in the addons path is shadowed by upstream
unless the upstream directory is removed.

For testing in a Docker container we work around this by `rm -rf`-ing
the upstream directory before launching `odoo-bin`. For production
deployments, either:

- mount this repo's `l10n_pa/` *into* the container's
  `/usr/lib/python3/dist-packages/odoo/addons/l10n_pa` (replacing
  upstream), or
- bake a custom Odoo image that omits upstream `l10n_pa`.

Once a PR for the additions lands in `odoo/odoo` master, this dance
becomes unnecessary.

## Running the Tests

The repo's tests are written against `odoo.tests.common.{BaseCase,
TransactionCase}` with `@tagged('-at_install', 'post_install',
'l10n_pa[_…]')`. Run with `--test-tags=/l10n_pa,/l10n_pa_edi,/l10n_pa_edi_factura_facil`
to filter to this repo only.

Quick recipe:

```bash
docker run --rm \
  --network odoo_default --user 0:0 \
  -v $(pwd):/mnt/odoo-panama:ro \
  -v /tmp/odoo-test.conf:/etc/odoo/odoo.conf:ro \
  -v /tmp/odoo-test-data:/var/lib/odoo-test \
  -e HOST=db odoo:19.0 \
  bash -c '
    rm -rf /usr/lib/python3/dist-packages/odoo/addons/l10n_pa &&
    odoo -c /etc/odoo/odoo.conf -d test_repo --stop-after-init \
         -i l10n_pa_edi_factura_facil --test-enable \
         --test-tags=/l10n_pa,/l10n_pa_edi,/l10n_pa_edi_factura_facil \
         --no-http --without-demo=False
  '
```

Look for the closing line:

```
… 0 failed, 0 error(s) of N tests when loading database 'test_repo'
```

## Writing Tests

- **Pure functions** (no DB) → inherit from `BaseCase`.
- **Anything ORM-y** → inherit from `TransactionCase`. Tests get
  rolled back at the end; never depend on cross-test state.
- **External HTTP** → always mocked. Patch
  `requests.request` (or higher in the call chain) with `unittest.mock.patch`.
- **PAC providers in tests** → register a fake provider via
  `_l10n_pa_provider_registry` and `_l10n_pa_pac_provider_selection`
  (see `l10n_pa_edi/tests/test_send_method.py` for the pattern).

## Coding Conventions

- Follow the upstream Odoo coding guidelines:
  <https://www.odoo.com/documentation/19.0/contributing/development/coding_guidelines.html>
- Field names on extended models are prefixed `l10n_pa_…`.
- XML IDs for fiscal positions use `fp_pa_<role>`; for taxes,
  `tax_pa_itbms_<rate>`; for tests, `test_<feature>.py`.
- User-facing strings: Spanish, wrapped in `_()`. Code comments and
  log messages: English.
- Logger setup: `_logger = logging.getLogger(__name__)` at the top.

## Sending Patches

1. Fork on GitHub.
2. Branch off `main`.
3. Make your changes; add tests.
4. `git commit` with a clear message — first line ≤ 70 chars.
5. Open a PR against `main`. CI will run the test suite.

For substantial changes, please open a discussion issue first to align
on direction.

## License

By contributing, you agree your code is offered under the LGPL-3
license that this repository uses.

## Sub-licensee Notes

- `l10n_pa/models/res_partner.py` ports the DV algorithm from
  `apple314159/panama-dv` (Apache-2.0). Keep the credit comment intact.
- `l10n_pa_edi/models/cufe.py` ports the CUFE algorithm from
  `Electronic-Signatures-Industries/dgi-fe` (MIT). Keep the credit
  comment intact.

## Need help?

Open an issue at
<https://github.com/gobeyondpty/odoo-panama/issues>.
