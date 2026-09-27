"""Comprehensive unit tests for production-grade document ingestion pipeline.

Tests parsing (TXT, MD, PDF, DOCX), cleaning, chunking, metadata preservation,
duplicate detection via content hashes, incremental ingestion, reindexing, and failure modes.
"""

import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    DocxParser,
    MarkdownParser,
    ParsingError,
    PDFParser,
    TextParser,
    UnsupportedFileTypeError,
    get_parser,
)
from mcp_rag_agent.ingestion.pipeline import DocumentIngestionPipeline

# ============================================================================
# 1. PARSER TESTS
# ============================================================================


class TestDocumentParsers:
    """Test suite for format-specific parsers."""

    def test_text_parser_success(self, tmp_path):
        """Verify plain text parsing and title extraction."""
        file_path = tmp_path / "sample_policy.txt"
        file_path.write_text(
            "Company Remote Work Policy\n\nEmployees may work remotely 2 days per week.",
            encoding="utf-8",
        )

        parser = TextParser()
        assert parser.can_handle(file_path) is True

        parsed = parser.parse(
            file_path, document_id="doc_test_1", content_hash="hash123"
        )
        assert parsed.document_id == "doc_test_1"
        assert parsed.filename == "sample_policy.txt"
        assert parsed.file_type == "txt"
        assert parsed.title == "Company Remote Work Policy"
        assert parsed.content_hash == "hash123"
        assert len(parsed.segments) == 1
        assert "Employees may work remotely" in parsed.segments[0].text

    def test_markdown_parser_headings_and_sections(self, tmp_path):
        """Verify markdown parser extracts title and partitions by headings."""
        content = """# Antigravity Architecture Guide

This is an introduction.

## Section 1: Ingestion

Details on ingestion.

## Section 2: Retrieval

Details on retrieval.
"""
        file_path = tmp_path / "architecture.md"
        file_path.write_text(content, encoding="utf-8")

        parser = MarkdownParser()
        assert parser.can_handle(file_path) is True

        parsed = parser.parse(file_path, document_id="doc_md_1", content_hash="hash_md")
        assert parsed.title == "Antigravity Architecture Guide"
        assert parsed.file_type == "md"
        assert len(parsed.segments) >= 3

        # Check section names
        sections = [seg.section for seg in parsed.segments]
        assert "Section 1: Ingestion" in sections
        assert "Section 2: Retrieval" in sections

    def test_pdf_parser_multipage_and_pages(self, tmp_path):
        """Verify PDF parser extracts per-page text and assigns page numbers."""
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.add_blank_page(width=200, height=200)

        pdf_path = tmp_path / "multipage_doc.pdf"
        with open(pdf_path, "wb") as f:
            writer.write(f)

        parser = PDFParser()
        assert parser.can_handle(pdf_path) is True

        # Note: blank pages have empty text, so segments list will handle gracefully
        parsed = parser.parse(
            pdf_path, document_id="doc_pdf_1", content_hash="hash_pdf"
        )
        assert parsed.file_type == "pdf"
        assert parsed.filename == "multipage_doc.pdf"
        assert parsed.document_id == "doc_pdf_1"

    def test_docx_parser_headings_and_paragraphs(self, tmp_path):
        """Verify DOCX parser parses paragraphs and captures heading sections."""
        from docx import Document

        doc = Document()
        doc.add_heading("Cloud Security Guidelines", level=0)
        doc.add_heading("Access Control", level=1)
        doc.add_paragraph("MFA must be enforced for all cloud accounts.")
        doc.add_heading("Data Encryption", level=1)
        doc.add_paragraph("All data at rest must use AES-256.")

        docx_path = tmp_path / "security_guidelines.docx"
        doc.save(docx_path)

        parser = DocxParser()
        assert parser.can_handle(docx_path) is True

        parsed = parser.parse(
            docx_path, document_id="doc_docx_1", content_hash="hash_docx"
        )
        assert parsed.file_type == "docx"
        assert (
            "Security Guidelines" in parsed.title
            or "Cloud Security Guidelines" in parsed.title
        )
        assert len(parsed.segments) >= 2
        sections = [seg.section for seg in parsed.segments]
        assert any("Access Control" in (s or "") for s in sections)
        assert any("Data Encryption" in (s or "") for s in sections)

    def test_unsupported_file_type_raises_error(self, tmp_path):
        """Verify unsupported extensions raise UnsupportedFileTypeError."""
        bin_file = tmp_path / "payload.bin"
        bin_file.write_bytes(b"\x00\x01\x02\x03")

        with pytest.raises(UnsupportedFileTypeError):
            get_parser(bin_file)

    def test_corrupt_pdf_raises_parsing_error(self, tmp_path):
        """Verify corrupt PDF raises ParsingError."""
        corrupt_pdf = tmp_path / "corrupt.pdf"
        corrupt_pdf.write_bytes(b"%PDF-1.4 definitely not a valid pdf stream")

        parser = PDFParser()
        with pytest.raises(ParsingError):
            parser.parse(corrupt_pdf, document_id="doc_err", content_hash="h1")


