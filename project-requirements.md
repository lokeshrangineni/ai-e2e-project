# Project requirements

Single source of truth for implementing a **production-oriented learning project**: an LLM-backed chatbot with business-domain tools, deployed to **OpenShift**, with **local development** and **cluster deployment** documented end-to-end.

Use the prompt snippet in §12 when asking an agent to build or extend the codebase.

---

## 1. Product summary

- **Working name:** (TBD — e.g. “Domain Assistant” or “Shop Chat POC”)
- **Purpose:** Gain hands-on experience with the **AI application stack** and **shipping to production** on **OpenShift**, not with perfecting a specific business schema or UX.
- **One-sentence value proposition:** A web chatbot that answers user questions using **Claude on Google Cloud Vertex AI**, with access to **products, orders, and customers** via an **MCP (Model Context Protocol) service**, with **open-source observability** and an **agent** pattern where it helps, so the setup mirrors a real internal assistant over enterprise data.
- **Success criteria (v1):**
  - User can chat in a browser with **streamed** assistant output (§5.0); backend (BFF) calls Vertex-hosted Claude with a clear system policy.
  - **Simple retrieval** of product, order, and customer facts (no rich commerce workflows).
  - **MCP** exposes tools for those entities with **role-based access** (§2.1, §5.7); the LLM uses them when appropriate.
  - **Guardrails** and **prompt-injection hardening** are implemented and documented.
  - **LLM observability** via **Langfuse** (see naming note below) — traces/spans for requests, model calls, tool/MCP steps, latency, and token/cost signals where available.
  - **README (or docs/)** covers: local dev, env vars/secrets, **OpenShift** deployment, and **how to run eval/regression checks** after dependency or model upgrades (§13).
  - Team can **build quickly** and **run tests**; UI is **functional**, not polished.

---

## 2. Target users and context

- **Primary users:** Developers / platform engineers learning AI-on-K8s patterns; optional internal demo users.
- **Usage context:** Web UI (React), online-only; short chat sessions; backend is a **Python BFF** (see §5.0): **streaming HTTP (SSE)** for the assistant reply path; **REST/JSON** for operational and non-chat APIs.

### 2.1 User roles (RBAC)

| Role | Description | Data access | Operations |
|------|-------------|-------------|------------|
| **Customer** | End user of the shop | Own orders, own profile only | Read own data |
| **Operator** | Support staff helping customers | Any customer, any order | Read all data (for troubleshooting) |
| **Admin** | System administrator | Everything | Read + write (add/edit products) |

---

## 3. Scope

### 3.1 In scope (v1)

