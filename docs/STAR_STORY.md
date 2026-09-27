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

`[MEASURE AFTER IMPLEMENTATION]`

### Task

`[MEASURE AFTER IMPLEMENTATION]`

### Action

`[MEASURE AFTER IMPLEMENTATION]`

### Result

`[MEASURE AFTER IMPLEMENTATION]`

---

## Phase 13-F: IT-Specific Evaluation & Admin UI

### Situation

`[MEASURE AFTER IMPLEMENTATION]`

### Task

`[MEASURE AFTER IMPLEMENTATION]`

### Action

`[MEASURE AFTER IMPLEMENTATION]`

### Result

`[MEASURE AFTER IMPLEMENTATION]`

