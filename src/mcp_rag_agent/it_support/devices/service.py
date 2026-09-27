"""Device domain service for fetching and managing device context."""

from typing import Any, Optional

from mcp_rag_agent.it_support.devices.models import DeviceRecord
from mcp_rag_agent.it_support.devices.store import DeviceNotFoundError, DeviceStore


class DeviceService:
    """Domain service managing device info lookups and management."""

    def __init__(self, store: DeviceStore) -> None:
        self._store = store

    def get_device_info(self, device_id: str) -> DeviceRecord:
        """Retrieve device info by device_id.

        Args:
            device_id: Unique identifier for the enterprise device.

        Returns:
            DeviceRecord

        Raises:
            ValueError: If device_id is empty or invalid.
            DeviceNotFoundError: If device does not exist.
        """
        if not device_id or not isinstance(device_id, str) or not device_id.strip():
            raise ValueError("device_id must be a non-empty string")
        return self._store.get(device_id.strip())

    def get_user_devices(self, user_id: str) -> list[DeviceRecord]:
        """Retrieve all devices registered to a specific user.

        Args:
            user_id: Unique identifier for the employee/user.

        Returns:
            List of DeviceRecords.
        """
        if not user_id or not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id must be a non-empty string")
        return self._store.get_by_user(user_id.strip())

    def create_device(self, device: DeviceRecord) -> DeviceRecord:
        """Register a new device."""
        return self._store.create(device)

    def upsert_device(self, device: DeviceRecord) -> DeviceRecord:
        """Upsert a device record (idempotent seeding)."""
        return self._store.upsert(device)

    def list_devices(self, filters: Optional[dict[str, Any]] = None) -> list[DeviceRecord]:
        """List devices matching optional filter criteria."""
        return self._store.list(filters)
