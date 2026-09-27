"""Integration tests for live MongoDB connectivity, document operations, and checkpoints."""

import os
import uuid

import pytest
from pymongo import MongoClient

from mcp_rag_agent.core.config import Config
from mcp_rag_agent.mongodb.client import MongoDBClient


def is_mongodb_available() -> bool:
    """Check whether a reachable MongoDB instance is configured."""
    uri = os.environ.get("MONGODB_ATLAS_CLUSTER_URI", "mongodb://localhost:27017")
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=1500)
        client.admin.command("ping")
        return True
    except Exception:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not is_mongodb_available(),
        reason="Live MongoDB instance is not reachable at MONGODB_ATLAS_CLUSTER_URI or localhost:27017",
    ),
]


class TestMongoDBLiveIntegration:
    """Live integration test suite for MongoDB operations."""

    @pytest.fixture
    def mongo_uri(self) -> str:
        return os.environ.get("MONGODB_ATLAS_CLUSTER_URI", "mongodb://localhost:27017")

    @pytest.fixture
    def test_db_name(self) -> str:
        return f"test_ci_{uuid.uuid4().hex[:8]}"

    def test_live_ping(self, mongo_uri: str):
        """Verify successful ping command to live MongoDB database."""
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
        res = client.admin.command("ping")
        assert res.get("ok") == 1.0

    def test_live_document_crud(self, mongo_uri: str, test_db_name: str):
        """Verify CRUD operations against a live database with cleanup."""
        client = MongoClient(mongo_uri)
        db = client[test_db_name]
        collection = db["test_integration_docs"]

        try:
            doc_id = str(uuid.uuid4())
            test_doc = {
                "_id": doc_id,
                "title": "CI Integration Test",
                "status": "active",
            }

            # Insert
            insert_result = collection.insert_one(test_doc)
            assert insert_result.inserted_id == doc_id

            # Read
            found = collection.find_one({"_id": doc_id})
            assert found is not None
            assert found["title"] == "CI Integration Test"

            # Update
            collection.update_one({"_id": doc_id}, {"$set": {"status": "verified"}})
            updated = collection.find_one({"_id": doc_id})
            assert updated["status"] == "verified"

            # Delete
            del_result = collection.delete_one({"_id": doc_id})
            assert del_result.deleted_count == 1
        finally:
            client.drop_database(test_db_name)

    def test_live_mongodb_client_wrapper(self, mongo_uri: str, test_db_name: str):
        """Verify MongoDBClient wrapper connects and queries properly."""
        client_wrapper = MongoDBClient(uri=mongo_uri, database_name=test_db_name)
        try:
            client_wrapper.connect()
            assert client_wrapper.get_collection("test_col") is not None
        finally:
            client_wrapper.disconnect()
            raw_client = MongoClient(mongo_uri)
            raw_client.drop_database(test_db_name)
