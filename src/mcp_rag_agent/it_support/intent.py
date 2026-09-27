"""IT Support Intent Classifier.

Classifies user queries into structured ITIssue objects using a two-tier approach:

Tier 1 — Rule-Based Classification (fast, deterministic, zero LLM cost):
    Pattern-matching against keyword sets and regex signatures compiled from
    common IT support vocabularies (ITIL categories, ITSM keywords, error
    message patterns, service names). Suitable for 70-80% of routine requests.

Tier 2 — LLM-Assisted Classification (fallback for ambiguous queries):
    Invokes a lightweight classification prompt against the configured LLM
    when the rule-based tier returns ITCategory.UNKNOWN with low confidence.
    Not called in unit tests (mocked via dependency injection).

Public API:
    classify_issue(description: str) -> ITIssue
        Synchronous rule-based classification only.

    async classify_issue_async(description: str, llm=None) -> ITIssue
        Full two-tier classification with optional LLM fallback.
"""

import logging
import re
import unicodedata
from typing import Optional

from mcp_rag_agent.it_support.models import ITCategory, ITIssue, Priority

logger = logging.getLogger("ITIntentClassifier")

# ---------------------------------------------------------------------------
# Rule-Based Classification Tables
# ---------------------------------------------------------------------------

# Maps ITCategory → list of keyword/phrase sets (case-insensitive matching)
# Order matters: higher-specificity categories are listed first so the
# first-match-wins logic returns the most specific classification.
_CATEGORY_RULES: list[tuple[ITCategory, list[str]]] = [
    # --- Security (highest specificity — always check first) ---
    (
        ITCategory.SECURITY_INCIDENT,
        [
            "security incident",
            "data breach",
            "unauthorized access",
            "suspicious activity",
            "we have been hacked",
            "someone hacked",
            "ransomware attack",
            "data leak detected",
            "security alert triggered",
            "intrusion detected",
            "account compromised",
            "serious security breach",
            "serious security",
        ],
    ),
    (
        ITCategory.PHISHING,
        [
            "phishing",
            "suspicious email",
            "spam email",
            "fake email",
            "scam email",
            "malicious link",
            "clicked a link",
            "suspicious attachment",
        ],
    ),
    (
        ITCategory.MALWARE,
        [
            "malware",
            "virus",
            "ransomware",
            "trojan",
            "spyware",
            "adware",
            "infected",
            "antivirus",
            "malicious software",
        ],
    ),
    (
        ITCategory.PASSWORD_RESET,
        [
            "reset password",
            "forgot password",
            "forgot my password",
            "change password",
            "password expired",
            "cannot log in",
            "can't log in",
            "can't login",
            "cannot login",
            "password reset",
            "reset my password",
        ],
    ),
    (
        ITCategory.ACCOUNT_LOCKOUT,
        [
            "account locked",
            "locked out",
            "account lockout",
            "too many failed",
            "locked account",
            "account disabled",
        ],
    ),
    (
        ITCategory.MFA,
        [
            "mfa",
            "multi-factor",
            "multifactor",
            "two-factor",
            "2fa",
            "authenticator app",
            "verification code",
            "otp",
            "one-time password",
            "authenticator",
        ],
    ),
    # --- Network / Connectivity ---
    (
        ITCategory.VPN,
        [
            "vpn",
            "virtual private network",
            "vpn connection",
            "cannot connect to vpn",
            "vpn disconnecting",
            "vpn error",
            "remote access",
        ],
    ),
    (
        ITCategory.WIFI,
        [
            "wifi",
            "wi-fi",
            "wireless",
            "no internet",
            "internet not working",
            "cannot connect to wifi",
            "wifi dropping",
            "network connection",
        ],
    ),
    (
        ITCategory.EMAIL,
        [
            "email",
            "outlook",
            "mailbox",
            "email not working",
            "cannot send email",
            "email bouncing",
            "email delivery",
            "inbox full",
            "email client",
            "exchange",
        ],
    ),
    (
        ITCategory.NETWORK,
        [
            "network",
            "connectivity",
            "internet",
            "ethernet",
            "lan",
            "cannot access",
            "slow network",
            "network outage",
            "dns",
            "ip address",
        ],
    ),
    # --- Hardware ---
    (
        ITCategory.HARDWARE_FAILURE,
        [
            "hardware failure",
            "hard drive",
            "ssd",
            "ram",
            "memory error",
            "blue screen",
            "bsod",
            "kernel panic",
            "won't turn on",
            "won't start",
            "dead laptop",
            "screen broken",
            "cracked screen",
            "battery",
            "overheating",
            "fan noise",
            "hardware",
        ],
    ),
    (
        ITCategory.PERIPHERAL,
        [
            "keyboard",
            "mouse",
            "monitor",
            "display",
            "webcam",
            "headset",
            "usb",
            "dock",
            "docking station",
            "external",
            "peripheral",
            "second screen",
            "dual monitor",
        ],
    ),
    (
        ITCategory.PRINTING,
        [
            "print",
            "printer",
            "printing",
            "cannot print",
            "print queue",
            "paper jam",
            "scanner",
            "scanning",
        ],
    ),
    (
        ITCategory.MOBILE_DEVICE,
        [
            "mobile",
            "phone",
            "iphone",
            "android",
            "smartphone",
            "tablet",
            "ipad",
            "mobile device",
            "byod",
        ],
    ),
    # --- Collaboration (BEFORE software_crash to prevent false positives) ---
    (
        ITCategory.VIDEO_CONFERENCING,
        [
            "zoom meeting",
            "microsoft teams",
            "google meet",
            "webex",
            "video call",
            "conference call",
            "camera not working",
            "microphone not working",
            "audio issue in meeting",
            "video conferencing",
            "zoom call",
        ],
    ),
    (
        ITCategory.MESSAGING,
        [
            "slack",
            "instant message",
            "teams chat",
            "messaging platform",
        ],
    ),
    # --- HR / Lifecycle (BEFORE installation to avoid 'setup' conflict) ---
    (
        ITCategory.ONBOARDING,
        [
            "new employee",
            "new hire",
            "onboarding",
            "new starter",
            "new team member",
            "employee starting",
            "starting monday",
        ],
    ),
    (
        ITCategory.OFFBOARDING,
        [
            "offboarding",
            "employee leaving",
            "termination notice",
            "departing employee",
            "last day",
        ],
    ),
    # --- Service (BEFORE generic software_crash) ---
    (
        ITCategory.SERVICE_OUTAGE,
        [
            "service outage",
            "system outage",
            "service unavailable",
            "completely down",
            "portal down",
            "maintenance window",
            "service degraded",
        ],
    ),
    (
        ITCategory.PERFORMANCE,
        [
            "running slow",
            "high cpu",
            "high memory",
            "takes forever",
            "performance issue",
            "laggy performance",
            "high latency",
        ],
    ),
    # --- Software (generic terms, lower specificity) ---
    (
        ITCategory.SOFTWARE_CRASH,
        [
            "application crash",
            "keeps crashing",
            "not responding",
            "frozen screen",
            "app freezing",
            "stopped working",
            "error message",
            "application stopped",
            "software crashed",
        ],
    ),
    (
        ITCategory.ACCESS_REQUEST,
        [
            "access request",
            "need access",
            "grant access",
            "request access",
            "onboard",
            "new user",
            "provision",
            "provisioning",
        ],
    ),
    (
        ITCategory.PERMISSIONS,
        [
            "permission",
            "permissions",
            "access denied",
            "forbidden",
            "unauthorized",
            "no permission",
            "admin rights",
            "elevated access",
            "privilege",
            "role",
        ],
    ),
    (
        ITCategory.INSTALLATION,
        [
            "install software",
            "software installation",
            "uninstall application",
            "software update",
            "upgrade software",
            "deploy application",
            "configure software",
            "software setup",
        ],
    ),
    (
        ITCategory.LICENSE,
        [
            "license",
            "licence",
            "product key",
            "trial expired",
            "unlicensed product",
            "license expired",
        ],
    ),
    # --- Access & Identity ---
    # --- Policy ---
    (
        ITCategory.POLICY_QUESTION,
        [
            "policy",
            "it policy",
            "security policy",
            "password policy",
            "acceptable use",
            "byod policy",
            "bring your own device",
            "compliance",
            "gdpr",
            "data protection",
        ],
    ),
    (
        ITCategory.COMPLIANCE,
        [
            "compliance",
            "audit",
            "regulation",
            "regulatory",
            "sox",
            "iso 27001",
            "gdpr",
            "hipaa",
            "data protection",
        ],
    ),
]

