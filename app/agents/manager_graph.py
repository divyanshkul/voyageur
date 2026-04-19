"""LangGraph state machine definition (Phase 5a).

Defines the StateGraph over VoyageurState with nodes for each agent and
conditional edges that drive the conversation flow from preference collection
through research, approval, calling, and report compilation.

The compiled graph documents the full flow.  For multi-turn execution the
``ManagerAgent`` drives nodes step-by-step using the node-function dict
returned alongside the compiled graph by ``build_graph()``.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

from langgraph.graph import END, StateGraph

from app.agents.manager_planner import parse_approval
from app.state import VoyageurState

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Node factories -- each returns an async function(state) → partial-update
# ═══════════════════════════════════════════════════════════════════════════

def make_collect_preferences(preference_agent: Any) -> Callable:
    """Create the *collect_preferences* node (bound to *preference_agent*)."""

    async def collect_preferences(state: VoyageurState) -> dict:
        logger.info("node enter=collect_preferences stage=%s", state.get("stage"))

        messages: list[dict] = state["messages"]
        reply, prefs = await preference_agent.run(messages)

        new_msg = {"role": "assistant", "content": reply}
        updated_messages = messages + [new_msg]

        if prefs is not None:
            logger.info(
                "node exit=collect_preferences -> researching dest=%s",
                prefs.destination,
            )
            return {
                "preferences": prefs,
                "preferences_complete": True,
                "stage": "researching",
                "messages": updated_messages,
            }

        logger.info("node exit=collect_preferences -> still collecting")
        return {
            "preferences_complete": False,
            "messages": updated_messages,
        }

    return collect_preferences


def make_research_hotels(research_agent: Any) -> Callable:
    """Create the *research_hotels* node (bound to *research_agent*)."""

    async def research_hotels(state: VoyageurState) -> dict:
        logger.info("node enter=research_hotels")

        prefs = state["preferences"]
        assert prefs is not None, "preferences must be set before research"

        hotels = await research_agent.run(prefs)

        # Build response messages
        new_messages = list(state["messages"])

        # If facile pipeline ran, include the itinerary first
        itinerary_msg = research_agent.get_itinerary_message()
        if itinerary_msg:
            new_messages.append({
                "role": "assistant",
                "content": f"Here's the itinerary I planned for your trip:\n\n{itinerary_msg}",
            })
            logger.info("node research_hotels -> itinerary message added")

        # Then the hotel shortlist
        shortlist_text = research_agent.format_for_approval(hotels)
        new_messages.append({"role": "assistant", "content": shortlist_text})

        logger.info(
            "node exit=research_hotels -> approving hotels_found=%d",
            len(hotels),
        )
        return {
            "hotel_candidates": hotels,
            "stage": "approving",
            "messages": new_messages,
        }

    return research_hotels


def make_get_approval() -> Callable:
    """Create the *get_approval* node (stateless -- uses ``parse_approval``)."""

    async def get_approval(state: VoyageurState) -> dict:
        logger.info("node enter=get_approval")

        messages: list[dict] = state["messages"]

        # Extract latest user message
        user_input = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_input = msg.get("content", "")
                break

        lower = user_input.lower().strip()

        # -- "search again" → back to research ----------------------------
        if any(kw in lower for kw in (
            "search again", "different hotels", "more options", "look again",
        )):
            reply = "No problem, I'll search for more options!"
            logger.info("node exit=get_approval -> researching (re-search)")
            return {
                "stage": "researching",
                "messages": messages + [{"role": "assistant", "content": reply}],
            }

        # -- Parse which hotels the user approved --------------------------
        approved = parse_approval(user_input, state["hotel_candidates"])

        if not approved:
            reply = (
                "No hotels selected. Would you like me to search again, "
                "or say 'start over' to change your preferences?"
            )
            logger.info("node exit=get_approval -> approving (none selected)")
            return {
                "stage": "approving",
                "messages": messages + [{"role": "assistant", "content": reply}],
            }

        names = ", ".join(h.name for h in approved)
        reply = (
            f"Great, I'll call {len(approved)} hotel(s): {names}.\n"
            f"Starting calls now -- this may take a few minutes..."
        )

        logger.info(
            "node exit=get_approval -> calling approved=%d", len(approved),
        )
        return {
            "approved_hotels": approved,
            "stage": "calling",
            "messages": messages + [{"role": "assistant", "content": reply}],
        }

    return get_approval


def make_call_hotels(calling_agent: Any) -> Callable:
    """Create the *call_hotels* node (bound to *calling_agent*)."""

    async def call_hotels(state: VoyageurState) -> dict:
        logger.info(
            "node enter=call_hotels hotels=%d",
            len(state["approved_hotels"]),
        )

        results = await calling_agent.run(
            state["approved_hotels"],
            state["preferences"],
        )

        completed = sum(1 for r in results if r.status == "completed")
        reply = (
            f"Calls complete! {completed}/{len(results)} hotels reached "
            f"successfully. Compiling your report..."
        )

        logger.info(
            "node exit=call_hotels -> compiling completed=%d/%d",
            completed,
            len(results),
        )
        return {
            "call_results": results,
            "stage": "compiling",
            "messages": state["messages"] + [{"role": "assistant", "content": reply}],
        }

    return call_hotels


def make_compile_report(report_agent: Any) -> Callable:
    """Create the *compile_report* node (bound to *report_agent*)."""

    async def compile_report(state: VoyageurState) -> dict:
        logger.info("node enter=compile_report")

        report = await report_agent.run(
            state["call_results"],
            state["preferences"],
        )

        top_name = report.top_pick.hotel.name if report.top_pick else "none"
        savings = report.average_savings_percent

        logger.info(
            "node exit=compile_report -> done top_pick=%s avg_savings=%s",
            top_name,
            f"{savings:.1f}%" if savings is not None else "N/A",
        )
        return {
            "report": report,
            "stage": "done",
            "messages": state["messages"] + [
                {"role": "assistant", "content": report.markdown},
            ],
        }

    return compile_report


# ═══════════════════════════════════════════════════════════════════════════
# Conditional edge routers
# ═══════════════════════════════════════════════════════════════════════════

def route_after_preferences(state: VoyageurState) -> str:
    """After *collect_preferences*: continue to research or loop back."""
    if state.get("preferences_complete"):
        return "research_hotels"
    return "collect_preferences"


def route_after_approval(state: VoyageurState) -> str:
    """After *get_approval*: proceed to calling, re-research, or restart."""
    stage = state.get("stage", "")
    if stage == "calling":
        return "call_hotels"
    if stage == "researching":
        return "research_hotels"
    # Stay in approval loop or fall back to preferences
    if stage == "approving":
        return "get_approval"
    return "collect_preferences"


# ═══════════════════════════════════════════════════════════════════════════
# Graph builder
# ═══════════════════════════════════════════════════════════════════════════

NodeFnMap = dict[str, Callable[..., Coroutine]]


def build_graph(
    preference_agent: Any,
    research_agent: Any,
    calling_agent: Any,
    report_agent: Any,
) -> tuple[Any, NodeFnMap]:
    """Build and compile the LangGraph StateGraph.

    Returns:
        ``(compiled_graph, nodes_dict)`` -- the compiled graph (for
        visualisation / future invoke) and a mapping of node-name →
        async-callable so the ``ManagerAgent`` can drive execution
        step-by-step for the multi-turn flow.
    """
    # -- Create node functions (closures bound to agent instances) ----------
    nodes: NodeFnMap = {
        "collect_preferences": make_collect_preferences(preference_agent),
        "research_hotels": make_research_hotels(research_agent),
        "get_approval": make_get_approval(),
        "call_hotels": make_call_hotels(calling_agent),
        "compile_report": make_compile_report(report_agent),
    }

    # -- Assemble the graph ------------------------------------------------
    graph = StateGraph(VoyageurState)

    for name, fn in nodes.items():
        graph.add_node(name, fn)

    graph.set_entry_point("collect_preferences")

    graph.add_conditional_edges(
        "collect_preferences",
        route_after_preferences,
        {"research_hotels": "research_hotels", "collect_preferences": "collect_preferences"},
    )
    graph.add_edge("research_hotels", "get_approval")
    graph.add_conditional_edges(
        "get_approval",
        route_after_approval,
        {
            "call_hotels": "call_hotels",
            "research_hotels": "research_hotels",
            "get_approval": "get_approval",
            "collect_preferences": "collect_preferences",
        },
    )
    graph.add_edge("call_hotels", "compile_report")
    graph.add_edge("compile_report", END)

    compiled = graph.compile()

    logger.info("build_graph compiled nodes=%s", list(nodes.keys()))
    return compiled, nodes
