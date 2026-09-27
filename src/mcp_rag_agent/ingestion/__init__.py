"""Document Ingestion Subsystem for MCP RAG Agent.

Provides production-grade multi-format parsing, cleaning, structural chunking,
metadata enrichment, content-hash deduplication, and vector indexing.
"""

from mcp_rag_agent.ingestion.chunker import DocumentChunker
from mcp_rag_agent.ingestion.cleaner import DocumentCleaner
from mcp_rag_agent.ingestion.models import (
    DocumentChunk,
    DocumentSegment,
    IngestionResult,
    IngestionStatus,
    ParsedDocument,
    PipelineSummary,
)
from mcp_rag_agent.ingestion.parsers import (
    BaseDocumentParser,
    DocxParser,
    IngestionError,
    MarkdownParser,
    ParserRegistry,
    ParsingError,
    PDFParser,
    TextParser,
    UnsupportedFileTypeError,
    default_parser_registry,
    get_parser,
)
from mcp_rag_agent.ingestion.pipeline import DocumentIngestionPipeline

__all__ = [
    # Pipeline
    "DocumentIngestionPipeline",
    # Cleaning & Chunking
    "DocumentCleaner",
    "DocumentChunker",
    # Parsers
    "BaseDocumentParser",
    "TextParser",
    "MarkdownParser",
    "PDFParser",
    "DocxParser",
    "ParserRegistry",
    "default_parser_registry",
    "get_parser",
    # Models
    "DocumentChunk",
    "DocumentSegment",
    "ParsedDocument",
    "IngestionResult",
    "IngestionStatus",
    "PipelineSummary",
    # Exceptions
    "IngestionError",
    "UnsupportedFileTypeError",
    "ParsingError",
]
