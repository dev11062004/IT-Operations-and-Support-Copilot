"""MCP server tools for RAG agent with strong typed schemas and privacy-safe logging."""

import logging
import re
import time
from typing import Any, Optional

from mcp_rag_agent.agent.models import (
    CheckServiceStatusInput,
    CheckServiceStatusOutput,
    CreateTicketToolInput,
    CreateTicketToolOutput,
    GetDeviceInfoInput,
    GetDeviceInfoOutput,
    GetUserContextInput,
    GetUserContextOutput,
    RetrievedChunkOutput,
    SearchDocumentsInput,
    SearchDocumentsOutput,
    UpdateTicketToolInput,
    UpdateTicketToolOutput,
)
from mcp_rag_agent.core.config import Config, config
from mcp_rag_agent.core.log_setup import setup_logging
from mcp_rag_agent.embeddings.embedding_generator import EmbeddingGenerator
from mcp_rag_agent.embeddings.hybrid_search import HybridSearch
from mcp_rag_agent.guardrails.context_guardrails import sanitize_document_text
from mcp_rag_agent.mongodb.client import MongoDBClient
from mcp_rag_agent.retrieval.pipeline import AdvancedRetriever

setup_logging()
logger = logging.getLogger("Retriever")

_hybrid_search: Optional[HybridSearch] = None
_advanced_retriever: Optional[AdvancedRetriever] = None
_mongo_client: Optional[MongoDBClient] = None
_user_service: Optional[Any] = None
_device_service: Optional[Any] = None
_service_status_checker: Optional[Any] = None
_ticket_service: Optional[Any] = None
_incident_service: Optional[Any] = None

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


def mask_sensitive(text: str) -> str:
    """Mask credentials, API keys, passwords, bearer tokens, and connection strings from logs."""
    if not isinstance(text, str):
        return str(text)
    masked = text
    for pattern, replacement in _SECRET_PATTERNS:
        masked = pattern.sub(replacement, masked)
    return masked


def get_mongo_client(cfg: Optional[Config] = None) -> MongoDBClient:
    """Get or lazily initialize the shared MongoDB client."""
    global _mongo_client
    active_config = cfg or config
    if _mongo_client is None:
        active_config.validate_database_config()
        logger.info(
            f"Initializing MongoDB client for database: {active_config.db_name}..."
        )
        _mongo_client = MongoDBClient(
            uri=active_config.db_url, database_name=active_config.db_name
        )
        _mongo_client.connect()
    return _mongo_client


def get_hybrid_search(cfg: Optional[Config] = None) -> HybridSearch:
    """Get or lazily initialize the shared HybridSearch engine (legacy compatibility)."""
    global _hybrid_search
    active_config = cfg or config
    if _hybrid_search is None:
        active_config.validate_all()
        client = get_mongo_client(active_config)
        logger.info("Initializing embedding generator for retriever...")
        embedder = EmbeddingGenerator(
            api_key=active_config.model_api_key,
            model=active_config.embedding_model,
            dimensions=active_config.embedding_dimension,
        )
        logger.info("Initializing hybrid search engine...")
        _hybrid_search = HybridSearch(
            mongo_client=client,
            embedding_generator=embedder,
            default_collection=active_config.db_vector_collection,
            default_vector_index=active_config.db_vector_index_name,
            default_text_index="text_index",
        )
    return _hybrid_search


def set_hybrid_search(hybrid_search: Optional[HybridSearch]) -> None:
    """Set or override the HybridSearch instance (for testing and dependency injection)."""
    global _hybrid_search
    _hybrid_search = hybrid_search


