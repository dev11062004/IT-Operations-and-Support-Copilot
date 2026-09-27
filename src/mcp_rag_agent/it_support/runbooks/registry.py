"""Runbook registry managing enterprise procedure lookup, versioning, and selection."""

import logging
from typing import Optional

from mcp_rag_agent.it_support.intent import ITIntentClassifier
from mcp_rag_agent.it_support.models import ITCategory
from mcp_rag_agent.it_support.runbooks.models import Runbook
from mcp_rag_agent.it_support.runbooks.runbook_definitions import get_all_standard_runbooks

logger = logging.getLogger("RunbookRegistry")


class RunbookNotFoundError(KeyError):
    """Raised when a requested runbook or version does not exist."""
    pass


class RunbookRegistry:
    """In-memory thread-safe registry of validated troubleshooting runbooks."""

    def __init__(self, auto_populate: bool = True) -> None:
        # Key: (runbook_id, version) -> Runbook
        self._runbooks: dict[tuple[str, str], Runbook] = {}
        # Key: runbook_id -> active version str
        self._active_versions: dict[str, str] = {}
        self._classifier = ITIntentClassifier()

        if auto_populate:
            for runbook in get_all_standard_runbooks():
                self.register(runbook)

    def register(self, runbook: Runbook) -> None:
        """Register a validated runbook. If marked active, sets as active version for its ID."""
        runbook.validate_graph()
        key = (runbook.runbook_id, runbook.version)
        self._runbooks[key] = runbook
        if runbook.is_active or runbook.runbook_id not in self._active_versions:
            self._active_versions[runbook.runbook_id] = runbook.version
        logger.debug(f"[RUNBOOK_REGISTRY] Registered '{runbook.runbook_id}' v{runbook.version}")

    def get(self, runbook_id: str, version: Optional[str] = None) -> Runbook:
        """Retrieve a runbook by ID, resolving to the active version if version is omitted."""
        target_version = version or self._active_versions.get(runbook_id)
        if not target_version:
            raise RunbookNotFoundError(f"Runbook '{runbook_id}' is not registered.")
        key = (runbook_id, target_version)
        if key not in self._runbooks:
            raise RunbookNotFoundError(f"Runbook '{runbook_id}' version '{target_version}' not found.")
        return self._runbooks[key]

    def list_active(self) -> list[Runbook]:
        """List all currently active runbooks."""
        return [
            self._runbooks[(r_id, v)]
            for r_id, v in self._active_versions.items()
            if (r_id, v) in self._runbooks
        ]

    def get_by_category(self, category: ITCategory) -> list[Runbook]:
        """Return all active runbooks matching an ITCategory."""
        return [rb for rb in self.list_active() if rb.category == category]

    def find_for_query(self, query: str, category: Optional[ITCategory] = None) -> Optional[Runbook]:
        """Select the most appropriate runbook following User issue -> IT Intent -> Runbook selection."""
        lowered = query.lower()
        normalized = lowered.replace("-", " ")

        # 1. Target Category: use explicit category or infer from IT Intent
        target_category = category
        if not target_category:
            classification = self._classifier.classify(query)
            if classification.category and classification.category != ITCategory.OTHER:
                target_category = classification.category

        if target_category:
            candidates = self.get_by_category(target_category)
            if len(candidates) == 1:
                return candidates[0]
            if len(candidates) > 1:
                # If multiple candidates in category (e.g. GitHub vs Jira, Printer vs Display), score by tags/words
                scored: list[tuple[int, Runbook]] = []
                for candidate in candidates:
                    score = 0
                    for tag in candidate.tags:
                        tag_norm = tag.lower().replace("-", " ")
                        if tag_norm in normalized or tag.lower() in lowered:
                            score += 3
                    for word in candidate.title.lower().split():
                        if len(word) > 3 and word in lowered:
                            score += 2
                    scored.append((score, candidate))
                scored.sort(key=lambda x: x[0], reverse=True)
                return scored[0][1]

        # 2. Tag and Title Heuristic Match across all active runbooks
        active = self.list_active()
        scored_candidates: list[tuple[int, Runbook]] = []
        for rb in active:
            score = 0
            for tag in rb.tags:
                tag_norm = tag.lower().replace("-", " ")
                if tag_norm in normalized or tag.lower() in lowered:
                    score += 3
            for word in rb.title.lower().split():
                if len(word) > 3 and word in lowered:
                    score += 2
            if score > 0:
                scored_candidates.append((score, rb))

        if scored_candidates:
            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            return scored_candidates[0][1]

        return None


# Global singleton instance pre-populated with standard enterprise runbooks
_default_registry: Optional[RunbookRegistry] = None


def get_default_registry() -> RunbookRegistry:
    """Return the global default RunbookRegistry singleton."""
    global _default_registry
    if _default_registry is None:
        _default_registry = RunbookRegistry(auto_populate=True)
    return _default_registry
