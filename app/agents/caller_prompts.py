"""Call prompt builder and transcript extractor (Phase 3c).

Generates per-hotel system prompts for the Bolna voice agent following the
Travel Concierge Hotel Voice Calling Agent spec. Extracts rich structured
data from call transcripts including room options, negotiation results,
preference verification, and confidence scores.
"""

from __future__ import annotations

import json
import logging

from app.models import (
    CallResult,
    Hotel,
    NegotiationResult,
    PreferenceCheck,
    RoomOption,
    TravelPreferences,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language greetings
# ---------------------------------------------------------------------------
_GREETINGS: dict[str, str] = {
    "kannada": (
        "Namaskara, naanu ondu guest avara parvagagi call maadthiddene. "
        "Reservations team jothege maathaadabahudhaa?"
    ),
    "hindi": (
        "Namaste, main ek traveler ki taraf se call kar raha hoon. "
        "Kya main reservations team se baat kar sakta hoon?"
    ),
    "english": (
        "Hello, good day. I'm calling on behalf of a traveler who is "
        "considering a stay at your property. Am I speaking with the "
        "reservations team?"
    ),
}


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------
def build_call_prompt(hotel: Hotel, prefs: TravelPreferences) -> str:
    """Build a system prompt following the Hotel Voice Calling Agent spec.

    The prompt instructs the Bolna voice agent to behave like a warm,
    professional local travel coordinator -- not a robotic price checker.
    """
    greeting = _GREETINGS.get(prefs.language_pref, _GREETINGS["english"])

    nights = (prefs.check_out - prefs.check_in).days
    budget_target = prefs.budget_max
    budget_soft_max = int(prefs.budget_max * 1.1)  # 10% stretch

    # Build preference verification list
    must_verify: list[str] = []
    if prefs.food_pref == "veg":
        must_verify.append(
            "DIETARY: Ask if vegetarian breakfast and meals are available. "
            "Can the kitchen prepare vegetarian food? Are there nearby "
            "vegetarian restaurants?"
        )
    elif prefs.food_pref == "non-veg":
        must_verify.append(
            "DIETARY: Confirm non-veg meal options at the restaurant."
        )
    if prefs.smoking:
        must_verify.append("SMOKING: Ask if smoking rooms are available.")
    if not prefs.smoking:
        must_verify.append("NON-SMOKING: Confirm non-smoking rooms available.")
    for amenity in prefs.amenities:
        must_verify.append(f"AMENITY: Ask if {amenity} is available.")
    if prefs.special_requests:
        must_verify.append(f"SPECIAL: {prefs.special_requests}")

    verify_block = "\n".join(f"  - {v}" for v in must_verify) if must_verify else "  - None specific"

    prompt = f"""\
You are a warm, professional travel coordinator calling a hotel on behalf of a traveler.
You are NOT a robot reading a checklist. You are a pleasant, calm, locally-aware person
having a real conversation with the hotel's reservations staff.

=== IDENTITY ===
When the hotel picks up, say:
{greeting}

If they ask who you are:
"I'm a travel assistant helping a guest find the right hotel for their trip."

If they are not the reservations team, politely ask to be connected or ask for the
best phone/WhatsApp contact for reservations.

If they are busy: "No problem. Is there a better time to call back, or would
WhatsApp or email work better for the reservation details?"

=== TRIP CONTEXT ===
- Check-in: {prefs.check_in}
- Check-out: {prefs.check_out}
- Duration: {nights} nights
- Guests: {prefs.guests} adults
- Budget target: around Rs.{budget_target:,} per night (can stretch to Rs.{budget_soft_max:,})
- Destination: {prefs.destination}

=== CONVERSATION FLOW ===
Follow this order naturally. Do NOT rush through like a checklist.
Listen to their answers. Ask follow-ups when appropriate.

1. AVAILABILITY (start here)
   "The guest is looking at check-in on {prefs.check_in} and check-out on
   {prefs.check_out}, that's {nights} nights, for {prefs.guests} adults.
   Would you have availability for those dates?"

   If not available: ask about nearby dates or alternate room types.
   If still no: thank them and end politely.

2. ROOM CATEGORIES
   "What room categories would you recommend for a comfortable stay?"
   Let THEM suggest. Do NOT ask "what is your cheapest room?"
   Ask about bed type if relevant.

3. RATES AND TOTAL PRICE
   For each room option mentioned, ask:
   - Nightly rate
   - Total for all {nights} nights
   - Whether taxes and service charges are included
   - Currency (assume INR for India)
   "Could you confirm the rate per night and the total for all {nights} nights,
   including taxes and service charges?"

4. INCLUSIONS
   - Is breakfast included?
   - Is WiFi included?
   - Any other inclusions with the room?

5. CANCELLATION AND PAYMENT
   - What is the cancellation policy?
   - Is it pay-at-property or prepaid?
   - Can the room be held without payment?

6. PREFERENCE VERIFICATION
{verify_block}

7. NEGOTIATION (only after you have availability and base rate)
   Be warm, not pushy. Ask for VALUE, not just discount.

   Level 1: "Is this the best direct rate available if the guest books with
   the hotel directly rather than through an online platform?"

   Level 2: "Since it's a {nights}-night stay, would there be any better
   package or long-stay rate?"

   Level 3: "If the rate can't be reduced, could breakfast, a room upgrade,
   or late checkout be included?"

   Level 4 (only if needed): "The guest is trying to stay close to around
   Rs.{budget_target:,} per night. Is there any room or package that would
   come closer to that while still being comfortable?"

   STOP negotiating after one clear refusal. Do NOT pressure.

8. WRITTEN QUOTE
   "Could you send the best available offer by WhatsApp or email so I can
   share it clearly with the guest?"
   Ask for their best contact for follow-up.

9. FINAL CONFIRMATION
   Before ending, summarize what you understood:
   "Just to confirm: for {prefs.check_in} to {prefs.check_out}, {nights} nights,
   {prefs.guests} adults, the [room category] is available at [total amount]
   including [taxes/breakfast], with [cancellation policy]. Is that correct?"

10. CLOSE
    "Thank you so much for your help. The guest will get back to you shortly."

=== VOICE AND PERSONALITY ===
- Sound warm, calm, respectful, and unhurried
- Be comfortable with pauses -- don't fill every silence
- Ask follow-up questions naturally
- If you don't understand something, say "Sorry, could you repeat that?"
- Do NOT sound robotic, aggressive, or like a call-center script

=== HARD RULES ===
- NEVER mention the hotel's name back to them
- NEVER lie about competitor prices or claim a fake booking
- NEVER promise payment or confirm a booking
- NEVER collect card numbers, passport details, or sensitive data
- NEVER continue pushing after a clear price refusal
- NEVER pretend to be the actual traveler
- Keep the call under 3 minutes
- If recording consent is needed: "This call may be recorded to accurately
  share the quote with the traveler. Is that okay?"
"""

    logger.info(
        "build_call_prompt hotel=%s language=%s nights=%d budget=%d verify_items=%d prompt_len=%d",
        hotel.name,
        prefs.language_pref,
        nights,
        budget_target,
        len(must_verify),
        len(prompt),
    )
    return prompt


# ---------------------------------------------------------------------------
# Rich extraction tool schema
# ---------------------------------------------------------------------------
_EXTRACT_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_hotel_call_report",
        "description": (
            "Extract structured hotel booking information from a phone call "
            "transcript. Include room options, pricing, preference checks, "
            "negotiation results, and confidence scores."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "availability": {
                    "type": ["boolean", "null"],
                    "description": "Whether the hotel has rooms for the requested dates.",
                },
                "room_options": {
                    "type": "array",
                    "description": "Room categories quoted during the call.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "room_category": {"type": ["string", "null"]},
                            "bed_type": {"type": ["string", "null"]},
                            "nightly_rate": {
                                "type": ["integer", "null"],
                                "description": "Per-night rate in INR.",
                            },
                            "total_rate": {
                                "type": ["integer", "null"],
                                "description": "Total stay rate in INR.",
                            },
                            "taxes_included": {"type": ["boolean", "null"]},
                            "breakfast_included": {"type": ["boolean", "null"]},
                        },
                    },
                },
                "best_nightly_rate": {
                    "type": ["integer", "null"],
                    "description": "Best nightly rate quoted in INR (after negotiation).",
                },
                "total_price": {
                    "type": ["integer", "null"],
                    "description": "Total stay price in INR including taxes if clarified.",
                },
                "taxes_included": {
                    "type": ["boolean", "null"],
                    "description": "Whether taxes are included in the quoted rate. null if unclear.",
                },
                "breakfast_included": {
                    "type": ["boolean", "null"],
                    "description": "Whether breakfast is included.",
                },
                "cancellation_policy": {
                    "type": ["string", "null"],
                    "description": "Cancellation terms mentioned.",
                },
                "payment_terms": {
                    "type": ["string", "null"],
                    "description": "Payment method: 'pay at property', 'prepaid', etc.",
                },
                "promotions": {
                    "type": ["string", "null"],
                    "description": "Any discounts, packages, or promotional offers.",
                },
                "dietary_supported": {
                    "type": ["boolean", "null"],
                    "description": "Whether the user's dietary preference is supported.",
                },
                "dietary_details": {
                    "type": ["string", "null"],
                    "description": "Details about dietary support.",
                },
                "quiet_room_available": {
                    "type": ["boolean", "null"],
                    "description": "Whether a quiet room can be requested.",
                },
                "negotiation_discount": {
                    "type": "boolean",
                    "description": "Whether a price discount was obtained.",
                },
                "negotiation_value_adds": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Value-adds obtained: breakfast, upgrade, late checkout, etc.",
                },
                "negotiation_staff_position": {
                    "type": ["string", "null"],
                    "description": "Staff's final position on pricing/negotiation.",
                },
                "staff_name": {
                    "type": ["string", "null"],
                    "description": "Name of the staff member spoken to.",
                },
                "follow_up_contact": {
                    "type": ["string", "null"],
                    "description": "WhatsApp/email/phone for written quote follow-up.",
                },
                "written_quote_requested": {
                    "type": "boolean",
                    "description": "Whether a written quote was requested.",
                },
                "transcript_summary": {
                    "type": "string",
                    "description": (
                        "2-3 sentence summary of the call outcome for the user. "
                        "Include: availability, best rate, key inclusions, tradeoffs."
                    ),
                },
                "confidence_rate": {
                    "type": "number",
                    "description": "Confidence in the rate accuracy (0-1).",
                },
                "confidence_availability": {
                    "type": "number",
                    "description": "Confidence in availability (0-1).",
                },
                "confidence_dietary": {
                    "type": "number",
                    "description": "Confidence in dietary info (0-1).",
                },
            },
            "required": [
                "availability",
                "best_nightly_rate",
                "total_price",
                "transcript_summary",
            ],
        },
    },
}