def get_advanced_retriever(cfg: Optional[Config] = None) -> AdvancedRetriever:
    """Get or lazily initialize the shared AdvancedRetriever engine."""
    global _advanced_retriever
    active_config = cfg or config
    if _advanced_retriever is None:
        active_config.validate_all()
        client = get_mongo_client(active_config)
        logger.info("Initializing embedding generator for advanced retriever...")
        embedder = EmbeddingGenerator(
            api_key=active_config.model_api_key,
            model=active_config.embedding_model,
            dimensions=active_config.embedding_dimension,
        )
        logger.info("Initializing advanced hybrid retriever pipeline...")
        _advanced_retriever = AdvancedRetriever(
            mongo_client=client,
            embedding_generator=embedder,
            default_collection=active_config.db_vector_collection,
            default_vector_index=active_config.db_vector_index_name,
            default_text_index="text_index",
            oversample_factor=active_config.retrieval_oversample_factor,
            rrf_k=active_config.retrieval_rrf_k,
        )
    return _advanced_retriever


def set_advanced_retriever(retriever: Optional[AdvancedRetriever]) -> None:
    """Set or override the AdvancedRetriever instance (for testing and dependency injection)."""
    global _advanced_retriever
    _advanced_retriever = retriever


def reset_it_services() -> None:
    """Reset cached IT domain service instances."""
    global _user_service, _device_service, _service_status_checker, _ticket_service, _incident_service
    _user_service = None
    _device_service = None
    _service_status_checker = None
    _ticket_service = None
    _incident_service = None


def reset_retriever() -> None:
    """Reset the cached retriever, IT services, and MongoDB client instances."""
    global _hybrid_search, _advanced_retriever, _mongo_client
    if _mongo_client:
        _mongo_client.disconnect()
    _mongo_client = None
    _hybrid_search = None
    _advanced_retriever = None
    reset_it_services()


def get_user_service(client: Optional[MongoDBClient] = None) -> Any:
    """Get or lazily initialize the shared UserService."""
    global _user_service
    if _user_service is None:
        from mcp_rag_agent.it_support.users.service import UserService
        from mcp_rag_agent.it_support.users.store import UserStore

        mongo = client or get_mongo_client()
        _user_service = UserService(UserStore(mongo))
    return _user_service


def set_user_service(service: Optional[Any]) -> None:
    """Set or override the UserService instance."""
    global _user_service
    _user_service = service


def get_device_service(client: Optional[MongoDBClient] = None) -> Any:
    """Get or lazily initialize the shared DeviceService."""
    global _device_service
    if _device_service is None:
        from mcp_rag_agent.it_support.devices.service import DeviceService
        from mcp_rag_agent.it_support.devices.store import DeviceStore

        mongo = client or get_mongo_client()
        _device_service = DeviceService(DeviceStore(mongo))
    return _device_service


def set_device_service(service: Optional[Any]) -> None:
    """Set or override the DeviceService instance."""
    global _device_service
    _device_service = service


def get_incident_service(client: Optional[MongoDBClient] = None) -> Any:
    """Get or lazily initialize the shared IncidentService."""
    global _incident_service
    if _incident_service is None:
        from mcp_rag_agent.it_support.incidents.service import IncidentService
        from mcp_rag_agent.it_support.incidents.store import IncidentStore

        mongo = client or get_mongo_client()
        _incident_service = IncidentService(IncidentStore(mongo))
    return _incident_service


def set_incident_service(service: Optional[Any]) -> None:
    """Set or override the IncidentService instance."""
    global _incident_service
    _incident_service = service


def get_service_status_checker(client: Optional[MongoDBClient] = None) -> Any:
    """Get or lazily initialize the shared ServiceStatusChecker."""
    global _service_status_checker
    if _service_status_checker is None:
        from mcp_rag_agent.it_support.services.service import ServiceStatusChecker
        from mcp_rag_agent.it_support.services.store import ServiceStatusStore

        mongo = client or get_mongo_client()
        store = ServiceStatusStore(mongo)
        incidents = get_incident_service(mongo)
        _service_status_checker = ServiceStatusChecker(store=store, incident_service=incidents)
    return _service_status_checker


def set_service_status_checker(checker: Optional[Any]) -> None:
    """Set or override the ServiceStatusChecker instance."""
    global _service_status_checker
    _service_status_checker = checker


def get_ticket_service(client: Optional[MongoDBClient] = None) -> Any:
    """Get or lazily initialize the shared TicketService."""
    global _ticket_service
    if _ticket_service is None:
        from mcp_rag_agent.it_support.tickets.service import TicketService
        from mcp_rag_agent.it_support.tickets.store import TicketStore

        mongo = client or get_mongo_client()
        _ticket_service = TicketService(TicketStore(mongo))
    return _ticket_service


