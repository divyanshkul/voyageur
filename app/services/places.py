"""Google Places client backed by SerpAPI's google_maps engine.

We use SerpAPI rather than the Google Places API directly so one key
(SERPAPI_API_KEY) powers both this module (hotel discovery) and
``serpapi.py`` (OTA prices). Interface is preserved from the original mock,
so callers (ResearchAgent) need no changes.

Fail-safe: if the API key is missing/placeholder, or a request fails, we
fall back to the curated mock data below so the demo keeps working.
"""

from __future__ import annotations

import logging
import random
import re

import httpx

from app.models import Hotel
from app.services import tracing

logger = logging.getLogger(__name__)

SERPAPI_BASE = "https://serpapi.com/search"

# ---------------------------------------------------------------------------
# Mock fallback data (kept so the pipeline still runs without a live key)
# ---------------------------------------------------------------------------

_COORG_HOTELS: list[dict] = [
    {"name": "The Coorg Wilderness Resort", "address": "Madikeri-Mangalore Hwy, Coorg, Karnataka 571201", "phone": "+919584009988", "rating": 4.6, "amenities": ["WiFi", "Pool", "Restaurant", "Parking", "Room Service"]},
    {"name": "Hotel Kaveri Residency", "address": "Main Road, Madikeri, Coorg, Karnataka 571201", "phone": "+919584009988", "rating": 3.8, "amenities": ["WiFi", "Parking", "Restaurant", "AC"]},
    {"name": "Coorg Heritage Inn", "address": "Stuart Hill, Madikeri, Coorg, Karnataka 571201", "phone": "+919584009988", "rating": 4.1, "amenities": ["WiFi", "Parking", "AC", "Room Service"]},
    {"name": "Club Mahindra Madikeri", "address": "Galibeedu Post, Madikeri, Coorg, Karnataka 571201", "phone": "+919584009988", "rating": 4.3, "amenities": ["WiFi", "Pool", "Restaurant", "Gym", "Parking"]},
    {"name": "The Tamara Coorg", "address": "Kabbinakad Estate, Jodupala, Coorg, Karnataka 571212", "phone": "+919584009988", "rating": 4.7, "amenities": ["WiFi", "Pool", "Restaurant", "Room Service", "Gym", "Parking"]},
    {"name": "Zostel Coorg", "address": "Pollibetta, Coorg, Karnataka 571215", "phone": "+919584009988", "rating": 3.5, "amenities": ["WiFi", "Parking"]},
    {"name": "Meriyanda Nature Lodge", "address": "Makkandur Village, Madikeri, Coorg, Karnataka 571201", "phone": "+919584009988", "rating": 4.0, "amenities": ["WiFi", "Parking", "Restaurant", "Room Service"]},
]

_GOA_HOTELS: list[dict] = [
    {"name": "Goa Beach House Calangute", "address": "Calangute Beach Road, Calangute, Goa 403516", "phone": "+91-832-227-6001", "rating": 4.2, "amenities": ["WiFi", "Pool", "Restaurant", "AC", "Room Service"]},
    {"name": "Hotel Mandovi Panjim", "address": "D.B. Bandodkar Marg, Panjim, Goa 403001", "phone": "+91-832-222-6102", "rating": 3.9, "amenities": ["WiFi", "AC", "Restaurant", "Parking"]},
    {"name": "The Leela Goa", "address": "Mobor, Cavelossim, South Goa 403731", "phone": "+91-832-662-1203", "rating": 4.7, "amenities": ["WiFi", "Pool", "Restaurant", "Gym", "Room Service", "Parking"]},
    {"name": "Zostel Goa Anjuna", "address": "Anjuna Beach Road, Anjuna, Goa 403509", "phone": "+91-887-100-7204", "rating": 3.4, "amenities": ["WiFi", "Parking"]},
    {"name": "Palolem Beach Resort", "address": "Palolem Beach, Canacona, South Goa 403702", "phone": "+91-832-264-3805", "rating": 4.0, "amenities": ["WiFi", "Restaurant", "AC", "Room Service"]},
    {"name": "The Park Calangute", "address": "Holiday Street, Calangute, Goa 403516", "phone": "+91-832-227-9906", "rating": 4.4, "amenities": ["WiFi", "Pool", "Restaurant", "Gym", "AC", "Parking"]},
]

