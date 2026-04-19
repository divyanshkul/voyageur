"""Dynamic task planner (Phase 5b).

Given user input and current state, decides what the next steps should be
(e.g. skip preferences if already provided) and parses user approval of
the hotel shortlist.
"""

from __future__ import annotations

import logging
import re

from thefuzz import fuzz

from app.models import Hotel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Word → number mapping for "first two", "top three", etc.
# ---------------------------------------------------------------------------
_WORD_NUMS: dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

# Keywords
_RESET_KEYWORDS = ("start over", "restart", "begin again", "change preferences")
_RESEARCH_KEYWORDS = ("search again", "different hotels", "more options", "look again")
_CANCEL_KEYWORDS = ("none", "cancel", "no thanks", "skip calling", "don't call")
_ALL_KEYWORDS = ("all", "call all", "call them all", "every one", "all of them")


# ---------------------------------------------------------------------------
# Next-action routing (rule-based, no LLM)
# ---------------------------------------------------------------------------
def determine_next_action(user_input: str, current_stage: str | None) -> str:
    """Map *user_input* + *current_stage* to the next graph node name.

    Pure rule-based routing -- no LLM needed for MVP.
    """
    lower = user_input.lower().strip()

    # -- Reset commands always restart preference collection ----------------
    if any(kw in lower for kw in _RESET_KEYWORDS):
        logger.info(
            "determine_next_action stage=%s decision=collect_preferences (reset)",
            current_stage,
        )
        return "collect_preferences"

    # -- Re-search (only valid after preference collection is done) ---------
    if any(kw in lower for kw in _RESEARCH_KEYWORDS):
        if current_stage and current_stage != "collecting":
            logger.info(
                "determine_next_action stage=%s decision=research_hotels (re-search)",
                current_stage,
            )
            return "research_hotels"

    # -- Stage-based default ------------------------------------------------
    _STAGE_MAP: dict[str | None, str] = {
        None: "collect_preferences",
        "collecting": "collect_preferences",
        "researching": "research_hotels",
        "approving": "get_approval",
        "calling": "call_hotels",
        "compiling": "compile_report",
        "done": "collect_preferences",
    }
    decision = _STAGE_MAP.get(current_stage, "collect_preferences")
    logger.info(
        "determine_next_action stage=%s decision=%s", current_stage, decision,
    )
    return decision


# ---------------------------------------------------------------------------
# Approval parser
# ---------------------------------------------------------------------------
def parse_approval(
    user_input: str,
    hotel_candidates: list[Hotel],
) -> list[Hotel]:
    """Parse which hotels the user approved from the shortlist.

    Handles:
      - ``"all"`` / ``"call all"``  → all hotels
      - ``"1, 3, 5"`` / ``"1 and 3"``  → by 1-indexed position
      - ``"first two"`` / ``"top 3"``  → first N
      - ``"none"`` / ``"cancel"``  → empty list
      - Hotel name substring  → fuzzy match via thefuzz
      - Unparseable  → all hotels (safe default)
    """
    if not hotel_candidates:
        logger.info("parse_approval no_candidates")
        return []

    stripped = user_input.strip()
    lower = stripped.lower()

    # -- Exact place_id match (sent by frontend) ---------------------------
    if stripped.startswith("APPROVE_IDS:"):
        ids_str = stripped[len("APPROVE_IDS:"):]
        approved_ids = set(id.strip() for id in ids_str.split(",") if id.strip())
        result = [h for h in hotel_candidates if h.place_id in approved_ids]
        logger.info(
            "parse_approval parsed=place_ids requested=%d matched=%d",
            len(approved_ids),
            len(result),
        )
        return result

    # -- Demo call: pick one hotel, swap phone to demo number ---------------
    if stripped.startswith("DEMO_CALL:"):
        parts = stripped[len("DEMO_CALL:"):].split(":", 1)
        place_id = parts[0].strip()
        demo_phone = parts[1].strip() if len(parts) > 1 else ""
        for h in hotel_candidates:
            if h.place_id == place_id:
                demo_hotel = h.model_copy(update={"phone": demo_phone})
                logger.info(
                    "parse_approval parsed=demo_call hotel=%s phone=****%s",
                    demo_hotel.name,
                    demo_phone[-4:],
                )
                return [demo_hotel]
        # place_id not found -- try first hotel as fallback
        if hotel_candidates:
            demo_hotel = hotel_candidates[0].model_copy(update={"phone": demo_phone})
            logger.info(
                "parse_approval parsed=demo_call fallback hotel=%s",
                demo_hotel.name,
            )
            return [demo_hotel]
        return []

    # -- None / cancel -----------------------------------------------------
    if any(kw in lower for kw in _CANCEL_KEYWORDS):
        logger.info("parse_approval parsed=none count=0")
        return []

    # -- All ---------------------------------------------------------------
    if any(kw in lower for kw in _ALL_KEYWORDS):
        logger.info("parse_approval parsed=all count=%d", len(hotel_candidates))
        return list(hotel_candidates)

    # -- "first/top N" (digit) ---------------------------------------------
    m = re.search(r"(?:first|top)\s+(\d+)", lower)
    if m:
        n = min(int(m.group(1)), len(hotel_candidates))
        logger.info("parse_approval parsed=first_%d count=%d", n, n)
        return hotel_candidates[:n]

    # -- "first/top <word>" (e.g. "first two") -----------------------------
    m = re.search(r"(?:first|top)\s+(\w+)", lower)
    if m and m.group(1) in _WORD_NUMS:
        n = min(_WORD_NUMS[m.group(1)], len(hotel_candidates))
        logger.info("parse_approval parsed=first_%d_word count=%d", n, n)
        return hotel_candidates[:n]

    # -- Number selection: "1, 3, 5" or "1 and 3" -------------------------
    numbers = re.findall(r"\d+", lower)
    if numbers:
        indices = [int(x) - 1 for x in numbers]           # 1-indexed → 0
        result = [
            hotel_candidates[i]
            for i in indices
            if 0 <= i < len(hotel_candidates)
        ]
        if result:
            logger.info(
                "parse_approval parsed=indices=%s count=%d", numbers, len(result),
            )
            return result

    # -- Fuzzy hotel-name match --------------------------------------------
    matched: list[Hotel] = []
    for hotel in hotel_candidates:
        score = fuzz.partial_ratio(hotel.name.lower(), lower)
        if score >= 75:
            matched.append(hotel)
    if matched:
        logger.info("parse_approval parsed=name_match count=%d", len(matched))
        return matched

    # -- Fallback: return all (safe default) -------------------------------
    logger.info(
        "parse_approval unparseable, default=all count=%d",
        len(hotel_candidates),
    )
    return list(hotel_candidates)
