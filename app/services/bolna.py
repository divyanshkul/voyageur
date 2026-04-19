"""Bolna API v2 client (Phase 3a).

Wraps the Bolna REST API for creating voice agents, initiating outbound calls,
and polling execution status until terminal.

API reference:
  - Create Agent: POST /v2/agent
  - Make Call:    POST /call
  - Get Execution: GET /executions/{execution_id}
Base URL: https://api.bolna.ai
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from app.services import tracing

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Terminal statuses reported by Bolna execution API
# ---------------------------------------------------------------------------
_TERMINAL_STATUSES = frozenset({
    "completed",
    "call-disconnected",
    "no-answer",
    "busy",
    "failed",
    "canceled",
    "balance-low",
})


class BolnaClient:
    """Async client for the Bolna Voice AI REST API (v2)."""

    BASE_URL = "https://api.bolna.ai"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=60.0,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    # ------------------------------------------------------------------
    # Agent management
    # ------------------------------------------------------------------
    @tracing.observe(name="bolna.create_agent")
    async def create_agent(self, agent_config: dict, agent_prompts: dict) -> str:
        """Create a Bolna voice agent.

        Args:
            agent_config: Full ``agent_config`` dict (name, tasks, etc.).
            agent_prompts: Prompt mapping, e.g. ``{"task_1": {"system_prompt": "..."}}``.

        Returns:
            The ``agent_id`` string from Bolna.
        """
        body = {"agent_config": agent_config, "agent_prompts": agent_prompts}
        t0 = time.monotonic()
        resp = await self._request("POST", "/v2/agent", json=body)
        latency_ms = (time.monotonic() - t0) * 1000
        agent_id = resp.get("agent_id", "")
        logger.info(
            "bolna create_agent agent_name=%s agent_id=%s latency_ms=%.0f",
            agent_config.get("agent_name", "?"),
            agent_id,
            latency_ms,
        )
        return agent_id

    # ------------------------------------------------------------------
    # Update agent prompt
    # ------------------------------------------------------------------
    async def update_agent_prompt(self, agent_id: str, system_prompt: str) -> None:
        """PATCH the agent's system prompt before a call."""
        body = {
            "agent_prompts": {
                "task_1": {
                    "system_prompt": system_prompt,
                }
            }
        }
        start = time.time()
        await self._request("PATCH", f"/v2/agent/{agent_id}", json=body)
        latency_ms = (time.time() - start) * 1000
        logger.info(
            "bolna update_agent_prompt agent_id=%s prompt_len=%d latency_ms=%.0f",
            agent_id,
            len(system_prompt),
            latency_ms,
        )

    # ------------------------------------------------------------------
    # Calling
    # ------------------------------------------------------------------
    @tracing.observe(name="bolna.make_call")
    async def make_call(self, agent_id: str, phone: str) -> str:
        """Initiate an outbound call.

        Args:
            agent_id: Bolna agent UUID.
            phone: Recipient phone in E.164 format.

        Returns:
            The ``execution_id`` for the call.
        """
        body = {"agent_id": agent_id, "recipient_phone_number": phone}
        resp = await self._request("POST", "/call", json=body)
        execution_id = resp.get("execution_id", "")
        logger.info(
            "bolna make_call agent_id=%s phone=****%s execution_id=%s",
            agent_id,
            phone[-4:] if len(phone) >= 4 else phone,
            execution_id,
        )
        return execution_id

    # ------------------------------------------------------------------
    # Execution polling
    # ------------------------------------------------------------------
    async def get_execution(self, execution_id: str) -> dict:
        """Fetch a single execution record.

        Args:
            execution_id: UUID of the execution.

        Returns:
            Full execution dict (status, transcript, telephony_data, …).
        """
        resp = await self._request("GET", f"/executions/{execution_id}")
        logger.info(
            "bolna get_execution execution_id=%s status=%s",
            execution_id,
            resp.get("status", "?"),
        )
        return resp

    @tracing.observe(name="bolna.poll_until_complete")
    async def poll_until_complete(
        self,
        execution_id: str,
        timeout: int = 120,
        interval: float = 5.0,
    ) -> dict:
        """Poll ``get_execution`` until a terminal status is reached.

        Args:
            execution_id: UUID of the execution.
            timeout: Max seconds to wait.
            interval: Seconds between polls.

        Returns:
            The final execution dict, or a synthetic ``{"status": "failed"}``
            on timeout.
        """
        t0 = time.monotonic()
        poll_count = 0

        while True:
            elapsed = time.monotonic() - t0
            if elapsed >= timeout:
                logger.error(
                    "bolna poll timeout execution_id=%s elapsed=%.1fs polls=%d",
                    execution_id,
                    elapsed,
                    poll_count,
                )
                return {"status": "failed", "error": "timeout"}

            result = await self.get_execution(execution_id)
            poll_count += 1
            status = result.get("status", "")

            if status in _TERMINAL_STATUSES:
                logger.info(
                    "bolna poll done execution_id=%s status=%s "
                    "elapsed=%.1fs polls=%d",
                    execution_id,
                    status,
                    time.monotonic() - t0,
                    poll_count,
                )
                return result

            await asyncio.sleep(interval)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        _retried: bool = False,
    ) -> dict:
        """Issue an HTTP request with optional 5xx retry (once).

        Raises ``httpx.HTTPStatusError`` for non-retryable errors.
        """
        try:
            resp = await self._client.request(method, path, json=json)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            body = exc.response.text[:500]
            logger.error(
                "bolna HTTP %s %s status=%d body=%s",
                method,
                path,
                status_code,
                body,
            )
            # Retry 5xx once
            if status_code >= 500 and not _retried:
                logger.info("bolna retrying %s %s after 5xx", method, path)
                return await self._request(method, path, json=json, _retried=True)
            raise
        except httpx.HTTPError as exc:
            logger.error("bolna HTTP error %s %s: %s", method, path, exc)
            raise
