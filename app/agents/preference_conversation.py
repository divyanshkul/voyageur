"""Preference conversation manager (Phase 1b).

Manages multi-turn chat with the user to collect travel preferences.
Each call to process_message() either returns an agent reply (still collecting)
or a completed TravelPreferences object.
"""

from __future__ import annotations

import json
import logging
import time

from app.models import TravelPreferences
from app.agents.preference_prompts import get_system_prompt, PREFERENCE_TOOLS

logger = logging.getLogger(__name__)


class PreferenceConversation:
    """Multi-turn conversation that extracts TravelPreferences via GPT-4o."""

    def __init__(self, openai_client) -> None:
        """
        Args:
            openai_client: An ``openai.AsyncOpenAI`` instance.
        """
        self._client = openai_client
        self._history: list[dict] = []
        self._extracted_state: dict = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_message(
        self, user_message: str
    ) -> tuple[str | None, TravelPreferences | None]:
        """Process one user turn.

        Returns:
            ``(agent_reply, None)`` if still collecting.
            ``(confirmation_message, TravelPreferences)`` when extraction is done.
        """
        logger.debug("process_message called", extra={"user_message": user_message})
        self._history.append({"role": "user", "content": user_message})

        messages = [
            {"role": "system", "content": get_system_prompt()},
            *self._history,
        ]

        start = time.time()
        response = await self._client.chat.completions.create(
            model="gpt-5.4",
            messages=messages,
            tools=PREFERENCE_TOOLS,
            tool_choice="auto",
        )
        latency_ms = (time.time() - start) * 1000
        choice = response.choices[0]
        usage = response.usage

        logger.info(
            "openai chat completion",
            extra={
                "message_count": len(self._history),
                "latency_ms": f"{latency_ms:.0f}",
                "prompt_tokens": usage.prompt_tokens if usage else None,
                "completion_tokens": usage.completion_tokens if usage else None,
            },
        )

        # -- Tool call path: extraction triggered --------------------------
        if choice.message.tool_calls:
            tool_call = choice.message.tool_calls[0]
            raw_args = tool_call.function.arguments
            args = json.loads(raw_args)

            logger.info(
                "extract_preferences tool called",
                extra={"extracted_fields": list(args.keys())},
            )

            # Build TravelPreferences from the extracted arguments
            prefs = TravelPreferences(**args)
            self._extracted_state = args

            # Append the assistant's tool-call message and a synthetic tool
            # response so the history stays valid for any follow-up turns.
            self._history.append(choice.message.model_dump())
            self._history.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({"status": "ok"}),
                }
            )

            confirmation = (
                f"Got it! Here's what I have:\n"
                f"- Destination: {prefs.destination}\n"
                f"- Dates: {prefs.check_in} to {prefs.check_out}\n"
                f"- Budget: {'Rs.' + str(prefs.budget_min) + '-' if prefs.budget_min else 'up to Rs.'}"
                f"{prefs.budget_max}/night\n"
                f"- Guests: {prefs.guests}"
            )
            return confirmation, prefs

        # -- Text path: still collecting -----------------------------------
        assistant_text = choice.message.content or ""
        self._history.append({"role": "assistant", "content": assistant_text})

        logger.debug(
            "still collecting preferences",
            extra={"message_count": len(self._history)},
        )
        return assistant_text, None

    def get_current_state(self) -> dict:
        """Return what has been discussed / extracted so far (for debugging)."""
        return {
            "message_count": len(self._history),
            "extracted": self._extracted_state,
        }
