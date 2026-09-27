"""MongoDB persistence adapter for devices; reuses shared MongoDBClient."""

from datetime import datetime, timezone
from typing import Any

from mcp_rag_agent.it_support.devices.models import DeviceRecord
from mcp_rag_agent.mongodb import MongoDBClient


class DeviceNotFoundError(KeyError):
    """Raised when a requested device cannot be found."""
    pass


class DeviceStore:
    """Persistence store for enterprise devices in MongoDB."""

    def __init__(self, mongo_client: MongoDBClient, collection_name: str = "it_devices") -> None:
        self._mongo_client = mongo_client
        self._collection_name = collection_name

    @property
    def _collection(self) -> Any:
        return self._mongo_client.get_collection(self._collection_name)

    @staticmethod
    def _to_record(document: dict[str, Any] | None) -> DeviceRecord:
        if document is None:
            raise DeviceNotFoundError("Device not found")
        document.pop("_id", None)
        return DeviceRecord.model_validate(document)

    def create(self, device: DeviceRecord) -> DeviceRecord:
        self._collection.insert_one(device.model_dump(mode="json"))
        return device

    def upsert(self, device: DeviceRecord) -> DeviceRecord:
        payload = device.model_dump(mode="json")
        self._collection.update_one(
            {"device_id": device.device_id},
            {"$set": payload},
            upsert=True,
        )
        return device

    def get(self, device_id: str) -> DeviceRecord:
        doc = self._collection.find_one({"device_id": device_id})
        return self._to_record(doc)

    def get_by_user(self, user_id: str) -> list[DeviceRecord]:
        docs = self._collection.find({"user_id": user_id})
        return [self._to_record(doc) for doc in docs]

    def list(self, filters: dict[str, Any] | None = None, limit: int = 100) -> list[DeviceRecord]:
        return [self._to_record(item) for item in self._collection.find(filters or {}).limit(limit)]

    def update_fields(self, device_id: str, fields: dict[str, Any]) -> DeviceRecord:
        payload = {**fields, "updated_at": datetime.now(timezone.utc).isoformat()}
        result = self._collection.update_one({"device_id": device_id}, {"$set": payload})
        if not result.matched_count:
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        return self.get(device_id)
