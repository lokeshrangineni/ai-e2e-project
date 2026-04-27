# Langfuse Observability

> **What this covers:** How to use Langfuse to trace and monitor your LLM application. Explains core concepts (traces, spans, generations, scores), how to integrate with LangGraph, how to tag traces for version comparisons, and local setup with Docker.
>
> **Skip if you already know:** How distributed tracing works for LLM apps, how to instrument Python code with Langfuse decorators, and how to use Langfuse dashboards for debugging and cost tracking.

---

## What Problem Does It Solve?

Traditional apps: you log HTTP requests, DB queries, errors. You can trace what happened.

LLM apps are different:

- A single request might make 3 model calls and 5 tool calls
- You pay per token — need to track costs
- "Why did it say that?" requires seeing the full conversation + tool results
- Model behavior changes with upgrades (even same model, different version)

## What Langfuse Gives You

| Feature | What it shows |
|---------|---------------|
| **Traces** | Full journey of a request (user → guardrail → LLM → tool → LLM → response) |
| **Spans** | Individual steps within a trace, with timing |
| **Token counts** | Input/output tokens per LLM call |
| **Cost** | Estimated $ per request |
| **Scores** | You can attach pass/fail or numeric scores (for evals) |
| **Tags/metadata** | Filter by model version, app version, user, etc. |

## Why It Matters

When you upgrade Claude from one version to another, you can:

1. Run the same test inputs
2. Compare traces side-by-side
3. See if latency changed, if tool usage changed, if costs went up

## Core Concepts

### Trace

A trace represents one end-to-end request. For a chat app, one user message → one trace.

```
Trace: "user asked about product price"
├── Span: guardrail_check (2ms)
├── Span: llm_call (450ms, 150 tokens)
├── Span: tool_call: get_product (35ms)
└── Span: llm_call (380ms, 200 tokens)
```

### Span

A span is one step within a trace. Spans can be nested. Each span captures:

- Name (what operation)
- Start/end time (latency)
- Input/output (what went in/out)
- Metadata (model id, version, etc.)

### Generation

A special span type for LLM calls. Automatically captures:

- Model name
- Prompt / completion
- Token counts (input, output, total)
- Cost (if model pricing is configured)

### Score

A numeric or boolean value attached to a trace. Used for:

- Eval results (pass/fail)
- Quality ratings (1-5)
- Human feedback (thumbs up/down)

## How It Works (Simplified)

```python
from langfuse.decorators import observe

# @observe creates a trace (if none exists) or a span (if inside a trace)
@observe(name="chat_request")
def handle_chat(message):
    
    @observe(name="llm_call")
    def call_model():
        return claude.invoke(message)
    
    return call_model()
```

Langfuse SDK automatically captures inputs, outputs, timing, and sends to the Langfuse server.

## Integration with LangGraph

### Option 1: Decorator Per Node

```python
from langfuse.decorators import observe, langfuse_context

@observe(name="guardrail_node")
def guardrail_node(state):
    # Check if on-topic
    is_allowed = check_topic(state["messages"][-1])
    return {"allowed": is_allowed}

@observe(name="llm_node")  
def llm_node(state):
    response = model.invoke(state["messages"])
    return {"messages": [response]}

@observe(name="tool_node")
def tool_node(state):
    result = execute_tool(state["tool_call"])
    return {"messages": [result]}
```

### Option 2: Wrap the Graph Invocation

```python
@observe(name="chat_request")
def handle_chat(user_message: str, conversation_id: str):
    # Add metadata for filtering
    langfuse_context.update_current_trace(
        user_id=conversation_id,
        metadata={
            "app_version": os.getenv("APP_VERSION", "dev"),
            "model_id": os.getenv("VERTEX_MODEL_ID"),
            "guardrails_version": "1.0.0",
        }
    )
    
    result = graph.invoke({"messages": [HumanMessage(content=user_message)]})
    return result
```

## Tagging for Comparisons

Always tag traces with version info (per FR-13 in requirements):

| Tag | Purpose |
|-----|---------|
| `model_id` | Which Claude version |
| `app_version` | Your app's release |
| `guardrails_version` | Guardrail rules version |
| `langfuse_sdk_version` | SDK version |

This lets you filter: "Show me all traces from before/after we upgraded Claude."

## Local Setup

Langfuse provides a Docker Compose for local development:

```bash
# Clone langfuse
git clone https://github.com/langfuse/langfuse.git
cd langfuse

# Start with Docker Compose
docker compose up -d

# Access UI at http://localhost:3000
# Create a project, get API keys
```

Environment variables for your app:

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
```

## Key Dashboards

Once traces flow in, Langfuse shows:

| Dashboard | What to look at |
|-----------|-----------------|
| Traces | Individual request details, debugging |
| Metrics | Latency p50/p95, token usage over time |
| Cost | $ per day/week, by model |
| Scores | Eval pass rates, quality trends |

## Using Scores for Eval

```python
from langfuse import Langfuse

langfuse = Langfuse()

# After running an eval case
langfuse.score(
    trace_id=trace.id,
    name="eval_passed",
    value=1,  # or 0 for fail
    comment="product_price_lookup test"
)
```

Then filter in UI: "Show traces where eval_passed = 0" to find failures.

## Related

- [Guardrails](guardrails.md) — what to trace
- [Eval Setup](eval.md) — using Langfuse for regression testing
