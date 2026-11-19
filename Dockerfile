# =========================
# Stage 1: Build dependencies
# =========================
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /tai_pr_api

# Use cache mounts to speed up builds and compile bytecode for performance
ENV UV_COMPILE_BYTECODE=1
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# =========================
# Stage 2: Test
# =========================

FROM builder AS test

RUN groupadd -r tai_runner && \
    useradd -r -g tai_runner -m tai_runner

WORKDIR /tai_pr_api

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project

COPY --chown=tai_runner:tai_runner . .

ENV PATH="/tai_pr_api/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/tai_runner \
    UV_NO_CACHE=1

USER tai_runner
CMD ["uv", "run", "pytest", "-v"]

# =========================
# Stage 3: Final image
# =========================
FROM python:3.13-slim AS runtime

# 1. Install tini and setup user in one step
RUN apt-get update && \
    apt-get install -y --no-install-recommends tini && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd -r tai_runner && \
    useradd -r -g tai_runner tai_runner

WORKDIR /tai_pr_api

# 2. Fix Bloat: Copy the venv AND set ownership in the same step
COPY --from=builder --chown=tai_runner:tai_runner /tai_pr_api/.venv /tai_pr_api/.venv

# 3. Setup environment
ENV PATH="/tai_pr_api/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/tai_runner

# 4. Create config dir and copy app code with correct ownership
RUN mkdir -p /home/tai_runner/.config && chown -R tai_runner:tai_runner /home/tai_runner
COPY --chown=tai_runner:tai_runner app ./app

USER tai_runner
EXPOSE 8080

ENTRYPOINT ["tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]