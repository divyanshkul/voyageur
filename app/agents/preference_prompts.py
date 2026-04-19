"""Preference extraction prompts and tool schemas (Phase 1a).

Implements the Chat Intake Agent spec: acts as a smart travel consultant,
not a survey form. Collects trip preferences incrementally through natural
conversation, following priority-based slot filling and stage-based flow.
"""

import logging
from datetime import date as _date

from app.models import TravelPreferences  # noqa: F401 (used by importers)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------
_PREFERENCE_SYSTEM_PROMPT_TEMPLATE: str = """\
You are Voyageur, a smart travel consultant -- not a form, not a generic chatbot.

**Today's date is {today}.**
Resolve relative dates ("tomorrow", "next weekend", "this Friday") into YYYY-MM-DD.

=== YOUR ROLE ===
Collect enough trip information to hand off to the planning layer.
You do NOT generate itineraries, recommend hotels, or book anything.
You ONLY gather, clarify, and confirm.

=== CONVERSATION PHILOSOPHY ===
Behave like an experienced travel consultant having a real conversation:
- Ask at most 1-2 questions per turn
- Combine RELATED questions naturally ("Where from, how long, and who's joining?")
- Never repeat a question the user already answered
- Infer what you safely can (e.g., "couple trip" = 2 adults, "we" = 2+ people)
- Stop asking once you have enough to plan
- Be warm, concise, adaptive, and non-repetitive

=== CONVERSATION STAGES ===
Follow this natural flow. Skip stages where the user already provided info.

STAGE 1 — OPENING (destination + origin + duration)
Start with ONE broad question:
"Tell me about the trip — where are you thinking of going, from where, and roughly how long?"
If user gives partial info, ask only what's missing.

STAGE 2 — TRIP FRAMING (who + vibe)
"Is this solo, couple, friends, or family? And do you want it to feel more relaxed, \
sightseeing-heavy, or adventure-packed?"

STAGE 3 — BUDGET (total or per-night)
"What total budget should I plan around, excluding flights?"
Accept ranges ("around 70k", "4-5k per night"). Extract both total and per-night if given.
If they give per-night, calculate total using the duration.
If they give total, calculate per-night using the duration.

STAGE 4 — CONSTRAINTS (dietary, must-visit, preferences)
Ask ONE smart question that captures multiple things:
"Any dietary preferences or anything I should account for — like veg food, \
quiet stay, specific places you want to include, or anything to avoid?"

STAGE 5 — SUMMARY CONFIRMATION
Before extracting, summarize EVERYTHING you understood in 2-3 sentences:
"Got it — [origin] to [destination], [nights] nights, [group type] trip, \
[pace/vibe], around [budget], [dietary], [must-visit]. I'll use that to find \
the best options."

Then call extract_preferences.

=== SLOT PRIORITY ===
Priority 1 (ask first): destination, origin_city, dates/duration, group_type, budget
Priority 2 (ask next): trip_intent, pace, must_visit_places, food_pref
Priority 3 (ask if natural): amenities, smoking, alcohol, language_pref, special_requests

Always ask: "What is the most important missing piece?" NOT "What haven't I asked?"

=== INDIAN CONTEXT ===
- "Coorg" is in Karnataka. "Goa" implies beach.
- "4-5k" means INR 4000-5000
- "next weekend" → resolve to actual dates using today's date
- "couple trip" = group_type="couple", adults=2
- "family trip" = group_type="family", ask about children
- "solo" = group_type="solo", adults=1
- "Bangalore" → origin_city="Bengaluru"

=== HARD RULES ===
- NEVER ask more than 2 questions in a single message
- NEVER ask about something the user already told you
- NEVER make up information — leave fields null if not mentioned
- ALWAYS confirm before calling extract_preferences
- ALWAYS include origin_city if the user mentioned where they're coming from
- Keep the total intake to 3-5 turns max
"""


def get_system_prompt() -> str:
    """Return the system prompt with today's date injected."""
    return _PREFERENCE_SYSTEM_PROMPT_TEMPLATE.format(today=_date.today().isoformat())


# Keep static reference for backward compat
PREFERENCE_SYSTEM_PROMPT = get_system_prompt()


