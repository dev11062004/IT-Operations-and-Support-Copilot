# MCP IT Operations Tool Layer

This document details the architecture, tools, contracts, error taxonomy, security controls, and runtime modes for the IT Operations MCP Tool Layer introduced in Phase 13-D.

---

## Architecture

The IT Operations tool layer enforces a clean layered architecture, ensuring the LLM/Agent interacts with operational capabilities only via typed MCP tools and domain services, without direct MongoDB access or raw SQL/NoSQL query execution.

```
                  ┌─────────────────────────────────┐
                  │    LangGraph ReAct Agent        │
                  │   (Direct Mode or MCP Mode)     │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │     Typed MCP Tool Layer        │
                  │  (FastMCP & StructuredTools)    │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │       IT Domain Services        │
                  │  - UserService                  │
                  │  - DeviceService                │
                  │  - ServiceStatusChecker         │
                  │  - TicketService (Phase 13-B)   │
                  │  - IncidentService (Phase 13-B) │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │    Stores / Repositories        │
                  │  - UserStore                    │
                  │  - DeviceStore                  │
                  │  - ServiceStatusStore           │
                  │  - TicketStore / IncidentStore  │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │    Shared MongoDBClient         │
                  │  (Collections: it_users,        │
                  │   it_devices, it_service_...    │
                  │   it_tickets, it_incidents)     │
                  └─────────────────────────────────┘
```

---

## Tool Catalog

### 1. `get_user_context`

Retrieves verified employee context including department, role, support tier, and account status.

- **Inputs (`GetUserContextInput`):**
  - `user_id` (`str`, required): Unique employee or user identifier (e.g., `"EMP-1001"`, `"user-1"`).
- **Outputs (`GetUserContextOutput`):**
  - `status` (`str`): `"success"`, `"not_found"`, or `"error"`.
  - `user` (`dict`, optional): User context containing `user_id`, `name`, `department`, `role`, `support_tier`, `status`.
  - `error_code` (`str`, optional): Standard error code.
  - `error_message` (`str`, optional): Privacy-safe explanation.
- **Example Output String:**
  ```text
  [USER CONTEXT] Found record for user 'EMP-1001':
  - Name: John Doe
  - Department: Engineering
  - Role: Software Engineer
  - Support Tier: standard
  - Status: active
  ```

---

### 2. `get_device_info`

Retrieves hardware specifications, operating system versions, client agent versions, and security compliance status.

- **Inputs (`GetDeviceInfoInput`):**
  - `device_id` (`str`, optional): Unique device identifier (e.g., `"DEV-001"`).
  - `user_id` (`str`, optional): User identifier to query all assigned devices.
- **Outputs (`GetDeviceInfoOutput`):**
  - `status` (`str`): `"success"`, `"not_found"`, or `"error"`.
  - `devices` (`list[dict]`): List of matching device records.
  - `total_found` (`int`): Count of devices returned.
- **Example Output String:**
  ```text
  [DEVICE INFO] Found 1 registered device(s):
  - Device ID: DEV-001 | Hostname: MAC-JDOE-01 | Type: laptop | OS: macOS 14.3.1 | VPN Client: 5.1.2 | Security: compliant | Status: active
  ```

---

### 3. `check_service_status`

Queries synthetic operational health of enterprise systems (`corporate_vpn`, `corporate_wifi`, `github`, `jira`, `outlook`, `teams`) and correlates active incidents from `IncidentService`.

- **Inputs (`CheckServiceStatusInput`):**
  - `service_name` (`str`, required): Name or alias of enterprise service.
- **Outputs (`CheckServiceStatusOutput`):**
  - `status` (`str`): `"success"`, `"not_found"`, or `"error"`.
  - `service_name` (`str`): Canonical service name.
  - `service_status` (`str`): `"OPERATIONAL"`, `"DEGRADED"`, `"OUTAGE"`, or `"UNKNOWN"`.
  - `known_incident_id` (`str`, optional): Linked active incident ID if degraded/outage.
  - `message` (`str`, optional): Operational summary.
- **Example Output String:**
  ```text
  [SERVICE STATUS] Service: 'corporate_vpn'
  - Operational Status: OPERATIONAL
  - Message: Corporate VPN Gateways (US-East, US-West, EU-Central) fully operational (Synthetic).
  ```

---

### 4. `create_ticket`

Delegates to the existing Phase 13-B `TicketService` to create a new support ticket or detect unresolved duplicates.

