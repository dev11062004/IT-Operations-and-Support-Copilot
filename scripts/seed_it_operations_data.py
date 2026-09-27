"""Deterministic, idempotent seed script for IT operations data (Users, Devices, Service Statuses).

Usage:
    python scripts/seed_it_operations_data.py
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src directory to path if running directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# isort: split
from mcp_rag_agent.core.config import config  # noqa: E402
from mcp_rag_agent.core.log_setup import setup_logging  # noqa: E402
from mcp_rag_agent.it_support.devices.models import DeviceRecord  # noqa: E402
from mcp_rag_agent.it_support.devices.store import DeviceStore  # noqa: E402
from mcp_rag_agent.it_support.services.models import (  # noqa: E402
    ServiceOperationalStatus,
    ServiceStatusRecord,
)
from mcp_rag_agent.it_support.services.store import ServiceStatusStore  # noqa: E402
from mcp_rag_agent.it_support.users.models import (  # noqa: E402
    SupportTier,
    UserContextRecord,
    UserStatus,
)
from mcp_rag_agent.it_support.users.store import UserStore  # noqa: E402
from mcp_rag_agent.mongodb.client import MongoDBClient  # noqa: E402

setup_logging()
logger = logging.getLogger("SeedITOperations")


def get_seed_users() -> list[UserContextRecord]:
    now = datetime.now(timezone.utc)
    return [
        UserContextRecord(
            user_id="EMP-1001",
            name="John Doe",
            email="john.doe@enterprise.internal",
            department="Engineering",
            role="Software Engineer",
            support_tier=SupportTier.STANDARD,
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            metadata={"location": "New York", "cost_center": "ENG-402"},
        ),
        UserContextRecord(
            user_id="EMP-1002",
            name="Jane Smith",
            email="jane.smith@enterprise.internal",
            department="Product",
            role="Product Manager",
            support_tier=SupportTier.TIER_1,
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            metadata={"location": "San Francisco", "cost_center": "PROD-101"},
        ),
        UserContextRecord(
            user_id="EMP-1003",
            name="Alice Johnson",
            email="alice.j@enterprise.internal",
            department="Finance",
            role="Financial Analyst",
            support_tier=SupportTier.VIP,
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            metadata={"location": "London", "cost_center": "FIN-203"},
        ),
        UserContextRecord(
            user_id="user-1",
            name="Alex Rivera",
            email="alex.rivera@enterprise.internal",
            department="IT Support",
            role="Support Specialist",
            support_tier=SupportTier.TIER_2,
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            metadata={"location": "Austin", "cost_center": "IT-001"},
        ),
    ]


def get_seed_devices() -> list[DeviceRecord]:
    now = datetime.now(timezone.utc)
    return [
        DeviceRecord(
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
            created_at=now,
            updated_at=now,
        ),
        DeviceRecord(
            device_id="DEV-002",
            user_id="EMP-1002",
            device_type="laptop",
            manufacturer="Dell",
            model="XPS 15 9530",
            os="Windows",
            os_version="11 Pro 23H2",
            hostname="WIN-JSMITH-01",
            status="active",
            vpn_client_version="5.0.8",
            security_status="compliant",
            created_at=now,
            updated_at=now,
        ),
        DeviceRecord(
            device_id="DEV-003",
            user_id="EMP-1003",
            device_type="laptop",
            manufacturer="Lenovo",
            model="ThinkPad X1 Carbon Gen 11",
            os="Windows",
            os_version="11 Enterprise",
            hostname="WIN-AJOHN-01",
            status="active",
            vpn_client_version="5.1.0",
            security_status="compliant",
            created_at=now,
            updated_at=now,
        ),
        DeviceRecord(
            device_id="DEV-004",
            user_id="user-1",
            device_type="workstation",
            manufacturer="Dell",
            model="Precision 3660",
            os="Ubuntu",
            os_version="22.04 LTS",
            hostname="LNX-US1-01",
            status="active",
            vpn_client_version="5.1.2",
            security_status="compliant",
            created_at=now,
            updated_at=now,
        ),
    ]


def get_seed_service_statuses() -> list[ServiceStatusRecord]:
    now = datetime.now(timezone.utc)
    return [
        ServiceStatusRecord(
            service_name="corporate_vpn",
            status=ServiceOperationalStatus.OPERATIONAL,
            last_updated=now,
            message="Corporate VPN Gateways (US-East, US-West, EU-Central) fully operational (Synthetic).",
        ),
        ServiceStatusRecord(
            service_name="corporate_wifi",
            status=ServiceOperationalStatus.OPERATIONAL,
            last_updated=now,
            message="Enterprise 802.1X wireless controllers and RADIUS authentication operational (Synthetic).",
        ),
        ServiceStatusRecord(
            service_name="github",
            status=ServiceOperationalStatus.OPERATIONAL,
            last_updated=now,
            message="GitHub Enterprise Cloud SSO & Repo Access operational (Synthetic).",
        ),
        ServiceStatusRecord(
            service_name="jira",
            status=ServiceOperationalStatus.OPERATIONAL,
            last_updated=now,
            message="Atlassian Cloud Jira Software & Service Desk operational (Synthetic).",
        ),
        ServiceStatusRecord(
            service_name="outlook",
            status=ServiceOperationalStatus.OPERATIONAL,
            last_updated=now,
            message="Microsoft 365 Exchange Online and Outlook Web Access operational (Synthetic).",
        ),
        ServiceStatusRecord(
            service_name="teams",
            status=ServiceOperationalStatus.OPERATIONAL,
            last_updated=now,
            message="Microsoft Teams chat, meetings, and calling services operational (Synthetic).",
        ),
    ]


def seed_it_operations_data(client: MongoDBClient) -> dict[str, int]:
    """Idempotently seed users, devices, and service statuses."""
    user_store = UserStore(client)
    device_store = DeviceStore(client)
    service_store = ServiceStatusStore(client)

    users = get_seed_users()
    for user in users:
        user_store.upsert(user)

    devices = get_seed_devices()
    for device in devices:
        device_store.upsert(device)

    services = get_seed_service_statuses()
    for service in services:
        service_store.upsert(service)

    logger.info(
        f"Seeded {len(users)} users, {len(devices)} devices, and {len(services)} service statuses."
    )
    return {
        "users": len(users),
        "devices": len(devices),
        "services": len(services),
    }


if __name__ == "__main__":
    config.validate_database_config()
    client = MongoDBClient(uri=config.db_url, database_name=config.db_name)
    client.connect()
    try:
        results = seed_it_operations_data(client)
        print(f"Seed complete: {results}")
    finally:
        client.disconnect()
