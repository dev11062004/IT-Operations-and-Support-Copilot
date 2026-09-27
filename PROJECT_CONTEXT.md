# PROJECT CONTEXT: MCP RAG AGENT

> **Document Type:** Canonical Master Project Context & Specification  
> **Target Audience:** AI Models, Autonomous Coding Agents, and Human Engineers  
> **Purpose:** Provide complete, authoritative, hallucination-free context on architecture, code structure, configurations, conventions, data models, workflows, gotchas, and technical debt.  
> **Instruction for AI Agents:** Treat this document as the single source of truth for the `mcp-rag-agent` codebase. Do not invent modules, classes, functions, or configurations not described herein. All phases from Phase 1 through Phase 12 are fully implemented, verified, and operational.

---

## 1. Executive Summary

- **Project Name:** `mcp_rag_agent`
- **Author:** Luis Rodrigues, PhD (`luisrodriguesphd@gmail.com`)
- **Repository:** `https://github.com/luisrodriguesphd/mcp-rag-agent.git`
- **License:** MIT
- **Current Version:** `0.1.0`

### Core Objective
The **MCP RAG Agent** is an enterprise-grade Retrieval-Augmented Generation (RAG) system engineered to answer organizational policy questions with high factual fidelity, zero hallucinations, verifiable source citations, and sub-second retrieval performance.

### Architectural Foundations
1. **LangChain & LangGraph ReAct Orchestration:** Autonomous reasoning and acting agent managing query decomposition, tool invocation, context synthesis, and grounded answering.
2. **Model Context Protocol (MCP) Standard:** Exposes MongoDB semantic retrieval tools via FastMCP (supporting both `stdio` subprocess and `sse` network transport) with dual-mode direct fallback for local testing and CI/CD pipelines.
3. **MongoDB Atlas Hybrid Search & Reciprocal Rank Fusion (RRF):** Combines dense vector embeddings (OpenAI `text-embedding-3-small`, 256 dimensions) with sparse full-text search (`$text` index, stemming, term frequency) dampened by constant $k=60$.
4. **COSTAR Prompt Framework & Grounding Guardrails:** Strictly grounded answers enforced via structured system prompting and defense-in-depth guardrails (prompt injection filtering, citation validation, out-of-domain rejection, and numerical conflict detection).
5. **Persistent Conversation Memory:** Stateful multi-turn dialogue continuity backed by MongoDB Atlas checkpoints (`MongoDBSaver`), surviving process restarts with strict thread isolation and graceful fallback during database outages.
6. **Multi-Tier Quantitative Evaluation Framework:** Benchmarks retrieval quality (Recall@K, MRR, Hit Rate), factual generation (Faithfulness, Answer Correctness with 50% numeric weighting, Relevancy), and operational latency/cost using RAGAS and native mathematical metrics.
7. **Production Observability & Tracing:** Thread-safe correlation context propagation (`contextvars`), structured JSON logging with automated secret masking (`MaskingFilter`), token usage accounting, dynamic cost estimation, and LangSmith telemetry.
8. **Production FastAPI Backend & Modern Web UI:** Asynchronous REST API with Zero Chain-of-Thought (Zero-CoT) guarantee, paired with a lightweight, responsive Vanilla ES6/HTML5/CSS web interface featuring real-time diagnostics and a slide-over citation drawer.
9. **Containerized Microservice Deployment:** Multi-stage Docker builds running unprivileged (`appuser` UID 10001, `nginx` UID 101) coordinated via Docker Compose across 4 microservices (`mongodb`, `api`, `frontend`, `mcp-server`).
10. **Automated CI/CD Quality Assurance:** Comprehensive GitHub Actions workflows covering formatting, linting, unit test matrix (Python 3.10 and 3.11), test coverage reporting (75% threshold), Docker build validation, Bandit AST security scans, `pip-audit` CVE checks, and live MongoDB integration tests.

---

## 2. Complete Repository Tree & File Manifest