# ---------------------------------------------------------------------------
# Tool schema — enriched with spec fields
# ---------------------------------------------------------------------------
PREFERENCE_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "extract_preferences",
            "description": (
                "Extract the user's confirmed travel preferences. Call this "
                "ONLY after you have summarized the trip back to the user and "
                "all required fields (destination, dates, budget, guests) are present."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "Trip destination (city/region, e.g. 'Coorg', 'Bali', 'Goa').",
                    },
                    "origin_city": {
                        "type": "string",
                        "description": "Where the traveler is coming from (e.g. 'Bengaluru'). Null if not mentioned.",
                    },
                    "check_in": {
                        "type": "string",
                        "description": "Check-in date YYYY-MM-DD.",
                    },
                    "check_out": {
                        "type": "string",
                        "description": "Check-out date YYYY-MM-DD.",
                    },
                    "budget_min": {
                        "type": "integer",
                        "description": "Min budget per night INR. Null if not a range.",
                    },
                    "budget_max": {
                        "type": "integer",
                        "description": "Max budget per night INR.",
                    },
                    "guests": {
                        "type": "integer",
                        "description": "Total number of guests (adults + children).",
                    },
                    "group_type": {
                        "type": "string",
                        "enum": ["solo", "couple", "friends", "family"],
                        "description": "Who is traveling.",
                    },
                    "children": {
                        "type": "integer",
                        "description": "Number of children (0 if not mentioned).",
                    },
                    "trip_intent": {
                        "type": "string",
                        "enum": ["relaxation", "sightseeing", "adventure", "mixed", "business"],
                        "description": "Primary trip vibe/goal.",
                    },
                    "pace": {
                        "type": "string",
                        "enum": ["slow", "medium", "packed"],
                        "description": "Desired trip pace.",
                    },
                    "must_visit_places": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific places the user wants to visit.",
                    },
                    "must_avoid": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Things to avoid.",
                    },
                    "budget_total_trip": {
                        "type": "integer",
                        "description": "Total trip budget excluding flights (INR). Null if only per-night given.",
                    },
                    "budget_flexibility": {
                        "type": "string",
                        "enum": ["strict", "can_stretch_10_percent", "flexible"],
                        "description": "How flexible the budget is.",
                    },
                    "star_rating": {
                        "type": "integer",
                        "description": "Preferred min star rating (1-5).",
                    },
                    "food_pref": {
                        "type": "string",
                        "enum": ["veg", "non-veg", "both"],
                        "description": "Dietary preference.",
                    },
                    "smoking": {
                        "type": "boolean",
                        "description": "Smoking room needed.",
                    },
                    "alcohol": {
                        "type": "boolean",
                        "description": "Alcohol availability matters.",
                    },
                    "amenities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Desired amenities (pool, wifi, parking, etc.).",
                    },
                    "language_pref": {
                        "type": "string",
                        "enum": ["kannada", "hindi", "english"],
                        "description": "Preferred language for hotel calls.",
                    },
                    "special_requests": {
                        "type": "string",
                        "description": "Special requests (anniversary, accessibility, etc.).",
                    },
                },
                "required": [
                    "destination",
                    "check_in",
                    "check_out",
                    "budget_max",
                    "guests",
                ],
            },
        },
    }
]


# ---------------------------------------------------------------------------
# Few-shot examples
# ---------------------------------------------------------------------------
EXTRACTION_EXAMPLES: list[dict] = [
    {
        "input": "I want to plan a Bali trip.",
        "response": (
            "Nice. Where are you traveling from, how many nights are you "
            "thinking, and is this solo, couple, friends, or family?"
        ),
        "reasoning": "One broad question covering origin, duration, and group type.",
    },
    {
        "input": "From Bangalore, 5 nights, couple trip.",
        "response": (
            "Got it. Do you want this to feel more relaxed, more sightseeing-heavy, "
            "or more activity-heavy? And what total budget should I plan around, "
            "excluding flights?"
        ),
        "reasoning": "Trip vibe + budget in one turn. Only 2 questions.",
    },
    {
        "input": "Relaxed mostly, but not too boring. Budget maybe 70k.",
        "response": (
            "Perfect. Any dietary preference or anything important I should "
            "account for — like veg food, quiet stay, or places you definitely "
            "want included?"
        ),
        "reasoning": "One smart question covering dietary, stay pref, and must-visits.",
    },
    {
        "input": "Vegetarian. And I definitely want Uluwatu.",
        "response": (
            "Great — I've got Bengaluru to Bali, 5 nights, couple trip, relaxed "
            "but not dull, around Rs.70,000 excluding flights, vegetarian preference, "
            "and Uluwatu as a must. I'll use that to find the best options."
        ),
        "reasoning": "Summary confirmation, then call extract_preferences.",
    },
]


logger.debug(
    "preference_prompts loaded prompt_len=%d tools=%d examples=%d",
    len(PREFERENCE_SYSTEM_PROMPT),
    len(PREFERENCE_TOOLS),
    len(EXTRACTION_EXAMPLES),
)
