# IT Operations & Support Copilot — Implementation Roadmap

## Codebase Status: Phases 1–12 Complete ✅

---

## Transformation Strategy

The existing system is a **policy/knowledge RAG assistant** (Phase 1–12 complete).  
The goal is to extend it into a full **IT Operations & Support Copilot** via new domain-oriented modules.

**Core principle:** Extend, never replace. All existing subsystems remain untouched unless an explicit extension is required.

---

## Phase Plan

### Phase 13-A — IT Support Domain Foundation (THIS PHASE)
**Goal:** Establish the `it_support/` module with core data models, an IT-specific intent classifier, and an extended system prompt. Update guardrails to accept IT support vocabulary. Create initial unit tests.

**Files to create:**
- `src/mcp_rag_agent/it_support/__init__.py`
- `src/mcp_rag_agent/it_support/models.py`  — ITIssue, Ticket, Incident, SupportUser, Device, ITCategory enum, Priority enum
- `src/mcp_rag_agent/it_support/intent.py`  — ITIntentClassifier (rule-based + LLM-assisted)
- `src/mcp_rag_agent/agent/prompts/it_support_prompt.py` — IT Support COSTAR prompt
- `tests/unit_tests/it_support/test_models.py`
- `tests/unit_tests/it_support/test_intent.py`
- `docs/PROJECT_STORY.md`
- `docs/STAR_STORY.md`

**Guardrail extension:**  
Add IT support keywords to `_POLICY_KEYWORDS` in `input_guardrails.py` so IT queries aren't blocked as out-of-domain.

---

### Phase 13-B — Ticket & Incident Management (Future)
- `it_support/tickets/` — TicketStore (MongoDB-backed), CRUD, lifecycle state machine
- `it_support/incidents/` — IncidentStore, known-incident detection
- New API routes: `POST /api/v1/it/tickets`, `GET /api/v1/it/tickets/{id}`, `PATCH /api/v1/it/tickets/{id}`

---

### Phase 13-C — Runbook Engine (Future)
- `it_support/runbooks/` — RunbookRegistry, RunbookStep, RunbookExecutor
- LangGraph sub-graph for guided troubleshooting (Step → Evaluate → Branch)
- Integration with agent runner via new tool: `execute_runbook_step`

---

### Phase 13-D — MCP IT Operations Tools (Future)
- `it_support/users/` — UserContext (RBAC lookup from MongoDB users collection)
- `it_support/devices/` — DeviceContext
- `it_support/services/` — ServiceStatusChecker
- Extend `mcp_server/tools.py` with IT tools: `get_user_context`, `get_device_info`, `check_service_status`, `create_ticket`, `update_ticket`

---

### Phase 13-E — Security, RBAC & Human Approval (Future)
- `security/rbac.py` — Role definitions, permission matrix
- `security/authorization.py` — Permission check middleware
- `security/approval.py` — High-risk action approval workflow
- `security/audit.py` — Audit event logger (MongoDB-backed)

---

### Phase 13-F — IT-Specific Evaluation & Admin UI (Future)
- New benchmark dataset: `evaluation/datasets/v1_it_support_benchmark.json`
- New evaluation metrics: intent_accuracy, ticket_creation_success_rate, runbook_completion_rate, escalation_rate
- Admin UI extension: ticket dashboard, incident viewer, resolution analytics

---

## Architecture Decision Record

| Decision | Rationale |
|---|---|
| New `it_support/` module, not a new package | Keeps single `mcp_rag_agent` namespace, consistent with existing patterns |
| Rule-based + LLM intent classifier | Deterministic for known patterns (fast, testable), LLM fallback for ambiguous queries |
| Extend existing guardrails | Avoids duplicate keyword lists; single source of truth |
| MongoDB for tickets/incidents | Consistent with existing data store; no new infrastructure required |
| LangGraph sub-graph for runbooks | Reuses existing runtime; proven pattern |
| Feature flags for all new capabilities | Preserves backward compatibility; direct mode unaffected |
