# Enterprise Security, RBAC & Human Approval Model (Phase 13-E)

This document specifies the enterprise security architecture, Role-Based Access Control (RBAC), resource-level authorization, tool authorization, pre-retrieval document access control, deterministic risk policies, human-in-the-loop (HITL) approval workflows, and MongoDB-backed audit logging for the **IT Operations & Support Copilot**.

---

## 1. Architectural Principles & Separation of Concerns

The security subsystem strictly decouples five discrete concerns to prevent security bypasses:

```text
Authentication (SecuritySubject)
       ↓
Authorization (AuthorizationService & RBAC Matrix)
       ↓
Risk Assessment (RiskPolicy)
       ↓
Human Approval (ApprovalService)
       ↓
Audit Logging (AuditService)
```

1. **Authentication / Identity**: Encapsulated in `SecuritySubject(user_id, role, department, support_tier)`. Context propagation is managed via thread-safe `contextvars`.
2. **Authorization**: Deterministic verification of role permissions (`can`), resource ownership (`can_access_ticket`, `can_access_user`, `can_access_device`), tool invocation permissions (`can_execute_tool`), and pre-retrieval document visibility (`filter_documents_for_subject`).
3. **Risk**: Pure deterministic classification into `LOW`, `MEDIUM`, `HIGH`, and `CRITICAL` tiers with explicit approval gate triggers.
4. **Approval**: Stateful human-in-the-loop lifecycle with strict **Separation of Duties** (an AI agent or requester can never approve their own actions).
5. **Audit**: Immutable, structured event logging to MongoDB with recursive credential/secret sanitization.

---

## 2. Roles & Permissions

### 2.1 Enterprise Roles (`Role` Enum)

| Role Enum | Description | Intended Actors |
| :--- | :--- | :--- |
| `EMPLOYEE` | Standard enterprise employee with least-privilege self-service access. | End users, non-IT staff |
| `IT_SUPPORT` | Tier 1/2 IT support engineers resolving tickets and running diagnostic runbooks. | Helpdesk, Tier 1/2 Support |
| `SECURITY_ANALYST` | Infosec team members investigating alerts, threats, and security incidents. | SOC, InfoSec Engineers |
| `IT_ADMIN` | IT operations leadership with ticket, incident, and knowledge management authority. | IT Operations Leads, Managers |
| `SYSTEM_ADMIN` | Elevated system administrators with global operational and security privileges. | Enterprise Sysadmins, Root Admins |

### 2.2 Granular Permissions (`Permission` Enum)

- `SEARCH_KNOWLEDGE`: Query general enterprise knowledge base and policy articles.
- `VIEW_OWN_TICKETS`: View and comment on tickets requested by the caller.
- `VIEW_TICKET`: View support tickets across all users.
- `CREATE_TICKET`: Create a new support ticket.
- `UPDATE_TICKET`: Update ticket lifecycle status, team assignment, or comments.
- `ESCALATE_TICKET`: Escalate a ticket to higher support tiers or specialized engineering teams.
- `VIEW_INCIDENT`: View general IT infrastructure incidents and service disruptions.
- `VIEW_SECURITY_INCIDENT`: View confidential security incidents, breach data, and threat reports.
- `UPDATE_SECURITY_INCIDENT`: Modify and update confidential security incident records.
- `VIEW_USER_CONTEXT`: Query verified employee profile data, role, department, and account status.
- `VIEW_DEVICE_CONTEXT`: Query hardware specs, OS versions, installed client software, and compliance status.
- `CHECK_SERVICE_STATUS`: Check real-time synthetic operational status of enterprise services.
- `MANAGE_TICKETS`: Administrative ticket reconfiguration, bulk actions, and ownership reassignment.
- `MANAGE_INCIDENTS`: Declare, escalate, update, and resolve enterprise-wide IT incidents.
- `MANAGE_KNOWLEDGE`: Author, update, publish, or deprecate knowledge base and runbook documents.
- `EXECUTE_HIGH_RISK_ACTION`: Execute privileged operations (e.g. account unlocks, credential resets) following approval.
- `APPROVE_HIGH_RISK_ACTION`: Review, approve, or reject high-risk operational requests submitted by users or AI agents.
- `VIEW_AUDIT_LOGS`: Query and inspect immutable security audit records.

