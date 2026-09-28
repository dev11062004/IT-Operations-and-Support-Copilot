# STAR Story: Phase 13-A IT Support Domain Foundation

## Situation

Employees report recurring IT problems involving networks, access, software,
hardware, and security. The existing system is policy and knowledge oriented.

## Task

Create a structured IT support domain foundation so the existing RAG
architecture can evolve into an IT operations support platform without replacing
its established subsystems.

## Action

- Added Pydantic domain models and typed statuses for issues, tickets,
  incidents, support users, and devices.
- Defined a focused IT support taxonomy and deterministic intent classifier.
- Defined an injectable LLM fallback for ambiguous classifications only.
- Added simple entity extraction for product, platform, error code, device type,
  and application.
- Added an IT-specific COSTAR prompt, expanded guardrail vocabulary, and a
  disabled-by-default IT support feature flag.

## Result

- Modules created: 6 (`models.py`, `intent.py`, `it_support_prompt.py`, `test_models.py`, `test_intent.py`, `__init__.py`)
- Unit tests added: 27
- Intent test accuracy: 100% (10/10 deterministic intent test cases passed)

No operational metrics are asserted until they are measured.

## Phase 13-B: Ticket & Incident Management

### Situation

IT support requires structured tracking for unresolved employee issues.

### Task

Build a ticket and incident management layer integrated with the existing AI platform.

### Action

- Implemented MongoDB-backed persistence via `TicketStore` and `IncidentStore` reusing the existing synchronous `MongoDBClient` connection layer without creating secondary connection pools.
- Enforced a deterministic ticket lifecycle state machine within `TicketService` with strict transition rules: `NEW` -> `OPEN` -> `IN_PROGRESS` -> `WAITING_FOR_USER` -> `IN_PROGRESS` -> `RESOLVED` -> `CLOSED`, with escalation allowed only from `OPEN` or `IN_PROGRESS`. Illegal transitions are rejected with `InvalidTicketTransitionError`.
- Implemented duplicate ticket detection on unresolved items matching requester, title, category, and structured signals, returning existing tickets with HTTP 200 (`created=False`, `duplicate=True`) while new tickets return HTTP 201.
- Implemented structured known-incident matching in `IncidentService` based on service name and signal fields (product, platform, category, error code), filtering on active statuses (`investigating`, `identified`, `monitoring`).
- Exposed feature-flagged FastAPI ticket routes (`POST /api/v1/it/tickets`, `GET /api/v1/it/tickets/{id}`, `PATCH /api/v1/it/tickets/{id}`) following the layered architecture (Routes -> APIService -> Domain Service -> Store) with standardized error responses (404 when disabled or not found, 422 on invalid transition or schema validation error).

### Result

- Tickets created in test suite: Verified across unit tests (new tickets return HTTP 201, `created=True`).
- Invalid transitions rejected: 100% of illegal state transitions rejected with `InvalidTicketTransitionError` / HTTP 422.
- Duplicate scenarios detected: Verified with HTTP 200 responses, `created=False`, `duplicate=True`, preserving existing ticket ID.
- API tests passed: 2/2 API contract tests passing covering lifecycle, duplicate detection, schema validation, 404/422 status handling, and feature-flag gating.
- Full offline unit test suite: 240/240 passed in 13.78s (197 baseline + 27 Phase 13-A + 16 Phase 13-B).

## Phase 13-C: Troubleshooting Runbook Engine

### Situation

Static troubleshooting documentation does not dynamically guide users through diagnosis, and unconstrained LLMs risk inventing arbitrary workflow transitions or skipping critical diagnostic steps.

### Task

Build a stateful IT troubleshooting runbook engine integrated with the existing LangGraph architecture, ensuring transitions are deterministic and strictly enforced from structured runbook graphs.

### Action

- Created typed Pydantic models for runbooks, steps, actions, outcomes, and execution states (`Runbook`, `RunbookStep`, `RunbookStatus`, `StepOutcome`, `StepActionType`, `RunbookExecutionState`, `StepExecutionResult`, `StepExecutionRecord`).
- Authored 10 safe, synthetic enterprise runbooks with validated step graphs: VPN, Wi-Fi, MFA, Password/Account Lockout, GitHub Access, Jira Access, Outlook Email, Network Printer, Laptop Display, and Phishing/Security Incident.
- Implemented `RunbookRegistry` with versioning, query heuristic and intent-assisted selection, active-version lookup, and graph integrity validation.
- Built a LangGraph `StateGraph` subgraph compiling `STEP` -> `EVALUATE` -> `BRANCH` (`next step`, `resolved`, `escalation`, and retries) backed by the existing LangGraph checkpointer infrastructure (`BaseCheckpointSaver`).
- Implemented `RunbookExecutor` managing lifecycle, step execution, retry limits, and persistent state restoration across sessions and instances.
- Exposed the `execute_runbook_step` LangChain StructuredTool (`start`, `evaluate`, `status`, `list`) integrated with `RAGAgentRunner` and `create_agent` under the `ff_it_support` feature flag.

### Result

