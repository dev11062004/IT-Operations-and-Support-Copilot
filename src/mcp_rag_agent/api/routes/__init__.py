"""API router aggregation for v1 endpoints."""

from fastapi import APIRouter

from mcp_rag_agent.api.routes.chat import router as chat_router
from mcp_rag_agent.api.routes.conversations import router as conversations_router
from mcp_rag_agent.api.routes.health import router as health_router
from mcp_rag_agent.api.routes.it_tickets import router as it_tickets_router

api_router = APIRouter(prefix="/api/v1")

# Register sub-routers
api_router.include_router(chat_router)
api_router.include_router(conversations_router)
api_router.include_router(health_router)
api_router.include_router(it_tickets_router)

__all__ = ["api_router"]
