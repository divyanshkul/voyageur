from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator


ROOT_DIR = Path(__file__).resolve().parents[1]  # app/facile/
PLANNER_SCHEMA_PATH = ROOT_DIR / "schemas" / "planner_itinerary_options.schema.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        datetime.fromisoformat(value)
        return value
    except ValueError:
        return None


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    safe = _safe_date(value)
    if not safe:
        return None
    return datetime.fromisoformat(safe).date()


def _extract_message_text(message: Any) -> str:
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: List[str] = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") in {"text", "output_text"}:
                    chunks.append(str(part.get("text", "")))
                continue
            text = getattr(part, "text", None)
            if text:
                chunks.append(str(text))
        return "".join(chunks)
    if content is None:
        return ""
    return str(content)


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)
        f.write("\n")


def _dedupe_strings(values: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        item = str(value).strip()
        if not item:
            continue
        low = item.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(item)
    return out


def _infer_primary_goal(weights: Dict[str, float]) -> Tuple[str, List[str]]:
    if not weights:
        return "balanced_exploration", ["light sightseeing"]

    mapped = {
        "relaxation": float(weights.get("wellness", 0)),
        "sightseeing": float(weights.get("sightseeing", 0)),
        "adventure": float(weights.get("adventure", 0)),
        "activities": float(weights.get("activities", 0)),
        "nature": float(weights.get("nature", 0)),
        "culture": float(weights.get("culture", 0)),
        "food": float(weights.get("food", 0)),
        "nightlife": float(weights.get("nightlife", 0)),
        "romantic": (float(weights.get("nature", 0)) + float(weights.get("wellness", 0))) / 2.0,
    }
    ranked = sorted(mapped.items(), key=lambda kv: kv[1], reverse=True)
    primary = ranked[0][0]
    secondary = [name for name, score in ranked[1:] if score > 0][:2]
    return primary, secondary


def _infer_planning_style(trip_pace: str) -> Tuple[str, str, str]:
    pace = (trip_pace or "balanced").lower()
    if pace == "relaxed":
        return "slow_and_comfortable", "slow", "low_to_moderate"
    if pace == "fast":
        return "dense_and_experiential", "fast", "high"
    return "balanced", "medium", "moderate"


def _infer_spend_priority(ranking_priorities: List[str]) -> str:
    ranked = [str(x).strip().lower() for x in ranking_priorities if str(x).strip()]
    if "luxury" in ranked:
        return "comfort_first"
    if "budget" in ranked or "value" in ranked:
        return "balanced"
    return "balanced"


def _canonicalize_preferences(preferences: Dict[str, Any]) -> Dict[str, Any]:
    trip = preferences.get("trip_basics", {})
    traveler = preferences.get("traveler_profile", {})
    budget = preferences.get("budget", {})
    stay = preferences.get("stay_preferences", {})
    transport = preferences.get("transport_preferences", {})
    planner_cfg = preferences.get("planner_config", {})

    dest_candidates = trip.get("destination_candidates", [])
    first_dest = dest_candidates[0] if dest_candidates else {}
    destination_query = first_dest.get("city_or_region") or ""
    destination_country = first_dest.get("country") or ""
    destination_flexibility = first_dest.get("flexibility") or "open"

    must_places = trip.get("must_visit_places", []) or []
    preferred_areas = stay.get("preferred_areas", []) or []
    specific_places = _dedupe_strings(must_places + preferred_areas)

    start_date = _safe_date(trip.get("start_date"))
    end_date = _safe_date(trip.get("end_date"))
    duration_nights = int(trip.get("trip_nights", 0)) if trip.get("trip_nights") else 0
    if duration_nights <= 0 and start_date and end_date:
        start = _parse_iso_date(start_date)
        end = _parse_iso_date(end_date)
        if start and end:
            duration_nights = max((end - start).days, 1)

    trip_weights = trip.get("trip_style_weights", {}) or {}
    primary_goal, secondary_goals = _infer_primary_goal(trip_weights)
    planning_style, pace, energy_level = _infer_planning_style(trip.get("trip_pace", "balanced"))

    budget_flex = str(budget.get("budget_flexibility", "moderate")).lower()
    budget_flex_map = {
        "strict": "strict",
        "moderate": "can_stretch_10_percent",
        "flexible": "flexible",
    }
    spend_priority = _infer_spend_priority(planner_cfg.get("ranking_priorities", []))

    star_min = int(stay.get("star_rating_min", 3))
    hotel_class_pref = [star_min, min(star_min + 1, 5)]

    location_preferences = _dedupe_strings(preferred_areas)
    if not location_preferences:
        location_preferences = ["scenic", "quiet"]

    canonical = {
        "trip_request_id": preferences.get("request_id", ""),
        "source_mode": preferences.get("channel", "chat"),
        "conversation_state": {
            "missing_slots": [],
            "clarifications_needed": [],
            "confidence": 0.9,
        },
        "traveler_profile": {
            "group_type": traveler.get("group_type", "mixed"),
            "adults": int(traveler.get("adults", max(int(traveler.get("travelers_count", 1)), 1))),
            "children": int(traveler.get("children", 0)),
            "seniors": int(traveler.get("seniors", 0)),
        },
        "origin": {
            "city": (trip.get("origin") or {}).get("city", ""),
            "country": (trip.get("origin") or {}).get("country", ""),
        },
        "destination": {
            "query": destination_query,
            "is_fixed": destination_flexibility == "fixed",
            "country": destination_country,
            "specific_places": specific_places,
            "flexibility": (
                "low"
                if destination_flexibility == "fixed"
                else ("medium" if destination_flexibility == "flexible" else "high")
            ),
        },
        "dates": {
            "mode": "fixed" if start_date and end_date else "flexible",
            "start_date": start_date,
            "end_date": end_date,
            "duration_nights": duration_nights,
        },
        "trip_intent": {
            "primary_goal": primary_goal,
            "secondary_goals": secondary_goals,
            "planning_style": planning_style,
            "pace": pace,
            "energy_level": energy_level,
        },
        "budget": {
            "total_excl_flights": float(budget.get("total_budget", 0)),
            "currency": budget.get("currency", (preferences.get("locale") or {}).get("currency", "INR")),
            "flexibility": budget_flex_map.get(budget_flex, "can_stretch_10_percent"),
            "spend_priority": spend_priority,
        },
        "stay_preferences": {
            "property_types": stay.get("accommodation_types", ["hotel"]),
            "hotel_class_preference": hotel_class_pref,
            "location_preferences": location_preferences,
            "must_have_amenities": stay.get("amenities_must_have", []),
            "nice_to_have_amenities": [],
            "deal_preference": "best_value",
        },
        "mobility_and_transport": {
            "walking_tolerance_minutes": 20,
            "transport_preference": (
                "cabs_preferred" if transport.get("intra_city") == "cabs" else "mixed"
            ),
            "mobility_constraints": traveler.get("mobility_or_accessibility_needs", []),
        },
        "food_preferences": {
            "dietary_preferences": traveler.get("dietary_restrictions", []),
            "restaurant_interest": "medium",
            "special_food_notes": traveler.get("allergies_or_health_notes", []),
        },
        "trip_constraints": {
            "must_visit_places": trip.get("must_visit_places", []),
            "must_avoid": trip.get("places_or_experiences_to_avoid", []),
            "special_requests": [],
        },
        "call_preferences": {
            "preferred_languages_for_vendor_calls": traveler.get("languages_spoken", []),
        },
    }
    return canonical


def _missing_critical_slots(canonical: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    destination = canonical.get("destination", {})
    dates = canonical.get("dates", {})
    traveler = canonical.get("traveler_profile", {})
    budget = canonical.get("budget", {})
    trip_intent = canonical.get("trip_intent", {})

    if not destination.get("query"):
        missing.append("destination")
    if not dates.get("duration_nights"):
        missing.append("trip_duration")
    if not traveler.get("group_type"):
        missing.append("group_type")
    if float(budget.get("total_excl_flights", 0)) <= 0:
        missing.append("budget")
    if not trip_intent.get("primary_goal"):
        missing.append("trip_style")
    return missing


def _build_follow_up_questions(missing_slots: List[str]) -> List[Dict[str, str]]:
    templates = {
        "destination": (
            "fq_destination",
            "Which destination city or region are you targeting?",
            "Planner cannot produce location-aware options without a destination.",
        ),
        "trip_duration": (
            "fq_duration",
            "How many nights do you want for this trip?",
            "Trip pacing and feasibility depend on duration.",
        ),
        "group_type": (
            "fq_group_type",
            "Who is traveling: solo, couple, friends, or family?",
            "Trip style and density depend on traveler type.",
        ),
        "budget": (
            "fq_budget",
            "What is your total trip budget excluding flights?",
            "Planner needs budget boundaries to avoid unrealistic plans.",
        ),
        "trip_style": (
            "fq_style",
            "Would you prefer relaxed, balanced, or activity-heavy planning?",
            "Style preference is required to generate distinct itinerary options.",
        ),
    }
    out = []
    for slot in missing_slots:
        if slot in templates:
            ident, prompt, reason = templates[slot]
            out.append(
                {
                    "id": ident,
                    "prompt": prompt,
                    "reason": reason,
                }
            )
    return out


def _estimate_destination_cost_floor(
    destination_query: str,
    hotel_class_preference: List[int],
    location_preferences: List[str],
) -> float:
    class_floor = min(hotel_class_preference) if hotel_class_preference else 3
    base = 3200 + (class_floor * 1150)
    query = destination_query.lower()

    if "bali" in query:
        base += 700
    if "tokyo" in query or "japan" in query:
        base += 2800
    if "paris" in query or "london" in query:
        base += 3400

    prefs = " ".join(location_preferences).lower()
    if "beach" in prefs:
        base += 900
    if "quiet" in prefs:
        base += 300
    return float(base)


def _build_budget_model(canonical: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    budget = canonical["budget"]
    stay = canonical["stay_preferences"]
    destination = canonical["destination"]
    nights = max(int(canonical["dates"].get("duration_nights", 1)), 1)
    total_budget = float(budget.get("total_excl_flights", 0))

    spend_priority = str(budget.get("spend_priority", "balanced")).lower()
    hotel_share_target = 0.45
    if spend_priority == "comfort_first":
        hotel_share_target = 0.52
    if spend_priority == "budget_first":
        hotel_share_target = 0.38

    hotel_budget_total_target = total_budget * hotel_share_target
    hotel_budget_per_night_target = max(hotel_budget_total_target / nights, 1)
    hotel_budget_per_night_soft_max = round(hotel_budget_per_night_target * 1.25, 2)
    hotel_budget_per_night_hard_max = round(hotel_budget_per_night_target * 1.5, 2)

    destination_floor = _estimate_destination_cost_floor(
        destination_query=destination.get("query", ""),
        hotel_class_preference=stay.get("hotel_class_preference", []),
        location_preferences=stay.get("location_preferences", []),
    )

    ratio = hotel_budget_per_night_target / max(destination_floor, 1)
    if ratio >= 1.12:
        status = "feasible"
        comment = "Budget is feasible for the requested style with comfortable hotel choices."
        adjustments = []
    elif ratio >= 0.92:
        status = "feasible_with_tradeoffs"
        comment = (
            "Trip is feasible with tradeoffs. Premium micro-areas or peak dates can push hotel costs up."
        )
        adjustments = [
            "choose best-value 3-4 star stays",
            "avoid over-premium micro-areas for all nights",
            "keep paid activities to selected anchors",
        ]
    elif ratio >= 0.78:
        status = "stretched"
        comment = "Budget is stretched for this destination and preference mix."
        adjustments = [
            "reduce one paid activity day",
            "pick one lower-cost stay area",
            "tighten transport hops to reduce cab spend",
        ]
    else:
        status = "not_recommended"
        comment = "Budget is likely too low for this destination and style without major compromises."
        adjustments = [
            "increase total budget",
            "shorten trip by one night",
            "reduce hotel class preference",
        ]

    budget_model = {
        "total_budget_excl_flights": round(total_budget, 2),
        "hotel_budget_share_target": round(hotel_share_target, 2),
        "hotel_budget_total_target": round(hotel_budget_total_target, 2),
        "hotel_budget_per_night_target": round(hotel_budget_per_night_target, 2),
        "hotel_budget_per_night_soft_max": hotel_budget_per_night_soft_max,
        "hotel_budget_per_night_hard_max": hotel_budget_per_night_hard_max,
        "budget_status": status,
    }
    feasibility_summary = {
        "overall_status": status,
        "budget_comment": comment,
        "recommended_adjustments_if_needed": adjustments,
    }
    return budget_model, feasibility_summary


def _build_trip_archetype(canonical: Dict[str, Any]) -> str:
    group_type = str((canonical.get("traveler_profile") or {}).get("group_type", "mixed")).lower()
    primary_goal = str((canonical.get("trip_intent") or {}).get("primary_goal", "balanced")).lower()
    pace = str((canonical.get("trip_intent") or {}).get("pace", "medium")).lower()

    if group_type == "couple" and primary_goal in {"relaxation", "romantic"}:
        return "relaxed_couple_getaway"
    if group_type == "friends" and primary_goal in {"activities", "adventure"}:
        return "friends_activity_explorer"
    if group_type == "family":
        return "family_comfort_sightseeing"
    if pace == "fast":
        return "dense_explorer"
    return f"{group_type}_{primary_goal}_trip"


def _build_planner_brief(
    canonical: Dict[str, Any], budget_model: Dict[str, Any]
) -> Dict[str, Any]:
    destination = canonical["destination"]
    specific_places = destination.get("specific_places", [])
    recommended_micro_areas = specific_places[:3] if specific_places else [destination.get("query", "")]
    recommended_micro_areas = [x for x in recommended_micro_areas if x]
    if not recommended_micro_areas:
        recommended_micro_areas = ["central_area"]

    trip_intent = canonical["trip_intent"]
    primary_goal = trip_intent.get("primary_goal", "balanced_exploration")
    secondary = trip_intent.get("secondary_goals", [])[:2]

    style_match = {
        primary_goal: 0.9,
    }
    for goal in secondary:
        style_match[goal] = 0.82

    pace = trip_intent.get("pace", "medium")
    if pace == "slow":
        density_limit = 2
        hotel_time_priority = "high"
    elif pace == "fast":
        density_limit = 4
        hotel_time_priority = "medium_low"
    else:
        density_limit = 3
        hotel_time_priority = "medium_high"

    planner_brief = {
        "trip_request_id": canonical["trip_request_id"],
        "destination_summary": {
            "primary_destination": destination.get("query", ""),
            "recommended_micro_areas": recommended_micro_areas,
            "destination_style_match": style_match,
        },
        "user_trip_model": {
            "trip_archetype": _build_trip_archetype(canonical),
            "pace_model": pace,
            "density_limit_per_day": density_limit,
            "hotel_time_priority": hotel_time_priority,
            "nightlife_priority": "low",
            "scenic_priority": "high",
        },
        "budget_model": budget_model,
        "planning_constraints": {
            "must_include": canonical.get("trip_constraints", {}).get("must_visit_places", []),
            "must_avoid": canonical.get("trip_constraints", {}).get("must_avoid", []),
            "transport_assumption": canonical.get("mobility_and_transport", {}).get(
                "transport_preference", "mixed"
            ),
            "max_intercity_hops": 2,
        },
        "quality_rules": {
            "max_major_anchors_per_day": 1,
            "max_secondary_items_per_day": 2,
            "min_buffer_minutes_per_day": 90,
            "geographic_clustering_required": True,
        },
    }
    return planner_brief


def _build_system_prompt() -> str:
    return (
        "You are PlannerAgent for a travel concierge.\n"
        "Output JSON only. No markdown.\n"
        "You must return exactly 3 clearly distinct itinerary strategies.\n"
        "Required strategy spread: one relaxed/comfort, one balanced/best-value, one activity-heavy/dense.\n"
        "Hard quality rules:\n"
        "1) Geographic clustering by day; avoid cross-city zig-zag plans.\n"
        "2) Per day: exactly one major_anchor and max two secondary_items.\n"
        "3) Budget excludes flights; reflect feasibility honestly.\n"
        "4) Must-visit places are anchors, not optional notes.\n"
        "5) selected_itinerary and handoff_for_hotel_discovery must be downstream-ready.\n"
        "6) Do not invent unsupported keys; follow schema strictly.\n"
        "7) Keep target_per_night <= hard_max_per_night."
    )


def _build_user_prompt(
    canonical: Dict[str, Any],
    planner_brief: Dict[str, Any],
    previous_errors: List[str],
) -> str:
    error_block = ""
    if previous_errors:
        error_lines = "\n".join(f"- {err}" for err in previous_errors)
        error_block = (
            "Previous attempt failed validation. Fix ALL errors:\n"
            f"{error_lines}\n"
        )

    payload = {
        "canonical_preferences": canonical,
        "planner_brief": planner_brief,
        "output_contract": {
            "itineraries_required": 3,
            "styles_required": ["relaxed", "balanced", "activity_heavy"],
            "feasibility_values": ["within_budget", "stretch", "over_budget"],
            "day_plan_rule": "one major anchor + max two secondary items",
            "include_fields": [
                "feasibility_summary",
                "itinerary_options.day_plan",
                "itinerary_options.handoff_for_hotel_discovery",
                "itinerary_options.selected_itinerary",
            ],
        },
    }

    return (
        "Create planner output from the given canonical preferences and planner brief.\n"
        "Make itinerary options meaningfully different.\n"
        "Use realistic budgets and day pacing.\n"
        f"{error_block}\n"
        "Input JSON:\n"
        f"{json.dumps(payload, ensure_ascii=True)}"
    )


def _selected_to_handoff(selected_itinerary: Dict[str, Any]) -> Dict[str, Any]:
    dates = selected_itinerary["dates"]
    nights = int(dates.get("nights", 1))
    budget = selected_itinerary["budget"]
    prefs = selected_itinerary["preferences"]
    constraints = selected_itinerary["constraints"]
    per_night = float(budget["target_per_night"])
    hard_max = float(budget["hard_max_per_night"])

    return {
        "destination": copy.deepcopy(selected_itinerary["destination"]),
        "dates": copy.deepcopy(dates),
        "party": copy.deepcopy(selected_itinerary["party"]),
        "budget": {
            "total_excl_flights": float(budget["total_excl_flights"]),
            "currency": budget["currency"],
            "hotel_budget_total_target": round(per_night * nights, 2),
            "hotel_budget_per_night_target": per_night,
            "hotel_budget_per_night_hard_max": hard_max,
        },
        "hotel_preferences": {
            "property_types": copy.deepcopy(prefs["property_types"]),
            "hotel_class_preference": copy.deepcopy(prefs["hotel_class"]),
            "must_have_amenities": copy.deepcopy(prefs["must_have_amenities"]),
            "nice_to_have_amenities": copy.deepcopy(prefs["nice_to_have_amenities"]),
            "free_cancellation_preferred": bool(prefs["free_cancellation_preferred"]),
        },
        "user_constraints": copy.deepcopy(constraints),
        "ranking_mode": selected_itinerary["ranking_mode"],
    }


def _build_fallback_day_plan(
    nights: int, areas: List[str], style: str, must_include: List[str]
) -> List[Dict[str, Any]]:
    zone_list = areas if areas else ["central_area"]
    plan: List[Dict[str, Any]] = []
    if style == "relaxed":
        pace = "light"
    elif style == "activity_heavy":
        pace = "high"
    else:
        pace = "medium"

    anchors = must_include[:]
    for day in range(1, nights + 1):
        zone = zone_list[min((day - 1), len(zone_list) - 1)]
        if day == 1:
            major = "Arrival and local orientation"
            secondaries = ["local dinner", "easy neighborhood walk"]
            theme = "Arrival and settle-in"
        elif anchors:
            major = anchors.pop(0)
            secondaries = ["local food stop", "sunset or evening stroll"]
            theme = "Anchor experience day"
        else:
            major = "Clustered sightseeing anchor"
            secondaries = ["cafe or rest break", "scenic viewpoint"]
            theme = "Exploration day"
        plan.append(
            {
                "day": day,
                "zone": zone,
                "theme": theme,
                "major_anchor": major,
                "secondary_items": secondaries[:2],
                "pace": pace,
            }
        )
    return plan


def _ensure_option_defaults(
    option: Dict[str, Any],
    request_id: str,
    must_include: List[str],
) -> None:
    itinerary_id = option.get("itinerary_id", "")
    selected = option.get("selected_itinerary", {})

    selected["trip_request_id"] = request_id
    selected["selected_itinerary_id"] = itinerary_id

    if "label" not in option:
        option["label"] = option.get("title", itinerary_id or "itinerary")
    if "title" not in option:
        option["title"] = option["label"]
    if "fit_reason" not in option:
        option["fit_reason"] = option.get("positioning", "Good match for stated preferences.")
    if "style" not in option:
        pace = str(option.get("trip_pace", "balanced")).lower()
        option["style"] = (
            "relaxed" if pace == "relaxed" else ("activity_heavy" if pace == "fast" else "balanced")
        )
    if "areas" not in option:
        option["areas"] = copy.deepcopy((selected.get("destination") or {}).get("micro_areas", []))
    option["areas"] = option.get("areas") or copy.deepcopy(
        (selected.get("destination") or {}).get("micro_areas", [])
    )

    if "budget_band" not in option:
        sb = selected.get("budget", {})
        option["budget_band"] = {
            "hotel_budget_per_night_target": float(sb.get("target_per_night", 0)),
            "hotel_budget_per_night_hard_max": float(sb.get("hard_max_per_night", 0)),
            "transport_intensity": "medium",
            "activity_spend_intensity": "medium",
        }

    if "handoff_for_hotel_discovery" not in option:
        option["handoff_for_hotel_discovery"] = _selected_to_handoff(selected)

    if "day_plan" not in option or not option["day_plan"]:
        nights = int((selected.get("dates") or {}).get("nights", 1))
        option["day_plan"] = _build_fallback_day_plan(
            nights=nights,
            areas=option.get("areas", []),
            style=option.get("style", "balanced"),
            must_include=must_include,
        )

    if "estimated_total_trip_cost" not in option:
        total = float((selected.get("budget") or {}).get("total_excl_flights", 0))
        option["estimated_total_trip_cost"] = {
            "amount_min": round(total * 0.9, 2),
            "amount_max": round(total * 1.08, 2),
            "currency": (selected.get("budget") or {}).get("currency", "INR"),
        }

    if "why_this_option" not in option or not option["why_this_option"]:
        option["why_this_option"] = [option.get("fit_reason", "Aligned to user preferences.")]


def _normalize_plan(
    plan: Dict[str, Any],
    preferences: Dict[str, Any],
    canonical: Dict[str, Any],
    planner_brief: Dict[str, Any],
    feasibility_summary: Dict[str, Any],
    model_name: str,
) -> Dict[str, Any]:
    request_id = preferences.get("request_id", canonical.get("trip_request_id", "unknown_request"))
    normalized = copy.deepcopy(plan)

    normalized["request_id"] = request_id
    normalized["model"] = model_name
    normalized["generated_at"] = _utc_now_iso()
    normalized["planner_version"] = str(normalized.get("planner_version") or "v1")
    normalized["canonical_preferences"] = canonical
    normalized["planner_brief"] = planner_brief

    if "feasibility_summary" not in normalized:
        normalized["feasibility_summary"] = feasibility_summary
    else:
        fs = normalized["feasibility_summary"]
        fs.setdefault("overall_status", feasibility_summary["overall_status"])
        fs.setdefault("budget_comment", feasibility_summary["budget_comment"])
        fs.setdefault(
            "recommended_adjustments_if_needed",
            feasibility_summary["recommended_adjustments_if_needed"],
        )

    if "planner_notes" not in normalized or not normalized["planner_notes"]:
        normalized["planner_notes"] = [
            "Planner built from canonical preferences and planner brief.",
            "Itinerary handoff JSON is ready for hotel discovery.",
        ]

    must_include = canonical.get("trip_constraints", {}).get("must_visit_places", [])
    for option in normalized.get("itinerary_options", []):
        _ensure_option_defaults(option, request_id=request_id, must_include=must_include)

    return normalized


def _validate_plan_schema(plan: Dict[str, Any], schema: Dict[str, Any]) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(plan), key=lambda e: list(e.path))
    if not errors:
        return
    first = errors[0]
    path = ".".join(str(x) for x in first.path)
    raise ValueError(f"Schema validation failed at `{path}`: {first.message}")


def _validate_plan_business_rules(
    plan: Dict[str, Any],
    preferences: Dict[str, Any],
    canonical: Dict[str, Any],
) -> None:
    options = plan.get("itinerary_options", [])
    if len(options) != 3:
        raise ValueError("itinerary_options must contain exactly 3 options")

    ids = [opt.get("itinerary_id") for opt in options]
    if len(set(ids)) != len(ids):
        raise ValueError("itinerary_id values must be unique")

    rec_id = plan.get("recommended_itinerary_id")
    if rec_id not in ids:
        raise ValueError("recommended_itinerary_id must match one itinerary_id")

    styles = [opt.get("style") for opt in options]
    if len(set(styles)) < 3:
        raise ValueError("three itinerary options must be stylistically distinct")

    request_id = preferences.get("request_id")
    fixed_destination = None
    dest_candidates = preferences.get("trip_basics", {}).get("destination_candidates", [])
    if dest_candidates:
        first = dest_candidates[0]
        if first.get("flexibility") == "fixed":
            fixed_destination = (first.get("country"), first.get("city_or_region"))

    required_nights = int(canonical.get("dates", {}).get("duration_nights", 1))

    for option in options:
        itinerary_id = option["itinerary_id"]
        selected = option["selected_itinerary"]

        if selected.get("selected_itinerary_id") != itinerary_id:
            raise ValueError(f"selected_itinerary_id mismatch for {itinerary_id}")
        if request_id and selected.get("trip_request_id") != request_id:
            raise ValueError(f"trip_request_id mismatch for {itinerary_id}")

        budget = selected["budget"]
        if float(budget["target_per_night"]) > float(budget["hard_max_per_night"]):
            raise ValueError(f"target_per_night > hard_max_per_night in {itinerary_id}")

        day_plan = option["day_plan"]
        if len(day_plan) != required_nights:
            raise ValueError(
                f"day_plan length must equal duration_nights ({required_nights}) for {itinerary_id}"
            )
        for day in day_plan:
            if len(day.get("secondary_items", [])) > 2:
                raise ValueError(f"secondary_items cannot exceed 2 per day in {itinerary_id}")

        handoff = option["handoff_for_hotel_discovery"]
        if handoff["destination"]["city_or_region"] != selected["destination"]["city_or_region"]:
            raise ValueError(f"handoff destination mismatch in {itinerary_id}")

        if fixed_destination is not None:
            country, city = fixed_destination
            selected_dest = selected["destination"]
            if (selected_dest.get("country"), selected_dest.get("city_or_region")) != (country, city):
                raise ValueError(f"fixed destination violated in {itinerary_id}")


def _build_strict_model_schema(output_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Return a strict response schema compatible with OpenAI JSON schema mode.

    canonical_preferences and planner_brief are injected post-generation by code,
    so we exclude them from model output contract.
    """
    schema = copy.deepcopy(output_schema)
    props = schema.get("properties", {})
    if isinstance(props, dict):
        props.pop("canonical_preferences", None)
        props.pop("planner_brief", None)
    return schema


def pick_selected_itinerary(
    planner_output: Dict[str, Any], itinerary_id: Optional[str] = None
) -> Dict[str, Any]:
    options = planner_output.get("itinerary_options", [])
    if not options:
        raise ValueError("planner_output has no itinerary_options")

    target = itinerary_id or planner_output.get("recommended_itinerary_id")
    for option in options:
        if option.get("itinerary_id") == target:
            return copy.deepcopy(option["selected_itinerary"])
    raise ValueError(f"Could not find selected itinerary: {target}")


@dataclass
class PlannerConfig:
    model: str = "gpt-5.4"
    temperature: float = 0.2
    max_attempts: int = 3


class PlannerAgent:
    def __init__(
        self,
        client: Any,
        config: Optional[PlannerConfig] = None,
        schema_path: Path = PLANNER_SCHEMA_PATH,
    ):
        self.client = client
        self.config = config or PlannerConfig()
        self.output_schema = _read_json(schema_path)
        self.model_response_schema = _build_strict_model_schema(self.output_schema)

    def _call_model(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        completion = self.client.chat.completions.create(
            model=self.config.model,
            temperature=self.config.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "planner_itinerary_options",
                    "strict": True,
                    "schema": self.model_response_schema,
                },
            },
        )
        choice = completion.choices[0]
        refusal = getattr(choice.message, "refusal", None)
        if refusal:
            raise RuntimeError(f"Model refused request: {refusal}")

        raw_text = _extract_message_text(choice.message).strip()
        if not raw_text:
            raise RuntimeError("Model returned empty content")
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Model output is not valid JSON: {exc}") from exc

    def create_plan(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
        canonical = _canonicalize_preferences(preferences)
        missing_slots = _missing_critical_slots(canonical)
        follow_ups = _build_follow_up_questions(missing_slots)

        canonical["conversation_state"]["missing_slots"] = missing_slots
        canonical["conversation_state"]["clarifications_needed"] = [
            q["prompt"] for q in follow_ups
        ]
        canonical["conversation_state"]["confidence"] = 0.68 if missing_slots else 0.93

        if missing_slots:
            raise ValueError(
                "Planner missing critical slots. Ask follow-ups first: "
                + json.dumps(follow_ups, ensure_ascii=True)
            )

        budget_model, feasibility_summary = _build_budget_model(canonical)
        planner_brief = _build_planner_brief(canonical, budget_model=budget_model)

        system_prompt = _build_system_prompt()
        validation_errors: List[str] = []
        last_exception: Optional[Exception] = None

        for _attempt in range(1, self.config.max_attempts + 1):
            user_prompt = _build_user_prompt(
                canonical=canonical,
                planner_brief=planner_brief,
                previous_errors=validation_errors,
            )
            try:
                raw_plan = self._call_model(system_prompt=system_prompt, user_prompt=user_prompt)
                plan = _normalize_plan(
                    plan=raw_plan,
                    preferences=preferences,
                    canonical=canonical,
                    planner_brief=planner_brief,
                    feasibility_summary=feasibility_summary,
                    model_name=self.config.model,
                )
                _validate_plan_schema(plan, self.output_schema)
                _validate_plan_business_rules(plan, preferences, canonical)
                return plan
            except Exception as exc:  # noqa: PERF203
                last_exception = exc
                validation_errors = [str(exc)]

        raise RuntimeError(f"Planner agent failed after retries: {last_exception}")

    @staticmethod
    def save_json(path: Path, payload: Dict[str, Any]) -> None:
        _write_json(path, payload)
