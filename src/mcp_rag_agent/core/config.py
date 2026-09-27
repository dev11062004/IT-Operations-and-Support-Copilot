import os
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv(override=True)


class ConfigurationError(ValueError):
    """Raised when required configuration settings are missing or invalid."""

    pass


class Config(BaseSettings):
    """Configuration settings for the MCP RAG Agent."""

    # Application settings
    app_name: str = "MCP RAG Agent"
    app_version: str = "0.1.0"
    # API Server settings
    api_host: str = os.environ.get("API_HOST", "0.0.0.0")  # nosec B104
    api_port: int = int(os.environ.get("API_PORT", "8000"))
    cors_origins: list[str] = ["*"]
    # Logging settings
    log_level: str = os.environ.get("LOG_LEVEL", "INFO")
    log_format: str = os.environ.get("LOG_FORMAT", "text")  # "text" or "json"
    debug: bool = os.environ.get("DEBUG", "false").lower() == "true"
    # LangSmith Observability settings
    langsmith_tracing: bool = (
        os.environ.get("LANGSMITH_TRACING", "false").lower() == "true"
    )
    langsmith_endpoint: str = os.environ.get(
        "LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"
    )
    langsmith_api_key: str = os.environ.get("LANGSMITH_API_KEY", "")
    langsmith_project: str = os.environ.get("LANGSMITH_PROJECT", "mcp-rag-agent")
    langsmith_hide_inputs: bool = (
        os.environ.get("LANGSMITH_HIDE_INPUTS", "false").lower() == "true"
    )
    langsmith_hide_outputs: bool = (
        os.environ.get("LANGSMITH_HIDE_OUTPUTS", "false").lower() == "true"
    )
    # Database settings
    db_url: str = os.environ.get("MONGODB_ATLAS_CLUSTER_URI", "")
    db_name: str = os.environ.get("MONGODB_ATLAS_DB_NAME", "")
    db_users_collection: str = os.environ.get("MONGODB_USERS_COLLECTION", "users")
    db_conversations_collection: str = os.environ.get(
        "MONGODB_CONVERSATIONS_COLLECTION", "conversations"
    )
    db_checkpoints_collection: str = os.environ.get(
        "MONGODB_CHECKPOINTS_COLLECTION", "checkpoints"
    )
    db_checkpoint_writes_collection: str = os.environ.get(
        "MONGODB_CHECKPOINT_WRITES_COLLECTION", "checkpoint_writes"
    )
    db_messages_collection: str = os.environ.get(
        "MONGODB_MESSAGES_COLLECTION", "messages"
    )
    db_documents_collection: str = os.environ.get(
        "MONGODB_DOCUMENTS_COLLECTION", "documents"
    )
    db_vector_collection: str = os.environ.get("MONGODB_VECTOR_COLLECTION", "vectors")
    db_vector_index_name: str = os.environ.get(
        "MONGODB_VECTOR_INDEX_NAME", "vector_index"
    )
    db_tickets_collection: str = os.environ.get("MONGODB_TICKETS_COLLECTION", "it_tickets")
    db_incidents_collection: str = os.environ.get("MONGODB_INCIDENTS_COLLECTION", "it_incidents")
    session_memory_ttl_seconds: Optional[int] = (
        int(os.environ.get("SESSION_MEMORY_TTL_SECONDS"))
        if os.environ.get("SESSION_MEMORY_TTL_SECONDS")
        else None
    )
    # Model settings
    model_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    embedding_model: str = os.environ.get(
        "EMBEDDING_MODEL_NAME", "text-embedding-3-small"
    )
    embedding_dimension: int = int(os.environ.get("EMBEDDING_DIMENSION", "256"))
    text_model: str = os.environ.get("TEXT_MODEL_NAME", "gpt-4.1")
    text_generation_kwargs: dict = {
        "max_tokens": 2048,
        "temperature": 0,
        "top_p": 0.1,
    }
    evaluation_model: str = os.environ.get("EVALUATION_MODEL_NAME", "gpt-4o-mini")
    # MCP server settings
    mcp_name: str = os.environ.get("MCP_SERVER_NAME", "mongodb-semantic-search")
    mcp_host: str = os.environ.get("MCP_SERVER_HOST", "127.0.0.1")
    mcp_port: int = int(os.environ.get("MCP_SERVER_PORT", "8000"))
    mcp_transport: str = os.environ.get("MCP_TRANSPORT", "stdio")
    mcp_url: Optional[str] = os.environ.get("MCP_SERVER_URL", None)
    # Search settings
    semantic_weight: float = float(
        os.environ.get("SEMANTIC_WEIGHT", "0.7")
    )  # 0.7 = 70% semantic, 30% keyword
    # Feature flags
    ff_mcp_server: bool = (
        os.environ.get("FEATURE_FLAG_MCPSERVER_ENABLED", "false").lower() == "true"
    )
    ff_web_search: bool = (
        os.environ.get("FEATURE_FLAG_WEBSEARCH_ENABLED", "false").lower() == "true"
    )
    ff_session_memory: bool = (
        os.environ.get("FEATURE_FLAG_SESSION_MEMORY_ENABLED", "true").lower() == "true"
    )
    ff_guardrails: bool = (
        os.environ.get("FEATURE_FLAG_GUARDRAILS_ENABLED", "true").lower() == "true"
    )
    ff_it_support: bool = (
        os.environ.get("FEATURE_FLAG_IT_SUPPORT_ENABLED", "false").lower()
        == "true"
    )
    # Guardrail settings
    guardrail_confidence_threshold: float = float(
        os.environ.get("GUARDRAIL_CONFIDENCE_THRESHOLD", "0.015")
    )
    guardrail_min_vector_similarity: float = float(
        os.environ.get("GUARDRAIL_MIN_VECTOR_SIMILARITY", "0.50")
    )
    guardrail_max_context_chars: int = int(
        os.environ.get("GUARDRAIL_MAX_CONTEXT_CHARS", "4000")
    )
    guardrail_min_grounding_score: float = float(
        os.environ.get("GUARDRAIL_MIN_GROUNDING_SCORE", "0.20")
    )
    # Evaluation settings
    ingested_doc_dir: str = os.environ.get(
        "INGESTED_DOC_DIRECTORY", "./data/ingested_documents"
    )
    evaluation_doc_dir: str = os.environ.get(
        "EVALUATION_DOC_DIRECTORY", "./data/evaluation_documents"
    )
    # Ingestion & Chunking settings
    chunk_size: int = int(os.environ.get("CHUNK_SIZE", "500"))
    chunk_overlap: int = int(os.environ.get("CHUNK_OVERLAP", "50"))
    reindex: bool = os.environ.get("REINDEX", "false").lower() == "true"
    # Retrieval settings
    retrieval_oversample_factor: int = int(
        os.environ.get("RETRIEVAL_OVERSAMPLE_FACTOR", "3")
    )
    retrieval_rrf_k: int = int(os.environ.get("RETRIEVAL_RRF_K", "60"))
    retrieval_debug_mode: bool = (
        os.environ.get("RETRIEVAL_DEBUG_MODE", "false").lower() == "true"
    )
    retrieval_reranker_type: str = os.environ.get("RETRIEVAL_RERANKER_TYPE", "none")
    retrieval_top_k: int = int(os.environ.get("RETRIEVAL_TOP_K", "3"))

    def validate_database_config(self) -> None:
        """Validate database configuration settings. Raises ConfigurationError if invalid."""
        missing = []
        if not self.db_url:
            missing.append("MONGODB_ATLAS_CLUSTER_URI")
        if not self.db_name:
            missing.append("MONGODB_ATLAS_DB_NAME")
        if missing:
            raise ConfigurationError(
                f"Missing required MongoDB configuration: {', '.join(missing)}. "
                "Please configure them in your .env file or environment variables."
            )

    def validate_llm_config(self) -> None:
        """Validate LLM configuration settings. Raises ConfigurationError if invalid."""
        if not self.model_api_key:
            raise ConfigurationError(
                "Missing required OpenAI API configuration: OPENAI_API_KEY. "
                "Please configure it in your .env file or environment variables."
            )

    def validate_all(self) -> None:
        """Validate all required configurations."""
        self.validate_database_config()
        self.validate_llm_config()


config = Config()
