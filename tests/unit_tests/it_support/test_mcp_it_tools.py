"""Unit tests for typed IT Operations MCP tools and FastMCP registration."""

import pytest

from mcp_rag_agent.agent.models import (
    CheckServiceStatusInput,
    CreateTicketToolInput,
    GetDeviceInfoInput,
    GetUserContextInput,
    UpdateTicketToolInput,
)
from mcp_rag_agent.it_support.devices.models import DeviceRecord
from mcp_rag_agent.it_support.devices.service import DeviceService
from mcp_rag_agent.it_support.devices.store import DeviceNotFoundError
from mcp_rag_agent.it_support.models import ITCategory, Priority
from mcp_rag_agent.it_support.services.models import ServiceOperationalStatus, ServiceStatusRecord
from mcp_rag_agent.it_support.services.service import ServiceStatusChecker
from mcp_rag_agent.it_support.tickets.models import TicketLifecycleStatus, TicketRecord
from mcp_rag_agent.it_support.tickets.service import TicketService
from mcp_rag_agent.it_support.users.models import SupportTier, UserContextRecord, UserStatus
from mcp_rag_agent.it_support.users.service import UserService
from mcp_rag_agent.it_support.users.store import UserNotFoundError
from mcp_rag_agent.mcp_server.tools import (
    check_service_status_typed,
    create_ticket_typed,
    get_device_info_typed,
    get_user_context_typed,
    mask_sensitive,
    reset_retriever,
    set_device_service,
    set_service_status_checker,
    set_ticket_service,
    set_user_service,
    update_ticket_typed,
)


# -------------------------------------------------------------------
# In-Memory Test Doubles
# -------------------------------------------------------------------

class MemoryUserStore:
    def __init__(self):
        self.records: dict[str, UserContextRecord] = {}

    def get(self, user_id: str) -> UserContextRecord:
        if user_id not in self.records:
            raise UserNotFoundError(f"User '{user_id}' not found")
        return self.records[user_id]


class MemoryDeviceStore:
    def __init__(self):
        self.records: dict[str, DeviceRecord] = {}

    def get(self, device_id: str) -> DeviceRecord:
        if device_id not in self.records:
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        return self.records[device_id]

    def get_by_user(self, user_id: str) -> list[DeviceRecord]:
        return [d for d in self.records.values() if d.user_id == user_id]


class MemoryTicketStore:
    def __init__(self):
        self.records: dict[str, TicketRecord] = {}

    def find_unresolved_duplicate(self, ticket: TicketRecord):
        return next(
            (
                t
                for t in self.records.values()
                if t.requester_id == ticket.requester_id
                and t.category == ticket.category
                and t.title == ticket.title
                and t.status not in (TicketLifecycleStatus.CLOSED, TicketLifecycleStatus.RESOLVED)
            ),
            None,
        )

    def create(self, ticket: TicketRecord) -> TicketRecord:
        self.records[ticket.ticket_id] = ticket
        return ticket

    def get(self, ticket_id: str) -> TicketRecord:
        from mcp_rag_agent.it_support.tickets.store import TicketNotFoundError
        if ticket_id not in self.records:
            raise TicketNotFoundError(ticket_id)
        return self.records[ticket_id]

    def update_fields(self, ticket_id: str, fields: dict) -> TicketRecord:
        from mcp_rag_agent.it_support.tickets.store import TicketNotFoundError
        if ticket_id not in self.records:
            raise TicketNotFoundError(ticket_id)
        payload = self.records[ticket_id].model_dump()
        payload.update(fields)
        self.records[ticket_id] = TicketRecord.model_validate(payload)
        return self.records[ticket_id]

    def add_comment(self, ticket_id: str, comment) -> TicketRecord:
        from mcp_rag_agent.it_support.tickets.store import TicketNotFoundError
        if ticket_id not in self.records:
            raise TicketNotFoundError(ticket_id)
        self.records[ticket_id].comments.append(comment)
        return self.records[ticket_id]


# -------------------------------------------------------------------
# Fixtures & Setup
# -------------------------------------------------------------------

@pytest.fixture(autouse=True)
def setup_services():
    reset_retriever()
    user_store = MemoryUserStore()
    user_store.records["EMP-1001"] = UserContextRecord(
        user_id="EMP-1001",
        name="John Doe",
        email="john.doe@enterprise.internal",
        department="Engineering",
        role="Software Engineer",
        support_tier=SupportTier.STANDARD,
        status=UserStatus.ACTIVE,
    )
    set_user_service(UserService(user_store))

    device_store = MemoryDeviceStore()
    device_store.records["DEV-001"] = DeviceRecord(
        device_id="DEV-001",
        user_id="EMP-1001",
        device_type="laptop",
        manufacturer="Apple",
        model='MacBook Pro 16" M3',
        os="macOS",
        os_version="14.3.1",
        hostname="MAC-JDOE-01",
        status="active",
        vpn_client_version="5.1.2",
        security_status="compliant",
    )
    set_device_service(DeviceService(device_store))

    set_service_status_checker(ServiceStatusChecker())
    set_ticket_service(TicketService(MemoryTicketStore()))

    yield
    reset_retriever()


