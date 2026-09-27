"""Unit and integration tests for Phase 9: Production API Layer."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver

from mcp_rag_agent.agent.models import (
    AgentExecutionMetadata,
    AgentResponse,
    RetrievedChunkOutput,
)
from mcp_rag_agent.api import create_app
from mcp_rag_agent.api.services.chat_service import ChatService
from mcp_rag_agent.api.services.conversation_service import ConversationService
from mcp_rag_agent.core.config import Config
from mcp_rag_agent.guardrails.models import DecisionCategory


@pytest.fixture
def mock_runner():
    """Construct mock RAGAgentRunner returning realistic structured AgentResponse."""
    runner = MagicMock()
    runner.system_prompt = "You are a policy assistant."
    runner.checkpointer = MemorySaver()

    # Pre-populate runner state for test thread thread_history_1
    def _mock_aget_state(cfg):
        th_id = cfg.get("configurable", {}).get("thread_id", "")
        if th_id == "thread_history_1":
            mock_s = MagicMock()
            mock_s.values = {
                "messages": [
                    HumanMessage(content="What is the bereavement policy?"),
                    ToolMessage(
                        content="--- Document #1: HR Policy (ID: doc_hr, Chunk: c1) ---\nBereavement leave is 5 days.",
                        tool_call_id="call_1",
                    ),
                    AIMessage(
                        content="Employees are entitled to 5 consecutive days of bereavement leave."
                    ),
                ]
            }
            return mock_s
        mock_empty = MagicMock()
        mock_empty.values = {}
        return mock_empty

    runner.agent_graph = MagicMock()
    runner.agent_graph.aget_state = AsyncMock(side_effect=_mock_aget_state)

    metadata = AgentExecutionMetadata(
        request_id="req_test_123",
        thread_id="th_test_abc",
        user_id="user_test_99",
        model_name="gemini-2.5-flash",
        total_latency_ms=145.2,
        retrieval_latency_ms=35.0,
        model_latency_ms=110.2,
        citations=["HR Policy Handbook (Section 4.1)"],
        retrieved_document_ids=["doc_hr_handbook"],
    )

    runner.run = AsyncMock(
        return_value=AgentResponse(
            answer="Employees are entitled to 5 consecutive days of bereavement leave.",
            metadata=metadata,
            decision=DecisionCategory.SUPPORTED_BY_EVIDENCE,
            is_out_of_scope=False,
            messages=[],
        )
    )
    return runner


@pytest.fixture
def client(mock_runner):
    """TestClient fixture initialized with mock runner."""
    app = create_app(runner=mock_runner)
    with TestClient(app) as test_client:
        yield test_client


# ==============================================================================
# Health and Diagnostics Tests
# ==============================================================================


def test_health_endpoint(client):
    """Verify GET /api/v1/health liveness probe."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["app_name"] == "MCP RAG Agent"
    assert data["app_version"] == "0.1.0"

    # Verify middleware headers
    assert "X-Request-ID" in response.headers
    assert "X-Response-Time-Ms" in response.headers


def test_readiness_endpoint_connected(mock_runner):
    """Verify GET /api/v1/ready when database is connected and model configured."""
    with patch("mcp_rag_agent.api.routes.health.MongoClient") as mock_mongo:
        mock_instance = MagicMock()
        mock_instance.admin.command.return_value = {"ok": 1}
        mock_mongo.return_value = mock_instance

        custom_cfg = Config(
            db_url="mongodb://localhost:27017",
            db_name="test_db",
            model_api_key="valid_key",
        )
        app = create_app(cfg=custom_cfg, runner=mock_runner)
        with TestClient(app) as test_client:
            res = test_client.get("/api/v1/ready")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "ready"
            assert data["checks"]["database"] == "connected"
            assert data["checks"]["model"] == "configured"


def test_readiness_endpoint_disconnected(mock_runner):
    """Verify GET /api/v1/ready returns 503 when database is unreachable."""
    custom_cfg = Config(
        db_url="",
        db_name="",
        model_api_key="",
        ff_session_memory=False,
    )
    app = create_app(cfg=custom_cfg, runner=mock_runner)
    with TestClient(app) as test_client:
        res = test_client.get("/api/v1/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"] == "disconnected"
        assert data["checks"]["model"] == "unconfigured"


# ==============================================================================
# Conversations Endpoints Tests
# ==============================================================================


def test_create_and_get_conversation(client):
    """Verify POST /api/v1/conversations and subsequent GET."""
    # 1. Create thread
    payload = {"user_id": "usr_alpha", "metadata": {"platform": "mobile"}}
    res_create = client.post("/api/v1/conversations", json=payload)
    assert res_create.status_code == 201

    created_data = res_create.json()
    assert "thread_id" in created_data
    assert created_data["thread_id"].startswith("thread_")
    assert created_data["user_id"] == "usr_alpha"
    assert created_data["status"] == "active"
    assert created_data["metadata"]["platform"] == "mobile"

    thread_id = created_data["thread_id"]

    # 2. Get history (empty initial state)
    res_hist = client.get(f"/api/v1/conversations/{thread_id}")
    assert res_hist.status_code == 200
    hist_data = res_hist.json()
    assert hist_data["thread_id"] == thread_id
    assert hist_data["messages"] == []
    assert hist_data["total_messages"] == 0