---

## 3. Authoritative Role-to-Permission Matrix

The master permission matrix is statically defined in `mcp_rag_agent.security.rbac.ROLE_PERMISSIONS`:

| Permission | `EMPLOYEE` | `IT_SUPPORT` | `SECURITY_ANALYST` | `IT_ADMIN` | `SYSTEM_ADMIN` |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `SEARCH_KNOWLEDGE` | **YES** | **YES** | **YES** | **YES** | **YES** |
| `VIEW_OWN_TICKETS` | **YES** | **YES** | **YES** | **YES** | **YES** |
| `VIEW_TICKET` | NO | **YES** | **YES** | **YES** | **YES** |
| `CREATE_TICKET` | **YES** | **YES** | **YES** | **YES** | **YES** |
| `UPDATE_TICKET` | NO* | **YES** | **YES** | **YES** | **YES** |
| `ESCALATE_TICKET` | NO | **YES** | **YES** | **YES** | **YES** |
| `VIEW_INCIDENT` | NO | **YES** | **YES** | **YES** | **YES** |
| `VIEW_SECURITY_INCIDENT`| NO | NO | **YES** | NO | **YES** |
| `UPDATE_SECURITY_INCIDENT`| NO | NO | **YES** | NO | **YES** |
| `VIEW_USER_CONTEXT` | NO* | **YES** | **YES** | **YES** | **YES** |
| `VIEW_DEVICE_CONTEXT` | **YES** | **YES** | **YES** | **YES** | **YES** |
| `CHECK_SERVICE_STATUS` | **YES** | **YES** | **YES** | **YES** | **YES** |
| `MANAGE_TICKETS` | NO | NO | NO | **YES** | **YES** |
| `MANAGE_INCIDENTS` | NO | NO | NO | **YES** | **YES** |
| `MANAGE_KNOWLEDGE` | NO | NO | NO | **YES** | **YES** |
| `EXECUTE_HIGH_RISK_ACTION` | NO | NO | **YES** | NO | **YES** |
| `APPROVE_HIGH_RISK_ACTION` | NO | NO | NO | **YES** | **YES** |
| `VIEW_AUDIT_LOGS` | NO | NO | NO | **YES** | **YES** |

*\*Note: Employees can update comments on tickets and query profile/device context scoped strictly to their own identity via Resource-Level Authorization.*

---

## 4. Resource-Level Authorization

Role-level permission is necessary but insufficient. The `AuthorizationService` enforces fine-grained resource ownership checks:

### 4.1 Cross-User Ticket Isolation
- **Rule**: An `EMPLOYEE` can only view or add comments to tickets where `ticket.requester_id == subject.user_id`.
- **Violation**: If User A (`EMP-1001`) requests User B's (`EMP-1002`) ticket, access is rejected immediately with code `RESOURCE_ACCESS_DENIED`.

### 4.2 User Context Scoping
- **Rule**: An `EMPLOYEE` can query profile context for `user_id == subject.user_id`. Querying other employees' profiles is denied (`RESOURCE_ACCESS_DENIED`). Support and administrative roles can query any employee within operational scope.

### 4.3 Device Context Scoping
- **Rule**: An `EMPLOYEE` can only view hardware and software configurations for devices assigned to their `user_id`. Querying another user's device is rejected (`RESOURCE_ACCESS_DENIED`).

---

## 5. Pre-Retrieval Authorization (Document Access Filtering)

To prevent confidential data leaks into LLM context windows, document authorization is evaluated **BEFORE** retrieved chunks are synthesized:

```text
User Query
    ↓
Hybrid Retrieval (Vector + BM25)
    ↓
filter_documents_for_subject(subject, chunks)
    ↓ (Restricted documents stripped)
Sanitized Chunks injected into LLM Context
    ↓
LLM Grounded Synthesis
```

