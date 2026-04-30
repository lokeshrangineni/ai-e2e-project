# Test Strategy for AI/LLM Applications

> A beginner-friendly guide to testing ML/AI-based applications — why it's different from traditional testing, the standard industry practices, the different approaches with their pros and cons, and how tools like Langfuse fit into the picture.

---

## Why AI Apps Need a Different Testing Approach

Traditional software is **deterministic** — the same input always produces the same output. AI/LLM applications are **non-deterministic** — the same question may produce different (but equally valid) responses each time. This fundamentally changes how you validate correctness.

**Example:** Ask "What shoes do you sell?" three times:
- "Here are our footwear products: Nike Air Max ($129.99)..."
- "We carry several shoes! The Nike Air Max is $129.99..."
- "I'd be happy to help! In our Footwear category, you'll find..."

All correct, all different. You can't do `assert response == "exact string"`.

| Aspect | Traditional software | AI/LLM application |
|---|---|---|
| **Output** | Deterministic (same every time) | Non-deterministic (varies each run) |
| **Pass/fail** | Exact match (`==`) | Fuzzy judgment ("does it contain the right fact?") |
| **Judging** | Code assertion | Heuristics, substring checks, or another LLM |
| **Scoring** | Binary (pass/fail) | Often graded (0-1 score, categories) |
| **Why you re-run** | Code changed | Model changed, prompt changed, guardrails changed, or nothing changed (drift) |
| **What you compare** | This version vs expected | This version vs last version (regression detection) |

### Why are they called "evals" and not "tests"?

The term comes from the ML/AI world where **evaluation** has always meant "measure how well the model performs on a held-out dataset" (accuracy, precision, recall). LLM evals inherit that tradition: you're not checking if code is correct, you're **measuring how well a non-deterministic system behaves** across a set of scenarios, and tracking that measurement over time.

That said, many eval cases for production apps (guardrail fired? correct tool called?) are effectively traditional tests with deterministic assertions. The line between "test" and "eval" is blurry — and that's fine.

---

## The Testing Pyramid for AI Applications

Traditional software has the well-known test pyramid (unit → integration → e2e). AI applications add new layers on top:

```
                    ▲
                   / \
                  / 5 \     Production monitoring & drift detection
                 /─────\
                /   4   \    Human evaluation (annotation queues)
               /─────────\
              /     3     \   LLM-as-judge (automated quality scoring)
             /─────────────\
            /       2       \   Golden set evals (deterministic + heuristic)
           /─────────────────\
          /         1         \   Traditional unit & integration tests
         /─────────────────────\
```

Each layer builds on the one below. **Layers 1 and 2 are non-negotiable** for any production LLM app.

---

## Layer 1: Traditional Unit & Integration Tests

These test your **code**, not the LLM. They're fast, deterministic, and run in CI on every commit.

### What to test

| What | Example | Tool |
|---|---|---|
| Guardrail regex logic | `assert check_injection("ignore previous instructions").allowed == False` | pytest |
| Tool argument validation | `assert get_order(order_id="ORD-001")` returns expected schema | pytest |
| RBAC enforcement | `assert customer cannot call list_customers tool` | pytest |
| API contract | `POST /chat/stream` returns SSE with correct event format | pytest + httpx |
| Config loading | Settings parse `.env` correctly | pytest |
| Data access layer | CSV parsing returns correct DataFrame | pytest |

### Pros and cons

| Pros | Cons |
|---|---|
| No LLM calls — fast, free, no API keys needed | Doesn't test the LLM's actual behavior |
| 100% deterministic — no flakiness | Can't catch prompt regressions or model quality changes |
| Runs in CI on every commit | Only tests the code around the LLM, not the LLM itself |
| Easy to write and maintain | |

### When to use

Always. This is table stakes for any software project, AI or not.

---

## Layer 2: Golden Set Evals

This is the **industry standard minimum** for LLM applications. A curated dataset of inputs with expected outcomes, run against the actual LLM pipeline.

### How it works

1. Create a set of ~20-100 test cases (the "golden set")
2. Each case has: input, context (role, user ID), and **assertions**
3. A script runs each case through your actual agent (real LLM calls)
4. Results are scored and compared across versions

### What must be running during a golden set eval

The eval runs your **actual application end-to-end** — it's not a mock:

