"""Assertion helpers used by the eval runner.

Every helper returns ``(passed: bool, detail: str)``. The runner aggregates
these into a per-case verdict. No exceptions are raised on assertion failure
— failures are data, not crashes.
"""

from __future__ import annotations

import re
from typing import Any


def eq(actual: Any, expected: Any, *, field: str = "") -> tuple[bool, str]:
    ok = actual == expected
    return ok, (
        f"{field} ok" if ok else f"{field} expected={expected!r} actual={actual!r}"
    )


def in_range(
    actual: float | int | None,
    *,
    low: float | int | None = None,
    high: float | int | None = None,
    field: str = "",
) -> tuple[bool, str]:
    if actual is None:
        return False, f"{field} is None"
    if low is not None and actual < low:
        return False, f"{field}={actual} < low={low}"
    if high is not None and actual > high:
        return False, f"{field}={actual} > high={high}"
    return True, f"{field}={actual} in [{low}, {high}]"


def contains(haystack: str | None, needle: str, *, field: str = "") -> tuple[bool, str]:
    if not haystack:
        return False, f"{field} is empty"
    ok = needle.lower() in haystack.lower()
    return ok, (
        f"{field} contains {needle!r}"
        if ok
        else f"{field} missing {needle!r}"
    )


def matches(haystack: str | None, pattern: str, *, field: str = "") -> tuple[bool, str]:
    if not haystack:
        return False, f"{field} is empty"
    ok = re.search(pattern, haystack) is not None
    return ok, (
        f"{field} matches /{pattern}/"
        if ok
        else f"{field} does not match /{pattern}/"
    )


def is_one_of(actual: Any, options: list[Any], *, field: str = "") -> tuple[bool, str]:
    ok = actual in options
    return ok, (
        f"{field}={actual!r} in options"
        if ok
        else f"{field}={actual!r} not in {options!r}"
    )


def all_pass(*results: tuple[bool, str]) -> tuple[bool, list[str]]:
    details = [detail for _, detail in results]
    passed = all(r[0] for r in results)
    return passed, details
