# Production Deployment Guide: Containerization & Orchestration

This guide provides instructions for deploying the **MCP RAG Agent** system using multi-stage Docker builds and Docker Compose. It enables running the complete production stack on a clean machine with zero local Python or database installation requirements.

---

## 1. System Architecture & Container Topology

The containerized stack comprises four microservices coordinated via Docker Compose:

```
                          ┌────────────────────────────────┐
                          │         Web Browser            │
                          │   (http://localhost:3000)      │
                          └───────────────┬────────────────┘
                                          │
                         Port 3000 (HTTP) │
                                          ▼
                         ┌─────────────────────────────────┐
                         │       mcp-rag-frontend          │
                         │    (Nginx Reverse Proxy & UI)   │
                         └────────┬───────────────┬────────┘
                                  │               │
                     Static Assets│               │ Proxy /api/ to Port 8000
                     (index.html) │               │
                                  ▼               ▼
                        ┌──────────────────────────────────┐
                        │          mcp-rag-api             │
                        │    (FastAPI + LangGraph Agent)   │
                        └─────────┬──────────────┬─────────┘
                                  │              │
                   MongoDB Port   │              │ MCP SSE Port 8001
                   27017          │              │ (Optional Standalone)
                                  ▼              ▼
           ┌────────────────────────────┐  ┌────────────────────────────┐
           │      mcp-rag-mongodb       │  │     mcp-rag-mcp-server     │
           │  (MongoDB 7.0 Document &   │  │   (FastMCP SSE Service)    │
           │       Vector Store)        │  │     [Profile: mcp]         │
           └────────────────────────────┘  └─────────────┬──────────────┘
                                                         │
                                                         ▼
                                                MongoDB Port 27017
```

### Services Summary

| Service | Container Name | Base Image | Default Port | Non-Root User | Health Check Endpoint | Role |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`api`** | `mcp-rag-api` | `python:3.11-slim` | `8000` | `appuser` (UID 10001) | `GET /api/v1/health` | FastAPI REST API, LangGraph agent execution, conversation memory |
| **`frontend`** | `mcp-rag-frontend` | `nginx:alpine` | `3000` | `nginx` (UID 101) | `GET /healthz` | Static web UI host and API reverse proxy |
| **`mongodb`** | `mcp-rag-mongodb` | `mongo:7.0` | `27017` | `mongodb` (UID 999) | `mongosh db.adminCommand("ping")` | Local document database, vector search, and session checkpointer |
| **`mcp-server`** | `mcp-rag-mcp-server` | `python:3.11-slim` | `8001` | `appuser` (UID 10001) | `GET /sse` | Standalone FastMCP SSE server (optional profile: `mcp`) |

---

## 2. Security & Production Hardening Features

1. **Multi-Stage Build**:
   - `builder` stage: Compiles wheels and creates an isolated virtual environment (`/opt/venv`).
   - `runtime` stages: Minimal Debian slim (`api`, `mcp-server`) and Alpine (`frontend`) containing zero build compilers, debuggers, or package caches.
2. **Non-Root Execution**:
   - The Python API runs under unprivileged user `appuser` (`UID 10001`, `GID 10001`).
   - The Nginx frontend runs under unprivileged user `nginx` (`UID 101`), with temp paths redirecting to `/tmp/`.
3. **No Secrets Inside Image**:
   - `.dockerignore` blocks `.env`, git history, and secrets from entering build context.
   - All credentials (`OPENAI_API_KEY`, MongoDB URLs, etc.) are injected strictly at runtime via environment variables.
4. **Configurable Ports**:
   - Every service port is parameterized via environment variables (`API_PORT`, `FRONTEND_PORT`, `MCP_SERVER_PORT`, `MONGODB_PORT`).
5. **Graceful Shutdown**:
   - Python containers listen for `SIGTERM` with `timeout-graceful-shutdown 15`.
   - Nginx uses `STOPSIGNAL SIGQUIT` for connection draining.
   - Compose specifies `stop_grace_period` (10s to 20s) to allow ongoing HTTP requests to complete.
6. **Built-in Health Checks**:
   - Every container includes Docker-level health checks with automatic startup waiting and dependency gating (`condition: service_healthy`).

---

## 3. Clean Machine Quickstart

### Prerequisites
- Docker Engine 24+ or Docker Desktop
- Docker Compose v2.20+
- Internet access for image pulls and dependency resolution

