"""WebSocket connection manager for real-time event broadcasting.

Maintains per-session WebSocket connection pools and provides a
``broadcast()`` method for pushing events (stage changes, call updates,
report-ready signals) to all connected clients for a given session.

Usage:
    from app.ws_manager import ws_manager
    await ws_manager.broadcast(session_id, {"event": "stage_change", "stage": "calling"})
"""

import json
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WSManager:
    """Per-session WebSocket connection pool with broadcast support."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------
    async def connect(self, session_id: str, ws: WebSocket) -> None:
        """Accept *ws* and register it under *session_id*."""
        await ws.accept()
        self._connections.setdefault(session_id, []).append(ws)
        logger.info(
            "ws_connected session_id=%s total=%d",
            session_id,
            len(self._connections[session_id]),
        )

    def disconnect(self, session_id: str, ws: WebSocket) -> None:
        """Remove *ws* from *session_id*'s pool. Clean up if empty."""
        if session_id in self._connections:
            try:
                self._connections[session_id].remove(ws)
            except ValueError:
                pass
            if not self._connections[session_id]:
                del self._connections[session_id]
        logger.info("ws_disconnected session_id=%s", session_id)

    # ------------------------------------------------------------------
    # Broadcasting
    # ------------------------------------------------------------------
    async def broadcast(self, session_id: str, event: dict) -> None:
        """Send *event* as JSON to every WebSocket in *session_id*'s pool.

        Dead connections are silently pruned.
        """
        conns = self._connections.get(session_id)
        if not conns:
            return

        msg = json.dumps(event, default=str)
        dead: list[WebSocket] = []

        for ws in list(conns):  # iterate over a copy
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(session_id, ws)

        logger.debug(
            "ws_broadcast session_id=%s event=%s recipients=%d",
            session_id,
            event.get("event"),
            len(conns) - len(dead),
        )


# ---------------------------------------------------------------------------
# Module-level singleton -- importable by any module
# ---------------------------------------------------------------------------
ws_manager = WSManager()