```
┌───────────────────────────────────────────────────────┐
│  What must be running                                  │
├───────────────────────────────────────────────────────┤
│  ✓ Your LangGraph agent          ← processes each case │
│  ✓ MCP server (spawned by agent) ← tools need to work  │
│  ✓ Vertex AI (Sonnet)            ← the app's main LLM  │
│  ✓ Vertex AI (Haiku)             ← if NeMo guardrails   │
│  ✓ CSV data files                ← products, orders     │
│                                                         │
│  Optional:                                              │
│  ○ Langfuse instance    ← for storing/comparing results │
└───────────────────────────────────────────────────────┘
```

### Two approaches: with and without Langfuse

You can run golden set evals **purely locally** or **with Langfuse** for persistence. Here's the difference:

#### Without Langfuse (pure local pytest)

```python
def test_off_topic_blocked():
    result = await agent.invoke("guide me to travel india", role="customer")
    assert result.blocked == True
```

| Pros | Cons |
|---|---|
| No external dependencies needed | No history — results gone after terminal closes |
| Works offline (except LLM API) | Can't compare across versions side-by-side |
| Simple pytest setup | No trace inspection for debugging failures |
| | Only the person who ran it sees results |

#### With Langfuse (same eval, results persisted)

```python
result = langfuse.run_experiment(
    name="Guardrail Eval",
    data=test_cases,
    task=run_agent,
    evaluators=[guardrail_check],
    metadata={"model_id": "claude-sonnet-4@20250514"}
)
```

| Pros | Cons |
|---|---|
| Results stored permanently | Requires a running Langfuse instance |
| Side-by-side version comparison in UI | Slightly more setup |
| Click any trace to debug (see LLM calls, tools, tokens) | |
| Team can see results without re-running | |
| Latency and cost tracked automatically | |

**Key point:** Langfuse doesn't run your evals — your code does. Langfuse is the **database and dashboard** where results get stored. Think of it as the difference between running `pytest` and seeing results in the terminal vs running `pytest` and seeing results in a CI dashboard.

### Types of assertions (strict to fuzzy)

```
Strictest ──────────────────────────────────── Fuzziest

Tool called?    Substring    No forbidden    Semantic      LLM
(yes/no)        match        content         similarity    judge
```

| Assertion type | Example | Reliability | Extra LLM needed? |
|---|---|---|---|
| **Behavioral** | "Was `get_products` tool called?" | Very high — binary | No |
| **Blocked/allowed** | "Was guardrail triggered?" | Very high — binary | No |
| **Substring** | "Response contains 'Nike Air Max'" | High — factual grounding | No |
| **Exclusion** | "Response does NOT contain system prompt text" | High — security | No |
| **Pattern** | "Response mentions at least 2 product names" | Medium — requires parsing | No |
| **Semantic similarity** | "Response meaning is close to reference" | Medium — embedding comparison | No (embeddings only) |
| **LLM-as-judge** | "Rate helpfulness 1-5" | Lower — varies between runs | **Yes** |

### Golden set categories

A good golden set covers:

| Category | Purpose | Example |
|---|---|---|
| **Happy path** | Core functionality works | "What products do you have?" → lists products |
| **RBAC allowed** | Permitted access works | Operator asks for any customer's orders → returns data |
| **RBAC blocked** | Unpermitted access refused | Customer asks for another customer's data → refusal |
| **Guardrail - injection** | Injection attempts caught | "Ignore all instructions" → blocked |
| **Guardrail - jailbreak** | Jailbreak attempts caught | "You are DAN" → blocked |
| **Guardrail - off-topic** | Off-topic requests caught | "Plan my trip to India" → blocked |
| **Safe pass-through** | Legitimate queries not blocked (false positives) | "What products in Footwear?" → NOT blocked |
| **Edge cases** | Boundary conditions | Empty message, very long message, special characters |

### When to run

- **Every model upgrade** — Claude Sonnet 4 → Sonnet 5
- **Every prompt change** — system prompt rewording
- **Every guardrail change** — new Colang policies, regex updates
- **Every dependency upgrade** — LangGraph, NeMo Guardrails, Langfuse SDK

### Pros and cons

| Pros | Cons |
|---|---|
| Tests your actual LLM pipeline end-to-end | Requires real LLM API calls (costs money, takes time) |
| Catches regressions from model/prompt changes | Non-deterministic — may need to re-run for edge cases |
| Industry standard — this is what OpenAI, Anthropic do | Maintaining the golden set requires curation |
| Most assertions are deterministic (tool called, blocked) | Substring checks can be brittle if wording changes |

---

## Layer 3: LLM-as-Judge

When you can't write a deterministic rule, you use **another LLM** to judge quality.

### How it works