### Step 1: Clone the Repository
```bash
git clone <repository-url>
cd mcp-rag-agent
```

### Step 2: Configure Environment Variables
Copy the template configuration file:
```bash
cp .env.example .env
```

Open `.env` and configure your credentials:
```ini
# OpenAI Key (Required for inference)
OPENAI_API_KEY=sk-your-actual-openai-key-here

# Optional: MongoDB Atlas Cluster URI
# (If omitted or left as mongodb://mongodb:27017, the local MongoDB container is used)
MONGODB_ATLAS_CLUSTER_URI=mongodb://mongodb:27017
MONGODB_ATLAS_DB_NAME=mcp_rag_agent_db
```

### Step 3: Build the Images
Build all production images with multi-stage caching:
```bash
docker compose build
```

### Step 4: Launch the Standard Application Stack
Start MongoDB, API, and Frontend services in detached mode:
```bash
docker compose up -d
```

Docker Compose will automatically:
1. Start `mcp-rag-mongodb` and wait until it passes health check.
2. Start `mcp-rag-api` and wait until it passes `/api/v1/health`.
3. Start `mcp-rag-frontend` connected to the backend.

### Step 5: (Optional) Launch with Standalone MCP Server
To also run the optional standalone FastMCP SSE service on port 8001:
```bash
docker compose --profile mcp up -d
```

---

## 4. Verification & Testing

Run the following commands to verify all subsystems:

### 1. Check Container Health Status
```bash
docker compose ps
```
**Expected Output:**
```
NAME               STATUS                    PORTS
mcp-rag-api        Up (healthy)              0.0.0.0:8000->8000/tcp
mcp-rag-frontend   Up (healthy)              0.0.0.0:3000->3000/tcp
mcp-rag-mongodb    Up (healthy)              0.0.0.0:27017->27017/tcp
```

### 2. Verify API Liveness Probe
```bash
curl -i http://localhost:8000/api/v1/health
```
**Expected Output:** `HTTP/1.1 200 OK`
```json
{
  "status": "healthy",
  "app_name": "MCP RAG Agent",
  "app_version": "0.1.0"
}
```

### 3. Verify Readiness Probe & MongoDB Connectivity
```bash
curl -i http://localhost:8000/api/v1/ready
```
**Expected Output:** `HTTP/1.1 200 OK`
```json
{
  "status": "ready",
  "checks": {
    "database": "connected",
    "model": "configured",
    "session_memory": "active"
  }
}
```

### 4. Verify Frontend Web UI & Reverse Proxy
- **Frontend Health**:
  ```bash
  curl -i http://localhost:3000/healthz
  ```
- **Proxied API Health**:
  ```bash
  curl -i http://localhost:3000/api/v1/health
  ```
- **Browser Web Interface**:
  Open [http://localhost:3000](http://localhost:3000) in your web browser.

### 5. Verify Conversational Chat Request
Execute an end-to-end RAG chat request through the container API:
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the policy on annual leave in the UK?"}'
```
**Expected Output:** `HTTP/1.1 200 OK`
```json
{
  "answer": "...",
  "citations": ["..."],
  "sources": [...],
  "thread_id": "thread_...",
  "request_id": "req_...",
  "metadata": {
    "retrieval_latency_ms": 12.4,
    "total_latency_ms": 420.5,
    "model_name": "gpt-4.1",
    "decision": "supported_by_evidence"
  }
}
```

### 6. Verify Optional MCP Server Functionality
When running with `--profile mcp`:
```bash
curl -I http://localhost:8001/sse
```
**Expected Output:**
```http
HTTP/1.1 200 OK
content-type: text/event-stream; charset=utf-8
```

---

## 5. Operations & Maintenance

### Viewing Container Logs
- Follow all logs:
  ```bash
  docker compose logs -f
  ```
- Follow specific service logs:
  ```bash
  docker compose logs -f api
  docker compose logs -f frontend
  docker compose logs -f mcp-server
  ```

### Stopping the Stack
Perform a graceful shutdown of all services:
```bash
docker compose down
```
To stop the stack and include optional profiles:
```bash
docker compose --profile mcp down
```

### Resetting Persistent Data
To remove local MongoDB database volumes:
```bash
docker compose down -v
```

### Rebuilding Images After Code Changes
```bash
docker compose build --no-cache
docker compose up -d
```
