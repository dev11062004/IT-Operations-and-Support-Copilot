"""Incident use cases, including deterministic known-incident detection."""

from mcp_rag_agent.it_support.incidents.models import IncidentCreate, IncidentMatchCriteria, IncidentRecord
from mcp_rag_agent.it_support.incidents.store import IncidentStore
from mcp_rag_agent.it_support.models import IncidentStatus


class IncidentService:
    def __init__(self, store: IncidentStore) -> None:
        self._store = store

    def create_incident(self, request: IncidentCreate) -> IncidentRecord:
        return self._store.create(IncidentRecord(**request.model_dump()))

    def get_incident(self, incident_id: str) -> IncidentRecord:
        return self._store.get(incident_id)

    def update_status(self, incident_id: str, status: IncidentStatus) -> IncidentRecord:
        return self._store.update_status(incident_id, status)

    def list_active_incidents(self) -> list[IncidentRecord]:
        return self._store.list_active()

    def find_known_incident(self, criteria: IncidentMatchCriteria) -> IncidentRecord | None:
        """Match active incidents on service plus exact structured incident signals."""
        for incident in self._store.find_matching(criteria):
            if incident.service.casefold() != criteria.service.casefold():
                continue
            signals = ("product", "platform", "category", "error_code")
            supplied = [name for name in signals if getattr(criteria, name) is not None]
            if not supplied:
                return incident

            def _val(obj: object, attr: str) -> str | None:
                val = getattr(obj, attr, None)
                if val is None:
                    return None
                if hasattr(val, "value"):
                    return str(val.value).casefold()
                return str(val).casefold()

            if all(_val(incident, name) == _val(criteria, name) for name in supplied):
                return incident
        return None
