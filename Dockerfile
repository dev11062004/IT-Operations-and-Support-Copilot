# syntax=docker/dockerfile:1

# ==============================================================================
# Stage 1: Build virtual environment with all Python dependencies
# ==============================================================================
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Create virtualenv and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy package source and install in non-editable mode
COPY setup.py README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps .

# ==============================================================================
# Stage 2: Production Frontend (Static SPA & Nginx Reverse Proxy)
# ==============================================================================
FROM nginx:alpine AS frontend

# Add unprivileged configuration and writable directories for non-root nginx user
RUN mkdir -p /var/cache/nginx /var/run /var/log/nginx /tmp/client_temp /tmp/proxy_temp /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp \
    && chown -R nginx:nginx /var/cache/nginx /var/run /var/log/nginx /tmp/*_temp /etc/nginx /usr/share/nginx/html

COPY docker/nginx/nginx.conf /etc/nginx/nginx.conf
COPY src/mcp_rag_agent/api/static/ /usr/share/nginx/html/

USER nginx

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:3000/healthz || exit 1

STOPSIGNAL SIGQUIT

CMD ["nginx", "-g", "daemon off;"]

# ==============================================================================
# Stage 3: Production API & MCP Server Runtime (Default target)
# ==============================================================================
FROM python:3.11-slim AS api

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    API_HOST="0.0.0.0" \
    API_PORT="8000"

# Install curl for reliable container health probes
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root user and group
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /sbin/nologin -d /app appuser

WORKDIR /app

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code and source documents
COPY src/ /app/src/
COPY data/ /app/data/
COPY setup.py README.md /app/

# Set non-root ownership
RUN chown -R appuser:appgroup /app /opt/venv

# Run as non-root user
USER appuser

EXPOSE 8000

# Health check probe against API health endpoint
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${API_PORT:-8000}/api/v1/health || exit 1

# Graceful shutdown signal
STOPSIGNAL SIGTERM

# Production startup command with uvicorn factory and graceful shutdown timeout
CMD ["uvicorn", "mcp_rag_agent.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "15"]
