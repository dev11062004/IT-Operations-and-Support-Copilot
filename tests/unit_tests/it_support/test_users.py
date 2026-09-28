"""Unit tests for user context models, store, and domain service."""

from unittest.mock import MagicMock

import pytest

from mcp_rag_agent.it_support.users.models import (
    SupportTier,
    UserContextRecord,
    UserStatus,
)
from mcp_rag_agent.it_support.users.service import UserService
from mcp_rag_agent.it_support.users.store import UserNotFoundError, UserStore


def _sample_user() -> UserContextRecord:
    return UserContextRecord(
        user_id="EMP-1001",
        name="John Doe",
        email="john.doe@enterprise.internal",
        department="Engineering",
        role="Software Engineer",
        support_tier=SupportTier.STANDARD,
        status=UserStatus.ACTIVE,
        metadata={"location": "New York"},
    )


class MemoryUserStore:
    """In-memory test double for UserStore."""

    def __init__(self) -> None:
        self.records: dict[str, UserContextRecord] = {}

    def create(self, user: UserContextRecord) -> UserContextRecord:
        self.records[user.user_id] = user
        return user

    def upsert(self, user: UserContextRecord) -> UserContextRecord:
        self.records[user.user_id] = user
        return user

    def get(self, user_id: str) -> UserContextRecord:
        if user_id not in self.records:
            raise UserNotFoundError(f"User '{user_id}' not found")
        return self.records[user_id]

    def list(self, filters=None, limit=100):
        return list(self.records.values())[:limit]

    def update_fields(self, user_id: str, fields: dict) -> UserContextRecord:
        if user_id not in self.records:
            raise UserNotFoundError(f"User '{user_id}' not found")
        payload = self.records[user_id].model_dump()
        payload.update(fields)
        self.records[user_id] = UserContextRecord.model_validate(payload)
        return self.records[user_id]


def test_user_model_instantiation_and_validation() -> None:
    user = _sample_user()
    assert user.user_id == "EMP-1001"
    assert user.name == "John Doe"
    assert user.department == "Engineering"
    assert user.support_tier == SupportTier.STANDARD
    assert user.status == UserStatus.ACTIVE


def test_user_service_valid_lookup() -> None:
    store = MemoryUserStore()
    user = _sample_user()
    store.create(user)

    service = UserService(store)
    found = service.get_user_context("EMP-1001")
    assert found.user_id == "EMP-1001"
    assert found.name == "John Doe"
    assert found.department == "Engineering"


def test_user_service_missing_user_raises_not_found() -> None:
    store = MemoryUserStore()
    service = UserService(store)
    with pytest.raises(UserNotFoundError):
        service.get_user_context("EMP-9999")


def test_user_service_invalid_id_raises_value_error() -> None:
    store = MemoryUserStore()
    service = UserService(store)
    with pytest.raises(ValueError):
        service.get_user_context("")
    with pytest.raises(ValueError):
        service.get_user_context("   ")


def test_user_store_mongodb_adapter() -> None:
    client = MagicMock()
    collection = client.get_collection.return_value
    user = _sample_user()
    collection.find_one.return_value = user.model_dump(mode="json")
    collection.update_one.return_value.matched_count = 1

    store = UserStore(client)
    assert store.create(user).user_id == "EMP-1001"
    assert store.get("EMP-1001").name == "John Doe"
    assert store.upsert(user).user_id == "EMP-1001"

    collection.find_one.return_value = None
    with pytest.raises(UserNotFoundError):
        store.get("EMP-UNKNOWN")
