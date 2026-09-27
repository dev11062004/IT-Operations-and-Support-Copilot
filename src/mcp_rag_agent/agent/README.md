# Production Agent Module (Phase 4)

The production agent module implements a high-reliability, agentic RAG orchestration system built on top of LangChain, LangGraph, and the Model Context Protocol (MCP).

It transitions the agent from a basic ReAct loop into a clearly structured agentic system organized around **7 explicit responsibilities**, with strong typed schemas, dual-mode execution parity, anti-hallucination guardrails, and structured execution metadata tracking.

---

## 1. Architecture Overview

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       RAGAgentRunner (Phase 4)                              │
│                                                                             │
│  [1. Query Understanding]                                                   │
│     ├── Analyze intent, extract entities, check domain                      │
│     └── [7. Out-of-Scope Detection]: Check policy boundaries & safety       │
│                                                                             │
│  [2. Tool Selection]                                                        │
│     └── Determine whether retrieval is required via ReAct tool calling      │
│                                                                             │
│  [3. Retrieval Execution] (Dual Execution Mode Parity)                      │
│     ├── Mode A: Direct Mode (LangChain StructuredTool)                      │
│     └── Mode B: MCP Mode (FastMCP Client over stdio)                        │
│     └── Strongly Typed Schema: SearchDocumentsInput ──▶ SearchDocumentsOutput│
│                                                                             │
│  [4. Context Synthesis]                                                     │
│     ├── Aggregate chunks, deduplicate documents, calculate retrieval latency│
│     └── Detect retrieval failure (empty/error) ──▶ Explicit refusal         │
│                                                                             │
│  [5. Grounded Answer Generation]                                            │
│     ├── COSTAR System Prompt: strictly grounded, refusal standard           │
│     └── Anti-hallucination: No unsupported claims, no invented sources     │
│                                                                             │
│  [6. Citation Generation & Provenance Validation]                           │
│     ├── Regex citation extractor: "Reference: 1. <filename>"                │
│     └── Provenance check: only validate citations matching retrieved docs   │
│                                                                             │
│  [Execution Metadata & Logging]                                             │
│     ├── request_id, thread_id, retrieval_latency_ms, model_latency_ms       │
│     └── Zero credential leakage: mask_sensitive() scrubs sk-... & URIs      │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
AgentResponse / Dict (LangGraph Parity)
```

---

## 2. Directory Structure

```
agent/
├── __init__.py                # Exports RAGAgentRunner, models, and factory functions
├── README.md                  # (This file) Architecture & developer guide
├── models.py                  # Pydantic v2 schemas: input, output, metadata, response
├── runner.py                  # Production RAGAgentRunner orchestrating the 7 responsibilities
├── create_agent.py            # Dual-mode factory creating RAGAgentRunner instances
├── prompts/
│   ├── __init__.py            # Exports system_prompt
│   └── system_prompt.py       # COSTAR prompt framework with anti-hallucination directives
└── utils/
    ├── mcp_rag_agent_creator.py   # Factory: Agent via MultiServerMCPClient + stdio
    └── rag_agent_creator.py       # Factory: Agent via direct LangChain StructuredTool
```

---

## 3. The 7 Explicit Agentic Responsibilities

| # | Responsibility | Component | Description |
|---|---|---|---|
| **1** | **Query Understanding** | `RAGAgentRunner` | Inspects query length, intent, and parameters; prepares structured search input. |
| **2** | **Tool Selection** | LangGraph ReAct Loop | Uses LLM tool binding (`ChatOpenAI.bind_tools`) to decide whether to invoke retrieval tools. |
| **3** | **Retrieval Execution** | `search_policy_documents_typed` | Executes hybrid search with over-fetching, RRF fusion, deduplication, and score tracking. |
| **4** | **Context Synthesis** | `RAGAgentRunner` & `RetrievedChunkOutput` | Formats retrieved chunks into clean evidence; catches retrieval failures gracefully. |
| **5** | **Grounded Answer Generation** | `system_prompt.py` (COSTAR) | Synthesizes response strictly from retrieved context; mandates refusal standard if empty. |
| **6** | **Citation Generation** | `RAGAgentRunner._extract_citations` | Validates that cited documents exist in the retrieved document set; prevents fabrication. |
| **7** | **Out-of-Scope Detection** | `RAGAgentRunner._is_out_of_scope` | Detects queries outside XYZ company policy domain and safely refuses or redirects. |

---

## 4. Strongly Typed Schemas (`models.py`)

All retrieval tools and responses enforce strict Pydantic v2 models:

### `SearchDocumentsInput`
```python
class SearchDocumentsInput(BaseModel):
    query: str = Field(description="Search query text", min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=50, description="Max candidate chunks")
    filter_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata filters")
