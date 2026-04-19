"""FastAPI application for Voyageur.

Provides health-check, chat route, session status, WebSocket for real-time
events, Bolna webhook mount, request-logging middleware, and CORS setup.
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import get_settings
from app.logging_config import setup_logging
from app.services import tracing
from app.webhooks.bolna_webhook import bolna_webhook_router
from app.ws_manager import ws_manager

# ---------------------------------------------------------------------------
# Logging -- call once at import time so every module picks it up
# ---------------------------------------------------------------------------
setup_logging()
logger = logging.getLogger(__name__)

# Tracing — also init at import time so the langfuse.openai wrapper picks up
# env vars before the manager (and its OpenAI client) is ever instantiated.
# Lifespan will also flush + shutdown cleanly.
tracing.init_tracing(get_settings())


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Voyageur API starting")
    # Tracing MUST init before the manager is constructed so the
    # langfuse.openai wrapper sees the env vars on first import.
    tracing.init_tracing(get_settings())
    yield
    logger.info("Voyageur API shutting down")
    tracing.flush()
    tracing.shutdown()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Voyageur", lifespan=lifespan)

# CORS -- explicit origins + wildcard for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Mount Bolna webhook router
# ---------------------------------------------------------------------------
app.include_router(bolna_webhook_router)


# ---------------------------------------------------------------------------
# Request-logging middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    latency_ms = (time.time() - start) * 1000
    logger.info(
        "request %s %s status=%d latency_ms=%.1f",
        request.method,
        request.url.path,
        response.status_code,
        latency_ms,
    )
    return response


# ---------------------------------------------------------------------------
# Lazy ManagerAgent initialisation
# ---------------------------------------------------------------------------
_manager = None


def get_manager():
    """Return the singleton ManagerAgent (created on first call)."""
    global _manager
    if _manager is None:
        from app.agents.manager import ManagerAgent

        _manager = ManagerAgent(get_settings())
        logger.info("ManagerAgent initialised (lazy)")
    return _manager


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "service": "voyageur"}


@app.post("/api/chat")
async def api_chat(body: ChatRequest):
    """Process a user message through the ManagerAgent pipeline.

    Returns ``{"reply", "stage", "hotels", "call_progress", "report"}``.
    """
    try:
        manager = get_manager()
    except Exception as exc:
        logger.error("manager_init_failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Backend configuration error: {exc}"},
        )

    try:
        result = await manager.run(body.message, body.session_id)
        logger.info(
            "api_chat session=%s stage=%s reply_len=%d",
            body.session_id,
            result.get("stage"),
            len(result.get("reply", "")),
        )
        return result
    except Exception as exc:
        logger.exception("api_chat error session=%s: %s", body.session_id, exc)
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc)},
        )


@app.get("/api/status/{session_id}")
async def api_status(session_id: str):
    """Return current session state summary.

    Returns ``{"stage", "preferences", "hotel_count", "approved_count",
    "call_results", "report"}``.
    """
    try:
        manager = get_manager()
    except Exception as exc:
        logger.error("manager_init_failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Backend configuration error: {exc}"},
        )

    state = manager.get_session_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    call_results_summary = [
        {
            "hotel_name": r.hotel.name,
            "status": r.status,
            "price": r.direct_price,
        }
        for r in state.get("call_results", [])
    ]

    return {
        "stage": state["stage"],
        "preferences": (
            state["preferences"].model_dump(mode="json")
            if state["preferences"]
            else None
        ),
        "hotel_count": len(state.get("hotel_candidates", [])),
        "approved_count": len(state.get("approved_hotels", [])),
        "call_results": call_results_summary,
        "report": (
            state["report"].model_dump(mode="json")
            if state["report"]
            else None
        ),
    }


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------
@app.websocket("/ws/{session_id}")
async def ws_endpoint(websocket: WebSocket, session_id: str):
    """Real-time event stream for a session.

    The server pushes events via ``ws_manager.broadcast()``.
    The client can send ``"ping"`` to receive ``"pong"`` keepalive.
    """
    await ws_manager.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info("ws_client_disconnected session_id=%s", session_id)
    except Exception as exc:
        logger.warning("ws_error session_id=%s: %s", session_id, exc)
    finally:
        ws_manager.disconnect(session_id, websocket)