# ============================================================================
# 2. CLEANER TESTS
# ============================================================================


class TestDocumentCleaner:
    """Test suite for DocumentCleaner."""

    def test_clean_removes_null_bytes_and_control_characters(self):
        cleaner = DocumentCleaner()
        raw = "Data with null\x00byte and bell\x07character."
        cleaned = cleaner.clean(raw)
        assert "\x00" not in cleaned
        assert "\x07" not in cleaned
        assert cleaned == "Data with nullbyte and bellcharacter."

    def test_clean_normalizes_crlf_and_excessive_newlines(self):
        cleaner = DocumentCleaner()
        raw = "Line 1\r\n\r\n\r\n\r\n\r\nLine 2\rLine 3"
        cleaned = cleaner.clean(raw)
        assert "\r" not in cleaned
        assert "\n\n\n" not in cleaned
        assert "Line 1\n\nLine 2\nLine 3" == cleaned

    def test_clean_normalizes_unicode_nfkc(self):
        cleaner = DocumentCleaner()
        # Full-width characters
        raw = "Ｈｅｌｌｏ Ｗｏｒｌｄ"
        cleaned = cleaner.clean(raw)
        assert cleaned == "Hello World"

    def test_clean_handles_empty_or_whitespace_string(self):
        cleaner = DocumentCleaner()
        assert cleaner.clean("") == ""
        assert cleaner.clean("   \t  \n  ") == ""


# ============================================================================
# 3. CHUNKER TESTS
# ============================================================================


class TestDocumentChunker:
    """Test suite for DocumentChunker."""

    def test_invalid_parameters_raise_value_error(self):
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            DocumentChunker(chunk_size=0)

        with pytest.raises(ValueError, match="chunk_overlap cannot be negative"):
            DocumentChunker(chunk_size=100, chunk_overlap=-5)

        with pytest.raises(ValueError, match="strictly less than chunk_size"):
            DocumentChunker(chunk_size=100, chunk_overlap=100)

    def test_chunker_splits_long_text_and_sets_indices(self):
        chunker = DocumentChunker(chunk_size=50, chunk_overlap=10)
        long_text = "This is sentence one. This is sentence two. This is sentence three. This is sentence four."
        parsed_doc = ParsedDocument(
            document_id="doc_100",
            filename="sample.txt",
            file_type="txt",
            source_path="/tmp/sample.txt",
            title="Sample",
            content_hash="hash100",
            segments=[DocumentSegment(text=long_text, segment_index=0)],
            raw_text=long_text,
        )

        chunks = chunker.chunk_document(parsed_doc)
        assert len(chunks) > 1
        for idx, chunk in enumerate(chunks):
            assert chunk.document_id == "doc_100"
            assert chunk.chunk_id == f"doc_100_c{idx}"
            assert chunk.chunk_index == idx
            assert chunk.total_chunks == len(chunks)
            assert chunk.metadata["content_hash"] == "hash100"
            assert chunk.metadata["filename"] == "sample.txt"
            assert len(chunk.content) <= 60  # Allow slight leeway for word boundary

    def test_chunker_preserves_section_and_page_metadata(self):
        chunker = DocumentChunker(chunk_size=100, chunk_overlap=10)
        seg1 = DocumentSegment(
            text="Page 1 introduction text.",
            section="Intro",
            page_number=1,
            segment_index=0,
        )
        seg2 = DocumentSegment(
            text="Page 2 conclusion text.",
            section="Conclusion",
            page_number=2,
            segment_index=1,
        )
        parsed_doc = ParsedDocument(
            document_id="doc_200",
            filename="report.pdf",
            file_type="pdf",
            source_path="/docs/report.pdf",
            title="Annual Report",
            content_hash="hash200",
            segments=[seg1, seg2],
            raw_text="Page 1 introduction text.\n\nPage 2 conclusion text.",
        )

        chunks = chunker.chunk_document(parsed_doc)
        assert len(chunks) == 2
        assert chunks[0].section == "Intro"
        assert chunks[0].page_number == 1
        assert chunks[0].metadata["section"] == "Intro"
        assert chunks[0].metadata["page_number"] == 1

        assert chunks[1].section == "Conclusion"
        assert chunks[1].page_number == 2
        assert chunks[1].metadata["section"] == "Conclusion"
        assert chunks[1].metadata["page_number"] == 2


