"""Research brain -- LLM-powered search query generation (Phase 2d).

Generates intelligent Google Places search queries from preferences, decides
whether to broaden searches with too few results, and formats the hotel
shortlist for user approval.
"""

import json
import logging

from app.models import Hotel, TravelPreferences

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Query generation (LLM-powered)
# ---------------------------------------------------------------------------

async def generate_search_queries(
    prefs: TravelPreferences,
    openai_client,
) -> list[str]:
    """Use GPT-4o to generate 1-3 Google Places search queries."""
    fallback = [f"hotels in {prefs.destination}"]
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-5.4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generate 1-3 Google Places text search queries to find "
                        "hotels matching these preferences. Return as JSON array "
                        "of strings. Consider the Indian location, budget range, "
                        "and amenity preferences."
                    ),
                },
                {
                    "role": "user",
                    "content": prefs.model_dump_json(),
                },
            ],
            temperature=0.3,
        )

        raw = response.choices[0].message.content or ""
        # Strip markdown fences if LLM wraps the JSON
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]
            raw = raw.strip()

        queries: list[str] = json.loads(raw)
        if not isinstance(queries, list) or not queries:
            raise ValueError("LLM returned non-list or empty list")

        tokens_used = getattr(response.usage, "total_tokens", "N/A")
        logger.info(
            "generate_search_queries | destination=%s | queries=%s | tokens=%s",
            prefs.destination, queries, tokens_used,
        )
        return queries

    except Exception as exc:
        logger.warning(
            "generate_search_queries | LLM failed (%s), using fallback query",
            exc,
        )
        return fallback


# ---------------------------------------------------------------------------
# Search broadening decision
# ---------------------------------------------------------------------------

def should_broaden_search(
    results: list[Hotel],
    prefs: TravelPreferences,
) -> tuple[bool, str | None]:
    """Decide whether a broader search is needed.  Returns (should_broaden, query)."""
    if len(results) < 3:
        query = f"hotels in {prefs.destination}"
        logger.info(
            "should_broaden_search | results=%d (<3) | broadening with: %s",
            len(results), query,
        )
        return True, query

    if (
        results
        and all(h.ota_price is not None for h in results)
        and all(h.ota_price > prefs.budget_max for h in results)  # type: ignore[operator]
    ):
        query = f"budget hotels in {prefs.destination}"
        logger.info(
            "should_broaden_search | all %d results over budget | broadening with: %s",
            len(results), query,
        )
        return True, query

    logger.info(
        "should_broaden_search | results=%d | no broadening needed",
        len(results),
    )
    return False, None


# ---------------------------------------------------------------------------
# Shortlist formatting for user approval
# ---------------------------------------------------------------------------

def format_shortlist_for_approval(hotels: list[Hotel]) -> str:
    """Format a numbered hotel shortlist for the user to approve."""
    lines: list[str] = ["Here are the best matches I found:\n"]

    for i, h in enumerate(hotels, start=1):
        price_str = f"~Rs.{h.ota_price:,}/night" if h.ota_price else "Price: checking..."
        amenities_str = ", ".join(h.amenities) if h.amenities else "N/A"
        lines.append(
            f"{i}. {h.name} ({h.rating}*) - {h.address}\n"
            f"   OTA Price: {price_str} | {amenities_str}\n"
        )

    lines.append(
        "Which hotels should I call to get their direct rates? "
        "(Reply with numbers like '1, 3' or 'all')"
    )

    logger.info("format_shortlist_for_approval | hotels_formatted=%d", len(hotels))
    return "\n".join(lines)
