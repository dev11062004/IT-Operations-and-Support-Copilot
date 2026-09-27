# Production Observability & Debugging Guide

This guide describes how to monitor, trace, and debug requests across the entire execution lifecycle of the MCP RAG Agent:
$$\text{Request} \longrightarrow \text{Agent} \longrightarrow \text{Tool Call} \longrightarrow \text{Retrieval} \longrightarrow \text{MongoDB} \longrightarrow \text{LLM} \longrightarrow \text{Response}$$

---

## 1. Correlation Identifiers & Request Context

Every request flowing through the system is tagged with correlation identifiers managed via Python's thread-safe and async-safe `contextvars`:

- **`request_id`**: Globally unique UUID generated per request (or provided by the API gateway/client) that correlates every downstream log, tool call, database query, and model invocation.
- **`thread_id`**: Conversation session identifier ensuring persistent multi-turn memory isolation.
- **`user_id`**: Optional user identifier for access control and multi-tenant tracking.

### Context Propagation
The context is set at the root of `RAGAgentRunner.run()`:
```python
with set_request_context(request_id=req_id, thread_id=th_id, user_id=user_id, tracer=tracer):
    # Downstream components (Retriever, MongoDB, Tool, OutputGuard)
    # automatically access get_request_id() and get_thread_id()
```

---

## 2. Structured Application Logging

Logging is centralized in `src/mcp_rag_agent/core/log_setup.py`.

### A. Format Modes
Set the format via environment variable `LOG_FORMAT`:
- **Human-Readable Text Format (`LOG_FORMAT=text`, default)**:
  ```
  2026-09-23 09:40:12,123 INFO     [req:7f3a8b21-4d10 th:th_a9b1c2d3] [RAGAgentRunner] [AGENT:RUN] Request: 7f3a8b21-4d10 | Query: 'What is the UK annual leave entitlement?'
  2026-09-23 09:40:12,245 INFO     [req:7f3a8b21-4d10 th:th_a9b1c2d3] [Retriever] [TOOL:search_policy_documents] Status: success, Found: 3 chunks, Latency: 122.00ms
  2026-09-23 09:40:13,450 INFO     [req:7f3a8b21-4d10 th:th_a9b1c2d3] [RAGAgentRunner] [AGENT:DONE] Request: 7f3a8b21-4d10 | Total: 1327.0ms | Tokens: 412 | Cost: $0.00031
  ```
- **Structured JSON Format (`LOG_FORMAT=json`)**:
  ```json
  {
    "timestamp": "2026-09-23T04:10:12.123456+00:00",
    "level": "INFO",
    "logger": "RAGAgentRunner",
    "message": "[AGENT:RUN] Request: 7f3a8b21-4d10 | Query: 'What is the UK annual leave entitlement?'",
    "request_id": "7f3a8b21-4d10",
    "thread_id": "th_a9b1c2d3",
    "service": "mcp-rag-agent",
    "module": "runner",
    "lineno": 164
  }
  ```

### B. Secret Redaction Guarantees
Logs are automatically filtered through `MaskingFilter` at the handler level:
- OpenAI API Keys: `sk-[a-zA-Z0-9_-]{20,}` $\longrightarrow$ `sk-***REDACTED***`
- MongoDB URIs: `mongodb(+srv)://<credentials>@` $\longrightarrow$ `mongodb://***REDACTED***@`
- Bearer Tokens: `Bearer [token]` $\longrightarrow$ `Bearer ***REDACTED***`
- Passwords: `password='...'` $\longrightarrow$ `password='***REDACTED***'`
- Email Addresses: `user@domain.com` $\longrightarrow$ `***@REDACTED.COM`

---

## 3. The 7 Standardized Error Categories

All system errors, exceptions, and guardrail decisions are mapped to 7 standardized error codes:

| Error Category | Typical Trigger | Recoverable? | Recommended Action |
|:---|:---|:---|:---|
| **`RETRIEVAL_ERROR`** | Tool execution exception, missing Atlas vector index, embedding failure | Yes/No | Check MongoDB cluster status, embedding API quota, or document collection state. |
| **`MODEL_ERROR`** | OpenAI API exception, rate limits, context window overflow | No | Check OpenAI API status, inspect token usage, check API key validity. |
| **`MCP_ERROR`** | FastMCP stdio process crash, JSON-RPC connection dropped | No | Check MCP server process, inspect stderr logs in `mcp_server/server.py`. |
| **`DATABASE_ERROR`** | MongoDB connection timeout, network partition, replica set election | No | Verify network connectivity, MongoDB connection string, and cluster health. |
| **`VALIDATION_ERROR`**| Empty query, malformed JSON payload, invalid search parameters | No | Reject bad user input early at client or API gateway level. |
| **`GUARDRAIL_BLOCK`** | Prompt injection attempt, out-of-scope query, low confidence (<0.015) | Yes | Expected behavior for adversarial or out-of-domain queries. Verify guardrail rules. |
| **`TIMEOUT`** | Agent execution or database operation exceeded maximum allowed duration | No | Optimize search `numCandidates` or increase `TIMEOUT` threshold. |

