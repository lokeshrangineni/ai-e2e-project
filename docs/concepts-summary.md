# Key Concepts Summary

> **What this covers:** Brief summary of LLM application concepts discussed during project planning. Quick reference for the patterns and tools used in this project.
>
> **Skip if you already know:** LLM statelessness, guardrails, observability, eval, RBAC enforcement patterns.

---

## LLM is Stateless

- Each API request is independent — LLM has no memory between requests
- **Training data**: permanent, frozen (general knowledge)
- **Context window**: per-request only (your prompts, RAG chunks, tool results)
- "Sessions" are simulated by your app re-sending conversation history
- User data never persists in the model — only in your app's storage

---

## Guardrails

**Purpose:** Keep LLM on-topic and safe.

**Three layers:**
1. **System prompt** — instructions to the model
2. **Code-level checks** — input/output validation
3. **RBAC enforcement** — role-based tool/data access

**Tools:**
- **Guardrails AI** — validators for structure, PII, toxicity
- **NeMo Guardrails** (NVIDIA) — conversational rails, topic control
- **LLM Guard** — prompt injection, PII scanners

---

## Observability (Langfuse)

**Purpose:** See what's happening inside your LLM app.

**What it tracks:**
- Traces (full request journey)
- Spans (individual steps)
- Token counts and cost
- Latency per step
- Scores (for evals)

**Key practice:** Tag traces with `model_id`, `app_version` for before/after comparisons.

---

## Eval (Testing)

**Challenge:** LLM outputs are non-deterministic — can't use exact string matching.

**Approaches:**
- Contains checks, tool assertions, negative checks
- Golden test set (curated inputs + expected behaviors)
- Langfuse Datasets or Promptfoo for tooling

**CI Strategy (tiered):**
- **Every PR:** Unit tests + cached responses (fast, free)
- **Nightly:** Full integration with real LLM (catches model drift)

---

## RBAC

**Roles:** Customer (own data), Operator (all data read-only), Admin (full access)

**Enforcement — at the tool layer, not the question:**
1. Filter available tools by role
2. Validate tool arguments before execution
3. Filter data at the source (queries always scoped by user)

**Tools:**
- **OPA / Casbin / Cerbos** — policy engines for access decisions
- Custom code works fine for simple cases

**Key insight:** Don't interpret the user's question for RBAC — validate the action (tool call).

---

## RAG + Access Control

**Problem:** Documents have different access levels.

**Solution:** Filter at retrieval time, not after.
- Store ACLs as metadata in vector DB
- Query with user's groups as a filter
- Unauthorized docs never reach the LLM

**Enterprise platforms:** Microsoft Copilot, Glean, Vectara sync permissions from source systems.

---

## Mock Auth (This Project)

- UI dropdown to select role/user
- Headers (`X-User-Role`, `X-User-Id`) sent to BFF
- No real authentication — for demo/POC only

---

## Architecture Summary

```
User → React (role selector) → BFF → [Content Guardrails] → [RBAC Check] → [LLM] → [Tools]
              ↓                              ↓                    ↓              ↓
        Mock auth headers           Guardrails AI/NeMo      Policy engine    Filtered by role
                                                            or custom         and user context
```

---

## Related Docs

- [Guardrails](guardrails.md) — detailed implementation
- [Langfuse Observability](langfuse-observability.md) — tracing setup
- [Eval](eval.md) — testing strategies and CI integration
