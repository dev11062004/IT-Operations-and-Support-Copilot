"""FastAPI dependencies for injecting configuration and application services."""

from typing import Optional

from fastapi import Request

from mcp_rag_agent.api.services.chat_service import ChatService
from mcp_rag_agent.api.services.conversation_service import ConversationService
from mcp_rag_agent.core.config import Config, config
from mcp_rag_agent.api.services.it_ticket_service import ITTicketAPIService
from mcp_rag_agent.it_support.tickets.service import TicketService
from mcp_rag_agent.it_support.tickets.store import TicketStore
from mcp_rag_agent.mongodb import MongoDBClient

# Global singleton fallbacks for testing or standalone execution
_default_chat_service: Optional[ChatService] = None
_default_conversation_service: Optional[ConversationService] = None
_default_it_ticket_service: Optional[ITTicketAPIService] = None


def get_config(request: Request) -> Config:
    """Dependency provider for application configuration."""
    if hasattr(request.app.state, "config") and request.app.state.config is not None:
        return request.app.state.config
    return config


def get_chat_service(request: Request) -> ChatService:
    """Dependency provider for ChatService, retrieving from app.state."""
    if (
        hasattr(request.app.state, "chat_service")
        and request.app.state.chat_service is not None
    ):
        return request.app.state.chat_service

    global _default_chat_service
    if _default_chat_service is None:
        _default_chat_service = ChatService()
    return _default_chat_service


def get_conversation_service(request: Request) -> ConversationService:
    """Dependency provider for ConversationService, retrieving from app.state."""
    if (
        hasattr(request.app.state, "conversation_service")
        and request.app.state.conversation_service is not None
    ):
        return request.app.state.conversation_service

    global _default_conversation_service
    if _default_conversation_service is None:
        _default_conversation_service = ConversationService()
    return _default_conversation_service


def get_it_ticket_service(request: Request) -> ITTicketAPIService:
    """Build the IT ticket dependency with the shared MongoDB client abstraction."""
    if hasattr(request.app.state, "it_ticket_service") and request.app.state.it_ticket_service is not None:
        return request.app.state.it_ticket_service
    global _default_it_ticket_service
    if _default_it_ticket_service is None:
        cfg = get_config(request)
        store = TicketStore(MongoDBClient(cfg.db_url, cfg.db_name), cfg.db_tickets_collection)
        _default_it_ticket_service = ITTicketAPIService(TicketService(store))
    return _default_it_ticket_service
