"""One-shot probe of the DGI eTax2 ISR calculator.

Goal: answer whether the Privado / Público sector switch produces
different ISR amounts for the same salary. If yes, our localization is
under-specified and needs a sector field. If no, the field is cosmetic.

Run: python3 /tmp/etax2_probe.py
"""
from __future__ import annotations

import re
import sys
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

URL = "https://etax2.mef.gob.pa/etax2web/Ccc/CalculoSobreRenta.aspx"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
SALARY_FIELD = "ctl00$ctl00$Contenedor$Contenedor$idSalario"
SECTOR_FIELD = "ctl00$ctl00$Contenedor$Contenedor$idSector$idSector"
SPOUSE_FIELD = "ctl00$ctl00$Contenedor$Contenedor$idConyugeDependiente"
BTN_FIELD = "ctl00$ctl00$Contenedor$Contenedor$BtnCalcular"
RESULT_ID = "Contenedor_Contenedor_idImpuestoSobreRenta"


def initial_page(session: requests.Session) -> dict[str, str]:
    r = session.get(URL, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    fields = {}
    for name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        el = soup.find("input", {"name": name})
        if not el:
            raise RuntimeError(f"Missing hidden field {name}")
        fields[name] = el.get("value", "")
    return fields


def calc(session: requests.Session, sector: str, salary: float, spouse: bool) -> Optional[float]:
    state = initial_page(session)
    payload = {
        "__EVENTTARGET": BTN_FIELD,
        "__EVENTARGUMENT": "",
        "__VIEWSTATE": state["__VIEWSTATE"],
        "__VIEWSTATEGENERATOR": state["__VIEWSTATEGENERATOR"],
        "__EVENTVALIDATION": state["__EVENTVALIDATION"],
        SECTOR_FIELD: sector,
        SALARY_FIELD: f"{salary:,.2f}",
        # ScriptManager hidden fields are sent empty; ASP.NET tolerates that
        "ctl00$ctl00$ScriptManager1": "",
    }
    if spouse:
        payload[SPOUSE_FIELD] = "on"

    r = session.post(
        URL,
        data=payload,
        headers={
            "User-Agent": UA,
            "Referer": URL,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=30,
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    el = soup.find("input", {"id": RESULT_ID})
    if not el:
        return None
    val = (el.get("value") or "").strip()
    if not val:
        return None
    cleaned = re.sub(r"[^0-9.,-]", "", val).replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def main() -> int:
    cases = []
    for salary in (800, 1000, 1500, 2000, 4000, 6000, 10000):
        for sector in ("Privado", "Público"):
            for spouse in (False, True):
                cases.append((sector, salary, spouse))

    session = requests.Session()
    print(f"{'sector':10s}  {'salary':>10s}  {'spouse':>6s}  {'ISR':>10s}")
    print("-" * 44)
    last_pair = {}  # (salary, spouse) -> {sector: result}
    for sector, salary, spouse in cases:
        try:
            result = calc(session, sector, salary, spouse)
        except Exception as e:
            print(f"ERROR {sector} {salary} {spouse}: {e}", file=sys.stderr)
            return 2
        print(f"{sector:10s}  {salary:>10.2f}  {str(spouse):>6s}  {result if result is not None else 'None':>10}")
        last_pair.setdefault((salary, spouse), {})[sector] = result
        time.sleep(0.4)

    print()
    print("=== Sector comparison ===")
    diffs = 0
    for (salary, spouse), per_sector in sorted(last_pair.items()):
        priv = per_sector.get("Privado")
        pub = per_sector.get("Público")
        same = priv == pub
        diffs += 0 if same else 1
        print(f"  salary={salary:>7.2f} spouse={spouse!s:5s} priv={priv!r:>10s} pub={pub!r:>10s} same={same}")
    print()
    print(f"Sector matters? {'NO — field appears cosmetic' if diffs == 0 else f'YES — {diffs} cases differ'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