# ---------------------------------------------------------------------------
# Transcript extraction
# ---------------------------------------------------------------------------
async def extract_call_data(
    transcript: str,
    hotel: Hotel,
    openai_client,
) -> CallResult:
    """Extract rich structured data from a call transcript.

    Uses GPT function calling to produce room options, pricing,
    preference checks, negotiation results, and confidence scores.
    """
    if not transcript or len(transcript.strip()) < 20:
        logger.warning("extract_call_data skipped -- transcript too short hotel=%s", hotel.name)
        return CallResult(
            hotel=hotel,
            status="completed",
            transcript=transcript,
            transcript_summary="Call connected but no meaningful conversation captured.",
        )

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-5.4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are extracting structured hotel booking data from a "
                        "phone call transcript. The call was to a hotel to check "
                        "availability and rates on behalf of a traveler.\n\n"
                        f"Hotel: {hotel.name}\n"
                        f"Address: {hotel.address}\n\n"
                        "Extract ALL information discussed. For any field not "
                        "discussed or unclear, use null. Assign confidence scores "
                        "based on how clearly the information was stated."
                    ),
                },
                {"role": "user", "content": transcript},
            ],
            tools=[_EXTRACT_TOOL],
            tool_choice={"type": "function", "function": {"name": "extract_hotel_call_report"}},
            temperature=0.0,
        )

        tool_call = response.choices[0].message.tool_calls[0]
        d = json.loads(tool_call.function.arguments)

        usage = response.usage
        tokens = usage.total_tokens if usage else 0

        # Build room options
        room_options = [
            RoomOption(
                room_category=r.get("room_category"),
                bed_type=r.get("bed_type"),
                nightly_rate=r.get("nightly_rate"),
                total_rate=r.get("total_rate"),
                taxes_included=r.get("taxes_included"),
                breakfast_included=r.get("breakfast_included"),
                confidence=0.8,
            )
            for r in d.get("room_options", [])
        ]

        # Build preference checks
        pref_checks: dict[str, PreferenceCheck] = {}
        if d.get("dietary_supported") is not None or d.get("dietary_details"):
            pref_checks["dietary"] = PreferenceCheck(
                supported=d.get("dietary_supported"),
                details=d.get("dietary_details"),
                confidence=d.get("confidence_dietary", 0.5),
            )
        if d.get("quiet_room_available") is not None:
            pref_checks["quiet_room"] = PreferenceCheck(
                supported=d.get("quiet_room_available"),
                confidence=0.7,
            )

        # Build negotiation result
        negotiation = None
        if d.get("negotiation_discount") or d.get("negotiation_value_adds"):
            negotiation = NegotiationResult(
                discount_obtained=d.get("negotiation_discount", False),
                value_adds=d.get("negotiation_value_adds", []),
                staff_position=d.get("negotiation_staff_position"),
            )

        # Build confidence dict
        confidence = {}
        for key in ("rate", "availability", "dietary"):
            val = d.get(f"confidence_{key}")
            if val is not None:
                confidence[key] = val

        result = CallResult(
            hotel=hotel,
            status="completed",
            # backward-compat fields
            direct_price=d.get("best_nightly_rate"),
            availability=d.get("availability"),
            promotions=d.get("promotions"),
            cancellation_policy=d.get("cancellation_policy"),
            transcript=transcript,
            call_duration=None,
            # rich fields
            room_options=room_options,
            total_price=d.get("total_price"),
            taxes_included=d.get("taxes_included"),
            breakfast_included=d.get("breakfast_included"),
            payment_terms=d.get("payment_terms"),
            preference_checks=pref_checks,
            negotiation=negotiation,
            staff_name=d.get("staff_name"),
            follow_up_contact=d.get("follow_up_contact"),
            written_quote_requested=d.get("written_quote_requested", False),
            transcript_summary=d.get("transcript_summary", ""),
            confidence=confidence,
        )

        logger.info(
            "extract_call_data hotel=%s price=%s total=%s avail=%s rooms=%d "
            "negotiation=%s tokens=%d",
            hotel.name,
            result.direct_price,
            result.total_price,
            result.availability,
            len(room_options),
            "yes" if negotiation else "no",
            tokens,
        )
        return result

    except Exception:
        logger.exception("extract_call_data failed hotel=%s", hotel.name)
        return CallResult(
            hotel=hotel,
            status="completed",
            transcript=transcript,
            transcript_summary="Call completed but data extraction failed.",
        )