# Priority inference rules: keyword → Priority
# Higher-urgency keywords are listed first; first match wins.
_PRIORITY_RULES: list[tuple[Priority, list[str]]] = [
    (
        Priority.CRITICAL,
        [
            "security breach",
            "data breach",
            "ransomware",
            "system down",
            "production down",
            "entire team",
            "all users",
            "cannot work",
            "business critical",
            "emergency",
            "urgent",
            "critical",
            "hacked",
        ],
    ),
    (
        Priority.HIGH,
        [
            "cannot access",
            "completely broken",
            "not working at all",
            "major",
            "significant",
            "affecting multiple",
            "team cannot",
            "password locked",
            "account locked",
        ],
    ),
    (
        Priority.LOW,
        [
            "minor",
            "cosmetic",
            "not urgent",
            "when you get a chance",
            "eventually",
            "no rush",
            "nice to have",
            "low priority",
            "information",
            "question",
            "how do i",
            "how to",
            "wondering",
            "can you tell me",
        ],
    ),
]

# Error code extraction pattern
_ERROR_CODE_RE = re.compile(
    r"(?:"
    r"0x[0-9A-Fa-f]{4,8}"  # Windows hex error codes (e.g. 0xC000005)
    r"|error\s+(?:code\s+)?[0-9]{3,6}"  # Error 404, Error Code 500
    r"|[A-Z]{2,8}[-_][0-9]{3,6}"  # BSOD codes like CRITICAL_PROCESS_DIED
    r"|ERR_[A-Z_]+"  # Browser errors like ERR_CONNECTION_REFUSED
    r"|E[0-9]{3,4}"  # Short error codes like E1001
    r"|[Hh]ttp\s*[45][0-9]{2}"  # HTTP 4xx/5xx errors
    r")",
    re.IGNORECASE,
)

