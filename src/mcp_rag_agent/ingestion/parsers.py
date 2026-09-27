"""Document parsers for TXT, Markdown, PDF, and DOCX formats."""

import logging
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from mcp_rag_agent.ingestion.models import DocumentSegment, ParsedDocument

logger = logging.getLogger("DocumentParsers")


class IngestionError(Exception):
    """Base exception for ingestion errors."""

    pass


class UnsupportedFileTypeError(IngestionError):
    """Raised when an unsupported file extension is encountered."""

    pass


class ParsingError(IngestionError):
    """Raised when parsing fails due to corruption, encryption, or format issues."""

    pass


class BaseDocumentParser(ABC):
    """Abstract base class for format-specific document parsers."""

    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """Return the set of supported file extensions (lowercase, with dot)."""
        pass

    def can_handle(self, file_path: Path) -> bool:
        """Check if this parser can handle the given file."""
        return file_path.suffix.lower() in self.supported_extensions()

    @abstractmethod
    def parse(
        self, file_path: Path, document_id: str, content_hash: str
    ) -> ParsedDocument:
        """Parse file content and return structured ParsedDocument.

        Args:
            file_path: Path to the target file.
            document_id: Unique identifier for the document.
            content_hash: SHA-256 hash of the document bytes.

        Returns:
            ParsedDocument containing metadata and extracted segments.
        """
        pass

    @staticmethod
    def _clean_title_from_filename(file_path: Path) -> str:
        """Derive a readable default title from the file stem."""
        return file_path.stem.replace("_", " ").replace("-", " ").strip().title()


class TextParser(BaseDocumentParser):
    """Parser for plain text (.txt) files."""

    def supported_extensions(self) -> set[str]:
        return {".txt"}

    def parse(
        self, file_path: Path, document_id: str, content_hash: str
    ) -> ParsedDocument:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_text = f.read()
        except UnicodeDecodeError:
            logger.warning(
                f"UTF-8 decode failed for {file_path.name}; falling back with replacement characters"
            )
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                raw_text = f.read()
        except Exception as e:
            raise ParsingError(f"Failed to read text file {file_path.name}: {e}") from e

        # Extract title from first non-empty line if short, else file stem
        title = self._clean_title_from_filename(file_path)
        for line in raw_text.splitlines():
            line_str = line.strip()
            if line_str and len(line_str) <= 100:
                title = line_str
                break

        segment = DocumentSegment(
            text=raw_text, section=None, page_number=None, segment_index=0
        )

        return ParsedDocument(
            document_id=document_id,
            filename=file_path.name,
            file_type="txt",
            source_path=str(file_path.resolve()),
            title=title,
            content_hash=content_hash,
            segments=[segment],
            raw_text=raw_text,
        )


class MarkdownParser(BaseDocumentParser):
    """Parser for Markdown (.md, .markdown) files with heading awareness."""

    _HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    _FRONTMATTER_TITLE_RE = re.compile(
        r"^title:\s*[\"']?([^\"'\n]+)[\"']?", re.MULTILINE | re.IGNORECASE
    )

    def supported_extensions(self) -> set[str]:
        return {".md", ".markdown"}

    def parse(
        self, file_path: Path, document_id: str, content_hash: str
    ) -> ParsedDocument:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                raw_text = f.read()
        except Exception as e:
            raise ParsingError(
                f"Failed to read markdown file {file_path.name}: {e}"
            ) from e

        # Extract title from frontmatter or top # Header
        title = self._clean_title_from_filename(file_path)
        frontmatter_match = self._FRONTMATTER_TITLE_RE.search(raw_text)
        if frontmatter_match:
            title = frontmatter_match.group(1).strip()
        else:
            first_h1 = re.search(r"^#\s+(.+)$", raw_text, re.MULTILINE)
            if first_h1:
                title = first_h1.group(1).strip()

        # Split into segments by headings to preserve section metadata
        segments: list[DocumentSegment] = []
        lines = raw_text.splitlines(keepends=True)
        current_section: Optional[str] = None
        current_lines: list[str] = []
        segment_index = 0

        for line in lines:
            heading_match = self._HEADING_RE.match(line.rstrip())
            if heading_match:
                # Flush existing segment
                if current_lines:
                    seg_text = "".join(current_lines).strip()
                    if seg_text:
                        segments.append(
                            DocumentSegment(
                                text=seg_text,
                                section=current_section,
                                page_number=None,
                                segment_index=segment_index,
                            )
                        )
                        segment_index += 1
                    current_lines = []
                current_section = heading_match.group(2).strip()
            current_lines.append(line)

        # Flush final segment
        if current_lines:
            seg_text = "".join(current_lines).strip()
            if seg_text:
                segments.append(
                    DocumentSegment(
                        text=seg_text,
                        section=current_section,
                        page_number=None,
                        segment_index=segment_index,
                    )
                )

        if not segments:
            segments.append(
                DocumentSegment(
                    text=raw_text, section=None, page_number=None, segment_index=0
                )
            )

        return ParsedDocument(
            document_id=document_id,
            filename=file_path.name,
            file_type="md",
            source_path=str(file_path.resolve()),
            title=title,
            content_hash=content_hash,
            segments=segments,
            raw_text=raw_text,
        )


