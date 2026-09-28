"""Authorization service providing role-based, resource-level, tool, and retrieval access controls."""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from mcp_rag_agent.security.rbac import (
    Permission,
    Role,
    SecuritySubject,
    has_permission,
)


class AuthorizationDecision(BaseModel):
    """Structured result of an authorization evaluation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    allowed: bool
    reason_code: str = Field(
        description="Standard authorization code, e.g. AUTHORIZED, PERMISSION_DENIED, RESOURCE_ACCESS_DENIED"
    )
    message: str = Field(description="Safe explanation of authorization result")
    permission: Optional[Permission] = None

    @classmethod
    def allow(
        cls,
        message: str = "Operation authorized.",
        permission: Optional[Permission] = None,
    ) -> "AuthorizationDecision":
        return cls(
            allowed=True,
            reason_code="AUTHORIZED",
            message=message,
            permission=permission,
        )

    @classmethod
    def deny(
        cls, reason_code: str, message: str, permission: Optional[Permission] = None
    ) -> "AuthorizationDecision":
        return cls(
            allowed=False,
            reason_code=reason_code,
            message=message,
            permission=permission,
        )


class AuthorizationService:
    """Enterprise authorization service for IT operations and support."""

    def can(
        self, subject: SecuritySubject, permission: Permission
    ) -> AuthorizationDecision:
        """Check role-level permission."""
        if not subject or not subject.user_id:
            return AuthorizationDecision.deny(
                "AUTHENTICATION_REQUIRED",
                "A valid authenticated subject is required for this operation.",
            )

        if has_permission(subject.role, permission):
            return AuthorizationDecision.allow(
                f"Role '{subject.role.value}' has permission '{permission.value}'.",
                permission=permission,
            )

        return AuthorizationDecision.deny(
            "PERMISSION_DENIED",
            f"Role '{subject.role.value}' does not have permission '{permission.value}'.",
            permission=permission,
        )

    def can_access_ticket(
        self, subject: SecuritySubject, ticket: Any, action: str = "read"
    ) -> AuthorizationDecision:
        """Check resource-level authorization for support tickets.

        Rules:
        - Employees can only view/read/comment on tickets where ticket.requester_id == subject.user_id.
        - Employees cannot view another user's tickets.
        - IT Support can access and update general tickets.
        - Security Analysts can access and escalate security-related tickets.
        - IT Admin and System Admin can access and manage all tickets.
        """
        if not subject or not subject.user_id:
            return AuthorizationDecision.deny(
                "AUTHENTICATION_REQUIRED", "Authentication required."
            )

        requester_id = getattr(ticket, "requester_id", None)
        if isinstance(ticket, dict):
            requester_id = ticket.get("requester_id")

        # Employee role resource scoping
        if subject.role == Role.EMPLOYEE:
            if action in ("read", "view", "view_own_tickets"):
                if requester_id == subject.user_id:
                    return AuthorizationDecision.allow(
                        "Employee authorized to view own ticket.",
                        Permission.VIEW_OWN_TICKETS,
                    )
                return AuthorizationDecision.deny(
                    "RESOURCE_ACCESS_DENIED",
                    "Employees are not authorized to view tickets requested by other users.",
                )
            elif action in ("comment", "update"):
                if requester_id == subject.user_id:
                    return AuthorizationDecision.allow(
                        "Employee authorized to comment on own ticket.",
                        Permission.UPDATE_TICKET,
                    )
                return AuthorizationDecision.deny(
                    "RESOURCE_ACCESS_DENIED",
                    "Employees cannot modify tickets requested by other users.",
                )
            return AuthorizationDecision.deny(
                "PERMISSION_DENIED", f"Employees cannot perform '{action}' on tickets."
            )

        # IT Support, Security Analyst, IT Admin, System Admin
        if subject.role in (
            Role.IT_SUPPORT,
            Role.IT_ADMIN,
            Role.SYSTEM_ADMIN,
            Role.SECURITY_ANALYST,
        ):
            return AuthorizationDecision.allow(
                f"Role '{subject.role.value}' is authorized to access support ticket.",
                Permission.VIEW_TICKET,
            )

        return AuthorizationDecision.deny("PERMISSION_DENIED", "Ticket access denied.")

    def can_access_user(
        self, subject: SecuritySubject, target_user_id: str
    ) -> AuthorizationDecision:
        """Check authorization to access user context."""
        if not subject or not subject.user_id:
            return AuthorizationDecision.deny(
                "AUTHENTICATION_REQUIRED", "Authentication required."
            )

        clean_target = (target_user_id or "").strip()
        if subject.role == Role.EMPLOYEE:
            if clean_target == subject.user_id:
                return AuthorizationDecision.allow(
                    "Employee authorized to view own profile context.",
                    Permission.VIEW_USER_CONTEXT,
                )
            return AuthorizationDecision.deny(
                "RESOURCE_ACCESS_DENIED",
                "Employees are not permitted to query profile context of other users.",
            )

        if has_permission(subject.role, Permission.VIEW_USER_CONTEXT):
            return AuthorizationDecision.allow(
                f"Role '{subject.role.value}' authorized to view user context.",
                Permission.VIEW_USER_CONTEXT,
            )

        return AuthorizationDecision.deny(
            "PERMISSION_DENIED",
            "Access to user context denied.",
            Permission.VIEW_USER_CONTEXT,
        )

    def can_access_device(
        self, subject: SecuritySubject, device: Any
    ) -> AuthorizationDecision:
        """Check authorization to access device context."""
        if not subject or not subject.user_id:
            return AuthorizationDecision.deny(
                "AUTHENTICATION_REQUIRED", "Authentication required."
            )

        device_user_id = getattr(device, "user_id", None)
        if isinstance(device, dict):
            device_user_id = device.get("user_id")

        if subject.role == Role.EMPLOYEE:
            if device_user_id == subject.user_id:
                return AuthorizationDecision.allow(
                    "Employee authorized to view own device details.",
                    Permission.VIEW_DEVICE_CONTEXT,
                )
            return AuthorizationDecision.deny(
                "RESOURCE_ACCESS_DENIED",
                "Employees cannot query hardware or configuration details of devices assigned to other users.",
            )

        if has_permission(subject.role, Permission.VIEW_DEVICE_CONTEXT):
            return AuthorizationDecision.allow(
                f"Role '{subject.role.value}' authorized to view device context.",
                Permission.VIEW_DEVICE_CONTEXT,
            )

        return AuthorizationDecision.deny(
            "PERMISSION_DENIED",
            "Access to device context denied.",
            Permission.VIEW_DEVICE_CONTEXT,
        )

    def can_execute_tool(
        self,
        subject: SecuritySubject,
        tool_name: str,
        tool_args: Optional[dict[str, Any]] = None,
    ) -> AuthorizationDecision:
        """Check authorization before executing an MCP operational or diagnostic tool."""
        if not subject or not subject.user_id:
            return AuthorizationDecision.deny(
                "AUTHENTICATION_REQUIRED",
                "Authentication required to execute operational tools.",
            )

        args = tool_args or {}

        if tool_name == "search_policy_documents":
            return self.can(subject, Permission.SEARCH_KNOWLEDGE)

        elif tool_name == "get_user_context":
            target_user = args.get("user_id", "")
            return self.can_access_user(subject, target_user)

        elif tool_name == "get_device_info":
            target_user = args.get("user_id")
            if target_user:
                return self.can_access_user(subject, target_user)
            if subject.role == Role.EMPLOYEE and not args.get("device_id"):
                # Employee querying without parameters
                return AuthorizationDecision.deny(
                    "RESOURCE_ACCESS_DENIED",
                    "Employees must specify their own user_id or assigned device_id.",
                )
            return self.can(subject, Permission.VIEW_DEVICE_CONTEXT)

        elif tool_name == "check_service_status":
            return self.can(subject, Permission.CHECK_SERVICE_STATUS)

        elif tool_name == "create_ticket":
            # If requester_id is provided and caller is Employee, requester_id must match caller
            requester_id = args.get("requester_id")
            if (
                subject.role == Role.EMPLOYEE
                and requester_id
                and requester_id != subject.user_id
            ):
                return AuthorizationDecision.deny(
                    "RESOURCE_ACCESS_DENIED",
                    "Employees can only create support tickets on their own behalf.",
                )
            return self.can(subject, Permission.CREATE_TICKET)

        elif tool_name == "update_ticket":
            if subject.role == Role.EMPLOYEE:
                return AuthorizationDecision.allow(
                    "Employee update evaluated at resource level.",
                    Permission.UPDATE_TICKET,
                )
            return self.can(subject, Permission.UPDATE_TICKET)

        elif tool_name == "execute_runbook_step":
            return self.can(subject, Permission.SEARCH_KNOWLEDGE)

        return AuthorizationDecision.deny(
            "PERMISSION_DENIED",
            f"Execution of unmapped tool '{tool_name}' is prohibited.",
        )

    def filter_documents_for_subject(
        self, subject: SecuritySubject, chunks: list[Any]
    ) -> list[Any]:
        """Filter retrieved document chunks BEFORE LLM synthesis based on access level.

        Access Levels:
        - 'public': All roles
        - 'internal': All authenticated enterprise roles
        - 'confidential': IT_SUPPORT, IT_ADMIN, SECURITY_ANALYST, SYSTEM_ADMIN
        - 'security_ops': SECURITY_ANALYST, SYSTEM_ADMIN
        """
        if not subject:
            return []

        allowed_levels: set[str] = {"public"}
        if subject.role == Role.EMPLOYEE:
            allowed_levels.update({"internal"})
        elif subject.role == Role.IT_SUPPORT:
            allowed_levels.update({"internal", "confidential"})
        elif subject.role == Role.SECURITY_ANALYST:
            allowed_levels.update({"internal", "confidential", "security_ops"})
        elif subject.role in (Role.IT_ADMIN, Role.SYSTEM_ADMIN):
            allowed_levels.update(
                {"internal", "confidential", "security_ops", "admin_only"}
            )

        filtered: list[Any] = []
        for chunk in chunks:
            # Metadata access level extraction
            meta = getattr(chunk, "metadata", None)
            if isinstance(chunk, dict):
                meta = chunk.get("metadata", {})
            elif meta is None:
                meta = {}

            doc_level = meta.get("access_level", "internal").lower().strip()
            if doc_level in allowed_levels:
                filtered.append(chunk)

        return filtered
