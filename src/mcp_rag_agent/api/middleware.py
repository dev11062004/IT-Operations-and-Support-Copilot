"""HTTP middleware for correlation IDs, latency measurement, and request logging."""

import logging
import time
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from mcp_rag_agent.observability.context import set_request_context

logger = logging.getLogger("APIMiddleware")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Intercepts requests to extract or assign X-Request-ID and tracks response latency."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract existing X-Request-ID header or generate a new unique identifier
        incoming_req_id = request.headers.get("X-Request-ID")
        request_id = (
            incoming_req_id.strip()
            if incoming_req_id
            else f"req_{uuid.uuid4().hex[:16]}"
        )

        request.state.request_id = request_id
        start_time = time.perf_counter()

        with set_request_context(request_id=request_id):
            logger.info(
                f"[API:REQ] {request.method} {request.url.path} (request_id={request_id})"
            )
            try:
                response = await call_next(request)
            except Exception as exc:
                elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                logger.error(
                    f"[API:ERR] {request.method} {request.url.path} failed after {elapsed_ms}ms "
                    f"(request_id={request_id}): {exc}",
                    exc_info=True,
                )
                raise exc

            elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time-Ms"] = str(elapsed_ms)

            logger.info(
                f"[API:RES] {request.method} {request.url.path} {response.status_code} "
                f"took {elapsed_ms}ms (request_id={request_id})"
            )
            return response