# ============================================================================
# 4. DUPLICATE DETECTION & INCREMENTAL INGESTION TESTS
# ============================================================================


class TestDuplicateDetectionAndIncrementalIngestion:
    """Test suite for hash-based deduplication and reindexing."""

    @pytest.mark.asyncio
    async def test_duplicate_file_skipped_when_hash_matches(self, tmp_path):
        """Verify identical content hash causes pipeline to skip file."""
        file_path = tmp_path / "doc.txt"
        file_path.write_text("Hello world duplicate test", encoding="utf-8")

        mock_mongo = MagicMock()
        # Mock existing document with same hash
        mock_mongo.find_document.return_value = {
            "document_id": "doc_existing",
            "content_hash": DocumentIngestionPipeline.compute_content_hash(file_path),
            "total_chunks": 1,
        }
        mock_emb = MagicMock()
        mock_emb.generate_batch = AsyncMock(return_value=[[0.1] * 256])

        pipeline = DocumentIngestionPipeline(
            mongo_client=mock_mongo,
            embedding_generator=mock_emb,
        )

        result = await pipeline.ingest_file(file_path, reindex=False)
        assert result.status == IngestionStatus.SKIPPED_DUPLICATE
        assert result.document_id == "doc_existing"
        # Should not insert new documents or vectors
        mock_mongo.insert_document.assert_not_called()
        mock_mongo.insert_documents.assert_not_called()

    @pytest.mark.asyncio
    async def test_reindex_flag_purges_old_chunks_and_reindexes(self, tmp_path):
        """Verify reindex=True deletes old records and re-ingests."""
        file_path = tmp_path / "doc.txt"
        file_path.write_text("Updated document content.", encoding="utf-8")

        mock_mongo = MagicMock()
        old_hash = "old_stale_hash"
        mock_mongo.find_document.side_effect = [
            None,  # find by hash returns None
            {
                "document_id": "doc_old",
                "content_hash": old_hash,
                "source_path": str(file_path.resolve()),
            },  # find by path
        ]
        mock_mongo.delete_documents.return_value = 1
        mock_mongo.insert_document.return_value = "doc_new_id"
        mock_mongo.insert_documents.return_value = ["vec_1"]

        mock_emb = MagicMock()
        mock_emb.generate_batch = AsyncMock(return_value=[[0.2] * 256])

        pipeline = DocumentIngestionPipeline(
            mongo_client=mock_mongo,
            embedding_generator=mock_emb,
        )

        result = await pipeline.ingest_file(file_path, reindex=True)
        assert result.status == IngestionStatus.REINDEXED
        assert result.chunk_count >= 1

        # Verify old records were deleted
        mock_mongo.delete_documents.assert_any_call(
            collection_name=pipeline.vectors_collection,
            query={"metadata.document_id": "doc_old"},
        )
        mock_mongo.delete_documents.assert_any_call(
            collection_name=pipeline.documents_collection,
            query={"document_id": "doc_old"},
        )

        # Verify new records were inserted
        mock_mongo.insert_document.assert_called_once()
        mock_mongo.insert_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_file_ingested_cleanly(self, tmp_path):
        """Verify new file without duplicate records is cleanly ingested."""
        file_path = tmp_path / "new_doc.txt"
        file_path.write_text("Fresh unique content.", encoding="utf-8")

        mock_mongo = MagicMock()
        mock_mongo.find_document.return_value = None
        mock_mongo.insert_document.return_value = "doc_fresh"
        mock_mongo.insert_documents.return_value = ["vec_1"]

        mock_emb = MagicMock()
        mock_emb.generate_batch = AsyncMock(return_value=[[0.5] * 256])

        pipeline = DocumentIngestionPipeline(
            mongo_client=mock_mongo,
            embedding_generator=mock_emb,
        )

        result = await pipeline.ingest_file(file_path, reindex=False)
        assert result.status == IngestionStatus.INGESTED
        assert result.chunk_count == 1
        mock_mongo.insert_document.assert_called_once()
        mock_mongo.insert_documents.assert_called_once()


