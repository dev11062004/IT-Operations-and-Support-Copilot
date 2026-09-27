# Project Story: Phase 13-A IT Support Foundation

The MCP RAG Agent remains a policy and knowledge assistant. Phase 13-A extends
that system with a small, persistence-free IT support domain layer so later phases
can add ticketing, incidents, runbooks, and IT operations safely.

The extension provides typed Pydantic contracts for issues, tickets, incidents,
users, and devices; a stable support taxonomy; deterministic intent
classification with an optional LLM fallback; an IT-specific COSTAR prompt; and
expanded guardrail vocabulary. The existing retrieval, LangGraph, MCP, memory,
guardrails, evaluation, observability, FastAPI, frontend, Docker, and CI/CD
systems are not replaced.

Phase 13-A intentionally added no ticket database, ticket API, incident store,
runbook executor, operational MCP tools, RBAC, approval workflow, or admin
dashboard. Feature rollout remains disabled by default through
`FEATURE_FLAG_IT_SUPPORT_ENABLED=false`.

Phase 13-B adds the MongoDB-backed ticket and incident lifecycle layer. Ticket
state changes are deterministic and validated by the domain service; duplicate
tickets and known active incidents are detected from structured fields before
new work is created. The ticket HTTP API remains behind the IT support feature
flag.

Phase 13-C adds a stateful IT troubleshooting runbook engine integrated with the
existing LangGraph architecture. The engine provides 10 synthetic enterprise
runbooks (VPN, Wi-Fi, MFA, Password Lockout, GitHub Access, Jira Access,
Outlook, Printer, Laptop Display, Phishing Incident) with strictly validated
step transition graphs. A LangGraph subgraph coordinates the STEP -> EVALUATE ->
BRANCH (`next step`, `resolved`, `escalation`) state machine, backed by the
system's existing checkpointer. Step transitions are deterministic and cannot be
invented by the LLM. An `execute_runbook_step` LangChain StructuredTool integrates
the executor with the agent runner under the IT support feature flag.

Phase 13-D adds the MCP IT Operations Tool Layer, exposing 5 typed operational
tools (`get_user_context`, `get_device_info`, `check_service_status`, `create_ticket`,
`update_ticket`) across FastMCP server mode and Direct mode LangChain StructuredTools.
The tools are backed by domain services and stores for users (`it_support/users/`),
devices (`it_support/devices/`), and service statuses (`it_support/services/`),
reusing the existing MongoDB connection layer and Phase 13-B ticket services.
RBAC and human approval (Phase 13-E) and admin dashboards/evaluation (Phase 13-F)
remain future phases.

## Evidence

- Phase 13-A modules created: 6 (`models.py`, `intent.py`, `it_support_prompt.py`, `test_models.py`, `test_intent.py`, `__init__.py`)
- Phase 13-A unit tests added: 27 (10 models, 17 intent)
- Intent test accuracy: 100% (10/10 deterministic intent query test cases passed)
- Phase 13-B modules created: 14 (tickets domain, incidents domain, API routes/schemas/services, and 3 test suites)
- Phase 13-B unit tests added: 16 (8 tickets, 6 incidents, 2 ticket API)
- Phase 13-C modules created: 8 (`models.py`, `runbook_definitions.py`, `registry.py`, `graph.py`, `executor.py`, `tools.py`, `__init__.py`, `test_runbooks.py`)
- Phase 13-C unit tests added: 17 covering registration, active-versioning, heuristic/intent selection, step execution, branching, retries, escalations, cross-instance state restoration, and invalid transitions
- Phase 13-D modules created: 17 (users domain [4], devices domain [4], services domain [4], tools/script [2], and 5 test suites)
- Phase 13-D unit tests added: 28 covering user lookups, device info, service status, incident correlation, ticket creation/duplicate detection/updates via MCP, and direct agent workflow tool execution
- Total IT Support unit tests: 88/88 passed
- Total offline unit test suite: 285/285 passed (197 baseline + 27 Phase 13-A + 16 Phase 13-B + 17 Phase 13-C + 28 Phase 13-D)

