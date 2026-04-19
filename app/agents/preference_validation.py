"""Preference validation and query building (Phase 1c).

Validates extracted preferences, applies sensible defaults, normalises Indian
destination names, and builds Google Places search queries.
Pure Python -- no external API calls.
"""

from __future__ import annotations

import logging
from datetime import date

from app.models import TravelPreferences

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Destination alias map (case-insensitive)
# ---------------------------------------------------------------------------
_DESTINATION_ALIASES: dict[str, str] = {
    "bangalore": "Bengaluru, Karnataka",
    "bengaluru": "Bengaluru, Karnataka",
    "coorg": "Coorg, Karnataka",
    "kodagu": "Coorg, Karnataka",
    "ooty": "Ooty, Tamil Nadu",
    "goa": "Goa",
    "mysore": "Mysuru, Karnataka",
    "mysuru": "Mysuru, Karnataka",
    "pondicherry": "Puducherry",
    "bombay": "Mumbai, Maharashtra",
    "mumbai": "Mumbai, Maharashtra",
    "madras": "Chennai, Tamil Nadu",
    "chennai": "Chennai, Tamil Nadu",
    "calcutta": "Kolkata, West Bengal",
    "kolkata": "Kolkata, West Bengal",
    "alleppey": "Alappuzha, Kerala",
    "alappuzha": "Alappuzha, Kerala",
    "cochin": "Kochi, Kerala",
    "kochi": "Kochi, Kerala",
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_preferences(prefs: TravelPreferences) -> tuple[bool, list[str]]:
    """Validate extracted preferences.

    Returns:
        ``(True, [])`` when valid.
        ``(False, [list of human-readable issues])`` otherwise.
    """
    logger.debug("validate_preferences called")
    issues: list[str] = []

    today = date.today()

    if not prefs.destination or not prefs.destination.strip():
        issues.append("destination is empty")

    if prefs.check_in < today:
        issues.append("check_in is in the past")

    if prefs.check_out <= prefs.check_in:
        issues.append("check_out must be after check_in")

    if prefs.budget_max <= 0:
        issues.append("budget_max must be greater than 0")

    if prefs.budget_min is not None and prefs.budget_min >= prefs.budget_max:
        issues.append("budget_min must be less than budget_max")

    if prefs.guests < 1:
        issues.append("guests must be at least 1")

    valid = len(issues) == 0
    if valid:
        logger.info("validate_preferences passed")
    else:
        logger.info("validate_preferences failed", extra={"issues": issues})

    return valid, issues


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

def apply_defaults(prefs: TravelPreferences) -> TravelPreferences:
    """Fill in sensible defaults for optional fields the user didn't specify."""
    logger.debug("apply_defaults called")

    updates: dict = {}
    applied: list[str] = []

    if prefs.star_rating is None:
        updates["star_rating"] = 3
        applied.append("star_rating=3")

    # food_pref, smoking, alcohol, language_pref already have model-level
    # defaults ("both", False, False, "english") so they are always set.
    # We only log if the value is still the model default -- meaning the user
    # didn't explicitly choose.  No override needed; the model defaults are
    # exactly what the spec asks for.

    if not prefs.amenities:
        updates["amenities"] = ["wifi"]
        applied.append("amenities=['wifi']")

    if applied:
        logger.info("apply_defaults applied", extra={"defaults": applied})
    else:
        logger.debug("apply_defaults no changes needed")

    return prefs.model_copy(update=updates) if updates else prefs


# ---------------------------------------------------------------------------
# Destination normalisation
# ---------------------------------------------------------------------------

def normalize_destination(destination: str) -> str:
    """Normalise common Indian destination aliases.

    Case-insensitive lookup.  Returns the input unchanged if no alias matches.
    """
    key = destination.strip().lower()
    normalised = _DESTINATION_ALIASES.get(key, destination)

    if normalised != destination:
        logger.info(
            "normalize_destination mapped",
            extra={"original": destination, "normalised": normalised},
        )
    return normalised


# ---------------------------------------------------------------------------
# Search query builder
# ---------------------------------------------------------------------------

def build_search_query(prefs: TravelPreferences) -> str:
    """Build a Google Places text-search query from preferences."""
    parts: list[str] = []

    # Budget tier prefix
    if prefs.budget_max < 3000:
        parts.append("budget")
    elif prefs.budget_max > 10000:
        parts.append("luxury")

    # Star rating
    if prefs.star_rating:
        parts.append(f"{prefs.star_rating}+ star")

    parts.append(f"hotels in {prefs.destination}")

    # Amenities
    if "pool" in prefs.amenities:
        parts.append("with swimming pool")

    query = " ".join(parts)
    logger.info("build_search_query", extra={"query": query})
    return query