_MYSORE_HOTELS: list[dict] = [
    {"name": "Royal Orchid Metropole Mysore", "address": "5 Jhansi Lakshmi Bai Road, Mysore, Karnataka 570005", "phone": "+91-821-425-5001", "rating": 4.3, "amenities": ["WiFi", "Pool", "Restaurant", "AC", "Parking", "Room Service"]},
    {"name": "Hotel Dasaprakash", "address": "Gandhi Square, Mysore, Karnataka 570001", "phone": "+91-821-244-2402", "rating": 3.7, "amenities": ["WiFi", "Restaurant", "AC"]},
    {"name": "Radisson Blu Plaza Mysore", "address": "Nazarbad Main Road, Mysore, Karnataka 570010", "phone": "+91-821-425-6003", "rating": 4.5, "amenities": ["WiFi", "Pool", "Restaurant", "Gym", "AC", "Parking", "Room Service"]},
    {"name": "The Windflower Resort & Spa", "address": "Maharanapratap Road, Nazarbad, Mysore, Karnataka 570010", "phone": "+91-821-425-2204", "rating": 4.1, "amenities": ["WiFi", "Pool", "Restaurant", "Parking"]},
    {"name": "Hotel Mayura Hoysala", "address": "2 Jhansi Lakshmi Bai Road, Mysore, Karnataka 570005", "phone": "+91-821-242-5305", "rating": 3.3, "amenities": ["WiFi", "Parking", "AC"]},
    {"name": "Lalitha Mahal Palace Hotel", "address": "Siddhartha Nagar, Mysore, Karnataka 570011", "phone": "+91-821-247-6306", "rating": 4.6, "amenities": ["WiFi", "Pool", "Restaurant", "Gym", "AC", "Parking", "Room Service"]},
]

_GENERIC_HOTELS: list[dict] = [
    {"name": "Hotel Grand Palace", "address": "M.G. Road, City Centre", "phone": "+91-800-123-4001", "rating": 4.0, "amenities": ["WiFi", "AC", "Restaurant", "Parking"]},
    {"name": "Comfort Inn Residency", "address": "Station Road, Near Bus Stand", "phone": "+91-800-123-4002", "rating": 3.6, "amenities": ["WiFi", "AC", "Parking"]},
    {"name": "Treebo Trend Star Stay", "address": "Ring Road, Sector 12", "phone": "+91-800-123-4003", "rating": 3.9, "amenities": ["WiFi", "AC", "Room Service"]},
    {"name": "OYO Townhouse Elite", "address": "NH-44, Opposite City Mall", "phone": "+91-800-123-4004", "rating": 3.4, "amenities": ["WiFi", "AC"]},
    {"name": "The Heritage Boutique Hotel", "address": "Palace Road, Old Town", "phone": "+91-800-123-4005", "rating": 4.4, "amenities": ["WiFi", "Pool", "Restaurant", "Gym", "Parking", "Room Service"]},
    {"name": "FabHotel Prime Residency", "address": "Link Road, Near Market", "phone": "+91-800-123-4006", "rating": 3.7, "amenities": ["WiFi", "AC", "Parking", "Room Service"]},
]

_DESTINATION_MAP: dict[str, list[dict]] = {
    "coorg": _COORG_HOTELS,
    "karnataka": _COORG_HOTELS,
    "goa": _GOA_HOTELS,
    "mysore": _MYSORE_HOTELS,
    "mysuru": _MYSORE_HOTELS,
}


def _detect_destination(query: str) -> tuple[str, list[dict]]:
    lower = query.lower()
    for key, hotels in _DESTINATION_MAP.items():
        if key in lower:
            return key, hotels
    match = re.search(r"\bin\s+(\w+)", lower)
    dest = match.group(1) if match else "generic"
    return dest, _DESTINATION_MAP.get(dest, _GENERIC_HOTELS)


def _build_mock_hotels(destination: str, raw_hotels: list[dict]) -> list[Hotel]:
    slug = re.sub(r"[^a-z0-9]+", "_", destination.lower()).strip("_")
    result: list[Hotel] = []
    for i, h in enumerate(raw_hotels):
        result.append(Hotel(
            place_id=f"mock_{i}_{slug}",
            name=h["name"],
            phone=h["phone"],
            address=h["address"],
            rating=h["rating"],
            ota_price=None,
            amenities=h["amenities"],
        ))
    return result


def _normalize_phone(raw: str | None) -> str:
    if not raw:
        return ""
    cleaned = re.sub(r"[^\d+]", "", raw)
    return cleaned


