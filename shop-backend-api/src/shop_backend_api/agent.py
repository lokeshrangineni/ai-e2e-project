"""LangGraph agent with MCP client for tool access."""

import os
from typing import Annotated, TypedDict, Literal
from contextlib import asynccontextmanager

from langchain_anthropic import ChatAnthropic
from langchain_google_vertexai.model_garden import ChatAnthropicVertex
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from langchain_mcp_adapters.client import MultiServerMCPClient

from .config import settings
from .guardrails import run_input_guardrails, run_granite_guardrail, get_system_prompt


class UserContext(TypedDict):
    """User context for RBAC."""
    role: str
    user_id: str
    user_name: str


class AgentState(TypedDict):
    """State for the LangGraph agent."""
    messages: Annotated[list, add_messages]
    user_context: UserContext
    guardrail_blocked: bool
    guardrail_message: str | None


# MCP Client configuration (langchain-mcp-adapters 0.1.0+ format)
# Uses `uv run --directory` so the MCP server runs inside its own venv
# where shop_mcp_server is installed, not the backend's venv.
MCP_SERVERS = {
    "shop": {
        "transport": "stdio",
        "command": settings.mcp_server_command,
        "args": [
            "run",
            "--directory", settings.mcp_server_dir,
            "python", "-m", settings.mcp_server_name,
        ],
        "env": {
            **os.environ,
            "SHOP_DATA_DIR": settings.shop_data_dir,
        },
    }
}


