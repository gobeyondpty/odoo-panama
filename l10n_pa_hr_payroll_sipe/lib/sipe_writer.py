# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""SIPE planilla XLSX writer.

Pure-Python module so the column order, header names, and per-row validation
can be unit-tested without an Odoo bootstrap. The file format is dictated by
the official CSS document `Manual de Carga Masiva de Planilla V2`
(https://www.css.gob.pa/sipe/Manual%20Carga%20de%20Archivo%20V2.pdf), section
2.1 "Formato de carga": 25 columns A-Y, header row in row 1, data from row 2,
file extension `.xlsx`.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Iterable

from openpyxl import Workbook

# Column order per CSS Manual de Carga Masiva V2, section 2.1.
# Header text matches the canonical column labels listed under the screenshot
# in the manual (A. Tipo de Documento ... Y. Indemnización).
SIPE_COLUMNS: tuple[str, ...] = (
    "Tipo de Documento",
    "Número de Documento",
    "Número de Seguro Social",
    "Nombre",
    "Apellido",
    "Sueldo",
    "Horas Extras",
    "Impuesto Sobre Renta",
    "Décimo Tercer Mes",
    "Vacaciones",
    "Comisiones",
    "Bonificaciones",
    "Combustible",
    "Dieta",
    "Salario en Especie",
    "Viáticos",
    "Gasto de Representación",
    "Impuesto Sobre Renta Gasto Representación",
    "Décimo Tercer Mes Gasto Representación",
    "Primas de Producción",
    "Dividendo",
    "Participación Beneficio Ingresos",
    "Gratificación Aguinaldo",
    "Preaviso",
    "Indemnización",
)

# snake_case field keys that map 1:1 to SIPE_COLUMNS by index.
FIELD_KEYS: tuple[str, ...] = (
    "tipo_documento",
    "numero_documento",
    "numero_seguro_social",
    "nombre",
    "apellido",
    "sueldo",
    "horas_extras",
    "impuesto_sobre_renta",
    "decimo_tercer_mes",
    "vacaciones",
    "comisiones",
    "bonificaciones",
    "combustible",
    "dieta",
    "salario_en_especie",
    "viaticos",
    "gasto_representacion",
    "impuesto_sobre_renta_gasto_representacion",
    "decimo_tercer_mes_gasto_representacion",
    "primas_de_produccion",
    "dividendo",
    "participacion_beneficio_ingresos",
    "gratificacion_aguinaldo",
    "preaviso",
    "indemnizacion",
)

assert len(SIPE_COLUMNS) == len(FIELD_KEYS) == 25

# Tipo de Documento valid values. The SIPE planilla form distinguishes
# Cédula (Panama national ID), Pasaporte (foreign passport), and "Seguro
# Social" (CSS-only number assigned to employees without a cédula).
SIPE_TIPO_CEDULA = "CEDULA"
SIPE_TIPO_PASAPORTE = "PASAPORTE"
SIPE_TIPO_SEGURO_SOCIAL = "SEGURO SOCIAL"
SIPE_VALID_TIPOS: tuple[str, ...] = (
    SIPE_TIPO_CEDULA,
    SIPE_TIPO_PASAPORTE,
    SIPE_TIPO_SEGURO_SOCIAL,
)

# The first five columns are employee metadata (strings); the remaining 20
# are numeric amounts that aggregate payslip lines for the period.
_NUMERIC_KEYS = FIELD_KEYS[5:]


@dataclass(slots=True)
class SipeRow:
    """One employee row in a SIPE planilla file.

    Numeric fields default to 0.0 so callers only need to populate the
    components that the period actually has. Validation runs at construction:
    `tipo_documento` must be one of `SIPE_VALID_TIPOS`, identification fields
    must be non-empty, and numeric fields must be non-negative finite floats.
    """

    tipo_documento: str
    numero_documento: str
    numero_seguro_social: str
    nombre: str
    apellido: str
    sueldo: float = 0.0
    horas_extras: float = 0.0
    impuesto_sobre_renta: float = 0.0
    decimo_tercer_mes: float = 0.0
    vacaciones: float = 0.0
    comisiones: float = 0.0
    bonificaciones: float = 0.0
    combustible: float = 0.0
    dieta: float = 0.0
    salario_en_especie: float = 0.0
    viaticos: float = 0.0
    gasto_representacion: float = 0.0
    impuesto_sobre_renta_gasto_representacion: float = 0.0
    decimo_tercer_mes_gasto_representacion: float = 0.0
    primas_de_produccion: float = 0.0
    dividendo: float = 0.0
    participacion_beneficio_ingresos: float = 0.0
    gratificacion_aguinaldo: float = 0.0
    preaviso: float = 0.0
    indemnizacion: float = 0.0

    def __post_init__(self) -> None:
        if self.tipo_documento not in SIPE_VALID_TIPOS:
            raise ValueError(
                f"tipo_documento must be one of {SIPE_VALID_TIPOS!r}, "
                f"got {self.tipo_documento!r}"
            )
        for key in ("numero_documento", "numero_seguro_social", "nombre", "apellido"):
            value = getattr(self, key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{key} must be a non-empty string, got {value!r}")
        for key in _NUMERIC_KEYS:
            value = getattr(self, key)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise TypeError(f"{key} must be int or float, got {type(value).__name__}")
            fvalue = float(value)
            if fvalue != fvalue or fvalue == float("inf") or fvalue == float("-inf"):
                raise ValueError(f"{key} must be finite, got {value!r}")
            if fvalue < 0:
                raise ValueError(f"{key} must be non-negative, got {value!r}")
            setattr(self, key, fvalue)

    def to_cells(self) -> list:
        return [getattr(self, key) for key in FIELD_KEYS]


def write_sipe_xlsx(rows: Iterable[SipeRow], sheet_name: str = "Planilla") -> bytes:
    """Serialize an iterable of `SipeRow` to SIPE-format XLSX bytes.

    Uses openpyxl write-only mode so memory stays bounded for large planillas.
    The output passes CSS SIPE bulk-upload validation at the structural level;
    employee-specific validation (cédula recognized, salary above mínimo legal,
    etc.) still happens server-side after upload.
    """
    wb = Workbook(write_only=True)
    ws = wb.create_sheet(sheet_name)
    ws.append(list(SIPE_COLUMNS))
    for row in rows:
        ws.append(row.to_cells())
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


# Public field metadata for callers that want to introspect the schema
# (e.g. wizard previews, mapping configuration UIs). Order matches both
# SIPE_COLUMNS and FIELD_KEYS.
COLUMN_FIELD_META: tuple[tuple[str, str, str], ...] = tuple(
    (chr(ord("A") + i), key, label)
    for i, (key, label) in enumerate(zip(FIELD_KEYS, SIPE_COLUMNS, strict=True))
)


def numeric_field_keys() -> tuple[str, ...]:
    """Return the 20 numeric SIPE field keys (sueldo through indemnizacion)."""
    return _NUMERIC_KEYS


def all_field_keys() -> tuple[str, ...]:
    return FIELD_KEYS
