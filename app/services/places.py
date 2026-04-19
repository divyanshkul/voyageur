# MOCK IMPLEMENTATION - Will be replaced with real Google Places API by teammate
# Interface must stay exactly the same: GooglePlacesClient with search_hotels() and get_hotel_details()
"""Google Places API client (Phase 2a).

Initially a MOCK implementation returning realistic fake Indian hotel data.
A teammate will replace this with the real Google Places API (New) Text Search
integration.  The interface (GooglePlacesClient) is LOCKED.
"""

import logging
import random
import re

from app.models import Hotel

logger = logging.getLogger(__name__)

MOCK_MODE = True

# ---------------------------------------------------------------------------
# Mock hotel data per destination
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
    """Parse destination from query and return matching hotel list."""
    lower = query.lower()
    for key, hotels in _DESTINATION_MAP.items():
        if key in lower:
            return key, hotels
    # Try "in {destination}" pattern
    match = re.search(r"\bin\s+(\w+)", lower)
    dest = match.group(1) if match else "generic"
    return dest, _DESTINATION_MAP.get(dest, _GENERIC_HOTELS)


def _build_mock_hotels(destination: str, raw_hotels: list[dict]) -> list[Hotel]:
    """Convert raw dicts into Hotel model instances with mock place_ids."""
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


class GooglePlacesClient:
    """Mock Google Places client returning realistic fake Indian hotel data.

    The real implementation will swap in without changing method signatures.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        logger.warning("GooglePlacesClient initialized (MOCK MODE)")

    async def search_hotels(self, query: str) -> list[Hotel]:
        """Return 6-8 realistic fake Hotel objects based on the query."""
        destination, raw_hotels = _detect_destination(query)
        hotels = _build_mock_hotels(destination, raw_hotels)

        # Return 6-8 results (trim if needed, pad from generic if too few)
        if len(hotels) > 8:
            hotels = random.sample(hotels, 8)
        elif len(hotels) < 6:
            extra_needed = 6 - len(hotels)
            generic = _build_mock_hotels(destination, _GENERIC_HOTELS[:extra_needed])
            hotels.extend(generic)

        logger.warning(
            "MOCK search_hotels | query=%s | destination=%s | returning %d results",
            query, destination, len(hotels),
        )
        return hotels

    async def get_hotel_details(self, place_id: str) -> Hotel:
        """Return a mock hotel matching the given place_id."""
        # Search through all hotel sets
        for dest, raw_hotels in _DESTINATION_MAP.items():
            for i, h in enumerate(raw_hotels):
                slug = re.sub(r"[^a-z0-9]+", "_", dest).strip("_")
                if place_id == f"mock_{i}_{slug}":
                    logger.warning("MOCK get_hotel_details | place_id=%s | found=%s", place_id, h["name"])
                    return Hotel(
                        place_id=place_id,
                        name=h["name"],
                        phone=h["phone"],
                        address=h["address"],
                        rating=h["rating"],
                        ota_price=None,
                        amenities=h["amenities"],
                    )
        # Fallback: check generic
        for i, h in enumerate(_GENERIC_HOTELS):
            if place_id == f"mock_{i}_generic":
                logger.warning("MOCK get_hotel_details | place_id=%s | found=%s", place_id, h["name"])
                return Hotel(
                    place_id=place_id,
                    name=h["name"],
                    phone=h["phone"],
                    address=h["address"],
                    rating=h["rating"],
                    ota_price=None,
                    amenities=h["amenities"],
                )

        logger.warning("MOCK get_hotel_details | place_id=%s | NOT FOUND, returning placeholder", place_id)
        return Hotel(
            place_id=place_id,
            name="Unknown Hotel",
            phone="+91-800-000-0000",
            address="Address unavailable",
            rating=3.0,
            ota_price=None,
            amenities=[],
        )

    async def close(self) -> None:
        """No-op for mock client."""
        pass
