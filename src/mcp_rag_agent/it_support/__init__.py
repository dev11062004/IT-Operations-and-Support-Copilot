"""IT Operations & Support Copilot — domain module.

This package provides the IT Support layer built on top of the existing
MCP RAG Agent infrastructure. It adds:

- Core data models (ITIssue, Ticket, Incident, SupportUser, Device)
- Intent classification (rule-based + LLM-assisted)
- Runbook engine (Phase 13-C)
- Ticket lifecycle management (Phase 13-B)
- Incident detection (Phase 13-B)
- User/device context (Phase 13-D)
- Security, RBAC, and audit (Phase 13-E)
"""

from mcp_rag_agent.it_support.models import (
    Device,
    ITCategory,
    ITIssue,
    Priority,
    SupportUser,
    Ticket,
    TicketStatus,
)

__all__ = [
    "ITCategory",
    "Priority",
    "TicketStatus",
    "ITIssue",
    "Ticket",
    "SupportUser",
    "Device",
]
