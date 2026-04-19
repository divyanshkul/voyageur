"""Shared Pydantic models -- the contract layer every agent imports from.

All data structures exchanged between agents, services, and the LangGraph
state machine are defined here. Do NOT define models anywhere else.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel


class TravelPreferences(BaseModel):
    # --- core trip (required) ---
    destination: str
    check_in: date
    check_out: date
    budget_min: int | None = None
    budget_max: int                         # per night INR
    guests: int
    # --- enriched from spec (all optional, backward compat) ---
    origin_city: str | None = None          # "Bengaluru"
    group_type: str | None = None           # "couple", "solo", "family", "friends"
    children: int = 0
    seniors: int = 0
    trip_intent: str | None = None          # "relaxation", "sightseeing", "adventure", "mixed"
    pace: str | None = None                 # "slow", "medium", "packed"
    must_visit_places: list[str] = []       # ["Uluwatu", "Nusa Penida"]
    must_avoid: list[str] = []
    # --- existing optional ---
    star_rating: int | None = None
    food_pref: Literal["veg", "non-veg", "both"] = "both"
    smoking: bool = False
    alcohol: bool = False
    amenities: list[str] = []
    language_pref: Literal["kannada", "hindi", "english"] = "english"
    special_requests: str | None = None
    # --- budget context from spec ---
    budget_total_trip: int | None = None    # total budget excl flights
    budget_flexibility: str | None = None   # "strict", "can_stretch_10_percent", "flexible"


class Hotel(BaseModel):
    place_id: str
    name: str
    phone: str
    address: str
    rating: float
    ota_price: int | None = None
    photo_url: str | None = None
    amenities: list[str] = []
    match_score: float | None = None


class RoomOption(BaseModel):
    """A room category quoted during the call."""
    room_category: str | None = None
    bed_type: str | None = None
    nightly_rate: int | None = None        # INR
    total_rate: int | None = None          # INR for full stay
    taxes_included: bool | None = None
    breakfast_included: bool | None = None
    confidence: float = 0.5                # 0-1


class PreferenceCheck(BaseModel):
    """Result of verifying a user preference during the call."""
    supported: bool | None = None
    details: str | None = None
    confidence: float = 0.5


class NegotiationResult(BaseModel):
    """What happened when we asked for a better deal."""
    discount_obtained: bool = False
    value_adds: list[str] = []             # e.g. ["breakfast included", "late checkout"]
    staff_position: str | None = None      # e.g. "No lower rate but flexible cancellation"


class CallResult(BaseModel):
    hotel: Hotel
    status: Literal[
        "completed", "no_answer", "voicemail", "failed",
        "wrong_number", "language_barrier", "callback_requested",
    ]
    # --- core pricing (backward compat) ---
    direct_price: int | None = None        # best nightly rate INR
    availability: bool | None = None
    promotions: str | None = None
    cancellation_policy: str | None = None
    transcript: str | None = None
    call_duration: float | None = None
    # --- rich extraction (new) ---
    room_options: list[RoomOption] = []
    total_price: int | None = None         # full-stay total INR incl taxes
    taxes_included: bool | None = None
    breakfast_included: bool | None = None
    payment_terms: str | None = None       # "pay at property", "prepaid", etc.
    preference_checks: dict[str, PreferenceCheck] = {}   # dietary, quiet_room, etc.
    negotiation: NegotiationResult | None = None
    staff_name: str | None = None
    follow_up_contact: str | None = None   # WhatsApp/email for written quote
    written_quote_requested: bool = False
    transcript_summary: str | None = None
    confidence: dict[str, float] = {}      # per-field confidence scores


class HotelComparison(BaseModel):
    hotel: Hotel
    call_result: CallResult
    ota_price: int | None = None
    direct_price: int | None = None
    savings_amount: int | None = None
    savings_percent: float | None = None
    verdict: Literal["cheaper", "same", "more_expensive", "unknown"]


class Report(BaseModel):
    preferences: TravelPreferences
    comparisons: list[HotelComparison]
    top_pick: HotelComparison | None = None
    average_savings_percent: float | None = None
    summary: str
    markdown: str


class TaskStep(BaseModel):
    agent: Literal["preference", "research", "calling", "report"]
    action: str
    depends_on: list[int]  # indices of prior steps


class TaskPlan(BaseModel):
    steps: list[TaskStep]