def test_get_conversation_history_with_turns(client):
    """Verify GET /api/v1/conversations/{thread_id} extracts clean dialogue, omitting ToolMessage (Zero-CoT)."""
    res = client.get("/api/v1/conversations/thread_history_1")
    assert res.status_code == 200

    data = res.json()
    assert data["thread_id"] == "thread_history_1"
    assert data["total_messages"] == 2
    messages = data["messages"]
    assert len(messages) == 2

    # Verify Turn 1 is user
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "What is the bereavement policy?"

    # Verify Turn 2 is assistant
    assert messages[1]["role"] == "assistant"
    assert "5 consecutive days" in messages[1]["content"]

    # Verify ToolMessage is completely absent (Zero-CoT)
    for m in messages:
        assert m["role"] != "tool"
        assert "--- Document" not in m["content"]


def test_delete_conversation(client):
    """Verify DELETE /api/v1/conversations/{thread_id} purges thread state."""
    # 1. Create thread
    res_create = client.post("/api/v1/conversations", json={})
    thread_id = res_create.json()["thread_id"]

    # 2. Delete thread
    res_delete = client.delete(f"/api/v1/conversations/{thread_id}")
    assert res_delete.status_code == 200
    del_data = res_delete.json()
    assert del_data["thread_id"] == thread_id
    assert del_data["deleted"] is True

    # 3. Verify subsequent GET returns 404
    res_after = client.get(f"/api/v1/conversations/{thread_id}")
    assert res_after.status_code == 404
    assert res_after.json()["error"] == "HTTP_ERROR"


def test_conversation_not_found(client):
    """Verify GET and DELETE on non-existent thread ID return 404."""
    res_get = client.get("/api/v1/conversations/non_existent_thread_999")
    assert res_get.status_code == 404
    assert "not found" in res_get.json()["message"].lower()

    res_del = client.delete("/api/v1/conversations/non_existent_thread_999")
    assert res_del.status_code == 404


# ==============================================================================
# Chat Endpoint Tests
# ==============================================================================


def test_chat_endpoint_success(client, mock_runner):
    """Verify POST /api/v1/chat returns structured Zero-CoT response."""
    payload = {
        "message": "What is the bereavement leave entitlement?",
        "thread_id": "th_test_abc",
        "user_id": "user_test_99",
    }
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 200

    data = response.json()
    # Check top-level contract
    assert "answer" in data
    assert "Employees are entitled to 5 consecutive days" in data["answer"]
    assert "citations" in data
    assert data["citations"] == ["HR Policy Handbook (Section 4.1)"]
    assert data["thread_id"] == "th_test_abc"
    assert data["request_id"] is not None

    # Check metadata contract
    meta = data["metadata"]
    assert meta["retrieval_latency_ms"] == 35.0
    assert meta["total_latency_ms"] == 145.2
    assert meta["model_name"] == "gemini-2.5-flash"
    assert meta["decision"] == "supported_by_evidence"

    # Verify Zero-CoT: no messages or internal chain of thought in response
    assert "messages" not in data
    assert "trace" not in data
    assert "violations" not in data

    # Verify mock was called with expected arguments
    mock_runner.run.assert_called_once()
    call_kwargs = mock_runner.run.call_args.kwargs
    assert call_kwargs["query"] == "What is the bereavement leave entitlement?"
    assert call_kwargs["thread_id"] == "th_test_abc"
    assert call_kwargs["user_id"] == "user_test_99"


def test_chat_custom_request_id_header(client):
    """Verify client-supplied X-Request-ID is honored across headers and response."""
    custom_req_id = "req_custom_trace_98765"
    payload = {"message": "Hello policy assistant!"}

    response = client.post(
        "/api/v1/chat",
        json=payload,
        headers={"X-Request-ID": custom_req_id},
    )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_req_id


def test_chat_validation_error_empty_message(client):
    """Verify POST /api/v1/chat returns 422 for empty or missing message."""
    # Empty string
    res_empty = client.post("/api/v1/chat", json={"message": ""})
    assert res_empty.status_code == 422
    data = res_empty.json()
    assert data["error"] == "VALIDATION_ERROR"
    assert "request_id" in data
    assert len(data["details"]) > 0

    # Missing message field
    res_missing = client.post("/api/v1/chat", json={"user_id": "u1"})
    assert res_missing.status_code == 422
    assert res_missing.json()["error"] == "VALIDATION_ERROR"


def test_chat_internal_error_handling(mock_runner):
    """Verify unhandled exceptions during agent execution return structured 500 error."""
    mock_runner.run = AsyncMock(side_effect=RuntimeError("Unexpected connection drop"))
    app = create_app(runner=mock_runner)

    with TestClient(app, raise_server_exceptions=False) as err_client:
        payload = {"message": "Test error handling"}
        response = err_client.post("/api/v1/chat", json=payload)
        assert response.status_code == 500

        data = response.json()
        assert data["error"] == "INTERNAL_SERVER_ERROR"
        assert "request_id" in data


