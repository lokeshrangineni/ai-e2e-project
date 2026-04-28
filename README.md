# ShopChat — AI-Powered Shopping Assistant

A production-oriented learning project that demonstrates how to build, secure, observe, and deploy an **LLM-backed chatbot** on **OpenShift**. The assistant answers questions about products, orders, and customers using **Claude on Google Cloud Vertex AI**, with tool access via the **Model Context Protocol (MCP)**, multi-layer guardrails including **NVIDIA NeMo Guardrails**, observability through **Langfuse**, and agent orchestration with **LangGraph**.

## Why This Project Exists

The goal is hands-on experience with the **AI application stack** and **shipping to production** — not perfecting a specific business schema or UI. It mirrors a real internal assistant over enterprise data, covering:

- **Streaming chat** (SSE) from a Python BFF to a React UI
- **Tool-grounded answers** via MCP — the LLM calls structured tools instead of guessing
- **Role-based access control** — customer, operator, and admin roles with different tool visibility and data access
- **Defence-in-depth guardrails** — regex, NeMo Guardrails (Colang policies), and LLM system prompt
- **LLM observability** — traces, latency, token counts, and cost signals via Langfuse
- **OpenShift-ready** architecture with documented deployment patterns

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser  (React + Vite)                  :5173                 │
│  - Role selector (customer / operator / admin)                  │
│  - Streaming chat UI via SSE                                    │
└────────────────────────┬────────────────────────────────────────┘
                         │ POST /chat/stream  (SSE)
                         │ Headers: X-User-Role, X-User-Id, X-User-Name
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Shop Backend API  (FastAPI + LangGraph)   :8000                │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  LangGraph Workflow                                      │   │
│  │                                                         │   │
│  │  [input_guardrail] → [call_model] → [process_tool_calls]│   │
│  │        ↑                                  │             │   │
│  │        └──────────[tools]─────────────────┘             │   │
│  │                                                         │   │
│  │  Guardrail layers:                                      │   │
│  │    1. Regex patterns (sync, zero latency)               │   │
│  │    2. NeMo Guardrails + Claude Haiku (Colang policies)  │   │
│  │    3. LLM system prompt (implicit, per-role)            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                         │ stdio (MCP)                           │
│                         │                                       │
│  Langfuse ◄─── traces/spans via LangChain callback ────────   │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  MCP Server  (Python, spawned as subprocess)                    │
│  - Tools: get_customer, get_orders, get_products, list_customers│
│  - Role-based tool access enforcement                           │
│  - Reads CSV data from /data/                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
ai-e2e-project/
├── shop-ui/                  # React + TypeScript + Vite frontend
├── shop-backend-api/         # FastAPI backend with LangGraph agent
│   ├── src/shop_backend_api/
│   │   ├── main.py           # FastAPI app, SSE streaming endpoint
│   │   ├── agent.py          # LangGraph workflow, MCP client
│   │   ├── guardrails.py     # Regex guardrails + NeMo wrapper
│   │   ├── nemo_guardrails.py# NeMo Guardrails integration (LLMRails)
│   │   ├── observability.py  # Langfuse callback handler
│   │   └── config.py         # All configuration via env vars
│   └── guardrails_config/    # Colang policy files (per role)
│       ├── customer/         # config.yml + main.co
│       ├── operator/         # config.yml + main.co
│       └── admin/            # config.yml + main.co
├── mcp-server/               # MCP tool server
│   └── src/shop_mcp_server/
│       ├── server.py         # Tool definitions + RBAC enforcement
│       └── data.py           # CSV data access layer
├── data/                     # CSV data files
│   ├── customers.csv
│   ├── orders.csv
│   ├── order_items.csv
│   └── products.csv
└── project-requirements.md   # Full requirements document
```

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | >= 3.11 | Backend and MCP server |
| Node.js | >= 18 | Frontend |
| `uv` | latest | Python package manager |
| `npm` | latest | Node package manager |
| GCP account | — | Vertex AI / Claude access |

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/lokeshrangineni/ai-e2e-project.git
cd ai-e2e-project

# Create your environment file
cp shop-backend-api/.env.example shop-backend-api/.env
# Edit .env — at minimum set ANTHROPIC_VERTEX_PROJECT_ID
```