```

### `SearchDocumentsOutput`
```python
class SearchDocumentsOutput(BaseModel):
    query: str
    total_results: int
    retrieval_latency_ms: float
    results: List[RetrievedChunkOutput]
    status: Literal["success", "empty", "error"]
    error_message: Optional[str] = None
```

### `AgentExecutionMetadata`
```python
class AgentExecutionMetadata(BaseModel):
    request_id: str
    thread_id: str
    retrieval_latency_ms: float
    model_latency_ms: float
    total_latency_ms: float
    retrieved_document_ids: List[str]
    citations: List[str]
    is_out_of_scope: bool
    retrieval_status: str
```

---

## 5. Dual Execution Modes & Parity

The system supports two interchangeable execution modes that expose identical functionality:

### Mode A: Direct Mode (`FEATURE_FLAG_MCPSERVER_ENABLED=false` - Default)
- **Use Case**: Fast CI/CD, evaluation harnesses (`evaluation/main.py`), unit tests, embedded microservices.
- **Implementation**: Directly wraps `search_policy_documents_typed` in a LangChain `StructuredTool` with `SearchDocumentsInput`.
- **Latency**: Lowest possible latency (no inter-process communication overhead).

### Mode B: MCP Mode (`FEATURE_FLAG_MCPSERVER_ENABLED=true`)
- **Use Case**: Enterprise decoupled tool serving, cross-language tool integration (Model Context Protocol).
- **Implementation**: Spawns `mcp_rag_agent.mcp_server.server` via `stdio` using `MultiServerMCPClient`.
- **Parity**: Exposes the exact same `search_policy_documents` tool with the same schemas.

---

## 6. Anti-Hallucination & Refusal Standard

The system strictly enforces the COSTAR prompt directives:

1. **Unsupported Knowledge Refusal**:
   If retrieved chunks are empty or do not contain the answer, the agent MUST reply:
   > `"I couldn't find this information in the available policy content."`
2. **No Source Invention**:
   The agent is forbidden from citing sources that do not exist in the retrieved context.
3. **Citation Format**:
   ```
   Reference:
   1. <Exact Document Name>
   ```

---

## 7. Structured Logging & Secret Masking

All logging throughout the agent and retrieval tools utilizes `mask_sensitive()` regex scrubbing:
- OpenAI API Keys: `sk-...` ──▶ `sk-...[MASKED]`
- MongoDB Connection Strings: `mongodb+srv://user:pass@host` ──▶ `mongodb+srv://***:***@host`

---

## 8. Persistent Conversation Memory (Phase 5)

The agent integrates LangGraph's official `MongoDBSaver` (`langgraph-checkpoint-mongodb`) to persist conversation history across process restarts while ensuring strict thread isolation.

### Features
1. **Multi-Turn Continuity**: Same `thread_id` restores full conversational message history.
2. **Process Restart Persistence**: Checkpoints are stored in MongoDB Atlas collections (`checkpoints` and `checkpoint_writes`), surviving application crashes and restarts.
3. **Strict Thread Isolation**: Different `thread_id` sessions operate in complete isolation with zero context leakage.
4. **Graceful Outage Fallback**: If MongoDB Atlas is unreachable during startup or query execution, the checkpointer catches the error, logs a sanitized warning, and automatically falls back to an in-memory `MemorySaver`.
5. **Evaluation Isolation**: In the evaluation harness (`evaluation/answer_generator.py`), each benchmark question receives an isolated UUID-based thread ID to ensure clean single-turn metrics without memory pollution.

### Configuration
```bash
FEATURE_FLAG_SESSION_MEMORY_ENABLED=true
MONGODB_CHECKPOINTS_COLLECTION=checkpoints
MONGODB_CHECKPOINT_WRITES_COLLECTION=checkpoint_writes
SESSION_MEMORY_TTL_SECONDS=2592000 # Optional 30-day TTL index
```

