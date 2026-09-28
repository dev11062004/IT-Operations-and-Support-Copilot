"""Offline checks for deterministic and fallback IT intent classification."""

from unittest.mock import AsyncMock

import pytest

# Import the existing agent package first, matching application startup order.
import mcp_rag_agent.agent  # noqa: F401
from mcp_rag_agent.guardrails.input_guardrails import check_out_of_domain
from mcp_rag_agent.it_support.intent import ITIntentClassifier
from mcp_rag_agent.it_support.models import ITCategory, ITIntentResult


@pytest.mark.parametrize(
    ("query", "category"),
    [
        ("VPN not working", ITCategory.VPN),
        ("Wi-Fi keeps disconnecting", ITCategory.WIFI),
        ("I forgot my password", ITCategory.PASSWORD),
        ("My MFA code is rejected", ITCategory.MFA),
        ("I need GitHub access", ITCategory.ACCESS),
        ("I need Jira access", ITCategory.ACCESS),
        ("My laptop monitor is blank", ITCategory.HARDWARE),
        ("The application keeps crashing", ITCategory.SOFTWARE),
        ("I clicked a phishing link", ITCategory.SECURITY),
        ("The network is unavailable", ITCategory.NETWORK),
    ],
)
def test_known_queries_use_deterministic_rules(
    query: str, category: ITCategory
) -> None:
    result = ITIntentClassifier().classify(query)
    assert result.category is category
    assert result.classification_source == "rule"
    assert result.confidence >= 0.60


def test_rule_classification_extracts_requested_entities() -> None:
    result = ITIntentClassifier().classify(
        "My Windows laptop shows VPN-ERR-742 when connecting to the corporate VPN."
    )
    assert result.category is ITCategory.VPN
    assert result.entities.platform == "Windows"
    assert result.entities.device_type == "laptop"
    assert result.entities.product == "corporate VPN"
    assert result.entities.error_code == "VPN-ERR-742"


def test_unknown_query_is_structured_and_concise() -> None:
    result = ITIntentClassifier().classify("The fizzing quasar emits photonic blargle")
    assert result.category is ITCategory.OTHER
    assert result.intent == "unknown"
    assert result.classification_source == "rule"
    assert len(result.reason) < 300


@pytest.mark.parametrize(
    "query",
    ["My Wi-Fi is unstable", "I need GitHub access", "Please help with a Jira ticket"],
)
def test_it_terms_are_not_rejected_as_out_of_domain(query: str) -> None:
    is_in_domain, violations = check_out_of_domain(query)
    assert is_in_domain
    assert violations == []


@pytest.mark.asyncio
async def test_deterministic_match_never_calls_fallback() -> None:
    fallback = AsyncMock()
    result = await ITIntentClassifier(fallback).classify_async("VPN not working")
    fallback.classify.assert_not_awaited()
    assert result.category is ITCategory.VPN


@pytest.mark.asyncio
async def test_ambiguous_query_uses_injected_llm_fallback() -> None:
    fallback = AsyncMock()
    fallback.classify.return_value = ITIntentResult(
        intent="issue",
        category=ITCategory.SOFTWARE,
        confidence=0.70,
        reason="Fallback identified a software issue.",
        classification_source="rule",
    )
    result = await ITIntentClassifier(fallback).classify_async(
        "The workspace object is failing"
    )
    fallback.classify.assert_awaited_once()
    assert result.category is ITCategory.SOFTWARE
    assert result.classification_source == "llm"
