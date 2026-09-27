"""Data models for production agent architecture, typed tool schemas, and execution metadata."""

import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field


class SearchDocumentsInput(BaseModel):
    """Input schema for the search_policy_documents retrieval tool."""

    query: str = Field(
        ...,
        description="The search query text to find relevant company policy documents.",
        min_length=1,
    )
    top_k: int = Field(
        default=3, description="The maximum number of results to return.", ge=1, le=10
    )
    filter_query: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional MongoDB query filter dictionary (e.g. {'metadata.file_type': 'docx'}).",
    )


class RetrievedChunkOutput(BaseModel):
    """Typed representation of a single retrieved chunk for agent context."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    document_id: str = Field(..., description="Parent document identifier")
    document_name: str = Field(..., description="Source document filename or title")
    content: str = Field(..., description="Text content of the retrieved chunk")
    fusion_score: float = Field(..., description="Reciprocal Rank Fusion score")
    rank: int = Field(..., description="Rank position among retrieved candidates")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Preserved metadata"
    )


class SearchDocumentsOutput(BaseModel):
    """Strongly typed output schema returned by the retrieval tool."""

    status: str = Field(
        ..., description="Execution status: 'success', 'empty', or 'error'"
    )
    chunks: list[RetrievedChunkOutput] = Field(
        default_factory=list, description="Retrieved document chunks"
    )
    total_found: int = Field(0, description="Total number of chunks returned")
    error_message: Optional[str] = Field(
        None, description="Error details if retrieval encountered an issue"
    )
    retrieval_latency_ms: float = Field(
        0.0, description="Latency of retrieval execution in milliseconds"
    )
    document_ids: list[str] = Field(
        default_factory=list,
        description="List of parent document IDs represented in the retrieved chunks",
    )

    def to_tool_string(self) -> str:
        """Format output into clear, grounded text representation for LLM context synthesis."""
        if self.status == "error":
            return f"[ERROR] Document retrieval failed: {self.error_message}. No policy documents could be searched."
        if self.status == "low_confidence":
            return f"[LOW_CONFIDENCE] Retrieved documents fell below confidence threshold: {self.error_message}."
        if not self.chunks or self.status == "empty":
            return "[EMPTY] No policy documents found matching the search criteria."

        parts = [f"Retrieved {len(self.chunks)} relevant policy section(s):\n"]
        for idx, chunk in enumerate(self.chunks, start=1):
            parts.append(
                f"--- Document #{idx}: {chunk.document_name} (ID: {chunk.document_id}, Chunk: {chunk.chunk_id}) ---\n"
                f'<retrieved_policy_chunk document="{chunk.document_name}" id="{chunk.chunk_id}" untrusted_data="true">\n'
                f"{chunk.content.strip()}\n"
                f"</retrieved_policy_chunk>\n"
            )
        return "\n".join(parts)


# isort: split
from mcp_rag_agent.guardrails.models import (  # noqa: E402
    DecisionCategory,
    GuardrailResult,
)
from mcp_rag_agent.observability.models import ErrorRecord, TokenUsage  # noqa: E402


class AgentExecutionMetadata(BaseModel):
    """Structured execution metadata attached to every agent response."""

    request_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique request trace identifier",
    )
    thread_id: str = Field(
        "default_thread", description="Conversation session or thread identifier"
    )
    user_id: Optional[str] = Field(
        None, description="Optional user identifier for multi-user session management"
    )
    model_name: str = Field("gpt-4.1", description="Name of the text model utilized")
    retrieval_latency_ms: float = Field(
        0.0, description="Time spent executing retrieval tools"
    )
    model_latency_ms: float = Field(
        0.0, description="Time spent in LLM reasoning and generation"
    )
    total_latency_ms: float = Field(
        0.0, description="Total end-to-end agent response latency"
    )
    token_usage: Optional[TokenUsage] = Field(
        default=None, description="Token consumption and cost estimation"
    )
    errors: list[ErrorRecord] = Field(
        default_factory=list,
        description="List of categorized errors or guardrail interventions",
    )
    retrieved_document_ids: list[str] = Field(
        default_factory=list,
        description="IDs of documents retrieved and exposed in context",
    )
    retrieved_chunks: list[RetrievedChunkOutput] = Field(
        default_factory=list,
        description="Retrieved chunk objects supporting the response",
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Document titles or filenames explicitly cited in the answer",
    )
    guardrail_result: Optional[GuardrailResult] = Field(
        default=None,
        description="Detailed guardrail and grounding evaluation diagnostics",
    )
    trace: Optional[dict[str, Any]] = Field(
        default=None, description="Serialized execution trace and spans"
    )


class AgentResponse(BaseModel):
    """Production response container produced by the RAG agent."""

    answer: str = Field(..., description="Grounded answer text")
    metadata: AgentExecutionMetadata = Field(
        ..., description="Structured execution metrics"
    )
    decision: DecisionCategory = Field(
        default=DecisionCategory.SUPPORTED_BY_EVIDENCE,
        description="4-tier grounding decision taxonomy: supported_by_evidence, insufficient_evidence, out_of_domain, or system_failure",
    )
    is_out_of_scope: bool = Field(
        False, description="Whether query was identified as out of scope"
    )
    messages: list[Any] = Field(
        default_factory=list, description="LangGraph message history"
    )


# -------------------------------------------------------------------
# Phase 13-D IT Operations MCP Tool Schemas
# -------------------------------------------------------------------


class GetUserContextInput(BaseModel):
    """Input schema for get_user_context tool."""

    user_id: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Unique employee / user identifier (e.g. 'EMP-1001', 'user-1')",
    )


class GetUserContextOutput(BaseModel):
    """Output schema for get_user_context tool."""

    status: str = Field(..., description="Status: 'success', 'not_found', or 'error'")
    user: Optional[dict[str, Any]] = Field(default=None, description="User context details")
    error_code: Optional[str] = Field(default=None, description="Standard error code")
    error_message: Optional[str] = Field(default=None, description="User-safe error explanation")

    def to_tool_string(self) -> str:
        if self.status == "success" and self.user:
            return (
                f"[USER CONTEXT] Found record for user '{self.user.get('user_id')}':\n"
                f"- Name: {self.user.get('name')}\n"
                f"- Department: {self.user.get('department')}\n"
                f"- Role: {self.user.get('role')}\n"
                f"- Support Tier: {self.user.get('support_tier')}\n"
                f"- Status: {self.user.get('status')}"
            )
        if self.status == "not_found":
            return f"[NOT_FOUND] User context not found: {self.error_message}"
        return f"[ERROR] Failed to retrieve user context: {self.error_message}"


class GetDeviceInfoInput(BaseModel):
    """Input schema for get_device_info tool."""

    device_id: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional unique device identifier (e.g. 'DEV-001')",
    )
    user_id: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional employee / user identifier to fetch all assigned devices",
    )


class GetDeviceInfoOutput(BaseModel):
    """Output schema for get_device_info tool."""

    status: str = Field(..., description="Status: 'success', 'not_found', or 'error'")
    devices: list[dict[str, Any]] = Field(default_factory=list, description="Matching device records")
    total_found: int = Field(default=0, description="Number of devices found")
    error_code: Optional[str] = Field(default=None, description="Standard error code")
    error_message: Optional[str] = Field(default=None, description="User-safe error explanation")

    def to_tool_string(self) -> str:
        if self.status == "success" and self.devices:
            lines = [f"[DEVICE INFO] Found {len(self.devices)} registered device(s):"]
            for d in self.devices:
                lines.append(
                    f"- Device ID: {d.get('device_id')} | Hostname: {d.get('hostname')} | "
                    f"Type: {d.get('device_type')} | OS: {d.get('os')} {d.get('os_version')} | "
                    f"VPN Client: {d.get('vpn_client_version')} | Security: {d.get('security_status')} | "
                    f"Status: {d.get('status')}"
                )
            return "\n".join(lines)
        if self.status == "not_found":
            return f"[NOT_FOUND] Device info not found: {self.error_message}"
        return f"[ERROR] Failed to retrieve device info: {self.error_message}"


class CheckServiceStatusInput(BaseModel):
    """Input schema for check_service_status tool."""

    service_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name or alias of enterprise service (e.g. 'vpn', 'wifi', 'github', 'jira', 'outlook', 'teams')",
    )


class CheckServiceStatusOutput(BaseModel):
    """Output schema for check_service_status tool."""

    status: str = Field(..., description="Status: 'success', 'not_found', or 'error'")
    service_name: str = Field(..., description="Canonical service name")
    service_status: str = Field(..., description="Status: 'OPERATIONAL', 'DEGRADED', 'OUTAGE', 'UNKNOWN'")
    last_updated: Optional[str] = Field(default=None, description="Timestamp of status update")
    known_incident_id: Optional[str] = Field(default=None, description="Active incident ID if degraded/outage")
    message: Optional[str] = Field(default=None, description="Status summary message")
    error_code: Optional[str] = Field(default=None, description="Standard error code")
    error_message: Optional[str] = Field(default=None, description="User-safe error explanation")

    def to_tool_string(self) -> str:
        if self.status in ("success", "operational", "degraded", "outage", "unknown"):
            inc = f" (Linked Incident: {self.known_incident_id})" if self.known_incident_id else ""
            return (
                f"[SERVICE STATUS] Service: '{self.service_name}'\n"
                f"- Operational Status: {self.service_status}{inc}\n"
                f"- Message: {self.message}"
            )
        return f"[ERROR] Failed to check service status: {self.error_message}"


class CreateTicketToolInput(BaseModel):
    """Input schema for create_ticket MCP tool."""

    title: str = Field(..., min_length=1, max_length=200, description="Short summary of the issue")
    description: str = Field(..., min_length=1, max_length=4000, description="Detailed description of the issue")
    category: str = Field(..., min_length=1, max_length=100, description="IT Category (e.g. 'vpn', 'wifi', 'hardware', 'software', 'access', 'security', 'email')")
    priority: str = Field(default="medium", description="Priority: 'low', 'medium', 'high', 'critical'")
    requester_id: str = Field(..., min_length=1, max_length=200, description="Employee / requester user ID")
    assigned_team: Optional[str] = Field(default=None, max_length=200, description="Optional support team")
    conversation_id: Optional[str] = Field(default=None, max_length=200, description="Optional conversation / thread ID")
    product: Optional[str] = Field(default=None, max_length=200, description="Product or service involved")
    platform: Optional[str] = Field(default=None, max_length=100, description="OS or platform involved")
    error_code: Optional[str] = Field(default=None, max_length=100, description="Observed error code")


class CreateTicketToolOutput(BaseModel):
    """Output schema for create_ticket MCP tool."""

    status: str = Field(..., description="Status: 'success', 'duplicate', or 'error'")
    ticket_id: Optional[str] = Field(default=None, description="Created or existing ticket ID")
    ticket: Optional[dict[str, Any]] = Field(default=None, description="Ticket details")
    created: bool = Field(default=False, description="Whether a new ticket was created")
    duplicate: bool = Field(default=False, description="Whether an existing duplicate was matched")
    error_code: Optional[str] = Field(default=None, description="Standard error code")
    error_message: Optional[str] = Field(default=None, description="User-safe error explanation")

    def to_tool_string(self) -> str:
        if self.created:
            return (
                f"[TICKET CREATED] Successfully created ticket '{self.ticket_id}':\n"
                f"- Title: {self.ticket.get('title') if self.ticket else ''}\n"
                f"- Category: {self.ticket.get('category') if self.ticket else ''}\n"
                f"- Status: {self.ticket.get('status') if self.ticket else 'new'}\n"
                f"- Requester: {self.ticket.get('requester_id') if self.ticket else ''}"
            )
        if self.duplicate:
            return (
                f"[TICKET DUPLICATE] Existing active ticket '{self.ticket_id}' matches this request:\n"
                f"- Title: {self.ticket.get('title') if self.ticket else ''}\n"
                f"- Status: {self.ticket.get('status') if self.ticket else 'open'}\n"
                f"No duplicate ticket was created."
            )
        return f"[ERROR] Failed to create ticket: {self.error_message}"


class UpdateTicketToolInput(BaseModel):
    """Input schema for update_ticket MCP tool."""

    ticket_id: str = Field(..., min_length=1, max_length=200, description="Ticket ID to update (e.g. 'TKT-1234ABCD')")
    status: Optional[str] = Field(default=None, description="Target status ('open', 'in_progress', 'waiting_for_user', 'resolved', 'closed', 'escalated')")
    assigned_team: Optional[str] = Field(default=None, max_length=200, description="Assign to team")
    comment: Optional[str] = Field(default=None, max_length=4000, description="Comment to append to ticket")
    author_id: Optional[str] = Field(default=None, max_length=200, description="Author user ID of the comment")


class UpdateTicketToolOutput(BaseModel):
    """Output schema for update_ticket MCP tool."""

    status: str = Field(..., description="Status: 'success' or 'error'")
    ticket_id: Optional[str] = Field(default=None, description="Updated ticket ID")
    ticket: Optional[dict[str, Any]] = Field(default=None, description="Updated ticket details")
    error_code: Optional[str] = Field(default=None, description="Standard error code")
    error_message: Optional[str] = Field(default=None, description="User-safe error explanation")

    def to_tool_string(self) -> str:
        if self.status == "success" and self.ticket:
            return (
                f"[TICKET UPDATED] Ticket '{self.ticket_id}' updated successfully:\n"
                f"- Status: {self.ticket.get('status')}\n"
                f"- Assigned Team: {self.ticket.get('assigned_team')}\n"
                f"- Comments Count: {len(self.ticket.get('comments', []))}"
            )
        return f"[ERROR] Failed to update ticket: {self.error_message}"
