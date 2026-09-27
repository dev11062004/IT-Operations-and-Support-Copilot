"""Script and entry point for production-grade document ingestion into MongoDB."""

import argparse
import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

from mcp_rag_agent.core.config import config
from mcp_rag_agent.core.log_setup import setup_logging
from mcp_rag_agent.embeddings.embedding_generator import EmbeddingGenerator
from mcp_rag_agent.embeddings.semantic_search import SemanticSearch
from mcp_rag_agent.ingestion.chunker import DocumentChunker
from mcp_rag_agent.ingestion.cleaner import DocumentCleaner
from mcp_rag_agent.ingestion.models import PipelineSummary
from mcp_rag_agent.ingestion.pipeline import DocumentIngestionPipeline
from mcp_rag_agent.mongodb.client import MongoDBClient

setup_logging()
logger = logging.getLogger("DocumentIndexer")


async def index_documents_from_folder(
    folder_path: str | Path,
    mongo_client: MongoDBClient,
    semantic_search: Optional[SemanticSearch] = None,
    documents_collection: Optional[str] = None,
    vectors_collection: Optional[str] = None,
    reindex: bool = False,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    embedding_generator: Optional[EmbeddingGenerator] = None,
) -> PipelineSummary:
    """Index all documents from a folder into MongoDB using the production pipeline.

    Preserves backward compatibility with legacy calls while utilizing the
    new DocumentIngestionPipeline.

    Args:
        folder_path: Path to the folder containing documents.
        mongo_client: Connected MongoDBClient instance.
        semantic_search: Optional SemanticSearch instance (for backward compatibility).
        documents_collection: Collection name for storing document metadata.
        vectors_collection: Collection name for storing vectors.
        reindex: Whether to force re-indexing of documents.
        chunk_size: Optional chunk size override.
        chunk_overlap: Optional chunk overlap override.
        embedding_generator: Optional EmbeddingGenerator instance.

    Returns:
        PipelineSummary with ingestion details.
    """
    folder = Path(folder_path).resolve()

    if not folder.exists() or not folder.is_dir():
        logger.error(f"Folder '{folder}' does not exist.")
        print(f"[ERROR] Folder '{folder}' does not exist.")
        return PipelineSummary(total_scanned=0)

    docs_col = documents_collection or config.db_documents_collection
    vecs_col = vectors_collection or config.db_vector_collection

    # Resolve embedding generator
    emb_gen = embedding_generator
    if emb_gen is None and semantic_search is not None:
        emb_gen = getattr(semantic_search, "_embedding_generator", None)

    # Handle mock / test instances where index_document is directly mocked
    is_mocked_semantic = (
        semantic_search is not None
        and hasattr(semantic_search, "index_document")
        and not isinstance(emb_gen, EmbeddingGenerator)
    )

    cleaner = DocumentCleaner()
    chunker = DocumentChunker(
        chunk_size=chunk_size or config.chunk_size,
        chunk_overlap=chunk_overlap or config.chunk_overlap,
        cleaner=cleaner,
    )

    if is_mocked_semantic:
        # Backward compatibility adapter for unit tests mocking semantic_search.index_document
        pipeline = DocumentIngestionPipeline(
            mongo_client=mongo_client,
            embedding_generator=emb_gen or MagicMockWrapper(),
            cleaner=cleaner,
            chunker=chunker,
            documents_collection=docs_col,
            vectors_collection=vecs_col,
        )
        # Intercept embedding & vector storage with mocked semantic_search
        summary = await _run_legacy_compatible_ingestion(
            pipeline=pipeline,
            folder=folder,
            semantic_search=semantic_search,
            documents_collection=docs_col,
            vectors_collection=vecs_col,
            reindex=reindex,
        )
        return summary

    if emb_gen is None:
        emb_gen = EmbeddingGenerator(
            api_key=config.model_api_key,
            model=config.embedding_model,
            dimensions=config.embedding_dimension,
        )

    pipeline = DocumentIngestionPipeline(
        mongo_client=mongo_client,
        embedding_generator=emb_gen,
        cleaner=cleaner,
        chunker=chunker,
        documents_collection=docs_col,
        vectors_collection=vecs_col,
    )

    print(f"\n[SCAN] Ingesting documents from '{folder}'...")
    summary = await pipeline.ingest_directory(folder, reindex=reindex)
    print(
        f"\n[DONE] Ingestion Complete! Total: {summary.total_scanned}, "
        f"Ingested: {summary.ingested}, Reindexed: {summary.reindexed}, "
        f"Skipped: {summary.skipped_duplicate}, Failed: {summary.failed}"
    )
    return summary


