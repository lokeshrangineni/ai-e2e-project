"""Langfuse observability integration (Langfuse SDK v4+).

Langfuse v4 uses an OpenTelemetry-based architecture.  Key changes from v3:
  - CallbackHandler no longer accepts auth credentials or per-request fields.
  - Auth (public_key / secret_key / host) is configured on the global client.
  - Per-trace metadata (user_id, session_id, tags) is applied after the run via
    the client using the trace_id exposed by ``handler.last_trace_id``.

Usage
-----
    handler = get_langfuse_handler(user_id=..., session_id=..., role=...)
    callbacks = [handler] if handler else []
    await graph.astream_events(state, {"callbacks": callbacks}, version="v2")
    flush_langfuse_handler(handler, user_id=..., session_id=..., role=...)

The handler (and flush helper) are None-safe — callers never need their own
``if langfuse_enabled`` guards.
"""

from __future__ import annotations

import logging

from .config import settings

logger = logging.getLogger(__name__)

_langfuse_client = None


def _ensure_client():
    """Initialise (once) the global Langfuse client from application settings.

    Langfuse v4 uses a process-level singleton.  Calling ``Langfuse(...)``
    multiple times is safe but wasteful; we cache the first instance.
    """
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client

    from langfuse import Langfuse  # noqa: PLC0415

    _langfuse_client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    logger.info("[Langfuse] Global client initialised (host=%s)", settings.langfuse_host)
    return _langfuse_client


def get_langfuse_handler(
    user_id: str,
    session_id: str,
    role: str,
    trace_name: str = "shop-chat",
):
    """Return a Langfuse CallbackHandler, or None if observability is off.

    Parameters
    ----------
    user_id:     Identifies the end user in the Langfuse dashboard.
    session_id:  Groups conversation turns into one session.
    role:        RBAC role (customer / operator / admin).
    trace_name:  Label shown in the Langfuse trace list.
    """
    if not settings.langfuse_enabled:
        return None

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.warning(
            "[Langfuse] LANGFUSE_ENABLED=true but keys are missing — tracing skipped."
        )
        return None

    try:
        _ensure_client()

        from langfuse.langchain import CallbackHandler  # noqa: PLC0415

        handler = CallbackHandler()
        # Stash per-request metadata so flush_langfuse_handler can apply it after
        # the LangGraph run completes and handler.last_trace_id is populated.
        handler._lf_meta = {  # type: ignore[attr-defined]
            "user_id": user_id,
            "session_id": session_id,
            "role": role,
            "trace_name": trace_name,
        }
        logger.info("[Langfuse] CallbackHandler created (user=%s session=%s)", user_id, session_id)
        return handler

    except Exception:
        logger.exception("[Langfuse] Failed to create CallbackHandler — tracing skipped.")
        return None


def flush_langfuse_handler(handler) -> None:
    """Flush buffered spans and log the trace_id for debugging.

    Call this *after* the LangGraph run completes so that ``handler.last_trace_id``
    is available.  Safe to call with ``handler=None``.

    Note: Per-trace metadata (user_id, session_id) is set at handler creation time
    via ``_lf_meta`` and is applied through the OpenTelemetry span attributes during
    the run — see ``get_langfuse_handler``.
    """
    if handler is None:
        return

    trace_id = getattr(handler, "last_trace_id", None)
    logger.info("[Langfuse] Run complete — trace_id=%s", trace_id)

    try:
        client = _ensure_client()
        client.flush()
        logger.info("[Langfuse] Spans flushed successfully")
    except Exception:
        logger.exception("[Langfuse] Failed to flush spans.")