# Service name extraction
_KNOWN_SERVICES = [
    "outlook",
    "teams",
    "zoom",
    "slack",
    "sharepoint",
    "onedrive",
    "office 365",
    "microsoft 365",
    "azure",
    "aws",
    "google workspace",
    "jira",
    "confluence",
    "salesforce",
    "sap",
    "workday",
    "servicenow",
    "vpn",
    "active directory",
    "okta",
    "duo",
    "crowdstrike",
    "defender",
]


def _normalize_text(text: str) -> str:
    """Unicode NFKC normalization + lowercase + whitespace collapse."""
    normalized = unicodedata.normalize("NFKC", text)
    collapsed = " ".join(normalized.split())
    return collapsed.lower()


def _match_category(text_lower: str) -> tuple[ITCategory, float]:
    """Run keyword-matching against _CATEGORY_RULES.

    Returns:
        (best_category, confidence) where confidence is based on match
        specificity (multi-word phrases score higher than single keywords).
    """
    for category, keywords in _CATEGORY_RULES:
        for kw in keywords:
            if kw in text_lower:
                # Multi-word phrases (>= 2 words) score higher confidence
                word_count = len(kw.split())
                confidence = 0.75 + min(word_count * 0.05, 0.20)
                return category, round(confidence, 2)

    return ITCategory.UNKNOWN, 0.0


def _match_priority(text_lower: str) -> Priority:
    """Infer priority from keyword signals."""
    for priority, keywords in _PRIORITY_RULES:
        for kw in keywords:
            if kw in text_lower:
                return priority
    return Priority.MEDIUM  # default


def _extract_error_codes(text: str) -> list[str]:
    """Extract all error codes from the description."""
    return list(set(_ERROR_CODE_RE.findall(text)))


def _extract_affected_service(text_lower: str) -> Optional[str]:
    """Identify the first known enterprise service mentioned."""
    for svc in _KNOWN_SERVICES:
        if svc in text_lower:
            return svc
    return None


def _extract_keywords(text_lower: str) -> list[str]:
    """Extract meaningful diagnostic keywords (3+ char alpha tokens)."""
    tokens = re.findall(r"\b[a-z][a-z0-9\-]{2,}\b", text_lower)
    # Filter stopwords
    stopwords = {
        "the",
        "and",
        "for",
        "that",
        "this",
        "with",
        "have",
        "from",
        "not",
        "can",
        "are",
        "was",
        "but",
        "its",
        "all",
        "any",
        "has",
        "had",
        "get",
        "got",
        "let",
        "try",
        "use",
        "our",
        "out",
        "my",
        "me",
        "it",
        "be",
        "is",
        "in",
        "of",
        "to",
        "do",
        "so",
        "if",
        "we",
        "by",
        "at",
        "on",
        "or",
        "an",
        "a",
    }
    return sorted(set(t for t in tokens if t not in stopwords))[:15]


def classify_issue(description: str) -> ITIssue:
    """Synchronous rule-based IT issue classification.

    Performs Tier 1 classification using keyword matching and pattern
    extraction. No LLM calls are made. Suitable for unit tests and
    real-time classification of common IT requests.

    Args:
        description: Raw natural language description of the IT issue.

    Returns:
        ITIssue with populated category, priority, keywords, and metadata.
        classification_method will be 'rule_based'.
    """
    stripped = description.strip() if description else ""
    if not stripped:
        # Return a minimal placeholder that satisfies Pydantic min_length=1
        return ITIssue(
            raw_description=stripped or " ",
            normalized_description="",
            category=ITCategory.UNKNOWN,
            priority=Priority.MEDIUM,
            intent_confidence=0.0,
            classification_method="rule_based",
        )

    normalized = _normalize_text(stripped)
    category, confidence = _match_category(normalized)
    priority = _match_priority(normalized)
    error_codes = _extract_error_codes(stripped)
    affected_service = _extract_affected_service(normalized)
    keywords = _extract_keywords(normalized)

    logger.debug(
        f"[ITIntentClassifier] category={category.value} confidence={confidence:.2f} "
        f"priority={priority.value} service={affected_service}"
    )

    words = stripped.split()
    return ITIssue(
        raw_description=stripped,
        normalized_description=normalized,
        category=category,
        priority=priority,
        affected_service=affected_service,
        error_codes=error_codes,
        keywords=keywords,
        intent_confidence=confidence,
        classification_method="rule_based",
        metadata={
            "text_length": len(stripped),
            "word_count": len(words),
        },
    )


