"""Manager Agent -- top-level orchestrator (Phase 5-int).

Initialises all sub-agents, builds the LangGraph state machine, and exposes
a single ``run()`` entry-point that processes user input through the full
preference → research → calling → report pipeline.

Multi-turn execution is driven step-by-step via node functions (not by
invoking the compiled graph directly) so that interactive stages
(collecting, approving) can pause for user input without a checkpointer.
"""

from __future__ import annotations

import logging
import time

from app.agents.caller import CallingAgent
from app.agents.manager_graph import build_graph
from app.agents.manager_planner import determine_next_action
from app.agents.preference import PreferenceAgent
from app.agents.reporter import ReportAgent
from app.agents.research import ResearchAgent
from app.config import Settings
from app.services import tracing
from app.services.places import GooglePlacesClient
from app.services.serpapi import SerpAPIClient
from app.state import VoyageurState
from app.ws_manager import ws_manager

# Use the Langfuse-wrapped AsyncOpenAI if tracing is enabled so every
# chat.completions call is auto-traced as a generation. Fall back to the
# plain SDK otherwise — identical API, just no traces.
if tracing.is_enabled():
    from langfuse.openai import AsyncOpenAI  # type: ignore
else:
    from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Stages that require new user input before the loop should continue.
_INTERACTIVE_STAGES = frozenset({"collecting", "approving", "done"})

# Stage → next node name for auto-continuation (non-interactive stages).
_AUTO_CONTINUE: dict[str, str] = {
    "researching": "research_hotels",
    "calling": "call_hotels",
    "compiling": "compile_report",
}


def _initial_state() -> VoyageurState:
    """Return a fresh, empty ``VoyageurState``."""
    return {
        "messages": [],
        "preferences": None,
        "preferences_complete": False,
        "hotel_candidates": [],
        "approved_hotels": [],
        "call_results": [],
        "report": None,
        "stage": "collecting",
        "task_plan": None,
        "error": None,
    }


