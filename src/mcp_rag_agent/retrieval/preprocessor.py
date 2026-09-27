"""Query preprocessing and normalization for hybrid retrieval."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional


@dataclass
class PreprocessedQuery:
    """Preprocessed query variants optimized for different search modalities."""

    raw_query: str
    normalized_query: str
    semantic_query: str
    keyword_query: str
    tokens: list[str]


class QueryPreprocessor:
    """Normalizes and prepares user queries for semantic vector search and keyword text search."""

    # Matches control characters
    _CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

    # Matches consecutive whitespace
    _WHITESPACE_RE = re.compile(r"\s+")

    # Smart quote normalization mapping
    _QUOTE_TRANSLATION = str.maketrans(
        {
            "“": '"',
            "”": '"',
            "„": '"',
            "«": '"',
            "»": '"',
            "‘": "'",
            "’": "'",
            "‚": "'",
            "‛": "'",
        }
    )

    def normalize(self, query: str) -> str:
        """Apply core normalization: Unicode NFKC, control-char removal, and space compaction.

        Args:
            query: Raw query string.

        Returns:
            Normalized query string.
        """
        if not query:
            return ""

        # 1. Unicode NFKC normalization
        normalized = unicodedata.normalize("NFKC", query)

        # 2. Normalize smart quotes to standard ASCII quotes
        normalized = normalized.translate(self._QUOTE_TRANSLATION)

        # 3. Strip control characters
        normalized = self._CONTROL_CHAR_RE.sub("", normalized)

        # 4. Collapse whitespace
        normalized = self._WHITESPACE_RE.sub(" ", normalized).strip()

        return normalized

    def build_keyword_query(self, query: str) -> str:
        """Sanitize query for MongoDB text search ($text operator).

        Handles unbalanced quotes, safely escapes syntax characters, and prevents
        unintentional negation operators (e.g. leading hyphens).

        Args:
            query: Normalized query string.

        Returns:
            Sanitized query string safe for full-text search.
        """
        if not query:
            return ""

        # Fix unbalanced double quotes: if count of quotes is odd, remove them
        if query.count('"') % 2 != 0:
            cleaned = query.replace('"', "")
        else:
            cleaned = query

        # Prevent leading hyphens from acting as MongoDB exclusion operators
        words = cleaned.split()
        safe_words = [
            w.lstrip("-") if w.startswith("-") and len(w) > 1 else w for w in words
        ]
        safe_query = " ".join(w for w in safe_words if w)

        return safe_query or query

    def preprocess(self, query: str) -> PreprocessedQuery:
        """Preprocess a raw query into normalized, semantic, and keyword representations.

        Args:
            query: User's raw query string.

        Returns:
            PreprocessedQuery instance containing specialized query variants.
        """
        norm_query = self.normalize(query)
        kw_query = self.build_keyword_query(norm_query)

        # Tokenize (lowercased alphanumeric tokens)
        tokens = re.findall(r"\b\w+\b", norm_query.lower())

        return PreprocessedQuery(
            raw_query=query,
            normalized_query=norm_query,
            semantic_query=norm_query,
            keyword_query=kw_query,
            tokens=tokens,
        )