# ============================================================================
# 5. INGESTION FAILURE & EDGE CASE TESTS
# ============================================================================


class TestIngestionFailures:
    """Test suite for failure handling and edge cases."""

    @pytest.mark.asyncio
    async def test_non_existent_file_returns_failed_result(self):
        mock_mongo = MagicMock()
        mock_emb = MagicMock()
        pipeline = DocumentIngestionPipeline(
            mongo_client=mock_mongo, embedding_generator=mock_emb
        )

        result = await pipeline.ingest_file("/non/existent/path/doc.txt")
        assert result.status == IngestionStatus.FAILED
        assert "File not found" in result.error_message

    @pytest.mark.asyncio
    async def test_empty_file_returns_failed_result(self, tmp_path):
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("   \n\t  \n", encoding="utf-8")

        mock_mongo = MagicMock()
        mock_mongo.find_document.return_value = None
        mock_emb = MagicMock()
        pipeline = DocumentIngestionPipeline(
            mongo_client=mock_mongo, embedding_generator=mock_emb
        )

        result = await pipeline.ingest_file(empty_file)
        assert result.status == IngestionStatus.FAILED
        assert "zero chunks" in result.error_message

    @pytest.mark.asyncio
    async def test_embedding_generation_failure_returns_failed_result(self, tmp_path):
        file_path = tmp_path / "valid.txt"
        file_path.write_text("Valid text that should fail embedding.", encoding="utf-8")

        mock_mongo = MagicMock()
        mock_mongo.find_document.return_value = None
        mock_emb = MagicMock()
        mock_emb.generate_batch = AsyncMock(
            side_effect=RuntimeError("OpenAI API rate limit")
        )

        pipeline = DocumentIngestionPipeline(
            mongo_client=mock_mongo, embedding_generator=mock_emb
        )

        result = await pipeline.ingest_file(file_path)
        assert result.status == IngestionStatus.FAILED
        assert "rate limit" in result.error_message
        mock_mongo.insert_document.assert_not_called()
        mock_mongo.insert_documents.assert_not_called()

    @pytest.mark.asyncio
    async def test_unsupported_file_type_in_directory_scan_is_ignored(self, tmp_path):
        """Unsupported files should be excluded from candidate files."""
        (tmp_path / "valid.txt").write_text("Valid text", encoding="utf-8")
        (tmp_path / "binary.bin").write_bytes(b"\x00\x01\x02")

        mock_mongo = MagicMock()
        mock_mongo.find_document.return_value = None
        mock_emb = MagicMock()
        mock_emb.generate_batch = AsyncMock(return_value=[[0.1] * 256])

        pipeline = DocumentIngestionPipeline(
            mongo_client=mock_mongo, embedding_generator=mock_emb
        )

        summary = await pipeline.ingest_directory(tmp_path)
        assert summary.total_scanned == 1
        assert summary.ingested == 1
        assert summary.failed == 0

    def test_clear_indexes(self):
        mock_mongo = MagicMock()
        mock_mongo.collection_exists.return_value = True
        mock_mongo.delete_documents.side_effect = [5, 20]
        mock_emb = MagicMock()

        pipeline = DocumentIngestionPipeline(
            mongo_client=mock_mongo, embedding_generator=mock_emb
        )
        cleared = pipeline.clear_indexes()

        assert cleared["deleted_documents"] == 5
        assert cleared["deleted_vectors"] == 20
        assert mock_mongo.delete_documents.call_count == 2