```
mcp-rag-agent/
├── .coverage                                  # Coverage data artifact from local pytest runs
├── .dockerignore                              # Excludes .env, git, caches from Docker build context
├── .env                                       # Local environment variables file (git-ignored)
├── .env.example                               # Authoritative template for all 38+ environment variables
├── .flake8                                    # Flake8 lint configuration (max-line-length=120, ignores)
├── .gitignore                                 # Git ignore patterns (.env, venv, pycache, dist, coverage)
├── Dockerfile                                 # Multi-stage production container build (builder, frontend, api)
├── Dockerfile.frontend                        # Dedicated standalone Nginx frontend container image
├── docker-compose.yml                         # Orchestration for mongodb, api, frontend, and mcp-server
├── PROJECT_CONTEXT.md                         # (This document) Master canonical project specification
├── pytest.ini                                 # Pytest configuration (pythonpath, testpaths, unit/integration markers)
├── README.md                                  # High-level overview, architecture diagrams, and usage guide
├── requirements.txt                           # Production runtime dependencies
├── requirements_dev.txt                       # Development, linting, evaluation, and test dependencies
├── setup.py                                   # Package setup (`pip install -e .`, package root: `src`)
├── start.cmd                                  # Windows environment bootstrap script (venv, pip, deps)
├── start.sh                                   # POSIX environment bootstrap script
│
├── .github/
│   └── workflows/
│       ├── ci.yml                             # Primary CI: Lint, Unit Tests (3.10/3.11), API Tests, Build, Security
│       └── integration.yml                    # Live Integration Suite: Live MongoDB container + optional live OpenAI
│
├── data/
│   ├── ingested_documents/                    # Raw input corpus for ingestion & vectorization
│   │   └── policies/
│   │       ├── 1 - Remote Working.txt         # Remote work policy (up to 3 days/week, manager approval)
│   │       ├── 2 - Expenses.txt               # Travel, meal, and 30-day submission expense rules
│   │       ├── 3 - Annual Leave.txt           # UK (25d), EU (30d, 5d carryover), US (15d) leave policies
│   │       ├── 4 - IT Security.txt            # Passwords (12 chars, 90d), laptops, incident reporting
│   │       └── 5 - Sustainability.txt         # Carbon reduction (-20% by 2030), travel, recycling
│   └── evaluation_documents/
│       └── expected_behaviour.xlsx            # Benchmark evaluation dataset (10 QA test cases with ground truth)
│
├── docker/
│   └── nginx/
│       └── nginx.conf                         # Unprivileged Nginx configuration, SPA routing, API reverse proxy
│
├── docs/
│   ├── [2025-11-30]Case-MCP-RAG-Agent-Architecture.drawio       # Draw.io architectural diagram source
│   ├── [2025-11-30]Case-MCP-RAG-Agent-Architecture.drawio.png   # Rendered architecture diagram
│   ├── DEBUGGING_GUIDE.md                                       # Observability, request tracing & triage guide
│   └── DEPLOYMENT.md                                            # Complete containerization & deployment manual
│
├── evaluation/                                # Production RAG Evaluation Subsystem (Phase 7)
│   ├── __init__.py                            # Module export
│   ├── README.md                              # Evaluation guide & CLI execution manual
│   ├── METHODOLOGY.md                         # Mathematical definitions, protocols & engineering limitations
│   ├── answer_generator.py                    # Legacy Phase 1 runner
│   ├── metrics_evaluator.py                   # Legacy Phase 2 runner
│   ├── metrics.py                             # Backward-compatible shim re-exporting RAGASEvaluator
│   ├── main.py                                # Legacy interactive entrypoint
│   ├── datasets/
│   │   ├── __init__.py
│   │   ├── loader.py                          # BenchmarkItem, BenchmarkDataset models & loaders
│   │   └── v1_policy_benchmark.json           # Curated golden benchmark dataset (15 test cases)
│   ├── metrics/
│   │   ├── __init__.py                        # Unified public exports
│   │   ├── retrieval.py                       # Recall@K, Precision@K, MRR, Hit Rate
│   │   ├── generation.py                      # Faithfulness, Answer Correctness, Relevancy, Context Prec/Recall
│   │   ├── operational.py                     # Retrieval/Gen/Total latency, Token counts, Cost (USD)
│   │   └── ragas_evaluator.py                 # RAGAS wrapper with graceful native fallback
│   ├── runners/
│   │   ├── __init__.py
│   │   └── eval_runner.py                     # ProductionEvalRunner (full, retrieval_only, offline)
│   ├── reports/
│   │   ├── __init__.py
│   │   ├── comparator.py                      # RegressionComparator (Baseline vs Current diff & failures)
│   │   └── sample_regression_report.md        # Reference regression report artifact
│   └── results/                               # Output artifacts (JSON & CSV evaluation runs)
│
├── scripts/
│   ├── benchmark_retrieval.py                 # Retrieval latency benchmarking harness
│   ├── compare_memory_evaluation.py           # Pre vs Post Memory RAGAS evaluation comparison harness
│   └── generate_sample_regression_report.py   # Generates sample baseline vs current regression evaluation report
│
├── src/
│   └── mcp_rag_agent/                         # Core Python package namespace
│       ├── core/                              # Infrastructure, configuration, memory & logging
│       │   ├── __init__.py
│       │   ├── checkpointer.py                # MongoDB & in-memory conversation checkpointer factory
│       │   ├── config.py                      # Pydantic BaseSettings config class (`config` singleton)
│       │   └── log_setup.py                   # Centralized logging, JSON formatter & secret masking filter
│       │
│       ├── mongodb/                           # MongoDB Atlas connectivity & search primitives
│       │   ├── __init__.py                    # Exports `MongoDBClient`
│       │   ├── README.md                      # MongoDB client API reference
│       │   ├── SEARCH_GUIDE.md                # Comprehensive guide comparing Vector vs Text vs Hybrid search
│       │   └── client.py                      # MongoDBClient with vector_search, text_search, and hybrid_search (RRF)
│       │
│       ├── embeddings/                        # Embedding generation & vector search
│       │   ├── __init__.py                    # Module definition
│       │   ├── README.md                      # Detailed guide to indexing and search
│       │   ├── embedding_generator.py         # Async OpenAI embedding client wrapper (single & batch)
│       │   ├── semantic_search.py             # Pure vector search engine abstraction
│       │   ├── hybrid_search.py               # Hybrid search engine abstraction (vector + text + RRF)
│       │   └── index_documents.py             # Production CLI batch entrypoint for document ingestion
│       │
│       ├── ingestion/                         # Production-Grade Document Ingestion Pipeline (Phase 2)
│       │   ├── __init__.py                    # Public API exports
│       │   ├── models.py                      # Data models (ParsedDocument, DocumentChunk, IngestionResult)
│       │   ├── cleaner.py                     # Text normalization (NFKC) and control-character sanitization
│       │   ├── parsers.py                     # Multi-format parsers (TXT, PDF, DOCX, Markdown) & ParserFactory
│       │   ├── chunker.py                     # Structure-aware recursive text chunker
│       │   └── pipeline.py                    # End-to-end ingestion pipeline with deduplication & reindexing
│       │
│       ├── retrieval/                         # Advanced Hybrid Retrieval & Ranking Subsystem (Phase 3)
│       │   ├── __init__.py                    # Public API exports
│       │   ├── models.py                      # Data models (RetrievedChunk, RetrievalResult, RetrievalLatency)
│       │   ├── preprocessor.py                # Query preprocessing, Unicode normalization, keyword sanitization
│       │   ├── reranker.py                    # Pluggable rerankers (NoOp, CrossEncoder, LLMReranker)
│       │   └── pipeline.py                    # AdvancedRetriever orchestrating over-fetching, RRF, deduplication
│       │
│       ├── guardrails/                        # RAG Safety & Grounding Guardrails (Phase 6)
│       │   ├── __init__.py                    # Public API exports
│       │   ├── models.py                      # DecisionCategory, ViolationType, GuardrailViolation, GuardrailResult
│       │   ├── input_guardrails.py            # Direct prompt injection defense & out-of-domain detection
│       │   ├── context_guardrails.py          # Document injection neutralization, sandboxing, confidence cutoff
│       │   ├── output_guardrails.py           # Citation validation, source existence check, grounding score
│       │   └── manager.py                     # Central RAGGuardrails orchestrator
│       │
│       ├── mcp_server/                        # Model Context Protocol (MCP) server & tools
│       │   ├── __init__.py                    # Module definition
│       │   ├── README.md                      # FastMCP server documentation and CLI test commands
│       │   ├── server.py                      # FastMCP server instance (`mcp`), tool registration, MCP prompt
│       │   └── tools.py                       # `search_policy_documents_typed` retrieval tool implementation
│       │
│       ├── agent/                             # Production LangChain / LangGraph Agent (Phases 4 & 5)
│       │   ├── __init__.py                    # Exports agent instance, runner, and models
│       │   ├── README.md                      # Agent architecture, 7 explicit responsibilities & session memory
│       │   ├── models.py                      # Strongly typed tool schemas & execution metadata
│       │   ├── runner.py                      # Production RAGAgentRunner orchestrating 7 responsibilities
│       │   ├── create_agent.py                # Dual-mode agent factory (Direct vs MCP) with StructuredTool
│       │   ├── prompts/
│       │   │   ├── __init__.py                # Exports `system_prompt`
│       │   │   └── system_prompt.py           # COSTAR prompt framework & anti-hallucination guardrails
│       │   └── utils/
│       │       ├── mcp_rag_agent_creator.py   # Factory: Agent via MultiServerMCPClient + stdio
│       │       └── rag_agent_creator.py       # Factory: Agent via direct LangChain StructuredTool
│       │
│       ├── api/                               # Production FastAPI Backend & Web UI Layer (Phases 9 & 10)
│       │   ├── __init__.py                    # Exports `create_app` factory
│       │   ├── app.py                         # FastAPI application factory, CORS, static UI mount, exception handlers
│       │   ├── dependencies.py                # Dependency injection for Config, ChatService, ConversationService
│       │   ├── middleware.py                  # CorrelationIdMiddleware (X-Request-ID, latency, structured access logs)
│       │   ├── routes/
│       │   │   ├── __init__.py                # API v1 router aggregator (`/api/v1`)
│       │   │   ├── chat.py                    # POST /api/v1/chat endpoint (Zero-CoT)
│       │   │   ├── conversations.py           # GET, POST, DELETE /api/v1/conversations endpoints
│       │   │   └── health.py                  # GET /api/v1/health (liveness) and GET /api/v1/ready (readiness)
│       │   ├── schemas/
│       │   │   ├── __init__.py
│       │   │   ├── chat.py                    # ChatRequest, ChatResponse, SourceDocument, ChatResponseMetadata
│       │   │   ├── conversation.py            # CreateConversationRequest, ConversationThreadResponse, etc.
│       │   │   └── health.py                  # HealthResponse, ReadinessResponse, ReadinessDetails
│       │   ├── services/
│       │   │   ├── __init__.py
│       │   │   ├── chat_service.py            # ChatService coordinating RAGAgentRunner with Zero-CoT output
│       │   │   └── conversation_service.py    # ConversationService managing threads, dialogue history, checkpoints
│       │   └── static/                        # Enterprise Web UI (Phase 10)
│       │       ├── index.html                 # Semantic HTML5 app shell, sidebar, drawer, modals, empty states
│       │       ├── styles.css                 # Dark theme, glassmorphism, responsive typography, micro-animations
│       │       └── app.js                     # ES6 frontend controller, API client, markdown parser, citation drawer
│       │
│       └── observability/                     # Production Observability & Tracing Subsystem (Phase 8)
│           ├── __init__.py                    # Public API exports
│           ├── models.py                      # ErrorCategory (7 codes), ErrorRecord, TokenUsage, TraceSpan, RequestTrace
│           ├── context.py                     # Async-safe contextvars for request_id, thread_id, user_id, current_tracer
│           ├── tracer.py                      # ObservabilityTracer, sub-spans, model rate cards, cost calculations
│           └── langsmith_integration.py       # LangSmith tracing, run configs, metadata and tag injection
│
└── tests/
    ├── unit_tests/                            # 15 Isolated unit test suites (Zero external secret dependencies)
    │   ├── __init__.py
    │   ├── test_config.py                     # Configuration validation tests
    │   ├── test_embedding_generator.py        # Embedding dimension and generation tests
    │   ├── test_tools_and_retriever.py        # Hybrid search tool tests
    │   ├── test_agent_creation.py             # Direct and MCP mode agent creation tests
    │   ├── test_answer_generator.py           # Evaluation answer generator tests
    │   ├── test_ingestion.py                  # Ingestion CLI backward compatibility tests
    │   ├── test_ingestion_pipeline.py         # Full Phase 2 ingestion pipeline tests
    │   ├── test_advanced_retrieval.py         # Full Phase 3 advanced retrieval tests
    │   ├── test_agent_architecture.py         # Full Phase 4 production agent architecture tests
    │   ├── test_session_memory.py             # Full Phase 5 persistent session memory tests
    │   ├── test_guardrails_adversarial.py     # Full Phase 6 RAG safety and adversarial tests (30 tests)
    │   ├── test_evaluation_framework.py       # Full Phase 7 quantitative evaluation framework tests
    │   ├── test_observability.py              # Full Phase 8 end-to-end observability, error categories & tracing tests
    │   ├── test_api.py                        # Full Phase 9 FastAPI endpoints, validation, Zero-CoT & correlation tests
    │   └── mongodb/
    │       ├── __init__.py
    │       └── test_client.py                 # Pytest suite with mocked MongoDB client operations
    │
    └── integration_tests/                     # Segregated integration tests (Requires live MongoDB or live OpenAI)
        ├── __init__.py
        ├── test_api_integration.py            # Live Starlette TestClient endpoint and correlation header checks
        ├── test_mcp_integration.py            # Live FastMCP server metadata, prompts, and retrieval tool contracts
        └── test_mongodb_integration.py        # Live MongoDB ping, document CRUD, and checkpoint verification
```

