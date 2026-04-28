"""FastAPI application for the shopping chatbot backend."""

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .config import settings
from .agent import get_agent, cleanup_agent, UserContext
from .observability import get_langfuse_handler, flush_langfuse_handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    # Startup
    print("Starting Shop Backend API...")
    agent = await get_agent()
    print(f"Agent initialized with {len(agent.tools)} tools")
    yield
    # Shutdown
    print("Shutting down...")
    await cleanup_agent()


app = FastAPI(
    title="Shop Backend API",
    description="Shopping chatbot backend with LangGraph + MCP + Claude",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class ChatRequest(BaseModel):
    """Chat request body."""
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    """Chat response body (for non-streaming)."""
    response: str
    conversation_id: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str


# Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for liveness/readiness probes."""
    return HealthResponse(status="healthy", version=settings.app_version)


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    x_user_role: str = Header(default="customer", alias="X-User-Role"),
    x_user_id: str = Header(default="cust_001", alias="X-User-Id"),
    x_user_name: str = Header(default="Guest", alias="X-User-Name"),
):
    """
    Non-streaming chat endpoint.

    Headers:
    - X-User-Role: customer | operator | admin
    - X-User-Id: User ID (e.g., cust_001)
    - X-User-Name: User display name
    """
    agent = await get_agent()

    user_context = UserContext(
        role=x_user_role,
        user_id=x_user_id,
        user_name=x_user_name,
    )

    conversation_id = request.conversation_id or str(uuid.uuid4())

    lf_handler = get_langfuse_handler(
        user_id=x_user_id,
        session_id=conversation_id,
        role=x_user_role,
    )

    try:
        response = await agent.chat(
            message=request.message,
            user_context=user_context,
            conversation_history=None,  # TODO: Implement conversation history
            callbacks=[lf_handler] if lf_handler else None,
        )

        return ChatResponse(response=response, conversation_id=conversation_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        flush_langfuse_handler(lf_handler)


@app.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    x_user_role: str = Header(default="customer", alias="X-User-Role"),
    x_user_id: str = Header(default="cust_001", alias="X-User-Id"),
    x_user_name: str = Header(default="Guest", alias="X-User-Name"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
):
    """
    Streaming chat endpoint using Server-Sent Events (SSE).

    Headers:
    - X-User-Role: customer | operator | admin
    - X-User-Id: User ID (e.g., cust_001)
    - X-User-Name: User display name
    - X-Request-Id: Optional request ID for tracing

    SSE Events:
    - data: {"type": "token", "content": "..."}
    - data: {"type": "done", "conversation_id": "..."}
    - data: {"type": "error", "message": "..."}
    """
    agent = await get_agent()

    user_context = UserContext(
        role=x_user_role,
        user_id=x_user_id,
        user_name=x_user_name,
    )

    conversation_id = request.conversation_id or str(uuid.uuid4())
    request_id = x_request_id or str(uuid.uuid4())

    lf_handler = get_langfuse_handler(
        user_id=x_user_id,
        session_id=conversation_id,
        role=x_user_role,
    )

    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            async for token in agent.chat_stream(
                message=request.message,
                user_context=user_context,
                conversation_history=None,
                callbacks=[lf_handler] if lf_handler else None,
            ):
                # Pre-serialize to JSON string: sse_starlette calls str() on data dict,
                # producing Python repr with single quotes — not valid JSON.
                yield {
                    "event": "message",
                    "data": json.dumps({"type": "token", "content": token}),
                }

            yield {
                "event": "message",
                "data": json.dumps({"type": "done", "conversation_id": conversation_id}),
            }

        except Exception as e:
            yield {
                "event": "message",
                "data": json.dumps({"type": "error", "message": str(e)}),
            }
        finally:
            flush_langfuse_handler(lf_handler)

    return EventSourceResponse(event_generator())


@app.get("/tools")
async def list_tools():
    """List available MCP tools (for debugging)."""
    agent = await get_agent()
    return {
        "tools": [
            {"name": tool.name, "description": tool.description}
            for tool in agent.tools
        ]
    }


def run():
    """Run the server."""
    import uvicorn
    uvicorn.run(
        "shop_backend_api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