### 2. Start the backend

```bash
cd shop-backend-api
uv sync                    # install dependencies (first time)
uv run uvicorn shop_backend_api.main:app --reload --host 0.0.0.0 --port 8000
```

The MCP server is spawned automatically as a subprocess — no separate start needed.

API available at `http://localhost:8000` | Docs at `http://localhost:8000/docs`

### 3. Start the frontend

```bash
cd shop-ui
npm install                # first time only
npm run dev
```

UI available at `http://localhost:5173`

### 4. Stop services

| Service | How to stop |
|---|---|
| Backend API | `Ctrl+C` in the terminal running `uvicorn` |
| Frontend | `Ctrl+C` in the terminal running `npm run dev` |
| MCP Server | Stops automatically when the backend stops |

---

## Configuration

All backend settings are controlled via environment variables or a `.env` file in `shop-backend-api/`.

```bash
cp shop-backend-api/.env.example shop-backend-api/.env
```

### Required

| Variable | Description | Example |
|---|---|---|
| `ANTHROPIC_VERTEX_PROJECT_ID` | GCP project with Claude access | `your-gcp-project` |
| `CLOUD_ML_REGION` | Vertex AI region | `global` |
| `MODEL_ID` | Claude model ID | `claude-sonnet-4@20250514` |

### Optional — Langfuse (LLM Observability)

| Variable | Default | Description |
|---|---|---|
| `LANGFUSE_ENABLED` | `false` | Enable trace collection |
| `LANGFUSE_PUBLIC_KEY` | — | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | — | Langfuse secret key |
| `LANGFUSE_HOST` | `http://localhost:3000` | Langfuse server URL (cloud or self-hosted) |

### Optional — NeMo Guardrails (Layer 2)

| Variable | Default | Description |
|---|---|---|
| `NEMO_GUARDRAILS_ENABLED` | `false` | Enable Colang policy enforcement |
| `GUARDIAN_MODEL_ID` | `claude-haiku-4-5@20251001` | LLM used for intent classification |
| `GUARDIAN_REGION` | `us-east5` | Vertex AI region for Haiku (regional, not `global`) |

### Optional — Regex Guardrails (Layer 1)

| Variable | Default | Description |
|---|---|---|
| `REGEX_GUARDRAILS_ENABLED` | `true` | Enable fast regex pattern checks |

> **Note:** The server must be restarted after `.env` changes — hot-reload only watches `.py` files.

---

## Guardrails (Defence in Depth)

The application uses a three-layer guardrail architecture. Each layer is independently configurable and catches progressively subtler attacks.

| Layer | Type | Latency | Config | Catches |
|---|---|---|---|---|
| 1 | **Regex patterns** | ~0ms | `REGEX_GUARDRAILS_ENABLED` | Obvious injection keywords, off-topic patterns, input length abuse |
| 2 | **NeMo Guardrails** (Colang + Claude Haiku) | ~200-500ms | `NEMO_GUARDRAILS_ENABLED` | Rephrased injection, jailbreaks, off-topic (LLM-classified), cross-customer probing |
| 3 | **LLM system prompt** | Built-in | Always active | Role enforcement, RBAC at reasoning level, general policy |

### How NeMo Guardrails works

[NVIDIA NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails) enforces policies defined in **Colang** (`.co`) files — plain text, version-controlled, and completely independent of the main LLM's system prompt. Claude Sonnet never sees these policies and cannot bypass them.

**Flow per request:**
1. User message arrives at the `input_guardrail` node in LangGraph
2. NeMo sends a policy prompt to **Claude Haiku** asking: "Should this message be blocked?" (yes/no)
3. If Haiku answers "yes" → NeMo's deterministic engine fires the matching Colang flow → returns a canned refusal
4. If Haiku answers "no" → message passes through to Claude Sonnet for normal processing

**Per-role policies** live in `guardrails_config/`:
- `customer/` — blocks off-topic, injection, jailbreak, cross-customer access, write attempts
- `operator/` — blocks off-topic, injection, jailbreak, data modification attempts
- `admin/` — only blocks injection and jailbreak (broadest access)

