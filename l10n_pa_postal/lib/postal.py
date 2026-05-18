# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Codec for Panama postal codes.

Ported from the MIT-licensed `kass507/panama-postal` project
(copyright (c) 2026 kass507) and relicensed as part of this Odoo module
under LGPL-3. The algorithm is pure arithmetic over Panama's geospatial
postal-code grid and does not require network access.
"""

from dataclasses import dataclass


ALPHABET = "23456789ABCDEFGHJKLMNPQRSTVWXZ"
ALPHA_INDEX = {ch: i for i, ch in enumerate(ALPHABET)}

ORIGIN_LAT = 10.0
ORIGIN_LNG = -83.5

STEP_MACRO = 0.1425
STEP_MICRO = 0.1425 / 24
STEP_NANO = 0.0059375 / 25
STEP_PICO = 2375e-7 / 8

MACRO_COLS = 40
MICRO_COLS, MICRO_ROWS = 24, 24
NANO_COLS, NANO_ROWS = 25, 25
PICO_COLS, PICO_ROWS = 8, 8


@dataclass(frozen=True)
class DecodedPostal:
    """Decoded center point of a Panama postal-code grid cell."""

    lat: float
    lng: float
    precision_meters: float
    level: str
    estafeta_prefix: str | None
    body: str


def _encode_pair(value: int) -> str:
    return ALPHABET[value // 30] + ALPHABET[value % 30]


def _decode_pair(pair: str) -> int:
    return ALPHA_INDEX[pair[0]] * 30 + ALPHA_INDEX[pair[1]]


def normalize(code: str) -> tuple[str, str | None]:
    """Return ``(body, estafeta_prefix)`` for a postal code.

    Full 10-character codes contain a two-character estafeta prefix and
    an eight-character geospatial body. Shorter even-length bodies are
    accepted for coarser grid levels.
    """
    if not isinstance(code, str):
        return "", None

    clean = code.replace("-", "").replace(" ", "").upper()
    if not clean or len(clean) > 10:
        return "", None
    if any(ch not in ALPHA_INDEX for ch in clean):
        return "", None

    if len(clean) == 10:
        return clean[2:], clean[:2]
    if len(clean) % 2:
        return "", None
    return clean, None


def decode(code: str) -> DecodedPostal | None:
    """Decode a Panama postal code to the center of its grid cell."""
    body, prefix = normalize(code)
    if not body:
        return None

    lat = ORIGIN_LAT
    lng = ORIGIN_LNG
    level = "MACRO"
    precision = STEP_MACRO * 111_000

    if len(body) >= 2:
        macro = _decode_pair(body[0:2])
        macro_row = macro // MACRO_COLS
        macro_col = macro % MACRO_COLS
        lat = ORIGIN_LAT - macro_row * STEP_MACRO + STEP_MACRO / 2
        lng = ORIGIN_LNG + macro_col * STEP_MACRO + STEP_MACRO / 2
        level, precision = "MACRO", STEP_MACRO * 111_000

    if len(body) >= 4:
        macro = _decode_pair(body[0:2])
        macro_row, macro_col = macro // MACRO_COLS, macro % MACRO_COLS
        micro = _decode_pair(body[2:4])
        micro_row = micro // MICRO_COLS
        micro_col = micro % MICRO_COLS
        macro_lat = ORIGIN_LAT - macro_row * STEP_MACRO
        macro_lng = ORIGIN_LNG + macro_col * STEP_MACRO
        lat = macro_lat - micro_row * STEP_MICRO - STEP_MICRO / 2
        lng = macro_lng + micro_col * STEP_MICRO + STEP_MICRO / 2
        level, precision = "MICRO", STEP_MICRO * 111_000

    if len(body) >= 6:
        macro = _decode_pair(body[0:2])
        macro_row, macro_col = macro // MACRO_COLS, macro % MACRO_COLS
        micro = _decode_pair(body[2:4])
        micro_row, micro_col = micro // MICRO_COLS, micro % MICRO_COLS
        nano = _decode_pair(body[4:6])
        nano_row = nano // NANO_COLS
        nano_col = nano % NANO_COLS
        macro_lat = ORIGIN_LAT - macro_row * STEP_MACRO - micro_row * STEP_MICRO
        macro_lng = ORIGIN_LNG + macro_col * STEP_MACRO + micro_col * STEP_MICRO
        lat = macro_lat - nano_row * STEP_NANO - STEP_NANO / 2
        lng = macro_lng + nano_col * STEP_NANO + STEP_NANO / 2
        level, precision = "NANO", STEP_NANO * 111_000

    if len(body) >= 8:
        macro = _decode_pair(body[0:2])
        macro_row, macro_col = macro // MACRO_COLS, macro % MACRO_COLS
        micro = _decode_pair(body[2:4])
        micro_row, micro_col = micro // MICRO_COLS, micro % MICRO_COLS
        nano = _decode_pair(body[4:6])
        nano_row, nano_col = nano // NANO_COLS, nano % NANO_COLS
        pico = _decode_pair(body[6:8])
        pico_row = pico // PICO_COLS
        pico_col = pico % PICO_COLS
        macro_lat = (
            ORIGIN_LAT
            - macro_row * STEP_MACRO
            - micro_row * STEP_MICRO
            - nano_row * STEP_NANO
        )
        macro_lng = (
            ORIGIN_LNG
            + macro_col * STEP_MACRO
            + micro_col * STEP_MICRO
            + nano_col * STEP_NANO
        )
        lat = macro_lat - pico_row * STEP_PICO - STEP_PICO / 2
        lng = macro_lng + pico_col * STEP_PICO + STEP_PICO / 2
        level, precision = "PICO", STEP_PICO * 111_000

    return DecodedPostal(
        lat=lat,
        lng=lng,
        precision_meters=round(precision, 2),
        level=level,
        estafeta_prefix=prefix,
        body=body,
    )


def encode(lat: float, lng: float, level: str = "PICO") -> str:
    """Encode coordinates to the geospatial body of a Panama postal code."""
    if level not in ("MACRO", "MICRO", "NANO", "PICO"):
        raise ValueError(f"Invalid level: {level}")

    dlng = lng - ORIGIN_LNG
    dlat = ORIGIN_LAT - lat

    macro_col = int(dlng // STEP_MACRO)
    macro_row = int(dlat // STEP_MACRO)
    macro_code = _encode_pair(macro_row * MACRO_COLS + macro_col)
    if level == "MACRO":
        return macro_code

    rem_lng = dlng % STEP_MACRO
    rem_lat = dlat % STEP_MACRO
    micro_col = int(rem_lng // STEP_MICRO)
    micro_row = int(rem_lat // STEP_MICRO)
    micro_code = _encode_pair(micro_row * MICRO_COLS + micro_col)
    if level == "MICRO":
        return f"{macro_code}{micro_code}"

    rem_lng %= STEP_MICRO
    rem_lat %= STEP_MICRO
    nano_col = int(rem_lng // STEP_NANO)
    nano_row = int(rem_lat // STEP_NANO)
    nano_code = _encode_pair(nano_row * NANO_COLS + nano_col)
    if level == "NANO":
        body = f"{macro_code}{micro_code}{nano_code}"
        return f"{body[:3]}-{body[3:]}"

    rem_lng %= STEP_NANO
    rem_lat %= STEP_NANO
    pico_col = int(rem_lng // STEP_PICO)
    pico_row = int(rem_lat // STEP_PICO)
    pico_code = _encode_pair(pico_row * PICO_COLS + pico_col)
    body = f"{macro_code}{micro_code}{nano_code}{pico_code}"
    return f"{body[:3]}-{body[3:]}"


def is_in_panama(lat: float, lng: float, strict: bool = False) -> bool:
    """Return whether coordinates fall within Panama's postal-code bounds."""
    if strict:
        return 7.15 <= lat <= 9.70 and -83.10 <= lng <= -77.10
    return 6.0 <= lat <= 11.0 and -86.0 <= lng <= -74.0


def validate(code: str, strict: bool = False) -> bool:
    """Validate format and Panama bounding-box membership."""
    decoded = decode(code)
    return bool(decoded and is_in_panama(decoded.lat, decoded.lng, strict=strict))
