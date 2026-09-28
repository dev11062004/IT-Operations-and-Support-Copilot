"""MongoDB persistence adapter for service statuses; reuses shared MongoDBClient."""

from datetime import datetime, timezone
from typing import Any

from mcp_rag_agent.it_support.services.models import (
    ServiceOperationalStatus,
    ServiceStatusRecord,
)
from mcp_rag_agent.mongodb import MongoDBClient


class ServiceNotFoundError(KeyError):
    """Raised when a requested service status cannot be found."""

    pass


class ServiceStatusStore:
    """Persistence store for enterprise service statuses in MongoDB."""

    def __init__(
        self, mongo_client: MongoDBClient, collection_name: str = "it_service_statuses"
    ) -> None:
        self._mongo_client = mongo_client
        self._collection_name = collection_name

    @property
    def _collection(self) -> Any:
        return self._mongo_client.get_collection(self._collection_name)

    @staticmethod
    def _to_record(document: dict[str, Any] | None) -> ServiceStatusRecord:
        if document is None:
            raise ServiceNotFoundError("Service status not found")
        document.pop("_id", None)
        return ServiceStatusRecord.model_validate(document)

    def upsert(self, record: ServiceStatusRecord) -> ServiceStatusRecord:
        payload = record.model_dump(mode="json")
        self._collection.update_one(
            {"service_name": record.service_name},
            {"$set": payload},
            upsert=True,
        )
        return record

    def get(self, service_name: str) -> ServiceStatusRecord:
        doc = self._collection.find_one({"service_name": service_name})
        return self._to_record(doc)

    def list_all(self) -> list[ServiceStatusRecord]:
        return [self._to_record(item) for item in self._collection.find({})]
