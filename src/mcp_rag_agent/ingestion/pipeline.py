"""Production-grade document ingestion pipeline coordinating parsing, cleaning, chunking, embedding, and storage."""

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from mcp_rag_agent.core.config import config
from mcp_rag_agent.embeddings.embedding_generator import EmbeddingGenerator
from mcp_rag_agent.ingestion.chunker import DocumentChunker
from mcp_rag_agent.ingestion.cleaner import DocumentCleaner
from mcp_rag_agent.ingestion.models import (
    DocumentChunk,
    IngestionResult,
    IngestionStatus,
    PipelineSummary,
)
from mcp_rag_agent.ingestion.parsers import (
    ParserRegistry,
    UnsupportedFileTypeError,
    default_parser_registry,
)
from mcp_rag_agent.mongodb.client import MongoDBClient

logger = logging.getLogger("IngestionPipeline")


class DocumentIngestionPipeline:
    """End-to-end scalable pipeline for ingesting, chunking, embedding, and indexing documents."""

    def __init__(
        self,
        mongo_client: MongoDBClient,
        embedding_generator: EmbeddingGenerator,
        cleaner: Optional[DocumentCleaner] = None,
        chunker: Optional[DocumentChunker] = None,
        parser_registry: Optional[ParserRegistry] = None,
        documents_collection: Optional[str] = None,
        vectors_collection: Optional[str] = None,
    ):
        """Initialize ingestion pipeline.

        Args:
            mongo_client: Connected MongoDBClient instance.
            embedding_generator: EmbeddingGenerator instance for chunk vectors.
            cleaner: DocumentCleaner instance for text normalization.
            chunker: DocumentChunker instance for structure-aware splitting.
            parser_registry: Registry of supported format parsers.
            documents_collection: MongoDB collection for parent document metadata.
            vectors_collection: MongoDB collection for chunk vector embeddings.
        """
        self.mongo_client = mongo_client
        self.embedding_generator = embedding_generator
        self.cleaner = cleaner or DocumentCleaner()
        self.chunker = chunker or DocumentChunker(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            cleaner=self.cleaner,
        )
        self.parser_registry = parser_registry or default_parser_registry
        self.documents_collection = (
            documents_collection or config.db_documents_collection
        )
        self.vectors_collection = vectors_collection or config.db_vector_collection

    @staticmethod
    def compute_content_hash(file_path: Path) -> str:
        """Compute SHA-256 hash of file content.

        Args:
            file_path: Path to the target file.

        Returns:
            Hex-encoded SHA-256 digest.
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def ingest_file(
        self, file_path: Path | str, reindex: bool = False
    ) -> IngestionResult:
        """Process, chunk, embed, and store a single document.

        Args:
            file_path: Path to document file.
            reindex: If True, forces re-indexing even if content hash matches.

        Returns:
            IngestionResult with status and execution details.
        """
        path = Path(file_path).resolve()
        if not path.is_file():
            logger.error(f"File not found: {path}")
            return IngestionResult(
                status=IngestionStatus.FAILED,
                filename=path.name,
                source_path=str(path),
                error_message=f"File not found: {path}",
            )

        # 1. Compute content hash for deduplication
        try:
            content_hash = self.compute_content_hash(path)
        except Exception as e:
            logger.error(
                f"Failed to compute content hash for {path.name}: {e}", exc_info=True
            )
            return IngestionResult(
                status=IngestionStatus.FAILED,
                filename=path.name,
                source_path=str(path),
                error_message=f"Hash computation failed: {e}",
            )

        # 2. Duplicate & incremental check against documents collection
        abs_source_path = str(path)
        existing_doc_by_hash = self.mongo_client.find_document(
            collection_name=self.documents_collection,
            query={"content_hash": content_hash},
        )
        existing_doc_by_path = self.mongo_client.find_document(
            collection_name=self.documents_collection,
            query={"source_path": abs_source_path},
        )

        is_reindex_action = False

        if existing_doc_by_hash and not reindex:
            # File with identical content hash already ingested
            logger.info(
                f"[SKIP] Document '{path.name}' already ingested with hash {content_hash[:8]}..."
            )
            return IngestionResult(
                status=IngestionStatus.SKIPPED_DUPLICATE,
                document_id=existing_doc_by_hash.get("document_id"),
                filename=path.name,
                source_path=abs_source_path,
                content_hash=content_hash,
                chunk_count=existing_doc_by_hash.get("total_chunks", 0),
            )

        # If reindex requested or same file path exists with different hash, purge old data
        stale_doc = existing_doc_by_path or existing_doc_by_hash
        if stale_doc and (reindex or stale_doc.get("content_hash") != content_hash):
            old_doc_id = stale_doc.get("document_id")
            if old_doc_id:
                logger.info(
                    f"[PURGE] Removing stale document and chunks for ID {old_doc_id}"
                )
                self.mongo_client.delete_documents(
                    collection_name=self.vectors_collection,
                    query={"metadata.document_id": old_doc_id},
                )
                self.mongo_client.delete_documents(
                    collection_name=self.documents_collection,
                    query={"document_id": old_doc_id},
                )
            is_reindex_action = True

        # 3. Parse document
        try:
            parser = self.parser_registry.get_parser(path)
        except UnsupportedFileTypeError as e:
            logger.error(f"[ERROR] Unsupported file format for {path.name}: {e}")
            return IngestionResult(
                status=IngestionStatus.FAILED,
                filename=path.name,
                source_path=abs_source_path,
                content_hash=content_hash,
                error_message=str(e),
            )

        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        try:
            logger.info(
                f"[PARSE] Parsing {path.name} using {parser.__class__.__name__}"
            )
            parsed_doc = parser.parse(
                path, document_id=doc_id, content_hash=content_hash
            )
        except Exception as e:
            logger.error(f"[ERROR] Failed to parse {path.name}: {e}", exc_info=True)
            return IngestionResult(
                status=IngestionStatus.FAILED,
                document_id=doc_id,
                filename=path.name,
                source_path=abs_source_path,
                content_hash=content_hash,
                error_message=f"Parsing error: {e}",
            )

        # 4. Chunk document
        chunks: list[DocumentChunk] = self.chunker.chunk_document(
            parsed_doc=parsed_doc, ingestion_timestamp=timestamp
        )

        if not chunks:
            logger.warning(
                f"[WARN] File '{path.name}' produced 0 chunks (empty content)"
            )
            return IngestionResult(
                status=IngestionStatus.FAILED,
                document_id=doc_id,
                filename=path.name,
                source_path=abs_source_path,
                content_hash=content_hash,
                error_message="Document produced zero chunks after cleaning and splitting",
            )

        # 5. Generate embeddings per chunk in batch
        logger.info(
            f"[EMBED] Generating embeddings for {len(chunks)} chunk(s) of '{path.name}'"
        )
        try:
            chunk_texts = [c.content for c in chunks]
            embeddings = await self.embedding_generator.generate_batch(chunk_texts)
            for chunk, emb in zip(chunks, embeddings):
                chunk.embedding = emb
        except Exception as e:
            logger.error(
                f"[ERROR] Failed generating embeddings for {path.name}: {e}",
                exc_info=True,
            )
            return IngestionResult(
                status=IngestionStatus.FAILED,
                document_id=doc_id,
                filename=path.name,
                source_path=abs_source_path,
                content_hash=content_hash,
                error_message=f"Embedding generation error: {e}",
            )

        # 6. Store parent document metadata in documents collection
        doc_record = {
            "document_id": doc_id,
            "filename": path.name,
            "file_type": parsed_doc.file_type,
            "source_path": abs_source_path,
            "title": parsed_doc.title,
            "content_hash": content_hash,
            "total_chunks": len(chunks),
            "total_characters": len(parsed_doc.raw_text),
            "ingestion_timestamp": timestamp,
            "created_at": datetime.now(timezone.utc),
        }
        self.mongo_client.insert_document(
            collection_name=self.documents_collection, document=doc_record
        )

        # 7. Store chunks separately in vectors collection
        vector_docs = [chunk.to_vector_document() for chunk in chunks]
        self.mongo_client.insert_documents(
            collection_name=self.vectors_collection, documents=vector_docs
        )

        outcome_status = (
            IngestionStatus.REINDEXED if is_reindex_action else IngestionStatus.INGESTED
        )
        logger.info(
            f"[OK] Successfully {outcome_status.value} '{path.name}' "
            f"({len(chunks)} chunks, ID: {doc_id})"
        )

        return IngestionResult(
            status=outcome_status,
            document_id=doc_id,
            filename=path.name,
            source_path=abs_source_path,
            content_hash=content_hash,
            chunk_count=len(chunks),
        )

    async def ingest_directory(
        self, directory_path: Path | str, reindex: bool = False
    ) -> PipelineSummary:
        """Scan directory recursively and ingest all supported documents.

        Args:
            directory_path: Root folder path containing documents.
            reindex: If True, forces re-indexing of all documents.

        Returns:
            PipelineSummary with detailed per-file results.
        """
        dir_path = Path(directory_path).resolve()
        if not dir_path.is_dir():
            logger.error(f"Directory does not exist: {dir_path}")
            return PipelineSummary(total_scanned=0)

        # Find all files supported by registered parsers
        candidate_files: list[Path] = []
        for file in sorted(dir_path.rglob("*")):
            if file.is_file() and self.parser_registry.is_supported(file):
                candidate_files.append(file)

        summary = PipelineSummary(total_scanned=len(candidate_files))
        logger.info(
            f"[SCAN] Found {len(candidate_files)} supported document(s) in {dir_path}"
        )

        for file_path in candidate_files:
            result = await self.ingest_file(file_path=file_path, reindex=reindex)
            summary.results.append(result)
            if result.status == IngestionStatus.INGESTED:
                summary.ingested += 1
            elif result.status == IngestionStatus.SKIPPED_DUPLICATE:
                summary.skipped_duplicate += 1
            elif result.status == IngestionStatus.REINDEXED:
                summary.reindexed += 1
            elif result.status == IngestionStatus.FAILED:
                summary.failed += 1

        logger.info(
            f"[SUMMARY] Total: {summary.total_scanned}, Ingested: {summary.ingested}, "
            f"Reindexed: {summary.reindexed}, Skipped: {summary.skipped_duplicate}, "
            f"Failed: {summary.failed}"
        )
        return summary

    def clear_indexes(self) -> dict[str, int]:
        """Delete all documents and vectors from both collections.

        Returns:
            Dictionary with counts of deleted documents and vectors.
        """
        deleted_docs = 0
        deleted_vectors = 0

        if self.mongo_client.collection_exists(self.documents_collection):
            deleted_docs = self.mongo_client.delete_documents(
                collection_name=self.documents_collection, query={}
            )
            logger.info(
                f"[CLEAR] Deleted {deleted_docs} documents from {self.documents_collection}"
            )

        if self.mongo_client.collection_exists(self.vectors_collection):
            deleted_vectors = self.mongo_client.delete_documents(
                collection_name=self.vectors_collection, query={}
            )
            logger.info(
                f"[CLEAR] Deleted {deleted_vectors} vectors from {self.vectors_collection}"
            )

        return {"deleted_documents": deleted_docs, "deleted_vectors": deleted_vectors}