---

## 3. Technology Stack & Dependency Matrix

### Runtime Dependencies (`requirements.txt`)
- `langchain>=1.1.0`: Core agent orchestration and Runnable chains.
- `langchain-core>=1.1.0`: Foundation primitives (messages, tools, outputs, runnables).
- `langchain-text-splitters>=0.3.0`: Intelligent recursive text chunking.
- `langchain-mcp-adapters>=0.1.14`: Bridge converting MCP servers and tools to LangChain structured tools.
- `langchain-openai>=1.1.0`: OpenAI integrations (`ChatOpenAI`, `OpenAIEmbeddings`).
- `langgraph>=1.2.0`: Cyclic state graph agent runtime powering the ReAct loop.
- `langgraph-checkpoint-mongodb>=0.5.0`: Persistent conversation checkpointer (`MongoDBSaver`).
- `langsmith>=0.1.0`: Telemetry, distributed tracing, and prompt monitoring.
- `mcp>=1.2.0`: Official Python Model Context Protocol specification & SDK (`FastMCP`).
- `pymongo>=4.6.0`: Official MongoDB Python driver.
- `openai>=1.0.0`: Official OpenAI async/sync API client.
- `python-dotenv>=1.0.0`: Dotenv configuration loader.
- `pydantic-settings>=2.10.1`: Type-safe application settings from environment variables.
- `pypdf>=5.0.0`: PDF document extraction and page-level metadata parsing.
- `python-docx>=1.1.0`: Word document parser with paragraph and section extraction.
- `fastapi>=0.110.0`: Asynchronous REST API framework.
- `uvicorn>=0.28.0`: High-performance ASGI production server.

### Development, Evaluation & Quality Dependencies (`requirements_dev.txt`)
- `ragas==0.3.9`: Retrieval Augmented Generation Assessment framework.
- `openpyxl==3.1.5`: Excel parser for reading `expected_behaviour.xlsx`.
- `pandas==2.3.3`: Data processing and evaluation metrics aggregation.
- `datasets==4.4.1`: HuggingFace datasets library required by RAGAS.
- `pytest>=8.0.0`, `pytest-asyncio>=0.23.0`, `pytest-cov>=5.0.0`: Testing harness and coverage reporting.
- `httpx>=0.27.0`: Async HTTP client for API testing.
- `black>=24.0.0`: Deterministic code formatting.
- `flake8>=7.0.0`: Code linting.
- `isort>=5.13.0`: Import order sorting.
- `bandit>=1.7.0`: AST-based security vulnerability scanner.
- `pip-audit>=2.7.0`: Dependency CVE vulnerability auditor.
- `setuptools>=68.0.0`, `wheel>=0.42.0`: Standard Python packaging tools.

### Python Version Support
- Python **3.10** and **3.11** (officially tested and validated in GitHub Actions matrix).

---

## 4. Master Configuration & Environment Variables Reference

All application settings are defined in `src/mcp_rag_agent/core/config.py` using `pydantic-settings.BaseSettings`.  
The module automatically executes `load_dotenv(override=True)` upon initial import.

### Comprehensive Environment Variables Table

