"""Unit tests for service status models, store, and domain service."""

from unittest.mock import MagicMock
import pytest

from mcp_rag_agent.it_support.incidents.models import IncidentCreate, IncidentRecord
from mcp_rag_agent.it_support.incidents.service import IncidentService
from mcp_rag_agent.it_support.models import IncidentStatus, Priority
from mcp_rag_agent.it_support.services.models import (
    ServiceOperationalStatus,
    ServiceStatusRecord,
)
from mcp_rag_agent.it_support.services.service import ServiceStatusChecker
from mcp_rag_agent.it_support.services.store import ServiceNotFoundError, ServiceStatusStore


class MemoryServiceStore:
    """In-memory test double for ServiceStatusStore."""

    def __init__(self) -> None:
        self.records: dict[str, ServiceStatusRecord] = {}

    def upsert(self, record: ServiceStatusRecord) -> ServiceStatusRecord:
        self.records[record.service_name] = record
        return record

    def get(self, service_name: str) -> ServiceStatusRecord:
        if service_name not in self.records:
            raise ServiceNotFoundError(f"Service '{service_name}' not found")
        return self.records[service_name]

    def list_all(self) -> list[ServiceStatusRecord]:
        return list(self.records.values())


class MemoryIncidentStore:
    """In-memory test double for IncidentStore."""

    def __init__(self) -> None:
        self.records: dict[str, IncidentRecord] = {}

    def create(self, incident: IncidentRecord) -> IncidentRecord:
        self.records[incident.incident_id] = incident
        return incident

    def get(self, incident_id: str) -> IncidentRecord:
        return self.records[incident_id]

    def list_active(self):
        return [item for item in self.records.values() if item.status != IncidentStatus.RESOLVED]

    def find_matching(self, criteria):
        return [item for item in self.list_active() if item.service == criteria.service]


def test_service_status_known_services_and_aliases() -> None:
    checker = ServiceStatusChecker()
    # Canonical services
    vpn_status = checker.check_service_status("corporate_vpn")
    assert vpn_status.service_name == "corporate_vpn"
    assert vpn_status.status == ServiceOperationalStatus.OPERATIONAL

    # Aliases
    wifi_alias = checker.check_service_status("wi-fi")
    assert wifi_alias.service_name == "corporate_wifi"
    assert wifi_alias.status == ServiceOperationalStatus.OPERATIONAL

    jira_status = checker.check_service_status("jira")
    assert jira_status.service_name == "jira"
    assert jira_status.status == ServiceOperationalStatus.OPERATIONAL


def test_service_status_unknown_service() -> None:
    checker = ServiceStatusChecker()
    unknown = checker.check_service_status("nonexistent_service_xyz")
    assert unknown.status == ServiceOperationalStatus.UNKNOWN
    assert "not a recognized" in unknown.message


def test_service_status_invalid_input_raises_value_error() -> None:
    checker = ServiceStatusChecker()
    with pytest.raises(ValueError):
        checker.check_service_status("")
    with pytest.raises(ValueError):
        checker.check_service_status("   ")


def test_service_status_active_incident_correlation() -> None:
    incident_store = MemoryIncidentStore()
    incident_service = IncidentService(incident_store)

    # Register an active high-severity incident for VPN
    incident_service.create_incident(
        IncidentCreate(
            title="Global VPN Gateway Degradation",
            description="High latency on US-East VPN nodes",
            service="corporate_vpn",
            severity=Priority.HIGH,
            status=IncidentStatus.INVESTIGATING,
        )
    )

    checker = ServiceStatusChecker(incident_service=incident_service)
    status = checker.check_service_status("vpn")

    assert status.status == ServiceOperationalStatus.OUTAGE
    assert status.known_incident_id is not None
    assert "Active incident" in status.message


def test_service_status_store_mongodb_adapter() -> None:
    client = MagicMock()
    collection = client.get_collection.return_value
    record = ServiceStatusRecord(service_name="corporate_vpn", status=ServiceOperationalStatus.OPERATIONAL)
    collection.find_one.return_value = record.model_dump(mode="json")
    collection.find.return_value = [record.model_dump(mode="json")]

    store = ServiceStatusStore(client)
    assert store.upsert(record).service_name == "corporate_vpn"
    assert store.get("corporate_vpn").status == ServiceOperationalStatus.OPERATIONAL
    assert len(store.list_all()) == 1
