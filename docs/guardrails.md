# Guardrails

How the application keeps the LLM on-topic, safe, and role-aware.

---

## Three Layers of Defense

| Layer | Where | How | Latency |
|-------|-------|-----|---------|
| **Regex** (Layer 1) | Before LLM | Pattern matching for injection/off-topic keywords | <1ms |
| **NeMo Guardrails** (Layer 2) | Before LLM | Colang policy files + Claude Haiku for intent classification | ~1-2s |
| **System Prompt** (Layer 3) | Inside LLM | Role-specific instructions that constrain Claude's behavior | Implicit |

Each layer is independently configurable via `.env`:
- `REGEX_GUARDRAILS_ENABLED=true/false`
- `NEMO_GUARDRAILS_ENABLED=true/false`

## Layer 1: Regex (Fast, Cheap)

Pattern matching catches obvious attacks with zero latency.

**Source:** `shop-backend-api/src/shop_backend_api/guardrails.py`

Two pattern sets:
- `INJECTION_PATTERNS` — "ignore instructions", "pretend you are", "jailbreak", "DAN mode", etc.
- `OFF_TOPIC_PATTERNS` — "capital of", "write a poem", "weather in", "stock price", etc.

## Layer 2: NeMo Guardrails (Policy-Driven)

Uses NVIDIA NeMo Guardrails with Colang policy files. Claude Haiku classifies intent ("should this be blocked? yes/no") and NeMo enforces the policy deterministically.

**Config:** `shop-backend-api/guardrails_config/<role>/config.yml`

Each role has its own policy defining what's allowed/blocked. The LLM (Haiku) is only used for a single binary classification — it never sees the main conversation.

## Layer 3: System Prompt (Last Line of Defense)

Role-specific system prompts instruct the main LLM (Claude Sonnet) on scope:

| Role | Can do | Cannot do |
|------|--------|-----------|
| Customer | View own orders, browse products | Access other customers, modify anything |
| Operator | View any customer/order (read-only) | Modify products, off-topic |
| Admin | View all, add/update products | Off-topic |

When declining, the LLM prefixes its response with `Blocked by: LLM System Prompt`.

## RBAC Enforcement

Role-Based Access Control operates at the **tool layer**, not the question layer:

1. **Tool filtering** — MCP server exposes only role-appropriate tools
2. **Argument injection** — Agent injects `_user_context` into every tool call
3. **Data-level check** — MCP server validates ownership (customer can only see own orders)

**Source:** `mcp-server/src/shop_mcp_server/server.py`

## Blocked Response Format

All layers use a consistent format so the UI and evals can identify which layer caught a violation:

```
🛡️ Blocked by: Regex Guardrail
🛡️ Blocked by: NeMo Guardrails
🛡️ Blocked by: LLM System Prompt
```

## Testing

- **Layer 1 unit tests:** `shop-backend-api/tests/test_guardrails.py` (regex patterns)
- **Layer 2 golden set:** `eval/cases/guardrail_injection.yaml`, `eval/cases/guardrail_off_topic.yaml`
- **False positive checks:** `eval/cases/safe_passthrough.yaml`

See [Test Strategy](test-strategy.md) for the full eval approach.
