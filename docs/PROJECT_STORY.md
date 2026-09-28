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

Phase 13-E adds enterprise security controls for the IT Operations & Support Copilot:
Role-Based Access Control (RBAC) with 5 strongly typed roles (`EMPLOYEE`, `IT_SUPPORT`,
`SECURITY_ANALYST`, `IT_ADMIN`, `SYSTEM_ADMIN`); 17 granular permissions; an authoritative
permission matrix; resource-level access control enforcing cross-user isolation for tickets,
user contexts, and devices; pre-retrieval document access-level filtering ensuring restricted
documents never enter the LLM context; MCP operational tool authorization; deterministic risk
classification (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`); human-in-the-loop (HITL) approval workflows
with strict separation of duties (preventing AI agents or requesters from approving their own
high-risk actions); and MongoDB-backed structured audit logging (`it_audit_logs`) with recursive
secret/credential redaction.

Phase 13-F adds the comprehensive IT-Specific Evaluation suite and Admin Operations Platform.
The evaluation framework introduces a versioned 105-scenario benchmark (`v1_it_support_benchmark.json`)
testing knowledge retrieval, multi-step troubleshooting, operational outages, security attacks, multi-turn
dialogue, and negative controls. Twelve IT-specific metrics (`intent_accuracy`, `runbook_selection_accuracy`,
`runbook_completion_rate`, `ticket_creation_success_rate`, `ticket_classification_accuracy`,
`duplicate_ticket_rate`, `tool_selection_accuracy`, `escalation_accuracy`, `escalation_rate`,
`unnecessary_escalation_rate`, `missed_escalation_rate`, `unauthorized_blocking_rate`) are computed
alongside classical RAG metrics. The regression comparator flags 9 distinct failure categories in
transparent markdown reports (`evaluation/reports/it_support_regression_report.md`).
The FastAPI backend exposes authorized Admin endpoints (`/api/v1/admin/tickets`, `/api/v1/admin/incidents`,
`/api/v1/admin/metrics`, `/api/v1/admin/evaluation`, `/api/v1/admin/audit`) protected by RBAC dependencies.
The web UI is enhanced with a Role Selector, Active Runbook Step Tracker widget (Step X of Y, current action,
completed milestones, next step), KPI Cards, Ticket Management Queue & Detail Modal, Incident Viewer,
Evaluation Benchmark visualizer, and Sanitized Audit Log inspector.

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
- Phase 13-E modules created: 9 (`rbac.py`, `authorization.py`, `approval.py`, `audit.py`, `__init__.py`, and 4 test suites: `test_rbac.py`, `test_authorization.py`, `test_approval.py`, `test_audit.py`, `test_security_regression.py`)
- Phase 13-E unit tests added: 44 covering RBAC permission matrix (11), authorization and pre-retrieval document filtering (12), HITL approval and separation of duties (10), structured audit logging and credential redaction (5), and cross-user isolation / privilege escalation security regressions (6)
- Phase 13-F modules created: 7 (`v1_it_support_benchmark.json`, `it_metrics.py`, `admin_service.py`, `admin.py`, `test_it_evaluation.py`, `test_admin_api.py`, `IT_EVALUATION.md`)
- Phase 13-F unit tests added: 11 (5 evaluation & regression comparator, 6 admin API & RBAC protection)
- IT Benchmark scenarios evaluated: 105
- Measured Intent accuracy: 83.8%
- Measured Runbook selection accuracy: 84.4%
- Measured Runbook completion rate: 80.0%
- Measured Ticket creation success rate: 100.0%
- Measured Escalation accuracy: 100.0%
- Measured Unauthorized action blocking rate: 100.0%
- Total IT Support unit tests: 143/143 passed
- Total offline unit test suite: 340/340 passed in 23.01s (197 baseline + 27 Phase 13-A + 16 Phase 13-B + 17 Phase 13-C + 28 Phase 13-D + 44 Phase 13-E + 11 Phase 13-F)
