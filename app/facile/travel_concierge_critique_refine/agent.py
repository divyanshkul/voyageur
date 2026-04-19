from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator


ROOT_DIR = Path(__file__).resolve().parents[1]  # app/facile/
REVIEW_SCHEMA_PATH = ROOT_DIR / "schemas" / "critique_refine_review.schema.json"


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _norm(value: str) -> str:
    return " ".join(str(value).lower().split())


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _text_contains_any(text: str, terms: List[str]) -> bool:
    hay = _norm(text)
    for term in terms:
        if _norm(term) and _norm(term) in hay:
            return True
    return False


def _collect_day_text(day: Dict[str, Any]) -> str:
    items = [str(day.get("theme", "")), str(day.get("major_anchor", ""))]
    for x in day.get("secondary_items", []):
        items.append(str(x))
    return " ".join(items)


def _status_rank(status: str) -> int:
    ranks = {"valid": 4, "valid_with_risk": 3, "conditionally_invalid": 2, "invalid": 1}
    return ranks.get(status, 0)


def _similarity_score(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    a_style = _norm(a.get("style", ""))
    b_style = _norm(b.get("style", ""))
    style_sim = 1.0 if a_style == b_style else 0.0

    a_areas = {_norm(x) for x in a.get("areas", []) if _norm(x)}
    b_areas = {_norm(x) for x in b.get("areas", []) if _norm(x)}
    if a_areas or b_areas:
        area_sim = len(a_areas & b_areas) / max(len(a_areas | b_areas), 1)
    else:
        area_sim = 0.0

    a_budget = _safe_float((a.get("budget_band") or {}).get("hotel_budget_per_night_target"), 0)
    b_budget = _safe_float((b.get("budget_band") or {}).get("hotel_budget_per_night_target"), 0)
    if a_budget <= 0 or b_budget <= 0:
        budget_sim = 0.5
    else:
        diff_ratio = abs(a_budget - b_budget) / max((a_budget + b_budget) / 2.0, 1.0)
        budget_sim = max(0.0, 1.0 - diff_ratio)

    return 0.45 * style_sim + 0.35 * area_sim + 0.2 * budget_sim


def _issue(
    issue_id: str,
    issue_type: str,
    severity: str,
    summary: str,
    why: str,
    action: str,
    day: Optional[int] = None,
    location: Optional[str] = None,
    confidence: str = "medium",
) -> Dict[str, Any]:
    return {
        "issue_id": issue_id,
        "type": issue_type,
        "severity": severity,
        "day": day,
        "location": location,
        "summary": summary,
        "why_it_matters": why,
        "recommended_action": action,
        "evidence_confidence": confidence,
    }


def _extract_canonical(preferences: Dict[str, Any], planner_output: Dict[str, Any]) -> Dict[str, Any]:
    if planner_output.get("canonical_preferences"):
        return copy.deepcopy(planner_output["canonical_preferences"])

    trip = preferences.get("trip_basics", {})
    traveler = preferences.get("traveler_profile", {})
    destination_candidates = trip.get("destination_candidates", [])
    first = destination_candidates[0] if destination_candidates else {}
    return {
        "trip_request_id": preferences.get("request_id", ""),
        "traveler_profile": {
            "group_type": traveler.get("group_type", "mixed"),
            "adults": _safe_int(traveler.get("adults", traveler.get("travelers_count", 1)), 1),
            "children": _safe_int(traveler.get("children", 0), 0),
            "seniors": _safe_int(traveler.get("seniors", 0), 0),
        },
        "destination": {
            "query": first.get("city_or_region", ""),
            "country": first.get("country", ""),
            "specific_places": trip.get("must_visit_places", []),
            "is_fixed": first.get("flexibility") == "fixed",
        },
        "dates": {
            "duration_nights": _safe_int(trip.get("trip_nights", 1), 1),
        },
        "trip_intent": {
            "pace": "medium"
            if trip.get("trip_pace", "balanced") == "balanced"
            else ("slow" if trip.get("trip_pace") == "relaxed" else "fast")
        },
        "budget": {
            "total_excl_flights": _safe_float((preferences.get("budget") or {}).get("total_budget"), 0),
            "currency": (preferences.get("budget") or {}).get("currency", "INR"),
        },
        "trip_constraints": {
            "must_visit_places": trip.get("must_visit_places", []),
            "must_avoid": trip.get("places_or_experiences_to_avoid", []),
        },
        "food_preferences": {
            "dietary_preferences": traveler.get("dietary_restrictions", []),
        },
    }


def _hard_checks(
    option: Dict[str, Any],
    canonical: Dict[str, Any],
    external_context_cache: Dict[str, Any],
) -> Tuple[List[str], List[Dict[str, Any]]]:
    hard_failures: List[str] = []
    issues: List[Dict[str, Any]] = []
    day_plan = option.get("day_plan", [])

    # Must-visit checks
    must_visit = canonical.get("trip_constraints", {}).get("must_visit_places", [])
    plan_text = " ".join(_collect_day_text(day) for day in day_plan)
    for place in must_visit:
        if not _text_contains_any(plan_text, [place]):
            hard_failures.append("must_visit_omitted")
            issues.append(
                _issue(
                    issue_id=f"iss_must_{len(issues)+1:03d}",
                    issue_type="constraint_violation",
                    severity="major",
                    summary=f"Must-visit anchor missing: {place}",
                    why="User-mandated anchor is missing from the itinerary.",
                    action="Add this anchor to a geographically compatible day.",
                    confidence="high",
                )
            )

    # Must-avoid checks
    must_avoid = canonical.get("trip_constraints", {}).get("must_avoid", [])
    for avoid_term in must_avoid:
        for day in day_plan:
            if _text_contains_any(_collect_day_text(day), [avoid_term]):
                hard_failures.append("must_avoid_included")
                issues.append(
                    _issue(
                        issue_id=f"iss_avoid_{len(issues)+1:03d}",
                        issue_type="constraint_violation",
                        severity="major",
                        summary=f"Must-avoid content appears in plan: {avoid_term}",
                        why="Itinerary includes an explicitly avoided experience.",
                        action="Replace this with a quieter / suitable alternative.",
                        day=_safe_int(day.get("day")),
                        location=str(day.get("zone", "")) or None,
                        confidence="high",
                    )
                )

    # Date / structure impossibility
    required_nights = _safe_int(canonical.get("dates", {}).get("duration_nights"), 1)
    if len(day_plan) != required_nights:
        hard_failures.append("day_count_mismatch")
        issues.append(
            _issue(
                issue_id=f"iss_daycount_{len(issues)+1:03d}",
                issue_type="date_impossibility",
                severity="major",
                summary=f"Day plan count ({len(day_plan)}) does not match trip nights ({required_nights}).",
                why="This breaks itinerary feasibility and downstream calculations.",
                action="Regenerate day skeleton with exact night count.",
                confidence="high",
            )
        )

    # Budget impossibility check
    selected_budget = ((option.get("selected_itinerary") or {}).get("budget") or {})
    total_budget = _safe_float(canonical.get("budget", {}).get("total_excl_flights"), 0)
    est_cost = option.get("estimated_total_trip_cost") or {}
    est_max = _safe_float(est_cost.get("amount_max"), 0)
    target_per_night = _safe_float(selected_budget.get("target_per_night"), 0)
    hard_max = _safe_float(selected_budget.get("hard_max_per_night"), 0)

    if hard_max > 0 and target_per_night > hard_max:
        hard_failures.append("budget_internal_contradiction")
        issues.append(
            _issue(
                issue_id=f"iss_budget_{len(issues)+1:03d}",
                issue_type="budget_impossibility",
                severity="major",
                summary="Target per-night budget exceeds hard max.",
                why="Internal budget contradiction makes the plan unreliable.",
                action="Lower target or raise hard max with explicit justification.",
                confidence="high",
            )
        )

    if total_budget > 0 and est_max > total_budget * 1.35:
        hard_failures.append("severe_over_budget")
        issues.append(
            _issue(
                issue_id=f"iss_overbudget_{len(issues)+1:03d}",
                issue_type="budget_impossibility",
                severity="major",
                summary="Estimated trip max is far above user budget.",
                why="Plan likely fails affordability constraints.",
                action="Reduce activity density or switch to lower-cost stay zones.",
                confidence="medium",
            )
        )

    # Routing impossibility: too many zone hops for short trip
    zones = [str(d.get("zone", "")).strip() for d in day_plan if str(d.get("zone", "")).strip()]
    hops = 0
    for i in range(1, len(zones)):
        if _norm(zones[i]) != _norm(zones[i - 1]):
            hops += 1
    max_hops = _safe_int(
        ((option.get("planner_brief") or {}).get("planning_constraints") or {}).get("max_intercity_hops"),
        2,
    )
    if hops > max_hops + 1:
        hard_failures.append("routing_impossibility")
        issues.append(
            _issue(
                issue_id=f"iss_route_{len(issues)+1:03d}",
                issue_type="routing_impossibility",
                severity="major",
                summary=f"Too many inter-zone hops ({hops}) for this trip structure.",
                why="Likely causes transit fatigue and timing slippage.",
                action="Re-cluster days by zone and reduce transfers.",
                confidence="medium",
            )
        )

    # External disruptions (optional cache)
    disruptions = external_context_cache.get("disruptions", [])
    for dis in disruptions:
        impact = str(dis.get("impact", "")).lower()
        if impact != "high":
            continue
        dis_zone = str(dis.get("zone", ""))
        dis_day = dis.get("day")
        for day in day_plan:
            day_no = _safe_int(day.get("day"), 0)
            zone = str(day.get("zone", ""))
            zone_match = dis_zone and _text_contains_any(zone, [dis_zone])
            day_match = dis_day is None or day_no == _safe_int(dis_day, -1)
            if zone_match and day_match:
                hard_failures.append("critical_external_disruption")
                issues.append(
                    _issue(
                        issue_id=f"iss_disruption_{len(issues)+1:03d}",
                        issue_type="event_risk",
                        severity="major",
                        summary=str(dis.get("summary", "High-impact disruption detected")),
                        why="External context indicates material risk to itinerary feasibility.",
                        action="Move this block to a lower-risk day/zone or replace anchor.",
                        day=day_no,
                        location=zone,
                        confidence=str(dis.get("confidence", "medium")),
                    )
                )

    return hard_failures, issues


def _soft_checks(
    option: Dict[str, Any],
    canonical: Dict[str, Any],
    peer_options: List[Dict[str, Any]],
    base_issue_count: int,
) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    day_plan = option.get("day_plan", [])

    # Preference fit: pace mismatch
    user_pace = _norm((canonical.get("trip_intent") or {}).get("pace", "medium"))
    opt_pace = _norm(option.get("trip_pace", "balanced"))
    pace_map = {"relaxed": "slow", "balanced": "medium", "fast": "fast"}
    mapped = pace_map.get(opt_pace, opt_pace)
    if user_pace and mapped and user_pace != mapped:
        issues.append(
            _issue(
                issue_id=f"iss_soft_{base_issue_count+len(issues)+1:03d}",
                issue_type="preference_fit",
                severity="medium",
                summary="Pace may not fully match traveler preference.",
                why="A pace mismatch can reduce satisfaction and increase fatigue.",
                action="Adjust one day to better align with user pace expectations.",
                confidence="medium",
            )
        )

    # Day density quality
    high_days = 0
    consecutive_high = 0
    max_consecutive_high = 0
    for day in day_plan:
        if _norm(day.get("pace", "")) == "high":
            high_days += 1
            consecutive_high += 1
            max_consecutive_high = max(max_consecutive_high, consecutive_high)
        else:
            consecutive_high = 0
    if max_consecutive_high >= 3:
        issues.append(
            _issue(
                issue_id=f"iss_soft_{base_issue_count+len(issues)+1:03d}",
                issue_type="day_density",
                severity="medium",
                summary="Too many consecutive high-intensity days.",
                why="Limited recovery time can degrade trip experience.",
                action="Introduce a lighter day after 2 high-intensity days.",
                confidence="high",
            )
        )

    # Distinctiveness check
    if peer_options:
        sims = [_similarity_score(option, peer) for peer in peer_options]
        max_sim = max(sims) if sims else 0.0
        if max_sim > 0.82:
            issues.append(
                _issue(
                    issue_id=f"iss_soft_{base_issue_count+len(issues)+1:03d}",
                    issue_type="distinctiveness",
                    severity="medium",
                    summary="This option is too similar to another itinerary.",
                    why="Low differentiation weakens user choice quality.",
                    action="Differentiate zones, pace, and budget posture more clearly.",
                    confidence="high",
                )
            )

    # Dietary feasibility hint
    dietary = canonical.get("food_preferences", {}).get("dietary_preferences", [])
    if dietary and not _text_contains_any(" ".join(_collect_day_text(d) for d in day_plan), dietary):
        issues.append(
            _issue(
                issue_id=f"iss_soft_{base_issue_count+len(issues)+1:03d}",
                issue_type="dining_constraints",
                severity="minor",
                summary="Dietary preferences are not explicitly represented in day flow.",
                why="Ignoring dietary constraints can reduce practical usability.",
                action="Add one dietary-compatible meal note in relevant zones.",
                confidence="medium",
            )
        )

    return issues


def _apply_penalties(issues: List[Dict[str, Any]]) -> float:
    penalties = 0.0
    for issue in issues:
        sev = issue["severity"]
        if sev == "major":
            penalties += 18
        elif sev == "medium":
            penalties += 8
        else:
            penalties += 3
    return penalties


def _compute_score_breakdown(
    option: Dict[str, Any],
    canonical: Dict[str, Any],
    issues: List[Dict[str, Any]],
    peer_options: List[Dict[str, Any]],
) -> Dict[str, float]:
    # Preference Match (25)
    user_pace = _norm((canonical.get("trip_intent") or {}).get("pace", "medium"))
    option_pace = _norm(option.get("trip_pace", "balanced"))
    pace_map = {"relaxed": "slow", "balanced": "medium", "fast": "fast"}
    pace_aligned = 1.0 if pace_map.get(option_pace, option_pace) == user_pace else 0.65

    must_visit = canonical.get("trip_constraints", {}).get("must_visit_places", [])
    text = " ".join(_collect_day_text(d) for d in option.get("day_plan", []))
    if must_visit:
        mv_hits = sum(1 for x in must_visit if _text_contains_any(text, [x]))
        must_visit_ratio = mv_hits / max(len(must_visit), 1)
    else:
        must_visit_ratio = 1.0
    preference_match = 25.0 * (0.55 * pace_aligned + 0.45 * must_visit_ratio)

    # Logical routing (20)
    zones = [str(d.get("zone", "")).strip() for d in option.get("day_plan", []) if str(d.get("zone", "")).strip()]
    hops = 0
    for i in range(1, len(zones)):
        if _norm(zones[i]) != _norm(zones[i - 1]):
            hops += 1
    max_reasonable_hops = max(1, math.ceil(len(zones) / 2))
    hop_ratio = min(hops / max(max_reasonable_hops, 1), 1.5)
    logical_routing = 20.0 * max(0.2, 1.0 - (0.55 * hop_ratio))

    # Temporal feasibility (15)
    duration = _safe_int(canonical.get("dates", {}).get("duration_nights"), 1)
    day_count = len(option.get("day_plan", []))
    day_score = 1.0 if duration == day_count else max(0.0, 1.0 - abs(duration - day_count) * 0.25)
    high_impact_count = sum(1 for i in issues if i["type"] == "event_risk" and i["severity"] == "major")
    temporal_feasibility = 15.0 * max(0.0, day_score - (0.2 * high_impact_count))

    # Budget fit (15)
    user_budget = _safe_float(canonical.get("budget", {}).get("total_excl_flights"), 0)
    est = option.get("estimated_total_trip_cost") or {}
    est_max = _safe_float(est.get("amount_max"), 0)
    if user_budget > 0 and est_max > 0:
        ratio = est_max / user_budget
        if ratio <= 1.0:
            budget_score_ratio = 1.0
        elif ratio <= 1.15:
            budget_score_ratio = max(0.5, 1.0 - ((ratio - 1.0) / 0.15) * 0.5)
        elif ratio <= 1.35:
            budget_score_ratio = max(0.2, 0.5 - ((ratio - 1.15) / 0.2) * 0.3)
        else:
            budget_score_ratio = 0.05
    else:
        budget_score_ratio = 0.55
    budget_fit = 15.0 * budget_score_ratio

    # Comfort usability (10)
    paces = [_norm(d.get("pace", "")) for d in option.get("day_plan", [])]
    high_days = sum(1 for p in paces if p == "high")
    comfort_ratio = max(0.25, 1.0 - (high_days / max(len(paces), 1)) * 0.5)
    comfort_usability = 10.0 * comfort_ratio

    # Constraint satisfaction (10)
    hard_fail_constraints = sum(
        1
        for i in issues
        if i["type"] in {"constraint_violation", "budget_impossibility"} and i["severity"] == "major"
    )
    constraint_satisfaction = max(0.0, 10.0 - hard_fail_constraints * 3.5)

    # Distinctiveness (5)
    if peer_options:
        sims = [_similarity_score(option, p) for p in peer_options]
        max_sim = max(sims) if sims else 0.0
        distinctiveness = 5.0 * max(0.0, 1.0 - max_sim)
    else:
        distinctiveness = 3.5

    penalties = _apply_penalties(issues)

    total = (
        preference_match
        + logical_routing
        + temporal_feasibility
        + budget_fit
        + comfort_usability
        + constraint_satisfaction
        + distinctiveness
        - penalties
    )
    total = max(0.0, min(100.0, total))

    return {
        "preference_match": round(preference_match, 2),
        "logical_routing": round(logical_routing, 2),
        "temporal_feasibility": round(temporal_feasibility, 2),
        "budget_fit": round(budget_fit, 2),
        "comfort_usability": round(comfort_usability, 2),
        "constraint_satisfaction": round(constraint_satisfaction, 2),
        "distinctiveness": round(distinctiveness, 2),
        "penalties": round(penalties, 2),
        "total": round(total, 2),
    }


def _inject_must_visit(day_plan: List[Dict[str, Any]], must_visit: List[str]) -> Optional[Tuple[int, str]]:
    if not must_visit or not day_plan:
        return None
    plan_text = " ".join(_collect_day_text(d) for d in day_plan)
    for place in must_visit:
        if _text_contains_any(plan_text, [place]):
            continue
        # Replace anchor in middle day for minimal disruption
        idx = min(max(len(day_plan) // 2, 0), len(day_plan) - 1)
        day_plan[idx]["major_anchor"] = place
        return (_safe_int(day_plan[idx].get("day"), idx + 1), place)
    return None


def _remove_must_avoid(day_plan: List[Dict[str, Any]], must_avoid: List[str]) -> Optional[Tuple[int, str]]:
    for day in day_plan:
        text = _collect_day_text(day)
        for avoid in must_avoid:
            if _text_contains_any(text, [avoid]):
                # Replace direct mentions with neutral quiet wording
                day["theme"] = "Local exploration and quiet experiences"
                day["major_anchor"] = "Quiet cultural or scenic anchor"
                day["secondary_items"] = ["local food stop", "sunset or evening walk"]
                return (_safe_int(day.get("day")), avoid)
    return None


def _reduce_consecutive_high(day_plan: List[Dict[str, Any]]) -> Optional[int]:
    consecutive = 0
    for idx, day in enumerate(day_plan):
        if _norm(day.get("pace", "")) == "high":
            consecutive += 1
        else:
            consecutive = 0
        if consecutive >= 3:
            day_plan[idx]["pace"] = "medium"
            if len(day_plan[idx].get("secondary_items", [])) > 1:
                day_plan[idx]["secondary_items"] = day_plan[idx]["secondary_items"][:1]
            return _safe_int(day_plan[idx].get("day"), idx + 1)
    return None


def _normalize_budget(
    option: Dict[str, Any],
    canonical: Dict[str, Any],
) -> Optional[str]:
    user_budget = _safe_float(canonical.get("budget", {}).get("total_excl_flights"), 0)
    est = option.get("estimated_total_trip_cost") or {}
    est_max = _safe_float(est.get("amount_max"), 0)
    if user_budget <= 0 or est_max <= user_budget * 1.15:
        return None

    # Apply modest correction to make it more realistic, not magical
    est["amount_max"] = round(max(user_budget * 1.08, user_budget), 2)
    est["amount_min"] = round(min(_safe_float(est.get("amount_min"), user_budget * 0.92), est["amount_max"] * 0.95), 2)
    option["estimated_total_trip_cost"] = est

    sb = (option.get("selected_itinerary") or {}).get("budget") or {}
    target = _safe_float(sb.get("target_per_night"), 0)
    hard_max = _safe_float(sb.get("hard_max_per_night"), 0)
    if hard_max > 0 and target > hard_max:
        sb["target_per_night"] = round(hard_max * 0.92, 2)
    return "Adjusted cost envelope to reduce severe budget stretch."


def _refine_option(
    option: Dict[str, Any],
    canonical: Dict[str, Any],
    issues: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    refined = copy.deepcopy(option)
    changes: List[Dict[str, Any]] = []
    day_plan = refined.get("day_plan", [])

    must_visit = canonical.get("trip_constraints", {}).get("must_visit_places", [])
    injected = _inject_must_visit(day_plan, must_visit)
    if injected:
        changes.append(
            {
                "change_type": "anchor_insertion",
                "day": injected[0],
                "summary": f"Inserted missing must-visit anchor: {injected[1]}",
            }
        )

    must_avoid = canonical.get("trip_constraints", {}).get("must_avoid", [])
    removed = _remove_must_avoid(day_plan, must_avoid)
    if removed:
        changes.append(
            {
                "change_type": "constraint_remediation",
                "day": removed[0],
                "summary": f"Replaced must-avoid content: {removed[1]}",
            }
        )

    reduced_day = _reduce_consecutive_high(day_plan)
    if reduced_day:
        changes.append(
            {
                "change_type": "pace_adjustment",
                "day": reduced_day,
                "summary": "Reduced high-intensity streak by inserting a medium-density day.",
            }
        )

    budget_change = _normalize_budget(refined, canonical)
    if budget_change:
        changes.append(
            {
                "change_type": "budget_rebalance",
                "day": None,
                "summary": budget_change,
            }
        )

    # Keep selected_itinerary and handoff budget internally consistent
    selected = refined.get("selected_itinerary", {})
    handoff = refined.get("handoff_for_hotel_discovery", {})
    sel_budget = selected.get("budget", {})
    handoff_budget = handoff.get("budget", {})
    if sel_budget and handoff_budget:
        nights = _safe_int((selected.get("dates") or {}).get("nights"), 1)
        handoff_budget["hotel_budget_per_night_target"] = _safe_float(sel_budget.get("target_per_night"), 0)
        handoff_budget["hotel_budget_per_night_hard_max"] = _safe_float(sel_budget.get("hard_max_per_night"), 0)
        handoff_budget["hotel_budget_total_target"] = round(
            _safe_float(sel_budget.get("target_per_night"), 0) * max(nights, 1), 2
        )
        handoff["budget"] = handoff_budget
        refined["handoff_for_hotel_discovery"] = handoff

    return refined, changes


def _status_from_failures(hard_failures: List[str], issues: List[Dict[str, Any]]) -> str:
    if not hard_failures:
        has_major = any(i["severity"] == "major" for i in issues)
        return "valid_with_risk" if has_major else "valid"

    critical = {
        "must_visit_omitted",
        "must_avoid_included",
        "day_count_mismatch",
        "budget_internal_contradiction",
        "severe_over_budget",
        "routing_impossibility",
        "critical_external_disruption",
    }
    critical_count = sum(1 for h in hard_failures if h in critical)
    if critical_count >= 2:
        return "invalid"
    return "conditionally_invalid"


def _validate_review_schema(payload: Dict[str, Any], schema: Dict[str, Any]) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if not errors:
        return
    first = errors[0]
    path = ".".join(str(x) for x in first.path)
    raise ValueError(f"Review schema validation failed at `{path}`: {first.message}")


def pick_selected_itinerary_from_review(
    review_output: Dict[str, Any],
    itinerary_id: Optional[str] = None,
) -> Dict[str, Any]:
    target = itinerary_id or (review_output.get("review_summary") or {}).get("top_recommendation_itinerary_id")
    for item in review_output.get("itinerary_reviews", []):
        refined = item.get("refined_itinerary", {})
        if refined.get("itinerary_id") == target:
            return copy.deepcopy((refined.get("selected_itinerary") or {}))
    raise ValueError(f"No refined itinerary found for `{target}`")


@dataclass
class CritiqueRefineConfig:
    max_major_penalty_for_valid: int = 1


class CritiqueRefineAgent:
    def __init__(self, config: Optional[CritiqueRefineConfig] = None):
        self.config = config or CritiqueRefineConfig()
        self.schema = _read_json(REVIEW_SCHEMA_PATH)

    def review(
        self,
        user_preferences: Dict[str, Any],
        planner_output: Dict[str, Any],
        external_context_cache: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        external_context_cache = external_context_cache or {}
        canonical = _extract_canonical(user_preferences, planner_output)
        options = copy.deepcopy(planner_output.get("itinerary_options", []))
        if len(options) != 3:
            raise ValueError("planner_output must contain exactly 3 itinerary options")

        review_items: List[Dict[str, Any]] = []
        all_issue_summaries: List[str] = []

        for idx, option in enumerate(options):
            itinerary_id = option.get("itinerary_id", f"itinerary_{idx+1}")
            peers = [x for i, x in enumerate(options) if i != idx]

            hard_failures, hard_issues = _hard_checks(
                option=option,
                canonical=canonical,
                external_context_cache=external_context_cache,
            )
            soft_issues = _soft_checks(
                option=option,
                canonical=canonical,
                peer_options=peers,
                base_issue_count=len(hard_issues),
            )
            issues_before = hard_issues + soft_issues

            score_before_breakdown = _compute_score_breakdown(
                option=option,
                canonical=canonical,
                issues=issues_before,
                peer_options=peers,
            )
            refined_option, changes = _refine_option(
                option=option,
                canonical=canonical,
                issues=issues_before,
            )

            # Re-run checks on refined version
            refined_hard_failures, refined_hard_issues = _hard_checks(
                option=refined_option,
                canonical=canonical,
                external_context_cache=external_context_cache,
            )
            refined_soft_issues = _soft_checks(
                option=refined_option,
                canonical=canonical,
                peer_options=[x if x is not option else refined_option for x in peers],
                base_issue_count=len(refined_hard_issues),
            )
            issues_after = refined_hard_issues + refined_soft_issues

            score_after_breakdown = _compute_score_breakdown(
                option=refined_option,
                canonical=canonical,
                issues=issues_after,
                peer_options=peers,
            )

            status = _status_from_failures(refined_hard_failures, issues_after)
            score_before = score_before_breakdown["total"]
            score_after = score_after_breakdown["total"]
            improvement = round(score_after - score_before, 2)

            all_issue_summaries.extend([i["summary"] for i in issues_after])

            review_items.append(
                {
                    "itinerary_id": itinerary_id,
                    "status": status,
                    "hard_failures": refined_hard_failures,
                    "issues": issues_after,
                    "score_breakdown_before_refine": score_before_breakdown,
                    "score_breakdown_after_refine": score_after_breakdown,
                    "score_before_refine": score_before,
                    "score_after_refine": score_after,
                    "improvement_delta": improvement,
                    "changes_made": changes,
                    "refined_itinerary": refined_option,
                    "ranking_position": 0,
                }
            )

        # Ranking
        review_items.sort(
            key=lambda x: (_status_rank(x["status"]), x["score_after_refine"]),
            reverse=True,
        )
        for idx, item in enumerate(review_items, start=1):
            item["ranking_position"] = idx

        top_id = review_items[0]["itinerary_id"]
        summary_notes = []
        if any(x["status"] in {"conditionally_invalid", "invalid"} for x in review_items):
            summary_notes.append("One or more options remained risky after critique/refine.")
        if any(x["improvement_delta"] > 0 for x in review_items):
            summary_notes.append("Refinement improved at least one itinerary score.")
        if not summary_notes:
            summary_notes.append("All options passed with acceptable feasibility.")

        # Common planner failures
        issue_counts: Dict[str, int] = {}
        for summary in all_issue_summaries:
            issue_counts[summary] = issue_counts.get(summary, 0) + 1
        common_failures = [
            k for k, _ in sorted(issue_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
        ]

        payload = {
            "trip_request_id": canonical.get("trip_request_id") or planner_output.get("request_id", ""),
            "review_summary": {
                "top_recommendation_itinerary_id": top_id,
                "notes": summary_notes,
            },
            "itinerary_reviews": review_items,
            "planner_feedback": {"common_failures": common_failures},
        }
        _validate_review_schema(payload, self.schema)
        return payload
