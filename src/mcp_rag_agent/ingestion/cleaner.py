"""Text sanitization and cleaning for document ingestion."""

import re
import unicodedata


class DocumentCleaner:
    """Sanitizes and normalizes extracted text from documents."""

    # Matches control characters except tab (\t), newline (\n), and carriage return (\r)
    _CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

    # Matches 3 or more consecutive newlines
    _MULTI_NEWLINE_RE = re.compile(r"\n{3,}")

    # Matches consecutive spaces and tabs (not newlines)
    _MULTI_SPACE_RE = re.compile(r"[^\S\n]+")

    def clean(self, text: str) -> str:
        """Clean and normalize a text string.

        Args:
            text: Raw input string from document parser.

        Returns:
            Sanitized, normalized string.
        """
        if not text:
            return ""

        # 1. Strip null bytes and harmful control characters
        cleaned = self._CONTROL_CHAR_RE.sub("", text)

        # 2. Normalize Unicode (NFKC handles compatibility decomposition/composition)
        cleaned = unicodedata.normalize("NFKC", cleaned)

        # 3. Normalize line breaks to standard Unix \n
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")

        # 4. Strip trailing whitespace from each line and collapse redundant horizontal spaces
        lines = [
            self._MULTI_SPACE_RE.sub(" ", line).strip() for line in cleaned.split("\n")
        ]
        cleaned = "\n".join(lines)

        # 5. Collapse 3+ consecutive newlines down to 2 (preserving paragraph breaks)
        cleaned = self._MULTI_NEWLINE_RE.sub("\n\n", cleaned)

        # 6. Final strip of leading/trailing whitespace
        return cleaned.strip()
