# Image layers are arranged by frequency of change from lowest to highest.
# Once Python or uv image changes all subsequent layers are rebuilt, therefore pin both.
FROM ghcr.io/astral-sh/uv:0.13.0@sha256:cdc6093146eb3ff6a40107b38f008b789e050e77ad87865e381d9917da55a168 AS uv
FROM python:3.13-slim@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f AS base

# Build this fork's dashboard with the same lockfile and installer as CI.
FROM node:22-bookworm-slim AS dashboard
COPY --from=oven/bun:1.2.1 /usr/local/bin/bun /usr/local/bin/bun
WORKDIR /build/dashboard
ENV ELECTRON_SKIP_BINARY_DOWNLOAD=1
COPY dashboard/package.json dashboard/bun.lock dashboard/bunfig.toml ./
COPY .github/scripts/install_dashboard_dependencies.sh /build/install_dashboard_dependencies.sh
RUN sed -i 's/\r$//' /build/install_dashboard_dependencies.sh \
    && GITHUB_ACTIONS=true bash /build/install_dashboard_dependencies.sh
COPY dashboard/ ./
RUN bun run build

# Only this separate service receives the Docker socket; it exposes no HTTP API.
FROM docker:28-cli AS updater
RUN apk add --no-cache python3
WORKDIR /opt/maibot
ENV PYTHONPATH=/opt/maibot
COPY src/common/self_update.py src/common/image_update.py src/common/update_errors.py src/common/instance_lock.py src/common/git_source.py src/common/paths.py src/common/version.py ./src/common/
COPY scripts/image_updater.py ./scripts/
ENTRYPOINT ["python3", "scripts/image_updater.py"]

# Install third-party runtime dependencies in a separate stage.
FROM base AS deps
COPY --from=uv /uv /bin/
WORKDIR /MaiMBot
COPY pyproject.toml ./
# Place uv cache in the cache mount.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project --link-mode=copy \
        --no-install-package maibot-dashboard \
        --no-install-package maibot-plugin-sdk \
        --no-install-package maim-message
# Store the Playwright package separately so it can be mounted when the runtime image installs.
RUN mkdir /playwright && cp -a .venv/lib/python3*/site-packages/playwright /playwright/

# Runtime image
FROM base AS runtime
COPY --from=uv /uv /uvx /bin/

# Working directory
WORKDIR /MaiMBot

ENV MAIBOT_LEGACY_0X_UPGRADE_CONFIRMED=1
ENV PATH="/MaiMBot/.venv/bin:${PATH}"
ENV MAIBOT_WEBUI_USE_LOCAL_DASHBOARD=1 MAIBOT_CONTAINER_IMAGE=1
ARG VERSION
ARG VCS_REF
LABEL org.opencontainers.image.source="https://github.com/Ariember/MaiBot" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Install system libraries required by Playwright Chromium. The browser binary
# itself is downloaded lazily into the configured data directory at runtime.
# This layer is rebuilt only when the Playwright version changes.
RUN --mount=type=bind,from=deps,source=/playwright,target=/tmp/playwright \
    PYTHONPATH=/tmp/playwright python -m playwright install-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY --from=deps /MaiMBot/.venv /MaiMBot/.venv

# Reuse the lock generated in the dependency stage for this build.
COPY --from=deps /MaiMBot/uv.lock ./uv.lock
# The dashboard is built above; only the Python runtime dependencies are installed here.
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project --no-install-package maibot-dashboard --link-mode=copy

# Copy project source
COPY . .
COPY --from=dashboard /build/dashboard/dist ./dashboard/dist

RUN sed -i 's/\r$//' docker-entrypoint.sh && chmod +x docker-entrypoint.sh

EXPOSE 8000 8001

HEALTHCHECK --interval=10s --timeout=5s --start-period=120s --retries=12 \
    CMD ["/MaiMBot/.venv/bin/python", "-m", "scripts.docker_healthcheck"]

ENTRYPOINT [ "./docker-entrypoint.sh" ]
