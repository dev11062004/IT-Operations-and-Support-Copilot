"""Integration tests for FastAPI application layer."""

import pytest
from starlette.testclient import TestClient

from mcp_rag_agent.api.app import create_app
from mcp_rag_agent.core.config import Config

pytestmark = pytest.mark.integration


class TestAPIIntegration:
    """Integration test suite for FastAPI application endpoints."""

    @pytest.fixture
    def app_client(self):
        """Create test client with test configuration."""
        test_cfg = Config(
            db_url="mongodb://localhost:27017",
            db_name="test_ci_db",
            model_api_key="sk-test-ci-key",
            ff_session_memory=False,
        )
        app = create_app(cfg=test_cfg)
        with TestClient(app) as client:
            yield client

    def test_root_endpoint_metadata(self, app_client: TestClient):
        """Verify API root endpoint exposes expected navigation links."""
        res = app_client.get("/")
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "MCP RAG Agent API"
        assert data["health"] == "/api/v1/health"
        assert data["ready"] == "/api/v1/ready"

    def test_health_liveness_probe(self, app_client: TestClient):
        """Verify liveness probe returns healthy status."""
        res = app_client.get("/api/v1/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_correlation_id_header_injection(self, app_client: TestClient):
        """Verify X-Request-ID header is always injected and propagated."""
        custom_id = "test-custom-ci-trace-12345"
        res = app_client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
        assert res.status_code == 200
        assert res.headers.get("x-request-id") == custom_id