---

## 9. RAG Safety and Grounding Guardrails (Phase 6)

The agent integrates a dedicated guardrails subsystem (`mcp_rag_agent.guardrails.manager.RAGGuardrails`) that enforces safety and grounding across input, context, and output stages.

### 4-Tier Grounding Decision Taxonomy
Every `AgentResponse` exposes `.decision: DecisionCategory`:
- **`DecisionCategory.SUPPORTED_BY_EVIDENCE`**: Answer supported by retrieved evidence ($\ge 0.20$ grounding score, valid citations, confident retrieval).
- **`DecisionCategory.INSUFFICIENT_EVIDENCE`**: Insufficient evidence (empty retrieval, low similarity $< 0.015$, or ungrounded claims). Standard refusal enforced:
  `"I couldn't find this information in the available policy content. Please consult Company XYZ HR or your manager for guidance."`
- **`DecisionCategory.OUT_OF_DOMAIN`**: Query falls outside Company XYZ policy scope (general coding, trivia, math, medical diagnosis, fiction, or prompt injection).
- **`DecisionCategory.SYSTEM_FAILURE`**: Database or model system errors.

### Defense-in-Depth Pipeline
1. **Input Guardrails**:
   - `check_input_prompt_injection`: Intercepts DAN, jailbreaks, and system prompt leaks before any model invocation.
   - `check_out_of_domain`: Filters off-topic coding, math, general trivia, and creative writing.
2. **Context Guardrails**:
   - `sanitize_document_text`: Neutralizes indirect prompt injections embedded in document text.
   - Untrusted Data Sandboxing: Chunks are wrapped in `<retrieved_policy_chunk untrusted_data="true">` tags.
   - `evaluate_retrieval_context`: Enforces confidence threshold ($0.015$ RRF score) and context limits ($4000$ chars).
   - `check_conflicting_documents`: Detects cross-document numeric policy contradictions.
3. **Output Guardrails**:
   - `validate_citations`: Cross-checks cited sources against retrieved chunk IDs and titles; rejects fabricated references.
   - `calculate_grounding_score`: Lexical and numerical overlap measurement between answer and context.
   - `mask_sensitive_data`: Masks credentials, API keys, bearer tokens, passwords, and emails in logs and responses.

### Configuration
```bash
FEATURE_FLAG_GUARDRAILS_ENABLED=true
GUARDRAIL_CONFIDENCE_THRESHOLD=0.015
GUARDRAIL_MIN_VECTOR_SIMILARITY=0.50
GUARDRAIL_MAX_CONTEXT_CHARS=4000
GUARDRAIL_MIN_GROUNDING_SCORE=0.20
```

---

## 10. Usage Examples

### Multi-Turn Conversation Example

```python
import asyncio
from mcp_rag_agent.agent import create_rag_agent_instance
from mcp_rag_agent.core.config import config

async def main():
    agent_runner = await create_rag_agent_instance(config=config)
    session_thread = "employee_session_101"

    # Turn 1: Initial Question
    response_1 = await agent_runner.run(
        query="What is the remote working policy regarding allowed days?",
        thread_id=session_thread,
        user_id="user_alice",
    )
    print("Turn 1 Answer:\n", response_1.answer)
    print("Citations:", response_1.metadata.citations)

    # Turn 2: Follow-up Question (Contextual Antecedent Resolution)
    # The checkpointer automatically provides previous conversation history!
    response_2 = await agent_runner.run(
        query="And who needs to approve it?",
        thread_id=session_thread,
        user_id="user_alice",
    )
    print("\nTurn 2 Answer (resolving 'it' to remote working):\n", response_2.answer)
    print("Turn 2 Thread:", response_2.metadata.thread_id)

    # LangGraph backward-compatible interface with configurable thread_id
    result = await agent_runner.ainvoke(
        {"messages": [{"role": "user", "content": "Can unused leave be carried over?"}]},
        config={"configurable": {"thread_id": "session_leave_202"}},
    )
    print("\nLangGraph result:", result["messages"][-1].content)

if __name__ == "__main__":
    asyncio.run(main())
```