def _is_valid_key(api_key: str) -> bool:
    return bool(api_key) and "your-" not in api_key and len(api_key) >= 20


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class GooglePlacesClient:
    """Hotel discovery backed by SerpAPI's google_maps engine.

    Constructor takes a SerpAPI key (the manager now wires
    ``settings.serpapi_api_key`` here). Falls back to curated mock data if
    the key is missing or a request fails.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._real = _is_valid_key(api_key)
        self._client = httpx.AsyncClient(timeout=20.0)
        if self._real:
            logger.info("GooglePlacesClient using SerpAPI google_maps engine")
        else:
            logger.warning("GooglePlacesClient: no valid key, MOCK fallback only")

    # ------------------------------------------------------------------
    @tracing.observe(name="places.search_hotels")
    async def search_hotels(self, query: str) -> list[Hotel]:
        """Return up to 8 Hotel objects with working phone numbers."""
        if self._real:
            try:
                hotels = await self._search_serpapi(query)
                if hotels:
                    return hotels
                logger.warning("SerpAPI returned 0 valid hotels for %r, using mock", query)
            except Exception as exc:
                logger.warning("SerpAPI search failed (%s); falling back to mock", exc)
        return self._search_mock(query)

    async def _search_serpapi(self, query: str) -> list[Hotel]:
        q = query if "hotel" in query.lower() else f"hotels in {query}"
        params = {
            "engine": "google_maps",
            "type": "search",
            "q": q,
            "api_key": self._api_key,
        }
        resp = await self._client.get(SERPAPI_BASE, params=params)
        resp.raise_for_status()
        data = resp.json()
        local = data.get("local_results") or []

        hotels: list[Hotel] = []
        for item in local:
            phone = _normalize_phone(item.get("phone"))
            if not phone:
                continue  # Bolna needs a phone number to call
            place_id = (
                item.get("place_id")
                or item.get("data_id")
                or f"sa_{len(hotels)}"
            )
            hotels.append(Hotel(
                place_id=place_id,
                name=item.get("title") or "Unknown Hotel",
                phone=phone,
                address=item.get("address") or "Address unavailable",
                rating=float(item.get("rating") or 0.0),
                ota_price=None,
                photo_url=item.get("thumbnail"),
                amenities=[],
            ))
            if len(hotels) >= 8:
                break

        logger.info(
            "SerpAPI search_hotels | q=%s | raw=%d | with_phone=%d",
            q, len(local), len(hotels),
        )
        return hotels

    def _search_mock(self, query: str) -> list[Hotel]:
        destination, raw_hotels = _detect_destination(query)
        hotels = _build_mock_hotels(destination, raw_hotels)
        if len(hotels) > 8:
            hotels = random.sample(hotels, 8)
        elif len(hotels) < 6:
            extra_needed = 6 - len(hotels)
            generic = _build_mock_hotels(destination, _GENERIC_HOTELS[:extra_needed])
            hotels.extend(generic)
        logger.warning(
            "MOCK search_hotels | query=%s | destination=%s | n=%d",
            query, destination, len(hotels),
        )
        return hotels

    # ------------------------------------------------------------------
    @tracing.observe(name="places.get_hotel_details")
    async def get_hotel_details(self, place_id: str) -> Hotel:
        """Fetch a single place; falls back to mock lookup on error."""
        if self._real and not place_id.startswith("mock_"):
            try:
                return await self._details_serpapi(place_id)
            except Exception as exc:
                logger.warning(
                    "SerpAPI details failed for %s (%s); using mock", place_id, exc
                )
        return self._details_mock(place_id)

    async def _details_serpapi(self, place_id: str) -> Hotel:
        params = {
            "engine": "google_maps",
            "place_id": place_id,
            "api_key": self._api_key,
        }
        resp = await self._client.get(SERPAPI_BASE, params=params)
        resp.raise_for_status()
        data = resp.json()
        item = data.get("place_results") or {}
        phone = _normalize_phone(item.get("phone")) or "+91-800-000-0000"
        return Hotel(
            place_id=place_id,
            name=item.get("title") or "Unknown Hotel",
            phone=phone,
            address=item.get("address") or "Address unavailable",
            rating=float(item.get("rating") or 0.0),
            ota_price=None,
            photo_url=item.get("thumbnail"),
            amenities=[],
        )

    def _details_mock(self, place_id: str) -> Hotel:
        for dest, raw_hotels in _DESTINATION_MAP.items():
            for i, h in enumerate(raw_hotels):
                slug = re.sub(r"[^a-z0-9]+", "_", dest).strip("_")
                if place_id == f"mock_{i}_{slug}":
                    return Hotel(
                        place_id=place_id,
                        name=h["name"],
                        phone=h["phone"],
                        address=h["address"],
                        rating=h["rating"],
                        ota_price=None,
                        amenities=h["amenities"],
                    )
        for i, h in enumerate(_GENERIC_HOTELS):
            if place_id == f"mock_{i}_generic":
                return Hotel(
                    place_id=place_id,
                    name=h["name"],
                    phone=h["phone"],
                    address=h["address"],
                    rating=h["rating"],
                    ota_price=None,
                    amenities=h["amenities"],
                )
        logger.warning("get_hotel_details | place_id=%s NOT FOUND", place_id)
        return Hotel(
            place_id=place_id,
            name="Unknown Hotel",
            phone="+91-800-000-0000",
            address="Address unavailable",
            rating=3.0,
            ota_price=None,
            amenities=[],
        )

    # ------------------------------------------------------------------
    async def close(self) -> None:
        await self._client.aclose()
