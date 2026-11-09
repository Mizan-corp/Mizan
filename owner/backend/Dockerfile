# syntax=docker/dockerfile:1
# Mizan owner API. Build from the repo root so the shared kernel is available:
#   docker build -f owner/backend/Dockerfile .

# ─── Builder: install the shared kernel and its wheels (compile deps live only here) ──
FROM python:3.12-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
      gcc g++ libpq-dev libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY shared/backend /build/shared
RUN pip install --prefix=/install --no-cache-dir /build/shared

# ─── Runtime: only what the service needs at run time (no gcc/toolchain) ───
FROM python:3.12-slim-bookworm

WORKDIR /app

# /shared holds the kernel source; it shadows the installed copy so a mounted
# volume (docker compose dev) picks up edits without rebuilding.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app:/shared

RUN apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
      libcairo2 libgdk-pixbuf-2.0-0 shared-mime-info \
      fonts-noto-core && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /install/ /usr/local/

COPY shared/backend/app /shared/app
COPY owner/backend /app

RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
