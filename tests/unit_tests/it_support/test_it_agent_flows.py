"""Integration and workflow tests for IT Operations agent capabilities and tool binding."""

from unittest.mock import MagicMock
import pytest

from mcp_rag_agent.agent.create_agent import create_rag_agent_instance
from mcp_rag_agent.core.config import Config
from mcp_rag_agent.it_support.devices.models import DeviceRecord
from mcp_rag_agent.it_support.devices.service import DeviceService
from mcp_rag_agent.it_support.devices.store import DeviceNotFoundError
from mcp_rag_agent.it_support.runbooks import RunbookExecutor
from mcp_rag_agent.it_support.services.service import ServiceStatusChecker
from mcp_rag_agent.it_support.tickets.models import TicketLifecycleStatus, TicketRecord
from mcp_rag_agent.it_support.tickets.service import TicketService
from mcp_rag_agent.it_support.tools import create_it_operations_tools
from mcp_rag_agent.it_support.users.models import SupportTier, UserContextRecord, UserStatus
from mcp_rag_agent.it_support.users.service import UserService
from mcp_rag_agent.it_support.users.store import UserNotFoundError
from mcp_rag_agent.mcp_server.tools import (
    reset_retriever,
    set_device_service,
    set_service_status_checker,
    set_ticket_service,
    set_user_service,
)


class MemoryUserStore:
    def __init__(self):
        self.records: dict[str, UserContextRecord] = {}

    def get(self, user_id: str) -> UserContextRecord:
        if user_id not in self.records:
            raise UserNotFoundError(user_id)
        return self.records[user_id]


class MemoryDeviceStore:
    def __init__(self):
        self.records: dict[str, DeviceRecord] = {}

    def get(self, device_id: str) -> DeviceRecord:
        if device_id not in self.records:
            raise DeviceNotFoundError(device_id)
        return self.records[device_id]

    def get_by_user(self, user_id: str) -> list[DeviceRecord]:
        return [d for d in self.records.values() if d.user_id == user_id]


class MemoryTicketStore:
    def __init__(self):
        self.records: dict[str, TicketRecord] = {}

    def find_unresolved_duplicate(self, ticket: TicketRecord):
        return None

    def create(self, ticket: TicketRecord) -> TicketRecord:
        self.records[ticket.ticket_id] = ticket
        return ticket

    def get(self, ticket_id: str) -> TicketRecord:
        return self.records[ticket_id]


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


def test_it_operations_tools_instantiation():
    tools = create_it_operations_tools()
    tool_names = {t.name for t in tools}
    expected = {
        "get_user_context",
        "get_device_info",
        "check_service_status",
        "create_ticket",
        "update_ticket",
    }
    assert expected.issubset(tool_names)


@pytest.mark.asyncio
async def test_agent_toolbelt_includes_it_operations_when_flag_enabled():
    cfg = Config(
        model_api_key="test-key-mock",
        db_url="mongodb://localhost:27017",
        db_name="test_db",
        ff_mcp_server=False,
        ff_it_support=True,
    )

    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()

    runner = await create_rag_agent_instance(
        cfg=cfg,
        checkpointer=checkpointer,
    )

    assert runner is not None
    assert runner.runbook_executor is not None


@pytest.mark.asyncio
async def test_it_tools_vpn_workflow():
    """Test tools invoked during a VPN diagnostic scenario."""
    tools = {t.name: t for t in create_it_operations_tools()}

    # 1. User context lookup
    user_out = await tools["get_user_context"].ainvoke({"user_id": "EMP-1001"})
    assert "Engineering" in user_out

    # 2. Service status check
    svc_out = await tools["check_service_status"].ainvoke({"service_name": "corporate_vpn"})
    assert "OPERATIONAL" in svc_out

    # 3. Device info lookup
    dev_out = await tools["get_device_info"].ainvoke({"user_id": "EMP-1001"})
    assert "MAC-JDOE-01" in dev_out


@pytest.mark.asyncio
async def test_it_tools_access_request_and_ticket_creation():
    """Test tools invoked during an access provisioning / ticket scenario."""
    tools = {t.name: t for t in create_it_operations_tools()}

    # 1. Check user context
    user_out = await tools["get_user_context"].ainvoke({"user_id": "EMP-1001"})
    assert "EMP-1001" in user_out

    # 2. Create ticket
    ticket_out = await tools["create_ticket"].ainvoke(
        {
            "title": "GitHub Org Access for Repo xyz",
            "description": "Please grant write access to repository xyz for engineering project.",
            "category": "access",
            "requester_id": "EMP-1001",
            "assigned_team": "Identity & Access Management",
        }
    )
    assert "[TICKET CREATED]" in ticket_out
    assert "TKT-" in ticket_out
