"""Thread-safe and async-safe request context management using contextvars."""

import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Generator, Optional

# Context variable singletons
_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
_thread_id_ctx: ContextVar[str] = ContextVar("thread_id", default="")
_user_id_ctx: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
_current_tracer_ctx: ContextVar[Optional[Any]] = ContextVar(
    "current_tracer", default=None
)


def get_request_id() -> str:
    """Get the current request ID from context or empty string if unset."""
    return _request_id_ctx.get()


def get_thread_id() -> str:
    """Get the current thread ID from context or empty string if unset."""
    return _thread_id_ctx.get()


def get_user_id() -> Optional[str]:
    """Get the current user ID from context or None if unset."""
    return _user_id_ctx.get()


def get_current_tracer() -> Optional[Any]:
    """Get the active ObservabilityTracer from context or None."""
    return _current_tracer_ctx.get()


def get_correlation_ids() -> dict[str, Any]:
    """Return dictionary of current correlation identifiers."""
    return {
        "request_id": get_request_id(),
        "thread_id": get_thread_id(),
        "user_id": get_user_id(),
    }


@contextmanager
def set_request_context(
    request_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    user_id: Optional[str] = None,
    tracer: Optional[Any] = None,
) -> Generator[dict[str, Any], None, None]:
    """Context manager to establish request correlation IDs across async task boundaries.

    Args:
        request_id: Trace ID (generates UUID if None or empty).
        thread_id: Session ID (generates fallback if None or empty).
        user_id: Optional user identifier.
        tracer: Optional active ObservabilityTracer instance.

    Yields:
        Dictionary containing current correlation IDs.
    """
    req_id = request_id or str(uuid.uuid4())
    th_id = thread_id or f"th_{uuid.uuid4().hex[:8]}"

    token_req = _request_id_ctx.set(req_id)
    token_th = _thread_id_ctx.set(th_id)
    token_user = _user_id_ctx.set(user_id)
    token_tracer = _current_tracer_ctx.set(tracer)

    try:
        yield {
            "request_id": req_id,
            "thread_id": th_id,
            "user_id": user_id,
        }
    finally:
        _request_id_ctx.reset(token_req)
        _thread_id_ctx.reset(token_th)
        _user_id_ctx.reset(token_user)
        _current_tracer_ctx.reset(token_tracer)