class ManagerAgent:
    """Top-level orchestrator that wires all sub-agents into a pipeline."""

    def __init__(self, config: Settings) -> None:
        openai_client = AsyncOpenAI(api_key=config.openai_api_key)

        # -- Sub-agents ----------------------------------------------------
        self._preference_agent = PreferenceAgent(openai_client)
        # GooglePlacesClient is backed by SerpAPI's google_maps engine, so it
        # uses the same SERPAPI key as SerpAPIClient.
        self._research_agent = ResearchAgent(
            places_client=GooglePlacesClient(config.serpapi_api_key),
            serpapi_client=SerpAPIClient(config.serpapi_api_key),
            openai_client=openai_client,
            openai_api_key=config.openai_api_key,
            serpapi_api_key=config.serpapi_api_key,
        )
        self._calling_agent = CallingAgent(config, openai_client)
        self._report_agent = ReportAgent(openai_client)

        # -- LangGraph (compiled graph + node functions) -------------------
        self._graph, self._nodes = build_graph(
            self._preference_agent,
            self._research_agent,
            self._calling_agent,
            self._report_agent,
        )

        # -- Per-session state storage -------------------------------------
        self._sessions: dict[str, VoyageurState] = {}

        logger.info("ManagerAgent initialised")

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------
    def get_session_state(self, session_id: str) -> VoyageurState | None:
        """Return session state if it exists, or None."""
        return self._sessions.get(session_id)

    def _get_or_create_state(self, session_id: str) -> VoyageurState:
        """Return existing session state or create a fresh one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = _initial_state()
            logger.info("session created session_id=%s", session_id)
        return self._sessions[session_id]

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    @tracing.observe(name="manager.run")
    async def run(self, user_input: str, session_id: str = "default") -> dict:
        """Process one user message and return the agent's response.

        Drives the graph step-by-step, auto-continuing through non-
        interactive stages (researching → approving, calling → compiling →
        done) so the user gets back a complete result per interaction.

        Returns:
            ``{"reply", "stage", "hotels", "call_progress", "report", "trace_url"}``
        """
        t0 = time.monotonic()
        state = self._get_or_create_state(session_id)

        # Tag the active Langfuse trace with session + incoming stage so all
        # turns from one browser session collapse into a single Session view.
        tracing.update_current_trace(
            session_id=session_id,
            user_id=session_id,
            tags=["voyageur", f"stage:{state['stage']}"],
            metadata={"input_len": len(user_input)},
            input={"user_input": user_input, "stage_in": state["stage"]},
        )

        # -- If pipeline finished, reset for a new conversation ------------
        if state["stage"] == "done":
            state = _initial_state()
            self._sessions[session_id] = state

        # -- Record user message -------------------------------------------
        state["messages"] = state["messages"] + [
            {"role": "user", "content": user_input},
        ]
        msg_count_before = len(state["messages"])

        # -- Determine first action ----------------------------------------
        action: str | None = determine_next_action(user_input, state["stage"])

        # -- Execute nodes, auto-continuing through non-interactive stages --
        while action:
            node_fn = self._nodes.get(action)
            if node_fn is None:
                logger.error("manager unknown node=%s, breaking", action)
                break

            old_stage = state["stage"]

            try:
                update = await node_fn(state)
                # Merge partial update into state
                for key, value in update.items():
                    state[key] = value  # type: ignore[literal-required]
            except Exception as exc:
                logger.exception("manager node=%s failed: %s", action, exc)
                error_msg = (
                    f"Sorry, something went wrong during the "
                    f"{action.replace('_', ' ')} step. "
                    f"Please try again."
                )
                state["messages"] = state["messages"] + [
                    {"role": "assistant", "content": error_msg},
                ]
                state["error"] = str(exc)  # type: ignore[literal-required]
                break

            # -- Broadcast real-time events via WebSocket ------------------
            await self._emit_events(session_id, old_stage, state, update)

            # Decide whether to auto-continue
            current_stage = state["stage"]
            if current_stage in _INTERACTIVE_STAGES:
                break
            action = _AUTO_CONTINUE.get(current_stage)

        # -- Persist state -------------------------------------------------
        self._sessions[session_id] = state

        # -- Collect all assistant messages produced this turn --------------
        new_assistant_msgs = [
            m["content"]
            for m in state["messages"][msg_count_before:]
            if m.get("role") == "assistant"
        ]
        reply = "\n\n".join(new_assistant_msgs) if new_assistant_msgs else ""

        elapsed_ms = (time.monotonic() - t0) * 1000
        logger.info(
            "manager.run session=%s input_stage=%s output_stage=%s "
            "reply_len=%d latency_ms=%.0f",
            session_id,
            state.get("stage"),
            state["stage"],
            len(reply),
            elapsed_ms,
        )

        trace_url = tracing.get_trace_url()
        tracing.update_current_trace(
            output={
                "stage": state["stage"],
                "reply_len": len(reply),
                "hotels": len(state.get("hotel_candidates", [])),
                "calls": len(state.get("call_results", [])),
                "has_report": state.get("report") is not None,
            },
        )

        return {
            "reply": reply,
            "stage": state["stage"],
            "hotels": (
                [h.model_dump(mode="json") for h in state["hotel_candidates"]]
                if state["hotel_candidates"]
                else None
            ),
            "call_progress": (
                [r.model_dump(mode="json") for r in state["call_results"]]
                if state["call_results"]
                else None
            ),
            "report": (
                state["report"].model_dump(mode="json")
                if state["report"]
                else None
            ),
            "trace_url": trace_url,
        }

    # ------------------------------------------------------------------
    # WebSocket event broadcasting
    # ------------------------------------------------------------------
    async def _emit_events(
        self,
        session_id: str,
        old_stage: str,
        state: VoyageurState,
        update: dict,
    ) -> None:
        """Broadcast WebSocket events based on what changed after a node ran."""
        try:
            new_stage = state["stage"]

            # stage_change
            if old_stage != new_stage:
                await ws_manager.broadcast(
                    session_id,
                    {"event": "stage_change", "stage": new_stage},
                )

            # hotels_found -- after research produces candidates
            if "hotel_candidates" in update and update["hotel_candidates"]:
                hotels = update["hotel_candidates"]
                await ws_manager.broadcast(
                    session_id,
                    {
                        "event": "hotels_found",
                        "count": len(hotels),
                        "hotels": [
                            h.model_dump(mode="json") for h in hotels
                        ],
                    },
                )

            # call_started -- when stage transitions to "calling"
            if new_stage == "calling" and old_stage != "calling":
                for h in state.get("approved_hotels", []):
                    await ws_manager.broadcast(
                        session_id,
                        {"event": "call_started", "hotel": h.name},
                    )

            # call_completed -- after calling node produces results
            if "call_results" in update and update["call_results"]:
                for r in update["call_results"]:
                    await ws_manager.broadcast(
                        session_id,
                        {
                            "event": "call_completed",
                            "hotel": r.hotel.name,
                            "price": r.direct_price,
                            "available": (
                                r.availability
                                if r.availability is not None
                                else False
                            ),
                        },
                    )

            # report_ready -- after compile_report produces the report
            if "report" in update and update["report"] is not None:
                await ws_manager.broadcast(
                    session_id,
                    {
                        "event": "report_ready",
                        "report": update["report"].model_dump(mode="json"),
                    },
                )
        except Exception as exc:
            # Broadcasting must never break the main pipeline
            logger.warning("ws_broadcast_error session=%s: %s", session_id, exc)