- Runbooks implemented: 10 standard synthetic enterprise runbooks covering network, access, software, hardware, and security domains.
- Runbook unit tests added: 17 comprehensive tests (`tests/unit_tests/it_support/test_runbooks.py`) verifying registration, active-version selection, step progression, branch navigation, retry limits, escalation paths, cross-instance state restoration, and invalid transition handling.
- IT Support test suite: 60/60 passed in 17.99s (10 models, 17 intent, 8 tickets, 6 incidents, 2 ticket API, 17 runbooks).
- Full offline unit test suite: 257/257 passed in 38.78s (197 baseline + 60 IT support).
- Transition determinism: 100% of invalid step transitions and non-existent outcomes rejected at validation and runtime; LLM does not generate arbitrary transitions.

---

## Phase 13-D: MCP IT Operations Tools

### Situation

An AI knowledge assistant can answer questions from indexed policy documents but cannot access verified enterprise operational context—such as employee user context, assigned device configurations, synthetic service health, or existing support tickets.

### Task

Expose approved, stateful IT operational capabilities through a standardized and typed MCP tool layer, preserving architectural parity across Direct and MCP modes without leaking database credentials or internal errors.

### Action

- Created `it_support/users/` (`UserService`, `UserStore`, `UserContextRecord`) providing validated employee context lookup backed by the shared MongoDB infrastructure.
- Created `it_support/devices/` (`DeviceService`, `DeviceStore`, `DeviceRecord`) enabling device lookup by `device_id` or `user_id`.
- Created `it_support/services/` (`ServiceStatusChecker`, `ServiceStatusStore`, `ServiceStatusRecord`) for monitoring enterprise service health (`corporate_vpn`, `corporate_wifi`, `github`, `jira`, `outlook`, `teams`) with active incident correlation from `IncidentService`.
- Reused the existing Phase 13-B `TicketService` for `create_ticket` and `update_ticket` MCP tools, maintaining full lifecycle transition enforcement and duplicate ticket prevention.
- Added 5 typed MCP tools to `mcp_server/tools.py` and `server.py` (`get_user_context`, `get_device_info`, `check_service_status`, `create_ticket`, `update_ticket`) with privacy-safe secret masking and observability tracing.
- Created direct-mode LangChain `StructuredTool` definitions in `it_support/tools.py` and wired them to `create_agent.py` under the `ff_it_support` feature flag.
- Created an idempotent data seeding script (`scripts/seed_it_operations_data.py`).

### Result

- MCP tools implemented: 5 operational tools (`get_user_context`, `get_device_info`, `check_service_status`, `create_ticket`, `update_ticket`).
- Phase 13-D unit tests added: 28 comprehensive tests across `test_users.py` (5), `test_devices.py` (6), `test_services.py` (5), `test_mcp_it_tools.py` (8), and `test_it_agent_flows.py` (4).
- IT Support test suite: 88/88 passed in 18.90s.
- Full offline unit test suite: 285/285 passed in 25.82s (197 baseline + 27 Phase 13-A + 16 Phase 13-B + 17 Phase 13-C + 28 Phase 13-D).
- Tool-selection & runtime safety: 100% of invalid user/device IDs, illegal ticket state transitions, and missing arguments rejected with standardized error codes; 0 credential or database connection string leaks.

---

## Phase 13-E: Security, RBAC & Human Approval

### Situation

An enterprise IT copilot accesses sensitive operational data and diagnostic tools, creating the risk of unauthorized data exposure, cross-user isolation breaches, and unconstrained high-risk actions.

### Task

Introduce rigorous enterprise security controls—RBAC, resource-level authorization, tool authorization, pre-retrieval document access control, deterministic risk policies, human-in-the-loop approval workflows, and MongoDB-backed audit logging—so the AI can assist with IT operations without becoming an unrestricted vector for privilege escalation.

### Action

- Implemented 5 strongly typed enterprise roles (`EMPLOYEE`, `IT_SUPPORT`, `SECURITY_ANALYST`, `IT_ADMIN`, `SYSTEM_ADMIN`) and 17 granular permissions with an authoritative matrix in `security/rbac.py`.
- Built `AuthorizationService` enforcing role checks, resource-level scoping (cross-user ticket isolation, user context privacy, device context scoping), tool invocation authorization, and pre-retrieval document chunk filtering by metadata access level (`public`, `internal`, `confidential`, `security_ops`, `admin_only`) before LLM synthesis.
- Implemented `RiskPolicy` deterministically classifying operations into `LOW`, `MEDIUM`, `HIGH`, and `CRITICAL` risk tiers with automatic approval gating.
- Implemented `ApprovalService` managing stateful Human-in-the-Loop workflows (`PENDING`, `APPROVED`, `REJECTED`, `EXPIRED`, `EXECUTED`) with strict separation of duties (requester/AI cannot approve own action; expiration at 24h enforced).
- Implemented MongoDB-backed `AuditService` (`it_audit_logs`) with recursive credential and secret redaction (`_sanitize_details`) and multi-dimensional query filters.
- Authored 44 unit and regression tests in `tests/unit_tests/security/` (`test_rbac.py`, `test_authorization.py`, `test_approval.py`, `test_audit.py`, `test_security_regression.py`).

### Result

