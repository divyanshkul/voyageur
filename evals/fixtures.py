"""Synthetic fixtures for offline eval cases.

Pure builders for Hotel / CallResult / TravelPreferences objects so eval
cases can exercise `rank_hotels`, `compare_prices`, and `ReportAgent` without
hitting Google Places, SerpAPI, or Bolna.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.models import (
    CallResult,
    Hotel,
    TravelPreferences,
)


def hotel(
    name: str,
    *,
    place_id: str | None = None,
    phone: str = "+911234567890",
    rating: float = 4.0,
    ota_price: int | None = None,
    amenities: list[str] | None = None,
    address: str = "Somewhere, India",
) -> Hotel:
    return Hotel(
        place_id=place_id or f"pid_{name.lower().replace(' ', '_')}",
        name=name,
        phone=phone,
        address=address,
        rating=rating,
        ota_price=ota_price,
        amenities=amenities or [],
    )


def call_result(
    h: Hotel,
    *,
    status: str = "completed",
    direct_price: int | None = None,
    availability: bool | None = True,
    transcript: str | None = "Synthetic transcript for eval.",
) -> CallResult:
    return CallResult(
        hotel=h,
        status=status,  # type: ignore[arg-type]
        direct_price=direct_price,
        availability=availability,
        transcript=transcript,
    )


def preferences(
    *,
    destination: str = "Coorg, Karnataka",
    nights: int = 3,
    start_offset_days: int = 30,
    budget_max: int = 8000,
    budget_min: int | None = 4000,
    guests: int = 2,
    amenities: list[str] | None = None,
    star_rating: int | None = 4,
) -> TravelPreferences:
    ci = date.today() + timedelta(days=start_offset_days)
    co = ci + timedelta(days=nights)
    return TravelPreferences(
        destination=destination,
        check_in=ci,
        check_out=co,
        budget_max=budget_max,
        budget_min=budget_min,
        guests=guests,
        amenities=amenities or ["wifi"],
        star_rating=star_rating,
    )


def preferences_from_dict(payload: dict[str, Any]) -> TravelPreferences:
    """Build TravelPreferences from a JSON-ish dict, resolving relative dates.

    Any string value of the form ``{today+Nd}`` (e.g. ``{today+30d}``) is
    replaced with today+N days in ISO format.
    """
    resolved: dict[str, Any] = {}
    for k, v in payload.items():
        if isinstance(v, str) and v.startswith("{today") and v.endswith("}"):
            inner = v[1:-1].replace("today", "").strip()  # "+30d"
            sign = 1 if inner.startswith("+") else -1
            n = int("".join(ch for ch in inner if ch.isdigit()))
            resolved[k] = (date.today() + timedelta(days=sign * n)).isoformat()
        else:
            resolved[k] = v
    return TravelPreferences(**resolved)


def hotels_from_list(items: list[dict[str, Any]]) -> list[Hotel]:
    return [hotel(**it) for it in items]


def call_results_from_list(items: list[dict[str, Any]]) -> list[CallResult]:
    results: list[CallResult] = []
    for it in items:
        h_payload = it.pop("hotel")
        results.append(call_result(hotel(**h_payload), **it))
    return results
