"""Unit tests for IT Support Intent Classifier (Phase 13-A).

Tests cover:
- Rule-based classification (Tier 1) for all major ITCategory buckets
- Priority inference from urgency keywords
- Error code extraction regex
- Affected service detection
- Keyword extraction and stopword filtering
- Empty/whitespace input handling
- Confidence score bounds
- Two-tier async classification with mocked LLM (Tier 2)
- LLM fallback: response parsing of CATEGORY/PRIORITY format
- LLM fallback: graceful handling of malformed LLM output
- LLM fallback: skipped when no LLM provided
- Backward-compatible with existing out-of-domain guardrail tests

All tests are offline — zero real network, database, or LLM calls.
LLM interactions use AsyncMock or simple async callable mocks.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_rag_agent.it_support.intent import (
    _build_llm_classification_prompt,
    _extract_error_codes,
    _extract_keywords,
    _match_category,
    _match_priority,
    _normalize_text,
    classify_issue,
    classify_issue_async,
)
from mcp_rag_agent.it_support.models import ITCategory, ITIssue, Priority


# ---------------------------------------------------------------------------
# Text Normalization Tests
# ---------------------------------------------------------------------------


class TestNormalizeText:
    def test_basic_lowercase(self):
        assert _normalize_text("VPN IS DOWN") == "vpn is down"

    def test_unicode_normalization(self):
        """NFKC normalization: composed forms converted to compatibility forms."""
        result = _normalize_text("Ré\u0301seau")  # 'é' + combining accent
        assert "r" in result

    def test_whitespace_collapse(self):
        result = _normalize_text("my   laptop   is   slow")
        assert "  " not in result
        assert result == "my laptop is slow"

    def test_empty_string(self):
        assert _normalize_text("") == ""


# ---------------------------------------------------------------------------
# Error Code Extraction Tests
# ---------------------------------------------------------------------------


class TestExtractErrorCodes:
    def test_windows_hex_code(self):
        codes = _extract_error_codes("Getting error 0xC0000005 on startup")
        assert "0xC0000005" in codes

    def test_http_error(self):
        codes = _extract_error_codes("SharePoint returns HTTP 403")
        assert any("403" in c for c in codes)

    def test_browser_error(self):
        codes = _extract_error_codes("Browser shows ERR_CONNECTION_REFUSED")
        assert "ERR_CONNECTION_REFUSED" in codes

    def test_multiple_codes(self):
        codes = _extract_error_codes(
            "I get 0xC0000005 and also Error Code 404 and ERR_NAME_NOT_RESOLVED"
        )
        assert len(codes) >= 2

    def test_no_error_codes(self):
        codes = _extract_error_codes("My printer is jammed")
        assert codes == []


# ---------------------------------------------------------------------------
# Keyword Extraction Tests
# ---------------------------------------------------------------------------


class TestExtractKeywords:
    def test_extracts_meaningful_words(self):
        kws = _extract_keywords("cannot connect to vpn from home office")
        assert "vpn" in kws or "connect" in kws

    def test_filters_short_tokens(self):
        """Tokens shorter than 3 chars should be filtered."""
        kws = _extract_keywords("my it laptop is on")
        # 'on', 'my' are too short or stopwords
        assert "on" not in kws
        assert "my" not in kws

    def test_deduplicated(self):
        kws = _extract_keywords("error error error")
        assert kws.count("error") <= 1

    def test_max_15_keywords(self):
        long_text = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike november oscar papa"
        kws = _extract_keywords(long_text)
        assert len(kws) <= 15


# ---------------------------------------------------------------------------
# Category Matching Tests (Tier 1)
# ---------------------------------------------------------------------------


class TestMatchCategory:
    """Rule-based category matching tests."""

    def test_security_incident(self):
        cat, conf = _match_category("serious security breach on our server")
        assert cat == ITCategory.SECURITY_INCIDENT
        assert conf > 0.7

    def test_password_reset(self):
        cat, _ = _match_category("forgot my password and need to reset it")
        assert cat == ITCategory.PASSWORD_RESET

    def test_account_lockout(self):
        cat, _ = _match_category("my account is locked out after failed attempts")
        assert cat == ITCategory.ACCOUNT_LOCKOUT

    def test_mfa(self):
        cat, _ = _match_category("i cannot set up my authenticator app for mfa")
        assert cat == ITCategory.MFA

    def test_vpn(self):
        cat, _ = _match_category("vpn connection keeps dropping when working remotely")
        assert cat == ITCategory.VPN

    def test_wifi(self):
        cat, _ = _match_category("wifi is not working in the meeting room")
        assert cat == ITCategory.WIFI

    def test_email(self):
        cat, _ = _match_category("outlook is not syncing and emails are bouncing")
        assert cat == ITCategory.EMAIL

    def test_network(self):
        cat, _ = _match_category("there is a network connectivity issue in building 3")
        assert cat == ITCategory.NETWORK

    def test_hardware_failure(self):
        cat, _ = _match_category("my laptop blue screen and won't start")
        assert cat == ITCategory.HARDWARE_FAILURE

    def test_peripheral(self):
        cat, _ = _match_category("my keyboard and external monitor are not detected")
        assert cat in (ITCategory.PERIPHERAL, ITCategory.HARDWARE_FAILURE)

    def test_printing(self):
        cat, _ = _match_category("i cannot print the document and there's a paper jam")
        assert cat == ITCategory.PRINTING

    def test_software_crash(self):
        cat, _ = _match_category("the application crash when i try to open it")
        assert cat == ITCategory.SOFTWARE_CRASH

    def test_installation(self):
        cat, _ = _match_category("i need to install software and update it")
        assert cat == ITCategory.INSTALLATION

    def test_license(self):
        cat, _ = _match_category("my software license expired and i need a new key")
        assert cat == ITCategory.LICENSE

    def test_access_request(self):
        cat, _ = _match_category("i need access to the new sharepoint site")
        assert cat in (ITCategory.ACCESS_REQUEST, ITCategory.PERMISSIONS)

    def test_permissions(self):
        cat, _ = _match_category("i keep getting access denied when opening the folder")
        assert cat == ITCategory.PERMISSIONS

    def test_video_conferencing(self):
        cat, _ = _match_category("my camera is not working in zoom meeting")
        assert cat == ITCategory.VIDEO_CONFERENCING

    def test_service_outage(self):
        cat, _ = _match_category("the system is completely down for our team")
        assert cat == ITCategory.SERVICE_OUTAGE

    def test_performance(self):
        cat, _ = _match_category("my laptop is running slow today")
        assert cat == ITCategory.PERFORMANCE

    def test_phishing(self):
        cat, _ = _match_category(
            "i received a suspicious email with a phishing link"
        )
        assert cat == ITCategory.PHISHING

    def test_malware(self):
        cat, _ = _match_category("my computer may be infected with malware")
        assert cat == ITCategory.MALWARE

    def test_onboarding(self):
        cat, _ = _match_category("we have a new hire starting monday and need setup")
        assert cat == ITCategory.ONBOARDING

    def test_unknown_returns_zero_confidence(self):
        cat, conf = _match_category("the sky is blue and birds fly high")
        assert cat == ITCategory.UNKNOWN
        assert conf == 0.0

    def test_multi_word_phrase_gives_higher_confidence(self):
        _, conf_single = _match_category("password")
        _, conf_multi = _match_category("reset password")
        assert conf_multi >= conf_single


# ---------------------------------------------------------------------------
# Priority Matching Tests
# ---------------------------------------------------------------------------


class TestMatchPriority:
    def test_critical_priority(self):
        p = _match_priority("this is an emergency security breach, system is down")
        assert p == Priority.CRITICAL

    def test_high_priority(self):
        p = _match_priority("account locked and cannot access anything")
        assert p == Priority.HIGH

    def test_low_priority(self):
        p = _match_priority("how do i change my desktop wallpaper no rush")
        assert p == Priority.LOW

    def test_medium_priority_default(self):
        p = _match_priority("my printer is not working")
        assert p == Priority.MEDIUM

    def test_urgent_keyword(self):
        p = _match_priority("urgent: vpn is down for the whole team")
        assert p == Priority.CRITICAL


# ---------------------------------------------------------------------------
# classify_issue() Integration Tests (Tier 1 end-to-end)
# ---------------------------------------------------------------------------


class TestClassifyIssue:
    def test_returns_it_issue_instance(self):
        result = classify_issue("VPN is not connecting")
        assert isinstance(result, ITIssue)

    def test_vpn_classification(self):
        result = classify_issue("I cannot connect to the VPN from home")
        assert result.category == ITCategory.VPN
        assert result.classification_method == "rule_based"
        assert result.intent_confidence > 0.0

    def test_security_incident_gets_critical_priority(self):
        result = classify_issue("We have a serious security breach — urgent!")
        assert result.category == ITCategory.SECURITY_INCIDENT
        assert result.priority == Priority.CRITICAL

    def test_password_reset_classified_correctly(self):
        result = classify_issue("I forgot my password and cannot log in")
        assert result.category == ITCategory.PASSWORD_RESET

    def test_outlook_email_classified(self):
        result = classify_issue("Outlook keeps crashing when I open emails")
        # Should match either EMAIL or SOFTWARE_CRASH (email takes precedence)
        assert result.category in (ITCategory.EMAIL, ITCategory.SOFTWARE_CRASH)

    def test_error_codes_extracted(self):
        result = classify_issue("Getting BSOD with error code 0xC0000005 on startup")
        assert len(result.error_codes) > 0

    def test_affected_service_outlook_detected(self):
        result = classify_issue("Outlook is not working properly")
        assert result.affected_service == "outlook"

    def test_keywords_extracted(self):
        result = classify_issue("My laptop screen is flickering and the battery drains fast")
        assert len(result.keywords) > 0

    def test_empty_description_returns_unknown(self):
        """Empty string returns UNKNOWN with minimal placeholder."""
        result = classify_issue("")
        assert result.category == ITCategory.UNKNOWN
        assert result.intent_confidence == 0.0
        # raw_description is set to ' ' (single space placeholder) to satisfy min_length
        assert result.raw_description.strip() == ""

    def test_whitespace_only_returns_unknown(self):
        result = classify_issue("   \t  \n  ")
        assert result.category == ITCategory.UNKNOWN

    def test_metadata_contains_text_stats(self):
        result = classify_issue("My mouse is not working")
        assert "text_length" in result.metadata
        assert "word_count" in result.metadata
        assert result.metadata["word_count"] == 5  # 'My mouse is not working'

    def test_confidence_within_bounds(self):
        for text in [
            "VPN error",
            "password reset required",
            "new hire onboarding setup",
            "system is down urgent",
            "something completely unrelated xyz 123",
        ]:
            result = classify_issue(text)
            assert 0.0 <= result.intent_confidence <= 1.0

    def test_unique_issue_ids(self):
        r1 = classify_issue("test issue one")
        r2 = classify_issue("test issue two")
        assert r1.issue_id != r2.issue_id

    def test_created_at_is_utc(self):
        from datetime import timezone as tz
        result = classify_issue("My laptop is slow")
        assert result.created_at.tzinfo == tz.utc


# ---------------------------------------------------------------------------
# classify_issue_async() Tests (Two-tier with mocked LLM)
# ---------------------------------------------------------------------------


class TestClassifyIssueAsync:
    """Tests for the two-tier async classification path."""

    @pytest.mark.asyncio
    async def test_skips_llm_when_confident(self):
        """When Tier 1 is confident, LLM should not be called."""
        mock_llm = AsyncMock()
        result = await classify_issue_async(
            "VPN is not connecting for our remote team", llm=mock_llm
        )
        # VPN is well-covered by Tier 1; LLM should not be invoked
        mock_llm.ainvoke.assert_not_called()
        assert result.category == ITCategory.VPN

    @pytest.mark.asyncio
    async def test_skips_llm_when_no_llm_provided(self):
        """When llm=None and Tier 1 returns UNKNOWN, Tier 2 is skipped gracefully."""
        result = await classify_issue_async(
            "something completely ambiguous with no it keywords xyz987", llm=None
        )
        # Should still return a valid ITIssue from Tier 1
        assert isinstance(result, ITIssue)
        assert result.category == ITCategory.UNKNOWN

    @pytest.mark.asyncio
    async def test_llm_fallback_called_for_unknown(self):
        """When Tier 1 returns UNKNOWN with low confidence, LLM is invoked."""
        mock_response = MagicMock()
        mock_response.content = "CATEGORY: printing\nPRIORITY: low"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        # Use text with zero IT keywords to guarantee UNKNOWN from Tier 1
        result = await classify_issue_async(
            "the fizzing quasar emits photonic blargle with no it context", llm=mock_llm
        )

        mock_llm.ainvoke.assert_called_once()
        assert result.category == ITCategory.PRINTING
        assert result.priority == Priority.LOW
        assert result.classification_method in ("llm", "hybrid")

    @pytest.mark.asyncio
    async def test_llm_fallback_handles_malformed_response(self):
        """When LLM returns garbage, Tier 1 result is returned as fallback."""
        mock_response = MagicMock()
        mock_response.content = "I don't know what this is"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        # Use text with zero IT keywords so Tier 2 is invoked
        result = await classify_issue_async(
            "the fizzing quasar emits photonic blargle with no it context", llm=mock_llm
        )
        # Should return gracefully with category from Tier 1 or LLM parse
        assert isinstance(result, ITIssue)
        assert 0.0 <= result.intent_confidence <= 1.0

    @pytest.mark.asyncio
    async def test_llm_exception_falls_back_to_tier1(self):
        """When LLM throws an exception, Tier 1 result is returned without crashing."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM API unavailable"))

        result = await classify_issue_async(
            "something with no clear category", llm=mock_llm
        )
        assert isinstance(result, ITIssue)
        # Should not raise; Tier 1 result returned


# ---------------------------------------------------------------------------
# LLM Prompt Builder Tests
# ---------------------------------------------------------------------------


class TestBuildLLMClassificationPrompt:
    def test_prompt_contains_description(self):
        desc = "I cannot access my email account"
        prompt = _build_llm_classification_prompt(desc)
        assert desc in prompt

    def test_prompt_contains_valid_categories(self):
        prompt = _build_llm_classification_prompt("test")
        assert "vpn" in prompt.lower()
        assert "hardware_failure" in prompt.lower()

    def test_prompt_contains_valid_priorities(self):
        prompt = _build_llm_classification_prompt("test")
        assert "critical" in prompt.lower()
        assert "medium" in prompt.lower()

    def test_prompt_format_structure(self):
        prompt = _build_llm_classification_prompt("my test issue")
        assert "CATEGORY:" in prompt
        assert "PRIORITY:" in prompt