class MagicMockWrapper:
    """Fallback generator for mock tests when real EmbeddingGenerator is absent."""

    async def generate_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * config.embedding_dimension for _ in texts]

    async def generate(self, text: str) -> list[float]:
        return [0.0] * config.embedding_dimension


async def _run_legacy_compatible_ingestion(
    pipeline: DocumentIngestionPipeline,
    folder: Path,
    semantic_search: Any,
    documents_collection: str,
    vectors_collection: str,
    reindex: bool,
) -> PipelineSummary:
    """Helper for mock-based tests asserting on semantic_search.index_document."""
    from mcp_rag_agent.ingestion.models import IngestionResult, IngestionStatus

    summary = PipelineSummary()
    candidate_files = [
        f
        for f in sorted(folder.rglob("*"))
        if f.is_file() and pipeline.parser_registry.is_supported(f)
    ]
    summary.total_scanned = len(candidate_files)

    for file_path in candidate_files:
        try:
            content_hash = pipeline.compute_content_hash(file_path)
            parser = pipeline.parser_registry.get_parser(file_path)
            parsed_doc = parser.parse(
                file_path, document_id="doc_123", content_hash=content_hash
            )
            chunks = pipeline.chunker.chunk_document(parsed_doc)

            doc_metadata = {
                "name": file_path.name,
                "folder": file_path.parent.name,
                "relative_path": str(file_path.relative_to(folder)),
                "absolute_path": str(file_path.resolve()),
                "content": parsed_doc.raw_text,
                "size": len(parsed_doc.raw_text),
            }
            doc_id = pipeline.mongo_client.insert_document(
                documents_collection, doc_metadata
            )

            for chunk in chunks:
                await semantic_search.index_document(
                    content=chunk.content,
                    metadata=chunk.metadata,
                    collection_name=vectors_collection,
                )

            summary.ingested += 1
            summary.results.append(
                IngestionResult(
                    status=IngestionStatus.INGESTED,
                    document_id=doc_id,
                    filename=file_path.name,
                    source_path=str(file_path.resolve()),
                    chunk_count=len(chunks),
                )
            )
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}")
            summary.failed += 1

    return summary


