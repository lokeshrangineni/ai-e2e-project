# ShopChat — AI-Powered Shopping Assistant

> Building an AI chatbot is easy. Building one that's **secure, observable, tested, and production-ready** is hard. This project does both — end to end.

ShopChat is a reference implementation of an **enterprise-grade LLM application** deployed on OpenShift. It connects a React frontend to a Claude-powered agent that can browse products, look up orders, and manage customers — with data surfaced through **MCP (Model Context Protocol)** for structured, real-time backend access, **RBAC** woven into every layer from the API to agent tool permissions, multi-layer guardrails, full observability, and a golden-set eval suite.

If you're looking for a working example of how the modern AI stack fits together — from streaming chat to NeMo Guardrails to Langfuse experiments — this is it.

![RBAC in action — a customer is blocked from another user's order, while an admin can access it freely](docs/screenshots/rbac-order-blocked.png)

## What You'll Find Here

- **Streaming chat** (SSE) from a Python BFF to a React UI
- **Tool-grounded answers** via MCP — the LLM calls structured tools instead of hallucinating
- **Role-based access control** — customer, operator, and admin roles with different tool visibility and data access
- **Defence-in-depth guardrails** — regex patterns, NVIDIA NeMo Guardrails (Colang policies), and role-aware system prompts
- **LLM observability** — traces, latency, token counts, and cost tracked via Langfuse
- **Golden set evals** — 47 automated test cases with Langfuse Experiments for model comparison
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
├── mcp-server/               # MCP tool server (RBAC-enforced tools)
├── eval/                     # Layer 2 golden set evals (47 cases)
│   ├── cases/                # YAML test case definitions
│   └── run_eval.py           # Langfuse-integrated eval runner
├── data/                     # Synthetic CSV data (customers, products, orders)
├── docs/                     # Design docs (guardrails, observability, test strategy)
├── Makefile                  # Common commands (test, eval, start)
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

Three independently-configurable layers that catch progressively subtler attacks:

| Layer | Type | Latency | Catches |
|---|---|---|---|
| 1 | Regex patterns | ~0ms | Obvious injection keywords, off-topic patterns |
| 2 | NeMo Guardrails (Colang + Haiku) | ~200-500ms | Rephrased injection, jailbreaks, off-topic |
| 3 | LLM system prompt | Built-in | Role enforcement, RBAC at reasoning level |

NeMo policies live in `guardrails_config/<role>/` as version-controlled Colang files — completely independent of the main LLM's system prompt.

See [docs/guardrails.md](docs/guardrails.md) for details.

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

When enabled, every request emits traces (LLM calls, tool invocations, guardrail decisions, token counts, latency). Results are also used for storing golden set eval experiments.

See [docs/langfuse-observability.md](docs/langfuse-observability.md) for integration details.

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