def set_ticket_service(service: Optional[Any]) -> None:
    """Set or override the TicketService instance."""
    global _ticket_service
    _ticket_service = service


async def search_policy_documents_typed(
    input_data: SearchDocumentsInput,
) -> SearchDocumentsOutput:
    """Execute typed search_policy_documents tool with robust error handling and privacy-safe logging.

    Args:
        input_data: Validated SearchDocumentsInput containing query, top_k, and optional filter_query.

    Returns:
        SearchDocumentsOutput with status, chunks, latency, and document IDs.
    """
    from mcp_rag_agent.observability import (
        ErrorCategory,
        get_current_tracer,
        get_request_id,
    )

    req_id = get_request_id() or "-"
    tracer = get_current_tracer()

    safe_query = mask_sensitive(input_data.query)
    logger.info(
        f"[TOOL:search_policy_documents] [req:{req_id}] Executing query: '{safe_query}' (top_k={input_data.top_k})"
    )
    start_t = time.perf_counter()

    try:
        retriever = get_advanced_retriever()
        result = await retriever.retrieve(
            query=input_data.query,
            top_k=input_data.top_k,
            filter_query=input_data.filter_query,
            semantic_weight=config.semantic_weight,
        )

        chunks_out: list[RetrievedChunkOutput] = []
        doc_ids: set[str] = set()

        for c in result.chunks:
            chunk_content = c.content
            if config.ff_guardrails:
                chunk_content, injection_found = sanitize_document_text(c.content)
                if injection_found:
                    logger.warning(
                        f"[GUARDRAIL:RETRIEVAL] Neutralized indirect prompt injection in chunk '{c.chunk_id}' "
                        f"of document '{c.document_name}'"
                    )

            chunks_out.append(
                RetrievedChunkOutput(
                    chunk_id=c.chunk_id,
                    document_id=c.document_id,
                    document_name=c.document_name,
                    content=chunk_content,
                    fusion_score=c.fusion_score,
                    rank=c.rank,
                    metadata=c.metadata,
                )
            )
            if c.document_id:
                doc_ids.add(c.document_id)

        status = "success" if chunks_out else "empty"
        latency_ms = result.latency.total_latency_ms
        error_msg = None

        if config.ff_guardrails and chunks_out:
            top_score = chunks_out[0].fusion_score
            if top_score < config.guardrail_confidence_threshold:
                status = "low_confidence"
                error_msg = f"Top fusion score ({top_score:.4f}) is below confidence threshold ({config.guardrail_confidence_threshold:.4f})"
                logger.warning(f"[GUARDRAIL:RETRIEVAL] {error_msg}")

        logger.info(
            f"[TOOL:search_policy_documents] [req:{req_id}] Status: {status}, "
            f"Found: {len(chunks_out)} chunks, Latency: {latency_ms:.2f}ms"
        )

        if tracer:
            tracer.record_tool_call(
                tool_name="search_policy_documents",
                query=input_data.query,
                chunks_count=len(chunks_out),
                latency_ms=latency_ms,
                status=status,
            )

        return SearchDocumentsOutput(
            status=status,
            chunks=chunks_out,
            total_found=len(chunks_out),
            error_message=error_msg,
            retrieval_latency_ms=latency_ms,
            document_ids=sorted(list(doc_ids)),
        )

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        safe_err = mask_sensitive(str(e))
        logger.error(
            f"[TOOL:search_policy_documents] [req:{req_id}] Retrieval error: {safe_err}",
            exc_info=True,
        )
        if tracer:
            tracer.record_error(
                category=ErrorCategory.RETRIEVAL_ERROR,
                message=f"Retrieval tool error: {safe_err}",
                exc=e,
                recoverable=False,
            )
        return SearchDocumentsOutput(
            status="error",
            chunks=[],
            total_found=0,
            error_message=f"Retrieval system failure: {safe_err}",
            retrieval_latency_ms=round(elapsed_ms, 2),
            document_ids=[],
        )


