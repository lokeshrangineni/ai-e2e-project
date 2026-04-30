# Build stage: install dependencies for both backend and mcp-server
FROM --platform=linux/amd64 python:3.11-slim AS builder

WORKDIR /build

# g++ is needed to compile annoy (a nemoguardrails dependency) from source.
# It lives only in the builder stage — the final runtime image does not include it.
RUN apt-get update && apt-get install -y --no-install-recommends g++ && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy dependency files first for layer caching
COPY shop-backend-api/pyproject.toml shop-backend-api/
COPY mcp-server/pyproject.toml mcp-server/

# Sync backend dependencies (no dev extras)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --directory shop-backend-api --no-dev

# Sync mcp-server dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --directory mcp-server --no-dev

# Copy full source after deps are cached
COPY shop-backend-api/ shop-backend-api/
COPY mcp-server/ mcp-server/
COPY data/ data/

# Install backend package into its venv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --directory shop-backend-api --no-dev


# Runtime stage
FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /app

# Install uv in the runtime image (needed to launch mcp-server subprocess via `uv run`)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy everything from the build stage
COPY --from=builder /build/shop-backend-api /app/shop-backend-api
COPY --from=builder /build/mcp-server /app/mcp-server
COPY --from=builder /build/data /app/data

# OpenShift runs pods as arbitrary non-root UIDs — ensure the app directory is group-writable
RUN chmod -R g=u /app

# Application environment defaults (can be overridden via ConfigMap/Secret)
ENV API_HOST=0.0.0.0 \
    API_PORT=8000 \
    DEBUG=false \
    MCP_SERVER_DIR=/app/mcp-server \
    SHOP_DATA_DIR=/app/data \
    MCP_SERVER_COMMAND=uv \
    MCP_SERVER_NAME=shop_mcp_server.server \
    UV_NO_CACHE=1 \
    UV_CACHE_DIR=/tmp/uv-cache

EXPOSE 8000

# Health check (used by OpenShift readiness probes as a fallback)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

WORKDIR /app/shop-backend-api

CMD ["uv", "run", "shop-backend-api"]
