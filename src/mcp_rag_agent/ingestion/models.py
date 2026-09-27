"""Data models for document ingestion and chunking."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class IngestionStatus(str, Enum):
    """Status outcomes for document ingestion."""

    INGESTED = "ingested"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    REINDEXED = "reindexed"
    FAILED = "failed"


class DocumentSegment(BaseModel):
    """A logical segment of a document (e.g., page, section, or paragraph)."""

    text: str = Field(..., description="Raw text content of the segment")
    section: Optional[str] = Field(
        None, description="Section heading or title if available"
    )
    page_number: Optional[int] = Field(
        None, description="1-indexed page number if applicable"
    )
    segment_index: int = Field(
        0, description="Sequential index of the segment within the document"
    )


class ParsedDocument(BaseModel):
    """Represents a document extracted by a parser before chunking."""

    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(
        ..., description="File extension without dot (e.g., txt, pdf, docx, md)"
    )
    source_path: str = Field(..., description="Absolute path to the source file")
    title: str = Field(..., description="Inferred or extracted document title")
    content_hash: str = Field(..., description="SHA-256 hash of the source content")
    segments: list[DocumentSegment] = Field(
        default_factory=list, description="Extracted document segments"
    )
    raw_text: str = Field(
        "", description="Full concatenated cleaned text of the document"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional custom metadata"
    )


class DocumentChunk(BaseModel):
    """Represents an individual text chunk ready for embedding and storage."""

    chunk_id: str = Field(..., description="Unique chunk identifier, e.g. doc_id_c0")
    document_id: str = Field(..., description="ID of parent document")
    content: str = Field(..., description="Text content of the chunk")
    chunk_index: int = Field(..., description="0-indexed position of chunk in document")
    total_chunks: int = Field(
        ..., description="Total chunks produced for this document"
    )
    section: Optional[str] = Field(None, description="Section heading if applicable")
    page_number: Optional[int] = Field(
        None, description="1-indexed page number if applicable"
    )
    embedding: Optional[list[float]] = Field(
        None, description="Vector embedding of the chunk content"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata preserved for retrieval"
    )

    def to_vector_document(self) -> dict[str, Any]:
        """Convert chunk into MongoDB vector store document format."""
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "embedding": self.embedding,
            "metadata": {
                "chunk_id": self.chunk_id,
                "document_id": self.document_id,
                "filename": self.metadata.get("filename", ""),
                "file_type": self.metadata.get("file_type", ""),
                "source_path": self.metadata.get("source_path", ""),
                "title": self.metadata.get("title", ""),
                "section": self.section,
                "page_number": self.page_number,
                "chunk_index": self.chunk_index,
                "total_chunks": self.total_chunks,
                "content_hash": self.metadata.get("content_hash", ""),
                "ingestion_timestamp": self.metadata.get(
                    "ingestion_timestamp", datetime.now(timezone.utc).isoformat()
                ),
                **{
                    k: v
                    for k, v in self.metadata.items()
                    if k
                    not in {
                        "filename",
                        "file_type",
                        "source_path",
                        "title",
                        "section",
                        "page_number",
                        "chunk_index",
                        "total_chunks",
                        "content_hash",
                        "ingestion_timestamp",
                    }
                },
            },
        }


class IngestionResult(BaseModel):
    """Result summary for a single document ingestion."""

    status: IngestionStatus = Field(..., description="Outcome of ingestion")
    document_id: Optional[str] = Field(
        None, description="Assigned or existing document ID"
    )
    filename: str = Field(..., description="Name of the file processed")
    source_path: str = Field(..., description="Path to the file")
    content_hash: Optional[str] = Field(
        None, description="SHA-256 hash of file content"
    )
    chunk_count: int = Field(0, description="Number of chunks generated")
    error_message: Optional[str] = Field(
        None, description="Error details if ingestion failed"
    )


class PipelineSummary(BaseModel):
    """Aggregate summary of an ingestion run across multiple documents."""

    total_scanned: int = Field(0, description="Total files discovered")
    ingested: int = Field(0, description="Number of newly ingested documents")
    skipped_duplicate: int = Field(
        0, description="Number of documents skipped as duplicates"
    )
    reindexed: int = Field(0, description="Number of documents re-indexed")
    failed: int = Field(0, description="Number of failed documents")
    results: list[IngestionResult] = Field(
        default_factory=list, description="Individual file results"
    )
