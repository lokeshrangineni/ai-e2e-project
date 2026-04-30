"""Configuration for the backend API."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # Claude via Vertex AI (uses your existing env vars)
    anthropic_vertex_project_id: str | None = None  # ANTHROPIC_VERTEX_PROJECT_ID
    cloud_ml_region: str = "global"  # CLOUD_ML_REGION
    model_id: str = "claude-sonnet-4@20250514"

    # Alias for compatibility
    @property
    def vertex_project(self) -> str | None:
        return self.anthropic_vertex_project_id

    @property
    def vertex_location(self) -> str:
        return self.cloud_ml_region

    # Claude via Anthropic API (fallback)
    anthropic_api_key: str | None = None

    # MCP Server
    mcp_server_command: str = "uv"
    mcp_server_name: str = "shop_mcp_server.server"
    mcp_server_dir: str = str(Path(__file__).parent.parent.parent.parent / "mcp-server")
    shop_data_dir: str = str(Path(__file__).parent.parent.parent.parent / "data")

    # Langfuse
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "http://localhost:3000"
    langfuse_enabled: bool = False

    # Layer 1 — Regex guardrails (sync, zero latency)
    regex_guardrails_enabled: bool = True

    # Layer 2 — NeMo Guardrails (Colang policy files, deterministic enforcement)
    # Uses Claude Haiku via Vertex AI for intent classification only.
    nemo_guardrails_enabled: bool = False
    guardian_model_id: str = "claude-haiku-4-5@20251001"
    guardian_region: str = "us-east5"  # Haiku is regional, not on 'global' endpoint

    # CORS — comma-separated list of allowed origins (use "*" for local dev only)
    cors_origins: str = "*"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # App version (for tracing)
    app_version: str = "0.1.0"
    guardrails_version: str = "1.0.0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # silently ignore unrecognised env vars (e.g. old keys after refactors)


settings = Settings()
