"""Unit tests for travel_agent/tools.py — all external calls mocked."""

from unittest.mock import MagicMock, patch

import pytest

from travel_agent.tools import find_nearby_places_open, _geocode_cache, _overpass_cache


@pytest.fixture(autouse=True)
def clear_caches():
    """Reset module-level caches before each test."""
    _geocode_cache._store.clear()
    _overpass_cache._store.clear()
    yield
    _geocode_cache._store.clear()
    _overpass_cache._store.clear()


class TestFindNearbyPlacesOpen:
    def test_returns_results_for_known_location(self):
        mock_loc = MagicMock()
        mock_loc.latitude = 48.8566
        mock_loc.longitude = 2.3522

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "elements": [
                {"tags": {"name": "Café de Flore", "addr:street": "Rue Saint-Germain"}},
                {"tags": {"name": "Le Procope", "addr:street": "Rue de l'Ancienne Comédie"}},
            ]
        }

        with patch("travel_agent.tools.Nominatim") as mock_nom, \
             patch("travel_agent.tools._overpass_request", return_value=mock_response):
            mock_nom.return_value.geocode.return_value = mock_loc
            result = find_nearby_places_open("café", "Paris", radius=1000, limit=2)

        assert "Café de Flore" in result
        assert "Le Procope" in result
        assert "Paris" in result

    def test_handles_geocoding_failure(self):
        with patch("travel_agent.tools.Nominatim") as mock_nom:
            mock_nom.return_value.geocode.return_value = None
            result = find_nearby_places_open("restaurant", "NonExistentCity123")

        assert "Could not find location" in result

    def test_handles_overpass_http_error(self):
        mock_loc = MagicMock()
        mock_loc.latitude = 51.5074
        mock_loc.longitude = -0.1278

        import requests as req_mod
        with patch("travel_agent.tools.Nominatim") as mock_nom, \
             patch("travel_agent.tools._overpass_request",
                   side_effect=req_mod.exceptions.HTTPError("500")):
            mock_nom.return_value.geocode.return_value = mock_loc
            result = find_nearby_places_open("pub", "London")

        assert "Error" in result

    def test_handles_empty_overpass_results(self):
        mock_loc = MagicMock()
        mock_loc.latitude = 35.6762
        mock_loc.longitude = 139.6503

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"elements": []}

        with patch("travel_agent.tools.Nominatim") as mock_nom, \
             patch("travel_agent.tools._overpass_request", return_value=mock_response):
            mock_nom.return_value.geocode.return_value = mock_loc
            result = find_nearby_places_open("izakaya", "Tokyo")

        assert "No results found" in result

    def test_geocode_cache_is_used_on_second_call(self):
        mock_loc = MagicMock()
        mock_loc.latitude = 48.8566
        mock_loc.longitude = 2.3522

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "elements": [{"tags": {"name": "Boulangerie Paul"}}]
        }

        with patch("travel_agent.tools.Nominatim") as mock_nom, \
             patch("travel_agent.tools._overpass_request", return_value=mock_response) as mock_req:
            mock_nom.return_value.geocode.return_value = mock_loc

            find_nearby_places_open("bakery", "Paris", limit=1)
            find_nearby_places_open("restaurant", "Paris", limit=1)

            # Geocoder should only be called once (cache hit on second call)
            assert mock_nom.return_value.geocode.call_count == 1
            # Overpass is called twice (different queries)
            assert mock_req.call_count == 2

    def test_overpass_cache_hit_skips_request(self):
        mock_loc = MagicMock()
        mock_loc.latitude = 48.8566
        mock_loc.longitude = 2.3522

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "elements": [{"tags": {"name": "Croissant Corner"}}]
        }

        with patch("travel_agent.tools.Nominatim") as mock_nom, \
             patch("travel_agent.tools._overpass_request", return_value=mock_response) as mock_req:
            mock_nom.return_value.geocode.return_value = mock_loc

            find_nearby_places_open("bakery", "Paris", radius=3000, limit=5)
            find_nearby_places_open("bakery", "Paris", radius=3000, limit=5)

            # Second call must use overpass cache — only 1 HTTP request total
            assert mock_req.call_count == 1
