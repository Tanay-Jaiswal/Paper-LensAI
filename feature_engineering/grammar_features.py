# ============================================================
# feature_engineering/grammar_features.py
# Grammar & Spelling Error Analysis for Essay Scoring
# ============================================================
# This module provides the GrammarAnalyzer class which detects
# grammar and spelling errors in essay text.
#
# Primary backend:  language_tool_python  (wraps LanguageTool)
# Fallback backend: spaCy + regex-based heuristics
#
# The fallback activates automatically when language_tool_python
# is not installed or when Java (required by LanguageTool) is
# unavailable.
# ============================================================

import os
import sys
import re
import logging
from collections import Counter
from typing import Dict, List, Any, Optional

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Common misspellings for fallback checker
# ---------------------------------------------------------------------------
_COMMON_MISSPELLINGS: Dict[str, str] = {
    "teh": "the", "recieve": "receive", "occured": "occurred",
    "seperate": "separate", "definately": "definitely",
    "goverment": "government", "enviroment": "environment",
    "untill": "until", "wich": "which", "becuase": "because",
    "thier": "their", "freind": "friend", "wierd": "weird",
    "beleive": "believe", "accomodate": "accommodate",
    "occurence": "occurrence", "arguement": "argument",
    "independant": "independent", "noticable": "noticeable",
    "refered": "referred", "succesful": "successful",
    "realy": "really", "alot": "a lot", "writting": "writing",
    "beggining": "beginning", "comming": "coming",
    "happenning": "happening", "grammer": "grammar",
    "concious": "conscious", "existance": "existence",
    "knowlege": "knowledge", "neccessary": "necessary",
    "posession": "possession", "privelege": "privilege",
    "publically": "publicly", "tommorrow": "tomorrow",
    "sincerly": "sincerely", "truely": "truly",
    "adress": "address", "buisness": "business",
}


