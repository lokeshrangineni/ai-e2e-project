# Shop Backend API

Backend service for the shopping chatbot. Uses LangGraph for orchestration, MCP for tool access, and Claude for the LLM.

## Architecture

```
React UI
    │
    ▼
┌─────────────────────────────────────────┐
│           Shop Backend API              │
│  ┌─────────────────────────────────┐   │
│  │         FastAPI + SSE           │   │
│  └─────────────────────────────────┘   │
│                  │                      │
│  ┌─────────────────────────────────┐   │
│  │   LangGraph (Orchestration)     │   │
│  │   ├── Input Guardrails          │   │
│  │   ├── LLM Node (Claude)         │   │
│  │   └── Tool Node (MCP)           │   │
│  └─────────────────────────────────┘   │
│                  │                      │
│  ┌─────────────────────────────────┐   │
│  │   MCP Client (langchain-mcp)    │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
                   │
                   ▼
         ┌─────────────────┐
         │   MCP Server    │
         │  (shop tools)   │
         └─────────────────┘
```

## Setup

```bash
cd shop-backend-api
pip install -e .

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys
```

## Running

```bash
# Development
shop-backend-api

# Or directly
uvicorn shop_backend_api.main:app --reload --port 8000
```

## API Endpoints

### Health Check
```
GET /health
```

### Chat (Non-streaming)
```
POST /chat
Content-Type: application/json
X-User-Role: customer
X-User-Id: cust_001
X-User-Name: Alice

{
  "message": "What's the price of Nike Air Max?",
  "conversation_id": "optional-uuid"
}
```

### Chat (Streaming SSE)
```
POST /chat/stream
Content-Type: application/json
X-User-Role: customer
X-User-Id: cust_001
X-User-Name: Alice

{
  "message": "What's the price of Nike Air Max?"
}

Response: Server-Sent Events
data: {"type": "token", "content": "The"}
data: {"type": "token", "content": " Nike"}
data: {"type": "token", "content": " Air"}
...
data: {"type": "done", "conversation_id": "uuid"}
```

### List Tools
```
GET /tools
```

## RBAC Headers

| Header | Values | Description |
|--------|--------|-------------|
| X-User-Role | customer, operator, admin | User's role |
| X-User-Id | cust_001, op_001, admin_001 | User identifier |
| X-User-Name | Alice, Bob, etc. | Display name |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| ANTHROPIC_API_KEY | Anthropic API key | - |
| SHOP_DATA_DIR | Path to data directory | ../data |
| API_PORT | Server port | 8000 |
| DEBUG | Enable debug mode | false |
| LANGFUSE_ENABLED | Enable Langfuse tracing | false |

## Testing

```bash
pip install -e ".[dev]"
pytest
```