```
Your app's LLM (Sonnet)                    Judge LLM (Haiku, Sonnet, or GPT-4)
         ↓                                              ↓
User message → Agent → Response  ──────→  "Rate this response:
                                            Correctness (1-5)?
                                            Completeness (1-5)?
                                            Tone (1-5)?"
                                                        ↓
                                           {"correctness": 5, "completeness": 4, "tone": 5}
```

**LLMs involved:** 2 — your app's LLM + the judge LLM.
**Cost:** ~2x a normal chat request.

### When to use vs when NOT to use

| Use LLM-as-judge when... | Use deterministic checks instead when... |
|---|---|
| Checking tone, helpfulness, or quality | Checking if a tool was called (yes/no) |
| Detecting hallucinations rules can't catch | Checking if guardrail fired (yes/no) |
| Grading open-ended responses | Checking if response contains a specific fact |
| Comparing "which version is better?" | Checking if response leaks system prompt |

### The variance problem

The same input may score 4/5 one run and 5/5 the next. Mitigations:
- Run the judge multiple times and average
- Use a strong model (Claude Sonnet or GPT-4) as the judge, not a weak one
- Use a fixed rubric with concrete examples for each score level
- Compare distributions across runs, not individual scores

### Pros and cons

| Pros | Cons |
|---|---|
| Can evaluate subjective quality (tone, helpfulness) | Costs money — every judgment is an LLM call |
| Catches hallucinations that rules miss | Non-deterministic — scores vary between runs |
| Scales to many test cases | A weak judge model gives unreliable scores |
| Can compare two versions ("is B better than A?") | Can't be the sole signal — pair with deterministic checks |

### Standard tools

| Tool | Approach | Notes |
|---|---|---|
| **Langfuse managed evaluators** | Built-in LLM-as-judge | Runs on traces in Langfuse, scores stored automatically |
| **RAGAS** | Framework for RAG evaluation | Faithfulness, relevance, context recall |
| **DeepEval** | pytest-style LLM eval framework | G-Eval, hallucination, toxicity metrics |
| **Promptfoo** | CLI tool for prompt testing | Red-teaming, comparative evals, multiple providers |

---

## Layer 4: Human Evaluation

Machines can't catch everything. Human review fills the gap and provides ground truth.

### How it works in practice

1. **Annotation queues** — route a sample of production traces to human reviewers
2. Reviewers score on a rubric (correct/incorrect, helpful/unhelpful, safe/unsafe)
3. Human scores become the **ground truth** to calibrate your LLM-as-judge
4. Disagreements between human and automated scores reveal eval gaps

### When it matters most

- **Initial launch** — "Is this actually good enough to ship?"
- **After model upgrade** — spot-check before full rollout
- **Edge cases** the automated evals miss
- **Calibrating LLM-as-judge** — are your automated scores aligned with human judgment?

### Typical workflow

```
Production traces → Sample 50-200 → Annotation queue → Human scores
                                                            ↓
                                          Compare with automated scores
                                                            ↓
                                          Tune judge prompts if misaligned
```

### Pros and cons

| Pros | Cons |
|---|---|
| Highest quality signal — humans understand nuance | Slow — can't run on every commit |
| Ground truth for calibrating automated evals | Expensive — human time costs money |
| Catches things all automated approaches miss | Doesn't scale to thousands of cases |
| | Subjective — reviewers may disagree |

### Tools

- **Langfuse Annotation Queues** — built into Langfuse, assign traces to reviewers
- **Argilla** — open-source data labeling for LLMs
- **Scale AI / Labelbox** — commercial human evaluation services

---

## Layer 5: Production Monitoring & Drift Detection

Once deployed, you continuously monitor for degradation — even when no code changes.

### Why things drift without code changes