class GrammarAnalyzer:
    """
    Detects grammar and spelling errors in essay text.

    On initialisation the class tries to load ``language_tool_python``.
    If that fails (missing package *or* missing Java runtime) a lighter
    rule-based fallback is used instead.

    Public API::

        analyzer = GrammarAnalyzer()
        results  = analyzer.analyze(essay_text)
        details  = analyzer.get_error_details(essay_text)

    Attributes:
        _tool:       LanguageTool instance or ``None`` (fallback mode).
        _use_lt:     ``True`` if LanguageTool is available.
        _nlp:        Cached spaCy model for fallback mode.
    """

    def __init__(self) -> None:
        """
        Initialise the grammar checker.

        Tries ``language_tool_python`` → falls back to spaCy + regex.
        All errors during initialisation are caught and logged so that
        the class always constructs successfully.
        """
        self._tool = None
        self._use_lt: bool = False
        self._nlp = None  # Lazy-loaded for fallback

        try:
            import language_tool_python
            self._tool = language_tool_python.LanguageTool("en-US")
            self._use_lt = True
            logger.info("GrammarAnalyzer: using LanguageTool backend.")
        except ImportError:
            logger.warning(
                "language_tool_python not installed — "
                "falling back to spaCy-based grammar checks.\n"
                "Install with: pip install language-tool-python"
            )
        except Exception as exc:
            # LanguageTool requires Java; catch any Java-related errors
            logger.warning(
                "LanguageTool initialisation failed (%s: %s) — "
                "using spaCy fallback.  Ensure Java is installed if you "
                "want full grammar checking.",
                type(exc).__name__, exc,
            )

    # ----------------------------------------------------------------
    # Lazy spaCy loader (only needed in fallback mode)
    # ----------------------------------------------------------------

    def _get_nlp(self):
        """Return a cached spaCy model, loading it on first call."""
        if self._nlp is not None:
            return self._nlp

        try:
            import spacy
            try:
                self._nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.error(
                    "spaCy model 'en_core_web_sm' not found. "
                    "Run: python -m spacy download en_core_web_sm"
                )
                raise
        except ImportError:
            raise ImportError(
                "spaCy is required for the fallback grammar checker. "
                "Run: pip install spacy && python -m spacy download en_core_web_sm"
            )
        return self._nlp

    # ================================================================
    # Public: analyze
    # ================================================================

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Analyse *text* for grammar and spelling errors.

        Args:
            text: Raw or cleaned essay text.

        Returns:
            Dictionary with the following keys:

            - ``grammar_error_count`` (int): Number of grammar errors.
            - ``spelling_error_count`` (int): Number of spelling errors.
            - ``error_rate`` (float): Total errors / word count.
            - ``common_error_types`` (dict): Counter of error categories.
            - ``grammar_score`` (float): Quality score in [0, 1] where
              1.0 means no errors detected.
        """
        if not isinstance(text, str) or not text.strip():
            return {
                "grammar_error_count": 0,
                "spelling_error_count": 0,
                "error_rate": 0.0,
                "common_error_types": {},
                "grammar_score": 1.0,
            }

        word_count = max(len(text.split()), 1)

        if self._use_lt:
            return self._analyze_with_lt(text, word_count)
        else:
            return self._analyze_with_fallback(text, word_count)

    # ================================================================
    # Public: get_error_details
    # ================================================================

    def get_error_details(self, text: str) -> List[Dict[str, str]]:
        """
        Return a list of individual error details.

        Each element is a dict with:
            - ``message``: Human-readable error explanation.
            - ``category``: Error category / rule id.
            - ``context``: The text surrounding the error.

        Args:
            text: Essay text.

        Returns:
            List of error-detail dictionaries (may be empty).
        """
        if not isinstance(text, str) or not text.strip():
            return []

        if self._use_lt:
            return self._get_lt_error_details(text)
        else:
            return self._get_fallback_error_details(text)

    # ================================================================
    # LanguageTool backend
    # ================================================================

    def _analyze_with_lt(
        self, text: str, word_count: int
    ) -> Dict[str, Any]:
        """Run analysis using language_tool_python."""
        matches = self._tool.check(text)

        grammar_errors = 0
        spelling_errors = 0
        error_types: Counter = Counter()

        for match in matches:
            category = getattr(match, 'rule_id', getattr(match, 'ruleId', 'UNKNOWN'))
            error_types[category] += 1

            # LanguageTool categorises misspellings under MORFOLOGIK_*
            if "MORFOLOGIK" in category or "SPELLER" in category.upper():
                spelling_errors += 1
            else:
                grammar_errors += 1

        total_errors = grammar_errors + spelling_errors
        error_rate = total_errors / word_count

        # Grammar score: 1.0 = perfect, decays towards 0 as errors grow
        grammar_score = max(0.0, 1.0 - error_rate)

        return {
            "grammar_error_count": grammar_errors,
            "spelling_error_count": spelling_errors,
            "error_rate": round(error_rate, 4),
            "common_error_types": dict(error_types.most_common(10)),
            "grammar_score": round(grammar_score, 4),
        }

    def _get_lt_error_details(self, text: str) -> List[Dict[str, str]]:
        """Get per-error details from LanguageTool."""
        matches = self._tool.check(text)
        details = []
        for match in matches:
            details.append(
                {
                    "message": match.message,
                    "category": getattr(match, 'rule_id', getattr(match, 'ruleId', 'UNKNOWN')),
                    "context": match.context or "",
                }
            )
        return details

    # ================================================================
    # Fallback backend (spaCy + regex heuristics)
    # ================================================================

    def _fallback_grammar_check(self, text: str) -> List[Dict[str, str]]:
        """
        Simple rule-based grammar & spelling checks using regex and
        spaCy.  Detects:

        1. **Repeated words** — e.g. "the the"
        2. **Missing capitalisation** after sentence-ending punctuation.
        3. **Common misspellings** from a curated dictionary.
        4. **Missing period at end** of text.
        5. **Double punctuation** — e.g. ".."
        """
        errors: List[Dict[str, str]] = []

        # 1.  Repeated words -------------------------------------------
        repeated = re.findall(r"\b(\w+)\s+\1\b", text, re.IGNORECASE)
        for word in repeated:
            errors.append(
                {
                    "message": f"Repeated word: '{word}'",
                    "category": "REPEATED_WORD",
                    "context": word,
                }
            )

        # 2.  Missing capitalisation after sentence-ending punctuation -
        missing_caps = re.findall(r"[.!?]\s+[a-z]", text)
        for match_text in missing_caps:
            errors.append(
                {
                    "message": "Sentence should start with a capital letter.",
                    "category": "CAPITALIZATION",
                    "context": match_text.strip(),
                }
            )

        # Check first character capitalisation
        stripped = text.strip()
        if stripped and stripped[0].islower():
            errors.append(
                {
                    "message": "Text should start with a capital letter.",
                    "category": "CAPITALIZATION",
                    "context": stripped[:20],
                }
            )

        # 3.  Common misspellings --------------------------------------
        words_lower = re.findall(r"\b[a-z]+\b", text.lower())
        for word in words_lower:
            if word in _COMMON_MISSPELLINGS:
                errors.append(
                    {
                        "message": (
                            f"Possible misspelling: '{word}' → "
                            f"'{_COMMON_MISSPELLINGS[word]}'"
                        ),
                        "category": "SPELLING",
                        "context": word,
                    }
                )

        # 4.  Missing period at end ------------------------------------
        if stripped and stripped[-1] not in ".!?\"'":
            errors.append(
                {
                    "message": "Text may be missing ending punctuation.",
                    "category": "PUNCTUATION",
                    "context": stripped[-30:],
                }
            )

        # 5.  Double punctuation (excluding ellipsis "...") ------------
        double_punct = re.findall(r"([.!?,;:]){2}", text)
        for p in double_punct:
            # Allow "..." (ellipsis)
            if p == "." and "..." in text:
                continue
            errors.append(
                {
                    "message": f"Double punctuation detected: '{p}{p}'",
                    "category": "PUNCTUATION",
                    "context": p * 2,
                }
            )

        return errors

    def _analyze_with_fallback(
        self, text: str, word_count: int
    ) -> Dict[str, Any]:
        """Run analysis using the spaCy + regex fallback."""
        errors = self._fallback_grammar_check(text)

        grammar_errors = 0
        spelling_errors = 0
        error_types: Counter = Counter()

        for err in errors:
            category = err["category"]
            error_types[category] += 1
            if category == "SPELLING":
                spelling_errors += 1
            else:
                grammar_errors += 1

        total_errors = grammar_errors + spelling_errors
        error_rate = total_errors / word_count
        grammar_score = max(0.0, 1.0 - error_rate)

        return {
            "grammar_error_count": grammar_errors,
            "spelling_error_count": spelling_errors,
            "error_rate": round(error_rate, 4),
            "common_error_types": dict(error_types.most_common(10)),
            "grammar_score": round(grammar_score, 4),
        }

    def _get_fallback_error_details(self, text: str) -> List[Dict[str, str]]:
        """Return per-error details from the fallback checker."""
        return self._fallback_grammar_check(text)


# ============================================================
# Quick smoke-test when run directly
# ============================================================
if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    analyzer = GrammarAnalyzer()

    test_texts = [
        # Good text
        "The quick brown fox jumps over the lazy dog. It was a sunny day.",
        # Repeated word + misspelling + missing caps
        "I went to the the store becuase I needed milk. she forgot her bag.",
        # Multiple errors
        "teh goverment should definately seperate the the departments.. "
        "this is important for the enviroment",
    ]

    for i, txt in enumerate(test_texts, 1):
        print("=" * 60)
        print(f"TEXT {i}: {txt[:80]}...")
        results = analyzer.analyze(txt)
        print(json.dumps(results, indent=2))

        details = analyzer.get_error_details(txt)
        if details:
            print(f"\n  Error details ({len(details)}):")
            for d in details:
                print(f"    [{d['category']}] {d['message']}")
        print()