class ShopAgent:
    """Shopping assistant agent using LangGraph and MCP."""

    def __init__(self):
        # Use Vertex AI if project is configured, otherwise Anthropic
        if settings.anthropic_vertex_project_id:
            self.llm = ChatAnthropicVertex(
                model_name=settings.model_id,
                project=settings.anthropic_vertex_project_id,
                location=settings.cloud_ml_region,
                max_tokens=1024,
            )
        else:
            self.llm = ChatAnthropic(
                model=settings.model_id,
                api_key=settings.anthropic_api_key,
                max_tokens=1024,
            )
        self.mcp_client = None
        self.tools = []
        self.graph = None

    async def initialize(self):
        """Initialize MCP client and build the graph."""
        # Connect to MCP server
        self.mcp_client = MultiServerMCPClient(MCP_SERVERS)

        # Load tools from MCP (new API in 0.1.0 - no context manager needed)
        self.tools = await self.mcp_client.get_tools()

        # Bind tools to LLM
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        # Build the graph
        self._build_graph()

    async def cleanup(self):
        """Cleanup MCP client."""
        # New langchain-mcp-adapters 0.1.0+ doesn't require explicit cleanup
        self.mcp_client = None

    def _build_graph(self):
        """Build the LangGraph workflow."""

        # Tool node for executing MCP tools
        tool_node = ToolNode(self.tools)

        # Define nodes
        async def input_guardrail(state: AgentState) -> AgentState:
            """Check input guardrails (regex always, Granite Guardian if enabled)."""
            last_message = state["messages"][-1]
            if not isinstance(last_message, HumanMessage):
                return state

            user_input = last_message.content

            # Layer 1: fast regex check (skipped if disabled in config)
            if settings.regex_guardrails_enabled:
                result = run_input_guardrails(user_input)
                if not result.allowed:
                    print(f"[Guardrail] Blocked by regex: {result.message}")
                    return {
                        **state,
                        "guardrail_blocked": True,
                        "guardrail_message": f"🛡️ Blocked by: Regex Guardrail\n\n{result.message}",
                    }

            # Layer 2: LLM-based guardrail check (Granite or Claude Haiku)
            if settings.granite_guardian_enabled:
                role = state["user_context"]["role"]
                result = await run_granite_guardrail(user_input, role=role)
                if not result.allowed:
                    label = {
                        "granite": "Granite Guardian",
                        "claude-haiku": "Claude Haiku Guardrail",
                    }.get(result.source, result.source.title())
                    print(f"[Guardrail] Blocked by {label}: {result.message}")
                    return {
                        **state,
                        "guardrail_blocked": True,
                        "guardrail_message": f"🛡️ Blocked by: {label}\n\n{result.message}",
                    }

            return {**state, "guardrail_blocked": False, "guardrail_message": None}

        async def call_model(state: AgentState) -> AgentState:
            """Call the LLM with tools."""
            # Build system prompt based on role
            user_ctx = state["user_context"]
            system_prompt = get_system_prompt(
                role=user_ctx["role"],
                user_id=user_ctx["user_id"],
                user_name=user_ctx["user_name"],
            )

            # Add system message if not present
            messages = state["messages"]
            if not messages or not isinstance(messages[0], SystemMessage):
                messages = [SystemMessage(content=system_prompt)] + messages

            # Call LLM
            response = await self.llm_with_tools.ainvoke(messages)

            return {"messages": [response]}

        async def process_tool_calls(state: AgentState) -> AgentState:
            """Inject user context into tool calls and execute."""
            last_message = state["messages"][-1]

            if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
                return state

            # Inject user context into each tool call
            user_ctx = state["user_context"]
            modified_tool_calls = []

            for tool_call in last_message.tool_calls:
                # Add user context to arguments
                args = tool_call["args"].copy()
                args["_user_context"] = {
                    "role": user_ctx["role"],
                    "user_id": user_ctx["user_id"],
                }
                modified_tool_calls.append({
                    **tool_call,
                    "args": args,
                })

            # Update the message with modified tool calls.
            # Preserve the original id so add_messages REPLACES it
            # rather than appending a duplicate, which would cause
            # Claude to see a tool_use block without a tool_result.
            modified_message = AIMessage(
                id=last_message.id,
                content=last_message.content,
                tool_calls=modified_tool_calls,
            )

            return {"messages": [modified_message]}

        def should_continue(state: AgentState) -> Literal["tools", "end", "blocked"]:
            """Determine next step."""
            if state.get("guardrail_blocked"):
                return "blocked"

            last_message = state["messages"][-1]

            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                return "tools"

            return "end"

        def blocked_response(state: AgentState) -> AgentState:
            """Return guardrail blocked response."""
            return {
                "messages": [AIMessage(content=state["guardrail_message"])],
            }

        # Build the graph
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("input_guardrail", input_guardrail)
        workflow.add_node("call_model", call_model)
        workflow.add_node("process_tool_calls", process_tool_calls)
        workflow.add_node("tools", tool_node)
        workflow.add_node("blocked_response", blocked_response)

        # Add edges
        workflow.add_edge(START, "input_guardrail")
        workflow.add_conditional_edges(
            "input_guardrail",
            should_continue,
            {
                "blocked": "blocked_response",
                "tools": "call_model",  # Won't happen here, but needed
                "end": "call_model",
            },
        )
        workflow.add_edge("call_model", "process_tool_calls")
        workflow.add_conditional_edges(
            "process_tool_calls",
            should_continue,
            {
                "tools": "tools",
                "end": END,
                "blocked": "blocked_response",
            },
        )
        workflow.add_edge("tools", "call_model")
        workflow.add_edge("blocked_response", END)

        self.graph = workflow.compile()

    async def chat(
        self,
        message: str,
        user_context: UserContext,
        conversation_history: list | None = None,
        callbacks: list | None = None,
    ) -> str:
        """Process a chat message and return the response."""
        messages = conversation_history or []
        messages.append(HumanMessage(content=message))

        state = AgentState(
            messages=messages,
            user_context=user_context,
            guardrail_blocked=False,
            guardrail_message=None,
        )

        run_config = {"callbacks": callbacks} if callbacks else {}
        result = await self.graph.ainvoke(state, run_config)

        # Get the last AI message
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage):
                return msg.content

        return "I'm sorry, I couldn't process your request."

    async def chat_stream(
        self,
        message: str,
        user_context: UserContext,
        conversation_history: list | None = None,
        callbacks: list | None = None,
    ):
        """Process a chat message and stream the response."""
        messages = conversation_history or []
        messages.append(HumanMessage(content=message))

        state = AgentState(
            messages=messages,
            user_context=user_context,
            guardrail_blocked=False,
            guardrail_message=None,
        )

        run_config = {"callbacks": callbacks} if callbacks else {}
        async for event in self.graph.astream_events(state, run_config, version="v2"):
            kind = event["event"]

            if kind == "on_chat_model_stream":
                # Only stream tokens from the main LLM node — not from any
                # guardrail classifier LLMs running inside input_guardrail
                if event.get("metadata", {}).get("langgraph_node") != "call_model":
                    continue
                chunk = event["data"]["chunk"]
                content = chunk.content
                # content is a list of blocks (ChatAnthropicVertex) or a plain str
                if isinstance(content, list):
                    text = "".join(
                        block["text"]
                        for block in content
                        if isinstance(block, dict) and block.get("type") == "text" and block.get("text")
                    )
                    if text:
                        yield text
                elif isinstance(content, str) and content:
                    yield content

            elif kind == "on_chain_end" and event.get("name") == "blocked_response":
                # Guardrail blocked the request — yield the blocked message directly
                # since no LLM was called, there are no on_chat_model_stream events
                output = event["data"].get("output", {})
                messages = output.get("messages", [])
                for msg in messages:
                    if hasattr(msg, "content") and msg.content:
                        yield msg.content


# Global agent instance
_agent: ShopAgent | None = None


async def get_agent() -> ShopAgent:
    """Get or create the global agent instance."""
    global _agent
    if _agent is None:
        _agent = ShopAgent()
        await _agent.initialize()
    return _agent


async def cleanup_agent():
    """Cleanup the global agent instance."""
    global _agent
    if _agent:
        await _agent.cleanup()
        _agent = None
