# PROJECT STORY: IT Operations & Support Copilot

## Document Purpose

This document provides the high-level product story for the transformation of the
MCP RAG Agent into an enterprise IT Operations & Support Copilot.
It is intended as onboarding documentation for new engineers and as evidence
for technical reviews, architecture reviews, and stakeholder presentations.

---

## Origin

The MCP RAG Agent was originally built (Phases 1–12) as an enterprise policy
knowledge assistant: employees could ask questions about HR policies (remote work,
annual leave, expenses, IT security, sustainability) and receive grounded answers
with source citations.

The system demonstrated:
- MongoDB Atlas hybrid vector + keyword retrieval (Reciprocal Rank Fusion)
- LangGraph ReAct agent with persistent multi-turn memory
- FastMCP / Model Context Protocol integration
- Zero-hallucination guardrails (citation validation, grounding score, confidence threshold)
- Quantitative evaluation (RAGAS + native retrieval metrics)
- Production FastAPI + Nginx deployment (Docker Compose)
- GitHub Actions CI/CD with security scanning

The core infrastructure was production-grade and extensible. The opportunity was
to evolve the domain from "policy Q&A" to "IT Operations & Support" — a much
richer domain with interactive workflows, tool execution, and ticket lifecycle management.

---

## Architecture Transformation

The transformation strategy is **extension, not replacement**.

All existing subsystems (retrieval, guardrails, memory, evaluation, observability,
API, UI, Docker, CI/CD) are preserved and extended rather than replaced.

New domain-oriented modules are introduced under `src/mcp_rag_agent/`:

```
it_support/           ← NEW: IT domain models, intent, runbooks, tickets, incidents
security/             ← PLANNED: RBAC, authorization, approval, audit
```

The existing `agent/`, `guardrails/`, `retrieval/`, `api/`, and `mcp_server/`
subsystems are extended minimally to support the new domain.

---

## Phased Evolution

| Phase | Domain | Status |
|---|---|---|
| 1–12 | Policy RAG Agent (Complete) | ✅ Done |
| 13-A | IT Support Domain Foundation | ✅ Done |
| 13-B | Ticket & Incident Management | 🔜 Planned |
| 13-C | Runbook Engine | 🔜 Planned |
| 13-D | MCP IT Operations Tools | 🔜 Planned |
| 13-E | Security, RBAC & Human Approval | 🔜 Planned |
| 13-F | IT-Specific Evaluation & Admin UI | 🔜 Planned |

---

## Key Engineering Principles Applied

1. **Domain Fidelity Over Generic Chatbot**: Every feature is traceable to a real
   IT support workflow step. The system follows: Intent → Classify → Retrieve → Troubleshoot → Resolve/Escalate → Ticket.

2. **No Fabrication**: The system never claims a ticket was created unless a tool
   created it, never invents troubleshooting steps not in the knowledge base,
   and never reports metrics not measured.

3. **Defense-in-Depth**: Guardrails are extended (not replaced) to accept IT vocabulary.
   The existing 4-tier decision taxonomy, confidence thresholds, and citation validation
   remain enforced.

4. **Testability First**: Every new module ships with offline unit tests before
   integration. The LLM fallback path in the intent classifier is mockable by
   design (dependency injection via `llm=` parameter).

5. **Backward Compatibility**: Existing 197+ unit tests continue to pass after
   each phase. The policy RAG mode is unchanged when `FEATURE_FLAG_IT_SUPPORT=false`.
