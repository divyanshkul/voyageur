"""Voyageur eval harness — CLI runner.

Usage:
    python -m evals.run_evals                 # all cases, fail on regression
    python -m evals.run_evals --suite offline # offline cases only (no API keys)
    python -m evals.run_evals --suite online  # requires OPENAI_API_KEY
    python -m evals.run_evals --case pricing_cheapest_direct_wins
    python -m evals.run_evals --update-baseline

Exits:
    0 — all cases passed, no regression vs baseline
    1 — at least one case failed OR per-suite pass-rate dropped below baseline
    2 — runner error (bad case file, etc.)
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import sys
import time
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from evals.evaluators import EVALUATORS, EvalOutcome  # noqa: E402

ROOT = Path(__file__).parent
CASES_DIR = ROOT / "cases"
REPORTS_DIR = ROOT / "reports"
BASELINE_PATH = ROOT / "baseline.json"


def load_cases(suite_filter: str | None, case_filter: str | None) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted(CASES_DIR.glob("*.json")):
        with path.open() as fh:
            case = json.load(fh)
        case["_path"] = str(path.relative_to(ROOT.parent))
        if suite_filter and case.get("suite") != suite_filter:
            continue
        if case_filter and case.get("id") != case_filter:
            continue
        cases.append(case)
    return cases


async def run_case(case: dict[str, Any]) -> EvalOutcome:
    kind = case.get("evaluator")
    fn = EVALUATORS.get(kind)
    if fn is None:
        return EvalOutcome(
            case_id=case.get("id", "<unknown>"),
            suite=case.get("suite", "unknown"),
            passed=False,
            reason=f"unknown evaluator: {kind}",
        )

    t0 = time.monotonic()
    try:
        maybe = fn(case)
        outcome = await maybe if inspect.isawaitable(maybe) else maybe
    except Exception as exc:  # noqa: BLE001
        outcome = EvalOutcome(
            case_id=case.get("id", "<unknown>"),
            suite=case.get("suite", "unknown"),
            passed=False,
            reason=f"exception: {type(exc).__name__}: {exc}",
        )
    outcome.latency_ms = (time.monotonic() - t0) * 1000
    return outcome


def summarise(outcomes: list[EvalOutcome]) -> dict[str, Any]:
    suites: dict[str, dict[str, int]] = {}
    for o in outcomes:
        s = suites.setdefault(
            o.suite, {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
        )
        s["total"] += 1
        if o.skipped:
            s["skipped"] += 1
        elif o.passed:
            s["passed"] += 1
        else:
            s["failed"] += 1

    for s in suites.values():
        ran = s["total"] - s["skipped"]
        s["pass_rate"] = round(s["passed"] / ran, 3) if ran else None  # type: ignore[assignment]

    return {
        "totals": {
            "cases": len(outcomes),
            "passed": sum(1 for o in outcomes if o.passed),
            "failed": sum(1 for o in outcomes if not o.passed and not o.skipped),
            "skipped": sum(1 for o in outcomes if o.skipped),
        },
        "suites": suites,
    }


def write_json_report(outcomes: list[EvalOutcome], summary: dict[str, Any]) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / "latest.json"
    payload = {
        "summary": summary,
        "cases": [
            {
                "id": o.case_id,
                "suite": o.suite,
                "passed": o.passed,
                "skipped": o.skipped,
                "reason": o.reason,
                "details": o.details,
                "latency_ms": round(o.latency_ms, 1),
            }
            for o in outcomes
        ],
    }
    path.write_text(json.dumps(payload, indent=2))
    return path


def write_markdown_report(outcomes: list[EvalOutcome], summary: dict[str, Any]) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / "latest.md"
    lines: list[str] = ["# Voyageur eval report", ""]
    t = summary["totals"]
    lines.append(
        f"**Totals:** {t['passed']}/{t['cases']} passed · {t['failed']} failed · {t['skipped']} skipped"
    )
    lines.append("")
    lines.append("## Per-suite")
    lines.append("")
    lines.append("| suite | passed | failed | skipped | pass_rate |")
    lines.append("|---|---|---|---|---|")
    for name, s in sorted(summary["suites"].items()):
        lines.append(
            f"| {name} | {s['passed']} | {s['failed']} | {s['skipped']} | {s['pass_rate']} |"
        )
    lines.append("")
    lines.append("## Cases")
    for o in outcomes:
        status = "PASS" if o.passed else ("SKIP" if o.skipped else "FAIL")
        lines.append(f"- **{status}** `{o.case_id}` ({o.suite}, {o.latency_ms:.0f}ms)")
        if o.reason:
            lines.append(f"    - reason: {o.reason}")
        for d in o.details:
            lines.append(f"    - {d}")
    path.write_text("\n".join(lines) + "\n")
    return path


def load_baseline() -> dict[str, Any]:
    if not BASELINE_PATH.exists():
        return {}
    with BASELINE_PATH.open() as fh:
        return json.load(fh)


def write_baseline(summary: dict[str, Any]) -> None:
    BASELINE_PATH.write_text(json.dumps(summary, indent=2))


def check_regression(summary: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    """Return a list of regression messages, empty if none."""
    if not baseline:
        return []
    issues: list[str] = []
    base_suites = baseline.get("suites", {})
    for name, s in summary["suites"].items():
        base = base_suites.get(name)
        if not base or base.get("pass_rate") is None:
            continue
        if s["pass_rate"] is None:
            continue
        if s["pass_rate"] < base["pass_rate"]:
            issues.append(
                f"suite={name} pass_rate={s['pass_rate']} dropped below baseline={base['pass_rate']}"
            )
    return issues


async def main_async(args: argparse.Namespace) -> int:
    cases = load_cases(args.suite, args.case)
    if not cases:
        print("No cases matched the given filters.", file=sys.stderr)
        return 2

    print(f"Running {len(cases)} case(s)…")
    outcomes: list[EvalOutcome] = []
    for case in cases:
        o = await run_case(case)
        outcomes.append(o)
        tag = "PASS" if o.passed else ("SKIP" if o.skipped else "FAIL")
        print(f"  [{tag}] {o.case_id} ({o.suite})")
        if not o.passed and not o.skipped:
            if o.reason:
                print(f"        reason: {o.reason}")
            for d in o.details:
                print(f"        - {d}")

    summary = summarise(outcomes)
    json_path = write_json_report(outcomes, summary)
    md_path = write_markdown_report(outcomes, summary)
    print(f"\nReports: {json_path}  ·  {md_path}")

    if args.update_baseline:
        write_baseline(summary)
        print(f"Baseline updated → {BASELINE_PATH}")
        return 0

    baseline = load_baseline()
    regressions = check_regression(summary, baseline)
    fails = summary["totals"]["failed"]

    if fails:
        print(f"\nFAIL: {fails} case(s) failed.", file=sys.stderr)
    if regressions:
        print("\nREGRESSION vs baseline:", file=sys.stderr)
        for msg in regressions:
            print(f"  - {msg}", file=sys.stderr)

    if args.no_fail:
        return 0
    return 1 if (fails or regressions) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Voyageur evals.")
    parser.add_argument("--suite", choices=["offline", "online"], default=None)
    parser.add_argument("--case", default=None, help="Run a single case by id")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Overwrite baseline.json with current results",
    )
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Always exit 0 (useful for local triage)",
    )
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
