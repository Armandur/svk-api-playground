import math
import re
import unicodedata

from pyproj import Transformer

MAX_MATCH_M = 200_000

_transformer = Transformer.from_crs("EPSG:3006", "EPSG:4326", always_xy=True)


def sweref_to_wgs84(x: float, y: float) -> tuple[float, float]:
    lng, lat = _transformer.transform(x, y)
    return round(lat, 6), round(lng, 6)


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * R * math.asin(math.sqrt(a)))


def normalize(name: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", name).lower().strip())


def closest_match(kbr_lat, kbr_lng, candidates, lat_k, lng_k, max_dist=MAX_MATCH_M):
    best, best_d = None, float("inf")
    for c in candidates:
        d = haversine(kbr_lat, kbr_lng, c[lat_k], c[lng_k])
        if d < best_d:
            best, best_d = c, d
    return (best, best_d) if best_d <= max_dist else (None, None)
