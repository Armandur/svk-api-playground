import pytest
from matching import closest_match, haversine, normalize, sweref_to_wgs84, MAX_MATCH_M


class TestNormalize:
    def test_lowercase_and_strip(self):
        assert normalize("  Härnösands   domkyrka  ") == "härnösands domkyrka"

    def test_nfc_normalization(self):
        # Decomposed "ä" (a + combining diaeresis) vs precomposed "ä"
        decomposed = "älgutsboda kyrka"
        assert normalize(decomposed) == "älgutsboda kyrka"

    def test_collapses_whitespace(self):
        assert normalize("Sankta  Maria  kyrka") == "sankta maria kyrka"


class TestHaversine:
    def test_one_degree_latitude(self):
        # 1° latitud ≈ 111 195 m (haversine ger int)
        d = haversine(0.0, 0.0, 1.0, 0.0)
        assert 110_500 < d < 111_500

    def test_same_point_is_zero(self):
        assert haversine(59.0, 18.0, 59.0, 18.0) == 0

    def test_returns_int(self):
        assert isinstance(haversine(55.0, 13.0, 56.0, 14.0), int)

    def test_symmetry(self):
        assert haversine(57.0, 12.0, 58.0, 13.0) == haversine(58.0, 13.0, 57.0, 12.0)


class TestSwerefToWgs84:
    def test_linkoping_domkyrka(self):
        # kbr_id 32555, känd punkt
        lat, lng = sweref_to_wgs84(543386, 6483302)
        assert abs(lat - 58.488171) < 0.001
        assert abs(lng - 15.744161) < 0.001

    def test_returns_sweden_bounds(self):
        # Mittpunkten av Sverige ungefär
        lat, lng = sweref_to_wgs84(500000, 6700000)
        assert 55.0 < lat < 70.0
        assert 10.0 < lng < 25.0


class TestClosestMatch:
    def test_empty_candidates(self):
        result = closest_match(59.0, 18.0, [], "lat", "lng")
        assert result == (None, None)

    def test_returns_nearest(self):
        candidates = [
            {"lat": 59.1, "lng": 18.0, "name": "nära"},
            {"lat": 60.0, "lng": 18.0, "name": "långt"},
        ]
        match, dist = closest_match(59.0, 18.0, candidates, "lat", "lng")
        assert match["name"] == "nära"

    def test_respects_max_dist(self):
        candidates = [{"lat": 61.0, "lng": 18.0, "name": "för långt"}]
        result = closest_match(59.0, 18.0, candidates, "lat", "lng", max_dist=100_000)
        assert result == (None, None)

    def test_within_max_dist_returns_match(self):
        candidates = [{"lat": 59.01, "lng": 18.0, "name": "nära nog"}]
        match, dist = closest_match(59.0, 18.0, candidates, "lat", "lng", max_dist=5_000)
        assert match is not None
        assert dist < 5_000

    def test_default_max_dist_is_200km(self):
        # Punkt 150 km bort ska matchas med defaultvärdet
        candidates = [{"lat": 60.35, "lng": 18.0, "name": "150 km bort"}]
        match, _ = closest_match(59.0, 18.0, candidates, "lat", "lng")
        assert match is not None

    def test_returns_distance_as_number(self):
        candidates = [{"lat": 59.01, "lng": 18.0}]
        _, dist = closest_match(59.0, 18.0, candidates, "lat", "lng")
        assert isinstance(dist, (int, float))
