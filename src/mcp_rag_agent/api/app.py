"""FastAPI application factory for MCP RAG Agent Production API Layer."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from mcp_rag_agent.agent.create_agent import create_rag_agent_instance
from mcp_rag_agent.agent.runner import RAGAgentRunner
from mcp_rag_agent.api.middleware import CorrelationIdMiddleware
from mcp_rag_agent.api.routes import api_router
from mcp_rag_agent.api.services.chat_service import ChatService
from mcp_rag_agent.api.services.conversation_service import ConversationService
from mcp_rag_agent.core.config import Config, config
from mcp_rag_agent.core.log_setup import setup_logging
from mcp_rag_agent.observability import configure_langsmith_environment

setup_logging()
logger = logging.getLogger("APIApp")


def create_app(
    cfg: Optional[Config] = None,
    runner: Optional[RAGAgentRunner] = None,
) -> FastAPI:
    """Factory function to build and configure the FastAPI application.

    Args:
        cfg: Optional application configuration override.
        runner: Optional pre-configured RAGAgentRunner instance (useful for testing).

    Returns:
        Configured FastAPI application instance.
    """
    active_cfg = cfg or config

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Manage startup and shutdown lifecycle tasks."""
        logger.info("[LIFESPAN] Starting up MCP RAG Agent API Layer...")
        configure_langsmith_environment(active_cfg)

        active_runner = runner
        if active_runner is None:
            try:
                logger.info("[LIFESPAN] Initializing RAG Agent Runner instance...")
                active_runner = await create_rag_agent_instance(cfg=active_cfg)
            except Exception as e:
                logger.warning(
                    f"[LIFESPAN] Deferred full agent startup due to initialization error: {e}. "
                    "Service will boot; chat endpoints may report degraded status if unconfigured."
                )

        # Wire services into app.state
        conv_service = ConversationService(
            runner=active_runner,
            checkpointer=active_runner.checkpointer if active_runner else None,
            cfg=active_cfg,
        )
        chat_service = ChatService(
            runner=active_runner,
            cfg=active_cfg,
            conversation_service=conv_service,
        )

        app.state.config = active_cfg
        app.state.runner = active_runner
        app.state.chat_service = chat_service
        app.state.conversation_service = conv_service

        logger.info("[LIFESPAN] MCP RAG Agent API successfully started.")
        yield
        logger.info("[LIFESPAN] Shutting down MCP RAG Agent API Layer...")

    app = FastAPI(
        title="MCP RAG Agent API",
        description=(
            "Production Conversational RAG API Layer with Multi-turn Persistence, "
            "Grounded Guardrails, and Distributed Observability."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # 1. CORS Middleware
    origins = active_cfg.cors_origins if hasattr(active_cfg, "cors_origins") else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Correlation ID & Latency Middleware
    app.add_middleware(CorrelationIdMiddleware)

    # 3. Standardized Exception Handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None)
        logger.warning(f"[API:VALIDATION_ERROR] (request_id={req_id}): {exc.errors()}")
        return JSONResponse(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            content={
                "error": "VALIDATION_ERROR",
                "message": "Invalid request parameters.",
                "details": exc.errors(),
                "request_id": req_id,
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTP_ERROR",
                "message": exc.detail,
                "status_code": exc.status_code,
                "request_id": req_id,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None)
        logger.error(
            f"[API:INTERNAL_ERROR] (request_id={req_id}): {exc}", exc_info=True
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred while processing the request.",
                "request_id": req_id,
            },
        )

    # 4. Root information endpoint
    @app.get("/", tags=["Root"], summary="API Root Information")
    async def root_info() -> dict[str, str]:
        return {
            "name": "MCP RAG Agent API",
            "version": "0.1.0",
            "docs": "/docs",
            "ui": "/ui",
            "health": "/api/v1/health",
            "ready": "/api/v1/ready",
        }

    # 5. Register Versioned Routes
    app.include_router(api_router)

    # 6. Mount Static UI Directory
    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/ui", StaticFiles(directory=str(static_dir), html=True), name="ui")

    return app