---

## 4. End-to-End Tracing (`ObservabilityTracer`)

Every `AgentResponse` exposes complete trace metadata in `response.metadata`:

```json
{
  "request_id": "7f3a8b21-4d10-4f9e-a89b-9876543210ab",
  "thread_id": "thread_abc123",
  "model_name": "gpt-4.1",
  "retrieval_latency_ms": 142.5,
  "model_latency_ms": 1120.0,
  "total_latency_ms": 1285.2,
  "token_usage": {
    "prompt_tokens": 340,
    "completion_tokens": 72,
    "total_tokens": 412,
    "estimated_cost_usd": 0.00031
  },
  "errors": [],
  "retrieved_document_ids": ["doc_3_annual_leave"],
  "citations": ["3 - Annual Leave.txt"],
  "decision": "supported_by_evidence",
  "trace": {
    "status": "completed",
    "spans": [
      {"name": "tool:search_policy_documents", "duration_ms": 142.5, "status": "success"},
      {"name": "retrieval:pipeline", "duration_ms": 140.2, "status": "success"},
      {"name": "mongodb:vector_search", "duration_ms": 45.1, "status": "success"},
      {"name": "mongodb:text_search", "duration_ms": 32.8, "status": "success"},
      {"name": "llm:gpt-4.1", "duration_ms": 1120.0, "status": "success"}
    ]
  }
}
```

---

## 5. LangSmith Integration

If LangSmith is configured in your `.env`:
```bash
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=your_api_key
LANGSMITH_PROJECT=mcp-rag-agent
```
The agent automatically:
1. Configures LangChain environment variables via `configure_langsmith_environment()`.
2. Attaches `request_id`, `thread_id`, and `user_id` as run metadata.
3. Tags runs with `["production", "mcp-rag-agent"]`.
4. Visualizes full tool-call trees, token consumption, and intermediate prompt messages directly in the LangSmith dashboard.

---

## 6. How a Developer Can Debug a Failed Request

### Step 1: Locate the Request ID
Every API response and error message includes the `request_id`.
Example:
```
[req: 9a8c7b6d-4e5f-4a3b-8c2d-1e0f9a8b7c6d]
```

### Step 2: Query Structured Logs
Using standard Linux utilities or cloud log search:

#### Find all logs for the request:
```bash
grep "req:9a8c7b6d" logs/agent.log
```

#### Query JSON structured logs with `jq`:
```bash
cat logs/agent.json | jq 'select(.request_id == "9a8c7b6d-4e5f-4a3b-8c2d-1e0f9a8b7c6d")'
```

#### Filter by error category:
```bash
cat logs/agent.json | jq 'select(.error_category == "DATABASE_ERROR")'
```

---

### Step 3: Triage Specific Failure Scenarios

#### Scenario A: Grounded Refusal ("I couldn't find this information...")
1. Search logs for `[GUARDRAIL:RETRIEVAL]` or `[GUARDRAIL:GROUNDING]`.
2. Check `trace.spans` for `tool:search_policy_documents`:
   - If `chunks_count == 0`: Query terms did not match indexed documents. Inspect `retrieval_query` to see if synonym expansion or chunking tuning is required.
   - If `status == "low_confidence"`: The top RRF score was $< 0.015$, triggering the confidence guardrail to prevent hallucination.
   - If `grounding_score < 0.20`: The model attempted to generate facts not present in the retrieved passages.

#### Scenario B: High Latency Spikes (> 2.5s)
1. Inspect the latency breakdown in the response metadata:
   - `retrieval_latency_ms`: Did vector search or text search slow down?
   - `model_latency_ms`: Did OpenAI inference take $>2$s?
2. If `retrieval_latency_ms` is high:
   - Check MongoDB Atlas metrics: index build in progress or memory pressure.
   - Check `numCandidates` setting (default 100).
3. If `model_latency_ms` is high:
   - Verify OpenAI API status.
   - Check if context length is close to max context chars (4000).

#### Scenario C: Database Connection Failure (`DATABASE_ERROR`)
1. Search logs for `[req:<id>] MongoDB`:
   ```
   [req:9a8c7b6d] MongoDBClient Failed to connect to MongoDB: ServerSelectionTimeoutError
   ```
2. Verify:
   - Network connectivity to MongoDB Atlas cluster.
   - IP access list in MongoDB Atlas dashboard includes the current server IP.
   - `MONGODB_ATLAS_CLUSTER_URI` credentials are valid.

#### Scenario D: Out-of-Domain or Prompt Injection Block (`GUARDRAIL_BLOCK`)
1. Search logs for `[GUARDRAIL:INPUT]`:
   ```
   [GUARDRAIL:INPUT] Direct prompt injection attempt blocked: 'Ignore previous instructions'
   ```
2. Verify query input. In the response metadata, `decision` will be `OUT_OF_DOMAIN` and `violations` will list the exact injection rule triggered.
