"""MCP server for RAG agent with semantic and keyword hybrid search capabilities."""

import logging
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from mcp_rag_agent.agent.models import SearchDocumentsInput
from mcp_rag_agent.core.config import config
from mcp_rag_agent.core.log_setup import setup_logging
from mcp_rag_agent.mcp_server.tools import search_policy_documents_typed

setup_logging()
logger = logging.getLogger("MCP Server")

# Initialize FastMCP Server
mcp = FastMCP(
    name=config.mcp_name,
    host=config.mcp_host,
    port=config.mcp_port,
)


@mcp.tool()
async def search_policy_documents(
    query: str,
    top_k: int = 3,
    filter_query: Optional[dict[str, Any]] = None,
) -> str:
    """Search stored company policy documents using hybrid semantic and keyword retrieval.

    This tool understands the meaning of the query, searches through company policies,
    and returns relevant grounded passages with document IDs and titles.

    Args:
        query: The search query text to find relevant company policies.
        top_k: The maximum number of results to return (1-10, default: 3).
        filter_query: Optional metadata filter dictionary.
    """
    input_data = SearchDocumentsInput(
        query=query, top_k=top_k, filter_query=filter_query
    )
    output = await search_policy_documents_typed(input_data)
    return output.to_tool_string()


@mcp.tool()
async def search_documents(
    query: str,
    top_k: int = 3,
) -> str:
    """Legacy alias for search_policy_documents."""
    return await search_policy_documents(query=query, top_k=top_k)


@mcp.tool()
async def get_user_context(
    user_id: str,
) -> str:
    """Retrieve verified enterprise employee and user context.

    Fetches user role, department, support tier, and account status.

    Args:
        user_id: Unique employee or user identifier (e.g. 'EMP-1001', 'user-1').
    """
    from mcp_rag_agent.agent.models import GetUserContextInput
    from mcp_rag_agent.mcp_server.tools import get_user_context_typed

    input_data = GetUserContextInput(user_id=user_id)
    output = await get_user_context_typed(input_data)
    return output.to_tool_string()


@mcp.tool()
async def get_device_info(
    device_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> str:
    """Retrieve hardware and device configuration information.

    Fetches device model, OS, client software versions, and security compliance status.

    Args:
        device_id: Optional unique device identifier (e.g. 'DEV-001').
        user_id: Optional user identifier to list all assigned hardware devices.
    """
    from mcp_rag_agent.agent.models import GetDeviceInfoInput
    from mcp_rag_agent.mcp_server.tools import get_device_info_typed

    input_data = GetDeviceInfoInput(device_id=device_id, user_id=user_id)
    output = await get_device_info_typed(input_data)
    return output.to_tool_string()


@mcp.tool()
async def check_service_status(
    service_name: str,
) -> str:
    """Check the real-time operational status of an enterprise IT service or infrastructure component.

    Args:
        service_name: Name of service (e.g. 'corporate_vpn', 'corporate_wifi', 'github', 'jira', 'outlook', 'teams').
    """
    from mcp_rag_agent.agent.models import CheckServiceStatusInput
    from mcp_rag_agent.mcp_server.tools import check_service_status_typed

    input_data = CheckServiceStatusInput(service_name=service_name)
    output = await check_service_status_typed(input_data)
    return output.to_tool_string()


@mcp.tool()
async def create_ticket(
    title: str,
    description: str,
    category: str,
    priority: str = "medium",
    requester_id: str = "EMP-1001",
    assigned_team: Optional[str] = None,
    conversation_id: Optional[str] = None,
    product: Optional[str] = None,
    platform: Optional[str] = None,
    error_code: Optional[str] = None,
) -> str:
    """Create a new IT support ticket or match an existing unresolved duplicate.

    Args:
        title: Short summary of the reported problem.
        description: Full technical details of the problem.
        category: IT domain category (e.g. 'vpn', 'wifi', 'hardware', 'software', 'access', 'security', 'email').
        priority: Priority level ('low', 'medium', 'high', 'critical'). Default 'medium'.
        requester_id: Employee ID of the user reporting the issue.
        assigned_team: Optional routing team (e.g. 'Network Support', 'SecOps').
        conversation_id: Optional conversation/thread ID.
        product: Optional software or product name.
        platform: Optional OS or platform.
        error_code: Optional error code.
    """
    from mcp_rag_agent.agent.models import CreateTicketToolInput
    from mcp_rag_agent.mcp_server.tools import create_ticket_typed

    input_data = CreateTicketToolInput(
        title=title,
        description=description,
        category=category,
        priority=priority,
        requester_id=requester_id,
        assigned_team=assigned_team,
        conversation_id=conversation_id,
        product=product,
        platform=platform,
        error_code=error_code,
    )
    output = await create_ticket_typed(input_data)
    return output.to_tool_string()


@mcp.tool()
async def update_ticket(
    ticket_id: str,
    status: Optional[str] = None,
    assigned_team: Optional[str] = None,
    comment: Optional[str] = None,
    author_id: Optional[str] = None,
) -> str:
    """Update an existing IT support ticket status, assigned team, or add a work note comment.

    Args:
        ticket_id: The ticket ID to update (e.g. 'TKT-1234ABCD').
        status: Target lifecycle status ('open', 'in_progress', 'waiting_for_user', 'resolved', 'closed', 'escalated').
        assigned_team: Support team to assign.
        comment: Work note or comment text to add.
        author_id: User or agent ID authoring the update.
    """
    from mcp_rag_agent.agent.models import UpdateTicketToolInput
    from mcp_rag_agent.mcp_server.tools import update_ticket_typed

    input_data = UpdateTicketToolInput(
        ticket_id=ticket_id,
        status=status,
        assigned_team=assigned_team,
        comment=comment,
        author_id=author_id,
    )
    output = await update_ticket_typed(input_data)
    return output.to_tool_string()


@mcp.prompt()
def grounded_qa_prompt() -> str:
    """Provide a prompt template for grounded question-answering using retrieved documents.

    Instructs language models to answer questions strictly based on provided document
    context, preventing hallucination or speculation beyond the given information.
    """
    return (
        "You answer questions ONLY using the provided documents from search_policy_documents. "
        "Never invent facts, policies, numbers, or dates. "
        "Cite the retrieved documents under 'Reference:'. "
        "If information is missing or retrieval yields no results, state clearly: "
        "'I couldn't find this information in the available policy content.' and invite the user to rephrase."
    )


if __name__ == "__main__":
    import os

    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    logger.info(
        f"Initializing MCP server on transport='{transport}' "
        f"(host={config.mcp_host}, port={config.mcp_port})..."
    )
    mcp.run(transport=transport)
