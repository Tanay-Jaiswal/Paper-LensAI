# ============================================================
# preprocessing/text_cleaner.py
# Text Cleaning & Tokenization for Essay Scoring Pipeline
# ============================================================
# This module provides the TextCleaner class, which handles all
# text preprocessing tasks required before feature extraction:
#   - Lowercasing and whitespace normalization
#   - Removal of ASAP-specific annotation tags (@CAPS1, etc.)
#   - URL stripping
#   - SpaCy-based tokenization and sentence segmentation
#   - Bulk DataFrame cleaning
# ============================================================

import os
import sys
import re
import logging
from typing import List, Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Path setup — allow imports from the project root regardless of where
# this script is executed from.
# ---------------------------------------------------------------------------
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SpaCy lazy-loading helper
# ---------------------------------------------------------------------------
_nlp = None  # Module-level cache so the model is loaded only once


def _get_nlp():
    """
    Lazily load the spaCy English model.

    Uses ``en_core_web_sm`` by default. If the model is not installed,
    a clear error message is printed with installation instructions.

    Returns:
        spacy.Language: The loaded spaCy model.

    Raises:
        OSError: If the spaCy model cannot be found.
    """
    global _nlp
    if _nlp is not None:
        return _nlp

    try:
        import spacy

        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.error(
                "spaCy model 'en_core_web_sm' not found.\n"
                "Install it with:  python -m spacy download en_core_web_sm"
            )
            raise OSError(
                "spaCy model 'en_core_web_sm' is not installed. "
                "Run: python -m spacy download en_core_web_sm"
            )
    except ImportError:
        logger.error(
            "spaCy is not installed.\n"
            "Install it with:  pip install spacy"
        )
        raise ImportError(
            "spaCy is required for tokenization. "
            "Run: pip install spacy && python -m spacy download en_core_web_sm"
        )

    return _nlp


# ============================================================
# ASAP Tag Replacement Maps
# ============================================================
# The ASAP 2.0 dataset replaces certain entities with
# placeholder tags (e.g., @PERSON1, @CAPS1, @CITY1).
# We map each tag category to a generic English word so
# downstream NLP models see real vocabulary.
# ============================================================

_ASAP_TAG_REPLACEMENTS = {
    r"@PERSON\d*":       "person",
    r"@ORGANIZATION\d*": "organization",
    r"@LOCATION\d*":     "place",
    r"@DATE\d*":         "date",
    r"@TIME\d*":         "time",
    r"@MONEY\d*":        "money",
    r"@PERCENT\d*":      "percent",
    r"@MONTH\d*":        "month",
    r"@EMAIL\d*":        "email",
    r"@NUM\d*":          "number",
    r"@CAPS\d*":         "word",
    r"@DR\d*":           "doctor",
    r"@CITY\d*":         "city",
    r"@STATE\d*":        "state",
}

# Pre-compile URL pattern once
_URL_PATTERN = re.compile(
    r"http[s]?://(?:[a-zA-Z]|[0-9]|[$\-_@.&+]|[!*\\(\\),]|"
    r"(?:%[0-9a-fA-F][0-9a-fA-F]))+",
    re.IGNORECASE,
)


