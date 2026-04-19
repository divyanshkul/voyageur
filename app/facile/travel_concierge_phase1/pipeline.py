from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


SCORE_WEIGHTS = {
    "budget_fit": 0.35,
    "quality_fit": 0.25,
    "reviews_fit": 0.15,
    "amenity_fit": 0.10,
    "area_fit": 0.10,
    "deal_bonus": 0.05,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _norm_text(text: str) -> str:
    lowered = text.lower().strip()
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(cleaned.split())


def _contains_amenity(amenities: List[str], required: str) -> bool:
    needle = _norm_text(required)
    needle_compact = needle.replace(" ", "")
    for item in amenities:
        normalized = _norm_text(item)
        compact = normalized.replace(" ", "")
        if needle in normalized or needle_compact in compact:
            return True
    return False


def _nights(check_in: str, check_out: str) -> int:
    in_dt = datetime.fromisoformat(check_in)
    out_dt = datetime.fromisoformat(check_out)
    return max((out_dt - in_dt).days, 1)


def _serpapi_amenities_param(amenities: List[Any]) -> Optional[str]:
    """Return comma-separated numeric amenities accepted by SerpApi, if any.

    SerpApi `amenities` does not accept free-text strings like "wifi".
    We keep free-text amenities for local filtering/scoring, but only pass
    numeric amenity identifiers through query params.
    """
    codes: List[str] = []
    for value in amenities:
        if isinstance(value, (int, float)):
            codes.append(str(int(value)))
            continue
        if isinstance(value, str) and value.strip().isdigit():
            codes.append(str(int(value.strip())))
    if not codes:
        return None
    return ",".join(codes)


def _extract_serpapi_params_from_link(link: str) -> Dict[str, str]:
    parsed = urllib.parse.urlparse(link)
    query = urllib.parse.parse_qs(parsed.query)
    params: Dict[str, str] = {}
    for key, values in query.items():
        if not values:
            continue
        if key == "api_key":
            continue
        params[key] = values[0]
    return params


def _detect_area_from_text(text: str, micro_areas: List[str]) -> Optional[str]:
    if not text.strip():
        return None
    normalized = _norm_text(text)
    matches = [area for area in micro_areas if _norm_text(area) in normalized]
    if len(matches) == 1:
        return matches[0]
    return None


def _rating_to_sentiment(rating: Optional[float]) -> str:
    if rating is None:
        return "unknown"
    if rating >= 4.0:
        return "positive"
    if rating <= 2.5:
        return "negative"
    return "mixed"


def _clip_text(text: str, limit: int = 320) -> str:
    clean = " ".join(text.replace("||", " ").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def _extract_photo_items(details: Dict[str, Any], max_photos: int) -> List[Dict[str, str]]:
    photos = []
    seen = set()
    for item in details.get("images", []) or []:
        if not isinstance(item, dict):
            continue
        original = item.get("original_image") or item.get("image") or item.get("url")
        thumb = item.get("thumbnail") or original
        if not original and not thumb:
            continue
        photo_url = str(original or thumb)
        thumb_url = str(thumb or original)
        if photo_url in seen:
            continue
        seen.add(photo_url)
        photos.append({"url": photo_url, "thumbnail": thumb_url})
        if len(photos) >= max_photos:
            break
    return photos


def build_hotel_discovery_request(selected_itinerary: Dict[str, Any]) -> Dict[str, Any]:
    destination = selected_itinerary["destination"]
    dates = selected_itinerary["dates"]
    budget = selected_itinerary["budget"]
    preferences = selected_itinerary["preferences"]
    nights = dates.get("nights") or _nights(dates["check_in"], dates["check_out"])

    target_per_night = budget["target_per_night"]
    hard_max_per_night = budget["hard_max_per_night"]

    return {
        "trip_request_id": selected_itinerary["trip_request_id"],
        "selected_itinerary_id": selected_itinerary["selected_itinerary_id"],
        "destination": {
            "country": destination["country"],
            "city_or_region": destination["city_or_region"],
            "micro_areas": destination["micro_areas"],
        },
        "dates": {
            "check_in": dates["check_in"],
            "check_out": dates["check_out"],
            "nights": nights,
        },
        "party": {
            "adults": selected_itinerary["party"]["adults"],
            "children": selected_itinerary["party"]["children"],
        },
        "budget": {
            "total_excl_flights": budget.get("total_excl_flights"),
            "currency": budget["currency"],
            "hotel_budget_total_target": int(target_per_night * nights),
            "hotel_budget_per_night_target": target_per_night,
            "hotel_budget_per_night_hard_max": hard_max_per_night,
        },
        "hotel_preferences": {
            "property_types": preferences.get(
                "property_types", ["hotel", "boutique hotel", "resort"]
            ),
            "hotel_class_preference": preferences.get("hotel_class", [3, 4]),
            "must_have_amenities": preferences.get("must_have_amenities", []),
            "nice_to_have_amenities": preferences.get("nice_to_have_amenities", []),
            "free_cancellation_preferred": preferences.get(
                "free_cancellation_preferred", False
            ),
            "minimum_rating": preferences.get("minimum_rating", 4.0),
        },
        "ranking_mode": selected_itinerary.get("ranking_mode", "best_value"),
        "user_constraints": {
            "dietary": selected_itinerary.get("constraints", {}).get("dietary", []),
            "location_preference": selected_itinerary.get("constraints", {}).get(
                "location_preference", []
            ),
            "mobility_constraints": selected_itinerary.get("constraints", {}).get(
                "mobility_constraints", []
            ),
            "special_notes": selected_itinerary.get("constraints", {}).get(
                "special_notes", []
            ),
        },
    }


def build_search_jobs(
    discovery_request: Dict[str, Any], include_social_proof: bool = False
) -> List[Dict[str, Any]]:
    dest = discovery_request["destination"]
    dates = discovery_request["dates"]
    party = discovery_request["party"]
    budget = discovery_request["budget"]
    prefs = discovery_request["hotel_preferences"]

    base_params = {
        "engine": "google_hotels",
        "check_in_date": dates["check_in"],
        "check_out_date": dates["check_out"],
        "adults": str(party["adults"]),
        "children": str(party["children"]),
        "currency": budget["currency"],
        "gl": "in",
        "hl": "en",
        "hotel_class": ",".join(str(x) for x in prefs["hotel_class_preference"]),
    }

    if prefs["free_cancellation_preferred"]:
        base_params["free_cancellation"] = "true"

    amenities_param = _serpapi_amenities_param(prefs["must_have_amenities"])
    if amenities_param:
        base_params["amenities"] = amenities_param

    buckets = [
        {"name": "balanced_search", "sort_by": None, "max_price": None},
        {
            "name": "value_search",
            "sort_by": "3",
            "max_price": str(int(budget["hotel_budget_per_night_hard_max"])),
        },
        {"name": "quality_search", "sort_by": "8", "max_price": None},
    ]
    if include_social_proof:
        buckets.append(
            {"name": "social_proof_search", "sort_by": "13", "max_price": None}
        )

    jobs: List[Dict[str, Any]] = []
    for area in dest["micro_areas"]:
        for bucket in buckets:
            params = dict(base_params)
            if bucket["name"] == "quality_search":
                params["q"] = f"{area} {dest['city_or_region']} boutique hotels"
            else:
                params["q"] = f"{area} {dest['city_or_region']} hotels"
            if bucket["sort_by"] is not None:
                params["sort_by"] = bucket["sort_by"]
            if bucket["max_price"] is not None:
                params["max_price"] = bucket["max_price"]

            jobs.append(
                {
                    "area": area,
                    "search_bucket": bucket["name"],
                    "params": params,
                }
            )
    return jobs


class SerpApiClient:
    def __init__(self, api_key: str, timeout_seconds: int = 30):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.ssl_context = self._build_ssl_context()

    def _build_ssl_context(self) -> ssl.SSLContext:
        insecure = os.environ.get("SERPAPI_INSECURE_SSL", "").lower() in {
            "1",
            "true",
            "yes",
        }
        if insecure:
            return ssl._create_unverified_context()

        try:
            import certifi

            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            return ssl.create_default_context()

    def _request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(params)
        payload["api_key"] = self.api_key
        query = urllib.parse.urlencode(payload)
        url = f"https://serpapi.com/search.json?{query}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "facile-travel-concierge-phase1/0.1",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(
                req, timeout=self.timeout_seconds, context=self.ssl_context
            ) as resp:
                raw = resp.read().decode("utf-8")
            return json.loads(raw)
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"SerpApi HTTP {exc.code}: {error_body}") from exc

    def search_hotels(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self._request(params)

    def hotel_details(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self._request(params)

    def hotel_reviews(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self._request(params)


class MockSerpApiClient:
    def __init__(self, inventory: List[Dict[str, Any]]):
        self.inventory = inventory
        self._index = {row["property_token"]: row for row in inventory}

    def search_hotels(self, params: Dict[str, Any]) -> Dict[str, Any]:
        q = _norm_text(params.get("q", ""))
        sort_by = params.get("sort_by")
        max_price = _safe_float(params.get("max_price"))
        known_areas = {_norm_text(row["area"]) for row in self.inventory}
        mentioned_areas = {area for area in known_areas if area in q}

        requested_classes = {
            int(x.strip())
            for x in str(params.get("hotel_class", ""))
            .replace("|", ",")
            .split(",")
            if x.strip().isdigit()
        }

        amenity_terms = [
            x.strip()
            for x in str(params.get("amenities", "")).split(",")
            if x.strip()
        ]
        free_cancel_required = str(params.get("free_cancellation", "")).lower() == "true"

        filtered = []
        for row in self.inventory:
            row_area = _norm_text(row["area"])
            if mentioned_areas:
                area_or_city_match = row_area in mentioned_areas
            else:
                area_or_city_match = _norm_text(row["city_or_region"]) in q or q == ""
            if not area_or_city_match:
                continue
            if requested_classes and int(row["hotel_class"]) not in requested_classes:
                continue
            if max_price is not None and float(row["rate_per_night"]) > max_price:
                continue
            if free_cancel_required and not bool(row.get("free_cancellation")):
                continue
            if amenity_terms:
                all_ok = True
                for required in amenity_terms:
                    if not _contains_amenity(row["amenities"], required):
                        all_ok = False
                        break
                if not all_ok:
                    continue
            filtered.append(row)

        if sort_by == "3":
            filtered.sort(key=lambda x: (x["rate_per_night"], -x["overall_rating"]))
        elif sort_by == "8":
            filtered.sort(key=lambda x: (-x["overall_rating"], x["rate_per_night"]))
        elif sort_by == "13":
            filtered.sort(key=lambda x: (-x["reviews"], x["rate_per_night"]))
        else:
            filtered.sort(
                key=lambda x: (
                    -(x["overall_rating"] * math.log1p(x["reviews"])),
                    x["rate_per_night"],
                )
            )

        properties = []
        for row in filtered:
            properties.append(
                {
                    "name": row["name"],
                    "property_token": row["property_token"],
                    "gps_coordinates": {
                        "latitude": row["latitude"],
                        "longitude": row["longitude"],
                    },
                    "rate_per_night": {"extracted_lowest": row["rate_per_night"]},
                    "total_rate": {
                        "extracted_lowest": row["rate_per_night"]
                        * _nights(params["check_in_date"], params["check_out_date"])
                    },
                    "overall_rating": row["overall_rating"],
                    "reviews": row["reviews"],
                    "location_rating": row.get("location_rating"),
                    "reviews_breakdown": row.get("reviews_breakdown", {}),
                    "amenities": row["amenities"],
                    "extracted_hotel_class": row["hotel_class"],
                    "deal": row.get("deal"),
                    "deal_description": row.get("deal_description"),
                }
            )

        return {"properties": properties}

    def hotel_details(self, params: Dict[str, Any]) -> Dict[str, Any]:
        token = params["property_token"]
        row = self._index.get(token)
        if row is None:
            return {}
        pos_category = f"pos_location_{token}"
        neg_category = f"neg_noise_{token}"
        pos_link = "https://serpapi.com/search.json?" + urllib.parse.urlencode(
            {
                "engine": "google_hotels_reviews",
                "property_token": token,
                "category_token": pos_category,
                "hl": "en",
            }
        )
        neg_link = "https://serpapi.com/search.json?" + urllib.parse.urlencode(
            {
                "engine": "google_hotels_reviews",
                "property_token": token,
                "category_token": neg_category,
                "hl": "en",
            }
        )
        return {
            "property_token": token,
            "name": row["name"],
            "phone": row.get("phone"),
            "address": row.get("address"),
            "link": row.get("link"),
            "overall_rating": row.get("overall_rating"),
            "reviews": row.get("reviews"),
            "rate_per_night": {"extracted_lowest": row["rate_per_night"]},
            "total_rate": {
                "extracted_lowest": row["rate_per_night"]
                * _nights(params["check_in_date"], params["check_out_date"])
            },
            "typical_price_range": row.get("typical_price_range"),
            "nearby_places": row.get("nearby_places", []),
            "reviews_breakdown": [
                {
                    "name": "Location",
                    "description": "Location",
                    "total_mentioned": 60,
                    "positive": 48,
                    "negative": 4,
                    "neutral": 8,
                    "category_token": pos_category,
                    "serpapi_link": pos_link,
                },
                {
                    "name": "Noise",
                    "description": "Noise",
                    "total_mentioned": 25,
                    "positive": 8,
                    "negative": 10,
                    "neutral": 7,
                    "category_token": neg_category,
                    "serpapi_link": neg_link,
                },
            ],
            "other_reviews": [
                {
                    "source": "MockSource",
                    "source_rating": {"score": row.get("overall_rating", 4.2), "max_score": 5},
                    "reviews": max(row.get("reviews", 0) // 2, 1),
                    "user_review": {
                        "username": "Mock Traveler",
                        "date": "2 months ago",
                        "rating": {"score": row.get("overall_rating", 4.2), "max_score": 5},
                        "comment": f"Overall pleasant stay at {row['name']} with good service and convenient location.",
                    },
                }
            ],
            "images": [
                {
                    "thumbnail": f"https://images.example.com/{token}_thumb_1.jpg",
                    "original_image": f"https://images.example.com/{token}_orig_1.jpg",
                },
                {
                    "thumbnail": f"https://images.example.com/{token}_thumb_2.jpg",
                    "original_image": f"https://images.example.com/{token}_orig_2.jpg",
                },
            ],
        }

    def hotel_reviews(self, params: Dict[str, Any]) -> Dict[str, Any]:
        token = params.get("property_token")
        category = str(params.get("category_token", ""))
        row = self._index.get(token or "")
        if row is None:
            return {"reviews": []}

        negative_mode = category.startswith("neg_")
        reviews = []
        if negative_mode:
            ratings = [2, 2, 3, 1, 2]
            snippets = [
                f"Room acoustics at {row['name']} can be noisy at night.",
                "Late-night hallway noise impacted sleep quality.",
                "Service response was slower than expected for one request.",
                "A few maintenance issues were noticed during the stay.",
                "Check-in experience could be smoother during busy hours.",
            ]
        else:
            ratings = [5, 4, 5, 4, 5]
            snippets = [
                f"Great stay at {row['name']}; staff were warm and helpful.",
                "Location is convenient and easy for nearby activities.",
                "Breakfast quality was strong with good variety.",
                "Pool and common spaces were clean and pleasant.",
                "Value for money felt very good for the area.",
            ]

        for idx, (rating, snippet) in enumerate(zip(ratings, snippets), start=1):
            reviews.append(
                {
                    "source": "MockGoogle",
                    "rating": rating,
                    "best_rating": 5,
                    "date": f"{idx} months ago",
                    "snippet": snippet,
                    "user": {"name": f"Mock User {idx}"},
                }
            )
        return {"reviews": reviews}


def _normalize_candidates(
    properties: List[Dict[str, Any]], area: str, search_bucket: str, currency: str
) -> List[Dict[str, Any]]:
    normalized = []
    for idx, prop in enumerate(properties, start=1):
        coords = prop.get("gps_coordinates") or {}
        rate_per_night = _safe_float((prop.get("rate_per_night") or {}).get("extracted_lowest"))
        total_rate = _safe_float((prop.get("total_rate") or {}).get("extracted_lowest"))
        hotel_class = _safe_int(prop.get("extracted_hotel_class") or prop.get("hotel_class"))

        normalized.append(
            {
                "hotel_candidate_id": f"cand_{search_bucket}_{idx}_{random.randint(100,999)}",
                "source_search_buckets": [search_bucket],
                "search_areas": [area],
                "name": prop.get("name", "Unknown Hotel"),
                "property_token": prop.get("property_token"),
                "area": area,
                "price": {
                    "rate_per_night": rate_per_night,
                    "total_rate": total_rate,
                    "currency": currency,
                },
                "quality": {
                    "overall_rating": _safe_float(prop.get("overall_rating")),
                    "reviews": _safe_int(prop.get("reviews")) or 0,
                    "location_rating": _safe_float(prop.get("location_rating")),
                },
                "hotel_class": hotel_class,
                "amenities": prop.get("amenities") or [],
                "deal": prop.get("deal"),
                "deal_description": prop.get("deal_description"),
                "gps_coordinates": {
                    "latitude": _safe_float(coords.get("latitude")),
                    "longitude": _safe_float(coords.get("longitude")),
                },
                "area_validation": {
                    "status": "unverified",
                    "search_area": area,
                    "detected_area": None,
                    "evidence": None,
                },
            }
        )
    return normalized


def _dedupe_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: Dict[str, Dict[str, Any]] = {}
    for cand in candidates:
        token = cand.get("property_token")
        if token:
            key = f"token:{token}"
        else:
            lat = cand["gps_coordinates"].get("latitude")
            lng = cand["gps_coordinates"].get("longitude")
            lat_key = "na" if lat is None else round(lat, 2)
            lng_key = "na" if lng is None else round(lng, 2)
            key = f"name:{_norm_text(cand['name'])}:{lat_key}:{lng_key}"

        existing = deduped.get(key)
        if existing is None:
            deduped[key] = cand
            continue

        existing["source_search_buckets"] = sorted(
            set(existing["source_search_buckets"] + cand["source_search_buckets"])
        )
        existing["search_areas"] = sorted(set(existing.get("search_areas", []) + cand.get("search_areas", [])))
        old_price = existing["price"]["rate_per_night"]
        new_price = cand["price"]["rate_per_night"]
        if new_price is not None and (old_price is None or new_price < old_price):
            existing["price"] = cand["price"]
        existing["quality"]["reviews"] = max(
            existing["quality"]["reviews"], cand["quality"]["reviews"]
        )
        if (cand["quality"]["overall_rating"] or 0) > (
            existing["quality"]["overall_rating"] or 0
        ):
            existing["quality"]["overall_rating"] = cand["quality"]["overall_rating"]
        existing["amenities"] = sorted(set(existing["amenities"] + cand["amenities"]))
        if not existing.get("deal") and cand.get("deal"):
            existing["deal"] = cand["deal"]
            existing["deal_description"] = cand.get("deal_description")
    return list(deduped.values())


def _hard_reject_reasons(
    cand: Dict[str, Any], discovery_request: Dict[str, Any]
) -> List[str]:
    reasons = []
    prefs = discovery_request["hotel_preferences"]
    budget = discovery_request["budget"]
    price = cand["price"]["rate_per_night"]
    if price is None:
        reasons.append("missing_price")
    else:
        if price > float(budget["hotel_budget_per_night_hard_max"]):
            reasons.append("over_hard_max_budget")

    min_rating = _safe_float(prefs.get("minimum_rating"))
    rating = cand["quality"]["overall_rating"]
    if min_rating is not None and rating is not None and rating < min_rating:
        reasons.append("below_minimum_rating")

    preferred_classes = set(prefs.get("hotel_class_preference") or [])
    if preferred_classes and cand["hotel_class"] not in preferred_classes:
        reasons.append("hotel_class_mismatch")

    must_have = prefs.get("must_have_amenities") or []
    for amenity in must_have:
        if not _contains_amenity(cand["amenities"], amenity):
            reasons.append(f"missing_must_have_amenity:{amenity}")

    return reasons


def _budget_fit(price: float, target: float, hard_max: float) -> float:
    if price <= 0:
        return 0.0
    band_low = max(target * 0.73, 1.0)
    if price > hard_max:
        return 0.0

    if band_low <= price <= hard_max:
        max_dist = max(target - band_low, hard_max - target, 1.0)
        return max(0.0, 1.0 - abs(price - target) / max_dist)

    if price < band_low:
        drop = (band_low - price) / band_low
        return max(0.15, 0.7 - drop)

    return 0.0


def _quality_fit(
    rating: Optional[float],
    location_rating: Optional[float],
    hotel_class: Optional[int],
    preferred_classes: List[int],
) -> float:
    rating_score = 0.0 if rating is None else max(0.0, min(rating / 5.0, 1.0))
    location_score = (
        0.0 if location_rating is None else max(0.0, min(location_rating / 5.0, 1.0))
    )

    class_score = 0.4
    if hotel_class is not None and preferred_classes:
        if hotel_class in preferred_classes:
            class_score = 1.0
        elif any(abs(hotel_class - pref) == 1 for pref in preferred_classes):
            class_score = 0.6
        else:
            class_score = 0.2
    elif not preferred_classes:
        class_score = 1.0

    return 0.5 * rating_score + 0.3 * location_score + 0.2 * class_score


def _reviews_fit(reviews: int) -> float:
    return max(0.0, min(math.log1p(max(reviews, 0)) / math.log1p(5000), 1.0))


def _amenity_fit(
    amenities: List[str], must_have: List[str], nice_to_have: List[str]
) -> float:
    if not must_have and not nice_to_have:
        return 1.0

    if must_have:
        must_hits = sum(1 for a in must_have if _contains_amenity(amenities, a))
        must_ratio = must_hits / max(len(must_have), 1)
    else:
        must_ratio = 1.0

    if nice_to_have:
        nice_hits = sum(1 for a in nice_to_have if _contains_amenity(amenities, a))
        nice_ratio = nice_hits / max(len(nice_to_have), 1)
    else:
        nice_ratio = 1.0

    return 0.7 * must_ratio + 0.3 * nice_ratio


def _area_fit(area: str, allowed_areas: List[str]) -> float:
    if not allowed_areas:
        return 1.0
    return 1.0 if _norm_text(area) in {_norm_text(x) for x in allowed_areas} else 0.25


def _score_candidate(
    cand: Dict[str, Any], discovery_request: Dict[str, Any]
) -> Dict[str, float]:
    budget = discovery_request["budget"]
    prefs = discovery_request["hotel_preferences"]
    allowed_areas = discovery_request["destination"]["micro_areas"]

    price = cand["price"]["rate_per_night"] or 0.0
    budget_score = _budget_fit(
        price=price,
        target=float(budget["hotel_budget_per_night_target"]),
        hard_max=float(budget["hotel_budget_per_night_hard_max"]),
    )
    quality_score = _quality_fit(
        rating=cand["quality"]["overall_rating"],
        location_rating=cand["quality"]["location_rating"],
        hotel_class=cand["hotel_class"],
        preferred_classes=prefs["hotel_class_preference"],
    )
    reviews_score = _reviews_fit(cand["quality"]["reviews"])
    amenity_score = _amenity_fit(
        amenities=cand["amenities"],
        must_have=prefs["must_have_amenities"],
        nice_to_have=prefs["nice_to_have_amenities"],
    )
    area_score = _area_fit(cand["area"], allowed_areas)
    deal_score = 1.0 if cand.get("deal") else 0.0

    final_score = (
        SCORE_WEIGHTS["budget_fit"] * budget_score
        + SCORE_WEIGHTS["quality_fit"] * quality_score
        + SCORE_WEIGHTS["reviews_fit"] * reviews_score
        + SCORE_WEIGHTS["amenity_fit"] * amenity_score
        + SCORE_WEIGHTS["area_fit"] * area_score
        + SCORE_WEIGHTS["deal_bonus"] * deal_score
    )
    return {
        "budget_fit": round(budget_score, 4),
        "quality_fit": round(quality_score, 4),
        "reviews_fit": round(reviews_score, 4),
        "amenity_fit": round(amenity_score, 4),
        "area_fit": round(area_score, 4),
        "deal_bonus": round(deal_score, 4),
        "final_score": round(final_score, 4),
    }


def _build_why_selected(
    cand: Dict[str, Any], scores: Dict[str, float], discovery_request: Dict[str, Any]
) -> List[str]:
    reasons = []
    target = discovery_request["budget"]["hotel_budget_per_night_target"]
    nightly = cand["price"]["rate_per_night"]
    if nightly is not None:
        gap = abs(nightly - target)
        if gap <= target * 0.12:
            reasons.append("close to budget target")
        elif nightly < target:
            reasons.append("under budget target")
    if cand["quality"]["overall_rating"] and cand["quality"]["overall_rating"] >= 4.4:
        reasons.append("strong guest rating")
    if cand["quality"]["reviews"] >= 1000:
        reasons.append("strong review volume")
    if scores["amenity_fit"] >= 0.9:
        reasons.append("matches key amenity preferences")
    if cand.get("deal"):
        reasons.append("active deal signal")
    area_validation = cand.get("area_validation") or {}
    if area_validation.get("status") == "corrected":
        reasons.append("area corrected via geolocation validation")
    if not reasons:
        reasons.append("best composite score")
    return reasons[:4]


def _enrich_candidates(
    client: Any,
    candidates: List[Dict[str, Any]],
    discovery_request: Dict[str, Any],
    photos_per_hotel: int,
) -> Dict[str, int]:
    dates = discovery_request["dates"]
    destination = discovery_request["destination"]
    micro_areas = destination["micro_areas"]
    enriched_count = 0
    area_corrected_count = 0
    area_unknown_count = 0
    for cand in candidates:
        token = cand.get("property_token")
        if not token:
            continue
        params = {
            "engine": "google_hotels",
            "q": f"{cand['area']} {destination['city_or_region']} hotels",
            "property_token": token,
            "check_in_date": dates["check_in"],
            "check_out_date": dates["check_out"],
            "adults": str(discovery_request["party"]["adults"]),
            "children": str(discovery_request["party"]["children"]),
            "currency": discovery_request["budget"]["currency"],
            "gl": "in",
            "hl": "en",
        }
        details = client.hotel_details(params)
        if not details:
            continue
        enriched_count += 1
        cand["contact"] = {
            "phone": details.get("phone"),
            "address": details.get("address"),
            "link": details.get("link"),
        }
        cand["price_context"] = {
            "rate_per_night": _safe_float(
                (details.get("rate_per_night") or {}).get("extracted_lowest")
            ),
            "total_rate": _safe_float(
                (details.get("total_rate") or {}).get("extracted_lowest")
            ),
            "typical_price_range": details.get("typical_price_range"),
        }
        cand["nearby_places"] = details.get("nearby_places", [])
        cand["photos"] = _extract_photo_items(details, max_photos=photos_per_hotel)
        cand["_details_cache"] = details

        address = details.get("address") or ""
        nearby_text = " ".join(
            (place.get("name") or "")
            for place in details.get("nearby_places", [])[:15]
            if isinstance(place, dict)
        )
        detection_source = f"{address} {nearby_text}".strip()
        detected_area = _detect_area_from_text(detection_source, micro_areas)

        original_area = cand["area"]
        if detected_area is None:
            cand["area_validation"] = {
                "status": "unknown",
                "search_area": original_area,
                "detected_area": None,
                "evidence": "No strong area keyword match in address/nearby places",
            }
            area_unknown_count += 1
        elif _norm_text(detected_area) == _norm_text(original_area):
            cand["area_validation"] = {
                "status": "matched",
                "search_area": original_area,
                "detected_area": detected_area,
                "evidence": "Address/nearby places confirm search area",
            }
            cand["area"] = detected_area
        else:
            cand["area_validation"] = {
                "status": "corrected",
                "search_area": original_area,
                "detected_area": detected_area,
                "evidence": "Address/nearby places indicate a different micro-area",
            }
            cand["area"] = detected_area
            area_corrected_count += 1

    return {
        "details_enriched_count": enriched_count,
        "area_corrected_count": area_corrected_count,
        "area_unknown_count": area_unknown_count,
    }


def _collect_topic_reviews(
    client: Any,
    topic: Dict[str, Any],
    property_token: str,
    default_hl: str = "en",
) -> List[Dict[str, Any]]:
    topic_link = topic.get("serpapi_link")
    params: Dict[str, Any] = {}
    if isinstance(topic_link, str) and "search.json" in topic_link:
        params = _extract_serpapi_params_from_link(topic_link)
    if not params:
        if not topic.get("category_token"):
            return []
        params = {
            "engine": "google_hotels_reviews",
            "property_token": property_token,
            "category_token": topic.get("category_token"),
            "hl": default_hl,
        }

    if "engine" not in params:
        params["engine"] = "google_hotels_reviews"
    params["property_token"] = property_token
    params.setdefault("hl", default_hl)

    try:
        response = client.hotel_reviews(params)
    except Exception:
        return []
    return response.get("reviews", []) or []


def _select_review_snippets(
    details: Dict[str, Any],
    client: Any,
    target_count: int,
    topics_per_sentiment: int,
) -> Tuple[Dict[str, Any], int]:
    breakdown = details.get("reviews_breakdown") or []
    property_token = details.get("property_token")
    if not property_token:
        return {
            "total_reviews": _safe_int(details.get("reviews")) or 0,
            "overall_rating": _safe_float(details.get("overall_rating")),
            "top_positive_topics": [],
            "top_negative_topics": [],
            "snippets": [],
        }, 0

    positive_topics = sorted(
        [item for item in breakdown if _safe_int(item.get("positive")) and item.get("serpapi_link")],
        key=lambda x: _safe_int(x.get("positive")) or 0,
        reverse=True,
    )[:topics_per_sentiment]
    negative_topics = sorted(
        [item for item in breakdown if _safe_int(item.get("negative")) and item.get("serpapi_link")],
        key=lambda x: _safe_int(x.get("negative")) or 0,
        reverse=True,
    )[:topics_per_sentiment]

    fetched_reviews = []
    review_api_calls = 0
    for topic in positive_topics:
        review_api_calls += 1
        for review in _collect_topic_reviews(client, topic, property_token):
            fetched_reviews.append((review, topic, "positive_topic"))
    for topic in negative_topics:
        review_api_calls += 1
        for review in _collect_topic_reviews(client, topic, property_token):
            fetched_reviews.append((review, topic, "negative_topic"))

    seen = set()
    positives = []
    negatives = []
    mixed = []

    def _push(review_obj: Dict[str, Any], topic: Dict[str, Any], topic_signal: str) -> None:
        snippet = _clip_text(str(review_obj.get("snippet", "")).strip())
        if not snippet:
            return
        key = _norm_text(snippet)
        if key in seen:
            return
        seen.add(key)
        rating = _safe_float(review_obj.get("rating"))
        sentiment = _rating_to_sentiment(rating)
        item = {
            "topic": topic.get("name"),
            "topic_signal": topic_signal,
            "rating": rating,
            "source": review_obj.get("source"),
            "date": review_obj.get("date"),
            "author": ((review_obj.get("user") or {}).get("name")),
            "snippet": snippet,
            "sentiment": sentiment,
        }
        if sentiment == "positive":
            positives.append(item)
        elif sentiment == "negative":
            negatives.append(item)
        else:
            mixed.append(item)

    for review_obj, topic, topic_signal in fetched_reviews:
        _push(review_obj, topic, topic_signal)

    for ext in details.get("other_reviews", []) or []:
        user_review = (ext or {}).get("user_review") or {}
        rating = _safe_float(((user_review.get("rating") or {}).get("score")))
        snippet = _clip_text(str(user_review.get("comment", "")).strip())
        if not snippet:
            continue
        pseudo_review = {
            "rating": rating,
            "source": ext.get("source"),
            "date": user_review.get("date"),
            "snippet": snippet,
            "user": {"name": user_review.get("username")},
        }
        _push(
            review_obj=pseudo_review,
            topic={"name": "External reviews"},
            topic_signal="external",
        )

    positives.sort(key=lambda x: (x["rating"] or 0), reverse=True)
    negatives.sort(key=lambda x: (x["rating"] if x["rating"] is not None else 99))
    mixed.sort(key=lambda x: (x["rating"] or 0), reverse=True)

    selected = []
    min_negative = min(2, len(negatives))
    min_positive = min(max(3, target_count - min_negative), len(positives))
    selected.extend(positives[:min_positive])
    selected.extend(negatives[:min_negative])

    remaining = target_count - len(selected)
    if remaining > 0:
        leftovers = positives[min_positive:] + mixed + negatives[min_negative:]
        selected.extend(leftovers[:remaining])

    top_positive_topics = [
        {
            "name": item.get("name"),
            "positive": _safe_int(item.get("positive")) or 0,
            "negative": _safe_int(item.get("negative")) or 0,
            "total_mentioned": _safe_int(item.get("total_mentioned")) or 0,
        }
        for item in positive_topics
    ]
    top_negative_topics = [
        {
            "name": item.get("name"),
            "positive": _safe_int(item.get("positive")) or 0,
            "negative": _safe_int(item.get("negative")) or 0,
            "total_mentioned": _safe_int(item.get("total_mentioned")) or 0,
        }
        for item in negative_topics
    ]

    return {
        "total_reviews": _safe_int(details.get("reviews")) or 0,
        "overall_rating": _safe_float(details.get("overall_rating")),
        "top_positive_topics": top_positive_topics,
        "top_negative_topics": top_negative_topics,
        "snippets": selected[:target_count],
    }, review_api_calls


def _attach_review_insights(
    client: Any,
    candidates: List[Dict[str, Any]],
    snippets_per_hotel: int,
    topics_per_sentiment: int,
) -> Dict[str, int]:
    hotels_with_reviews = 0
    total_review_api_calls = 0
    for cand in candidates:
        details = cand.get("_details_cache") or {}
        if not details:
            continue
        insights, api_calls = _select_review_snippets(
            details=details,
            client=client,
            target_count=snippets_per_hotel,
            topics_per_sentiment=topics_per_sentiment,
        )
        cand["review_insights"] = insights
        total_review_api_calls += api_calls
        if insights.get("snippets"):
            hotels_with_reviews += 1
    return {
        "hotels_with_review_snippets": hotels_with_reviews,
        "review_api_calls": total_review_api_calls,
    }


def _pick_final_five(
    ranked_candidates: List[Dict[str, Any]], micro_areas: List[str]
) -> List[Dict[str, Any]]:
    if not ranked_candidates:
        return []

    selected: List[Dict[str, Any]] = []
    selected_tokens: set[str] = set()

    grouped: Dict[str, List[Dict[str, Any]]] = {area: [] for area in micro_areas}
    for cand in ranked_candidates:
        area = cand["area"]
        grouped.setdefault(area, []).append(cand)

    if len(micro_areas) >= 2:
        for area in micro_areas[:2]:
            picks = grouped.get(area, [])[:2]
            for cand in picks:
                token = cand.get("property_token") or cand["name"]
                if token in selected_tokens:
                    continue
                selected.append(cand)
                selected_tokens.add(token)

    for cand in ranked_candidates:
        if len(selected) >= 5:
            break
        token = cand.get("property_token") or cand["name"]
        if token in selected_tokens:
            continue
        selected.append(cand)
        selected_tokens.add(token)

    return selected[:5]


@dataclass
class Phase1Config:
    include_social_proof_search: bool = False
    provisional_cutoff: int = 12
    final_shortlist_size: int = 5
    include_review_snippets: bool = True
    review_snippets_per_hotel: int = 8
    review_topics_per_sentiment: int = 2
    photos_per_hotel: int = 6


def run_phase1_shortlist(
    selected_itinerary: Dict[str, Any], client: Any, config: Optional[Phase1Config] = None
) -> Dict[str, Any]:
    cfg = config or Phase1Config()
    discovery_request = build_hotel_discovery_request(selected_itinerary)
    search_jobs = build_search_jobs(
        discovery_request, include_social_proof=cfg.include_social_proof_search
    )

    raw_results = []
    normalized_candidates = []
    for job in search_jobs:
        response = client.search_hotels(job["params"])
        props = response.get("properties", [])
        raw_results.append(
            {
                "area": job["area"],
                "search_bucket": job["search_bucket"],
                "params": job["params"],
                "result_count": len(props),
            }
        )
        normalized_candidates.extend(
            _normalize_candidates(
                properties=props,
                area=job["area"],
                search_bucket=job["search_bucket"],
                currency=discovery_request["budget"]["currency"],
            )
        )
        time.sleep(0.01)

    deduped = _dedupe_candidates(normalized_candidates)

    accepted = []
    rejected = []
    for cand in deduped:
        reasons = _hard_reject_reasons(cand, discovery_request)
        if reasons:
            rejected.append({"candidate": cand, "reasons": reasons})
            continue
        accepted.append(cand)

    for cand in accepted:
        cand["scores"] = _score_candidate(cand, discovery_request)
        cand["why_selected"] = _build_why_selected(
            cand=cand, scores=cand["scores"], discovery_request=discovery_request
        )

    ranked = sorted(accepted, key=lambda x: x["scores"]["final_score"], reverse=True)
    provisional = ranked[: cfg.provisional_cutoff]
    enrichment_stats = _enrich_candidates(
        client=client,
        candidates=provisional,
        discovery_request=discovery_request,
        photos_per_hotel=cfg.photos_per_hotel,
    )

    for cand in provisional:
        cand["scores"] = _score_candidate(cand, discovery_request)
        cand["why_selected"] = _build_why_selected(
            cand=cand, scores=cand["scores"], discovery_request=discovery_request
        )
    provisional_ranked = sorted(
        provisional, key=lambda x: x["scores"]["final_score"], reverse=True
    )

    final_candidates = _pick_final_five(
        ranked_candidates=provisional_ranked,
        micro_areas=discovery_request["destination"]["micro_areas"],
    )[: cfg.final_shortlist_size]

    review_stats = {
        "hotels_with_review_snippets": 0,
        "review_api_calls": 0,
    }
    if cfg.include_review_snippets:
        review_stats = _attach_review_insights(
            client=client,
            candidates=final_candidates,
            snippets_per_hotel=cfg.review_snippets_per_hotel,
            topics_per_sentiment=cfg.review_topics_per_sentiment,
        )

    top_5_hotels = []
    for rank, cand in enumerate(final_candidates, start=1):
        top_5_hotels.append(
            {
                "rank": rank,
                "name": cand["name"],
                "property_token": cand.get("property_token"),
                "area": cand["area"],
                "nightly_price": cand["price"]["rate_per_night"],
                "currency": cand["price"]["currency"],
                "rating": cand["quality"]["overall_rating"],
                "reviews": cand["quality"]["reviews"],
                "hotel_class": cand["hotel_class"],
                "amenities": cand["amenities"],
                "phone": (cand.get("contact") or {}).get("phone"),
                "address": (cand.get("contact") or {}).get("address"),
                "link": (cand.get("contact") or {}).get("link"),
                "typical_price_range": (cand.get("price_context") or {}).get(
                    "typical_price_range"
                ),
                "scores": cand["scores"],
                "why_selected": cand["why_selected"],
                "source_search_buckets": cand["source_search_buckets"],
                "search_areas": cand.get("search_areas", []),
                "area_validation": cand.get("area_validation"),
                "review_insights": cand.get("review_insights", {}),
                "photos": cand.get("photos", []),
            }
        )

    shortlist = {
        "shortlist_id": f"short_{selected_itinerary['trip_request_id']}",
        "generated_at": _utc_now_iso(),
        "selected_itinerary_id": selected_itinerary["selected_itinerary_id"],
        "discovery_request": discovery_request,
        "search_stats": {
            "search_jobs": raw_results,
            "raw_candidates_count": len(normalized_candidates),
            "deduped_candidates_count": len(deduped),
            "rejected_count": len(rejected),
            "accepted_count": len(accepted),
            "provisional_count": len(provisional),
            "details_enriched_count": enrichment_stats["details_enriched_count"],
            "area_corrected_count": enrichment_stats["area_corrected_count"],
            "area_unknown_count": enrichment_stats["area_unknown_count"],
            "hotels_with_review_snippets": review_stats["hotels_with_review_snippets"],
            "review_api_calls": review_stats["review_api_calls"],
        },
        "top_5_hotels": top_5_hotels,
    }
    return shortlist


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)
        f.write("\n")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Phase 1 hotel discovery + enrichment pipeline."
    )
    parser.add_argument(
        "--selected-itinerary",
        required=True,
        help="Path to selected itinerary JSON (Layer 1).",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Path to write shortlist JSON output.",
    )
    parser.add_argument(
        "--mock-inventory",
        default="examples/mock_hotels_inventory.json",
        help="Path to mock hotel inventory JSON for offline testing.",
    )
    parser.add_argument(
        "--serpapi-key",
        default="",
        help="SerpApi key. If omitted, mock mode is used.",
    )
    parser.add_argument(
        "--include-social-proof-search",
        action="store_true",
        help="Add sort_by=13 search bucket.",
    )
    parser.add_argument(
        "--provisional-cutoff",
        type=int,
        default=12,
        help="Count of ranked hotels to enrich before final top 5.",
    )
    parser.add_argument(
        "--review-snippets-per-hotel",
        type=int,
        default=8,
        help="How many mixed good/bad review snippets to include per shortlisted hotel.",
    )
    parser.add_argument(
        "--disable-review-snippets",
        action="store_true",
        help="Disable review snippet enrichment for top hotels.",
    )
    parser.add_argument(
        "--photos-per-hotel",
        type=int,
        default=6,
        help="Number of photos to include per shortlisted hotel.",
    )
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    selected_itinerary = _read_json(args.selected_itinerary)
    cfg = Phase1Config(
        include_social_proof_search=args.include_social_proof_search,
        provisional_cutoff=max(args.provisional_cutoff, 5),
        final_shortlist_size=5,
        include_review_snippets=not args.disable_review_snippets,
        review_snippets_per_hotel=max(1, min(args.review_snippets_per_hotel, 10)),
        review_topics_per_sentiment=2,
        photos_per_hotel=max(1, min(args.photos_per_hotel, 12)),
    )

    if args.serpapi_key:
        client = SerpApiClient(api_key=args.serpapi_key)
    else:
        inventory = _read_json(args.mock_inventory)["hotels"]
        client = MockSerpApiClient(inventory=inventory)

    shortlist = run_phase1_shortlist(
        selected_itinerary=selected_itinerary, client=client, config=cfg
    )
    _write_json(args.out, shortlist)

    print(f"Shortlist generated: {args.out}")
    print(f"Top hotels returned: {len(shortlist['top_5_hotels'])}")


if __name__ == "__main__":
    main()
