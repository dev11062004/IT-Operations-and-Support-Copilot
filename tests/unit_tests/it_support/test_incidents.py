"""Incident persistence and deterministic known-incident matching tests."""

from unittest.mock import MagicMock

from mcp_rag_agent.it_support.incidents.models import (
    IncidentCreate,
    IncidentMatchCriteria,
    IncidentRecord,
)
from mcp_rag_agent.it_support.incidents.service import IncidentService
from mcp_rag_agent.it_support.incidents.store import IncidentStore
from mcp_rag_agent.it_support.models import IncidentStatus, ITCategory, Priority


def _incident() -> IncidentCreate:
    return IncidentCreate(
        title="VPN outage",
        description="VPN unavailable",
        service="corporate VPN",
        severity=Priority.HIGH,
        product="corporate VPN",
        platform="Windows",
        category=ITCategory.VPN,
        error_code="VPN-ERR-742",
    )


class MemoryIncidentStore:
    def __init__(self) -> None:
        self.records: dict[str, IncidentRecord] = {}

    def create(self, incident: IncidentRecord) -> IncidentRecord:
        self.records[incident.incident_id] = incident
        return incident

    def get(self, incident_id: str) -> IncidentRecord:
        return self.records[incident_id]

    def update_status(self, incident_id: str, status: IncidentStatus) -> IncidentRecord:
        self.records[incident_id] = self.records[incident_id].model_copy(
            update={"status": status}
        )
        return self.records[incident_id]

    def list_active(self):
        return [
            item
            for item in self.records.values()
            if item.status is not IncidentStatus.RESOLVED
        ]

    def find_matching(self, criteria):
        return [item for item in self.list_active() if item.service == criteria.service]


def test_incident_create_retrieve_and_status_update() -> None:
    service = IncidentService(MemoryIncidentStore())
    created = service.create_incident(_incident())
    assert service.get_incident(created.incident_id).service == "corporate VPN"
    assert (
        service.update_status(created.incident_id, IncidentStatus.IDENTIFIED).status
        is IncidentStatus.IDENTIFIED
    )


def test_known_incident_detection_requires_structured_match() -> None:
    service = IncidentService(MemoryIncidentStore())
    known = service.create_incident(_incident())
    criteria = IncidentMatchCriteria(
        service="corporate VPN",
        product="corporate VPN",
        platform="Windows",
        category=ITCategory.VPN,
        error_code="VPN-ERR-742",
    )
    assert service.find_known_incident(criteria).incident_id == known.incident_id
    assert (
        service.find_known_incident(
            criteria.model_copy(update={"error_code": "OTHER-1"})
        )
        is None
    )


def test_incident_store_uses_mongodb() -> None:
    client = MagicMock()
    collection = client.get_collection.return_value
    record = IncidentRecord(**_incident().model_dump())
    collection.find_one.return_value = record.model_dump(mode="json")
    collection.update_one.return_value.matched_count = 1
    store = IncidentStore(client)
    assert store.create(record).incident_id == record.incident_id
    assert store.get(record.incident_id).incident_id == record.incident_id


def test_incident_resolve_sets_end_time() -> None:
    client = MagicMock()
    collection = client.get_collection.return_value
    record = IncidentRecord(**_incident().model_dump())
    collection.find_one.return_value = record.model_dump(mode="json")
    collection.update_one.return_value.matched_count = 1
    store = IncidentStore(client)

    store.update_status(record.incident_id, IncidentStatus.RESOLVED)
    # Check that update_one was called with end_time in $set
    call_args = collection.update_one.call_args
    assert "end_time" in call_args[0][1]["$set"]
    assert call_args[0][1]["$set"]["status"] == IncidentStatus.RESOLVED.value


def test_incident_store_queries_and_not_found_handling() -> None:
    import pytest

    from mcp_rag_agent.it_support.incidents.store import IncidentNotFoundError

    client = MagicMock()
    collection = client.get_collection.return_value
    record = IncidentRecord(**_incident().model_dump())
    store = IncidentStore(client)

    # list_active
    collection.find.return_value.limit.return_value = [record.model_dump(mode="json")]
    active = store.list_active()
    assert len(active) == 1
    assert active[0].incident_id == record.incident_id

    # find_matching
    matching = store.find_matching(
        IncidentMatchCriteria(service="corporate VPN", category=ITCategory.VPN)
    )
    assert len(matching) == 1

    # Not found on get
    collection.find_one.return_value = None
    with pytest.raises(IncidentNotFoundError):
        store.get("INC-NONEXISTENT")

    # Not found on update_status
    collection.update_one.return_value.matched_count = 0
    with pytest.raises(IncidentNotFoundError):
        store.update_status("INC-NONEXISTENT", IncidentStatus.IDENTIFIED)


def test_incident_service_find_known_case_insensitivity_and_partial_signals() -> None:
    service = IncidentService(MemoryIncidentStore())
    known = service.create_incident(_incident())

    # Exact service match with empty extra signals matches
    criteria_service_only = IncidentMatchCriteria(service="corporate VPN")
    matched = service.find_known_incident(criteria_service_only)
    assert matched is not None
    assert matched.incident_id == known.incident_id

    # Case-insensitive structured signal (platform='windows' vs 'Windows')
    criteria_platform_lower = IncidentMatchCriteria(
        service="corporate VPN", platform="windows"
    )
    assert service.find_known_incident(criteria_platform_lower) is not None

    # List active incidents through service
    active_incidents = service.list_active_incidents()
    assert len(active_incidents) == 1
    assert active_incidents[0].incident_id == known.incident_id

    # Different service does not match
    criteria_diff_service = IncidentMatchCriteria(service="Office 365")
    assert service.find_known_incident(criteria_diff_service) is None
