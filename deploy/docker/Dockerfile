# ==============================================================================
# SIA Backend — Production Multi-Stage Build
# Targets: linux/amd64, linux/arm64
# ==============================================================================

# ---------- Stage 1: Python dependency builder ----------
FROM python:3.12-slim AS py-builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libffi-dev libssl-dev \
    libcairo2-dev libpango1.0-dev libgdk-pixbuf2.0-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

# ---------- Stage 2: Runtime ----------
FROM python:3.12-slim AS runtime

LABEL maintainer="alex <unix_sec@163.com>" \
      org.opencontainers.image.title="sia-backend" \
      org.opencontainers.image.description="Security Intelligence Agent — API & Consumer" \
      org.opencontainers.image.version="0.2.0" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.source="https://github.com/unixsec/Security-Intelligence-agent"

# Runtime system libs (WeasyPrint, etc.)
# Explicit UID/GID 1000 matches K8s runAsUser. /home/sia is needed at runtime
# for cache dirs when readOnlyRootFilesystem=true (mounted as emptyDir volumes).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
    curl tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r -g 1000 sia \
    && useradd -r -u 1000 -g sia -d /home/sia -m -s /sbin/nologin sia

COPY --from=py-builder /install /usr/local

WORKDIR /app

# Application code
COPY src/    src/
COPY config/ config/
COPY prompts/ prompts/
COPY workflows/ workflows/
COPY migrations/ migrations/
COPY scripts/ops/ scripts/ops/
COPY pyproject.toml .

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    SIA_ENV=production

RUN chown -R sia:sia /app /home/sia

USER sia

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:8080/api/v1/health || exit 1

ENTRYPOINT ["tini", "--"]
CMD ["uvicorn", "sia.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4", "--loop", "uvloop", "--http", "httptools"]
