"""MongoDB persistence adapter for users; reuses shared MongoDBClient."""

from datetime import datetime, timezone
from typing import Any

from mcp_rag_agent.it_support.users.models import UserContextRecord
from mcp_rag_agent.mongodb import MongoDBClient


class UserNotFoundError(KeyError):
    """Raised when a requested user cannot be found."""

    pass


class UserStore:
    """Persistence store for enterprise user context in MongoDB."""

    def __init__(
        self, mongo_client: MongoDBClient, collection_name: str = "it_users"
    ) -> None:
        self._mongo_client = mongo_client
        self._collection_name = collection_name

    @property
    def _collection(self) -> Any:
        return self._mongo_client.get_collection(self._collection_name)

    @staticmethod
    def _to_record(document: dict[str, Any] | None) -> UserContextRecord:
        if document is None:
            raise UserNotFoundError("User not found")
        document.pop("_id", None)
        return UserContextRecord.model_validate(document)

    def create(self, user: UserContextRecord) -> UserContextRecord:
        self._collection.insert_one(user.model_dump(mode="json"))
        return user

    def upsert(self, user: UserContextRecord) -> UserContextRecord:
        payload = user.model_dump(mode="json")
        self._collection.update_one(
            {"user_id": user.user_id},
            {"$set": payload},
            upsert=True,
        )
        return user

    def get(self, user_id: str) -> UserContextRecord:
        doc = self._collection.find_one({"user_id": user_id})
        return self._to_record(doc)

    def list(
        self, filters: dict[str, Any] | None = None, limit: int = 100
    ) -> list[UserContextRecord]:
        return [
            self._to_record(item)
            for item in self._collection.find(filters or {}).limit(limit)
        ]

    def update_fields(self, user_id: str, fields: dict[str, Any]) -> UserContextRecord:
        payload = {**fields, "updated_at": datetime.now(timezone.utc).isoformat()}
        result = self._collection.update_one({"user_id": user_id}, {"$set": payload})
        if not result.matched_count:
            raise UserNotFoundError(f"User '{user_id}' not found")
        return self.get(user_id)
