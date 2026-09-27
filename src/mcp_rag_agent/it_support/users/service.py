"""User domain service for fetching and managing user context."""

from typing import Any, Optional

from mcp_rag_agent.it_support.users.models import UserContextRecord
from mcp_rag_agent.it_support.users.store import UserNotFoundError, UserStore


class UserService:
    """Domain service managing user context lookups and updates."""

    def __init__(self, store: UserStore) -> None:
        self._store = store

    def get_user_context(self, user_id: str) -> UserContextRecord:
        """Retrieve user context by user_id with validation.

        Args:
            user_id: Unique identifier for the employee/user.

        Returns:
            UserContextRecord

        Raises:
            ValueError: If user_id is empty or invalid.
            UserNotFoundError: If user does not exist in store.
        """
        if not user_id or not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id must be a non-empty string")
        return self._store.get(user_id.strip())

    def create_user(self, user: UserContextRecord) -> UserContextRecord:
        """Create or register a user record."""
        return self._store.create(user)

    def upsert_user(self, user: UserContextRecord) -> UserContextRecord:
        """Upsert a user record (idempotent seeding)."""
        return self._store.upsert(user)

    def list_users(self, filters: Optional[dict[str, Any]] = None) -> list[UserContextRecord]:
        """List users matching optional filter criteria."""
        return self._store.list(filters)
