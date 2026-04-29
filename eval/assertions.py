"""Assertion helpers for golden set eval cases.

Each check function returns (passed: bool, reason: str).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalResult:
    """Result of evaluating a single test case."""

    case_id: str
    passed: bool
    reason: str
    response_text: str = ""
    was_blocked: bool = False
    latency_ms: float = 0.0
    checks: list[dict] = field(default_factory=list)


def check_blocked(response_text: str, expected_blocked: bool) -> tuple[bool, str]:
    """Check if the response was blocked (contains 'Blocked by:' indicator)."""
    actually_blocked = "Blocked by" in response_text or "🛡️" in response_text

    if expected_blocked and not actually_blocked:
        return False, "Expected response to be BLOCKED but it was allowed through"
    if not expected_blocked and actually_blocked:
        return False, f"Expected response to be ALLOWED but it was blocked: {response_text[:200]}"
    return True, "blocked status matches expectation"


def check_contains(response_text: str, expected_substring: str) -> tuple[bool, str]:
    """Check if response contains exact substring (case-insensitive)."""
    if expected_substring.lower() in response_text.lower():
        return True, f"Found '{expected_substring}'"
    return False, f"Output missing: '{expected_substring}'"


def check_contains_any(response_text: str, candidates: list[str]) -> tuple[bool, str]:
    """Check if response contains at least one of the candidate substrings."""
    for candidate in candidates:
        if candidate.lower() in response_text.lower():
            return True, f"Found '{candidate}'"
    return False, f"Output missing ALL of: {candidates}"


def check_not_contains(response_text: str, forbidden: list[str]) -> tuple[bool, str]:
    """Check that response does NOT contain any of the forbidden strings."""
    for s in forbidden:
        if s.lower() in response_text.lower():
            return False, f"Output should NOT contain: '{s}'"
    return True, "No forbidden content found"


def run_assertions(response_text: str, expect: dict) -> EvalResult:
    """Run all assertions defined in the 'expect' block against the response.

    Returns an EvalResult with pass/fail and detailed check results.
    """
    checks: list[dict] = []
    all_passed = True

    # 1. Blocked check
    if "blocked" in expect:
        passed, reason = check_blocked(response_text, expect["blocked"])
        checks.append({"check": "blocked", "passed": passed, "reason": reason})
        if not passed:
            all_passed = False

    # 2. Contains check (single string)
    if "output_contains" in expect:
        passed, reason = check_contains(response_text, expect["output_contains"])
        checks.append({"check": "output_contains", "passed": passed, "reason": reason})
        if not passed:
            all_passed = False

    # 3. Contains any (at least one from list)
    if "output_contains_any" in expect:
        passed, reason = check_contains_any(response_text, expect["output_contains_any"])
        checks.append({"check": "output_contains_any", "passed": passed, "reason": reason})
        if not passed:
            all_passed = False

    # 4. Not contains (none of these should appear)
    if "output_not_contains" in expect:
        passed, reason = check_not_contains(response_text, expect["output_not_contains"])
        checks.append({"check": "output_not_contains", "passed": passed, "reason": reason})
        if not passed:
            all_passed = False

    was_blocked = "Blocked by" in response_text or "🛡️" in response_text

    first_failure = next((c["reason"] for c in checks if not c["passed"]), "All checks passed")

    return EvalResult(
        case_id="",
        passed=all_passed,
        reason=first_failure if not all_passed else "All checks passed",
        response_text=response_text,
        was_blocked=was_blocked,
        checks=checks,
    )
