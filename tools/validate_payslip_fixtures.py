#!/usr/bin/env python3
"""Validate synthetic/private Panama payroll fixture JSON files.

Each fixture declares a payroll ``structure`` (default ``PA_REGULAR``)
and its expected line items. The validator dispatches by structure to
the appropriate aggregator in ``lib/calculations.py``.

Fixture format::

    {
      "employee": "Synthetic A",
      "period": "2026-01",
      "gross_salary": 1000.0,
      "structure": "PA_REGULAR",        # optional, default PA_REGULAR
      "rates": { ... },                  # only used by PA_REGULAR
      "expected_lines": { ... },
      "expected_net": 866.92             # optional; employee-facing net
    }
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "l10n_pa_hr_payroll"))

from lib.calculations import (  # noqa: E402
    StatutoryRates,
    calculate_decimo_lines,
    calculate_period_income_tax,
    calculate_statutory_lines,
    money,
)


def load_fixture(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def actual_lines_for(fixture: dict) -> dict[str, float]:
    structure = fixture.get("structure", "PA_REGULAR")
    if structure == "PA_REGULAR":
        fixture_rates = fixture.get("rates", {})
        rates_kwargs = {
            k: v for k, v in fixture_rates.items()
            if k in StatutoryRates.__dataclass_fields__
        }
        if "monthly_income_tax" not in rates_kwargs and "periods_per_month" in fixture_rates:
            rates_kwargs["monthly_income_tax"] = calculate_period_income_tax(
                fixture["gross_salary"],
                fixture_rates["periods_per_month"],
                int(fixture_rates.get("income_tax_months", 13)),
                fixture_rates.get("annual_deductions", 0.0),
            )
        rates = StatutoryRates(**rates_kwargs)
        return calculate_statutory_lines(fixture["gross_salary"], rates)
    if structure == "PA_DECIMO":
        return calculate_decimo_lines(fixture["gross_salary"])
    raise ValueError(f"Unknown structure {structure!r} in {fixture.get('employee')}")


def compare_fixture(path: Path, tolerance: float) -> list[str]:
    fixture = load_fixture(path)
    actual = actual_lines_for(fixture)
    expected = fixture["expected_lines"]
    errors = []

    for code, expected_value in expected.items():
        actual_value = money(actual.get(code, 0.0))
        expected_value = money(expected_value)
        if abs(actual_value - expected_value) > tolerance:
            errors.append(f"{path}: {code}: expected {expected_value}, got {actual_value}")

    if "expected_net" in fixture:
        employee_lines = (
            value
            for code, value in actual.items()
            if code.endswith("_EMP") or code.endswith("_EMP_DEC")
        )
        actual_net = money(fixture["gross_salary"] + sum(employee_lines))
        expected_net = money(fixture["expected_net"])
        if abs(actual_net - expected_net) > tolerance:
            errors.append(f"{path}: expected_net: expected {expected_net}, got {actual_net}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="JSON fixture files or directories")
    parser.add_argument("--tolerance", type=float, default=0.01)
    args = parser.parse_args()

    files = []
    for path in args.paths:
        if path.is_dir():
            files.extend(sorted(path.glob("*.json")))
        else:
            files.append(path)

    errors = []
    for file_path in files:
        errors.extend(compare_fixture(file_path, args.tolerance))

    if errors:
        for error in errors:
            print(error)
        return 1

    print(f"Validated {len(files)} fixture(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
