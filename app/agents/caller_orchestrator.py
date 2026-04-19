"""Call orchestrator (Phase 3d).

Manages calling multiple hotels in parallel with concurrency limits,
retry logic (no-answer / failed), timeout handling, and result collection.
"""

from __future__ import annotations

import asyncio
import logging
import time

from app.agents.caller_prompts import build_call_prompt, extract_call_data
from app.models import CallResult, Hotel, TravelPreferences
from app.services.bolna import BolnaClient
from app.webhooks.bolna_webhook import clear_result, wait_for_result

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bolna status → CallResult.status mapping
# ---------------------------------------------------------------------------
_STATUS_MAP: dict[str, str] = {
    "completed": "completed",
    "call-disconnected": "completed",   # treat as completed (got some data)
    "no-answer": "no_answer",
    "busy": "failed",
    "failed": "failed",
    "canceled": "failed",
    "balance-low": "failed",
}


def _map_status(bolna_status: str, answered_by_voicemail: bool = False) -> str:
    """Map a Bolna execution status to a ``CallResult.status`` literal."""
    if answered_by_voicemail:
        return "voicemail"
    return _STATUS_MAP.get(bolna_status, "failed")


class CallOrchestrator:
    """Runs hotel calls in parallel with concurrency gating and retries."""

    def __init__(
        self,
        bolna_client: BolnaClient,
        openai_client,
        max_concurrent: int = 3,
        call_timeout: int = 120,
    ) -> None:
        self._bolna = bolna_client
        self._openai = openai_client
        self._call_timeout = call_timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    async def call_hotels(
        self,
        hotels: list[Hotel],
        prefs: TravelPreferences,
        agent_id: str,
    ) -> list[CallResult]:
        """Call every hotel and return structured results.

        Args:
            hotels: Hotels to call.
            prefs: Guest travel preferences.
            agent_id: Pre-created Bolna agent id.
        """
        logger.info(
            "call_hotels starting hotels=%d max_concurrent=%d",
            len(hotels),
            self._semaphore._value,  # noqa: SLF001
        )
        t0 = time.monotonic()

        tasks = [
            self._call_single_hotel(hotel, prefs, agent_id) for hotel in hotels
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[CallResult] = []
        failed_count = 0
        for hotel, res in zip(hotels, raw_results):
            if isinstance(res, BaseException):
                logger.error(
                    "call_hotels exception hotel=%s error=%s", hotel.name, res
                )
                results.append(
                    CallResult(hotel=hotel, status="failed", transcript=None)
                )
                failed_count += 1
            else:
                results.append(res)
                if res.status == "failed":
                    failed_count += 1

        elapsed = time.monotonic() - t0
        logger.info(
            "call_hotels done total=%d completed=%d failed=%d elapsed=%.1fs",
            len(results),
            len(results) - failed_count,
            failed_count,
            elapsed,
        )
        return results

    # ------------------------------------------------------------------
    # Single-hotel call flow
    # ------------------------------------------------------------------
    async def _call_single_hotel(
        self,
        hotel: Hotel,
        prefs: TravelPreferences,
        agent_id: str,
    ) -> CallResult:
        async with self._semaphore:
            logger.info(
                "calling hotel=%s phone=****%s",
                hotel.name,
                hotel.phone[-4:] if len(hotel.phone) >= 4 else hotel.phone,
            )

            # Build the per-hotel prompt and update the Bolna agent
            prompt = build_call_prompt(hotel, prefs)
            await self._bolna.update_agent_prompt(agent_id, prompt)

            # Initiate the call
            execution_id = await self._bolna.make_call(agent_id, hotel.phone)

            # Wait for webhook result first, fall back to polling
            result = await wait_for_result(
                execution_id, timeout=self._call_timeout
            )
            if result is None:
                logger.info(
                    "webhook miss, polling execution_id=%s", execution_id
                )
                result = await self._bolna.poll_until_complete(
                    execution_id, timeout=self._call_timeout
                )

            # Cleanup webhook state
            clear_result(execution_id)

            return await self._process_result(
                result, hotel, prefs, agent_id
            )

    # ------------------------------------------------------------------
    # Process a raw Bolna execution result
    # ------------------------------------------------------------------
    async def _process_result(
        self,
        result: dict,
        hotel: Hotel,
        prefs: TravelPreferences,
        agent_id: str,
    ) -> CallResult:
        bolna_status = result.get("status", "failed")
        answered_vm = result.get("answered_by_voice_mail", False)
        mapped_status = _map_status(bolna_status, answered_vm)
        transcript = result.get("transcript", "") or ""

        # Duration from telephony_data (seconds as string) or conversation_time
        duration: float | None = None
        tel_data = result.get("telephony_data") or {}
        if tel_data.get("duration"):
            try:
                duration = float(tel_data["duration"])
            except (TypeError, ValueError):
                pass
        if duration is None and result.get("conversation_time") is not None:
            try:
                duration = float(result["conversation_time"])
            except (TypeError, ValueError):
                pass

        # ---- Handle each mapped status ----
        if mapped_status == "completed" and transcript:
            call_result = await extract_call_data(
                transcript, hotel, self._openai
            )
            call_result.call_duration = duration
            logger.info(
                "call completed hotel=%s price=%s duration=%s",
                hotel.name,
                call_result.direct_price,
                duration,
            )
            return call_result

        if mapped_status == "no_answer":
            # Retry once after 30s delay
            logger.info("no_answer, retrying hotel=%s", hotel.name)
            return await self._retry_call(
                hotel, prefs, agent_id, delay=30.0
            )

        if mapped_status == "failed" and bolna_status in ("failed", "busy"):
            # Retry once immediately
            logger.info(
                "failed/busy, retrying hotel=%s bolna_status=%s",
                hotel.name,
                bolna_status,
            )
            return await self._retry_call(hotel, prefs, agent_id, delay=0)

        if mapped_status == "voicemail":
            logger.info("voicemail hotel=%s", hotel.name)
            return CallResult(
                hotel=hotel,
                status="voicemail",
                transcript=transcript or None,
                call_duration=duration,
            )

        # Fallback: completed with no transcript, or other
        logger.info(
            "call ended hotel=%s status=%s transcript_len=%d",
            hotel.name,
            mapped_status,
            len(transcript),
        )
        return CallResult(
            hotel=hotel,
            status=mapped_status,
            transcript=transcript or None,
            call_duration=duration,
        )

    # ------------------------------------------------------------------
    # Retry (one shot, no further retries)
    # ------------------------------------------------------------------
    async def _retry_call(
        self,
        hotel: Hotel,
        prefs: TravelPreferences,
        agent_id: str,
        delay: float = 0,
    ) -> CallResult:
        if delay > 0:
            await asyncio.sleep(delay)

        logger.info("retrying call hotel=%s", hotel.name)

        try:
            execution_id = await self._bolna.make_call(agent_id, hotel.phone)

            result = await wait_for_result(
                execution_id, timeout=self._call_timeout
            )
            if result is None:
                result = await self._bolna.poll_until_complete(
                    execution_id, timeout=self._call_timeout
                )

            clear_result(execution_id)

            bolna_status = result.get("status", "failed")
            answered_vm = result.get("answered_by_voice_mail", False)
            mapped = _map_status(bolna_status, answered_vm)
            transcript = result.get("transcript", "") or ""

            duration: float | None = None
            tel_data = result.get("telephony_data") or {}
            if tel_data.get("duration"):
                try:
                    duration = float(tel_data["duration"])
                except (TypeError, ValueError):
                    pass
            if duration is None and result.get("conversation_time") is not None:
                try:
                    duration = float(result["conversation_time"])
                except (TypeError, ValueError):
                    pass

            if mapped == "completed" and transcript:
                call_result = await extract_call_data(
                    transcript, hotel, self._openai
                )
                call_result.call_duration = duration
                return call_result

            return CallResult(
                hotel=hotel,
                status=mapped,
                transcript=transcript or None,
                call_duration=duration,
            )

        except Exception:
            logger.exception("retry failed hotel=%s", hotel.name)
            return CallResult(hotel=hotel, status="failed")