# ==============================================================================
# OpenAPI and Root Info Tests
# ==============================================================================


def test_root_and_openapi_docs(client):
    """Verify root endpoint and OpenAPI schema documentation."""
    # Root endpoint
    res_root = client.get("/")
    assert res_root.status_code == 200
    root_data = res_root.json()
    assert root_data["name"] == "MCP RAG Agent API"
    assert root_data["docs"] == "/docs"
    assert root_data["ui"] == "/ui"

    # OpenAPI JSON schema
    res_docs = client.get("/openapi.json")
    assert res_docs.status_code == 200
    schema = res_docs.json()

    paths = schema["paths"]
    assert "/api/v1/chat" in paths
    assert "post" in paths["/api/v1/chat"]

    assert "/api/v1/conversations" in paths
    assert "get" in paths["/api/v1/conversations"]
    assert "post" in paths["/api/v1/conversations"]

    assert "/api/v1/conversations/{thread_id}" in paths
    assert "get" in paths["/api/v1/conversations/{thread_id}"]
    assert "delete" in paths["/api/v1/conversations/{thread_id}"]

    assert "/api/v1/health" in paths
    assert "get" in paths["/api/v1/health"]

    assert "/api/v1/ready" in paths
    assert "get" in paths["/api/v1/ready"]


# ==============================================================================
# Phase 10 UI and Rich Sources Tests
# ==============================================================================


def test_list_conversations_endpoint(client):
    """Verify GET /api/v1/conversations lists active threads with metadata."""
    # 1. Create a conversation via POST /api/v1/conversations
    create_res = client.post(
        "/api/v1/conversations",
        json={"user_id": "user_ui_test", "metadata": {"title": "HR Inquiries"}},
    )
    assert create_res.status_code == 201
    created_id = create_res.json()["thread_id"]

    # 2. Query GET /api/v1/conversations
    res = client.get("/api/v1/conversations")
    assert res.status_code == 200
    threads = res.json()
    assert isinstance(threads, list)
    thread_ids = [t["thread_id"] for t in threads]
    assert created_id in thread_ids
    t1 = next(t for t in threads if t["thread_id"] == created_id)
    assert t1["user_id"] == "user_ui_test"
    assert t1["metadata"]["title"] == "HR Inquiries"


def test_chat_endpoint_with_structured_sources(mock_runner):
    """Verify POST /api/v1/chat returns structured SourceDocument objects with provenance."""
    chunk = RetrievedChunkOutput(
        chunk_id="chunk_sec_99",
        document_id="doc_security_2026",
        document_name="IT Security Policy.pdf",
        content="All company laptops must use BitLocker disk encryption.",
        fusion_score=0.9234,
        rank=1,
        metadata={"section": "Encryption", "page": 4, "file_type": "pdf"},
    )
    metadata = AgentExecutionMetadata(
        request_id="req_sec_456",
        thread_id="th_sec_789",
        model_name="gemini-2.5-flash",
        total_latency_ms=180.5,
        retrieval_latency_ms=42.0,
        model_latency_ms=138.5,
        citations=["IT Security Policy.pdf"],
        retrieved_document_ids=["doc_security_2026"],
        retrieved_chunks=[chunk],
    )
    mock_runner.run = AsyncMock(
        return_value=AgentResponse(
            answer="Laptops must be encrypted using BitLocker.",
            metadata=metadata,
            decision=DecisionCategory.SUPPORTED_BY_EVIDENCE,
            is_out_of_scope=False,
            messages=[],
        )
    )
    app = create_app(runner=mock_runner)
    with TestClient(app) as test_client:
        res = test_client.post(
            "/api/v1/chat", json={"message": "What is the laptop encryption standard?"}
        )
        assert res.status_code == 200
        data = res.json()
        assert "sources" in data
        assert len(data["sources"]) == 1
        s = data["sources"][0]
        assert s["document_name"] == "IT Security Policy.pdf"
        assert s["chunk_id"] == "chunk_sec_99"
        assert s["document_id"] == "doc_security_2026"
        assert "BitLocker disk encryption" in s["content"]
        assert s["fusion_score"] == 0.9234
        assert s["rank"] == 1
        assert s["metadata"]["section"] == "Encryption"
        assert s["metadata"]["page"] == 4


def test_static_ui_serving(client):
    """Verify Phase 10 enterprise web UI assets are properly served under /ui."""
    # HTML root
    res_index = client.get("/ui/index.html")
    assert res_index.status_code == 200
    assert "text/html" in res_index.headers["content-type"]
    assert "Enterprise Knowledge Assistant" in res_index.text
    assert 'id="dialogueList"' in res_index.text
    assert 'id="sourceDrawer"' in res_index.text

    # CSS styles
    res_css = client.get("/ui/styles.css")
    assert res_css.status_code == 200
    assert "text/css" in res_css.headers["content-type"]
    assert "--font-heading" in res_css.text

    # JS application logic
    res_js = client.get("/ui/app.js")
    assert res_js.status_code == 200
    assert "javascript" in res_js.headers["content-type"]
    assert "sendChat" in res_js.text
    assert "parseMarkdown" in res_js.text
