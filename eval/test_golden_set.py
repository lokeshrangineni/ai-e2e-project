"""Layer 2: Golden Set Eval — runs test cases against the real LLM agent.

Usage:
    # Run all golden set evals
    cd eval/
    pytest test_golden_set.py -v

    # Run only a specific category
    pytest test_golden_set.py -v -k "happy_path"
    pytest test_golden_set.py -v -k "guardrail_injection"
    pytest test_golden_set.py -v -k "rbac"

    # With Langfuse persistence (set env vars)
    LANGFUSE_PUBLIC_KEY=pk-... LANGFUSE_SECRET_KEY=sk-... pytest test_golden_set.py -v

Requirements:
    - Real LLM API access (Vertex AI or Anthropic API key)
    - MCP server available (uv installed, mcp-server project present)
    - ~30-60 seconds per test case (real LLM round-trips)
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
import yaml

from assertions import run_assertions, EvalResult

CASES_DIR = Path(__file__).parent / "cases"


def load_cases_by_file(filename: str) -> list[dict]:
    """Load cases from a specific YAML file."""
    filepath = CASES_DIR / filename
    if not filepath.exists():
        return []
    with open(filepath) as f:
        return yaml.safe_load(f) or []


def case_id(case: dict) -> str:
    """Generate a human-readable test ID from a case."""
    return f"{case.get('_source', 'unknown')}/{case['id']}"


# ─────────────────────────────────────────────────────────────
# Load all test cases at module level for parametrize
# ─────────────────────────────────────────────────────────────

_ALL_FILES = [
    "happy_path.yaml",
    "rbac.yaml",
    "guardrail_injection.yaml",
    "guardrail_off_topic.yaml",
    "safe_passthrough.yaml",
    "edge_cases.yaml",
]

_ALL_CASES: list[dict] = []
for _f in _ALL_FILES:
    _cases = load_cases_by_file(_f)
    for _c in _cases:
        _c["_source"] = _f.replace(".yaml", "")
    _ALL_CASES.extend(_cases)


# ─────────────────────────────────────────────────────────────
# Test function
# ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("case", _ALL_CASES, ids=[case_id(c) for c in _ALL_CASES])
@pytest.mark.asyncio
async def test_eval_case(case: dict, agent, langfuse_client, eval_run_id):
    """Run a single golden set eval case against the real agent."""
    context = case.get("context", {})
    user_context = {
        "role": context.get("role", "customer"),
        "user_id": context.get("user_id", "cust_001"),
        "user_name": context.get("user_name", "Test User"),
    }

    # Time the actual LLM call
    start = time.time()
    try:
        response_text = await agent.chat(
            message=case["input"],
            user_context=user_context,
            conversation_history=None,
        )
    except Exception as e:
        response_text = f"[ERROR] {type(e).__name__}: {e}"
    elapsed_ms = (time.time() - start) * 1000

    # Run assertions
    result = run_assertions(response_text, case.get("expect", {}))
    result.case_id = case["id"]
    result.latency_ms = elapsed_ms

    # Persist to Langfuse if available
    if langfuse_client:
        _report_to_langfuse(langfuse_client, case, result, eval_run_id)

    # Print details for failures
    if not result.passed:
        print(f"\n{'─' * 60}")
        print(f"FAILED: {case['id']} ({case.get('description', '')})")
        print(f"Input:    {case['input'][:100]}")
        print(f"Response: {response_text[:300]}")
        print(f"Reason:   {result.reason}")
        print(f"Latency:  {elapsed_ms:.0f}ms")
        for check in result.checks:
            status = "✓" if check["passed"] else "✗"
            print(f"  {status} {check['check']}: {check['reason']}")
        print(f"{'─' * 60}")

    assert result.passed, f"{case['id']}: {result.reason}"


def _report_to_langfuse(langfuse_client, case: dict, result: EvalResult, run_id: str):
    """Report eval result to Langfuse as a score (SDK v4 API)."""
    try:
        trace_id = langfuse_client.create_trace_id(seed=f"{run_id}/{case['id']}")
        langfuse_client.create_score(
            trace_id=trace_id,
            name="eval_pass",
            value=1.0 if result.passed else 0.0,
            comment=result.reason,
            metadata={
                "case_id": case["id"],
                "source_file": case.get("_source", "unknown"),
                "description": case.get("description", ""),
                "latency_ms": result.latency_ms,
            },
        )
        langfuse_client.create_score(
            trace_id=trace_id,
            name="latency_ms",
            value=result.latency_ms,
            metadata={"case_id": case["id"]},
        )
    except Exception as e:
        print(f"[Langfuse] Failed to report: {e}")
