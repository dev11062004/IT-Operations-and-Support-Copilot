"""LangChain StructuredTool definitions for IT Operations capabilities."""

import asyncio
import concurrent.futures
from typing import Any, Callable, Coroutine, Optional

from langchain_core.tools import StructuredTool

from mcp_rag_agent.agent.models import (
    CheckServiceStatusInput,
    CreateTicketToolInput,
    GetDeviceInfoInput,
    GetUserContextInput,
    UpdateTicketToolInput,
)
from mcp_rag_agent.mcp_server.tools import (
    check_service_status_typed,
    create_ticket_typed,
    get_device_info_typed,
    get_user_context_typed,
    update_ticket_typed,
)


def _make_sync_runner(
    async_fn: Callable[..., Coroutine[Any, Any, str]],
) -> Callable[..., str]:
    """Helper to run async coroutines safely from sync tool callers."""

    def _sync_wrapper(*args: Any, **kwargs: Any) -> str:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, async_fn(*args, **kwargs))
                return future.result()
        return asyncio.run(async_fn(*args, **kwargs))

    return _sync_wrapper


def create_user_context_tool() -> StructuredTool:
    async def _async_call(user_id: str) -> str:
        res = await get_user_context_typed(GetUserContextInput(user_id=user_id))
        return res.to_tool_string()

    return StructuredTool(
        name="get_user_context",
        description="Retrieve verified enterprise employee context (role, department, support tier, account status).",
        func=_make_sync_runner(_async_call),
        coroutine=_async_call,
        args_schema=GetUserContextInput,
    )


def create_device_info_tool() -> StructuredTool:
    async def _async_call(
        device_id: Optional[str] = None, user_id: Optional[str] = None
    ) -> str:
        res = await get_device_info_typed(
            GetDeviceInfoInput(device_id=device_id, user_id=user_id)
        )
        return res.to_tool_string()

    return StructuredTool(
        name="get_device_info",
        description="Retrieve hardware and device configuration details (model, OS, client software versions, security status).",
        func=_make_sync_runner(_async_call),
        coroutine=_async_call,
        args_schema=GetDeviceInfoInput,
    )


def create_service_status_tool() -> StructuredTool:
    async def _async_call(service_name: str) -> str:
        res = await check_service_status_typed(
            CheckServiceStatusInput(service_name=service_name)
        )
        return res.to_tool_string()

    return StructuredTool(
        name="check_service_status",
        description="Check real-time synthetic operational status of enterprise services ('corporate_vpn', 'corporate_wifi', 'github', 'jira', 'outlook', 'teams').",
        func=_make_sync_runner(_async_call),
        coroutine=_async_call,
        args_schema=CheckServiceStatusInput,
    )


def create_ticket_tool() -> StructuredTool:
    async def _async_call(
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
        res = await create_ticket_typed(
            CreateTicketToolInput(
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
        )
        return res.to_tool_string()

    return StructuredTool(
        name="create_ticket",
        description="Create a new IT support ticket or detect unresolved duplicates matching this request.",
        func=_make_sync_runner(_async_call),
        coroutine=_async_call,
        args_schema=CreateTicketToolInput,
    )


def create_update_ticket_tool() -> StructuredTool:
    async def _async_call(
        ticket_id: str,
        status: Optional[str] = None,
        assigned_team: Optional[str] = None,
        comment: Optional[str] = None,
        author_id: Optional[str] = None,
    ) -> str:
        res = await update_ticket_typed(
            UpdateTicketToolInput(
                ticket_id=ticket_id,
                status=status,
                assigned_team=assigned_team,
                comment=comment,
                author_id=author_id,
            )
        )
        return res.to_tool_string()

    return StructuredTool(
        name="update_ticket",
        description="Update ticket lifecycle status ('open', 'in_progress', 'waiting_for_user', 'resolved', 'closed', 'escalated'), assigned team, or add a comment.",
        func=_make_sync_runner(_async_call),
        coroutine=_async_call,
        args_schema=UpdateTicketToolInput,
    )


def create_it_operations_tools() -> list[StructuredTool]:
    """Create all 5 IT operational tools for direct agent execution."""
    return [
        create_user_context_tool(),
        create_device_info_tool(),
        create_service_status_tool(),
        create_ticket_tool(),
        create_update_ticket_tool(),
    ]