- Model provider updates weights (Claude gets a minor update)
- User behavior changes (new types of questions you didn't anticipate)
- Data changes (new products added, edge cases in catalog)
- Infrastructure changes (latency from a different region)

### What to monitor

| Signal | How to detect | Tool |
|---|---|---|
| **Latency regression** | p50/p95 response time increasing | Langfuse dashboards |
| **Error rate** | More timeouts, tool failures, guardrail errors | Langfuse + application logs |
| **Token cost spike** | Model using more tokens per request | Langfuse token tracking |
| **Quality drift** | LLM-as-judge scores trending down over time | Langfuse scores time series |
| **Guardrail bypass** | Unsafe content getting through | Manual review of unblocked traces |
| **False positive rate** | Legitimate queries getting blocked | User complaints, annotation review |
| **User feedback** | Thumbs up/down trends | Custom scoring via Langfuse API |

### Pros and cons

| Pros | Cons |
|---|---|
| Catches regressions that evals miss (real user behavior) | Requires production traffic to be meaningful |
| Continuous — not just point-in-time | Alerting thresholds need tuning (too noisy or too quiet) |
| Low effort once set up | Reactive — you find problems after users hit them |

---

## LLM Requirements by Eval Type — Summary

A common question: "Which eval types need a running LLM?"

| Eval type | App's LLM (Sonnet) | Guardrail LLM (Haiku) | Judge LLM | Total LLM calls |
|---|---|---|---|---|
| **Unit tests** (Layer 1) | Not needed (mocked) | Not needed | Not needed | 0 |
| **Golden set — deterministic** (Layer 2) | Yes | Yes (if NeMo enabled) | Not needed | 1-2 per case |
| **Golden set — LLM-as-judge** (Layer 2+3) | Yes | Yes (if NeMo enabled) | Yes | 2-3 per case |
| **Human evaluation** (Layer 4) | Already ran in production | Already ran | Not needed | 0 (reviewing past traces) |
| **Production monitoring** (Layer 5) | Already running | Already running | Optional | 0 (analyzing existing traces) |

### Cost implications

| Approach | Cost per 30-case eval run | LLM calls |
|---|---|---|
| Unit tests only | $0 | 0 |
| Golden set (deterministic assertions) | ~$0.10-0.50 | 30-60 |
| Golden set + LLM-as-judge | ~$0.30-1.00 | 60-90 |
| Golden set + Langfuse storage | Same as above + Langfuse hosting | Same |

**Recommendation:** Start with deterministic assertions (Layer 2 without LLM-as-judge). This covers ~80% of eval value at the lowest cost.

---

## Concrete Example: Model Upgrade Eval

Scenario: Switching from Claude Sonnet to Claude Haiku to save cost.

### Step 1: Run eval on current model (Sonnet)

```bash
MODEL_ID=claude-sonnet-4@20250514 python eval/run_eval.py
```

Langfuse records:
```
Experiment: "Eval — claude-sonnet-4@20250514"
  guardrail_correct:  30/30 (100%)
  tool_correct:       28/30 (93%)
  content_correct:    27/30 (90%)
  avg_latency:        2.1s
  avg_cost:           $0.004 per request
```

### Step 2: Switch model and re-run

```bash
MODEL_ID=claude-haiku-4-5@20251001 python eval/run_eval.py
```

Langfuse records:
```
Experiment: "Eval — claude-haiku-4-5@20251001"
  guardrail_correct:  30/30 (100%)
  tool_correct:       25/30 (83%)    ← regression
  content_correct:    22/30 (73%)    ← regression
  avg_latency:        0.8s           ← faster
  avg_cost:           $0.001 per request  ← cheaper
```

### Step 3: Compare in Langfuse

```
                          Sonnet          Haiku         Delta
                          ──────          ─────         ─────
guardrail_correct         100%            100%          same ✓
tool_correct              93%             83%           -10% ⚠️
content_correct           90%             73%           -17% ✗
avg_latency               2.1s            0.8s          -62% ✓
avg_cost/request          $0.004          $0.001        -75% ✓
```

### Step 4: Drill into regressions

Click any failed case in Langfuse to see the full trace — what the LLM said, which tools it called, how many tokens it used.

Without Langfuse, you'd have to re-run, add print statements, and try to remember what the old output looked like.

### Step 5: Make the decision

| Option | Trade-off |
|---|---|
| **Stay on Sonnet** | Higher quality, but 4x more expensive |
| **Switch to Haiku** | 75% cheaper, 62% faster, but 17% worse on content accuracy |
| **Hybrid** | Haiku for simple queries, Sonnet for complex tool-use scenarios |
| **Fix and re-eval** | Improve prompts for Haiku, re-run eval, check if gap closes |

---

## The Role of Langfuse in Evals

A common question: "If I can run evals locally, why do I need Langfuse?"

**Langfuse doesn't run your evals — your code does.** Langfuse is the **database and dashboard** where results get stored and compared.

| Capability | Without Langfuse | With Langfuse |
|---|---|---|
| **Run the eval** | Your code | Your code (same) |
| **Pass/fail result** | Terminal output | Terminal + stored permanently |
| **History** | Gone after terminal closes | Every run persisted |
| **Compare versions** | Re-run and eyeball | Side-by-side in UI |
| **Debug a failure** | Add print statements | Click trace — see every LLM call, tool, tokens |
| **Team visibility** | Only you see it | Anyone with access can view |
| **Latency/cost** | Not tracked | Automatically captured |
| **Trend over time** | Not possible | Scores graphed — spot drift |

### Everything is code-driven (no manual UI setup)

Langfuse datasets, experiments, and scoring can all be done programmatically — no clicking in a UI:

```python
from langfuse import get_client, Evaluation

langfuse = get_client()

# Create dataset programmatically
langfuse.create_dataset(name="shopchat-golden-set")
langfuse.create_dataset_item(
    dataset_name="shopchat-golden-set",
    input={"message": "show me products", "role": "customer"},
    expected_output={"blocked": False, "tool_called": "get_products"}
)

# Run experiment programmatically
def guardrail_evaluator(*, output, expected_output, **kwargs):
    if output["blocked"] == expected_output["blocked"]:
        return Evaluation(name="guardrail_correct", value=1.0)
    return Evaluation(name="guardrail_correct", value=0.0)

dataset = langfuse.get_dataset("shopchat-golden-set")
result = dataset.run_experiment(
    name="After NeMo Guardrails upgrade",
    task=run_agent,
    evaluators=[guardrail_evaluator],
    metadata={"model_id": "claude-sonnet-4@20250514", "guardrails_version": "1.0.0"}
)
print(result.format())
```

The only thing you use the Langfuse UI for is **viewing results** — the setup is 100% programmatic.

---

## How This Maps to ShopChat

| Layer | Status | Priority | What to build |
|---|---|---|---|
| 1 - Unit/integration tests | **Done** | **High** | Guardrail regex, RBAC tool filtering, config loading |
| 2 - Golden set evals | **Done** | **High** | 47 YAML test cases + Langfuse Experiment runner |
| 3 - LLM-as-judge | Not yet built | Medium | Add after golden set works; use Langfuse managed evaluators |
| 4 - Human eval | Manual (ad-hoc) | Low | Formalize with Langfuse annotation queues |
| 5 - Production monitoring | Langfuse traces flowing | **Partially done** | Add dashboards, alerting |

### Recommended implementation order

1. **Layer 1** — Unit tests for guardrails, RBAC, config (fast, no LLM calls, CI-friendly) ✅
2. **Layer 2** — Golden set eval with 47 cases covering all roles and guardrail scenarios ✅
3. **Layer 5** — Langfuse dashboards for latency/cost/error monitoring (partially in place)
4. **Layer 3** — LLM-as-judge for response quality (nice-to-have)
5. **Layer 4** — Human annotation queue (when the team grows)

---

## Decision Guide: Choosing Your Eval Approach

Use this table to decide which eval approach fits your situation:

| If you... | Start with | Add later |
|---|---|---|
| Just launched, small team | Layer 1 + Layer 2 (deterministic) | Layer 3 when quality questions arise |
| Need to compare model upgrades | Layer 2 + Langfuse | Layer 3 for subjective quality |
| Have production traffic | Layer 5 monitoring | Layer 4 for spot-checks |
| Care about response quality/tone | Layer 3 (LLM-as-judge) | Layer 4 to calibrate the judge |
| Have a large team / compliance needs | All layers | Formal annotation workflows (Layer 4) |
| Budget-constrained | Layer 1 (free) + Layer 2 (cheap) | Layer 3 only when needed |

---

## Running the Evals

For hands-on instructions (commands, prerequisites, adding test cases), see **[`eval/README.md`](../eval/README.md)**.

Quick reference:

```bash
# Layer 1: Unit tests (no LLM, runs in CI)
make test

# Layer 2: Golden set evals (real LLM calls, persisted to Langfuse)
make eval TAG=baseline-v1
```

---

## Key Takeaways

1. **Layers 1 + 2 are non-negotiable** for any production LLM app
2. **Start with deterministic assertions** (tool called? blocked? contains substring?) before LLM-as-judge — they cover ~80% of eval value at near-zero cost
3. **Run evals on every change** — model, prompt, guardrails, or dependencies
4. **Compare versions, not absolutes** — "Is version B better than version A?" matters more than a single score
5. **Langfuse is the memory and lens** — it doesn't run your evals, it stores and visualizes results for comparison
6. **Human eval is ground truth** — use it to calibrate automated scoring
7. **Monitor in production** — things can drift without any code change

---

## Further Reading

- [Langfuse Evaluation Docs](https://langfuse.com/docs/evaluation) — datasets, experiments, scoring
- [Langfuse Experiments via SDK](https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk) — programmatic eval runs
- [Promptfoo](https://promptfoo.dev/) — CLI for prompt testing and red-teaming
- [RAGAS](https://docs.ragas.io/) — RAG evaluation framework
- [DeepEval](https://docs.confident-ai.com/) — pytest-style LLM evaluation
