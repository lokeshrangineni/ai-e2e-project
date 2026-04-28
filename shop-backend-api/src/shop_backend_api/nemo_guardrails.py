"""NeMo Guardrails integration for role-based input policy enforcement.

How it works
------------
NeMo Guardrails enforces policies defined in Colang (.co) files.  Policies are
plain text, version-controlled, and completely independent of the main LLM's
system prompt — Claude Sonnet never sees them and cannot bypass them.

Flow per request
----------------
1. User message arrives.
2. NeMo uses Claude Haiku to classify the user's intent (one lightweight call).
3. The intent is matched deterministically against Colang flows (pure Python).
4a. If a flow fires  → NeMo returns the canned bot response from the .co file.
    We detect this by the unique "🛡️ Blocked by: NeMo Guardrails" prefix that
    every canned response starts with.  We return allowed=False.
4b. If no flow fires → NeMo calls Haiku to produce a response.
    That response does NOT start with the prefix, so we discard it and return
    allowed=True, letting the LangGraph agent handle the message normally.

Blocking detection
------------------
All canned bot responses in the .co files start with:
    "🛡️ Blocked by: NeMo Guardrails"
We check for this prefix to distinguish "rail fired" from "no rail fired".
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Config directory — shop-backend-api/guardrails_config/
# __file__ = shop-backend-api/src/shop_backend_api/nemo_guardrails.py
# .parent×3  = shop-backend-api/
_CONFIG_BASE = Path(__file__).parent.parent.parent / "guardrails_config"

_BLOCKED_PREFIX = "🛡️ Blocked by: NeMo Guardrails"


def _make_classifier_llm():
    """Build Claude Haiku via Vertex AI — used by NeMo for intent classification."""
    from .config import settings  # noqa: PLC0415
    from langchain_google_vertexai.model_garden import ChatAnthropicVertex  # noqa: PLC0415

    return ChatAnthropicVertex(
        model=settings.guardian_model_id,
        project=settings.anthropic_vertex_project_id,
        location=settings.guardian_region,
        temperature=0,
        max_tokens=128,
    )


async def check_input(user_message: str, role: str = "customer") -> Dict[str, Any]:
    """Run NeMo input rails against user_message for the given role.

    Returns
    -------
    dict with keys:
        allowed  (bool)   — True if message passed all input rails
        message  (str)    — canned refusal (from .co file) if blocked, None if allowed
        source   (str)    — "nemo"
    """
    from nemoguardrails import RailsConfig, LLMRails  # noqa: PLC0415

    config_dir = _CONFIG_BASE / role
    if not config_dir.exists():
        logger.warning(
            "[NeMo] No config for role '%s', falling back to 'customer'", role
        )
        config_dir = _CONFIG_BASE / "customer"

    try:
        config = RailsConfig.from_path(str(config_dir))
        llm = _make_classifier_llm()
        rails = LLMRails(config=config, llm=llm)

        response = await rails.generate_async(
            messages=[{"role": "user", "content": user_message}]
        )

        # generate_async returns a dict {"role": "assistant", "content": "..."}
        # when called with the messages format.
        if isinstance(response, dict):
            bot_reply = response.get("content", "").strip()
        elif isinstance(response, str):
            bot_reply = response.strip()
        else:
            bot_reply = ""

        print(f"[NeMo] role={role} input={user_message[:60]!r} → reply={bot_reply[:80]!r}")

        # If a Colang rail fired, the reply starts with our unique blocked prefix.
        # Any other reply means NeMo fell through to Haiku for normal generation
        # (no rail matched) — we discard that reply and let LangGraph handle it.
        if bot_reply.startswith(_BLOCKED_PREFIX):
            return {"allowed": False, "message": bot_reply, "source": "nemo"}

        return {"allowed": True, "message": None, "source": "nemo"}

    except Exception as exc:
        print(f"[NeMo] Error during input check — failing open: {exc}")
        return {"allowed": True, "message": None, "source": "nemo-error"}