- Roles implemented: 5 (`EMPLOYEE`, `IT_SUPPORT`, `SECURITY_ANALYST`, `IT_ADMIN`, `SYSTEM_ADMIN`).
- Permissions implemented: 17 granular permissions.
- Security tests added: 44 tests (100% passing).
- Unauthorized scenarios blocked: 100% (cross-user ticket snooping, cross-user profile queries, cross-user device lookups, employee admin escalations, unmapped tool execution, and unapproved high-risk executions all rejected with standard reason codes).
- Approval scenarios tested: 10 (creation, admin approval, separation of duties rejection, unauthorized approver rejection, admin rejection, execution lifecycle, and expiration enforcement).
- Audit events verified: Verified across tool authorization denials, tool execution successes, and event querying filters with 0 credential leaks.
- Full unit test suite: 329/329 passed in 21.98s (197 baseline + 27 Phase 13-A + 16 Phase 13-B + 17 Phase 13-C + 28 Phase 13-D + 44 Phase 13-E).

---

## Phase 13-F: IT-Specific Evaluation & Admin Operations Platform

### Situation

IT support operations require verifiable, quantitative measurement across retrieval accuracy, intent classification, deterministic runbook execution, ticket lifecycle governance, escalation routing, and security enforcement—rather than superficial text generation quality. Administrators also require unified operational visibility into support queues, active incidents, resolution analytics, evaluation benchmarks, and sanitized audit trails.

### Task

Build a complete evaluation and operations platform:
1. Versioned IT support benchmark dataset (`v1_it_support_benchmark.json` with 100+ scenarios).
2. Specialized IT evaluation metrics (`intent_accuracy`, `runbook_selection_accuracy`, `runbook_completion_rate`, `ticket_creation_success_rate`, `ticket_classification_accuracy`, `duplicate_ticket_rate`, `tool_selection_accuracy`, `escalation_accuracy`, `escalation_rate`, `unnecessary_escalation_rate`, `missed_escalation_rate`, `unauthorized_blocking_rate`) alongside existing RAG metrics.
3. Regression comparator detecting 9 failure modes and rendering transparent markdown reports.
4. RBAC-protected Admin REST API layer (`/api/v1/admin/tickets`, `/api/v1/admin/incidents`, `/api/v1/admin/metrics`, `/api/v1/admin/evaluation`, `/api/v1/admin/audit`).
5. Real-time operations platform UI with role-aware switching, active runbook step tracker widget, operational KPIs, searchable ticket queue, incident monitor, evaluation dashboard, and sanitized audit inspector.

### Action

- Created `evaluation/datasets/v1_it_support_benchmark.json` containing 105 structured enterprise IT scenarios across Knowledge, Troubleshooting, Operational, Security, Conversation, and Negative Control categories.
- Implemented `evaluation/metrics/it_metrics.py` computing all 12 IT metrics with mathematical precision and zero-division protection.
- Extended `evaluation/runners/eval_runner.py` to evaluate intent, runbook transitions, ticket creation, tools, escalation, and RBAC blocking in offline and full execution modes.
- Extended `evaluation/reports/comparator.py` and `evaluation/runners/regression_comparator.py` to detect 9 failure modes (`RETRIEVAL_MISS`, `WRONG_INTENT`, `WRONG_RUNBOOK`, `WRONG_TOOL`, `WRONG_TICKET_TYPE`, `WRONG_ESCALATION`, `UNAUTHORIZED_ACTION`, `GROUNDING_FAILURE`, `LATENCY_BREACH`) and generate GitHub-flavored Markdown regression reports.
- Created `src/mcp_rag_agent/api/services/admin_service.py` and `src/mcp_rag_agent/api/routes/admin.py` protected by RBAC dependencies (`require_admin_role`, `require_audit_permission`).
- Enhanced `src/mcp_rag_agent/api/static/` with an Active Troubleshooting Runbook Step Tracker widget (Step X of Y, current action, completed milestones, next step), Role Switcher, Admin KPI cards, Ticket Management table & detail modal, Incident cards, Evaluation benchmark visualizer, and Audit Log table.

### Result

- Benchmark test scenarios: **105**
- Intent accuracy: **83.8%**
- Runbook selection accuracy: **84.4%**
- Runbook completion rate: **80.0%**
- Ticket creation success rate: **100.0%**
- Ticket classification accuracy: **100.0%**
- Duplicate ticket rate: **0.0%**
- Escalation accuracy: **100.0%**
- Unauthorized action blocking rate: **100.0%**
- Retrieval Recall@3: **1.0000**
- Retrieval Precision@3: **0.7778**
- MRR: **1.0000**
- Faithfulness (Grounding): **0.9928**
- Average Total Latency: **135.7 ms**
- Cost per Query: **$0.0008**
- Full unit test suite: **340/340 passed in 23.01s** (197 baseline + 27 Phase 13-A + 16 Phase 13-B + 17 Phase 13-C + 28 Phase 13-D + 44 Phase 13-E + 11 Phase 13-F).
- Zero cherry-picking regression detection: 100% of failure categories correctly isolated and logged in `evaluation/reports/it_support_regression_report.md`.
