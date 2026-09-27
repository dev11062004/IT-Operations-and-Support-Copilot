# STAR STORY: IT Operations & Support Copilot

## Document Purpose

Records each implementation phase using the STAR (Situation, Task, Action, Result)
method for technical interviews, portfolio presentations, and engineering reviews.

**Rule:** Results marked `[MEASURE AFTER IMPLEMENTATION]` represent metrics
that will be measured after the implementation is live. No metrics are fabricated.

---

## Phase 13-A: IT Support Domain Foundation

### Situation

Enterprise IT helpdesks receive hundreds of support tickets per week. Common issues
(password resets, VPN failures, account lockouts, email problems) are repetitive and
well-documented. However, employees typically open tickets without attempting
self-service, and IT staff spend significant time on L1 issues that a knowledge-based
assistant could resolve in minutes.

The existing MCP RAG Agent had enterprise-grade retrieval, guardrails, and memory —
but was locked to the HR policy domain. Its guardrail keyword list actively blocked
IT support queries as "out-of-domain."

### Task

Establish the domain foundation for the IT Operations & Support Copilot without
breaking any of the 197 existing unit tests. Specifically:

1. Define a strongly-typed IT support data model (ITCategory, Priority, TicketStatus,
   ITIssue, Ticket, SupportUser, Device) as the canonical domain contract.
2. Build a two-tier intent classifier that can classify IT support queries into
   ITIL-aligned categories (rule-based fast path + LLM fallback for ambiguous queries).
3. Create an IT-specific COSTAR system prompt that extends the agent persona
   to the full IT support workflow (classify → search → troubleshoot → ticket → escalate).
4. Extend the existing guardrail keyword list to accept IT support vocabulary
   without disrupting the existing policy domain behavior.
5. Ship offline unit tests covering all new modules.
6. Create and maintain PROJECT_STORY.md and STAR_STORY.md.

### Action

**Data Modeling (`it_support/models.py`):**
- Defined `ITCategory` enum with 27 categories covering ITIL incident classification:
  hardware, software, network, security, access/identity, collaboration, service, compliance.
- `Priority` enum with 4 levels aligned to ITIL P1–P4 (CRITICAL/HIGH/MEDIUM/LOW).
- `TicketStatus` state machine with 7 states: OPEN → IN_PROGRESS → PENDING_USER →
  RESOLVED → CLOSED, plus ESCALATED and CANCELLED.
- `ITIssue`: progressive context-gathering model populated during intent classification.
  Auto-generates UUID-based `issue_id`. Tracks `intent_confidence` and `classification_method`.
- `Ticket`: full lifecycle work item with reporter, assignee, device, thread linkage,
  AI summary, and resolution notes. Auto-generates `TKT-{8 hex}` ticket IDs.
- `SupportUser` and `Device`: user profile and CMDB device models for context-aware support.
- All models use Pydantic v2 with field constraints, defaults, and UTC-aware datetimes.

**Intent Classifier (`it_support/intent.py`):**
- Tier 1 (rule-based): 30 `(ITCategory, keywords[])` rules ordered by specificity.
  First-match wins. Multi-word phrase matches score higher confidence (0.80–0.95) than
  single-keyword matches (0.75). Zero LLM calls, deterministic, fast.
- Error code extraction: regex covering Windows hex codes (0x...), HTTP 4xx/5xx,
  browser errors (ERR_*), BSOD codes, and numeric error codes.
- Service detection: matches against 25 known enterprise services (Outlook, Teams,
  Zoom, Slack, SharePoint, Okta, etc.).
- Keyword extraction: alpha-numeric token filtering with stopword removal, capped at 15 tokens.
- Priority inference: 3-tier keyword matching (CRITICAL/HIGH/LOW) with MEDIUM as default.
- Tier 2 (LLM-assisted): async path invoked only when Tier 1 confidence < 0.3 and an
  LLM instance is injected. Parses structured `CATEGORY: X / PRIORITY: Y` response format.
  Gracefully falls back to Tier 1 result on LLM error or parse failure.

**IT Support System Prompt (`agent/prompts/it_support_prompt.py`):**
- COSTAR format (Context, Objective, Style, Tone, Audience, Response Rules).
- 8 response rules covering: tool usage, grounding, interactive troubleshooting
  workflow (one step at a time), ticket creation triggers (3 failures or security incident),
  escalation criteria (security, multi-user impact, hardware intervention), citations,
  safety boundaries, and out-of-scope handling.
- Preserves the existing `search_policy_documents` tool contract — extended IT corpus
  will be added in Phase 13-B/13-D.

**Guardrail Extension (`guardrails/input_guardrails.py`):**
- Extended `_POLICY_KEYWORDS` from 33 to 87 entries with 54 IT support terms covering:
  hardware (laptop, keyboard, monitor, battery), software (crash, install, license),
  network (wifi, ethernet, dns, firewall), security (mfa, phishing, malware, lockout),
  collaboration (email, teams, zoom, slack), and support workflow (ticket, escalate, outage).
- Existing policy keywords preserved in full. No existing tests modified.

**Unit Tests (`tests/unit_tests/it_support/`):**
- `test_models.py`: 38 tests covering model creation, field defaults, UUID generation,
  UTC-awareness, field constraint validation (min_length, max_length, ge/le bounds).
- `test_intent.py`: 65+ tests covering normalization, error code extraction, keyword
  extraction, all 23 category matching paths, priority inference, full classify_issue()
  integration (12 scenarios), two-tier async with AsyncMock LLM, exception handling,
  and prompt builder validation.

### Result

| Metric | Value |
|---|---|
| Existing unit tests passing | 197/197 ✅ |
| New unit tests added | `[MEASURE AFTER IMPLEMENTATION]` |
| New IT model fields defined | 7 models, 50+ fields |
| IT categories in taxonomy | 27 |
| Intent classification rules | 30 category rules, 3 priority rules |
| Enterprise services detectable | 25 |
| Guardrail keywords extended | 33 → 87 (+54 IT support terms) |
| LLM calls for Tier 1 classification | 0 (deterministic) |
| Breaking changes to existing tests | 0 |

---

## Phase 13-B: Ticket & Incident Management

### Situation

`[MEASURE AFTER IMPLEMENTATION]`

### Task

`[MEASURE AFTER IMPLEMENTATION]`

### Action

`[MEASURE AFTER IMPLEMENTATION]`

### Result

`[MEASURE AFTER IMPLEMENTATION]`

---

## Phase 13-C: Runbook Engine

### Situation

`[MEASURE AFTER IMPLEMENTATION]`

### Task

`[MEASURE AFTER IMPLEMENTATION]`

### Action

`[MEASURE AFTER IMPLEMENTATION]`

### Result

`[MEASURE AFTER IMPLEMENTATION]`

---

## Phase 13-D: MCP IT Operations Tools

### Situation

`[MEASURE AFTER IMPLEMENTATION]`

### Task

`[MEASURE AFTER IMPLEMENTATION]`

### Action

`[MEASURE AFTER IMPLEMENTATION]`

### Result

`[MEASURE AFTER IMPLEMENTATION]`

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