1. **React** frontend: chat UI (message list, input, send, loading/error states); **role selector dropdown** for mock auth (Customer/Operator/Admin); consume **streaming** from the BFF (e.g. **Vercel AI SDK `useChat`**, **assistant-ui**, or equivalent — see §5.0). Visual polish is explicitly **not** a priority.
2. **Python** backend: **BFF / orchestration service** — **SSE** (default) or **WebSockets** (if justified) for **chat completions**; **REST/JSON** for health, metadata, and other non-streaming APIs. **Do not** rely on a blocking “POST → full JSON body only at end” pattern for the primary user chat path.
3. **LLM:** **Claude** via **Vertex AI** (enterprise path); configuration via env (project, region, model id, etc.).
4. **Domain data:** **Products, orders, and customers** — simple relational shape where an **order references a customer and one or more products** — from **public datasets**; schema is **flexible** — minimal tables or JSON seed acceptable.
5. **MCP server:** Tools for **products**, **orders**, and **customers** (e.g. get by id, bounded list). **Read-only** for Customer and Operator roles; **Admin** role adds write tools (`add_product`, `update_product`). Tool availability is filtered by role (see §5.7). Backend orchestrates MCP ↔ model; implementer documents the wiring (in-process vs sidecar, stdio vs HTTP, etc.).
6. **Agent orchestration:** Use **[LangGraph](https://github.com/langchain-ai/langgraph)** where it adds clarity — e.g. explicit graph for **tool-calling loop**, **guardrail / routing** nodes, or **human-in-the-loop**-ready structure — rather than a single unstructured script. Keep the graph **small and understandable** for a POC.
7. **Observability:** **Langfuse** integration (OSS; prefer **self-hosted** Langfuse for parity with “prefer open source” — or document Langfuse Cloud with clear data-boundary notes).
8. **Production-minded chatbot capabilities** (see §5.3 and §7): guardrails, injection defenses, safe tool use, limits, readiness for OpenShift.
9. **Documentation:** **Development environment** setup + **OpenShift** deployment instructions (images, Deployment/Route, secrets, probes).

### 3.2 Out of scope (v1)

- Fine-tuned models, custom training, or heavy RAG tuning beyond simple retrieval.
- Pixel-perfect UI, design system, or accessibility certification (basic usability only).
- Complex order lifecycle (cart, payment, inventory sync).
- Multi-tenant SaaS billing, full IAM productization (unless later added as stretch).

### 3.3 Future / nice-to-have

- Conversation persistence and admin review UI.
- CI pipeline (GitOps) wired to OpenShift; scheduled eval jobs publishing scores to Langfuse.

---

## 4. User journeys (happy path)

### 4.1 General journeys

| Goal                      | Steps                                                                                                                                                                                               |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ask about a product       | 1. Open web app. 2. Ask about a product (name, SKU, or attribute). 3. Assistant answers using MCP-backed facts.                                                                                     |
| Abuse / injection attempt | 1. User tries to override system policy or exfiltrate secrets. 2. System refuses or neutralizes; no raw system prompt leakage; traces in Langfuse tagged for review (PII policy respected in logs). |

### 4.2 Role-based journeys

| Role | Goal | Steps | Access |
|------|------|-------|--------|
| **Customer** | Check own order | 1. Log in. 2. Ask "Where is my order #123?" 3. Assistant returns status if order belongs to user. | Own data only |
| **Customer** | Ask about another customer | 1. Ask "Show me customer #456's orders." 2. Assistant refuses — not authorized. | Blocked |
| **Operator** | Help a customer | 1. Log in as operator. 2. Ask "What orders does customer #456 have?" 3. Assistant returns customer's order history. | Any customer/order |
| **Operator** | Try to add product | 1. Ask "Add a new product called XYZ." 2. Assistant refuses — operators are read-only. | Blocked |
| **Admin** | Add a product | 1. Log in as admin. 2. Ask "Add product 'Nike Zoom' at $149.99." 3. Assistant calls `add_product` tool and confirms. | Full access |


---

## 5. Functional requirements

### 5.0 Design: BFF, chat transport, and why not “REST-only” replies

**Pattern:** **React (SPA) → Python BFF → Vertex Claude / LangGraph / MCP / Langfuse.** The browser never holds Vertex credentials. The BFF is an **orchestration** layer (policy, tools, tracing), not a thin pass-through.

**Why streaming:** LLM replies are **long-lived** and tokenized. A single blocking **HTTP POST that returns the full assistant text only when complete** is a poor default: bad UX, **proxy/load balancer timeouts**, and harder cancellation. **Industry default for browser chat:** stream tokens over **HTTP with Server-Sent Events (SSE)** from the BFF to the UI, or use **WebSockets** if you need stronger bidirectionality (e.g. cancel, typing signals, multiple server pushes) as a first-class design choice.

**What REST/JSON is still for:** **Health/readiness**, optional **conversation** metadata, admin or **eval** endpoints that call the graph without the browser, and any CRUD that is naturally request/response. The **eval harness** (§13) may use non-streaming server-side calls for determinism; the **interactive UI** must stream.

**OpenShift / edge:** Document **Route/Ingress timeouts** and **SSE buffering** (some proxies buffer streaming responses); configure so streams stay alive for expected max generation time (or cap generation and document).

**React fit:** Prefer a hook or kit that understands **streaming** (`useChat`-style APIs, **assistant-ui**, etc.) so the UI matches the transport.

### 5.1 Chat API

- **FR-1:** **Streaming chat completion:** an HTTP endpoint (typically `POST`) accepts user message + `**conversation_id`** (client UUID or server-issued) and opens an **SSE** stream (or WS channel) that emits **assistant token deltas** and a **terminal** event (`done` / `error`). Tool traces appear only in **non-production** or **admin-only** modes if exposed at all.
- **FR-2:** **Timeouts and limits:** max stream duration, idle timeouts, and max request body size for the user message; on failure, emit a **safe terminal error** on the stream (no stack traces to the client). Document proxy alignment for **long-lived SSE** on OpenShift.
- **FR-2a (recommended):** Accept optional `**X-Request-Id`** (or generate one) on the chat request and attach it to **Langfuse** traces and structured logs (see FR-11, FR-12).

### 5.2 Data and MCP

- **FR-3:** Seed or import **public** product/order/**customer** data; document source URL(s) and license.
- **FR-4:** MCP tools are **read-only**: e.g. get product by id/SKU, list products (capped), get order by id, get customer by id — exact names flexible.
- **FR-5:** For factual questions about catalog, orders, or customers, the app **prefers tool-grounded answers** (document strategy: system policy + LangGraph node(s) if used).

### 5.3 Safety, guardrails, and prompt injection

- **FR-6:** System/developer policy defines allowed domains (products, orders, customers, app help) and refusal behavior for off-topic or harmful requests. The assistant must **decline non-business questions** (e.g., "What is the capital of India?", "Write me a poem") with a polite redirect to its intended scope. **RBAC enforcement:** guardrails must also enforce role-based access — e.g., refuse a Customer asking for another customer's data (see §5.7).
- **FR-7:** Prompt injection mitigations: untrusted user content; no echo of raw system prompt; structured message roles; optional secret-pattern output filters; strict tool argument validation.
- **FR-8:** Tool abuse limits: max tool calls per turn/request; deny unknown tools; MCP does not execute arbitrary code from the model. **RBAC enforcement:** tool availability is filtered by role before the model sees them (see §5.7).
- **FR-9:** Rate limiting on the **chat streaming** endpoint (and any heavy REST endpoints); basic DoS protection.

### 5.4 Operations (production-oriented)

- **FR-10:** Health endpoints suitable for OpenShift liveness/readiness probes.
- **FR-11:** Structured application logs (request id, latency, outcome); align sensitive prompt logging with org policy (often redact or sample in prod).

### 5.5 LLM observability (Langfuse)

- **FR-12:** Emit **Langfuse** traces (or spans) per chat request: user message metadata (hashed or redacted if required), model call(s), **tool/MCP** invocations, latencies, token counts and cost **when the Vertex/SDK exposes them**, and final outcome (success/error).
- **FR-13:** Tag traces with **version dimensions**: `app_version`, `guardrails_version` (or git sha of policy package), `langfuse_sdk_version`, `**model_id`** (Vertex Claude id). Enables before/after comparisons when any of these change.
- **FR-14:** Document how to run Langfuse locally (Docker Compose is typical) and optional OpenShift deployment for self-hosted Langfuse (can be a separate doc section if full deploy is deferred).

### 5.6 Agent (LangGraph)

- **FR-15:** Use **LangGraph** for orchestration when it improves clarity — recommended minimum: a **tool node** + **model node** loop with a **max-iteration** cap, optional **guardrail/router** node before the model. Avoid an unnecessarily large graph for this POC.

### 5.7 Role-Based Access Control (RBAC)

- **FR-16:** The BFF must identify the user's **role** (Customer, Operator, Admin) using **mock auth**: the React UI provides a role/user selector (dropdown), and passes the selection to the BFF via headers (`X-User-Role`, `X-User-Id`). No real authentication — this is for demo/POC purposes.
- **FR-17:** **Tool filtering by role:** Only expose tools appropriate for the role. The model should not even see tools it cannot use.

| Tool | Customer | Operator | Admin |
|------|----------|----------|-------|
| `get_product` | Yes | Yes | Yes |
| `list_products` | Yes | Yes | Yes |
| `get_order` | Own only | Any | Any |
| `get_customer` | Own only | Any | Any |
| `add_product` | No | No | Yes |
| `update_product` | No | No | Yes |

- **FR-18:** **Data filtering:** For Customer role, tools must auto-filter to the authenticated user's own data. Attempting to access another customer's order returns a refusal, not the data.
- **FR-19:** **System prompt per role:** The assistant's instructions vary by role:
  - **Customer:** "You are helping customer {name}. You can only access their orders and profile."
  - **Operator:** "You are a support operator. You can look up any customer or order to help resolve issues. You cannot modify data."
  - **Admin:** "You are an administrator with full access including adding and updating products."
- **FR-20:** **Guardrail enforcement:** A guardrail node (or check) must validate that:
  1. The requested tool is allowed for the role.
  2. The data being accessed belongs to the user (for Customer role).
  3. Write operations are only permitted for Admin role.
  
  Violations result in a polite refusal, logged to Langfuse with a `rbac_violation` tag for review.

---

## 6. Data and integrations

- **Data:** **Products, orders, customers** (simplified). Prefer **public** datasets; document provenance and license.
- **LLM:** **Google Vertex AI** — **Claude** as provisioned for the enterprise.
- **MCP:** Tools backed by the same DB/seed as any REST reads (single source of truth).
- **Observability:** **Langfuse** (OSS); prefer open-source/self-hosted components in the reference architecture.
- **Orchestration:** **LangGraph** (OSS, Apache 2.0) where appropriate for the agent loop.
- **Secrets:** Vertex/GCP and Langfuse keys via env or OpenShift Secrets; never commit secrets.

---

## 7. Non-functional requirements


| Category         | Requirement                                                                                                             |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Priority         | **Speed to runnable system** and **learn production patterns** over schema perfection or UI.                            |
| Security         | TLS at edge; Secrets for credentials; least-privilege GCP SA for Vertex.                                                |
| Performance      | Timeouts on LLM, MCP, and **stream** lifetime; bounded tool loops; OpenShift Route/proxy friendly streaming config.     |
| Observability    | **Langfuse** for LLM-centric traces; cluster-level logs still supported (FR-11).                                        |
| Open source bias | Prefer **OSS** for observability (Langfuse), orchestration (LangGraph), and self-hostable dependencies where practical. |
| Deploy target    | **OpenShift**: containerized services; documented probes and resources.                                                 |


---

## 8. Technical constraints


| Item               | Choice                                                                                           |
| ------------------ | ------------------------------------------------------------------------------------------------ |
| Frontend           | **React**                                                                                        |
| Backend            | **Python BFF** — **SSE** (default) for chat token stream; **REST/JSON** for health and other ops |
| Chat anti-pattern  | Blocking **POST → full JSON assistant body** as the **only** primary UI path                     |
| LLM                | **Claude on Vertex AI**                                                                          |
| Domain             | **Products, orders, customers** — simple schema                                                  |
| Facts to the model | **MCP** tools — read-only for Customer/Operator; read+write for Admin                           |
| Agent              | **LangGraph** where it clarifies tool + guardrail flow                                           |
| LLM observability  | **Langfuse**                                                                                     |
| Access control     | **RBAC** — Customer, Operator, Admin roles (§5.7)                                               |
| Production         | **OpenShift**                                                                                    |
| UI                 | **Basic** functional chat                                                                        |


---

## 9. Quality and delivery

- **Testing:** Unit tests for injection helpers and tool argument validation; smoke tests for chat (mock Vertex in CI if feasible); **golden or property-style tests** for a small **eval set** (see §13).
- **Definition of done:** Local runbook + OpenShift runbook; Langfuse receiving traces from a happy-path chat; documented **upgrade/regression** steps (§13).

---

## 10. Repository and documentation deliverables

1. **Local development:** Python/Node versions, DB seed, backend, MCP, frontend, **Langfuse** (e.g. Compose), env templates.
2. **OpenShift:** Images/manifests, Secrets/ConfigMaps, Routes, probes, notes on egress to Vertex and Langfuse.
3. **Eval / regression:** How to run the **eval suite** and compare Langfuse metrics across versions (pointer to §13).

---

## 11. Open questions


| #   | Question                                                  | Notes                                                                            |
| --- | --------------------------------------------------------- | -------------------------------------------------------------------------------- |
| 1   | Exact Vertex **model id**, **GCP project**, **region**    | Per environment                                                                  |
| 2   | **Workload identity** vs service account key on OpenShift | Cluster / security team                                                          |
| 3   | **Langfuse:** self-hosted on cluster vs Langfuse Cloud    | Data residency / effort                                                          |
| 4   | Confirm observability product name                        | **Langfuse**                                                                     |
| 5   | Public **dataset(s)** for products/orders/customers       | One or combined sources; document license                                        |
| 6   | **SSE vs WebSockets** for chat transport                  | Default **SSE**; choose WS only if cancel/bidirectional needs justify complexity |


---

## 12. Prompt snippet for later (copy-paste)

> Implement the system in `project-requirements.md`: React chat UI wired to a **Python BFF**; **chat completions over SSE** (or WebSockets if documented) per §5.0 — **not** blocking REST-as-only delivery for the main UI. Use **REST/JSON** for health and operational APIs. **Claude on Vertex AI**; SQLite or Postgres seeded from **public** data for **products, orders, and customers** (flexible simple schema). Add **MCP** tools for all three entities with **RBAC** per §5.7 (Customer: own data read-only; Operator: all data read-only; Admin: full read+write including `add_product`, `update_product`). Orchestrate with **LangGraph** where it helps (tool loop + caps + guardrail node for RBAC enforcement). Integrate **Langfuse** for tracing (model + tool steps + latency/tokens/cost when available); tag traces with `model_id`, app/guardrails revision, and SDK versions; propagate request/correlation id. Implement guardrails and prompt-injection defenses per §5.3 including **role-based access enforcement**. Include a small **eval/regression** harness (may use non-streaming server-side path per §13.3) and document §13 practices. Document local dev (including Langfuse), **streaming-friendly** OpenShift Route/proxy settings, and deployment. Prioritize production patterns and speed over UI polish.

---

## 13. How to know the app still “performs well” after upgrades

This section answers: *If we upgrade **guardrails**, **Langfuse** (SDK/server), or ship a **new Claude** model on Vertex, how do we detect regressions?* It summarizes **common industry practice**; the implementation should automate as much as is practical for a POC.

### 13.1 What “performing well” means (split by concern)


| Concern                     | Signals                                                                                                             |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| **Correctness / grounding** | Right tool chosen; factual answers match DB for golden queries; fewer hallucinated SKUs/ids.                        |
| **Safety / policy**         | Injection suite still **refuses** or **degrades safely**; no system-prompt leakage; tool allowlists still enforced. |
| **Latency & cost**          | p95 end-to-end latency stable or within budget; tokens per request not spiking (Langfuse dashboards).               |
| **Reliability**             | Error rate, timeouts, MCP failures unchanged or improved.                                                           |


### 13.2 Tools and practices (widely used)

1. **Versioned eval / regression suite (“golden set”)**
  - Curated **inputs** (normal questions + **injection** cases + edge cases) with **assertions**: expected tool(s), JSON schema of tool args, or **reference answers** substrings from known DB rows.  
  - Run in **CI on every change** to guardrails package, LangGraph graph, prompt templates, Langfuse SDK, or pinned model id.  
  - Optional: **LLM-as-judge** only as a secondary signal (higher variance; use fixed rubric and compare across versions in Langfuse Experiments).
2. **Observability comparison (Langfuse)**
  - Use **tags/metadata** (FR-13): `model_id`, `guardrails_version`, `langfuse_sdk_version`, `release`.  
  - After upgrade, run the same golden traffic (staging) and compare **latency**, **tool-call rate**, **error rate**, and **human or automated scores** in Langfuse (scores API / datasets).
3. **Canary or shadow traffic**
  - Route a **small percentage** of traffic (or internal testers only) to the new model or new policy version before 100% rollout; watch Langfuse and cluster metrics. Industry standard for **model** swaps.
4. **Prompt and policy as code**
  - Store system/guardrail text in **git** with semver or git sha in trace tags so regressions are bisectable.
5. **OpenTelemetry (optional alignment)**
  - Langfuse aligns with trace-style workflows; exporting compatible spans can help if the org standardizes on OTel + a backend later.

### 13.3 Deliverable for this project

- **Minimum:** A **documented** folder (e.g. `eval/` or `tests/eval/`) with **JSON/YAML cases** + a **script** (`pytest` or CLI) that drives the **orchestration layer** (HTTP **non-streaming** test endpoint, or **in-process graph** invocation) and asserts tools/outcomes; the **browser** path remains streaming per §5.0. README section “**Upgrading model or dependencies**” that says: run eval → compare Langfuse session for a fixed batch → canary if green.

---

## Document history

- **RBAC** added (§2.1, §5.7): three roles (Customer, Operator, Admin) with tool filtering, data filtering, role-specific system prompts, and guardrail enforcement. Admin role introduces **write operations** (`add_product`, `update_product`). **Mock auth** via UI dropdown — no SSO.
- Domain extended to **customers**; **Langfuse** observability; **LangGraph** agent; **§13** upgrade/regression practices added.
- **§5.0** and related updates: chat design uses **Python BFF + SSE** (default) for assistant streaming; **REST/JSON** for non-chat APIs; explicit rejection of blocking REST-only as the primary UI chat path.

