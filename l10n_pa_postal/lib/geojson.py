# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Local GeoJSON point-in-polygon helpers for Panama postal enrichment.

Ported from the MIT-licensed `kass507/panama-postal` project
(copyright (c) 2026 kass507) and relicensed as part of this Odoo module
under LGPL-3.
"""

import gzip
import json
import math
from pathlib import Path
from typing import Any


def _point_in_ring(lng: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    if len(ring) < 3:
        return False
    j = len(ring) - 1
    for i, point in enumerate(ring):
        xi, yi = point[0], point[1]
        xj, yj = ring[j][0], ring[j][1]
        intersects = ((yi > lat) != (yj > lat)) and (
            lng < (xj - xi) * (lat - yi) / (yj - yi) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _point_in_polygon(lng: float, lat: float, polygon: list[list[list[float]]]) -> bool:
    if not polygon or not _point_in_ring(lng, lat, polygon[0]):
        return False
    return not any(_point_in_ring(lng, lat, hole) for hole in polygon[1:])


def _feature_contains(lng: float, lat: float, geom: dict) -> bool:
    if not geom:
        return False
    geom_type = geom.get("type")
    coords = geom.get("coordinates")
    if geom_type == "Polygon":
        return _point_in_polygon(lng, lat, coords)
    if geom_type == "MultiPolygon":
        return any(_point_in_polygon(lng, lat, poly) for poly in coords)
    return False


def _iter_points(geom: dict):
    coords = geom.get("coordinates")
    geom_type = geom.get("type")
    if geom_type == "Polygon":
        for ring in coords or []:
            yield from ring
    elif geom_type == "MultiPolygon":
        for polygon in coords or []:
            for ring in polygon:
                yield from ring


def _feature_bbox(geom: dict) -> tuple[float, float, float, float] | None:
    min_lng = min_lat = math.inf
    max_lng = max_lat = -math.inf
    has_any = False
    for point in _iter_points(geom):
        has_any = True
        lng, lat = point[0], point[1]
        min_lng = min(min_lng, lng)
        min_lat = min(min_lat, lat)
        max_lng = max(max_lng, lng)
        max_lat = max(max_lat, lat)
    return (min_lng, min_lat, max_lng, max_lat) if has_any else None


class GeoJsonPointIndex:
    """Small in-memory point-in-polygon index for GeoJSON features."""

    def __init__(self, features: list[dict]):
        self._features = []
        for feature in features:
            geom = feature.get("geometry")
            bbox = _feature_bbox(geom or {})
            if not bbox:
                continue
            self._features.append({
                "geometry": geom,
                "properties": feature.get("properties", {}),
                "bbox": bbox,
            })

    @classmethod
    def from_file(cls, path: str | Path) -> "GeoJsonPointIndex":
        path = Path(path)
        if path.suffix == ".gz":
            with gzip.open(path, "rb") as file:
                data = json.loads(file.read().decode("utf-8"))
        else:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        return cls(data.get("features", []))

    def lookup(self, lat: float, lng: float) -> dict[str, Any] | None:
        candidates = []
        for feature in self._features:
            min_lng, min_lat, max_lng, max_lat = feature["bbox"]
            if not (min_lng <= lng <= max_lng and min_lat <= lat <= max_lat):
                continue
            if _feature_contains(lng, lat, feature["geometry"]):
                props = feature["properties"]
                try:
                    area = float(props.get("AREA", math.inf))
                except (TypeError, ValueError):
                    area = math.inf
                candidates.append((area, props))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def __len__(self) -> int:
        return len(self._features)
