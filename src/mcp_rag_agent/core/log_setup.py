"""Production structured logging system with correlation IDs and automated secret redaction."""

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Optional

from mcp_rag_agent.observability.context import get_request_id, get_thread_id

# Secret masking patterns
_SECRET_PATTERNS = [
    (re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE), "sk-***REDACTED***"),
    (
        re.compile(r"mongodb(?:\+srv)?:\/\/[^@\s]+@", re.IGNORECASE),
        "mongodb://***REDACTED***@",
    ),
    (
        re.compile(r"(?:bearer\s+)[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE),
        "Bearer ***REDACTED***",
    ),
    (
        re.compile(
            r"(?:password|passwd|pwd)\s*[:=]\s*['\"][^'\"]+['\"]", re.IGNORECASE
        ),
        "password='***REDACTED***'",
    ),
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"),
        "***@REDACTED.COM",
    ),
]


def mask_sensitive(text: Any) -> str:
    """Mask credentials, API keys, passwords, bearer tokens, and connection strings."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    masked = text
    for pattern, replacement in _SECRET_PATTERNS:
        masked = pattern.sub(replacement, masked)
    return masked


class CorrelationIdFilter(logging.Filter):
    """Logging filter that injects active request_id and thread_id from contextvars."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        record.thread_id = get_thread_id() or "-"
        return True


class MaskingFilter(logging.Filter):
    """Logging filter that ensures no secrets or credentials appear in log messages or args."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_sensitive(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: mask_sensitive(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    mask_sensitive(a) if isinstance(a, str) else a for a in record.args
                )
        return True


class JSONLogFormatter(logging.Formatter):
    """Structured JSON formatter for production log aggregators (ELK, CloudWatch, Datadog)."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "thread_id": getattr(record, "thread_id", "-"),
            "service": "mcp-rag-agent",
            "module": record.module,
            "lineno": record.lineno,
        }

        if hasattr(record, "error_category") and record.error_category:
            cat = record.error_category
            log_entry["error_category"] = (
                cat.value if hasattr(cat, "value") else str(cat)
            )

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class TextLogFormatter(logging.Formatter):
    """Human-readable console formatter with correlation ID tags."""

    def format(self, record: logging.LogRecord) -> str:
        req_id = getattr(record, "request_id", "-")
        th_id = getattr(record, "thread_id", "-")
        prefix = f"[req:{req_id} th:{th_id}]" if req_id != "-" or th_id != "-" else ""
        orig_format = self._style._fmt
        try:
            self._style._fmt = (
                f"%(asctime)s %(levelname)-8s {prefix} [%(name)s] %(message)s".strip()
            )
            return super().format(record)
        finally:
            self._style._fmt = orig_format


_is_logging_configured = False


def setup_logging(
    log_level: Optional[str] = None,
    log_format: Optional[str] = None,
    force_reconfigure: bool = False,
) -> None:
    """Configure centralized application logging with correlation IDs and secret redaction.

    Args:
        log_level: Desired log level (e.g. 'DEBUG', 'INFO', 'WARNING'). Default from LOG_LEVEL or INFO.
        log_format: 'text' or 'json'. Default from LOG_FORMAT or text.
        force_reconfigure: If True, reconfigures existing logging handlers.
    """
    global _is_logging_configured
    if _is_logging_configured and not force_reconfigure:
        return

    level_str = (log_level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    level = getattr(logging, level_str, logging.INFO)
    format_type = (log_format or os.environ.get("LOG_FORMAT", "text")).lower()

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers to prevent duplicate lines
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Attach filters
    correlation_filter = CorrelationIdFilter()
    masking_filter = MaskingFilter()
    handler.addFilter(correlation_filter)
    handler.addFilter(masking_filter)

    # Attach formatter
    if format_type == "json":
        formatter = JSONLogFormatter()
    else:
        formatter = TextLogFormatter(
            "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
        )
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _is_logging_configured = True


if __name__ == "__main__":
    setup_logging(log_format="json", force_reconfigure=True)
    logger = logging.getLogger("TestLogger")
    logger.info(
        "Structured JSON logging initialized with secret sk-1234567890abcdef1234567890"
    )