async def search_documents(
    query: str,
    top_k: int = 3,
    filter_query: Optional[dict[str, Any]] = None,
    debug: bool = False,
) -> list[dict[str, Any]]:
    """Perform hybrid search on indexed documents using vector and text search.

    Maintains backward compatibility for direct callers returning raw dictionaries.

    Args:
        query (str): The search query text to find relevant documents.
        top_k (int, optional): The maximum number of results to return. Defaults to 3.
        filter_query (dict, optional): MongoDB metadata filter query.
        debug (bool, optional): Whether to capture internal debug trace.

    Returns:
        list[dict]: List of matching chunks with chunk_id, document_id, document_name,
                    content, vector_score, keyword_score, fusion_score, rank, and metadata.
    """
    safe_query = mask_sensitive(query)
    logger.info(f"Hybrid retrieval initiated: '{safe_query}' (top_k={top_k})")

    # If a legacy mock or instance was injected directly into _hybrid_search, delegate to it
    if _hybrid_search is not None and _advanced_retriever is None:
        results = await _hybrid_search.search(
            query=query,
            limit=top_k,
            semantic_weight=config.semantic_weight,
            filter_query=filter_query,
        )
        logger.info(
            f"Found {len(results)} relevant documents via hybrid search adapter"
        )
        return results

    typed_input = SearchDocumentsInput(
        query=query, top_k=top_k, filter_query=filter_query
    )
    typed_output = await search_policy_documents_typed(typed_input)

    # Return list of chunk dicts
    return [c.model_dump() for c in typed_output.chunks]


