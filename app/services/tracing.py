"""Langfuse observability — initialization, decorators, and helpers.

Fail-closed design: if Langfuse credentials are absent, every public helper
degrades to a no-op so the app still runs. Agents and services never have to
check ``langfuse_enabled`` themselves.

Public surface:
    init_tracing(settings)    — call once at startup (from app.main lifespan)
    observe(...)              — decorator; auto-traces if Langfuse is enabled
    update_current_trace(...) — set session_id/user_id/tags on the active trace
    get_current_trace_id()    — read current trace id
    get_trace_url(trace_id)   — URL for a trace (or the current one)
    flush()                   — flush pending events (call on shutdown)

The OpenAI drop-in wrapper (``from langfuse.openai import AsyncOpenAI``) is
imported *directly* by ``app.agents.manager``; it lazy-reads env vars on first
call, so it works as long as ``init_tracing()`` set the env before the manager
is constructed. We still guard the import so missing langfuse doesn't blow up.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Awaitable, Callable, TypeVar

from app.config import Settings

logger = logging.getLogger(__name__)

_enabled: bool = False
_client: Any = None  # langfuse.Langfuse instance, typed loose to keep import optional

F = TypeVar("F", bound=Callable[..., Any])
AF = TypeVar("AF", bound=Callable[..., Awaitable[Any]])


def init_tracing(settings: Settings) -> bool:
    """Initialize Langfuse if credentials are present. Idempotent.

    Returns ``True`` if tracing is live, ``False`` otherwise.
    """
    global _enabled, _client

    if _enabled:
        return True

    if not settings.langfuse_enabled:
        logger.info("langfuse disabled — no credentials")
        return False

    # Export to env so langfuse.openai wrapper + implicit get_client() pick them up.
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_base_url)

    try:
        from langfuse import Langfuse  # type: ignore import-not-found

        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_base_url,
            release=settings.langfuse_release,
            environment=settings.langfuse_environment,
        )
        _enabled = True
        logger.info(
            "langfuse initialised host=%s release=%s env=%s",
            settings.langfuse_base_url,
            settings.langfuse_release,
            settings.langfuse_environment,
        )
        return True
    except Exception as exc:  # import or auth error — degrade to no-op
        logger.warning("langfuse init failed, tracing disabled: %s", exc)
        _enabled = False
        _client = None
        return False


def is_enabled() -> bool:
    return _enabled


def observe(
    *,
    name: str | None = None,
    as_type: str | None = None,
    capture_input: bool = True,
    capture_output: bool = True,
):
    """Drop-in replacement for ``langfuse.observe`` that no-ops if disabled.

    Usage:
        @observe(name="manager.run")
        async def run(...): ...

        @observe(name="bolna.make_call", as_type="span")
        async def make_call(...): ...
    """

    def decorator(func):
        if not _enabled:
            return func
        try:
            from langfuse import observe as _lf_observe  # type: ignore

            kwargs: dict[str, Any] = {
                "capture_input": capture_input,
                "capture_output": capture_output,
            }
            if name is not None:
                kwargs["name"] = name
            if as_type is not None:
                kwargs["as_type"] = as_type
            return _lf_observe(**kwargs)(func)
        except Exception as exc:
            logger.debug("observe decorator fallthrough: %s", exc)
            return func

    return decorator


def update_current_trace(**kwargs: Any) -> None:
    """Set session_id, user_id, tags, metadata, etc. on the active trace."""
    if not _enabled or _client is None:
        return
    try:
        _client.update_current_trace(**kwargs)
    except Exception as exc:
        logger.debug("update_current_trace failed: %s", exc)


def update_current_span(**kwargs: Any) -> None:
    if not _enabled or _client is None:
        return
    try:
        _client.update_current_span(**kwargs)
    except Exception as exc:
        logger.debug("update_current_span failed: %s", exc)


def get_current_trace_id() -> str | None:
    if not _enabled or _client is None:
        return None
    try:
        return _client.get_current_trace_id()
    except Exception:
        return None


def get_trace_url(trace_id: str | None = None) -> str | None:
    """Return the Langfuse UI URL for a trace (or the current one)."""
    if not _enabled or _client is None:
        return None
    try:
        if trace_id is None:
            return _client.get_trace_url()
        return _client.get_trace_url(trace_id=trace_id)
    except Exception:
        return None


def flush() -> None:
    """Block until queued events are sent. Call on app shutdown."""
    if not _enabled or _client is None:
        return
    try:
        _client.flush()
    except Exception as exc:
        logger.debug("flush failed: %s", exc)


def shutdown() -> None:
    if not _enabled or _client is None:
        return
    try:
        _client.shutdown()
    except Exception as exc:
        logger.debug("shutdown failed: %s", exc)
