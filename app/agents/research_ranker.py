"""Hotel ranking algorithm (Phase 2c).

Pure-Python ranking logic -- no external API calls.  Scores hotels on rating,
budget fit, amenity match, OTA-price availability, and rating quality, then
returns the top 8.
"""

import logging

from thefuzz import fuzz

from app.models import Hotel, TravelPreferences

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def rank_hotels(
    hotels: list[Hotel],
    prefs: TravelPreferences,
    ota_prices: dict[str, int],
) -> list[Hotel]:
    """Enrich, filter, score and rank hotels.  Returns top 8."""
    input_count = len(hotels)

    # 1. Enrich each hotel's ota_price via fuzzy matching
    enriched: list[Hotel] = []
    for h in hotels:
        matched_price = _fuzzy_match_price(h.name, ota_prices)
        if matched_price is not None:
            h = h.model_copy(update={"ota_price": matched_price})
        enriched.append(h)

    # 2. Filter out hotels without phone or wildly over budget
    filtered: list[Hotel] = []
    for h in enriched:
        if not h.phone:
            logger.debug("rank_hotels | filtered out (no phone): %s", h.name)
            continue
        if h.ota_price is not None and h.ota_price > prefs.budget_max * 1.5:
            logger.debug(
                "rank_hotels | filtered out (price %d > budget_max*1.5 %d): %s",
                h.ota_price, prefs.budget_max * 1.5, h.name,
            )
            continue
        filtered.append(h)

    # 3. Score and attach match_score
    scored: list[Hotel] = []
    for h in filtered:
        score = calculate_match_score(h, prefs)
        scored.append(h.model_copy(update={"match_score": score}))

    # 4. Sort descending and take top 8
    scored.sort(key=lambda h: h.match_score or 0.0, reverse=True)
    result = scored[:8]

    top_score = result[0].match_score if result else 0.0
    logger.info(
        "rank_hotels | input=%d | after_filter=%d | returned=%d | top_score=%.3f",
        input_count, len(filtered), len(result), top_score or 0.0,
    )
    return result


def calculate_match_score(hotel: Hotel, prefs: TravelPreferences) -> float:
    """Score a single hotel against preferences.  Returns 0.0 - 1.0."""

    # Rating score (weight 0.3)
    rating_score = hotel.rating / 5.0

    # Budget fit (weight 0.3)
    if hotel.ota_price is not None:
        if hotel.ota_price > prefs.budget_max * 1.2:
            budget_score = 0.0  # hard penalty
        else:
            budget_score = max(
                0.0,
                1.0 - abs(hotel.ota_price - prefs.budget_max) / prefs.budget_max,
            )
    else:
        budget_score = 0.5  # neutral when no price

    # Amenity match (weight 0.2)
    if not prefs.amenities:
        amenity_score = 1.0
    else:
        hotel_amenities_lower = [a.lower() for a in hotel.amenities]
        matched = 0
        for wanted in prefs.amenities:
            wanted_lower = wanted.lower()
            if any(wanted_lower in ha for ha in hotel_amenities_lower):
                matched += 1
        amenity_score = matched / len(prefs.amenities)

    # Has OTA price (weight 0.1)
    has_price_score = 1.0 if hotel.ota_price is not None else 0.0

    # High rating bonus (weight 0.1)
    if hotel.rating >= 4.0:
        rating_bonus = 1.0
    elif hotel.rating >= 3.5:
        rating_bonus = 0.5
    else:
        rating_bonus = 0.0

    # Weighted sum
    final = (
        0.3 * rating_score
        + 0.3 * budget_score
        + 0.2 * amenity_score
        + 0.1 * has_price_score
        + 0.1 * rating_bonus
    )
    final = max(0.0, min(1.0, final))

    logger.debug(
        "calculate_match_score | hotel=%s | rating=%.2f budget=%.2f amenity=%.2f "
        "has_price=%.2f bonus=%.2f | final=%.3f",
        hotel.name, rating_score, budget_score, amenity_score,
        has_price_score, rating_bonus, final,
    )
    return final


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fuzzy_match_price(hotel_name: str, ota_prices: dict[str, int]) -> int | None:
    """Fuzzy match hotel name against OTA price keys.  Threshold >= 80."""
    best_score = 0
    best_price: int | None = None
    best_name: str | None = None

    for ota_name, price in ota_prices.items():
        score = fuzz.token_sort_ratio(hotel_name.lower(), ota_name.lower())
        if score > best_score:
            best_score = score
            best_name = ota_name
            best_price = price

    if best_score >= 80:
        logger.debug(
            "_fuzzy_match_price | hotel=%s | matched=%s | score=%d",
            hotel_name, best_name, best_score,
        )
        return best_price

    logger.debug(
        "_fuzzy_match_price | hotel=%s | no match (best=%s, score=%d)",
        hotel_name, best_name, best_score,
    )
    return None
