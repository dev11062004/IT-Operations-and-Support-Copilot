"""Intelligent text chunking with structural awareness and metadata preservation."""

import logging
from datetime import datetime, timezone
from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter

from mcp_rag_agent.ingestion.cleaner import DocumentCleaner
from mcp_rag_agent.ingestion.models import DocumentChunk, ParsedDocument

logger = logging.getLogger("DocumentChunker")


class DocumentChunker:
    """Chunks documents intelligently while preserving section/page structure and metadata."""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        cleaner: Optional[DocumentCleaner] = None,
    ):
        """Initialize DocumentChunker.

        Args:
            chunk_size: Maximum character length per chunk.
            chunk_overlap: Overlapping character count between consecutive chunks.
            cleaner: DocumentCleaner instance for text normalization.
        """
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {chunk_size}")
        if chunk_overlap < 0:
            raise ValueError(f"chunk_overlap cannot be negative, got {chunk_overlap}")
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be strictly less than chunk_size ({chunk_size})"
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.cleaner = cleaner or DocumentCleaner()

        # Hierarchical separators preserving paragraphs, lines, sentences, and words
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", "? ", "! ", " ", ""],
            keep_separator=True,
            strip_whitespace=True,
        )

    def chunk_document(
        self, parsed_doc: ParsedDocument, ingestion_timestamp: Optional[str] = None
    ) -> list[DocumentChunk]:
        """Split a parsed document into structured DocumentChunks.

        Args:
            parsed_doc: The parsed document with extracted segments and metadata.
            ingestion_timestamp: Optional ISO 8601 UTC timestamp. Defaults to now.

        Returns:
            List of enriched DocumentChunk instances.
        """
        timestamp = ingestion_timestamp or datetime.now(timezone.utc).isoformat()
        raw_chunks: list[dict] = []

        if parsed_doc.segments:
            for segment in parsed_doc.segments:
                cleaned_seg_text = self.cleaner.clean(segment.text)
                if not cleaned_seg_text:
                    continue

                if len(cleaned_seg_text) <= self.chunk_size:
                    raw_chunks.append(
                        {
                            "content": cleaned_seg_text,
                            "section": segment.section,
                            "page_number": segment.page_number,
                        }
                    )
                else:
                    splits = self._splitter.split_text(cleaned_seg_text)
                    for split in splits:
                        raw_chunks.append(
                            {
                                "content": split,
                                "section": segment.section,
                                "page_number": segment.page_number,
                            }
                        )
        else:
            cleaned_text = self.cleaner.clean(parsed_doc.raw_text)
            if cleaned_text:
                splits = self._splitter.split_text(cleaned_text)
                for split in splits:
                    raw_chunks.append(
                        {
                            "content": split,
                            "section": None,
                            "page_number": None,
                        }
                    )

        total_chunks = len(raw_chunks)
        final_chunks: list[DocumentChunk] = []

        for idx, item in enumerate(raw_chunks):
            chunk_id = f"{parsed_doc.document_id}_c{idx}"
            chunk_metadata = {
                "chunk_id": chunk_id,
                "document_id": parsed_doc.document_id,
                "filename": parsed_doc.filename,
                "file_type": parsed_doc.file_type,
                "source_path": parsed_doc.source_path,
                "title": parsed_doc.title,
                "section": item["section"],
                "page_number": item["page_number"],
                "chunk_index": idx,
                "total_chunks": total_chunks,
                "content_hash": parsed_doc.content_hash,
                "ingestion_timestamp": timestamp,
                **parsed_doc.metadata,
            }

            final_chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=parsed_doc.document_id,
                    content=item["content"],
                    chunk_index=idx,
                    total_chunks=total_chunks,
                    section=item["section"],
                    page_number=item["page_number"],
                    embedding=None,
                    metadata=chunk_metadata,
                )
            )

        logger.debug(
            f"Chunked document '{parsed_doc.filename}' into {total_chunks} chunk(s) "
            f"(size={self.chunk_size}, overlap={self.chunk_overlap})"
        )
        return final_chunks