async def search_documents_with_debug(
    query: str,
    top_k: int = 3,
    filter_query: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Execute hybrid retrieval returning chunks, timing latency, and full debug trace."""
    retriever = get_advanced_retriever()
    result = await retriever.retrieve(
        query=query,
        top_k=top_k,
        semantic_weight=config.semantic_weight,
        filter_query=filter_query,
        debug=True,
    )
    return {
        "chunks": [chunk.to_dict() for chunk in result.chunks],
        "latency": result.latency.model_dump(),
        "debug": result.debug.model_dump() if result.debug else None,
    }


# -------------------------------------------------------------------
# Phase 13-D Typed IT Operations MCP Tool Handlers
# -------------------------------------------------------------------


async def get_user_context_typed(
    input_data: GetUserContextInput,
) -> GetUserContextOutput:
    """Execute typed get_user_context MCP tool with privacy masking and observability."""
    from mcp_rag_agent.it_support.users.store import UserNotFoundError
    from mcp_rag_agent.observability import (
        ErrorCategory,
        get_current_tracer,
        get_request_id,
    )

    req_id = get_request_id() or "-"
    tracer = get_current_tracer()
    safe_user_id = mask_sensitive(input_data.user_id)
    logger.info(f"[TOOL:get_user_context] [req:{req_id}] Looking up user: '{safe_user_id}'")

    start_t = time.perf_counter()
    try:
        service = get_user_service()
        user_record = service.get_user_context(input_data.user_id)
        latency_ms = (time.perf_counter() - start_t) * 1000.0

        user_data = user_record.model_dump(mode="json")
        # Remove any internal or private metadata keys before presenting to agent
        if "metadata" in user_data and isinstance(user_data["metadata"], dict):
            user_data["metadata"].pop("password_hash", None)
            user_data["metadata"].pop("api_keys", None)

        if tracer:
            tracer.record_tool_call(
                tool_name="get_user_context",
                query=safe_user_id,
                chunks_count=1,
                latency_ms=latency_ms,
                status="success",
            )

        logger.info(f"[TOOL:get_user_context] [req:{req_id}] User '{safe_user_id}' found ({latency_ms:.2f}ms)")
        return GetUserContextOutput(
            status="success",
            user=user_data,
        )

    except UserNotFoundError:
        latency_ms = (time.perf_counter() - start_t) * 1000.0
        logger.warning(f"[TOOL:get_user_context] [req:{req_id}] User '{safe_user_id}' not found")
        if tracer:
            tracer.record_tool_call(
                tool_name="get_user_context",
                query=safe_user_id,
                chunks_count=0,
                latency_ms=latency_ms,
                status="not_found",
            )
        return GetUserContextOutput(
            status="not_found",
            error_code="USER_NOT_FOUND",
            error_message=f"No user record found with ID '{safe_user_id}'.",
        )

    except ValueError as ve:
        logger.warning(f"[TOOL:get_user_context] [req:{req_id}] Invalid input: {ve}")
        return GetUserContextOutput(
            status="error",
            error_code="INVALID_ARGUMENT",
            error_message=str(ve),
        )

    except Exception as e:
        safe_err = mask_sensitive(str(e))
        logger.error(f"[TOOL:get_user_context] [req:{req_id}] Database error: {safe_err}", exc_info=True)
        if tracer:
            tracer.record_error(
                category=ErrorCategory.DATABASE_ERROR,
                message=f"User context lookup error: {safe_err}",
                exc=e,
                recoverable=False,
            )
        return GetUserContextOutput(
            status="error",
            error_code="DATABASE_ERROR",
            error_message="A database error occurred while looking up user context.",
        )


async def get_device_info_typed(
    input_data: GetDeviceInfoInput,
) -> GetDeviceInfoOutput:
    """Execute typed get_device_info MCP tool with privacy masking and observability."""
    from mcp_rag_agent.it_support.devices.store import DeviceNotFoundError
    from mcp_rag_agent.observability import (
        ErrorCategory,
        get_current_tracer,
        get_request_id,
    )

    req_id = get_request_id() or "-"
    tracer = get_current_tracer()
    start_t = time.perf_counter()

    if not input_data.device_id and not input_data.user_id:
        return GetDeviceInfoOutput(
            status="error",
            error_code="INVALID_ARGUMENT",
            error_message="Either device_id or user_id must be provided to query device info.",
        )

    try:
        service = get_device_service()
        devices: list[dict[str, Any]] = []

        if input_data.device_id:
            safe_dev = mask_sensitive(input_data.device_id)
            logger.info(f"[TOOL:get_device_info] [req:{req_id}] Looking up device_id: '{safe_dev}'")
            device_record = service.get_device_info(input_data.device_id)
            devices.append(device_record.model_dump(mode="json"))
        elif input_data.user_id:
            safe_user = mask_sensitive(input_data.user_id)
            logger.info(f"[TOOL:get_device_info] [req:{req_id}] Looking up devices for user_id: '{safe_user}'")
            device_records = service.get_user_devices(input_data.user_id)
            devices.extend([d.model_dump(mode="json") for d in device_records])

        latency_ms = (time.perf_counter() - start_t) * 1000.0

        if not devices:
            return GetDeviceInfoOutput(
                status="not_found",
                error_code="DEVICE_NOT_FOUND",
                error_message="No devices found matching the provided criteria.",
            )

        if tracer:
            tracer.record_tool_call(
                tool_name="get_device_info",
                query=input_data.device_id or input_data.user_id or "",
                chunks_count=len(devices),
                latency_ms=latency_ms,
                status="success",
            )

        return GetDeviceInfoOutput(
            status="success",
            devices=devices,
            total_found=len(devices),
        )

    except DeviceNotFoundError:
        latency_ms = (time.perf_counter() - start_t) * 1000.0
        return GetDeviceInfoOutput(
            status="not_found",
            error_code="DEVICE_NOT_FOUND",
            error_message=f"Device '{input_data.device_id}' was not found.",
        )

    except ValueError as ve:
        return GetDeviceInfoOutput(
            status="error",
            error_code="INVALID_ARGUMENT",
            error_message=str(ve),
        )

    except Exception as e:
        safe_err = mask_sensitive(str(e))
        logger.error(f"[TOOL:get_device_info] [req:{req_id}] Device lookup error: {safe_err}", exc_info=True)
        if tracer:
            tracer.record_error(
                category=ErrorCategory.DATABASE_ERROR,
                message=f"Device lookup error: {safe_err}",
                exc=e,
                recoverable=False,
            )
        return GetDeviceInfoOutput(
            status="error",
            error_code="DATABASE_ERROR",
            error_message="A database error occurred while looking up device information.",
        )


async def check_service_status_typed(
    input_data: CheckServiceStatusInput,
) -> CheckServiceStatusOutput:
    """Execute typed check_service_status MCP tool."""
    from mcp_rag_agent.observability import (
        ErrorCategory,
        get_current_tracer,
        get_request_id,
    )

    req_id = get_request_id() or "-"
    tracer = get_current_tracer()
    start_t = time.perf_counter()

    try:
        checker = get_service_status_checker()
        record = checker.check_service_status(input_data.service_name)
        latency_ms = (time.perf_counter() - start_t) * 1000.0

        if tracer:
            tracer.record_tool_call(
                tool_name="check_service_status",
                query=input_data.service_name,
                chunks_count=1,
                latency_ms=latency_ms,
                status="success",
            )

        return CheckServiceStatusOutput(
            status="success",
            service_name=record.service_name,
            service_status=record.status.value,
            last_updated=record.last_updated.isoformat(),
            known_incident_id=record.known_incident_id,
            message=record.message,
        )

    except ValueError as ve:
        return CheckServiceStatusOutput(
            status="error",
            service_name=input_data.service_name,
            service_status="UNKNOWN",
            error_code="INVALID_ARGUMENT",
            error_message=str(ve),
        )

    except Exception as e:
        safe_err = mask_sensitive(str(e))
        logger.error(f"[TOOL:check_service_status] [req:{req_id}] Error: {safe_err}", exc_info=True)
        if tracer:
            tracer.record_error(
                category=ErrorCategory.DATABASE_ERROR,
                message=f"Service status check error: {safe_err}",
                exc=e,
                recoverable=False,
            )
        return CheckServiceStatusOutput(
            status="error",
            service_name=input_data.service_name,
            service_status="UNKNOWN",
            error_code="DATABASE_ERROR",
            error_message="An error occurred while checking service operational status.",
        )


async def create_ticket_typed(
    input_data: CreateTicketToolInput,
) -> CreateTicketToolOutput:
    """Execute typed create_ticket MCP tool by delegating to Phase 13-B TicketService."""
    from mcp_rag_agent.it_support.models import ITCategory, Priority
    from mcp_rag_agent.it_support.tickets.models import TicketCreate
    from mcp_rag_agent.observability import (
        ErrorCategory,
        get_current_tracer,
        get_request_id,
    )

    req_id = get_request_id() or "-"
    tracer = get_current_tracer()
    start_t = time.perf_counter()

    try:
        # Category validation
        try:
            category_enum = ITCategory(input_data.category.lower().strip())
        except ValueError:
            category_enum = ITCategory.OTHER

        try:
            priority_enum = Priority(input_data.priority.lower().strip())
        except ValueError:
            priority_enum = Priority.MEDIUM

        ticket_create = TicketCreate(
            title=input_data.title,
            description=input_data.description,
            category=category_enum,
            priority=priority_enum,
            requester_id=input_data.requester_id,
            assigned_team=input_data.assigned_team,
            conversation_id=input_data.conversation_id,
            product=input_data.product,
            platform=input_data.platform,
            error_code=input_data.error_code,
        )

        service = get_ticket_service()
        op_result = service.create_ticket(ticket_create)
        latency_ms = (time.perf_counter() - start_t) * 1000.0

        if tracer:
            tracer.record_tool_call(
                tool_name="create_ticket",
                query=input_data.title,
                chunks_count=1,
                latency_ms=latency_ms,
                status="success" if op_result.created else "duplicate",
            )

        return CreateTicketToolOutput(
            status="success" if op_result.created else "duplicate",
            ticket_id=op_result.ticket.ticket_id,
            ticket=op_result.ticket.model_dump(mode="json"),
            created=op_result.created,
            duplicate=op_result.duplicate,
        )

    except ValueError as ve:
        return CreateTicketToolOutput(
            status="error",
            error_code="INVALID_ARGUMENT",
            error_message=str(ve),
        )

    except Exception as e:
        safe_err = mask_sensitive(str(e))
        logger.error(f"[TOOL:create_ticket] [req:{req_id}] Ticket creation error: {safe_err}", exc_info=True)
        if tracer:
            tracer.record_error(
                category=ErrorCategory.DATABASE_ERROR,
                message=f"Ticket creation error: {safe_err}",
                exc=e,
                recoverable=False,
            )
        return CreateTicketToolOutput(
            status="error",
            error_code="DATABASE_ERROR",
            error_message="A system error occurred while creating support ticket.",
        )


async def update_ticket_typed(
    input_data: UpdateTicketToolInput,
) -> UpdateTicketToolOutput:
    """Execute typed update_ticket MCP tool by delegating to Phase 13-B TicketService."""
    from mcp_rag_agent.it_support.tickets.models import (
        TicketComment,
        TicketLifecycleStatus,
    )
    from mcp_rag_agent.it_support.tickets.service import InvalidTicketTransitionError
    from mcp_rag_agent.it_support.tickets.store import TicketNotFoundError
    from mcp_rag_agent.observability import (
        ErrorCategory,
        get_current_tracer,
        get_request_id,
    )

    req_id = get_request_id() or "-"
    tracer = get_current_tracer()
    start_t = time.perf_counter()

    try:
        service = get_ticket_service()
        ticket_id = input_data.ticket_id.strip()
        ticket_record = service.get_ticket(ticket_id)

        # 1. Handle status transition if requested
        if input_data.status:
            try:
                target_status = TicketLifecycleStatus(input_data.status.lower().strip())
            except ValueError:
                return UpdateTicketToolOutput(
                    status="error",
                    ticket_id=ticket_id,
                    error_code="INVALID_ARGUMENT",
                    error_message=f"Invalid target status '{input_data.status}'.",
                )
            ticket_record = service.transition_status(ticket_id, target_status)

        # 2. Handle team assignment if requested
        if input_data.assigned_team is not None:
            ticket_record = service.assign_team(ticket_id, input_data.assigned_team)

        # 3. Handle comment addition if requested
        if input_data.comment:
            comment = TicketComment(
                author_id=input_data.author_id or "system",
                body=input_data.comment.strip(),
            )
            ticket_record = service.add_comment(ticket_id, comment)

        latency_ms = (time.perf_counter() - start_t) * 1000.0

        if tracer:
            tracer.record_tool_call(
                tool_name="update_ticket",
                query=ticket_id,
                chunks_count=1,
                latency_ms=latency_ms,
                status="success",
            )

        return UpdateTicketToolOutput(
            status="success",
            ticket_id=ticket_record.ticket_id,
            ticket=ticket_record.model_dump(mode="json"),
        )

    except TicketNotFoundError:
        return UpdateTicketToolOutput(
            status="error",
            ticket_id=input_data.ticket_id,
            error_code="TICKET_NOT_FOUND",
            error_message=f"Ticket '{input_data.ticket_id}' does not exist.",
        )

    except InvalidTicketTransitionError as te:
        return UpdateTicketToolOutput(
            status="error",
            ticket_id=input_data.ticket_id,
            error_code="INVALID_TRANSITION",
            error_message=str(te),
        )

    except ValueError as ve:
        return UpdateTicketToolOutput(
            status="error",
            ticket_id=input_data.ticket_id,
            error_code="INVALID_ARGUMENT",
            error_message=str(ve),
        )

    except Exception as e:
        safe_err = mask_sensitive(str(e))
        logger.error(f"[TOOL:update_ticket] [req:{req_id}] Error: {safe_err}", exc_info=True)
        if tracer:
            tracer.record_error(
                category=ErrorCategory.DATABASE_ERROR,
                message=f"Ticket update error: {safe_err}",
                exc=e,
                recoverable=False,
            )
        return UpdateTicketToolOutput(
            status="error",
            ticket_id=input_data.ticket_id,
            error_code="DATABASE_ERROR",
            error_message="A system error occurred while updating the ticket.",
        )
