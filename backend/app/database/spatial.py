from typing import Optional, Tuple

from geoalchemy2 import Geography
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator


def point_wkt(lat: float, lng: float) -> str:
    """Format latitude/longitude as EWKT/WKT POINT(lng lat) in SRID 4326 order."""
    return f"POINT({lng:.7f} {lat:.7f})"


def parse_point_wkt(value: Optional[str]) -> Optional[Tuple[float, float]]:
    """Parse 'POINT(lng lat)' string into (lat, lng)."""
    if not value or not isinstance(value, str):
        return None
    cleaned = value.strip()
    if cleaned.upper().startswith("SRID=4326;"):
        cleaned = cleaned.split(";", 1)[1]
    if not cleaned.upper().startswith("POINT(") or not cleaned.endswith(")"):
        return None
    inner = cleaned[6:-1].strip()
    parts = inner.split()
    if len(parts) != 2:
        return None
    lng, lat = float(parts[0]), float(parts[1])
    return lat, lng


class PointGeography(TypeDecorator):
    """
    Dialect-aware geospatial column:
    - Uses PostGIS GEOGRAPHY(POINT, 4326) on PostgreSQL.
    - Stores WKT POINT(lng lat) as TEXT on SQLite for local testing without SpatiaLite.
    """

    impl = String(128)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(
                Geography(geometry_type="POINT", srid=4326, spatial_index=True)
            )
        return dialect.type_descriptor(String(128))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, tuple) and len(value) == 2:
            lat, lng = value
            wkt = point_wkt(lat, lng)
        else:
            wkt = str(value)
        if dialect.name == "postgresql" and not wkt.upper().startswith("SRID="):
            return f"SRID=4326;{wkt}"
        return wkt

    def process_result_value(self, value, dialect):
        return value