class PDFParser(BaseDocumentParser):
    """Parser for PDF (.pdf) documents with page number tracking."""

    def supported_extensions(self) -> set[str]:
        return {".pdf"}

    def parse(
        self, file_path: Path, document_id: str, content_hash: str
    ) -> ParsedDocument:
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise IngestionError(
                "pypdf is required for PDF parsing. Please install pypdf."
            ) from e

        try:
            reader = PdfReader(str(file_path))
        except Exception as e:
            raise ParsingError(
                f"Corrupted or invalid PDF file {file_path.name}: {e}"
            ) from e

        if reader.is_encrypted:
            try:
                # Try decrypting with empty password
                reader.decrypt("")
            except Exception as e:
                raise ParsingError(
                    f"PDF file is password-protected and cannot be decrypted: {file_path.name}"
                ) from e

        title = self._clean_title_from_filename(file_path)
        if reader.metadata and reader.metadata.title:
            doc_title = str(reader.metadata.title).strip()
            if doc_title:
                title = doc_title

        segments: list[DocumentSegment] = []
        raw_parts: list[str] = []
        segment_index = 0

        for page_idx, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text() or ""
            except Exception as e:
                logger.warning(
                    f"Error extracting text from page {page_idx + 1} of {file_path.name}: {e}"
                )
                page_text = ""

            page_number = page_idx + 1
            if page_text.strip():
                segments.append(
                    DocumentSegment(
                        text=page_text,
                        section=f"Page {page_number}",
                        page_number=page_number,
                        segment_index=segment_index,
                    )
                )
                raw_parts.append(page_text)
                segment_index += 1

        raw_text = "\n\n".join(raw_parts)

        return ParsedDocument(
            document_id=document_id,
            filename=file_path.name,
            file_type="pdf",
            source_path=str(file_path.resolve()),
            title=title,
            content_hash=content_hash,
            segments=segments,
            raw_text=raw_text,
        )


class DocxParser(BaseDocumentParser):
    """Parser for Microsoft Word (.docx) documents with heading & paragraph awareness."""

    def supported_extensions(self) -> set[str]:
        return {".docx"}

    def parse(
        self, file_path: Path, document_id: str, content_hash: str
    ) -> ParsedDocument:
        try:
            from docx import Document
        except ImportError as e:
            raise IngestionError(
                "python-docx is required for DOCX parsing. Please install python-docx."
            ) from e

        try:
            doc = Document(str(file_path))
        except Exception as e:
            raise ParsingError(
                f"Corrupted or invalid DOCX file {file_path.name}: {e}"
            ) from e

        title = self._clean_title_from_filename(file_path)
        segments: list[DocumentSegment] = []
        current_section: Optional[str] = None
        current_lines: list[str] = []
        segment_index = 0

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            style_name = para.style.name if para.style else ""
            if "Title" in style_name and title == self._clean_title_from_filename(
                file_path
            ):
                title = text

            if "Heading" in style_name:
                # Flush previous segment
                if current_lines:
                    seg_text = "\n".join(current_lines).strip()
                    if seg_text:
                        segments.append(
                            DocumentSegment(
                                text=seg_text,
                                section=current_section,
                                page_number=None,
                                segment_index=segment_index,
                            )
                        )
                        segment_index += 1
                    current_lines = []
                current_section = text
            else:
                current_lines.append(text)

        # Extract text from tables if any
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(
                    cell.text.strip() for cell in row.cells if cell.text.strip()
                )
                if row_text:
                    current_lines.append(row_text)

        # Flush final segment
        if current_lines:
            seg_text = "\n".join(current_lines).strip()
            if seg_text:
                segments.append(
                    DocumentSegment(
                        text=seg_text,
                        section=current_section,
                        page_number=None,
                        segment_index=segment_index,
                    )
                )

        raw_text = "\n\n".join(seg.text for seg in segments)

        return ParsedDocument(
            document_id=document_id,
            filename=file_path.name,
            file_type="docx",
            source_path=str(file_path.resolve()),
            title=title,
            content_hash=content_hash,
            segments=segments,
            raw_text=raw_text,
        )


class ParserRegistry:
    """Registry managing available document parsers."""

    def __init__(self):
        self._parsers: list[BaseDocumentParser] = [
            TextParser(),
            MarkdownParser(),
            PDFParser(),
            DocxParser(),
        ]

    def register_parser(self, parser: BaseDocumentParser) -> None:
        """Register a custom document parser."""
        self._parsers.insert(0, parser)

    def get_parser(self, file_path: Path | str) -> BaseDocumentParser:
        """Get the appropriate parser for a given file path.

        Args:
            file_path: File path to find parser for.

        Returns:
            Matching BaseDocumentParser instance.

        Raises:
            UnsupportedFileTypeError: If no registered parser supports the file extension.
        """
        path = Path(file_path)
        for parser in self._parsers:
            if parser.can_handle(path):
                return parser
        supported = {ext for p in self._parsers for ext in p.supported_extensions()}
        raise UnsupportedFileTypeError(
            f"Unsupported file format '{path.suffix}' for '{path.name}'. Supported formats: {sorted(supported)}"
        )

    def is_supported(self, file_path: Path | str) -> bool:
        """Check if a file format is supported."""
        path = Path(file_path)
        return any(p.can_handle(path) for p in self._parsers)


# Global default registry instance
default_parser_registry = ParserRegistry()


def get_parser(file_path: Path | str) -> BaseDocumentParser:
    """Convenience function to get a parser from the default registry."""
    return default_parser_registry.get_parser(file_path)
