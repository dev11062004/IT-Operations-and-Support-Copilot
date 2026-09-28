"""Service status domain service for monitoring enterprise service health."""

import re
from datetime import datetime, timezone
from typing import Any, Optional

from mcp_rag_agent.it_support.incidents.models import IncidentMatchCriteria
from mcp_rag_agent.it_support.incidents.service import IncidentService
from mcp_rag_agent.it_support.models import IncidentStatus
from mcp_rag_agent.it_support.services.models import (
    ServiceOperationalStatus,
    ServiceStatusRecord,
)
from mcp_rag_agent.it_support.services.store import (
    ServiceNotFoundError,
    ServiceStatusStore,
)

# Canonical mapping for common variations
SERVICE_ALIASES: dict[str, str] = {
    "vpn": "corporate_vpn",
    "corporate_vpn": "corporate_vpn",
    "corp_vpn": "corporate_vpn",
    "wifi": "corporate_wifi",
    "wi-fi": "corporate_wifi",
    "corporate_wifi": "corporate_wifi",
    "corp_wifi": "corporate_wifi",
    "github": "github",
    "git": "github",
    "gh": "github",
    "jira": "jira",
    "atlassian": "jira",
    "outlook": "outlook",
    "exchange": "outlook",
    "email": "outlook",
    "o365": "outlook",
    "teams": "teams",
    "ms_teams": "teams",
    "microsoft_teams": "teams",
}


def normalize_service_name(name: str) -> str:
    """Normalize input service query into a canonical service key."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", name.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return SERVICE_ALIASES.get(cleaned, cleaned)


class ServiceStatusChecker:
    """Domain service checking synthetic operational status of enterprise services."""

    def __init__(
        self,
        store: Optional[ServiceStatusStore] = None,
        incident_service: Optional[IncidentService] = None,
    ) -> None:
        self._store = store
        self._incident_service = incident_service

    def check_service_status(self, service_name: str) -> ServiceStatusRecord:
        """Check operational status of a service with incident correlation.

        Args:
            service_name: Name or alias of the service (e.g. 'vpn', 'corporate_vpn', 'jira').

        Returns:
            ServiceStatusRecord containing status, timestamp, known_incident_id, and message.

        Raises:
            ValueError: If service_name is empty or invalid.
        """
        if (
            not service_name
            or not isinstance(service_name, str)
            or not service_name.strip()
        ):
            raise ValueError("service_name must be a non-empty string")

        canonical_name = normalize_service_name(service_name)

        # 1. Check persistent store if available
        record: Optional[ServiceStatusRecord] = None
        if self._store is not None:
            try:
                record = self._store.get(canonical_name)
            except (ServiceNotFoundError, Exception):
                record = None

        # 2. If not found in store, create default synthetic record
        if record is None:
            if canonical_name in SERVICE_ALIASES.values():
                record = ServiceStatusRecord(
                    service_name=canonical_name,
                    status=ServiceOperationalStatus.OPERATIONAL,
                    last_updated=datetime.now(timezone.utc),
                    message=f"All systems operational for {canonical_name} (Synthetic).",
                )
            else:
                return ServiceStatusRecord(
                    service_name=service_name.strip(),
                    status=ServiceOperationalStatus.UNKNOWN,
                    last_updated=datetime.now(timezone.utc),
                    message=f"Service '{service_name}' is not a recognized or monitored enterprise service.",
                )

        # 3. Check for active known incidents via IncidentService
        if self._incident_service is not None:
            try:
                criteria = IncidentMatchCriteria(service=canonical_name)
                incident = self._incident_service.find_known_incident(criteria)
                if incident and incident.status != IncidentStatus.RESOLVED:
                    status = (
                        ServiceOperationalStatus.OUTAGE
                        if incident.severity.value in ("high", "critical")
                        else ServiceOperationalStatus.DEGRADED
                    )
                    record = record.model_copy(
                        update={
                            "status": status,
                            "known_incident_id": incident.incident_id,
                            "message": f"Active incident ({incident.incident_id}): {incident.title}",
                        }
                    )
            except Exception:
                pass

        return record

    def set_service_status(
        self,
        service_name: str,
        status: ServiceOperationalStatus,
        message: Optional[str] = None,
        known_incident_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> ServiceStatusRecord:
        """Update or register status for a service in the store."""
        canonical_name = normalize_service_name(service_name)
        record = ServiceStatusRecord(
            service_name=canonical_name,
            status=status,
            last_updated=datetime.now(timezone.utc),
            known_incident_id=known_incident_id,
            message=message or f"Status set to {status.value}",
            details=details or {},
        )
        if self._store is not None:
            self._store.upsert(record)
        return record

    def list_all_services(self) -> list[ServiceStatusRecord]:
        """List statuses for all stored or standard services."""
        if self._store is not None:
            records = self._store.list_all()
            if records:
                return records

        # Default fallback list
        return [
            self.check_service_status(canonical)
            for canonical in sorted(list(set(SERVICE_ALIASES.values())))
        ]
