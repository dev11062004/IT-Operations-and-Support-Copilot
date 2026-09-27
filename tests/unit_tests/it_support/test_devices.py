"""Unit tests for device context models, store, and domain service."""

from unittest.mock import MagicMock
import pytest

from mcp_rag_agent.it_support.devices.models import DeviceRecord
from mcp_rag_agent.it_support.devices.service import DeviceService
from mcp_rag_agent.it_support.devices.store import DeviceNotFoundError, DeviceStore


def _sample_device() -> DeviceRecord:
    return DeviceRecord(
        device_id="DEV-001",
        user_id="EMP-1001",
        device_type="laptop",
        manufacturer="Apple",
        model='MacBook Pro 16" M3',
        os="macOS",
        os_version="14.3.1",
        hostname="MAC-JDOE-01",
        status="active",
        vpn_client_version="5.1.2",
        security_status="compliant",
    )


class MemoryDeviceStore:
    """In-memory test double for DeviceStore."""

    def __init__(self) -> None:
        self.records: dict[str, DeviceRecord] = {}

    def create(self, device: DeviceRecord) -> DeviceRecord:
        self.records[device.device_id] = device
        return device

    def upsert(self, device: DeviceRecord) -> DeviceRecord:
        self.records[device.device_id] = device
        return device

    def get(self, device_id: str) -> DeviceRecord:
        if device_id not in self.records:
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        return self.records[device_id]

    def get_by_user(self, user_id: str) -> list[DeviceRecord]:
        return [d for d in self.records.values() if d.user_id == user_id]

    def list(self, filters=None, limit=100):
        return list(self.records.values())[:limit]


def test_device_model_instantiation_and_validation() -> None:
    device = _sample_device()
    assert device.device_id == "DEV-001"
    assert device.user_id == "EMP-1001"
    assert device.os == "macOS"
    assert device.vpn_client_version == "5.1.2"
    assert device.security_status == "compliant"


def test_device_service_lookup_by_device_id() -> None:
    store = MemoryDeviceStore()
    device = _sample_device()
    store.create(device)

    service = DeviceService(store)
    found = service.get_device_info("DEV-001")
    assert found.device_id == "DEV-001"
    assert found.hostname == "MAC-JDOE-01"


def test_device_service_lookup_by_user_id() -> None:
    store = MemoryDeviceStore()
    dev1 = _sample_device()
    dev2 = DeviceRecord(
        device_id="DEV-002",
        user_id="EMP-1001",
        device_type="phone",
        manufacturer="Apple",
        model="iPhone 15 Pro",
        os="iOS",
        os_version="17.4",
        status="active",
    )
    store.create(dev1)
    store.create(dev2)

    service = DeviceService(store)
    user_devices = service.get_user_devices("EMP-1001")
    assert len(user_devices) == 2
    device_ids = {d.device_id for d in user_devices}
    assert device_ids == {"DEV-001", "DEV-002"}


def test_device_service_missing_device_raises_not_found() -> None:
    store = MemoryDeviceStore()
    service = DeviceService(store)
    with pytest.raises(DeviceNotFoundError):
        service.get_device_info("DEV-999")


def test_device_service_invalid_id_raises_value_error() -> None:
    store = MemoryDeviceStore()
    service = DeviceService(store)
    with pytest.raises(ValueError):
        service.get_device_info("")
    with pytest.raises(ValueError):
        service.get_user_devices("   ")


def test_device_store_mongodb_adapter() -> None:
    client = MagicMock()
    collection = client.get_collection.return_value
    device = _sample_device()
    collection.find_one.return_value = device.model_dump(mode="json")
    collection.find.return_value = [device.model_dump(mode="json")]

    store = DeviceStore(client)
    assert store.create(device).device_id == "DEV-001"
    assert store.get("DEV-001").hostname == "MAC-JDOE-01"
    assert len(store.get_by_user("EMP-1001")) == 1

    collection.find_one.return_value = None
    with pytest.raises(DeviceNotFoundError):
        store.get("DEV-UNKNOWN")