class TextCleaner:
    """
    Cleans and normalizes essay text for the scoring pipeline.

    Typical usage::

        cleaner = TextCleaner()
        cleaned = cleaner.clean(raw_essay_text)
        tokens  = cleaner.tokenize(cleaned)
        sents   = cleaner.get_sentences(cleaned)

    The class is intentionally stateless — every public method can be
    used independently without calling another method first.
    """

    # ----------------------------------------------------------------
    # Core cleaning
    # ----------------------------------------------------------------

    @staticmethod
    def clean(text: str) -> str:
        """
        Apply the full cleaning pipeline to a single essay string.

        Steps (in order):
            1. Strip leading / trailing whitespace.
            2. Replace ASAP annotation tags with generic words.
            3. Remove URLs.
            4. Lowercase the entire text.
            5. Collapse excessive whitespace (tabs, multiple spaces,
               multiple newlines) into single spaces, preserving
               sentence-ending punctuation.

        Args:
            text: Raw essay text.

        Returns:
            Cleaned essay string ready for feature extraction.
        """
        if not isinstance(text, str) or not text.strip():
            return ""

        # Step 1 — basic strip
        text = text.strip()

        # Step 2 — replace ASAP-specific annotation tags
        for pattern, replacement in _ASAP_TAG_REPLACEMENTS.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # Step 3 — remove URLs
        text = _URL_PATTERN.sub("", text)

        # Step 4 — lowercase
        text = text.lower()

        # Step 5 — collapse whitespace (preserves punctuation)
        text = re.sub(r"\s+", " ", text).strip()

        return text

    # ----------------------------------------------------------------
    # Tokenization
    # ----------------------------------------------------------------

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """
        Tokenize *text* using spaCy's tokenizer.

        Non-whitespace tokens are returned as a flat list of strings.
        Whitespace-only tokens (newlines, tabs) are dropped.

        Args:
            text: Cleaned (or raw) essay text.

        Returns:
            List of token strings.
        """
        if not isinstance(text, str) or not text.strip():
            return []

        nlp = _get_nlp()
        doc = nlp(text)
        return [token.text for token in doc if not token.is_space]

    # ----------------------------------------------------------------
    # Sentence segmentation
    # ----------------------------------------------------------------

    @staticmethod
    def get_sentences(text: str) -> List[str]:
        """
        Split *text* into sentences using spaCy's sentence boundary
        detector.

        Args:
            text: Cleaned (or raw) essay text.

        Returns:
            List of sentence strings.
        """
        if not isinstance(text, str) or not text.strip():
            return []

        nlp = _get_nlp()
        doc = nlp(text)
        return [sent.text.strip() for sent in doc.sents if sent.text.strip()]

    # ----------------------------------------------------------------
    # Bulk DataFrame cleaning
    # ----------------------------------------------------------------

    @classmethod
    def clean_dataframe(
        cls,
        df: pd.DataFrame,
        text_column: str = "essay",
    ) -> pd.DataFrame:
        """
        Clean every value in *text_column* of a DataFrame in-place.

        A new column ``cleaned_essay`` is added; the original column
        is left unchanged so users can compare raw vs. cleaned text.

        Args:
            df:          DataFrame containing essay texts.
            text_column: Name of the column to clean (default ``"essay"``).

        Returns:
            The same DataFrame with the additional ``cleaned_essay`` column.

        Raises:
            KeyError: If *text_column* is not present in the DataFrame.
        """
        if text_column not in df.columns:
            raise KeyError(
                f"Column '{text_column}' not found in DataFrame. "
                f"Available columns: {list(df.columns)}"
            )

        cleaner = cls()
        logger.info(
            "Cleaning %d essays in column '%s' ...", len(df), text_column
        )
        df["cleaned_essay"] = df[text_column].astype(str).apply(cleaner.clean)
        logger.info("Cleaning complete — added 'cleaned_essay' column.")
        return df


# ============================================================
# Quick smoke-test when run directly
# ============================================================
if __name__ == "__main__":
    sample = (
        "  @PERSON1 went to @CITY2 on @DATE1.  Check http://example.com  "
        "for MORE info.   @CAPS1 @CAPS2 are common tags.\n\n"
        "This is a second    paragraph with   extra   spaces!  "
    )

    cleaner = TextCleaner()

    print("=" * 60)
    print("RAW TEXT:")
    print(repr(sample))

    cleaned = cleaner.clean(sample)
    print("\nCLEANED TEXT:")
    print(repr(cleaned))

    tokens = cleaner.tokenize(cleaned)
    print(f"\nTOKENS ({len(tokens)}):")
    print(tokens)

    sentences = cleaner.get_sentences(cleaned)
    print(f"\nSENTENCES ({len(sentences)}):")
    for i, s in enumerate(sentences, 1):
        print(f"  {i}. {s}")

    # DataFrame demo
    demo_df = pd.DataFrame(
        {
            "essay_id": [1, 2],
            "essay": [
                "@PERSON1 said @CAPS1 loudly.",
                "Visit http://test.org now! @ORGANIZATION1 is great.",
            ],
        }
    )
    cleaned_df = TextCleaner.clean_dataframe(demo_df, "essay")
    print("\nDATAFRAME CLEANING:")
    print(cleaned_df[["essay", "cleaned_essay"]].to_string(index=False))
    print("=" * 60)