### Access Level Classifications:
1. `public`: Accessible to all callers.
2. `internal`: Standard internal documents; accessible to all authenticated enterprise employees.
3. `confidential`: Sensitive IT runbooks; restricted to `IT_SUPPORT`, `SECURITY_ANALYST`, `IT_ADMIN`, `SYSTEM_ADMIN`.
4. `security_ops`: Security playbooks and breach responses; restricted strictly to `SECURITY_ANALYST` and `SYSTEM_ADMIN`.
5. `admin_only`: Root administration keys and infrastructure docs; restricted to `IT_ADMIN` and `SYSTEM_ADMIN`.

---

## 6. MCP Operational Tool Authorization

All operational and diagnostic MCP tools execute within the security context:

```text
Tool Request (e.g. get_user_context, update_ticket)
    ↓
Extract Caller SecuritySubject (Parameter or ContextVar)
    ↓
AuthorizationService.can_execute_tool(subject, tool_name, args)
    ├── DENIED ──→ AuditService.log_event(DENIED) ──→ Return error (status="error")
    └── ALLOWED ──→ Resource Check ──→ Execute Domain Service ──→ AuditService.log_event(AUTHORIZED)
```

---

## 7. Deterministic Risk Model & Approval Gate

### 7.1 Risk Classification (`RiskPolicy`)

| Risk Tier | Operations | Approval Required? |
| :--- | :--- | :---: |
| `LOW` | `search_policy_documents`, `get_device_info`, `check_service_status`, `view_ticket` | **NO** |
| `MEDIUM` | `create_ticket`, `update_ticket`, `add_comment`, `get_user_context`, `escalate_ticket` | **NO** |
| `HIGH` | `credential_reset`, `password_reset`, `account_disable`, `account_unlock`, `device_block` | **YES** |
| `CRITICAL` | `privileged_access_change`, `grant_admin`, `revoke_admin`, `access_revocation` | **YES** |

### 7.2 Human-in-the-Loop (HITL) Approval Lifecycle

```text
Requested High-Risk Action
       ↓
RiskPolicy.classify_risk (HIGH / CRITICAL)
       ↓
ApprovalService.request_approval (Status: PENDING, Expiry: 24h)
       ↓
Human Admin Review (Role: IT_ADMIN / SYSTEM_ADMIN)
       ├── REJECT ──→ Status: REJECTED (Reason recorded, execution permanently blocked)
       └── APPROVE ──→ Status: APPROVED (Approver recorded, approved_at set)
                             ↓
             ApprovalService.execute_approved_action
                             ↓
                       Status: EXECUTED
```

### 7.3 Separation of Duties Enforcement
- An AI Agent or user can **NEVER** approve its own request (`req.user_id == approver.user_id` strictly raises `PermissionError`).
- Expired requests (`expires_at < utc_now`) cannot be approved or executed and transition to `EXPIRED`.

---

## 8. Audit Logging & Secret Sanitization

### 8.1 MongoDB Audit Trail (`it_audit_logs`)
Every authorization evaluation, tool execution, approval submission, and administrative action generates an immutable `AuditEvent`:
- `event_id`: Unique identifier (`AUD-...`).
- `timestamp`: UTC ISO-8601 timestamp.
- `request_id`, `thread_id`: Correlation IDs.
- `user_id`, `role`: Actor identity.
- `action`, `resource_type`, `resource_id`: Operation target.
- `authorization_result`: `AUTHORIZED` or `DENIED`.
- `risk_level`: `low`, `medium`, `high`, `critical`.
- `approval_id`: Associated HITL approval reference (if applicable).
- `status`: Execution status (`success`, `denied`, `error`).
- `details`: Structured payload.

### 8.2 Automated Secret Masking
The `_sanitize_details` engine recursively sanitizes payloads before logging:
- Explicit secret keys (`password`, `token`, `secret`, `api_key`, `password_hash`, `auth_token`) are replaced with `***REDACTED***`.
- MongoDB URIs, email addresses, and bearer tokens in strings are sanitized using `mask_sensitive`.
