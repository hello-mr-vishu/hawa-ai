import threading
import time
from typing import Any

import requests
from geopy.geocoders import Nominatim
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.google_search_tool import google_search
from tenacity import retry, stop_after_attempt, wait_exponential


# ---------------------------------------------------------------------------
# Google search grounding agent
# ---------------------------------------------------------------------------

LLM = "gemini-2.5-flash-lite"

_search_agent = Agent(
    model=LLM,
    name="google_search_wrapped_agent",
    description="An agent providing Google-search grounding capability",
    instruction="""
        Answer the user's question directly using google_search grounding tool; Provide a brief but concise response.
        Rather than a detail response, provide the immediate actionable item for a tourist or traveler, in a single sentence.
        Do not ask the user to check or look up information for themselves, that's your role; do your best to be informative.
        IMPORTANT:
        - Always return your response in bullet points
        - Specify what matters to the user
    """,
    tools=[google_search],
)

google_search_grounding = AgentTool(agent=_search_agent)


# ---------------------------------------------------------------------------
# Sync TTL cache (thread-safe, for use inside synchronous tool functions)
# ---------------------------------------------------------------------------

class _SyncTTLCache:
    """Simple thread-safe TTL cache for synchronous code paths."""

    def __init__(self, ttl: float = 86400.0, max_size: int = 1000):
        self._ttl = ttl
        self._max_size = max_size
        self._store: dict[str, tuple[Any, float]] = {}  # key -> (value, created_at)
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, created_at = entry
            if time.monotonic() - created_at > self._ttl:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._store) >= self._max_size and key not in self._store:
                oldest_key = next(iter(self._store))
                del self._store[oldest_key]
            self._store[key] = (value, time.monotonic())


_geocode_cache = _SyncTTLCache(ttl=86400.0)   # 24 h — locations rarely change
_overpass_cache = _SyncTTLCache(ttl=3600.0)   # 1 h — places data is less volatile


# ---------------------------------------------------------------------------
# Overpass API with tenacity retry
# ---------------------------------------------------------------------------

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def _overpass_request(overpass_url: str, params: dict) -> requests.Response:
    response = requests.get(overpass_url, params=params, timeout=25)
    if response.status_code != 200:
        raise requests.exceptions.HTTPError(
            f"Overpass returned {response.status_code}"
        )
    return response


# ---------------------------------------------------------------------------
# Nearby places tool
# ---------------------------------------------------------------------------

def find_nearby_places_open(query: str, location: str, radius: int = 3000, limit: int = 5) -> str:
    """
    Finds nearby places for any text query using ONLY free OpenStreetMap APIs (no API key needed).

    Args:
        query (str): What you're looking for (e.g., "restaurant", "hospital", "gym", "bar").
        location (str): The city or area to search in.
        radius (int): Search radius in meters (default: 3000).
        limit (int): Number of results to show (default: 5).

    Returns:
        str: List of matching place names and addresses.
    """
    try:
        # Step 1: Geocode the location — check cache first
        cache_key_geo = f"geo:{location.lower().strip()}"
        coords = _geocode_cache.get(cache_key_geo)
        if coords is None:
            geolocator = Nominatim(user_agent="open_place_finder")
            loc = geolocator.geocode(location)
            if not loc:
                return f"Could not find location '{location}'."
            coords = (loc.latitude, loc.longitude)
            _geocode_cache.set(cache_key_geo, coords)

        lat, lon = coords

        # Step 2: Query Overpass — check cache first
        cache_key_over = f"overpass:{query.lower()}:{lat:.4f}:{lon:.4f}:{radius}:{limit}"
        cached_result = _overpass_cache.get(cache_key_over)
        if cached_result is not None:
            return cached_result

        overpass_url = "https://overpass-api.de/api/interpreter"
        overpass_query = f"""
        [out:json][timeout:25];
        (
          node["name"~"{query}", i](around:{radius},{lat},{lon});
          node["amenity"~"{query}", i](around:{radius},{lat},{lon});
          node["shop"~"{query}", i](around:{radius},{lat},{lon});
        );
        out body {limit};
        """

        response = _overpass_request(overpass_url, {"data": overpass_query})
        data = response.json()
        elements = data.get("elements", [])
        if not elements:
            result = f"No results found for '{query}' near {location}."
            _overpass_cache.set(cache_key_over, result)
            return result

        # Step 3: Format results
        output = [f"Top results for '{query}' near {location}:"]
        for el in elements[:limit]:
            name = el.get("tags", {}).get("name", "Unnamed place")
            street = el.get("tags", {}).get("addr:street", "")
            city = el.get("tags", {}).get("addr:city", "")
            full_addr = ", ".join(filter(None, [street, city]))
            output.append(f"- {name} | {full_addr if full_addr else 'Address not available'}")

        result = "\n".join(output)
        _overpass_cache.set(cache_key_over, result)
        return result

    except Exception as e:
        return f"Error searching for '{query}' near '{location}': {str(e)}"


location_search_tool = FunctionTool(func=find_nearby_places_open)
