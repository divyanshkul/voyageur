"""LLM-powered report generation (Phase 4b).

Uses GPT-4o to generate a natural-language summary and recommendation from
the hotel comparison data, then assembles the full Report object.
"""

import json
import logging
import time

from app.models import HotelComparison, Report, TravelPreferences

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are Voyageur, a travel concierge. Write a brief 2-3 sentence summary "
    "recommending the best hotel option for this guest. Mention the top pick by "
    "name, the savings vs online booking platforms, and one key feature matching "
    "their preferences. Be direct and helpful."
)


async def generate_report(
    comparisons: list[HotelComparison],
    prefs: TravelPreferences,
    openai_client,
) -> Report:
    """Generate a Report with an LLM-written summary.

    Calls GPT-4o for a natural-language recommendation, selects the top pick,
    and assembles the full Report object.
    """
    start_time = time.time()

    # Build user message payload
    user_payload = {
        "preferences": prefs.model_dump(mode="json"),
        "comparisons": [c.model_dump(mode="json") for c in comparisons],
    }
    user_message = json.dumps(user_payload, indent=2, default=str)

    # Call GPT-4o for the summary
    response = await openai_client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
        max_completion_tokens=300,
    )

    summary = response.choices[0].message.content.strip()
    tokens_used = response.usage.total_tokens if response.usage else None

    # Determine top_pick
    top_pick: HotelComparison | None = None

    # First: cheapest with availability
    for c in comparisons:
        if c.verdict == "cheaper" and c.call_result.availability is True:
            top_pick = c
            break

    # Fallback: any available hotel
    if top_pick is None:
        for c in comparisons:
            if c.call_result.availability is True:
                top_pick = c
                break

    # Fallback: first overall
    if top_pick is None and comparisons:
        top_pick = comparisons[0]

    # Compute average savings percent
    savings_values = [
        c.savings_percent for c in comparisons if c.savings_percent is not None
    ]
    average_savings_percent = (
        round(sum(savings_values) / len(savings_values), 1)
        if savings_values
        else None
    )

    report = Report(
        preferences=prefs,
        comparisons=comparisons,
        top_pick=top_pick,
        average_savings_percent=average_savings_percent,
        summary=summary,
        markdown="",  # Filled by integration layer via formatter
    )

    elapsed_ms = round((time.time() - start_time) * 1000)

    logger.info(
        "report_generated | top_pick=%s avg_savings=%s summary_len=%d tokens=%s latency_ms=%d",
        top_pick.hotel.name if top_pick else "none",
        f"{average_savings_percent}%" if average_savings_percent is not None else "N/A",
        len(summary),
        tokens_used,
        elapsed_ms,
    )

    return report
