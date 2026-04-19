"""Adapter between Voyageur models and the Facile pipeline.

Converts TravelPreferences -> facile travel_concierge_request format,
runs the full pipeline (planner -> critique -> phase1 hotel discovery),
and converts the facile hotel_shortlist back to Voyageur Hotel objects.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import date

from openai import OpenAI

from app.models import Hotel, TravelPreferences

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Map voyageur group_type -> facile group_type
# ---------------------------------------------------------------------------
_GROUP_MAP = {
    "solo": "solo",
    "couple": "couple",
    "friends": "friends",
    "family": "family",
}

# Map voyageur trip_intent -> facile style weights
_INTENT_TO_WEIGHTS = {
    "relaxation": {
        "sightseeing": 0.3, "adventure": 0.1, "activities": 0.2,
        "nature": 0.7, "culture": 0.3, "food": 0.5,
        "nightlife": 0.1, "wellness": 0.7,
    },
    "sightseeing": {
        "sightseeing": 0.9, "adventure": 0.2, "activities": 0.4,
        "nature": 0.5, "culture": 0.7, "food": 0.5,
        "nightlife": 0.2, "wellness": 0.1,
    },
    "adventure": {
        "sightseeing": 0.3, "adventure": 0.9, "activities": 0.8,
        "nature": 0.7, "culture": 0.2, "food": 0.3,
        "nightlife": 0.3, "wellness": 0.1,
    },
    "mixed": {
        "sightseeing": 0.5, "adventure": 0.4, "activities": 0.5,
        "nature": 0.5, "culture": 0.5, "food": 0.5,
        "nightlife": 0.3, "wellness": 0.3,
    },
    "business": {
        "sightseeing": 0.2, "adventure": 0.0, "activities": 0.1,
        "nature": 0.1, "culture": 0.2, "food": 0.4,
        "nightlife": 0.1, "wellness": 0.2,
    },
}

_PACE_MAP = {
    "slow": "relaxed",
    "medium": "balanced",
    "packed": "fast",
}

_FLEXIBILITY_MAP = {
    "strict": "strict",
    "can_stretch_10_percent": "moderate",
    "flexible": "flexible",
}


def preferences_to_facile_request(prefs: TravelPreferences) -> dict:
    """Convert a Voyageur TravelPreferences to a facile travel_concierge_request.

    This bridges our intake model to the facile planner's expected input format.
    """
    nights = (prefs.check_out - prefs.check_in).days
    adults = prefs.guests - prefs.children if hasattr(prefs, "children") else prefs.guests
    children = getattr(prefs, "children", 0)
    group_type = _GROUP_MAP.get(prefs.group_type or "solo", "couple")

    # Trip style weights
    intent = prefs.trip_intent or "mixed"
    style_weights = _INTENT_TO_WEIGHTS.get(intent, _INTENT_TO_WEIGHTS["mixed"])

    # Budget: facile wants total excluding flights
    total_budget = prefs.budget_total_trip or (prefs.budget_max * nights)

    # Dietary
    dietary = []
    if prefs.food_pref == "veg":
        dietary = ["vegetarian"]
    elif prefs.food_pref == "non-veg":
        dietary = ["non-vegetarian"]

    # Amenities
    amenities_must = [a for a in prefs.amenities if a] or ["wifi"]

    # Star rating
    star_min = prefs.star_rating or 3

    # Budget flexibility
    flex = _FLEXIBILITY_MAP.get(
        prefs.budget_flexibility or "can_stretch_10_percent", "moderate"
    )

    request = {
        "request_id": f"trp_{uuid.uuid4().hex[:8]}",
        "channel": "chat",
        "locale": {
            "language": prefs.language_pref or "english",
            "currency": "INR",
            "timezone": "Asia/Kolkata",
        },
        "traveler_profile": {
            "travelers_count": prefs.guests,
            "group_type": group_type,
            "adults": max(adults, 1),
            "children": children,
            "seniors": getattr(prefs, "seniors", 0),
            "dietary_restrictions": dietary,
        },
        "trip_basics": {
            "origin": {
                "city": prefs.origin_city or "Unknown",
                "country": "India",
            },
            "destination_candidates": [
                {
                    "city_or_region": prefs.destination,
                    "country": "India",  # Will be overridden by planner for intl
                    "flexibility": "fixed",
                }
            ],
            "trip_nights": nights,
            "start_date": prefs.check_in.isoformat(),
            "end_date": prefs.check_out.isoformat(),
            "trip_pace": _PACE_MAP.get(prefs.pace or "medium", "balanced"),
            "trip_style_weights": style_weights,
            "must_visit_places": prefs.must_visit_places or [],
            "must_do_activities": [],
            "places_or_experiences_to_avoid": prefs.must_avoid or [],
        },
        "budget": {
            "total_budget": total_budget,
            "currency": "INR",
            "flights_included": False,
            "hotel_budget_preference_per_night": prefs.budget_max,
            "budget_flexibility": flex,
        },
        "stay_preferences": {
            "accommodation_types": ["hotel"],
            "star_rating_min": star_min,
            "room_count": 1,
            "amenities_must_have": amenities_must,
            "preferred_areas": [],
        },
        "transport_preferences": {
            "intra_city": "cab",
            "max_daily_travel_minutes": 120,
        },
        "question_state": {
            "completed_questions": [],
            "unanswered_critical": [],
            "follow_up_questions": [],
        },
        "planner_config": {
            "itineraries_required": 3,
            "ranking_priorities": ["value_for_money", "comfort_and_ratings"],
            "hotel_sources": ["serpapi"],
            "response_depth": "detailed",
        },
    }

    logger.info(
        "preferences_to_facile_request dest=%s nights=%d budget=%d group=%s",
        prefs.destination, nights, total_budget, group_type,
    )
    return request


def facile_shortlist_to_hotels(shortlist: dict) -> list[Hotel]:
    """Convert a facile hotel_shortlist JSON to a list of Voyageur Hotel objects.

    Preserves the facile scoring and rich metadata in a format the existing
    voyageur approval/calling/report pipeline can consume.
    """
    hotels: list[Hotel] = []
    top_5 = shortlist.get("top_5_hotels", [])

    for h in top_5:
        phone = h.get("phone", "") or ""
        # Skip hotels without phone -- can't call them
        if not phone:
            logger.warning("facile hotel %s has no phone, skipping", h.get("name"))
            continue

        hotel = Hotel(
            place_id=h.get("property_token", f"facile_{h.get('rank', 0)}"),
            name=h.get("name", "Unknown"),
            phone=phone,
            address=h.get("address", h.get("area", "")),
            rating=h.get("rating", 0.0),
            ota_price=int(h.get("nightly_price", 0)) if h.get("nightly_price") else None,
            photo_url=(h.get("photos", [{}])[0].get("url") if h.get("photos") else None),
            amenities=h.get("amenities", []),
            match_score=h.get("scores", {}).get("final_score"),
        )
        hotels.append(hotel)

    logger.info(
        "facile_shortlist_to_hotels converted=%d from_total=%d",
        len(hotels), len(top_5),
    )
    return hotels


class FacilePipelineResult:
    """Full output from the facile pipeline."""
    def __init__(
        self,
        hotels: list[Hotel],
        planner_output: dict,
        critique_review: dict,
        selected_itinerary: dict,
        shortlist: dict,
    ):
        self.hotels = hotels
        self.planner_output = planner_output
        self.critique_review = critique_review
        self.selected_itinerary = selected_itinerary
        self.shortlist = shortlist

    @property
    def itinerary_options(self) -> list[dict]:
        return self.planner_output.get("itinerary_options", [])

    @property
    def recommended_id(self) -> str | None:
        return self.planner_output.get("recommended_itinerary_id")

    @property
    def feasibility(self) -> dict:
        return self.planner_output.get("feasibility_summary", {})

    @property
    def selected_option(self) -> dict | None:
        """The winning itinerary option with day_plan, areas, style, etc."""
        sel_id = self.selected_itinerary.get("selected_itinerary_id")
        for opt in self.itinerary_options:
            if opt.get("itinerary_id") == sel_id:
                return opt
        return self.itinerary_options[0] if self.itinerary_options else None

    def format_itinerary_message(self) -> str:
        """Format the selected itinerary as a chat-friendly message."""
        opt = self.selected_option
        if not opt:
            return "Could not generate an itinerary for this trip."

        title = opt.get("title", "Your Trip")
        style = opt.get("style", "balanced")
        pace = opt.get("trip_pace", "balanced")
        areas = opt.get("areas", [])
        cost = opt.get("estimated_total_trip_cost")
        reasons = opt.get("why_this_option", [])
        day_plan = opt.get("day_plan", [])

        lines = [f"**{title}**", f"Style: {style} | Pace: {pace}"]
        if areas:
            lines.append(f"Areas: {', '.join(areas)}")
        cost_amount: int | None = None
        if isinstance(cost, dict):
            cost_amount = cost.get("amount") or cost.get("value") or cost.get("total")
        elif isinstance(cost, (int, float)):
            cost_amount = int(cost)
        if cost_amount:
            lines.append(f"Estimated total: Rs.{int(cost_amount):,}")
        lines.append("")

        # Day-by-day
        for day in day_plan:
            d_num = day.get("day", "?")
            zone = day.get("zone", "")
            theme = day.get("theme", "")
            anchor = day.get("major_anchor", "")
            secondaries = day.get("secondary_items", [])

            day_line = f"**Day {d_num}** — {zone}"
            if theme:
                day_line += f" ({theme})"
            lines.append(day_line)
            if anchor:
                lines.append(f"  Main: {anchor}")
            for s in secondaries:
                lines.append(f"  Also: {s}")

        lines.append("")
        if reasons:
            lines.append("**Why this plan:**")
            for r in reasons:
                lines.append(f"- {r}")

        return "\n".join(lines)


async def run_facile_pipeline(
    prefs: TravelPreferences,
    openai_api_key: str,
    serpapi_key: str | None = None,
) -> FacilePipelineResult:
    """Run the full facile pipeline: planner -> critique -> hotel discovery.

    Returns a FacilePipelineResult with all pipeline outputs.
    """
    import asyncio

    # Facile uses sync OpenAI client
    from app.facile.travel_concierge_planner.agent import (
        PlannerAgent, PlannerConfig, pick_selected_itinerary,
    )
    from app.facile.travel_concierge_critique_refine.agent import (
        CritiqueRefineAgent, pick_selected_itinerary_from_review,
    )
    from app.facile.travel_concierge_phase1.pipeline import (
        SerpApiClient, MockSerpApiClient, Phase1Config, run_phase1_shortlist,
    )

    logger.info("facile pipeline starting dest=%s", prefs.destination)
    t0 = time.time()

    # 1. Convert preferences
    facile_request = preferences_to_facile_request(prefs)

    # 2. Run planner (sync, so run in executor)
    client = OpenAI(api_key=openai_api_key)
    planner = PlannerAgent(client, PlannerConfig(model="gpt-5.4", max_attempts=2))

    loop = asyncio.get_event_loop()
    planner_output = await loop.run_in_executor(
        None, planner.create_plan, facile_request
    )
    logger.info("facile planner done options=%d", len(planner_output.get("itinerary_options", [])))

    # 3. Run critique/refine (sync, in executor)
    critic = CritiqueRefineAgent()
    review = await loop.run_in_executor(
        None, critic.review, facile_request, planner_output
    )
    logger.info("facile critique done top_rec=%s", review.get("review_summary", {}).get("top_recommendation_itinerary_id"))

    # 4. Pick selected itinerary from critique
    selected = pick_selected_itinerary_from_review(review)
    if not selected:
        # Fallback: pick from planner directly
        rec_id = planner_output.get("recommended_itinerary_id")
        selected = pick_selected_itinerary(planner_output, rec_id)
    logger.info("facile selected itinerary id=%s", selected.get("selected_itinerary_id"))

    # 5. Run Phase 1 hotel discovery
    if serpapi_key:
        serp_client = SerpApiClient(api_key=serpapi_key)
    else:
        serp_client = MockSerpApiClient()
        logger.warning("No SERPAPI_KEY -- using mock hotel data")

    phase1_config = Phase1Config(
        provisional_cutoff=12,
        review_snippets_per_hotel=6,
        photos_per_hotel=4,
        include_social_proof_search=False,
    )
    shortlist = await loop.run_in_executor(
        None, run_phase1_shortlist, selected, serp_client, phase1_config
    )

    elapsed = time.time() - t0
    hotel_count = len(shortlist.get("top_5_hotels", []))
    logger.info("facile pipeline done hotels=%d elapsed=%.1fs", hotel_count, elapsed)

    # 6. Convert to voyageur Hotel objects
    hotels = facile_shortlist_to_hotels(shortlist)
    return FacilePipelineResult(
        hotels=hotels,
        planner_output=planner_output,
        critique_review=review,
        selected_itinerary=selected,
        shortlist=shortlist,
    )
