# Stage 1: Build virtual environment using uv
FROM python:3.12-slim AS builder

# Install uv from official binary
COPY --from=ghcr.io/astral-sh/uv:0.6.5 /uv /bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install dependencies first for better layer caching
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Copy source tree and contract
COPY src /app/src
COPY contract /app/contract
COPY pyproject.toml uv.lock README.md /app/

# Install the application into virtual environment
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# -------------------------------------------------------------
# Stage 2: Minimal runtime image
# -------------------------------------------------------------
FROM python:3.12-slim AS runner

# Security: create non-root application user
RUN groupadd --gid 10001 appgroup && \
    useradd --uid 10001 --gid appgroup --shell /bin/false --no-create-home appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appgroup /app/data

WORKDIR /app

# Copy virtual environment and source from builder
COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appgroup /app/src /app/src
COPY --from=builder --chown=appuser:appgroup /app/contract /app/contract

# Runtime environment settings
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

# Healthcheck testing HTTP 200 on /health using Python stdlib urllib
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import os, urllib.request; p=os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{p}/health', timeout=2)" || exit 1

# Non-root user
USER appuser

EXPOSE 8000

# Exec form via shell wrapper ensuring PORT expansion and clean SIGTERM handling
CMD ["sh", "-c", "exec uvicorn tabchat.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
