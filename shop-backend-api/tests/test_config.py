"""Layer 1 tests for configuration loading — no LLM calls."""

import os
import pytest


class TestSettingsDefaults:
    """Settings should have sensible defaults without .env file."""

    def test_default_api_host(self):
        from shop_backend_api.config import Settings
        s = Settings(
            _env_file=None,
            anthropic_vertex_project_id=None,
        )
        assert s.api_host == "0.0.0.0"
        assert s.api_port == 8000

    def test_default_model(self):
        from shop_backend_api.config import Settings
        s = Settings(_env_file=None, anthropic_vertex_project_id=None)
        assert "claude-sonnet" in s.model_id

    def test_default_guardrails_enabled(self):
        from shop_backend_api.config import Settings
        s = Settings(_env_file=None, anthropic_vertex_project_id=None)
        assert s.regex_guardrails_enabled is True
        assert s.nemo_guardrails_enabled is False

    def test_default_langfuse_disabled(self):
        from shop_backend_api.config import Settings
        s = Settings(_env_file=None, anthropic_vertex_project_id=None)
        assert s.langfuse_enabled is False

    def test_guardian_region_default(self):
        from shop_backend_api.config import Settings
        s = Settings(_env_file=None, anthropic_vertex_project_id=None)
        assert s.guardian_region == "us-east5"

    def test_extra_env_vars_ignored(self):
        """Old/unknown env vars should not cause ValidationError."""
        from shop_backend_api.config import Settings
        s = Settings(
            _env_file=None,
            anthropic_vertex_project_id=None,
            SOME_UNKNOWN_VAR="should_be_ignored",  # type: ignore
        )
        assert s.api_host == "0.0.0.0"


class TestSettingsFromEnv:
    """Settings should correctly parse environment variables."""

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("API_PORT", "9999")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("REGEX_GUARDRAILS_ENABLED", "false")

        from shop_backend_api.config import Settings
        s = Settings(_env_file=None, anthropic_vertex_project_id=None)
        assert s.api_port == 9999
        assert s.debug is True
        assert s.regex_guardrails_enabled is False

    def test_vertex_project_from_env(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_VERTEX_PROJECT_ID", "my-gcp-project")

        from shop_backend_api.config import Settings
        s = Settings(_env_file=None)
        assert s.anthropic_vertex_project_id == "my-gcp-project"
        assert s.vertex_project == "my-gcp-project"
