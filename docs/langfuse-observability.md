# Langfuse Observability

How the application traces LLM requests and stores eval results.

---

## What It Gives You

| Feature | What it shows |
|---------|---------------|
| **Traces** | Full journey: user → guardrail → LLM → tool → response |
| **Token counts** | Input/output tokens per LLM call |
| **Cost** | Estimated $ per request |
| **Scores** | Eval pass/fail attached to traces |
| **Datasets** | Golden set experiments with side-by-side comparison |

## How It's Integrated

The app uses LangGraph's built-in **callback system** — not decorators. A `CallbackHandler` is created per request and passed to the graph invocation.

**Source:** `shop-backend-api/src/shop_backend_api/observability.py`

```python
handler = get_langfuse_handler(user_id=..., session_id=..., role=...)
result = await agent.chat(message, user_context, callbacks=[handler])
```

LangGraph automatically reports every node execution (guardrail, LLM call, tool call) as spans within the trace. No manual instrumentation needed.

## Configuration

Set in `shop-backend-api/.env`:

```
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://your-langfuse-instance
```

## Deployment

Langfuse runs on the shared OpenShift cluster (`ai-e2e-demo` namespace) with:
- PostgreSQL (data storage)
- Valkey/Redis (caching)
- MinIO (S3-compatible blob storage for OTLP exports)

## Key Dashboards

| Page | Use for |
|------|---------|
| **Tracing** | Debug individual requests — see every LLM call, tool result, tokens |
| **Sessions** | Group traces by conversation |
| **Scores** | View eval results across all traces |
| **Datasets** | Compare golden set experiment runs (e.g., before/after model upgrade) |

## Eval Integration

The eval runner (`eval/run_eval.py`) uses Langfuse's Dataset + Experiment API:
1. Creates a dataset (`shopchat-golden-set`) with test cases
2. Runs experiments against it (tagged per run)
3. Stores `eval_pass` and `blocked_correct` scores per item
4. Aggregates scores per run for quick comparison

See [Test Strategy](test-strategy.md) for details on running evals.
