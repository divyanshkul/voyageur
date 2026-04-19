# MOCK IMPLEMENTATION - Will be replaced with real SerpAPI by teammate
# Interface must stay exactly the same: SerpAPIClient with get_ota_prices() and match_hotel_price()
"""SerpAPI OTA pricing client (Phase 2b).

Initially a MOCK implementation returning realistic OTA prices in INR.
A teammate will replace this with the real SerpAPI Google Hotels engine.
The interface (SerpAPIClient) is LOCKED.  The match_hotel_price() fuzzy
matcher is real code (not mock).
"""

import logging
from datetime import date

from thefuzz import fuzz

from app.models import Hotel  # noqa: F401 – kept for interface parity

logger = logging.getLogger(__name__)

MOCK_MODE = True

# ---------------------------------------------------------------------------
# Mock OTA price data per destination
# Names intentionally have slight variations to test fuzzy matching.
# ---------------------------------------------------------------------------

_COORG_OTA_PRICES: dict[str, int] = {
    "Coorg Wilderness Resort & Spa": 8500,
    "Kaveri Residency Madikeri": 2200,
    "Coorg Heritage Inn Madikeri": 3000,
    "Club Mahindra Coorg": 6500,
    "Tamara Coorg Resort": 11000,
    "Zostel Coorg Hostel": 1500,
    "Meriyanda Nature Lodge Coorg": 4200,
    # Extra entries that don't match (to test fuzzy matching robustness)
    "Silver Brook Resort Coorg": 5800,
    "Kodagu Valley Resort": 4500,
}

_GOA_OTA_PRICES: dict[str, int] = {
    "Beach House Calangute Goa": 5200,
    "Hotel Mandovi": 3400,
    "Leela Goa Cavelossim": 11500,
    "Zostel Anjuna Goa": 1600,
    "Palolem Beach Resort Goa": 3800,
    "Park Calangute Goa": 7200,
    # Extra non-matching entries
    "Taj Fort Aguada Resort": 14000,
    "Alila Diwa Goa": 9200,
}

_MYSORE_OTA_PRICES: dict[str, int] = {
    "Royal Orchid Metropole": 5500,
    "Dasaprakash Hotel Mysore": 1800,
    "Radisson Blu Mysore": 7000,
    "Windflower Resort Mysore": 4800,
    "Hotel Mayura Hoysala Mysore": 1600,
    "Lalitha Mahal Palace": 9500,
    # Extra non-matching entries
    "Fortune JP Palace Mysore": 4200,
    "Southern Star Mysore": 3500,
}

_GENERIC_OTA_PRICES: dict[str, int] = {
    "Grand Palace Hotel": 4000,
    "Comfort Inn": 2500,
    "Treebo Star Stay": 2200,
    "OYO Townhouse": 1800,
    "Heritage Boutique Hotel": 6500,
    "FabHotel Residency": 2000,
    "Hotel Sunshine Inn": 3200,
}

_DEST_PRICE_MAP: dict[str, dict[str, int]] = {
    "coorg": _COORG_OTA_PRICES,
    "karnataka": _COORG_OTA_PRICES,
    "goa": _GOA_OTA_PRICES,
    "mysore": _MYSORE_OTA_PRICES,
    "mysuru": _MYSORE_OTA_PRICES,
}


class SerpAPIClient:
    """Mock SerpAPI client returning realistic OTA prices in INR.

    The real implementation will swap in without changing method signatures.
    match_hotel_price() is real (not mock) -- pure-Python fuzzy matching.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        logger.warning("SerpAPIClient initialized (MOCK MODE)")

    async def get_ota_prices(
        self,
        destination: str,
        check_in: date,
        check_out: date,
    ) -> dict[str, int]:
        """Return a dict mapping hotel names to realistic OTA prices (INR)."""
        lower = destination.lower()
        prices: dict[str, int] = _GENERIC_OTA_PRICES.copy()

        for key, dest_prices in _DEST_PRICE_MAP.items():
            if key in lower:
                prices = dest_prices.copy()
                break

        logger.warning(
            "MOCK get_ota_prices | destination=%s | check_in=%s | check_out=%s | returning %d prices",
            destination, check_in, check_out, len(prices),
        )
        return prices

    def match_hotel_price(
        self,
        hotel_name: str,
        ota_results: dict[str, int],
    ) -> int | None:
        """REAL IMPLEMENTATION -- fuzzy match hotel_name against OTA result keys.

        Uses thefuzz token_sort_ratio with a threshold of 80.
        Returns the best-match price, or None if no match above threshold.
        """
        best_score = 0
        best_name: str | None = None
        best_price: int | None = None

        for ota_name, price in ota_results.items():
            score = fuzz.token_sort_ratio(hotel_name.lower(), ota_name.lower())
            if score > best_score:
                best_score = score
                best_name = ota_name
                best_price = price

        if best_score >= 80:
            logger.info(
                "match_hotel_price | hotel=%s | matched_to=%s | score=%d | price=%s",
                hotel_name, best_name, best_score, best_price,
            )
            return best_price

        logger.info(
            "match_hotel_price | hotel=%s | no match above threshold (best=%s, score=%d)",
            hotel_name, best_name, best_score,
        )
        return None

    async def close(self) -> None:
        """No-op for mock client."""
        pass
