"""Unit tests for configuration validation and error handling."""

import os

import pytest

from mcp_rag_agent.core.config import Config, ConfigurationError


class TestConfigValidation:
    """Test suite for Config validation logic."""

    def test_import_without_credentials_does_not_raise_keyerror(self):
        """Verify Config can be instantiated without crashing on KeyError."""
        cfg = Config(db_url="", db_name="", model_api_key="")
        assert cfg.db_url == ""
        assert cfg.db_name == ""
        assert cfg.model_api_key == ""

    def test_default_embedding_dimension(self):
        """Verify default embedding dimension is 256."""
        cfg = Config()
        assert cfg.embedding_dimension == 256

    def test_validate_database_config_missing_url(self):
        """Verify validate_database_config raises ConfigurationError when db_url is missing."""
        cfg = Config(db_url="", db_name="test_db", model_api_key="sk-test")
        with pytest.raises(ConfigurationError, match="MONGODB_ATLAS_CLUSTER_URI"):
            cfg.validate_database_config()

    def test_validate_database_config_missing_db_name(self):
        """Verify validate_database_config raises ConfigurationError when db_name is missing."""
        cfg = Config(
            db_url="mongodb://localhost:27017", db_name="", model_api_key="sk-test"
        )
        with pytest.raises(ConfigurationError, match="MONGODB_ATLAS_DB_NAME"):
            cfg.validate_database_config()

    def test_validate_llm_config_missing_api_key(self):
        """Verify validate_llm_config raises ConfigurationError when model_api_key is missing."""
        cfg = Config(
            db_url="mongodb://localhost:27017", db_name="test_db", model_api_key=""
        )
        with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
            cfg.validate_llm_config()

    def test_validate_all_passes_when_configured(self):
        """Verify validate_all succeeds when all required fields are present."""
        cfg = Config(
            db_url="mongodb://localhost:27017",
            db_name="test_db",
            model_api_key="sk-test",
        )
        # Should not raise
        cfg.validate_all()

    def test_session_memory_config_defaults(self):
        """Verify session memory configuration defaults."""
        cfg = Config()
        assert cfg.ff_session_memory is True
        assert cfg.db_checkpoints_collection == "checkpoints"
        assert cfg.db_checkpoint_writes_collection == "checkpoint_writes"
        assert cfg.session_memory_ttl_seconds is None
