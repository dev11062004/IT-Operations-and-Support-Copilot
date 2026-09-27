"""Input guardrails: Prompt injection defense and out-of-domain detection for user queries."""

import re
from typing import Tuple

from mcp_rag_agent.guardrails.models import (
    DecisionCategory,
    GuardrailViolation,
    ViolationType,
)

# Common prompt injection, jailbreak, and system instruction override signatures
_INJECTION_PATTERNS = [
    re.compile(
        r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|prompts|rules|directions)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:disregard|forget)\s+(?:all\s+|prior\s+|previous\s+)?(?:instructions|rules|context|guidelines|prompts)",
        re.IGNORECASE,
    ),
    re.compile(
        r"you\s+are\s+now\s+(?:dan|developer\s+mode|jailbroken|unrestricted)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:bypass|override|disable)\s+(?:all\s+)?(?:safety|guardrails|policy|filters)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:print|output|display|show|reveal)\s+(?:the\s+)?(?:system\s+prompt|hidden\s+instructions|developer\s+prompt)",
        re.IGNORECASE,
    ),
    re.compile(r"<\s*system\s*>|\[\s*system\s*\]|```\s*system", re.IGNORECASE),
    re.compile(r"role\s*:\s*[\"']?system[\"']?", re.IGNORECASE),
]

# Explicit out-of-domain query indicators (non-policy, coding, math, medical, fiction)
_OUT_OF_DOMAIN_PATTERNS = [
    re.compile(
        r"(?:write|generate|give\s+me|create|can\s+you\s+write)\s+(?:a\s+)?(?:python|javascript|js|c\+\+|java|rust|html|sql|code|script|algorithm|regex|function)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:write|compose|generate)\s+(?:a\s+)?(?:poem|story|song|essay|joke|fantasy|novel)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:what\s+is\s+the\s+capital\s+of|who\s+won\s+(?:the\s+)?(?:fifa\s+)?world\s+cup|who\s+is\s+the\s+president\s+of)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:solve\s+(?:this\s+)?equation|calculate\s+(?:the\s+)?integral|derivative\s+of|2\s*\+\s*2)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:diagnose|symptoms\s+of\s+(?:cancer|diabetes|appendicitis|covid)|medical\s+treatment)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:quantum\s+physics|theory\s+of\s+relativity|speed\s+of\s+light|schrodinger)",
        re.IGNORECASE,
    ),
]

# Valid in-domain keywords (policy + IT support vocabulary)
# Extended in Phase 13-A to accept IT Operations & Support Copilot queries.
_POLICY_KEYWORDS = {
    # --- Existing policy keywords (Phase 1-12) ---
    "policy",
    "leave",
    "holiday",
    "vacation",
    "annual",
    "expense",
    "expenses",
    "remote",
    "working",
    "work",
    "password",
    "security",
    "laptop",
    "incident",
    "sustainability",
    "carbon",
    "travel",
    "mileage",
    "meal",
    "allowance",
    "approval",
    "manager",
    "carryover",
    "carry-over",
    "hours",
    "claim",
    "reimbursement",
    "equipment",
    "vpn",
    "confidential",
    "it",
    "hr",
    "company",
    # --- IT Support domain keywords (Phase 13-A) ---
    # Hardware
    "hardware",
    "computer",
    "monitor",
    "keyboard",
    "mouse",
    "printer",
    "scanner",
    "dock",
    "screen",
    "battery",
    "device",
    # Software & Applications
    "software",
    "application",
    "app",
    "crash",
    "install",
    "update",
    "upgrade",
    "license",
    "error",
    "bug",
    "broken",
    "frozen",
    # Network & Connectivity
    "network",
    "internet",
    "wifi",
    "ethernet",
    "connectivity",
    "dns",
    "firewall",
    "proxy",
    # Security & Identity
    "mfa",
    "authenticator",
    "lockout",
    "locked",
    "breach",
    "phishing",
    "virus",
    "malware",
    "ransomware",
    "hacked",
    "access",
    "permission",
    "login",
    "account",
    "reset",
    # Communication & Collaboration
    "email",
    "outlook",
    "teams",
    "zoom",
    "slack",
    "meeting",
    "calendar",
    "sharepoint",
    "onedrive",
    # Support Workflow
    "ticket",
    "issue",
    "support",
    "helpdesk",
    "troubleshoot",
    "escalate",
    "outage",
    "slow",
    "not working",
    "broken",
    "help",
    "fix",
}


def sanitize_query(query: str) -> str:
    """Normalize whitespace and strip unprintable control characters from user query."""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", query)
    return " ".join(cleaned.split())


def check_input_prompt_injection(query: str) -> Tuple[bool, list[GuardrailViolation]]:
    """Scan user query for prompt injection, jailbreak attempts, or system prompt exfiltration."""
    violations: list[GuardrailViolation] = []

    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(query)
        if match:
            matched_text = match.group(0)
            violations.append(
                GuardrailViolation(
                    violation_type=ViolationType.PROMPT_INJECTION_QUERY,
                    message=f"Prompt injection pattern detected: '{matched_text}'",
                    severity="critical",
                    details={
                        "matched_pattern": pattern.pattern,
                        "matched_text": matched_text,
                    },
                )
            )

    is_safe = len(violations) == 0
    return is_safe, violations


def check_out_of_domain(query: str) -> Tuple[bool, list[GuardrailViolation]]:
    """Check if query is outside the scope of organizational policy question-answering."""
    violations: list[GuardrailViolation] = []
    lowered = query.lower()

    # 1. Match explicit out-of-domain patterns
    for pattern in _OUT_OF_DOMAIN_PATTERNS:
        match = pattern.search(query)
        if match:
            violations.append(
                GuardrailViolation(
                    violation_type=ViolationType.OUT_OF_DOMAIN,
                    message="Query is outside knowledge scope (general coding, science, medical, or trivia).",
                    severity="warning",
                    details={"matched_pattern": pattern.pattern},
                )
            )
            return False, violations

    # 2. Check if query completely lacks any policy context and has no enterprise intent
    tokens = set(re.findall(r"\b[a-z]{3,}\b", lowered))
    if tokens and not (tokens & _POLICY_KEYWORDS):
        # Short non-policy inquiries (e.g. "What is quantum physics?")
        if len(tokens) <= 8 and any(
            k in lowered
            for k in ["quantum", "recipe", "weather", "horoscope", "crypto", "bitcoin"]
        ):
            violations.append(
                GuardrailViolation(
                    violation_type=ViolationType.OUT_OF_DOMAIN,
                    message="Query does not contain Company XYZ policy intent.",
                    severity="warning",
                    details={"tokens": sorted(list(tokens))},
                )
            )
            return False, violations

    return True, []