async def classify_issue_async(
    description: str,
    llm: Optional[object] = None,
) -> ITIssue:
    """Two-tier async IT issue classification with optional LLM fallback.

    Tier 1: Rule-based classification (always executed first).
    Tier 2: LLM-assisted classification (only when Tier 1 returns UNKNOWN
            with confidence < 0.3 AND an LLM instance is provided).

    Args:
        description: Raw natural language description of the IT issue.
        llm: Optional LangChain BaseChatModel for fallback classification.
             When None, only Tier 1 rule-based classification is performed.

    Returns:
        ITIssue with populated fields. classification_method will be
        'rule_based', 'llm', or 'hybrid' depending on the path taken.
    """
    # Always run Tier 1 first
    issue = classify_issue(description)

    # Short-circuit if Tier 1 produced a confident result
    if issue.category != ITCategory.UNKNOWN and issue.intent_confidence >= 0.3:
        return issue

    # Tier 2: LLM fallback
    if llm is None:
        logger.debug(
            "[ITIntentClassifier] Tier 2 skipped — no LLM provided. "
            "Returning Tier 1 result."
        )
        return issue

    try:
        prompt = _build_llm_classification_prompt(description)
        response = await llm.ainvoke(prompt)
        content = str(getattr(response, "content", "")).strip()
        llm_issue = _parse_llm_classification_response(content, issue)
        llm_issue.classification_method = (
            "hybrid" if issue.category != ITCategory.UNKNOWN else "llm"
        )
        logger.debug(
            f"[ITIntentClassifier] Tier 2 LLM result: category={llm_issue.category.value} "
            f"confidence={llm_issue.intent_confidence:.2f}"
        )
        return llm_issue
    except Exception as e:
        logger.warning(
            f"[ITIntentClassifier] Tier 2 LLM classification failed: {e}. "
            "Returning Tier 1 result."
        )
        return issue


def _build_llm_classification_prompt(description: str) -> str:
    """Build a structured LLM classification prompt.

    Uses a few-shot constrained classification format to minimize token usage
    and maximize determinism. The LLM is only asked for a single category
    code and priority, not a free-form explanation.
    """
    valid_categories = ", ".join(
        [
            c.value
            for c in ITCategory
            if c not in (ITCategory.UNKNOWN, ITCategory.OTHER)
        ]
    )
    valid_priorities = ", ".join([p.value for p in Priority])

    return f"""You are an IT support ticket classification engine.

Classify the following IT support request into exactly one category and one priority.
Respond in this exact format (no explanation, no markdown):
CATEGORY: <category_value>
PRIORITY: <priority_value>

Valid categories: {valid_categories}
Valid priorities: {valid_priorities}

IT Support Request:
{description}

Classification:"""


def _parse_llm_classification_response(content: str, base_issue: ITIssue) -> ITIssue:
    """Parse structured LLM classification response into updated ITIssue.

    Falls back to the base_issue values if parsing fails.
    """
    category = base_issue.category
    priority = base_issue.priority
    confidence = 0.65  # LLM-assigned baseline confidence

    cat_match = re.search(r"CATEGORY:\s*([a-z_]+)", content, re.IGNORECASE)
    pri_match = re.search(r"PRIORITY:\s*([a-z]+)", content, re.IGNORECASE)

    if cat_match:
        try:
            category = ITCategory(cat_match.group(1).lower())
            confidence = 0.70
        except ValueError:
            logger.warning(
                f"[ITIntentClassifier] LLM returned unknown category: {cat_match.group(1)}"
            )

    if pri_match:
        try:
            priority = Priority(pri_match.group(1).lower())
        except ValueError:
            logger.warning(
                f"[ITIntentClassifier] LLM returned unknown priority: {pri_match.group(1)}"
            )

    # Return a new ITIssue with LLM-updated fields, preserving Tier 1 extractions
    return ITIssue(
        issue_id=base_issue.issue_id,
        raw_description=base_issue.raw_description,
        normalized_description=base_issue.normalized_description,
        category=category,
        priority=priority,
        affected_service=base_issue.affected_service,
        error_codes=base_issue.error_codes,
        keywords=base_issue.keywords,
        intent_confidence=confidence,
        created_at=base_issue.created_at,
        metadata=base_issue.metadata,
    )
