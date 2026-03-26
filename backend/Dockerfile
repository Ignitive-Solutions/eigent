# Use a Python image with uv pre-installed (matches pyproject.toml requires-python >=3.11,<3.12)
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

# Install system dependencies (git for git-based deps, build tools for native packages)
RUN apt-get update -o Acquire::Retries=3 && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Disable bytecode compilation during build to avoid EMFILE on low nofile limits
ENV UV_COMPILE_BYTECODE=0

# Copy from cache instead of linking (required in Docker layered FS)
ENV UV_LINK_MODE=copy

# Copy dependency files first for optimal layer caching
COPY pyproject.toml uv.lock ./

# Install project dependencies (no dev extras)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev

# Copy the rest of the source code
COPY . /app

# Install the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# Place venv executables at the front of PATH
ENV PATH="/app/.venv/bin:$PATH"

# Set PYTHONPATH so `main.py` imports resolve correctly
ENV PYTHONPATH=/app

EXPOSE 8002

# Run the FastAPI app via uvicorn, binding to all interfaces
CMD ["uvicorn", "main:api", "--host", "0.0.0.0", "--port", "8002"]
