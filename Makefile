# ShopChat — Developer Commands
# Usage: make <target>

.PHONY: help test test-backend test-mcp lint-ui eval eval-category eval-verbose start-backend

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─────────────────────────────────────────────────
# Layer 1: Unit Tests (no LLM, fast, CI-friendly)
# ─────────────────────────────────────────────────

test: test-backend test-mcp ## Run all Layer 1 unit tests

test-backend: ## Run backend API unit tests (guardrails, config)
	cd shop-backend-api && uv run pytest tests/ -v

test-mcp: ## Run MCP server unit tests (RBAC, data)
	cd mcp-server && uv run pytest tests/ -v

lint-ui: ## Lint and type-check the UI
	cd shop-ui && npm run lint && npm run build

# ─────────────────────────────────────────────────
# Layer 2: Golden Set Evals (real LLM + Langfuse)
# ─────────────────────────────────────────────────

eval: ## Run full golden set eval (47 cases) — results stored in Langfuse
	@echo "Running golden set eval against Langfuse..."
	cd eval && PYTHONUNBUFFERED=1 ../shop-backend-api/.venv/bin/python run_eval.py --tag "$(or $(TAG),run-$$(date +%Y%m%d-%H%M%S))"

eval-tag: ## Run eval with a specific tag: make eval-tag TAG=after-upgrade
	cd eval && PYTHONUNBUFFERED=1 ../shop-backend-api/.venv/bin/python run_eval.py --tag "$(TAG)" --verbose

eval-category: ## Run eval for one category: make eval-category CAT=guardrail_injection
	cd eval && PYTHONUNBUFFERED=1 ../shop-backend-api/.venv/bin/python run_eval.py --tag "$(or $(TAG),$(CAT)-$$(date +%Y%m%d))" --category "$(CAT)" --verbose

eval-verbose: ## Run full eval with verbose failure output
	cd eval && PYTHONUNBUFFERED=1 ../shop-backend-api/.venv/bin/python run_eval.py --tag "$(or $(TAG),verbose-$$(date +%Y%m%d-%H%M%S))" --verbose

# ─────────────────────────────────────────────────
# Application
# ─────────────────────────────────────────────────

start-backend: ## Start the backend API server
	cd shop-backend-api && uv run shop-backend-api

start-ui: ## Start the UI dev server
	cd shop-ui && npm run dev
