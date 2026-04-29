#!/usr/bin/env python3
"""Standalone eval runner — runs the golden set and prints a summary report.

Uses Langfuse's Dataset + Experiment API to persist results for side-by-side
comparison across model upgrades, prompt changes, and guardrail updates.

Langfuse structure:
    Dataset:    "shopchat-golden-set"  (created once, holds all test cases)
    Experiment: "--tag" value          (one per eval run, e.g. "baseline-v1")

Usage:
    cd eval && python run_eval.py --tag "baseline-v1" --verbose
    cd eval && python run_eval.py --tag "after-haiku-upgrade" --verbose
    cd eval && python run_eval.py --category guardrail_injection --tag "test"
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Load .env from shop-backend-api (contains Langfuse keys, Vertex AI config, etc.)
_PROJECT_ROOT = Path(__file__).parent.parent
_ENV_FILE = _PROJECT_ROOT / "shop-backend-api" / ".env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)

# Add shop-backend-api/src to path
_BACKEND_SRC = _PROJECT_ROOT / "shop-backend-api" / "src"
sys.path.insert(0, str(_BACKEND_SRC))

from assertions import run_assertions, EvalResult

CASES_DIR = Path(__file__).parent / "cases"
DATASET_NAME = "shopchat-golden-set"


def load_cases(category: str | None = None) -> list[dict]:
    """Load cases from YAML files, optionally filtering by category."""
    cases = []
    for file in sorted(CASES_DIR.glob("*.yaml")):
        if category and file.stem != category:
            continue
        with open(file) as f:
            file_cases = yaml.safe_load(f) or []
            for case in file_cases:
                case["_source"] = file.stem
            cases.extend(file_cases)
    return cases


def get_langfuse_client():
    """Create Langfuse client if credentials are available."""
    try:
        from langfuse import Langfuse

        pk = os.getenv("LANGFUSE_PUBLIC_KEY")
        sk = os.getenv("LANGFUSE_SECRET_KEY")
        if not pk or not sk:
            return None
        return Langfuse(
            public_key=pk,
            secret_key=sk,
            host=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
        )
    except ImportError:
        return None


async def run_eval(category: str | None, tag: str | None, verbose: bool):
    """Run the full eval suite using Langfuse Experiment API."""
    from shop_backend_api.agent import ShopAgent

    cases = load_cases(category)
    if not cases:
        print(f"No cases found{f' for category: {category}' if category else ''}")
        sys.exit(1)

    run_name = tag or f"run-{int(time.time())}"

    print(f"{'═' * 60}")
    print(f"  ShopChat Golden Set Eval")
    print(f"  Cases: {len(cases)} | Run name: {run_name}")
    print(f"  Langfuse dataset: {DATASET_NAME}")
    print(f"{'═' * 60}\n")

    # Initialize agent
    print("Initializing agent (MCP + LLM)...")
    agent = ShopAgent()
    await agent.initialize()
    print(f"Agent ready with {len(agent.tools)} tools\n")

    langfuse = get_langfuse_client()
    if langfuse:
        print(f"Langfuse: connected")
        print(f"  Experiment will appear as: {DATASET_NAME} → {run_name}\n")
    else:
        print("Langfuse: not configured — results are local only\n")

    # ─────────────────────────────────────────────────────────
    # Run with Langfuse Experiment API (if available)
    # ─────────────────────────────────────────────────────────
    if langfuse:
        from langfuse import Evaluation

        # Step 1: Create or get the dataset in Langfuse (persists in UI)
        print(f"Creating/updating dataset '{DATASET_NAME}' in Langfuse...")
        langfuse.create_dataset(
            name=DATASET_NAME,
            description="ShopChat golden set — curated test cases for guardrails, RBAC, happy path, and edge cases.",
            metadata={"categories": [c.get("_source", "") for c in cases[:1]]},
        )

        # Step 2: Upsert dataset items (idempotent — uses case ID)
        for case in cases:
            langfuse.create_dataset_item(
                dataset_name=DATASET_NAME,
                id=case["id"],
                input={
                    "message": case["input"],
                    "context": case.get("context", {}),
                },
                expected_output=case.get("expect", {}),
                metadata={
                    "description": case.get("description", ""),
                    "source": case.get("_source", ""),
                },
            )

        langfuse.flush()

        # Step 3: Get the dataset and run the experiment against it
        dataset = langfuse.get_dataset(DATASET_NAME)

        async def task(item):
            """Run a single eval case through the real agent."""
            context = item.input.get("context", {})
            user_context = {
                "role": context.get("role", "customer"),
                "user_id": context.get("user_id", "cust_001"),
                "user_name": context.get("user_name", "Test User"),
            }
            try:
                response_text = await agent.chat(
                    message=item.input["message"],
                    user_context=user_context,
                    conversation_history=None,
                )
            except Exception as e:
                response_text = f"[ERROR] {type(e).__name__}: {e}"
            return {"response": response_text}

        def eval_pass(*, output, expected_output, **kwargs):
            """Evaluator: checks all assertions pass."""
            response_text = output.get("response", "")
            result = run_assertions(response_text, expected_output)
            return Evaluation(name="eval_pass", value=1.0 if result.passed else 0.0,
                             comment=result.reason)

        def eval_blocked(*, output, expected_output, **kwargs):
            """Evaluator: checks blocked status matches expectation."""
            response_text = output.get("response", "")
            is_blocked = "Blocked by" in response_text or "🛡️" in response_text
            expected_blocked = expected_output.get("blocked")
            if expected_blocked is None:
                return None
            correct = is_blocked == expected_blocked
            return Evaluation(name="blocked_correct", value=1.0 if correct else 0.0,
                             comment=f"expected={expected_blocked}, actual={is_blocked}")

        print(f"Running experiment '{run_name}' against dataset...")
        experiment_result = dataset.run_experiment(
            name=run_name,
            description=f"Golden set eval: {len(cases)} cases"
                        + (f" (category: {category})" if category else ""),
            task=task,
            evaluators=[eval_pass, eval_blocked],
            metadata={
                "model_id": os.getenv("MODEL_ID", "claude-sonnet-4@20250514"),
                "nemo_guardrails": os.getenv("NEMO_GUARDRAILS_ENABLED", "false"),
                "regex_guardrails": os.getenv("REGEX_GUARDRAILS_ENABLED", "true"),
            },
        )

        # Print results
        print(f"\n{experiment_result.format()}")

        langfuse.flush()
        await agent.cleanup()
        return 0

    # ─────────────────────────────────────────────────────────
    # Fallback: run without Langfuse (local-only mode)
    # ─────────────────────────────────────────────────────────
    results: list[EvalResult] = []
    passed_count = 0
    failed_count = 0

    for i, case in enumerate(cases, 1):
        context = case.get("context", {})
        user_context = {
            "role": context.get("role", "customer"),
            "user_id": context.get("user_id", "cust_001"),
            "user_name": context.get("user_name", "Test User"),
        }

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

        result = run_assertions(response_text, case.get("expect", {}))
        result.case_id = case["id"]
        result.latency_ms = elapsed_ms
        results.append(result)

        if result.passed:
            passed_count += 1
            symbol = "✓"
        else:
            failed_count += 1
            symbol = "✗"

        print(f"  [{i:2d}/{len(cases)}] {symbol} {case['_source']}/{case['id']}"
              f"  ({elapsed_ms:.0f}ms)")

        if not result.passed and verbose:
            print(f"         Input:    {case['input'][:80]}")
            print(f"         Response: {response_text[:200]}")
            print(f"         Reason:   {result.reason}")
            for check in result.checks:
                status = "✓" if check["passed"] else "✗"
                print(f"           {status} {check['check']}: {check['reason']}")
            print()

    # Summary
    total = passed_count + failed_count
    pass_rate = (passed_count / total * 100) if total > 0 else 0
    avg_latency = sum(r.latency_ms for r in results) / len(results) if results else 0

    print(f"\n{'═' * 60}")
    print(f"  RESULTS: {passed_count}/{total} passed ({pass_rate:.1f}%)")
    print(f"  Avg latency: {avg_latency:.0f}ms")
    print(f"{'═' * 60}")

    if failed_count > 0:
        print(f"\n  FAILURES ({failed_count}):")
        for r in results:
            if not r.passed:
                print(f"    ✗ {r.case_id}: {r.reason}")

    await agent.cleanup()
    return 0 if failed_count == 0 else 1


def main():
    parser = argparse.ArgumentParser(description="Run ShopChat golden set evals")
    parser.add_argument("--category", "-c", help="Run only a specific category (e.g., happy_path)")
    parser.add_argument("--tag", "-t", help="Experiment run name for Langfuse (e.g., baseline-v1)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show details for failures")
    args = parser.parse_args()

    exit_code = asyncio.run(run_eval(args.category, args.tag, args.verbose))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
