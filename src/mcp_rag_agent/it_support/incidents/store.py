"""MongoDB persistence adapter for incidents."""

from datetime import datetime, timezone
from typing import Any

from mcp_rag_agent.it_support.incidents.models import (
    IncidentMatchCriteria,
    IncidentRecord,
)
from mcp_rag_agent.it_support.models import IncidentStatus
from mcp_rag_agent.mongodb import MongoDBClient


class IncidentNotFoundError(KeyError):
    pass


class IncidentStore:
    def __init__(
        self, mongo_client: MongoDBClient, collection_name: str = "it_incidents"
    ) -> None:
        self._mongo_client = mongo_client
        self._collection_name = collection_name

    @property
    def _collection(self) -> Any:
        return self._mongo_client.get_collection(self._collection_name)

    @staticmethod
    def _to_record(document: dict[str, Any] | None) -> IncidentRecord:
        if document is None:
            raise IncidentNotFoundError("Incident not found")
        document.pop("_id", None)
        return IncidentRecord.model_validate(document)

    def create(self, incident: IncidentRecord) -> IncidentRecord:
        self._collection.insert_one(incident.model_dump(mode="json"))
        return incident

    def get(self, incident_id: str) -> IncidentRecord:
        return self._to_record(self._collection.find_one({"incident_id": incident_id}))

    def update_status(self, incident_id: str, status: IncidentStatus) -> IncidentRecord:
        updates: dict[str, Any] = {
            "status": status.value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if status is IncidentStatus.RESOLVED:
            updates["end_time"] = datetime.now(timezone.utc).isoformat()
        result = self._collection.update_one(
            {"incident_id": incident_id}, {"$set": updates}
        )
        if not result.matched_count:
            raise IncidentNotFoundError(incident_id)
        return self.get(incident_id)

    def list_active(self, limit: int = 100) -> list[IncidentRecord]:
        statuses = [
            IncidentStatus.INVESTIGATING.value,
            IncidentStatus.IDENTIFIED.value,
            IncidentStatus.MONITORING.value,
        ]
        return [
            self._to_record(item)
            for item in self._collection.find({"status": {"$in": statuses}}).limit(
                limit
            )
        ]

    def list_all(self, limit: int = 100) -> list[IncidentRecord]:
        return [
            self._to_record(item) for item in self._collection.find({}).limit(limit)
        ]

    def find_matching(self, criteria: IncidentMatchCriteria) -> list[IncidentRecord]:
        """Return active exact structured candidates for deterministic scoring."""
        query: dict[str, Any] = {
            "service": criteria.service,
            "status": {
                "$in": [
                    IncidentStatus.INVESTIGATING.value,
                    IncidentStatus.IDENTIFIED.value,
                    IncidentStatus.MONITORING.value,
                ]
            },
        }
        for name in ("product", "platform", "category", "error_code"):
            value = getattr(criteria, name)
            if value is not None:
                query[name] = value.value if hasattr(value, "value") else value
        return [
            self._to_record(item) for item in self._collection.find(query).limit(100)
        ]
