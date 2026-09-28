"""FastAPI dependencies for injecting configuration, application services, and RBAC authorization."""

from typing import Optional

from fastapi import Header, HTTPException, Request, status

from mcp_rag_agent.api.services.admin_service import AdminAPIService
from mcp_rag_agent.api.services.chat_service import ChatService
from mcp_rag_agent.api.services.conversation_service import ConversationService
from mcp_rag_agent.api.services.it_ticket_service import ITTicketAPIService
from mcp_rag_agent.core.config import Config, config
from mcp_rag_agent.it_support.incidents.service import IncidentService
from mcp_rag_agent.it_support.incidents.store import IncidentStore
from mcp_rag_agent.it_support.tickets.service import TicketService
from mcp_rag_agent.it_support.tickets.store import TicketStore
from mcp_rag_agent.mongodb import MongoDBClient
from mcp_rag_agent.security.audit import AuditService, AuditStore
from mcp_rag_agent.security.authorization import AuthorizationService
from mcp_rag_agent.security.rbac import (
    Permission,
    Role,
    SecuritySubject,
    get_current_subject,
    has_permission,
)

# Global singleton fallbacks for testing or standalone execution
_default_chat_service: Optional[ChatService] = None
_default_conversation_service: Optional[ConversationService] = None
_default_it_ticket_service: Optional[ITTicketAPIService] = None
_default_admin_service: Optional[AdminAPIService] = None
_auth_service: AuthorizationService = AuthorizationService()


def get_config(request: Request) -> Config:
    """Dependency provider for application configuration."""
    if hasattr(request.app.state, "config") and request.app.state.config is not None:
        return request.app.state.config
    return config


def get_chat_service(request: Request) -> ChatService:
    """Dependency provider for ChatService, retrieving from app.state."""
    if (
        hasattr(request.app.state, "chat_service")
        and request.app.state.chat_service is not None
    ):
        return request.app.state.chat_service

    global _default_chat_service
    if _default_chat_service is None:
        _default_chat_service = ChatService()
    return _default_chat_service


def get_conversation_service(request: Request) -> ConversationService:
    """Dependency provider for ConversationService, retrieving from app.state."""
    if (
        hasattr(request.app.state, "conversation_service")
        and request.app.state.conversation_service is not None
    ):
        return request.app.state.conversation_service

    global _default_conversation_service
    if _default_conversation_service is None:
        _default_conversation_service = ConversationService()
    return _default_conversation_service


def get_it_ticket_service(request: Request) -> ITTicketAPIService:
    """Build the IT ticket dependency with the shared MongoDB client abstraction."""
    if (
        hasattr(request.app.state, "it_ticket_service")
        and request.app.state.it_ticket_service is not None
    ):
        return request.app.state.it_ticket_service
    global _default_it_ticket_service
    if _default_it_ticket_service is None:
        cfg = get_config(request)
        store = TicketStore(
            MongoDBClient(cfg.db_url, cfg.db_name), cfg.db_tickets_collection
        )
        _default_it_ticket_service = ITTicketAPIService(TicketService(store))
    return _default_it_ticket_service


def get_admin_service(request: Request) -> AdminAPIService:
    """Build the AdminAPIService dependency with shared stores."""
    if (
        hasattr(request.app.state, "admin_service")
        and request.app.state.admin_service is not None
    ):
        return request.app.state.admin_service
    global _default_admin_service
    if _default_admin_service is None:
        cfg = get_config(request)
        mongo = MongoDBClient(cfg.db_url, cfg.db_name)
        t_store = TicketStore(mongo, cfg.db_tickets_collection)
        inc_store = IncidentStore(mongo, "it_incidents")
        aud_store = AuditStore(mongo, "it_audit_logs")
        _default_admin_service = AdminAPIService(
            ticket_service=TicketService(t_store),
            incident_service=IncidentService(inc_store),
            audit_service=AuditService(aud_store),
        )
    return _default_admin_service


def get_current_security_subject(
    request: Request,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    x_user_department: Optional[str] = Header(None, alias="X-User-Department"),
    x_user_support_tier: Optional[str] = Header(None, alias="X-User-Support-Tier"),
) -> SecuritySubject:
    """Extract and validate the authenticated SecuritySubject from request headers or context."""
    # Check contextvar first
    ctx_subj = get_current_subject()
    if ctx_subj is not None and not x_user_id and not x_user_role:
        return ctx_subj

    user_id = x_user_id or "anonymous_user"
    role_str = (x_user_role or "employee").lower().strip()
    try:
        role = Role(role_str)
    except ValueError:
        role = Role.EMPLOYEE

    return SecuritySubject(
        user_id=user_id,
        role=role,
        department=x_user_department,
        support_tier=x_user_support_tier,
    )


def require_admin_role(
    subject: SecuritySubject = None,
    request: Request = None,
) -> SecuritySubject:
    """RBAC dependency requiring IT_ADMIN or SYSTEM_ADMIN role."""
    subj = subject or get_current_security_subject(request)
    if subj.role not in (Role.IT_ADMIN, Role.SYSTEM_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "PERMISSION_DENIED",
                "message": f"Role '{subj.role.value}' is not authorized to access administrator endpoints.",
                "required_roles": ["it_admin", "system_admin"],
            },
        )
    return subj


def require_audit_permission(
    subject: SecuritySubject = None,
    request: Request = None,
) -> SecuritySubject:
    """RBAC dependency requiring VIEW_AUDIT_LOGS permission."""
    subj = subject or get_current_security_subject(request)
    if not has_permission(subj.role, Permission.VIEW_AUDIT_LOGS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "PERMISSION_DENIED",
                "message": f"Role '{subj.role.value}' does not have permission 'view_audit_logs'.",
                "required_permission": "view_audit_logs",
            },
        )
    return subj
