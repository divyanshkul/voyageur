"""Evaluator functions — one per case kind.

Each evaluator takes a case dict and returns ``EvalOutcome``. The runner
dispatches to the right evaluator based on ``case["evaluator"]``.

Offline evaluators exercise pure-Python logic (ranker, pricing, validation,
normalization) and never call external APIs.

Online evaluators hit OpenAI — they are skipped when ``OPENAI_API_KEY`` is
absent.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from app.agents.preference_validation import (
    normalize_destination,
    validate_preferences,
)
from app.agents.report_pricing import compare_prices
from app.agents.research_ranker import rank_hotels
from evals import fixtures, judges


@dataclass
class EvalOutcome:
    case_id: str
    suite: str
    passed: bool
    skipped: bool = False
    reason: str = ""
    details: list[str] = field(default_factory=list)
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# Offline evaluators
# ---------------------------------------------------------------------------


def eval_ranker(case: dict[str, Any]) -> EvalOutcome:
    """Exercise rank_hotels with synthetic candidates + OTA prices."""
    hotels = fixtures.hotels_from_list(case["input"]["hotels"])
    prefs = fixtures.preferences_from_dict(case["input"]["preferences"])
    ota_prices = case["input"].get("ota_prices", {})

    ranked = rank_hotels(hotels, prefs, ota_prices)
    expect = case["expect"]
    results: list[tuple[bool, str]] = []

    if "top_name" in expect:
        top = ranked[0].name if ranked else None
        results.append(judges.eq(top, expect["top_name"], field="top_name"))
    if "min_returned" in expect:
        results.append(
            judges.in_range(
                len(ranked), low=expect["min_returned"], field="returned_count"
            )
        )
    if "top_score_min" in expect:
        score = ranked[0].match_score if ranked else None
        results.append(
            judges.in_range(score, low=expect["top_score_min"], field="top_score")
        )
    if "excludes" in expect:
        names = {h.name for h in ranked}
        for bad in expect["excludes"]:
            results.append(
                judges.eq(bad not in names, True, field=f"excludes:{bad}")
            )

    ok, details = judges.all_pass(*results) if results else (True, ["no-assertions"])
    return EvalOutcome(
        case_id=case["id"], suite=case["suite"], passed=ok, details=details
    )


def eval_pricing(case: dict[str, Any]) -> EvalOutcome:
    """Exercise compare_prices with synthetic call results."""
    call_results = fixtures.call_results_from_list(
        [dict(it) for it in case["input"]["call_results"]]
    )
    comparisons = compare_prices(call_results)
    expect = case["expect"]
    results: list[tuple[bool, str]] = []

    if "top_name" in expect:
        top = comparisons[0].hotel.name if comparisons else None
        results.append(judges.eq(top, expect["top_name"], field="top_name"))
    if "verdicts_in_order" in expect:
        actual_verdicts = [c.verdict for c in comparisons]
        results.append(
            judges.eq(
                actual_verdicts, expect["verdicts_in_order"], field="verdict_order"
            )
        )
    if "savings_percent_min" in expect:
        best = comparisons[0].savings_percent if comparisons else None
        results.append(
            judges.in_range(
                best, low=expect["savings_percent_min"], field="best_savings"
            )
        )

    ok, details = judges.all_pass(*results) if results else (True, ["no-assertions"])
    return EvalOutcome(
        case_id=case["id"], suite=case["suite"], passed=ok, details=details
    )


def eval_destination(case: dict[str, Any]) -> EvalOutcome:
    """Exercise normalize_destination alias map."""
    actual = normalize_destination(case["input"]["alias"])
    ok, detail = judges.eq(actual, case["expect"]["canonical"], field="canonical")
    return EvalOutcome(
        case_id=case["id"], suite=case["suite"], passed=ok, details=[detail]
    )


def eval_validation(case: dict[str, Any]) -> EvalOutcome:
    """Exercise validate_preferences on a prefs payload."""
    prefs = fixtures.preferences_from_dict(case["input"]["preferences"])
    valid, issues = validate_preferences(prefs)
    expect = case["expect"]
    results: list[tuple[bool, str]] = [
        judges.eq(valid, expect["valid"], field="valid"),
    ]
    if "issue_contains" in expect:
        joined = " | ".join(issues)
        for needle in expect["issue_contains"]:
            results.append(judges.contains(joined, needle, field="issues"))

    ok, details = judges.all_pass(*results)
    return EvalOutcome(
        case_id=case["id"], suite=case["suite"], passed=ok, details=details
    )


# ---------------------------------------------------------------------------
# Online evaluators (require OPENAI_API_KEY)
# ---------------------------------------------------------------------------


async def eval_preference(case: dict[str, Any]) -> EvalOutcome:
    """Drive PreferenceAgent through one or more user turns and check extraction.

    Skipped if OPENAI_API_KEY is missing.
    """
    if not os.getenv("OPENAI_API_KEY"):
        return EvalOutcome(
            case_id=case["id"],
            suite=case["suite"],
            passed=False,
            skipped=True,
            reason="OPENAI_API_KEY not set",
        )

    # Imports deferred so the offline suite doesn't require openai at import.
    from openai import AsyncOpenAI

    from app.agents.preference import PreferenceAgent

    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    agent = PreferenceAgent(client)

    turns = case["input"]["turns"]
    resolved_turns = [_resolve_date_tokens(t) for t in turns]

    prefs = None
    final_reply = ""
    for turn in resolved_turns:
        reply, prefs = await agent.run([{"role": "user", "content": turn}])
        final_reply = reply
        if prefs is not None:
            break

    expect = case["expect"]
    results: list[tuple[bool, str]] = []

    if expect.get("extracted", False):
        results.append(judges.eq(prefs is not None, True, field="extracted"))
    if prefs is not None:
        pe = expect.get("preferences", {})
        if "destination_contains" in pe:
            results.append(
                judges.contains(
                    prefs.destination, pe["destination_contains"], field="destination"
                )
            )
        if "guests" in pe:
            results.append(judges.eq(prefs.guests, pe["guests"], field="guests"))
        if "budget_max_in_range" in pe:
            low, high = pe["budget_max_in_range"]
            results.append(
                judges.in_range(
                    prefs.budget_max, low=low, high=high, field="budget_max"
                )
            )
        if "nights_in_range" in pe:
            low, high = pe["nights_in_range"]
            nights = (prefs.check_out - prefs.check_in).days
            results.append(
                judges.in_range(nights, low=low, high=high, field="nights")
            )
    if "reply_contains" in expect and prefs is None:
        results.append(
            judges.contains(final_reply, expect["reply_contains"], field="reply")
        )

    ok, details = judges.all_pass(*results) if results else (True, ["no-assertions"])
    return EvalOutcome(
        case_id=case["id"], suite=case["suite"], passed=ok, details=details
    )


async def eval_report(case: dict[str, Any]) -> EvalOutcome:
    """Run ReportAgent on synthetic call results and check report shape."""
    if not os.getenv("OPENAI_API_KEY"):
        return EvalOutcome(
            case_id=case["id"],
            suite=case["suite"],
            passed=False,
            skipped=True,
            reason="OPENAI_API_KEY not set",
        )

    from openai import AsyncOpenAI

    from app.agents.reporter import ReportAgent

    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    agent = ReportAgent(client)

    prefs = fixtures.preferences_from_dict(case["input"]["preferences"])
    results_in = fixtures.call_results_from_list(
        [dict(it) for it in case["input"]["call_results"]]
    )

    report = await agent.run(results_in, prefs)

    expect = case["expect"]
    checks: list[tuple[bool, str]] = []

    if "top_pick_name" in expect:
        actual = report.top_pick.hotel.name if report.top_pick else None
        checks.append(judges.eq(actual, expect["top_pick_name"], field="top_pick"))
    if "summary_contains" in expect:
        for needle in expect["summary_contains"]:
            checks.append(judges.contains(report.summary, needle, field="summary"))
    if "markdown_contains" in expect:
        for needle in expect["markdown_contains"]:
            checks.append(judges.contains(report.markdown, needle, field="markdown"))

    ok, details = judges.all_pass(*checks) if checks else (True, ["no-assertions"])
    return EvalOutcome(
        case_id=case["id"], suite=case["suite"], passed=ok, details=details
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_date_tokens(text: str) -> str:
    """Replace {today+Nd} / {today-Nd} tokens inside a string."""
    import re
    from datetime import date, timedelta

    def _sub(match: re.Match[str]) -> str:
        sign = 1 if match.group(1) == "+" else -1
        n = int(match.group(2))
        return (date.today() + timedelta(days=sign * n)).isoformat()

    return re.sub(r"\{today([+-])(\d+)d\}", _sub, text)


EVALUATORS: dict[str, Any] = {
    "ranker": eval_ranker,
    "pricing": eval_pricing,
    "destination": eval_destination,
    "validation": eval_validation,
    "preference": eval_preference,
    "report": eval_report,
}