# -------------------------------------------------------------------
# Test Cases
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_user_context_success():
    res = await get_user_context_typed(GetUserContextInput(user_id="EMP-1001"))
    assert res.status == "success"
    assert res.user is not None
    assert res.user["user_id"] == "EMP-1001"
    assert res.user["department"] == "Engineering"
    assert "[USER CONTEXT]" in res.to_tool_string()


@pytest.mark.asyncio
async def test_get_user_context_not_found():
    res = await get_user_context_typed(GetUserContextInput(user_id="EMP-9999"))
    assert res.status == "not_found"
    assert res.error_code == "USER_NOT_FOUND"
    assert "[NOT_FOUND]" in res.to_tool_string()


@pytest.mark.asyncio
async def test_get_device_info_by_device_id_and_user_id():
    # By device ID
    dev_res = await get_device_info_typed(GetDeviceInfoInput(device_id="DEV-001"))
    assert dev_res.status == "success"
    assert dev_res.total_found == 1
    assert dev_res.devices[0]["hostname"] == "MAC-JDOE-01"

    # By user ID
    user_res = await get_device_info_typed(GetDeviceInfoInput(user_id="EMP-1001"))
    assert user_res.status == "success"
    assert user_res.total_found == 1
    assert user_res.devices[0]["device_id"] == "DEV-001"

    # Not found
    missing_res = await get_device_info_typed(GetDeviceInfoInput(device_id="DEV-NONEXISTENT"))
    assert missing_res.status == "not_found"
    assert missing_res.error_code == "DEVICE_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_device_info_missing_args():
    res = await get_device_info_typed(GetDeviceInfoInput(device_id=None, user_id=None))
    assert res.status == "error"
    assert res.error_code == "INVALID_ARGUMENT"


@pytest.mark.asyncio
async def test_check_service_status_operational_and_unknown():
    res_vpn = await check_service_status_typed(CheckServiceStatusInput(service_name="corporate_vpn"))
    assert res_vpn.status == "success"
    assert res_vpn.service_status == "OPERATIONAL"

    res_unknown = await check_service_status_typed(CheckServiceStatusInput(service_name="some_weird_service"))
    assert res_unknown.service_status == "UNKNOWN"


@pytest.mark.asyncio
async def test_create_ticket_flow_and_duplicate_detection():
    ticket_input = CreateTicketToolInput(
        title="VPN Connection Failure",
        description="Cannot authenticate with gateway",
        category="vpn",
        priority="high",
        requester_id="EMP-1001",
        product="AnyConnect",
        platform="macOS",
        error_code="VPN-742",
    )

    # 1. Create ticket
    res1 = await create_ticket_typed(ticket_input)
    assert res1.status == "success"
    assert res1.created is True
    assert res1.duplicate is False
    assert res1.ticket_id is not None
    assert "[TICKET CREATED]" in res1.to_tool_string()

    # 2. Duplicate submission
    res2 = await create_ticket_typed(ticket_input)
    assert res2.status == "duplicate"
    assert res2.created is False
    assert res2.duplicate is True
    assert res2.ticket_id == res1.ticket_id
    assert "[TICKET DUPLICATE]" in res2.to_tool_string()


@pytest.mark.asyncio
async def test_update_ticket_lifecycle_comment_and_team():
    # First create a ticket
    ticket_input = CreateTicketToolInput(
        title="Wi-Fi unstable",
        description="Dropping signal in room 302",
        category="wifi",
        requester_id="EMP-1001",
    )
    create_res = await create_ticket_typed(ticket_input)
    ticket_id = create_res.ticket_id

    # 1. Transition NEW -> OPEN
    upd_res = await update_ticket_typed(
        UpdateTicketToolInput(
            ticket_id=ticket_id,
            status="open",
            assigned_team="Network Engineering",
            comment="Assigned to network engineer for wireless spectrum analysis.",
            author_id="EMP-1001",
        )
    )
    assert upd_res.status == "success"
    assert upd_res.ticket["status"] == "open"
    assert upd_res.ticket["assigned_team"] == "Network Engineering"
    assert len(upd_res.ticket["comments"]) == 1

    # 2. Invalid Transition: OPEN -> CLOSED directly (bypassing IN_PROGRESS / RESOLVED)
    invalid_upd = await update_ticket_typed(
        UpdateTicketToolInput(
            ticket_id=ticket_id,
            status="closed",
        )
    )
    assert invalid_upd.status == "error"
    assert invalid_upd.error_code == "INVALID_TRANSITION"


def test_mask_sensitive_no_credential_leakage():
    sample_secret = "mongodb+srv://admin:my_secret_password_123@cluster0.mongodb.net/db?retryWrites=true"
    masked = mask_sensitive(sample_secret)
    assert "my_secret_password_123" not in masked
    assert "mongodb://***REDACTED***@" in masked
