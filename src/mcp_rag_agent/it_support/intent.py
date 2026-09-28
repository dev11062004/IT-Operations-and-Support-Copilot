"""Deterministic-first intent classification for IT support requests."""

import re
from typing import Protocol

from mcp_rag_agent.it_support.models import ITCategory, ITEntities, ITIntentResult


class IntentLLMFallback(Protocol):
    """Optional adapter used only for a query no rule can classify."""

    async def classify(self, query: str, rule_result: ITIntentResult) -> ITIntentResult:
        """Return a validated, concise classification result."""


_RULES: tuple[tuple[ITCategory, str, tuple[str, ...], float], ...] = (
    (
        ITCategory.SECURITY,
        "security_report",
        (
            "phishing",
            "malware",
            "ransomware",
            "breach",
            "compromised",
            "suspicious link",
        ),
        0.98,
    ),
    (
        ITCategory.PASSWORD,
        "issue",
        ("forgot my password", "forgot password", "reset password", "password expired"),
        0.96,
    ),
    (
        ITCategory.MFA,
        "issue",
        ("mfa", "2fa", "multi-factor", "authenticator", "verification code"),
        0.95,
    ),
    (
        ITCategory.ACCESS,
        "access_request",
        (
            "github access",
            "jira access",
            "need access",
            "access request",
            "access denied",
        ),
        0.94,
    ),
    (ITCategory.VPN, "issue", ("vpn", "virtual private network"), 0.95),
    (ITCategory.WIFI, "issue", ("wi-fi", "wifi", "wireless"), 0.94),
    (
        ITCategory.DNS,
        "issue",
        ("dns", "domain name resolution", "cannot resolve"),
        0.93,
    ),
    (
        ITCategory.SERVICE_OUTAGE,
        "issue",
        ("service outage", "system down", "all users", "outage"),
        0.92,
    ),
    (ITCategory.EMAIL, "issue", ("outlook", "email", "mailbox"), 0.90),
    (
        ITCategory.COLLABORATION,
        "issue",
        ("teams", "slack", "zoom", "sharepoint", "onedrive"),
        0.90,
    ),
    (
        ITCategory.DEVELOPER_TOOLS,
        "issue",
        ("github", "jira", "git", "ide", "developer tool"),
        0.88,
    ),
    (
        ITCategory.HARDWARE,
        "issue",
        ("laptop", "printer", "monitor", "keyboard", "mouse", "dock", "hardware"),
        0.86,
    ),
    (
        ITCategory.SOFTWARE,
        "issue",
        ("software", "application", "app crash", "install", "update", "license"),
        0.84,
    ),
    (
        ITCategory.ACCOUNT,
        "issue",
        ("account locked", "account", "login", "sign in"),
        0.80,
    ),
    (
        ITCategory.NETWORK,
        "issue",
        ("network", "internet", "ethernet", "connectivity"),
        0.80,
    ),
)
_ERROR_CODE = re.compile(
    r"\b(?:[A-Z][A-Z0-9]+(?:-[A-Z0-9]+)+|0x[0-9A-Fa-f]+|ERR_[A-Z_]+)\b"
)


def _extract_entities(query: str) -> ITEntities:
    lowered = query.lower()
    platform = next(
        (
            item
            for item in ("Windows", "macOS", "Linux", "iOS", "Android")
            if item.lower() in lowered
        ),
        None,
    )
    device_type = next(
        (
            item
            for item in ("laptop", "desktop", "phone", "tablet", "printer", "monitor")
            if item in lowered
        ),
        None,
    )
    application = next(
        (
            item
            for item in (
                "GitHub",
                "Jira",
                "Outlook",
                "Teams",
                "Slack",
                "Zoom",
                "SharePoint",
            )
            if item.lower() in lowered
        ),
        None,
    )
    product = (
        "corporate VPN"
        if "corporate vpn" in lowered
        else ("VPN" if "vpn" in lowered else application)
    )
    match = _ERROR_CODE.search(query)
    return ITEntities(
        product=product,
        platform=platform,
        error_code=match.group(0) if match else None,
        device_type=device_type,
        application=application,
    )


class ITIntentClassifier:
    """Rules are always evaluated before the optional injected LLM adapter."""

    def __init__(self, llm_fallback: IntentLLMFallback | None = None) -> None:
        self._llm_fallback = llm_fallback

    def classify(self, query: str) -> ITIntentResult:
        normalized = " ".join(query.lower().split())
        entities = _extract_entities(query)
        for category, intent, patterns, confidence in _RULES:
            if any(pattern in normalized for pattern in patterns):
                return ITIntentResult(
                    intent=intent,
                    category=category,
                    confidence=confidence,
                    reason=f"Matched {category.value} support terminology.",
                    entities=entities,
                    classification_source="rule",
                )
        return ITIntentResult(
            intent="unknown",
            category=ITCategory.OTHER,
            confidence=0.20,
            reason="No deterministic IT support pattern matched.",
            entities=entities,
            classification_source="rule",
        )

    async def classify_async(self, query: str) -> ITIntentResult:
        result = self.classify(query)
        if result.confidence >= 0.60 or self._llm_fallback is None:
            return result
        fallback_result = await self._llm_fallback.classify(query, result)
        return fallback_result.model_copy(update={"classification_source": "llm"})


def classify_intent(query: str) -> ITIntentResult:
    """Convenience deterministic API; it never invokes an LLM."""
    return ITIntentClassifier().classify(query)
