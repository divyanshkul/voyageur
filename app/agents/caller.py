"""Calling Agent -- integration layer (Phase 3-int).

Wires the Bolna API client (3a), webhook handler (3b), call prompt builder (3c),
and call orchestrator (3d) into a single CallingAgent that phones approved
hotels and returns structured CallResult objects.
"""

from __future__ import annotations

import logging

from app.agents.caller_orchestrator import CallOrchestrator
from app.agents.caller_prompts import build_call_prompt
from app.config import Settings
from app.models import CallResult, Hotel, TravelPreferences
from app.services.bolna import BolnaClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language → Sarvam locale mapping (used for transcriber + synthesizer)
# ---------------------------------------------------------------------------
_LANGUAGE_TO_SARVAM: dict[str, str] = {
    "kannada": "kn-IN",
    "hindi": "hi-IN",
    "english": "en-IN",
}

# Bodhi transcriber model mapping (per Bolna API spec)
_LANGUAGE_TO_BODHI_MODEL: dict[str, str] = {
    "kannada": "kn-general-v2-8khz",
    "hindi": "hi-general-v2-8khz",
    "english": "hi-general-v2-8khz",  # fallback to Hindi for English+India
}

_LANGUAGE_TO_BODHI_LANG: dict[str, str] = {
    "kannada": "kn",
    "hindi": "hi",
    "english": "hi",
}


class CallingAgent:
    """Top-level calling agent: creates a Bolna agent, then calls hotels."""

    def __init__(self, config: Settings, openai_client) -> None:
        self._bolna = BolnaClient(config.bolna_api_key)
        self._openai = openai_client
        self._config = config
        self._agent_id: str | None = None

    # ------------------------------------------------------------------
    # Lazy Bolna agent creation
    # ------------------------------------------------------------------
    async def _ensure_agent(self, prefs: TravelPreferences) -> str:
        """Create (or reuse) a Bolna voice agent configured for *prefs*.

        The agent uses:
          - Sarvam ``saaras:v3`` for transcription (STT)
          - Sarvam ``bulbul:v3`` for synthesis (TTS)
          - OpenAI ``gpt-4o`` for the LLM

        Returns:
            The Bolna ``agent_id``.
        """
        if self._agent_id is not None:
            return self._agent_id

        sarvam_lang = _LANGUAGE_TO_SARVAM.get(
            prefs.language_pref,
            self._config.bolna_agent_language,
        )

        # Build a generic system prompt -- the per-hotel prompt is injected
        # via user_data at call time, but we need a base prompt for the agent.
        sample_prompt = (
            "You are a polite hotel-booking assistant calling on behalf of a "
            "guest. Follow the user's instructions for each call carefully."
        )

        # Bodhi transcriber config for Indian languages
        bodhi_model = _LANGUAGE_TO_BODHI_MODEL.get(
            prefs.language_pref, "hi-general-v2-8khz"
        )
        bodhi_lang = _LANGUAGE_TO_BODHI_LANG.get(
            prefs.language_pref, "hi"
        )

        # --- Bolna v2 agent_config (matches verified OpenAPI spec) ---
        agent_config: dict = {
            "agent_name": "voyageur-hotel-caller",
            "agent_type": "other",
            "agent_welcome_message": "Hello, I am calling on behalf of a guest.",
            "webhook_url": self._config.bolna_webhook_url,
            "tasks": [
                {
                    "task_type": "conversation",
                    "tools_config": {
                        "llm_agent": {
                            "agent_type": "simple_llm_agent",
                            "agent_flow_type": "streaming",
                            "llm_config": {
                                "provider": "openai",
                                "family": "openai",
                                "model": "gpt-4o",
                                "agent_flow_type": "streaming",
                                "max_tokens": 150,
                                "temperature": 0.2,
                            },
                        },
                        "synthesizer": {
                            "provider": "sarvam",
                            "provider_config": {
                                "voice": "anushka",
                                "voice_id": "anushka",
                                "model": "bulbul:v2",
                                "language": sarvam_lang,
                            },
                            "stream": True,
                            "buffer_size": 250,
                            "audio_format": "wav",
                        },
                        "transcriber": {
                            "provider": "sarvam",
                            "model": "saaras:v3",
                            "language": sarvam_lang,
                            "stream": True,
                            "sampling_rate": 16000,
                            "encoding": "linear16",
                            "endpointing": 250,
                        },
                        "input": {
                            "provider": "plivo",
                            "format": "wav",
                        },
                        "output": {
                            "provider": "plivo",
                            "format": "wav",
                        },
                    },
                    "toolchain": {
                        "execution": "sequential",
                        "pipelines": [
                            ["transcriber", "llm", "synthesizer"],
                        ],
                    },
                    "task_config": {
                        "hangup_after_silence": 15,
                        "call_terminate": 150,
                        "voicemail": True,
                        "backchanneling": True,
                        "backchanneling_message_gap": 5,
                    },
                }
            ],
        }

        agent_prompts: dict = {
            "task_1": {
                "system_prompt": sample_prompt,
            },
        }

        self._agent_id = await self._bolna.create_agent(
            agent_config, agent_prompts
        )
        logger.info("CallingAgent bolna agent created id=%s", self._agent_id)
        return self._agent_id

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    async def run(
        self,
        hotels: list[Hotel],
        prefs: TravelPreferences,
    ) -> list[CallResult]:
        """Call all *hotels* and return extraction results.

        Args:
            hotels: Hotels shortlisted by the research agent.
            prefs: Guest travel preferences.

        Returns:
            One ``CallResult`` per hotel.
        """
        logger.info("CallingAgent.run starting hotels=%d", len(hotels))

        agent_id = await self._ensure_agent(prefs)

        orchestrator = CallOrchestrator(
            bolna_client=self._bolna,
            openai_client=self._openai,
            max_concurrent=self._config.max_concurrent_calls,
            call_timeout=self._config.call_timeout_seconds,
        )

        results = await orchestrator.call_hotels(hotels, prefs, agent_id)

        successful = sum(1 for r in results if r.status == "completed")
        logger.info(
            "CallingAgent.run done results=%d successful=%d",
            len(results),
            successful,
        )
        return results

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    async def close(self) -> None:
        """Shut down the underlying Bolna HTTP client."""
        await self._bolna.close()