| Variable Name | Required? | Default in Code | Purpose & Operational Impact |
|---|---|---|---|
| **`MONGODB_ATLAS_CLUSTER_URI`** | **YES** | `""` *(raises ConfigurationError)* | Connection string (`mongodb+srv://...` or `mongodb://mongodb:27017` in Docker). |
| **`MONGODB_ATLAS_DB_NAME`** | **YES** | `""` *(raises ConfigurationError)* | Target MongoDB database name (e.g. `mcp_rag_agent_db`). |
| **`OPENAI_API_KEY`** | **YES** | `""` *(raises ConfigurationError)* | OpenAI API key for embeddings, text generation, and RAGAS evaluations. |
| `API_HOST` | No | `"0.0.0.0"` | Network interface for FastAPI Uvicorn listener. |
| `API_PORT` | No | `8000` | Port for FastAPI Uvicorn listener (and container host mapping). |
| `FRONTEND_PORT` | No | `3000` | Host port mapped to Nginx web frontend in Docker Compose. |
| `MONGODB_PORT` | No | `27017` | Port exposed by local MongoDB container in Docker Compose. |
| `LOG_LEVEL` | No | `"INFO"` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). |
| `LOG_FORMAT` | No | `"text"` | Log formatting: `"text"` (human-readable with correlation) or `"json"`. |
| `DEBUG` | No | `false` | Global debug toggle. |
| `LANGSMITH_TRACING` | No | `false` | Enables LangSmith distributed tracing when `true`. |
| `LANGSMITH_ENDPOINT` | No | `"https://api.smith.langchain.com"` | LangSmith API collection endpoint. |
| `LANGSMITH_API_KEY` | No | `""` | Authentication key for LangSmith project. |
| `LANGSMITH_PROJECT` | No | `"mcp-rag-agent"` | Telemetry project name inside LangSmith. |
| `LANGSMITH_HIDE_INPUTS` | No | `false` | When `true`, redacts prompt text from LangSmith traces. |
| `LANGSMITH_HIDE_OUTPUTS`| No | `false` | When `true`, redacts model output text from LangSmith traces. |
| `MONGODB_USERS_COLLECTION` | No | `"users"` | Collection for future user profiles and RBAC. |
| `MONGODB_CONVERSATIONS_COLLECTION` | No | `"conversations"` | Collection for conversational session metadata. |
| `MONGODB_CHECKPOINTS_COLLECTION` | No | `"checkpoints"` | Collection storing LangGraph state checkpoints (`MongoDBSaver`). |
| `MONGODB_CHECKPOINT_WRITES_COLLECTION` | No | `"checkpoint_writes"` | Collection storing pending checkpoint writes. |
| `SESSION_MEMORY_TTL_SECONDS` | No | `2592000` *(in .env)* / `None` | Time-to-live expiration for checkpoint documents (2,592,000s = 30 days). |
| `MONGODB_MESSAGES_COLLECTION` | No | `"messages"` | Raw chat message log collection. |
| `MONGODB_DOCUMENTS_COLLECTION` | No | `"documents"` | Collection storing parent document records, hashes, and provenance. |
| `MONGODB_VECTOR_COLLECTION` | No | `"vectors"` | Collection storing chunk text, embeddings (256-dim), and chunk metadata. |
| `MONGODB_VECTOR_INDEX_NAME` | No | `"vector_index"` | Name of MongoDB Atlas vector search index on the `vectors` collection. |
| `EMBEDDING_MODEL_NAME` | No | `"text-embedding-3-small"`| OpenAI embedding model identifier. |
| `EMBEDDING_DIMENSION` | No | `256` | **CRITICAL:** Reduced dimension parameter passed to OpenAI embeddings API. |
| `TEXT_MODEL_NAME` | No | `"gpt-4.1"` | Primary LLM powering the LangGraph ReAct reasoning agent. |
| `EVALUATION_MODEL_NAME` | No | `"gpt-4o-mini"` | LLM used as the judge for RAGAS and quantitative evaluations. |
| `MCP_SERVER_NAME` | No | `"mongodb-semantic-search"`| Identifier registered by the FastMCP server. |
| `MCP_SERVER_HOST` | No | `"127.0.0.1"` | Host address for FastMCP server. |
| `MCP_SERVER_PORT` | No | `8000` *(8001 in Docker)* | Port for FastMCP server. |
| `MCP_TRANSPORT` | No | `"stdio"` | Transport protocol: `"stdio"` (subprocess) or `"sse"` (network HTTP). |
| `MCP_SERVER_URL` | No | `None` *(http://mcp-server:8001/sse)* | URL when connecting to FastMCP in SSE mode. |
| `SEMANTIC_WEIGHT` | No | `0.7` | Hybrid search weight (0.7 vector similarity vs 0.3 text search). |
| `FEATURE_FLAG_MCPSERVER_ENABLED` | No | `false` | When `true`, spawns MCP subprocess/client; when `false`, runs direct. |
| `FEATURE_FLAG_WEBSEARCH_ENABLED` | No | `false` | Feature flag reserved for future public web search fallback. |
| `FEATURE_FLAG_SESSION_MEMORY_ENABLED` | No | `true` | Enables persistent multi-turn conversational memory via checkpointer. |
| `FEATURE_FLAG_GUARDRAILS_ENABLED` | No | `true` | Enables 4-tier safety guardrails, prompt injection filtering & citations. |
| `GUARDRAIL_CONFIDENCE_THRESHOLD` | No | `0.015` | Minimum RRF score required for retrieval results to be accepted. |
| `GUARDRAIL_MIN_VECTOR_SIMILARITY` | No | `0.50` | Minimum raw cosine similarity accepted when vector candidates exist. |
| `GUARDRAIL_MAX_CONTEXT_CHARS` | No | `4000` | Maximum context length before truncation and safety warning. |
| `GUARDRAIL_MIN_GROUNDING_SCORE` | No | `0.20` | Minimum token/entity overlap score between answer and retrieved chunks. |
| `INGESTED_DOC_DIRECTORY` | No | `"./data/ingested_documents"`| Root folder path for raw policy documents. |
| `EVALUATION_DOC_DIRECTORY` | No | `"./data/evaluation_documents"`| Directory containing evaluation Excel test cases. |
| `CHUNK_SIZE` | No | `500` | Target character length for document text chunks. |
| `CHUNK_OVERLAP` | No | `50` | Character overlap between consecutive text chunks. |
| `REINDEX` | No | `false` | Force re-indexing of documents even when SHA-256 hashes match. |
| `RETRIEVAL_OVERSAMPLE_FACTOR` | No | `3` | Multiplier for candidate fetching: retrieves `top_k * factor` candidates. |
| `RETRIEVAL_RRF_K` | No | `60` | Reciprocal Rank Fusion rank dampening constant. |
| `RETRIEVAL_DEBUG_MODE` | No | `false` | When `true`, captures candidates, scores, and timings (Zero-CoT safe). |
| `RETRIEVAL_RERANKER_TYPE` | No | `"none"` | Pluggable reranker: `"none"` (NoOp), `"cross_encoder"`, or `"llm"`. |
| `RETRIEVAL_TOP_K` | No | `3` | Default number of top retrieved chunks returned to agent context. |

### Fixed LLM Generation Parameters (`config.py`)
```python
text_generation_kwargs = {
    "max_tokens": 2048,
    "temperature": 0,    # Zero temperature for deterministic generation
    "top_p": 0.1,        # Narrow nucleus sampling to eliminate hallucination
}
```

---

## 5. Data Models, Schemas & Type Contracts

The system enforces strict Pydantic v2 schemas across all subsystem boundaries.

### 5.1 Ingestion Schemas (`src/mcp_rag_agent/ingestion/models.py`)
- **`ParsedDocument`**: `document_id`, `filename`, `file_type` (`txt` | `pdf` | `docx` | `md`), `source_path`, `raw_text`, `title`, `content_hash` (SHA-256), `metadata`.
- **`DocumentChunk`**: `chunk_id` (`<doc_id>_c<index>`), `document_id`, `content`, `metadata` (dict containing `section`, `page_number`, `chunk_index`, `total_chunks`, `content_hash`).
- **`IngestionResult`**: `status` (`INGESTED`, `SKIPPED_UNCHANGED`, `FAILED`, `UPDATED`), `document_id`, `filename`, `source_path`, `chunk_count`, `error_message`.
- **`IngestionSummary`**: `total_documents`, `ingested`, `skipped`, `failed`, `results` (List[IngestionResult]), `elapsed_seconds`.

### 5.2 MongoDB Document Collections
1. **`documents` Collection (Parent Document Records)**:
   ```json
   {
     "_id": "ObjectId(...)",
     "document_id": "doc_e2a3b4c5d6e7",
     "filename": "1 - Remote Working.txt",
     "file_type": "txt",
     "source_path": "/app/data/ingested_documents/policies/1 - Remote Working.txt",
     "title": "Remote Working Policy",
     "content_hash": "a1b2c3d4e5f67890abcdef...",
     "total_chunks": 3,
     "total_characters": 1240,
     "ingestion_timestamp": "2026-09-27T10:00:00.000Z",
     "created_at": "2026-09-27T10:00:00.000Z"
   }
   ```
2. **`vectors` Collection (Chunks & Embeddings)**:
   ```json
   {
     "_id": "ObjectId(...)",
     "chunk_id": "doc_e2a3b4c5d6e7_c0",
     "content": "Employees may work remotely up to three days per week with manager agreement.\n",
     "embedding": [0.0123, -0.0456, 0.0891, ...], // Exactly 256 float numbers
     "metadata": {
       "chunk_id": "doc_e2a3b4c5d6e7_c0",
       "document_id": "doc_e2a3b4c5d6e7",
       "filename": "1 - Remote Working.txt",
       "file_type": "txt",
       "source_path": "/app/data/ingested_documents/policies/1 - Remote Working.txt",
       "title": "Remote Working Policy",
       "section": "Eligibility",
       "page_number": null,
       "chunk_index": 0,
       "total_chunks": 3,
       "content_hash": "a1b2c3d4e5f67890abcdef...",
       "ingestion_timestamp": "2026-09-27T10:00:00.000Z"
     }
   }
   ```

### 5.3 Retrieval Schemas (`src/mcp_rag_agent/retrieval/models.py`)
- **`RetrievedChunk`**: `chunk_id`, `document_id`, `document_name`, `content`, `vector_score` (Optional[float]), `keyword_score` (Optional[float]), `fusion_score` (float), `rerank_score` (Optional[float]), `rank` (int, 1-indexed), `metadata` (dict).
- **`RetrievalLatency`**: `query_embedding_ms`, `vector_search_ms`, `keyword_search_ms`, `fusion_ms`, `rerank_ms`, `total_retrieval_ms`.
- **`RetrievalResult`**: `query`, `normalized_query`, `chunks` (List[RetrievedChunk]), `total_candidates`, `latency` (RetrievalLatency), `debug_info` (Optional[RetrievalDebugInfo]).

### 5.4 Tool Contracts & Agent Models (`src/mcp_rag_agent/agent/models.py`)
- **`SearchDocumentsInput`**: `query` (str, 1-1000 characters), `top_k` (int, 1-50, default 3), `filter_query` (Optional[dict]).
- **`RetrievedChunkOutput`**: Typed representation of retrieved chunk for LLM tool consumption.
- **`SearchDocumentsOutput`**: `query`, `total_results`, `retrieval_latency_ms`, `chunks` (List[RetrievedChunkOutput]), `status` (`"success"` | `"empty"` | `"error"`), `error_message`. Provides `.to_tool_string()` for clean LLM prompt insertion.
- **`AgentExecutionMetadata`**: `request_id`, `thread_id`, `retrieval_latency_ms`, `model_latency_ms`, `total_latency_ms`, `retrieved_document_ids`, `citations` (List[str]), `guardrail_result` (Optional[dict]), `token_usage` (Optional[dict]), `trace` (Optional[dict]).
- **`AgentResponse`**: `answer` (str), `metadata` (AgentExecutionMetadata), `citations` (List[str]).

### 5.5 Guardrails Models (`src/mcp_rag_agent/guardrails/models.py`)
- **`DecisionCategory`** (Enum):
  - `SUPPORTED_BY_EVIDENCE`: High retrieval confidence, grounded answer, valid citations.
  - `INSUFFICIENT_EVIDENCE`: Retrieval returned empty or low-confidence results, ungrounded answer, or fabricated citations.
  - `OUT_OF_DOMAIN`: Query outside Company XYZ policies or direct prompt injection.
  - `SYSTEM_FAILURE`: Database, embedding, or model runtime failure.
- **`ViolationType`** (Enum): `PROMPT_INJECTION_DIRECT`, `PROMPT_INJECTION_INDIRECT`, `OUT_OF_DOMAIN_QUERY`, `EMPTY_RETRIEVAL`, `LOW_CONFIDENCE_RETRIEVAL`, `FABRICATED_CITATION`, `UNGROUNDED_ANSWER`, `CROSS_DOCUMENT_CONFLICT`, `MAX_CONTEXT_EXCEEDED`, `SENSITIVE_INFO_LEAK`.
- **`GuardrailResult`**: `is_safe` (bool), `decision` (DecisionCategory), `confidence_score` (float), `grounding_score` (float), `violations` (List[GuardrailViolation]), `warnings` (List[str]), `validated_citations` (List[str]), `rejected_citations` (List[str]), `sanitized_query` (str), `sanitized_context` (str).

### 5.6 Observability Schemas (`src/mcp_rag_agent/observability/models.py`)
- **`ErrorCategory`** (Enum): `RETRIEVAL_ERROR`, `MODEL_ERROR`, `MCP_ERROR`, `DATABASE_ERROR`, `VALIDATION_ERROR`, `GUARDRAIL_BLOCK`, `TIMEOUT`.
- **`TokenUsage`**: `prompt_tokens`, `completion_tokens`, `total_tokens`, `estimated_cost_usd`.
- **`TraceSpan`**: `span_id`, `parent_span_id`, `name`, `start_time`, `end_time`, `duration_ms`, `metadata`, `error`.
- **`RequestTrace`**: `request_id`, `thread_id`, `user_id`, `start_time`, `end_time`, `total_duration_ms`, `spans` (List[TraceSpan]), `token_usage`, `errors`.

### 5.7 API Schemas (`src/mcp_rag_agent/api/schemas/`)
- **`ChatRequest`**: `message` (str, 1-2000 chars), `thread_id` (Optional[str]), `user_id` (Optional[str]).
- **`SourceDocument`**: `document_name`, `document_id`, `chunk_id`, `content`, `rank`, `fusion_score`, `section`, `file_type`.
- **`ChatResponseMetadata`**: `request_id`, `thread_id`, `retrieval_latency_ms`, `model_latency_ms`, `total_latency_ms`, `model_name`, `decision`, `tokens` (TokenUsage).
- **`ChatResponse`**: `answer` (str), `citations` (List[str]), `thread_id` (str), `request_id` (str), `sources` (List[SourceDocument]), `metadata` (ChatResponseMetadata).
- **`HealthResponse`**: `status` (`"healthy"`), `app_name`, `version`, `timestamp`.
- **`ReadinessResponse`**: `status` (`"ready"` | `"degraded"` | `"not_ready"`), `app_name`, `version`, `details` (ReadinessDetails).

---

## 6. Detailed Subsystem Specifications

### 6.1 Document Ingestion Pipeline (Phase 2)
The ingestion subsystem transforms raw files into vectorized chunks:
1. **Deduplication Check:** Computes SHA-256 hash of raw file content. If a document record with matching hash exists in the `documents` collection and `--reindex` is false, processing is skipped.
2. **Multi-Format Parsers:**
   - `TextParser`: Decodes UTF-8 / Latin-1 text files.
   - `PDFParser`: Uses `pypdf.PdfReader` to extract text with page-number metadata.
   - `DocxParser`: Uses `python-docx` to extract text from Word documents with section headings.
   - `MarkdownParser`: Extracts structure, headers, and code blocks.
3. **Text Cleaning (`cleaner.py`):** Normalizes Unicode to NFKC format, replaces smart/curly quotes with ASCII equivalents, strips control characters, and removes redundant line breaks.
4. **Structure-Aware Chunking (`chunker.py`):** Uses `RecursiveCharacterTextSplitter` with separators `["\n\n", "\n", ". ", " ", ""]` maintaining paragraph integrity. Default `chunk_size=500`, `chunk_overlap=50`.
5. **Storage & Re-indexing:**
   - Inserts parent record into `documents` collection.
   - Deletes prior chunks for this document (if updating).
   - Generates batch embeddings via OpenAI (`dimensions=256`).
   - Inserts vectorized chunks into `vectors` collection.

### 6.2 MongoDB Atlas Hybrid Search & Reciprocal Rank Fusion (Phase 3)
1. **Query Preprocessing:** Normalizes user query using Unicode NFKC, cleans control characters, and strips leading negation hyphens that cause MongoDB `$text` syntax errors.
2. **Parallel Over-fetching:**
   - Candidate multiplier: `factor = 3` (fetches `top_k * 3` candidates from each modality).
   - Dense Vector Search: MongoDB `$vectorSearch` pipeline stage using cosine similarity against the 256-dimension embedding.
   - Sparse Full-Text Search: MongoDB `$text` search stage scoring via `textScore`.
3. **Reciprocal Rank Fusion (RRF):**
   - Merges candidate lists by `chunk_id`.
   - Formula:
     $$\text{RRF}(d) = \frac{w_{\text{vec}}}{k + r_{\text{vec}}(d)} + \frac{w_{\text{kw}}}{k + r_{\text{kw}}(d)}$$
     where $k = 60$, $w_{\text{vec}} = 0.7$, and $w_{\text{kw}} = 0.3$.
   - Why RRF? Vector cosine similarity ($[0, 1]$) and full-text TF-IDF scores ($[0, \infty)$) have incommensurable distributions. RRF relies strictly on ordinal rank positions, preventing raw score magnitude discrepancies from biasing retrieval.
4. **Pluggable Rerankers:**
   - `NoOpReranker`: Preserves pure RRF ranking order.
   - `CrossEncoderReranker`: Cross-attention re-scoring.
   - `LLMReranker`: Prompt-based LLM relevance scoring.

### 6.3 Agent Architecture & The 7 Explicit Responsibilities (Phase 4)
The agent is orchestrated by `RAGAgentRunner` (`src/mcp_rag_agent/agent/runner.py`) executing 7 core responsibilities:
1. **Query Understanding:** Evaluates intent, extracts entities, and formulates search query.
2. **Tool Selection:** Routes policy retrieval to `search_policy_documents` via the LangGraph ReAct cycle.
3. **Retrieval Execution:** Executes hybrid search with over-fetching, RRF fusion, and score tracking.
4. **Context Synthesis:** Aggregates chunks, deduplicates parent documents, tracks latency, and handles empty retrieval with explicit refusal.
5. **Grounded Answer Generation:** Enforces strict grounding via COSTAR system prompt with temperature=0.
6. **Citation Generation & Provenance Check:** Uses regex to validate that cited documents exist in the retrieved candidate set.
7. **Out-of-Scope Detection:** Detects queries outside Company XYZ policy scope and returns standard refusal without LLM invocation.

#### Dual Execution Modes (Architectural Parity)
- **Mode A: Direct Mode (`FEATURE_FLAG_MCPSERVER_ENABLED=false` - Default)**  
  Wraps `search_policy_documents_typed` in a `langchain_core.tools.StructuredTool`. Zero subprocess overhead, optimal for CI/CD, local testing, and production API deployments.
- **Mode B: MCP Mode (`FEATURE_FLAG_MCPSERVER_ENABLED=true`)**  
  Spawns FastMCP server via `MultiServerMCPClient` over `stdio` subprocess or connects to SSE endpoint. Adheres to open Model Context Protocol standard.

### 6.4 Persistent Conversation Memory & Checkpointing (Phase 5)
- **Checkpointer Factory (`core/checkpointer.py`):**
  - Inspects `FEATURE_FLAG_SESSION_MEMORY_ENABLED`.
  - When enabled, connects to MongoDB with a 2-second timeout and ping verification, initializing `MongoDBSaver` on `cfg.db_checkpoints_collection` and `cfg.db_checkpoint_writes_collection`.
  - **Graceful Fallback:** Catches network/timeout exceptions, logs a masked warning, and falls back to an in-memory `MemorySaver()`.
- **Session Isolation:** Executed with `config={"configurable": {"thread_id": th_id, "user_id": user_id}}`. Prevents cross-user data leakage. Resolves conversational coreference (e.g. "How many days for UK?" followed by "What about EU?").
- **Evaluation Isolation:** Evaluation runs generate isolated thread IDs (`eval_<uuid>`) to prevent history pollution.

### 6.5 RAG Safety & Grounding Guardrails (Phase 6)
- **4-Tier Decision Taxonomy:**
  - `SUPPORTED_BY_EVIDENCE`: Query in-scope, retrieval confidence $\ge 0.015$, grounding score $\ge 0.20$.
  - `INSUFFICIENT_EVIDENCE`: Retrieval confidence $< 0.015$, ungrounded answer, or fabricated citations. Returns mandatory refusal:  
    `"I couldn't find this information in the available policy content. Please consult Company XYZ HR or your manager for guidance."`
  - `OUT_OF_DOMAIN`: Coding, math, trivia, or prompt injection blocked immediately.
  - `SYSTEM_FAILURE`: Database or model execution failure.
- **Defense Mechanisms:**
  - Direct prompt injection filter for jailbreak / override patterns.
  - Indirect prompt injection sandboxing via `<retrieved_policy_chunk untrusted_data="true">` tags.
  - Regex citation validator cross-checking citations against retrieved chunk filenames.
  - Sensitive data masking: auto-redacts `sk-...` API keys, MongoDB URIs, passwords, and emails.
- **Adversarial Validation:** Tested with 30 adversarial unit tests in `tests/unit_tests/test_guardrails_adversarial.py`.

### 6.6 Quantitative Evaluation Framework (Phase 7)
- **Metrics Suite:**
  - Retrieval: `Recall@K`, `Precision@K`, `MRR` (Mean Reciprocal Rank), `Hit Rate`.
  - Generation: `Faithfulness`, `Answer Correctness` (50% semantic token F1 + 50% exact numeric match), `Answer Relevancy`, `Context Precision`, `Context Recall`.
  - Operational: Latencies (`retrieval`, `generation`, `total`), token usage, and cost estimation (USD).
- **Curated Benchmark Dataset (`evaluation/datasets/v1_policy_benchmark.json`):**
  - 15 test items covering leave, remote work, security, expenses, negative controls, and out-of-domain queries.
- **Runners & Reports:**
  - `ProductionEvalRunner`: Modes `"full"`, `"retrieval_only"`, and `"offline"`.
  - `RegressionComparator`: Compares baseline and candidate JSON runs, generating Markdown diff tables and detecting 7 failure categories (`RETRIEVAL_MISS`, `LOW_RECALL`, `HALLUCINATION`, `UNGROUNDED_REFUSAL`, `NUMERIC_MISMATCH`, `GUARDRAIL_BYPASS`, `LATENCY_BREACH`).

### 6.7 Production Observability & Tracing (Phase 8)
- **Contextvars Propagation:** Propagates `request_id`, `thread_id`, `user_id`, and active tracer asynchronously across all call layers without signature pollution.
- **7 Error Categories:** `RETRIEVAL_ERROR`, `MODEL_ERROR`, `MCP_ERROR`, `DATABASE_ERROR`, `VALIDATION_ERROR`, `GUARDRAIL_BLOCK`, `TIMEOUT`.
- **Structured Redaction:** `MaskingFilter` automatically redacts credentials, bearer tokens, and connection strings from console and logfiles.
- **Telemetry:** Injects run metadata and tags into LangSmith (`LANGSMITH_TRACING=true`).

### 6.8 Production FastAPI Backend (Phase 9)
- **Layered Architecture:** Routes (`routes/`) -> Services (`services/`) -> Agent Runner (`runner.py`).
- **Zero Chain-of-Thought (Zero-CoT) Standard:** Internal reasoning steps, scratchpad thoughts, prompt templates, and raw tool output strings are strictly filtered out of API responses. Clients receive only the synthesized answer, citations, sources, and latency metadata.
- **Endpoints:**
  - `POST /api/v1/chat`: Conversational RAG execution with Zero-CoT answer and rich source document metadata.
  - `POST /api/v1/conversations`: Creates isolated conversation thread.
  - `GET /api/v1/conversations/{thread_id}`: Retrieves cleaned dialogue history (user and assistant turns only).
  - `DELETE /api/v1/conversations/{thread_id}`: Deletes thread and purges MongoDB checkpoints.
  - `GET /api/v1/health`: Fast liveness probe returning HTTP 200.
  - `GET /api/v1/ready`: Deep readiness probe verifying MongoDB connection, LLM configuration, and session memory.
  - `GET /docs`: Interactive Swagger UI.

### 6.9 Enterprise Web UI (Phase 10)
- Mounted at `/ui` (with `/` redirecting to root information).
- Built with **Vanilla ES6 JavaScript, semantic HTML5, and modern CSS** (zero Node.js build step or bulky frontend framework dependencies).
- Features:
  - Sidebar with conversation history, active thread badges, and quick thread deletion.
  - Markdown message rendering via `marked.js` with code syntax blocks.
  - Source citation pill buttons beneath assistant answers.
  - Expandable slide-over citation drawer displaying document title, rank, RRF score, chunk ID, and full passage text.
  - Real-time diagnostic modal polling `/api/v1/health` and `/api/v1/ready`.
  - Keyboard shortcuts (`Cmd/Ctrl+K` for new conversation, `Enter` to send, `Shift+Enter` for multiline).
  - Modern dark theme, glassmorphism, responsive drawer, and latency badges (total, retrieval, model ms).

### 6.10 Containerization & Microservice Deployment (Phase 11)
- **Microservice Topology (`docker-compose.yml`):**
  1. `mongodb`: Official `mongo:7.0` container with health check.
  2. `api`: Multi-stage Python 3.11-slim container running Uvicorn under non-root user `appuser` (UID 10001).
  3. `frontend`: Alpine Nginx container running under non-root user `nginx` (UID 101) serving static UI on port 3000 and reverse proxying `/api/` to `api:8000`.
  4. `mcp-server`: Standalone FastMCP SSE service running under profile `mcp` (`docker compose --profile mcp up`).
- **Security & Hardening:**
  - Minimal runtime images with zero build compilers or package caches.
  - Zero hardcoded secrets; `.dockerignore` blocks `.env` and sensitive files.
  - Graceful shutdown signal handling (`SIGTERM` for Python, `SIGQUIT` for Nginx, `stop_grace_period: 20s`).
  - Container health checks with Compose dependency gating (`condition: service_healthy`).

### 6.11 CI/CD Automation & Quality Assurance (Phase 12)
- **Workflows (`.github/workflows/`):**
  - **`ci.yml`** (runs on every push/PR to main/master):
    1. `lint-and-format`: Validates code style with `black --check`, `isort --check`, and `flake8`.
    2. `unit-tests`: Matrix across Python `3.10` and `3.11` running 197+ unit tests in offline isolation with mock credentials. Measures code coverage with `pytest-cov` (target 75%) and uploads XML artifacts.
    3. `api-tests`: Executes FastAPI contract, route, and Zero-CoT validation tests.
    4. `build-validation`: Verifies `docker compose config`, builds container images in parallel, and checks Python wheel packaging (`python -m build`).
    5. `security-checks`: Scans AST for vulnerabilities using Bandit (`bandit -r src/ -ll`) and audits dependencies for known CVEs using `pip-audit`.
  - **`integration.yml`** (runs weekly on Mondays at 03:00 UTC and on-demand):
    - Deploys live MongoDB service container in GitHub Actions runner.
    - Executes live MongoDB CRUD, checkpoint, and FastMCP integration tests.
    - Optionally runs live OpenAI embedding tests when triggered with repository secrets.

---

## 7. Ingested Policy Corpus Summary

Located in `data/ingested_documents/policies/`:

1. **`1 - Remote Working.txt`**:
   - Employees may work remotely up to **3 days per week**.
   - Must be agreed in advance with line managers.
   - Staff must ensure data security and confidentiality from home offices.
2. **`2 - Expenses.txt`**:
   - Travel and accommodation for legitimate business purposes are reimbursable.
   - Meal costs reimbursable **only when working away from the home office**.
   - Expense claims must be submitted within **30 days** of incurring travel.
3. **`3 - Annual Leave.txt`**:
   - **United Kingdom (UK):** **25 days** paid annual leave. Request **2 weeks** in advance. Unused leave **cannot** be carried over except under exceptional circumstances.
   - **European Union (EU):** **30 days** paid annual leave. Request **4 weeks** in advance. Up to **5 days** carryover allowed.
   - **United States (US):** **15 days** paid annual leave. Request **1 week** in advance. Unused leave **cannot** be carried over.
4. **`4 - IT Security.txt`**:
   - Passwords must be at least **12 characters** and changed every **90 days**.
   - Company laptops must not be shared with anyone outside the organisation.
   - Security incidents or suspected breaches must be reported to IT **immediately**.
5. **`5 - Sustainability.txt`**:
   - Carbon target: Reduce carbon emissions by **20% by 2030**.
   - Business travel: Public transport is encouraged whenever possible.
   - Office waste: Mandatory use of designated recycling bins (paper, plastics, food).

---

## 8. COSTAR Prompt Engineering Specification

The system prompt is defined in `src/mcp_rag_agent/agent/prompts/system_prompt.py`:

```markdown
# Context
You are XYZ Policy Assistant, a RAG-based chatbot that answers questions about Company XYZ’s internal policies using only retrieved context from the policy corpus.

# Objective
Provide accurate, grounded, and concise answers strictly based on retrieved policy text.

# Style
Clear, factual, structured; prefer bullet points and short paragraphs; no jargon.

# Tone
Professional, neutral, helpful; no speculation or opinions.

# Audience
Company XYZ employees with varying policy knowledge.

# Response Rules
- Use only retrieved context; no assumptions or hallucinations.
- If context is missing or irrelevant:
    - Say: “I couldn’t find this information in the available policy content.”
    - Invite the user to rephrase.
- Provide short direct answer → cite relevant documents → offer follow-up help.
- Cite the relevant documents use: Reference:\n1. <document 1>\n2. <document 2>...
- Do not give legal/HR/compliance advice; redirect when needed.
- Out of scope: personal opinions, interpretations, decisions, or topics unrelated to XYZ policies.
```

---

## 9. Critical Gotchas, Resolved Technical Debt & Developer Pitfalls

### Resolved Technical Debt
1. **[RESOLVED] Hardcoded Ingestion Path in `index_documents.py`:**  
   *Previous issue:* Hardcoded path `D:\Projects\mcp-rag-agent\...` was used.  
   *Current state:* Fully resolved. Resolves dynamically using `Path(folder_path or config.ingested_doc_dir).resolve()`.
2. **[RESOLVED] Top-Level Async Execution on Import in `create_agent.py`:**  
   *Previous issue:* Top-level `asyncio.run()` executed immediately upon importing the module, crashing when MongoDB was offline.  
   *Current state:* Fully resolved. All instantiation logic is encapsulated inside explicit async factory `create_rag_agent_instance(...)`, and CLI test execution is protected behind `if __name__ == "__main__":`.

### Active Gotchas & Engineering Considerations
1. **MongoDB Atlas Search vs Local Community MongoDB:**  
   - In production and MongoDB Atlas clusters, `$vectorSearch` and `$text` run natively via Atlas Search indexes.
   - In local vanilla Docker Compose (`mongo:7.0`), `$vectorSearch` is an Atlas-specific feature. For full hybrid vector search locally, point `MONGODB_ATLAS_CLUSTER_URI` to a free MongoDB Atlas cluster, or run tests using the mocked unit test suite (`pytest tests/unit_tests -m "not integration"`).
2. **Embedding Dimension Alignment (256 vs 1536):**  
   - `config.py` specifies `embedding_dimension = 256` (`text-embedding-3-small` dimension reduction).
   - The MongoDB Atlas vector search index definition **must specify `numDimensions: 256`**. If an index was created with 1536 dimensions, MongoDB will throw `vector dimensions must match index dimensions`.
3. **MongoDB Text Index Requirement:**  
   - Hybrid search requires a text index on the `content` field of the `vectors` collection (`text_index`). If this index is missing, `$text` search queries will fail. The ingestion pipeline (`index_documents.py`) automatically ensures this index is created.
4. **Python Module Execution (`-m`):**  
   - Always run CLI commands using the module syntax from repository root:  
     `python -m mcp_rag_agent.embeddings.index_documents` or install the package in editable mode (`pip install -e .`). Direct script execution (`python src/.../script.py`) will fail with `ModuleNotFoundError`.
5. **Zero-CoT Response Contract:**  
   - The API layer strictly filters internal thoughts, prompts, and tool outputs. Do not expose `ToolMessage` or graph internal scratchpads to the frontend or API clients.

---

## 10. Standard Developer Workflows & CLI Cheat Sheet

### Environment Bootstrap
```bash
# Windows
start.cmd

# Linux / macOS
chmod +x start.sh && ./start.sh

# Configure environment variables
cp .env.example .env
# Edit .env and supply OPENAI_API_KEY, MONGODB_ATLAS_CLUSTER_URI, MONGODB_ATLAS_DB_NAME
```

### Document Ingestion
```bash
# Incremental ingestion (skips unchanged content hashes)
python -m mcp_rag_agent.embeddings.index_documents

# Force re-indexing of all documents
python -m mcp_rag_agent.embeddings.index_documents --reindex

# Clear all documents and vectors, then rebuild from scratch
python -m mcp_rag_agent.embeddings.index_documents --clear

# Custom folder ingestion with custom chunk size
python -m mcp_rag_agent.embeddings.index_documents --folder ./data/my_docs --chunk-size 600 --chunk-overlap 60
```

### Running the API & Web UI Locally
```bash
# Run FastAPI backend with Uvicorn (accessible at http://localhost:8000/ui and http://localhost:8000/docs)
uvicorn mcp_rag_agent.api:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

### Running with Docker Compose
```bash
# Launch standard production stack (mongodb, api, frontend)
docker compose up -d

# Check service health status
docker compose ps

# View live logs
docker compose logs -f api

# Launch including standalone FastMCP server
docker compose --profile mcp up -d

# Tear down stack and volumes
docker compose down -v
```

### Running Tests & Quality Checks
```bash
# Run all 197+ offline unit tests with coverage
pytest tests/unit_tests -v --cov=mcp_rag_agent --cov-report=term-missing

# Run only FastAPI contract tests
pytest tests/unit_tests/test_api.py -v

# Run only Guardrails adversarial tests (30 tests)
pytest tests/unit_tests/test_guardrails_adversarial.py -v

# Run live integration tests (requires reachable MongoDB)
pytest tests/integration_tests -m integration -v

# Run code style formatting checks
black --check src tests
isort --profile black --check src tests
flake8 src tests

# Run security AST audit & dependency CVE scan
bandit -r src/ -ll
pip-audit --desc
```

### Running the Quantitative Evaluation Harness
```bash
# Full evaluation on golden benchmark dataset
python -m evaluation.runners.eval_runner --dataset evaluation/datasets/v1_policy_benchmark.json --output evaluation/results/run_current.json --mode full

# Retrieval-only evaluation (no LLM generation cost)
python -m evaluation.runners.eval_runner --dataset evaluation/datasets/v1_policy_benchmark.json --output evaluation/results/retrieval_benchmark.json --mode retrieval_only

# Generate regression diff report between baseline and current run
python -m evaluation.reports.comparator --baseline evaluation/results/baseline_run.json --current evaluation/results/run_current.json --output evaluation/reports/regression_report.md
```

---

## 11. Phased Architecture & Roadmap Status

- [x] **Phase 1: Production Stabilization:** Async factories, configuration validation, dynamic logging, path resolution.
- [x] **Phase 2: Production Document Ingestion:** Multi-format parsing (TXT, PDF, DOCX, MD), Unicode sanitization, structure-aware chunking, SHA-256 deduplication, parent/chunk storage separation.
- [x] **Phase 3: Advanced Hybrid Retrieval:** Query preprocessing, candidate over-fetching (`factor=3`), Reciprocal Rank Fusion ($k=60$), score tracking, pluggable reranker abstraction (`NoOp`, `CrossEncoder`, `LLM`), Zero-CoT debug inspection.
- [x] **Phase 4: Production Agent Architecture:** 7 explicit agentic responsibilities, strongly typed tool schemas (`SearchDocumentsInput`/`SearchDocumentsOutput`), dual-mode architectural parity (Direct `StructuredTool` & MCP `FastMCP`), regex citation extraction, zero credential leakage.
- [x] **Phase 5: Persistent Conversation Memory:** Official LangGraph MongoDB checkpointer (`MongoDBSaver`), multi-turn dialogue continuity across restarts, strict thread isolation (`configurable.thread_id`), graceful database outage fallback to in-memory checkpointer.
- [x] **Phase 6: RAG Safety & Grounding Guardrails:** 4-tier decision taxonomy (`SUPPORTED_BY_EVIDENCE`, `INSUFFICIENT_EVIDENCE`, `OUT_OF_DOMAIN`, `SYSTEM_FAILURE`), `GuardrailResult` abstraction, confidence threshold ($0.015$), direct/indirect prompt injection defense, sandboxing, citation verification, and 30 adversarial unit tests.
- [x] **Phase 7: Quantitative Evaluation Framework:** Modular evaluation harness covering Retrieval metrics (Recall@K, Precision@K, MRR, Hit Rate), Generation metrics (Faithfulness, Answer Correctness with 50% numeric weight, Relevancy, Context Prec/Recall), Operational metrics (latencies, token counts, cost in USD), versioned benchmark dataset (`v1_policy_benchmark.json`), and regression diff comparator with 7 failure categories.
- [x] **Phase 8: Production Observability:** End-to-end tracing across Request → Agent → Tool → Retrieval → MongoDB → LLM → Response, thread-safe async correlation IDs (`contextvars`), structured JSON logging, zero-overhead secret redaction (`MaskingFilter`), 7 standardized error codes, token accounting & dynamic cost cards, and LangSmith telemetry.
- [x] **Phase 9: Production API Layer:** Asynchronous FastAPI backend, Zero-CoT output guarantee, correlation middleware (`X-Request-ID`, `X-Response-Time-Ms`), typed endpoints (`/api/v1/chat`, `/api/v1/conversations`, `/api/v1/health`, `/api/v1/ready`), and standardized error envelopes.
- [x] **Phase 10: Enterprise AI Knowledge Assistant UI:** Lightweight Vanilla ES6/HTML5/CSS web interface mounted at `/ui`. Demonstrates conversation history sidebar, markdown rendering, citation pills, slide-over document drawer, live readiness diagnostic modal, dark theme, and keyboard shortcuts (`Cmd/Ctrl+K`).
- [x] **Phase 11: Production Containerization & Deployment:** Microservice architecture via multi-stage Docker builds and Docker Compose (`mongodb`, `api`, `frontend`, `mcp-server`), minimal Debian slim and Alpine bases, strict non-root execution (`appuser` UID 10001, `nginx` UID 101), Compose healthcheck dependency gating (`condition: service_healthy`), graceful shutdown signals, and Nginx reverse proxy.
- [x] **Phase 12: CI/CD Automation & Quality Assurance:** GitHub Actions workflows (`ci.yml`, `integration.yml`) covering linting, Python multi-version test matrix (3.10, 3.11), 75% coverage reporting with `pytest-cov`, Docker build validation, Bandit AST security scans, `pip-audit` CVE checks, and live MongoDB integration tests.
- [ ] **Phase 13: Live Web Search Integration:** Planned integration of external search APIs (Tavily/Google) via `FEATURE_FLAG_WEBSEARCH_ENABLED` when policy corpus lacks sufficient grounding context.
