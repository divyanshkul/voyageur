"""Bolna webhook handler (Phase 3b).

FastAPI APIRouter that receives call-completion payloads from Bolna and
makes results available to the calling agent via asyncio.Event-based
wait_for_result().

Bolna sends a POST to /webhook/bolna with the same schema as the
GET /executions/{execution_id} response (status, transcript,
telephony_data, etc.).
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

bolna_webhook_router = APIRouter()

# ---------------------------------------------------------------------------
# Module-level state: execution results + async events
# ---------------------------------------------------------------------------
_results: dict[str, dict] = {}
_events: dict[str, asyncio.Event] = {}


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------
@bolna_webhook_router.post("/webhook/bolna")
async def handle_bolna_webhook(request: Request) -> dict:
    """Receive a Bolna call-completion webhook payload.

    Stores the payload so ``wait_for_result`` can return it, and signals
    any waiting coroutine.
    """
    payload: dict = await request.json()

    # Bolna may nest execution_id under different keys; normalise.
    execution_id = (
        payload.get("execution_id")
        or payload.get("id")
        or payload.get("call_id", "unknown")
    )

    status = payload.get("status", "?")
    transcript = payload.get("transcript", "") or ""
    transcript_len = len(transcript)

    # Terminal statuses -- only these mean the call is truly done
    _TERMINAL = {"completed", "failed", "no-answer", "busy", "error", "call-disconnected", "voicemail"}

    # Always store the latest payload (overwrite intermediate statuses)
    _results[execution_id] = payload

    # Only wake up the waiter on a terminal status
    if status in _TERMINAL:
        event = _events.get(execution_id)
        if event is not None:
            event.set()

    logger.info(
        "webhook received execution_id=%s status=%s transcript_len=%d",
        execution_id,
        status,
        transcript_len,
    )
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Async waiter -- used by caller_orchestrator
# ---------------------------------------------------------------------------
async def wait_for_result(execution_id: str, timeout: int = 180) -> dict | None:
    """Wait for a webhook result for the given execution_id.

    Returns the stored payload dict, or ``None`` on timeout.
    """
    # Already received (race-free check)
    if execution_id in _results:
        logger.info(
            "webhook wait_for_result execution_id=%s already_available=true",
            execution_id,
        )
        return _results[execution_id]

    # Create an event and wait
    event = asyncio.Event()
    _events[execution_id] = event

    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
        result = _results.get(execution_id)
        logger.info(
            "webhook wait_for_result execution_id=%s waited=true status=%s",
            execution_id,
            result.get("status", "?") if result else "none",
        )
        return result
    except asyncio.TimeoutError:
        logger.warning(
            "webhook wait_for_result timeout execution_id=%s timeout=%ds",
            execution_id,
            timeout,
        )
        return None
    finally:
        _events.pop(execution_id, None)


# ---------------------------------------------------------------------------
# Cleanup helper
# ---------------------------------------------------------------------------
def clear_result(execution_id: str) -> None:
    """Remove stored result and event for an execution (cleanup after processing)."""
    _results.pop(execution_id, None)
    _events.pop(execution_id, None)
