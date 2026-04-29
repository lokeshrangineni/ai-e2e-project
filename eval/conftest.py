"""Pytest fixtures for Layer 2 golden set evals.

These evals run against the REAL agent with real LLM calls.
They require:
  - Vertex AI credentials (ANTHROPIC_VERTEX_PROJECT_ID, CLOUD_ML_REGION)
  - MCP server available (uv + mcp-server project)
  - Optionally: Langfuse (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST)
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import AsyncGenerator

import pytest
import yaml
from dotenv import load_dotenv

# Load .env from shop-backend-api (Langfuse keys, Vertex AI config, etc.)
_PROJECT_ROOT = Path(__file__).parent.parent
_ENV_FILE = _PROJECT_ROOT / "shop-backend-api" / ".env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)

# Add shop-backend-api to sys.path so we can import the agent directly
_BACKEND_SRC = _PROJECT_ROOT / "shop-backend-api" / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def agent():
    """Initialize the ShopAgent once per test session (expensive — real MCP + LLM)."""
    from shop_backend_api.agent import ShopAgent

    agent = ShopAgent()
    await agent.initialize()
    yield agent
    await agent.cleanup()


@pytest.fixture(scope="session")
def langfuse_client():
    """Optional Langfuse client for persisting eval results."""
    try:
        from langfuse import Langfuse

        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        host = os.getenv("LANGFUSE_HOST", "http://localhost:3000")

        if not public_key or not secret_key:
            return None

        return Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
    except ImportError:
        return None


@pytest.fixture(scope="session")
def eval_run_id() -> str:
    """Unique identifier for this eval run (timestamp-based)."""
    return f"eval-{int(time.time())}"


def load_yaml_cases(cases_dir: Path) -> list[dict]:
    """Load all YAML case files from a directory."""
    cases = []
    for file in sorted(cases_dir.glob("*.yaml")):
        with open(file) as f:
            file_cases = yaml.safe_load(f) or []
            for case in file_cases:
                case["_source"] = file.stem
            cases.extend(file_cases)
    return cases


def pytest_collect_file(parent, file_path):
    """Custom collector: skip YAML files (they're loaded by test_runner, not directly)."""
    pass
