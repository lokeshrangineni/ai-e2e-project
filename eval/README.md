# Layer 2: Golden Set Evals

End-to-end evaluation suite that runs test cases against the **real LLM agent** with actual API calls.

## What It Tests

| Category | File | Cases | What It Validates |
|----------|------|-------|-------------------|
| Happy path | `cases/happy_path.yaml` | 6 | Products, orders, greetings work correctly |
| RBAC | `cases/rbac.yaml` | 8 | Role-based access control (allowed + blocked) |
| Injection | `cases/guardrail_injection.yaml` | 8 | Prompt injection attempts are caught |
| Off-topic | `cases/guardrail_off_topic.yaml` | 7 | Non-shopping queries are refused |
| Safe pass-through | `cases/safe_passthrough.yaml` | 10 | Legitimate queries are NOT false-positived |
| Edge cases | `cases/edge_cases.yaml` | 8 | Boundaries: empty input, special chars, etc. |

**Total: ~47 test cases**

## Prerequisites

- Python 3.11+
- Vertex AI credentials configured (`ANTHROPIC_VERTEX_PROJECT_ID`, `CLOUD_ML_REGION`)
- `uv` installed (for MCP server subprocess)
- The `shop-backend-api` and `mcp-server` projects synced

## Quick Start

```bash
# From the eval/ directory:
cd eval/

# Install dependencies
pip install pytest pytest-asyncio pyyaml langfuse

# Run all evals (standalone runner)
python run_eval.py --tag "baseline-v1" --verbose

# Run via pytest (better for CI)
pytest test_golden_set.py -v

# Run a specific category
python run_eval.py --category happy_path --verbose
pytest test_golden_set.py -v -k "happy_path"
```

## With Langfuse (Recommended)

Set these env vars to persist results for comparison:

```bash
export LANGFUSE_PUBLIC_KEY=pk-lf-...
export LANGFUSE_SECRET_KEY=sk-lf-...
export LANGFUSE_HOST=https://your-langfuse-instance

# Run with a version tag
python run_eval.py --tag "v1.0-sonnet"

# After model upgrade, run again
python run_eval.py --tag "v1.1-haiku"

# Compare in Langfuse UI: filter by tags
```

## Assertion Types

Each test case in YAML defines `expect:` with these checks:

| Check | What It Does |
|-------|--------------|
| `blocked: true/false` | Was the response blocked by guardrails? |
| `output_contains: "text"` | Response includes exact substring |
| `output_contains_any: [...]` | Response includes at least one |
| `output_not_contains: [...]` | Response must NOT include any |

## Adding Test Cases

Create or edit YAML files in `cases/`:

```yaml
- id: my_new_test
  description: What this tests
  input: "User's message to the agent"
  context:
    role: customer        # customer | operator | admin
    user_id: cust_001
    user_name: Alice Johnson
  expect:
    blocked: false
    output_contains_any:
      - "expected keyword"
    output_not_contains:
      - "should not see this"
```

## Architecture

```
eval/
├── cases/                    # YAML test case definitions
│   ├── happy_path.yaml
│   ├── rbac.yaml
│   ├── guardrail_injection.yaml
│   ├── guardrail_off_topic.yaml
│   ├── safe_passthrough.yaml
│   └── edge_cases.yaml
├── assertions.py             # Check logic (contains, blocked, etc.)
├── conftest.py               # Pytest fixtures (agent, langfuse)
├── test_golden_set.py        # Pytest parametrized tests
├── run_eval.py               # Standalone runner with summary report
├── pyproject.toml            # Eval dependencies
└── README.md                 # This file
```

## CI/CD

- **Nightly:** `.github/workflows/eval-nightly.yml` runs all cases on schedule
- **On-demand:** Trigger manually from GitHub Actions with a tag and optional category filter
- **Layer 1 tests** (unit, no LLM) still run on every commit via the existing `tests.yml` workflow

## Cost

Each eval run makes real LLM calls:
- ~47 cases × 1-2 Vertex AI calls each ≈ $0.20-0.50 per full run
- With NeMo Guardrails enabled: +1 Haiku call per case ≈ extra $0.05

## When to Run

- Before/after model upgrades
- After prompt changes
- After guardrail policy updates
- After dependency upgrades (LangGraph, NeMo, etc.)
- Nightly for drift detection
