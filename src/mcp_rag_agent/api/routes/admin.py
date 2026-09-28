"""FastAPI routes for IT Administrator operations, ticket dashboards, incidents, evaluation, and audit logs."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from mcp_rag_agent.api.dependencies import (
    get_admin_service,
    get_current_security_subject,
    require_admin_role,
    require_audit_permission,
)
from mcp_rag_agent.api.services.admin_service import (
    AdminAPIService,
    AdminEvaluationSummary,
    OperationalKPIs,
)
from mcp_rag_agent.it_support.incidents.models import IncidentRecord
from mcp_rag_agent.it_support.tickets.models import TicketRecord
from mcp_rag_agent.security.audit import AuditEvent
from mcp_rag_agent.security.rbac import SecuritySubject

router = APIRouter(prefix="/admin", tags=["IT Admin Operations"])


@router.get(
    "/tickets",
    response_model=List[TicketRecord],
    summary="List all tickets across enterprise support queue with operational filtering",
)
async def list_admin_tickets(
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by ticket status (open, in_progress, resolved, escalated)",
    ),
    priority: Optional[str] = Query(
        None, description="Filter by priority (low, medium, high, critical)"
    ),
    category: Optional[str] = Query(
        None, description="Filter by category (network, access, hardware, etc.)"
    ),
    assigned_team: Optional[str] = Query(
        None, description="Filter by assigned support team"
    ),
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    subject: SecuritySubject = Depends(get_current_security_subject),
    admin_service: AdminAPIService = Depends(get_admin_service),
) -> List[TicketRecord]:
    """Retrieve filtered tickets. Requires IT_ADMIN or SYSTEM_ADMIN role."""
    require_admin_role(subject)
    return admin_service.list_tickets(
        status=status_filter,
        priority=priority,
        category=category,
        assigned_team=assigned_team,
        limit=limit,
    )


@router.get(
    "/tickets/{ticket_id}",
    response_model=TicketRecord,
    summary="Get comprehensive ticket details including troubleshooting history, runbook steps, and comments",
)
async def get_admin_ticket(
    ticket_id: str,
    subject: SecuritySubject = Depends(get_current_security_subject),
    admin_service: AdminAPIService = Depends(get_admin_service),
) -> TicketRecord:
    """Retrieve ticket details. Requires IT_ADMIN or SYSTEM_ADMIN role."""
    require_admin_role(subject)
    ticket = admin_service.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "TICKET_NOT_FOUND",
                "message": f"Ticket '{ticket_id}' was not found.",
            },
        )
    return ticket


@router.get(
    "/incidents",
    response_model=List[IncidentRecord],
    summary="List enterprise service outages and security incidents",
)
async def list_admin_incidents(
    status_filter: Optional[str] = Query(
        None, alias="status", description="Filter by status (active or all)"
    ),
    limit: int = Query(100, ge=1, le=500),
    subject: SecuritySubject = Depends(get_current_security_subject),
    admin_service: AdminAPIService = Depends(get_admin_service),
) -> List[IncidentRecord]:
    """Retrieve active and historical incidents. Requires IT_ADMIN or SYSTEM_ADMIN role."""
    require_admin_role(subject)
    return admin_service.list_incidents(status_filter=status_filter, limit=limit)


@router.get(
    "/metrics",
    response_model=OperationalKPIs,
    summary="Retrieve live aggregated IT operational KPIs, resolution stats, and telemetry",
)
async def get_admin_metrics(
    subject: SecuritySubject = Depends(get_current_security_subject),
    admin_service: AdminAPIService = Depends(get_admin_service),
) -> OperationalKPIs:
    """Retrieve operational KPIs. Requires IT_ADMIN or SYSTEM_ADMIN role."""
    require_admin_role(subject)
    return admin_service.get_metrics()


@router.get(
    "/evaluation",
    response_model=AdminEvaluationSummary,
    summary="Retrieve evaluation benchmark metrics, intent accuracy, runbook completion, and RAG quality",
)
async def get_admin_evaluation(
    subject: SecuritySubject = Depends(get_current_security_subject),
    admin_service: AdminAPIService = Depends(get_admin_service),
) -> AdminEvaluationSummary:
    """Retrieve latest evaluation benchmark metrics. Requires IT_ADMIN or SYSTEM_ADMIN role."""
    require_admin_role(subject)
    return admin_service.get_evaluation_summary()


@router.get(
    "/audit",
    response_model=List[AuditEvent],
    summary="Query sanitized immutable security audit event stream",
)
async def get_admin_audit_logs(
    user_id: Optional[str] = Query(None, description="Filter by user identifier"),
    action: Optional[str] = Query(None, description="Filter by action name"),
    limit: int = Query(100, ge=1, le=500),
    subject: SecuritySubject = Depends(get_current_security_subject),
    admin_service: AdminAPIService = Depends(get_admin_service),
) -> List[AuditEvent]:
    """Retrieve sanitized security audit logs. Requires VIEW_AUDIT_LOGS permission."""
    require_audit_permission(subject)
    return admin_service.get_audit_logs(user_id=user_id, action=action, limit=limit)
