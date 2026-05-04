# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Compute the DGI Código Único de Factura Electrónica (CUFE).

The CUFE is a deterministic identifier for a Panama electronic invoice.
Algorithm derived from the public TypeScript reference
`Electronic-Signatures-Industries/dgi-fe` (`src/fe/CUFE.ts`, MIT) and
the DGI Ficha Técnica PAC v1.00 (April 2025).

Structure (concatenated, padded as noted):

    +--------------------------------------------+
    |  field                  | size | example   |
    +--------------------------------------------+
    | iDoc  (TipoDocumento)   |   2  | "01"      |
    | dTipoRuc (1=natural,2=jur)|  1  | "2"       |
    | dRUC                    | var  | "155718881-2-2018" (digits+dashes; dashes preserved
    |                                              in the published reference) |
    | dDV                     |   2  | "62"     |
    | dSucEm  (sucursal)      |   4  | "0001"    |
    | dFechaEm                |   8  | "20260504" (YYYYMMDD)
    | dNroDF                  |  10  | "0000000001"
    | dPtoFacDF               |   3  | "001"
    | iTpEmis                 |   2  | "01"      |
    | iAmb                    |   1  | "1" or "2" |
    | dSeg (security code)    |   9  | random or seed-derived
    +--------------------------------------------+

A 1-digit Luhn (mod 10) check digit is appended at the end. The final
CUFE is the 39-49-character sequence above plus the check digit, with
non-digit characters of the RUC asciified per `_asciify`.
"""
from __future__ import annotations

import datetime
import random
import string


def _asciify(value: str) -> str:
    """Convert a mixed letter+digit string to a digit-only string.

    Digits pass through. Non-digits are replaced by the last digit of
    their ASCII codepoint. Mirrors the `asciify` reduction in
    `dgi-fe/CUFE.ts` so CUFEs computed in Odoo match those computed by
    a Node-based PAC client given the same inputs.
    """
    out = []
    for ch in value:
        if ch.isdigit():
            out.append(ch)
        else:
            n = ord(ch)
            # Take the last digit of the ASCII code (mirrors reference).
            out.append(str(n % 10))
    return ''.join(out)


def _luhn_check_digit(numeric: str) -> str:
    """Compute the 1-digit mod-10 (Luhn) check character for `numeric`."""
    if not numeric.isdigit():
        raise ValueError(f"luhn_check_digit requires digits only, got {numeric!r}")
    total = 0
    parity = (len(numeric) + 1) % 2
    for i, c in enumerate(numeric):
        d = int(c)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - (total % 10)) % 10)


def generate_security_code(seed: int | None = None) -> str:
    """Return a 9-digit random security code (`dSeg`).

    Pass `seed` for deterministic codes in tests.
    """
    rng = random.Random(seed)
    return ''.join(rng.choice(string.digits) for _ in range(9))


def build_cufe(
    *,
    tipo_documento: str,
    tipo_ruc: str,
    ruc: str,
    dv: str,
    sucursal: str,
    fecha_emision: datetime.date | datetime.datetime,
    nro_df: str,
    pto_fac_df: str,
    tipo_emision: str,
    ambiente: str,
    security_code: str,
) -> str:
    """Build the full CUFE string including its trailing Luhn digit.

    All inputs must be strings already in their DGI canonical form
    (no leading zeros are added here except as noted by the spec).

    Args:
      tipo_documento: 2-char code from DGI table B06 (e.g. "01" factura).
      tipo_ruc: "1" (natural) or "2" (jurídico).
      ruc: emitter RUC, dashes preserved per dgi-fe reference.
      dv: 2-char Dígito Verificador.
      sucursal: 1–4 digit branch code; left-padded to 4.
      fecha_emision: emission date or datetime (formatted YYYYMMDD).
      nro_df: 1–10 digit document number; left-padded to 10.
      pto_fac_df: 1–3 digit point-of-billing code; left-padded to 3.
      tipo_emision: 1–2 digit emission-type code; left-padded to 2.
      ambiente: "1" (production) or "2" (testing).
      security_code: 9-digit security code (`dSeg`).

    Returns:
      The CUFE string with its trailing Luhn check digit, ready to be
      placed in the `<dCufe>` element or used as the `dId`.
    """
    if len(tipo_documento) != 2:
        raise ValueError(f"tipo_documento must be 2 chars, got {tipo_documento!r}")
    if tipo_ruc not in ('1', '2'):
        raise ValueError(f"tipo_ruc must be '1' or '2', got {tipo_ruc!r}")
    if len(dv) != 2:
        raise ValueError(f"dv must be 2 chars, got {dv!r}")
    if ambiente not in ('1', '2'):
        raise ValueError(f"ambiente must be '1' or '2', got {ambiente!r}")
    if len(security_code) != 9 or not security_code.isdigit():
        raise ValueError(f"security_code must be 9 digits, got {security_code!r}")

    parts = [
        tipo_documento,
        tipo_ruc,
        ruc,
        '-' + dv,                                  # dash kept per dgi-fe ref
        sucursal.rjust(4, '0'),
        fecha_emision.strftime('%Y%m%d'),
        nro_df.rjust(10, '0'),
        pto_fac_df.rjust(3, '0'),
        tipo_emision.rjust(2, '0'),
        ambiente,
        security_code,
    ]
    sequence = ''.join(parts)
    asciified = _asciify(sequence)
    check = _luhn_check_digit(asciified)
    return sequence + check
