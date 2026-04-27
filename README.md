# ShopChat — AI-Powered Shopping Assistant

A full-stack AI chatbot for a retail shop, built with **LangGraph**, **MCP (Model Context Protocol)**, **Claude on Vertex AI**, and a **React/Vite** frontend. Demonstrates role-based access control, streaming responses, multi-layer guardrails, and agentic tool use.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser  (React + Vite)                  :5173                 │
│  - Role selector (customer / operator / admin)                  │
│  - Streaming chat UI via SSE                                     │
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
│  │    1. Regex (always active)                             │   │
│  │    2. Granite Guardian LLM (optional, config-driven)    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                         │ stdio (MCP)                           │
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
├── shop-ui/              # React + TypeScript + Vite frontend
├── shop-backend-api/     # FastAPI backend with LangGraph agent
│   └── src/shop_backend_api/
│       ├── main.py       # FastAPI app, SSE endpoint
│       ├── agent.py      # LangGraph workflow, MCP client
│       ├── guardrails.py # Input validation (regex + Granite Guardian)
│       └── config.py     # All configuration via env vars
├── mcp-server/           # MCP tool server
│   └── src/shop_mcp_server/
│       ├── server.py     # Tool definitions + RBAC enforcement
│       └── data.py       # CSV data access layer
└── data/                 # CSV data files
    ├── customers.csv
    ├── orders.csv
    ├── order_items.csv
    └── products.csv
```

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | ≥ 3.11 | Backend & MCP server |
| Node.js | ≥ 18 | Frontend |
| `uv` | latest | Python package manager |
| `npm` | latest | Node package manager |
| Ollama | latest | Local LLM for Granite Guardian (optional) |
| GCP account | — | Vertex AI / Claude access |

---

## Starting the Services

### 1. MCP Server (started automatically)

The MCP server is spawned automatically by the backend as a subprocess — you do **not** need to start it manually.

---

### 2. Shop Backend API

```bash
cd shop-backend-api

# Install dependencies (first time only)
uv sync

# Start the server
uv run uvicorn shop_backend_api.main:app --reload --reload-include="*.env" --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.
Interactive API docs at `http://localhost:8000/docs`.

---

### 3. Shop UI (Frontend)

```bash
cd shop-ui

# Install dependencies (first time only)
npm install

# Start the dev server
npm run dev
```

The UI will be available at `http://localhost:5173`.

---

## Stopping the Services

| Service | How to stop |
|---|---|
| Backend API | `Ctrl+C` in the terminal running `uvicorn` |
| Frontend | `Ctrl+C` in the terminal running `npm run dev` |
| MCP Server | Stops automatically when the backend stops |

---

## Configuration

All backend settings are controlled via environment variables or a `.env` file in `shop-backend-api/`.

Create `shop-backend-api/.env`:

```env
# Claude via Vertex AI (required)
ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
CLOUD_ML_REGION=us-east5

# LLM model
MODEL_ID=claude-sonnet-4@20250514

# Data directory (defaults to ../data relative to the package)
SHOP_DATA_DIR=/path/to/ai-e2e-project/data

# Granite Guardian — LLM-based guardrails (optional, disabled by default)
GRANITE_GUARDIAN_ENABLED=false
GRANITE_GUARDIAN_MODEL=granite3-guardian:2b
GRANITE_GUARDIAN_ENDPOINT=http://localhost:11434
```

---

## Granite Guardian (LLM Guardrails)

The backend supports an optional second layer of input guardrails using [IBM Granite Guardian](https://huggingface.co/ibm-granite/granite-guardian-3.2-2b), a small specialist model for safety classification.

### Enable it

**1. Pull the model via Ollama (first time only):**

```bash
ollama pull granite3-guardian:2b
```

**2. Set the environment variable:**

```bash
GRANITE_GUARDIAN_ENABLED=true uv run uvicorn shop_backend_api.main:app --reload
```

Or add `GRANITE_GUARDIAN_ENABLED=true` to your `.env` file.

### Guardrail layers (in order)

| Layer | Type | Always active? | Catches |
|---|---|---|---|
| 1 | Regex | Yes | Obvious injection, off-topic, length abuse |
| 2 | Granite Guardian LLM | Config-driven | Rephrased injection, jailbreaks, cross-customer probing |
| 3 | LLM system prompt | Yes | Role enforcement, RBAC at reasoning level |

---

## Role-Based Access Control (RBAC)

The UI lets you switch between three roles. Role is sent as an HTTP header on every request.

| Role | What they can access |
|---|---|
| `customer` | Their own orders and profile only |
| `operator` | All customers and orders (read-only) |
| `admin` | All customers, orders, and products (read + write) |

RBAC is enforced at **two levels**:
1. **LLM system prompt** — instructs the LLM to refuse out-of-scope requests
2. **MCP server** — hard-enforces tool access based on role, regardless of LLM behaviour

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
| `X-Request-Id` | auto | Optional trace ID |

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