- **Inputs (`CreateTicketToolInput`):**
  - `title` (`str`, required): Short problem summary.
  - `description` (`str`, required): Detailed technical description.
  - `category` (`str`, required): Category (e.g., `"vpn"`, `"wifi"`, `"access"`, `"software"`, `"hardware"`).
  - `priority` (`str`, optional): `"low"`, `"medium"`, `"high"`, `"critical"`. Default `"medium"`.
  - `requester_id` (`str`, required): Employee ID.
  - `assigned_team` (`str`, optional): Target support team.
  - `conversation_id` (`str`, optional): Thread ID.
  - `product` / `platform` / `error_code` (`str`, optional): Structured diagnostic signals.
- **Outputs (`CreateTicketToolOutput`):**
  - `status` (`str`): `"success"`, `"duplicate"`, or `"error"`.
  - `ticket_id` (`str`, optional): Created or matched ticket ID.
  - `created` (`bool`): `True` if new ticket created.
  - `duplicate` (`bool`): `True` if existing active duplicate detected.
- **Example Output String:**
  ```text
  [TICKET CREATED] Successfully created ticket 'TKT-9D8E1F2A':
  - Title: VPN Connection Failure
  - Category: vpn
  - Status: new
  - Requester: EMP-1001
  ```

---

### 5. `update_ticket`

Delegates to the existing Phase 13-B `TicketService` to perform controlled lifecycle state transitions, team assignments, or append work note comments.

- **Inputs (`UpdateTicketToolInput`):**
  - `ticket_id` (`str`, required): Target ticket ID.
  - `status` (`str`, optional): Target lifecycle status (`"open"`, `"in_progress"`, `"waiting_for_user"`, `"resolved"`, `"closed"`, `"escalated"`).
  - `assigned_team` (`str`, optional): New team assignment.
  - `comment` (`str`, optional): Comment text.
  - `author_id` (`str`, optional): Author user ID.
- **Outputs (`UpdateTicketToolOutput`):**
  - `status` (`str`): `"success"` or `"error"`.
  - `ticket_id` (`str`, optional): Updated ticket ID.
  - `ticket` (`dict`, optional): Updated ticket record.
- **Example Output String:**
  ```text
  [TICKET UPDATED] Ticket 'TKT-9D8E1F2A' updated successfully:
  - Status: open
  - Assigned Team: Network Engineering
  - Comments Count: 1
  ```

---

## Error Contracts & Taxonomy

Standardized error codes ensure consistent error handling across direct execution and MCP clients:

| Error Code | HTTP / Tool Mapping | Description |
|---|---|---|
| `USER_NOT_FOUND` | 404 / `not_found` | Requested `user_id` does not exist in store |
| `DEVICE_NOT_FOUND` | 404 / `not_found` | Requested `device_id` or user device mapping not found |
| `SERVICE_NOT_FOUND` | 404 / `unknown` | Unmonitored or unmapped service name |
| `TICKET_NOT_FOUND` | 404 / `error` | Target `ticket_id` does not exist |
| `INVALID_ARGUMENT` | 422 / `error` | Empty or malformed input parameters |
| `INVALID_TRANSITION` | 422 / `error` | Prohibited ticket lifecycle transition (e.g. `open` -> `closed`) |
| `DATABASE_ERROR` | 500 / `error` | MongoDB read/write timeout or connection failure (internal details masked) |
| `TOOL_EXECUTION_ERROR` | 500 / `error` | Unexpected tool execution failure |

---

## Security & Privacy Controls

1. **Zero Secret Leakage:**
   - Connection strings (e.g., `mongodb+srv://...`), bearer tokens, passwords, and private API keys are filtered via `mask_sensitive()`.
   - Internal credentials or private fields (`password_hash`, `api_keys`) are stripped before returning user context.
2. **Deterministic State Enforcement:**
   - All ticket state transitions are validated by `TicketService.transition_status()` against `ALLOWED_TRANSITIONS`.
   - Arbitrary field mutations are prohibited.
3. **Traceability:**
   - Every tool call logs with `[TOOL:<name>] [req:<request_id>]`.
   - Observability spans and latencies are captured via `get_current_tracer().record_tool_call()`.

---

## Runtime Modes: Direct Mode vs MCP Mode

- **Direct Mode (`FEATURE_FLAG_MCPSERVER_ENABLED=false`):**
  - LangGraph compiles tools directly via LangChain `StructuredTool` instances.
  - Full offline unit testing runs without external subprocesses or network daemons.
- **MCP Server Mode (`FEATURE_FLAG_MCPSERVER_ENABLED=true`):**
  - FastMCP exposes the 5 tools alongside `search_policy_documents` over stdio or SSE transport.
  - MultiServerMCPClient dynamically discovers tools and bindings.