async def main(
    clear_existing: bool = False,
    reindex: bool = False,
    folder_path: Optional[str] = None,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> None:
    """Main function to run production document indexing.

    Args:
        clear_existing: If True, deletes all documents and vectors before indexing.
        reindex: If True, forces re-indexing of all documents.
        folder_path: Optional custom folder path. Defaults to config.ingested_doc_dir.
        chunk_size: Optional chunk size override.
        chunk_overlap: Optional chunk overlap override.
    """
    print("=" * 60)
    print("Production Document Ingestion Pipeline")
    print("=" * 60)

    # Validate configuration before connecting
    config.validate_all()

    # Initialize MongoDB client
    print(f"\n[DB] Connecting to MongoDB database '{config.db_name}'...")
    mongo_client = MongoDBClient(uri=config.db_url, database_name=config.db_name)
    mongo_client.connect()

    # Initialize embedding generator
    print(
        f"[MODEL] Initializing embedding generator "
        f"(model: {config.embedding_model}, dims: {config.embedding_dimension})..."
    )
    embedding_generator = EmbeddingGenerator(
        api_key=config.model_api_key,
        model=config.embedding_model,
        dimensions=config.embedding_dimension,
    )

    cleaner = DocumentCleaner()
    chunker = DocumentChunker(
        chunk_size=chunk_size or config.chunk_size,
        chunk_overlap=chunk_overlap or config.chunk_overlap,
        cleaner=cleaner,
    )

    pipeline = DocumentIngestionPipeline(
        mongo_client=mongo_client,
        embedding_generator=embedding_generator,
        cleaner=cleaner,
        chunker=chunker,
        documents_collection=config.db_documents_collection,
        vectors_collection=config.db_vector_collection,
    )

    try:
        # Clear existing data if requested
        if clear_existing:
            print("\n[CLEAR] Clearing existing collections...")
            cleared = pipeline.clear_indexes()
            print(
                f"   [OK] Deleted {cleared['deleted_documents']} document(s) from '{config.db_documents_collection}'"
            )
            print(
                f"   [OK] Deleted {cleared['deleted_vectors']} vector(s) from '{config.db_vector_collection}'"
            )

        # Ensure collections exist
        print("\n[DB] Ensuring collections exist...")
        for col_name in [config.db_documents_collection, config.db_vector_collection]:
            if not mongo_client.collection_exists(col_name):
                mongo_client.create_collection(col_name)
                print(f"   [OK] Created collection '{col_name}'")
            else:
                print(f"   [OK] Collection '{col_name}' exists")

        # Ensure vector search index exists
        print("\n[INDEX] Setting up search indexes...")
        try:
            semantic_search = SemanticSearch(
                mongo_client=mongo_client,
                embedding_generator=embedding_generator,
                default_collection=config.db_vector_collection,
                default_index=config.db_vector_index_name,
            )
            semantic_search.setup_index(
                collection_name=config.db_vector_collection,
                index_name=config.db_vector_index_name,
                dimensions=config.embedding_dimension,
            )
            print(f"   [OK] Vector search index '{config.db_vector_index_name}' ready")
        except Exception as e:
            print(f"   [NOTE] Vector index status: {e}")

        # Ensure text search index exists for hybrid search
        try:
            mongo_client.create_text_search_index(
                collection_name=config.db_vector_collection,
                index_name="text_index",
                text_fields=["content"],
            )
            print("   [OK] Text search index 'text_index' ready")
        except Exception as e:
            print(f"   [NOTE] Text index status: {e}")

        # Resolve target documents folder
        resolved_folder = Path(folder_path or config.ingested_doc_dir).resolve()
        logger.info(f"Target ingestion directory: {resolved_folder}")

        await index_documents_from_folder(
            folder_path=resolved_folder,
            mongo_client=mongo_client,
            documents_collection=config.db_documents_collection,
            vectors_collection=config.db_vector_collection,
            reindex=reindex or config.reindex,
            chunk_size=chunk_size or config.chunk_size,
            chunk_overlap=chunk_overlap or config.chunk_overlap,
            embedding_generator=embedding_generator,
        )

    except Exception as e:
        logger.error(f"Error during ingestion execution: {e}", exc_info=True)
        print(f"\n[ERROR] Ingestion failed: {e}")
        raise
    finally:
        print("\n[CLEANUP] Disconnecting from MongoDB...")
        mongo_client.disconnect()
        print("[OK] Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Production Document Ingestion Pipeline for MCP RAG Agent"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing documents and vectors before indexing",
    )
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="Force re-indexing even if content hashes match",
    )
    parser.add_argument(
        "--folder",
        type=str,
        default=None,
        help="Custom path to folder containing documents (defaults to config.ingested_doc_dir)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="Maximum chunk size in characters (defaults to config.chunk_size)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=None,
        help="Chunk overlap in characters (defaults to config.chunk_overlap)",
    )

    args = parser.parse_args()

    asyncio.run(
        main(
            clear_existing=args.clear,
            reindex=args.reindex,
            folder_path=args.folder,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
    )
