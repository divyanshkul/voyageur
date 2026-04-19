"""Preference Agent -- integration layer (Phase 1-int).

Wires prompt engineering (1a), conversation manager (1b), and validation (1c)
into a single PreferenceAgent that extracts structured TravelPreferences from
a multi-turn chat with the user.
"""

from __future__ import annotations

import logging
import time

from app.models import TravelPreferences
from app.agents.preference_conversation import PreferenceConversation
from app.agents.preference_validation import (
    apply_defaults,
    normalize_destination,
    validate_preferences,
)

logger = logging.getLogger(__name__)


class PreferenceAgent:
    """Top-level agent that manages the preference-collection flow."""

    def __init__(self, openai_client) -> None:
        """
        Args:
            openai_client: An ``openai.AsyncOpenAI`` instance.
        """
        self._conversation = PreferenceConversation(openai_client)

    async def run(
        self, messages: list[dict]
    ) -> tuple[str, TravelPreferences | None]:
        """Process the latest user message through the preference pipeline.

        Returns:
            ``(agent_reply, None)`` while still collecting.
            ``(summary, TravelPreferences)`` when extraction and validation pass.
        """
        start = time.time()

        # Take the most recent user message
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        if not user_message:
            return "I didn't catch that -- could you tell me about your trip?", None

        reply, prefs = await self._conversation.process_message(user_message)
        elapsed_ms = (time.time() - start) * 1000

        # -- Still collecting ----------------------------------------------
        if prefs is None:
            logger.info(
                "preference_agent collecting",
                extra={"stage": "collecting", "latency_ms": f"{elapsed_ms:.0f}"},
            )
            return reply or "", None

        # -- Extraction complete -- run post-processing --------------------
        logger.info("preference_agent extraction complete, running post-processing")

        # 1. Normalize destination
        normalised_dest = normalize_destination(prefs.destination)
        prefs = prefs.model_copy(update={"destination": normalised_dest})

        # 2. Apply defaults for optional fields
        prefs = apply_defaults(prefs)

        # 3. Validate
        valid, issues = validate_preferences(prefs)

        if not valid:
            issue_text = ", ".join(issues)
            error_reply = (
                f"Hmm, a few things need fixing: {issue_text}. "
                f"Could you help me correct those?"
            )
            logger.info(
                "preference_agent validation failed",
                extra={"issues": issues, "latency_ms": f"{elapsed_ms:.0f}"},
            )
            return error_reply, None

        # 4. Build consultant-style summary
        nights = (prefs.check_out - prefs.check_in).days
        origin_part = f"{prefs.origin_city} to " if prefs.origin_city else ""
        group_part = f", {prefs.group_type} trip" if prefs.group_type else ""
        intent_part = f", {prefs.trip_intent}" if prefs.trip_intent else ""
        food_part = f", {prefs.food_pref} food" if prefs.food_pref != "both" else ""
        visit_part = ""
        if prefs.must_visit_places:
            visit_part = f", must include {', '.join(prefs.must_visit_places)}"
        budget_str = f"Rs.{prefs.budget_max:,}/night"
        if prefs.budget_total_trip:
            budget_str = f"Rs.{prefs.budget_total_trip:,} total (Rs.{prefs.budget_max:,}/night)"

        summary = (
            f"Here's what I've got: {origin_part}{prefs.destination}, "
            f"{nights} nights ({prefs.check_in} to {prefs.check_out})"
            f"{group_part}{intent_part}, budget around {budget_str}, "
            f"{prefs.guests} guest{'s' if prefs.guests > 1 else ''}"
            f"{food_part}{visit_part}.\n\n"
            f"I'll start searching for the best hotel options now."
        )

        elapsed_ms = (time.time() - start) * 1000
        logger.info(
            "preference_agent complete",
            extra={
                "stage": "complete",
                "destination": prefs.destination,
                "latency_ms": f"{elapsed_ms:.0f}",
            },
        )
        return summary, prefs