To customize policies, edit the `config.yml` (prompt) and `main.co` (flow + refusal message) files. No code changes needed.

---

## Role-Based Access Control (RBAC)

The UI provides a role selector dropdown. Role is sent as HTTP headers on every request (mock auth for demo/POC — no real authentication).

| Role | Data Access | Operations |
|---|---|---|
| `customer` | Own orders and profile only | Read own data |
| `operator` | All customers and orders | Read all data (for troubleshooting) |
| `admin` | Everything | Read + write (add/edit products) |

RBAC is enforced at **three levels**:
1. **Guardrails** — NeMo policies and regex patterns block disallowed requests before the LLM
2. **LLM system prompt** — role-specific instructions tell the LLM to refuse out-of-scope requests
3. **MCP server** — hard-enforces tool access based on role, regardless of LLM behaviour

### Tool access matrix

| Tool | Customer | Operator | Admin |
|---|---|---|---|
| `get_product` / `list_products` | Yes | Yes | Yes |
| `get_order` | Own only | Any | Any |
| `get_customer` | Own only | Any | Any |
| `list_customers` | No | Yes | Yes |
| `add_product` / `update_product` | No | No | Yes |

---

## LLM Observability (Langfuse)

When enabled, every chat request emits **Langfuse traces** including:
- User message metadata
- Model calls (latency, token counts)
- Tool/MCP invocations
- Guardrail decisions
- Version tags: `model_id`, `app_version`, `guardrails_version`

Langfuse can be run as:
- **Cloud**: Sign up at [cloud.langfuse.com](https://cloud.langfuse.com) and set the API keys
- **Self-hosted on OpenShift**: Deploy using the [langfuse-k8s Helm chart](https://github.com/langfuse/langfuse-k8s) with OpenShift support

---

## API Reference

### `POST /chat/stream`

Streaming chat endpoint (Server-Sent Events).

**Headers:**

| Header | Default | Description |
|---|---|---|
| `X-User-Role` | `customer` | `customer` \| `operator` \| `admin` |
| `X-User-Id` | `cust_001` | User ID (e.g. `cust_021`) |
| `X-User-Name` | `Guest` | Display name |
| `X-Request-Id` | auto | Optional trace/correlation ID |

**Body:**
```json
{ "message": "What are my recent orders?", "conversation_id": "optional-uuid" }
```

**SSE Events:**
```
data: {"type": "token", "content": "Your "}
data: {"type": "token", "content": "recent order..."}
data: {"type": "done", "conversation_id": "uuid"}
data: {"type": "error", "message": "..."}
```

### `GET /health`

Returns `{"status": "healthy", "version": "0.1.0"}`.

---

## User Journeys

| Role | Goal | What happens |
|---|---|---|
| **Customer** | Ask about products | Assistant lists products using MCP tools |
| **Customer** | Check own orders | Assistant returns order status for the logged-in customer |
| **Customer** | Access another customer's data | Refused — guardrails + RBAC block the request |
| **Operator** | Look up any customer's orders | Assistant returns the data (operators have read access to all) |
| **Operator** | Try to modify data | Refused — operators are read-only |
| **Admin** | Add a new product | Assistant calls `add_product` tool and confirms |
| **Any** | Prompt injection / jailbreak | Caught by regex or NeMo Guardrails before reaching the LLM |
| **Any** | Off-topic question | Caught by NeMo Guardrails or LLM system prompt |

---

## Tech Stack

| Component | Technology | License |
|---|---|---|
| Frontend | React + TypeScript + Vite | MIT |
| Backend / BFF | Python + FastAPI | MIT / BSD |
| LLM | Claude on Google Vertex AI | Commercial |
| Agent orchestration | LangGraph | Apache 2.0 |
| Tool protocol | Model Context Protocol (MCP) | Apache 2.0 |
| Guardrails | NVIDIA NeMo Guardrails + Colang | Apache 2.0 |
| Intent classifier | Claude Haiku on Vertex AI | Commercial |
| Observability | Langfuse | MIT |
| Deployment target | OpenShift (Kubernetes) | — |
