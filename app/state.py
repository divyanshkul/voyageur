"""LangGraph state definition for Voyageur.

VoyageurState is the single shared state that flows through the LangGraph
state machine.  Every node reads from / writes to this TypedDict.
"""

from typing import Literal, TypedDict

from app.models import (
    CallResult,
    Hotel,
    Report,
    TaskPlan,
    TravelPreferences,
)


class VoyageurState(TypedDict):
    messages: list[dict]
    preferences: TravelPreferences | None
    preferences_complete: bool
    hotel_candidates: list[Hotel]
    approved_hotels: list[Hotel]
    call_results: list[CallResult]
    report: Report | None
    stage: Literal[
        "collecting", "researching", "approving",
        "calling", "compiling", "done",
    ]
    task_plan: TaskPlan | None
    error: str | None
