# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Local Panama postal location lookups from official GeoJSON layers.

Ported from the MIT-licensed `kass507/panama-postal` project
(copyright (c) 2026 kass507) and relicensed as part of this Odoo module
under LGPL-3.

This helper intentionally supports only local files. Odoo business flows
should not call public government endpoints implicitly while users edit
partners, invoices, or delivery addresses.
"""

from pathlib import Path
from typing import Any

from .geojson import GeoJsonPointIndex


LOCAL_LAYERS = {
    "provincia": ("PROVINCIAS.geojson.gz", "PROV_NOMB", "PROV_ID"),
    "distrito": ("DISTRITOS.geojson.gz", "DIST_NOMB", "DIST_ID"),
    "corregimiento": ("CORREGIMIENTOS.geojson.gz", "CORR_NOMB", "CORR_ID"),
    "poblado": ("POBLADOS.geojson.gz", "LUPO_NOMB", "LUPO_ID"),
    "barrio": ("BARRIOS.geojson.gz", "BARR_NOMB", "BARR_ID"),
}


class LocalLocator:
    """Lookup political divisions from local Panama GeoJSON files."""

    def __init__(self, data_dir: str | Path = "."):
        self.data_dir = Path(data_dir)
        self._indices: dict[str, GeoJsonPointIndex | None] = {}

    def _index_for(self, level: str) -> GeoJsonPointIndex | None:
        if level in self._indices:
            return self._indices[level]

        filename, _, _ = LOCAL_LAYERS[level]
        path = self.data_dir / filename
        if not path.exists():
            self._indices[level] = None
            return None

        self._indices[level] = GeoJsonPointIndex.from_file(path)
        return self._indices[level]

    def has_any_data(self) -> bool:
        return any(
            (self.data_dir / filename).exists()
            for filename, _, _ in LOCAL_LAYERS.values()
        )

    def lookup(self, lat: float, lng: float) -> dict[str, Any] | None:
        if not self.has_any_data():
            return None

        result = {}
        any_hit = False
        for level, (_, name_field, id_field) in LOCAL_LAYERS.items():
            index = self._index_for(level)
            if index is None:
                result[level] = None
                continue
            props = index.lookup(lat, lng)
            if props is None:
                result[level] = None
                continue
            result[level] = {
                "nombre": props.get(name_field),
                "codigo": props.get(id_field),
            }
            any_hit = True

        return result if any_hit else None
