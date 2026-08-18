# ============================================================
# feature_engineering/linguistic_features.py
# Linguistic Feature Extraction for Essay Scoring
# ============================================================
# Extracts ~25 hand-crafted linguistic features from essay text:
#
#   Surface-level:  word_count, sentence_count, paragraph_count,
#                   avg_word_length, avg_sentence_length
#   Lexical:        type_token_ratio, hapax_legomena_ratio,
#                   lexical_diversity_mtld
#   Syntactic:      noun/verb/adj/adv ratios  (POS tags)
#   Entity:         named_entity_count
#   Punctuation:    density, comma_rate, semicolon/exclamation/
#                   question counts
#   Vocabulary:     stopword_ratio, long_word_ratio,
#                   vocabulary_richness_score (composite)
#
# Uses spaCy for POS tagging, NER, and tokenisation.  NLTK is
# available as an optional fallback tokeniser.
# ============================================================

import os
import sys
import re
import math
import logging
from collections import Counter
from typing import Dict, Any, List, Optional

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
# spaCy lazy-loader
# ---------------------------------------------------------------------------
_nlp = None


def _get_nlp():
    """
    Lazily load the spaCy ``en_core_web_sm`` model.

    Returns:
        spacy.Language

    Raises:
        OSError / ImportError with installation instructions.
    """
    global _nlp
    if _nlp is not None:
        return _nlp

    try:
        import spacy
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            raise OSError(
                "spaCy model 'en_core_web_sm' not installed.  "
                "Run: python -m spacy download en_core_web_sm"
            )
    except ImportError:
        raise ImportError(
            "spaCy is required.  Run: pip install spacy && "
            "python -m spacy download en_core_web_sm"
        )
    return _nlp


# ---------------------------------------------------------------------------
# NLTK stopwords (lazy)
# ---------------------------------------------------------------------------
_STOPWORDS: Optional[set] = None


def _get_stopwords() -> set:
    """Return a set of English stopwords (NLTK or built-in fallback)."""
    global _STOPWORDS
    if _STOPWORDS is not None:
        return _STOPWORDS

    try:
        import nltk
        try:
            from nltk.corpus import stopwords as sw
            _STOPWORDS = set(sw.words("english"))
        except LookupError:
            # Download quietly if missing
            nltk.download("stopwords", quiet=True)
            from nltk.corpus import stopwords as sw
            _STOPWORDS = set(sw.words("english"))
    except ImportError:
        logger.warning(
            "nltk not installed — using built-in stopword list."
        )
        # Minimal fallback list
        _STOPWORDS = {
            "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
            "you", "your", "yours", "yourself", "yourselves", "he", "him",
            "his", "himself", "she", "her", "hers", "herself", "it", "its",
            "itself", "they", "them", "their", "theirs", "themselves",
            "what", "which", "who", "whom", "this", "that", "these",
            "those", "am", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "having", "do", "does", "did",
            "doing", "a", "an", "the", "and", "but", "if", "or", "because",
            "as", "until", "while", "of", "at", "by", "for", "with",
            "about", "against", "between", "through", "during", "before",
            "after", "above", "below", "to", "from", "up", "down", "in",
            "out", "on", "off", "over", "under", "again", "further",
            "then", "once", "here", "there", "when", "where", "why",
            "how", "all", "both", "each", "few", "more", "most", "other",
            "some", "such", "no", "nor", "not", "only", "own", "same",
            "so", "than", "too", "very", "s", "t", "can", "will", "just",
            "don", "should", "now",
        }

    return _STOPWORDS


class LinguisticAnalyzer:
    """
    Extract ~25 linguistic features from essay text.

    Example::

        analyzer = LinguisticAnalyzer()
        features = analyzer.analyze(essay_text)
        # features is a dict with ~25 float/int values
    """

    # ================================================================
    # Public: analyze
    # ================================================================

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Extract all linguistic features from *text*.

        Args:
            text: Essay text (cleaned or raw).

        Returns:
            Dictionary with ~25 features.  All values are numeric
            (``int`` or ``float``).
        """
        # --- Edge case: empty / trivial text ---
        if not isinstance(text, str) or not text.strip():
            return self._empty_features()

        nlp = _get_nlp()
        doc = nlp(text)

        # ---- Tokens (non-whitespace, non-empty) ----
        tokens = [t for t in doc if not t.is_space]
        word_tokens = [t for t in tokens if t.is_alpha]
        words_lower = [t.text.lower() for t in word_tokens]

        word_count = len(word_tokens)

        # Edge case: single word or no real words
        if word_count == 0:
            return self._empty_features()

        # ---- Sentences ----
        sentences = list(doc.sents)
        sentence_count = max(len(sentences), 1)

        # ---- Paragraphs (split on double newline or significant gap) ----
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        paragraph_count = max(len(paragraphs), 1)

        # ================================================================
        # Surface-level features
        # ================================================================
        avg_word_length = (
            sum(len(w) for w in words_lower) / word_count
        )
        avg_sentence_length = word_count / sentence_count

        # ================================================================
        # Lexical diversity features
        # ================================================================
        unique_words = set(words_lower)
        unique_count = len(unique_words)

        type_token_ratio = unique_count / word_count

        # Hapax legomena — words that appear exactly once
        word_freq = Counter(words_lower)
        hapax_count = sum(1 for freq in word_freq.values() if freq == 1)
        hapax_legomena_ratio = (
            hapax_count / unique_count if unique_count > 0 else 0.0
        )

        # MTLD (Measure of Textual Lexical Diversity)
        lexical_diversity_mtld = self._compute_mtld(words_lower)

        # ================================================================
        # POS tag ratios
        # ================================================================
        pos_counts: Counter = Counter()
        for token in word_tokens:
            pos_counts[token.pos_] += 1

        noun_ratio = (
            (pos_counts.get("NOUN", 0) + pos_counts.get("PROPN", 0))
            / word_count
        )
        verb_ratio = (
            (pos_counts.get("VERB", 0) + pos_counts.get("AUX", 0))
            / word_count
        )
        adj_ratio = pos_counts.get("ADJ", 0) / word_count
        adv_ratio = pos_counts.get("ADV", 0) / word_count

        # ================================================================
        # Named entities
        # ================================================================
        named_entity_count = len(doc.ents)

        # ================================================================
        # Punctuation features
        # ================================================================
        punct_tokens = [t for t in tokens if t.is_punct]
        punctuation_density = len(punct_tokens) / sentence_count

        # Specific punctuation counts
        comma_rate = sum(1 for t in punct_tokens if t.text == ",") / sentence_count
        semicolon_count = sum(1 for t in punct_tokens if t.text == ";")
        exclamation_count = sum(1 for t in punct_tokens if t.text == "!")
        question_mark_count = sum(1 for t in punct_tokens if t.text == "?")

        # ================================================================
        # Vocabulary features
        # ================================================================
        stopwords = _get_stopwords()
        stopword_count = sum(1 for w in words_lower if w in stopwords)
        stopword_ratio = stopword_count / word_count

        long_word_count = sum(1 for w in words_lower if len(w) > 6)
        long_word_ratio = long_word_count / word_count

        # ================================================================
        # Composite vocabulary richness score (0-1)
        # ================================================================
        # Weighted combination of TTR, hapax ratio, and MTLD
        vocabulary_richness_score = self._compute_vocabulary_richness(
            type_token_ratio, hapax_legomena_ratio, lexical_diversity_mtld
        )

        # ================================================================
        # Academic Features (Research Papers)
        # ================================================================
        # 1. Citation Count (e.g., [1], [1, 2], (Smith et al., 2020))
        citation_matches = re.findall(r'\[\d+(?:,\s*\d+)*\]|\([A-Z][a-z]+(?: et al\.)?, \d{4}\)', text)
        citation_count = len(citation_matches)
        
        # 2. Section Detection
        sections = ['abstract', 'introduction', 'methodology', 'results', 'conclusion', 'references']
        found_sections = sum(1 for section in sections if re.search(r'(?i)^\s*\d*\.?\s*' + section, text, re.MULTILINE))
        section_completeness = found_sections / len(sections)

        # 3. Academic Vocabulary Density
        academic_words = {'analysis', 'approach', 'assessment', 'concept', 'context', 'data', 'derived', 'distribution', 'established', 'estimate', 'evidence', 'factors', 'hypothesis', 'identified', 'indicate', 'interpretation', 'method', 'occur', 'percent', 'period', 'principle', 'procedure', 'process', 'required', 'research', 'response', 'role', 'significant', 'similar', 'specific', 'structure', 'theory', 'variables'}
        academic_word_count = sum(1 for w in words_lower if w in academic_words)
        academic_word_density = academic_word_count / word_count if word_count > 0 else 0.0

        # ================================================================
        # Assemble result dict
        # ================================================================
        return {
            # Surface
            "word_count":              word_count,
            "sentence_count":          sentence_count,
            "paragraph_count":         paragraph_count,
            "avg_word_length":         round(avg_word_length, 4),
            "avg_sentence_length":     round(avg_sentence_length, 4),
            # Lexical diversity
            "type_token_ratio":        round(type_token_ratio, 4),
            "hapax_legomena_ratio":     round(hapax_legomena_ratio, 4),
            "lexical_diversity_mtld":   round(lexical_diversity_mtld, 4),
            # POS ratios
            "noun_ratio":              round(noun_ratio, 4),
            "verb_ratio":              round(verb_ratio, 4),
            "adj_ratio":               round(adj_ratio, 4),
            "adv_ratio":               round(adv_ratio, 4),
            # Entities
            "named_entity_count":      named_entity_count,
            # Punctuation
            "punctuation_density":     round(punctuation_density, 4),
            "comma_rate":              round(comma_rate, 4),
            "semicolon_count":         semicolon_count,
            "exclamation_count":       exclamation_count,
            "question_mark_count":     question_mark_count,
            # Vocabulary
            "stopword_ratio":          round(stopword_ratio, 4),
            "long_word_ratio":         round(long_word_ratio, 4),
            "vocabulary_richness_score": round(vocabulary_richness_score, 4),
            # Academic
            "citation_count":          citation_count,
            "section_completeness":    round(section_completeness, 4),
            "academic_word_density":   round(academic_word_density, 4),
        }

    # ================================================================
    # MTLD (Measure of Textual Lexical Diversity)
    # ================================================================

    def _compute_mtld(
        self,
        tokens: List[str],
        threshold: float = 0.72,
    ) -> float:
        """
        Compute MTLD (Measure of Textual Lexical Diversity).

        MTLD counts how many consecutive *factors* (non-overlapping
        segments of text) achieve a TTR that drops to or below the
        *threshold*.  The measure is computed in both forward and
        backward directions, and the results are averaged.

        A higher MTLD indicates greater lexical diversity.

        Args:
            tokens:    List of word strings (lowercased).
            threshold: TTR threshold for factor boundaries (default 0.72).

        Returns:
            MTLD value (float).  Returns 0.0 for empty input.

        Reference:
            McCarthy, P. M. & Jarvis, S. (2010).  MTLD, vocd-D, and
            HD-D: A validation study of sophisticated approaches to
            lexical diversity assessment.  *Behavior Research Methods*,
            42(2), 381-392.
        """
        if not tokens or len(tokens) < 2:
            return 0.0

        def _one_direction(word_list: List[str]) -> float:
            """Compute MTLD in a single direction."""
            factor_count = 0.0
            current_types: set = set()
            current_length = 0

            for word in word_list:
                current_types.add(word)
                current_length += 1

                ttr = len(current_types) / current_length

                if ttr <= threshold:
                    # Factor boundary reached
                    factor_count += 1.0
                    current_types = set()
                    current_length = 0

            # Handle the remaining partial factor
            if current_length > 0:
                ttr = len(current_types) / current_length
                if ttr < 1.0:
                    # Proportional credit for partial factor
                    factor_count += (1.0 - ttr) / (1.0 - threshold)

            if factor_count == 0:
                return float(len(word_list))

            return len(word_list) / factor_count

        forward = _one_direction(tokens)
        backward = _one_direction(tokens[::-1])

        return (forward + backward) / 2.0

    # ================================================================
    # Vocabulary richness composite
    # ================================================================

    @staticmethod
    def _compute_vocabulary_richness(
        ttr: float,
        hapax_ratio: float,
        mtld: float,
    ) -> float:
        """
        Combine TTR, hapax ratio, and MTLD into a single richness
        score in [0, 1].

        The MTLD value is normalised with a sigmoid centred at 72
        (typical midpoint for student essays).

        Weights:
            TTR         — 0.30
            Hapax ratio — 0.20
            MTLD (norm) — 0.50

        Args:
            ttr:         Type-token ratio (0-1).
            hapax_ratio: Hapax legomena ratio (0-1).
            mtld:        Raw MTLD value.

        Returns:
            Vocabulary richness score in [0, 1].
        """
        # Normalise MTLD to [0, 1] using a sigmoid
        # sigmoid(x) = 1 / (1 + e^(-k*(x - midpoint)))
        mtld_midpoint = 72.0
        mtld_k = 0.05
        mtld_norm = 1.0 / (1.0 + math.exp(-mtld_k * (mtld - mtld_midpoint)))

        richness = (0.30 * ttr) + (0.20 * hapax_ratio) + (0.50 * mtld_norm)

        # Clamp to [0, 1]
        return max(0.0, min(1.0, richness))

    # ================================================================
    # Empty-text fallback
    # ================================================================

    @staticmethod
    def _empty_features() -> Dict[str, Any]:
        """Return a zero-initialised feature dict for edge cases."""
        return {
            "word_count":                0,
            "sentence_count":            0,
            "paragraph_count":           0,
            "avg_word_length":           0.0,
            "avg_sentence_length":       0.0,
            "type_token_ratio":          0.0,
            "hapax_legomena_ratio":       0.0,
            "lexical_diversity_mtld":    0.0,
            "noun_ratio":                0.0,
            "verb_ratio":                0.0,
            "adj_ratio":                 0.0,
            "adv_ratio":                 0.0,
            "named_entity_count":        0,
            "punctuation_density":       0.0,
            "comma_rate":                0.0,
            "semicolon_count":           0,
            "exclamation_count":         0,
            "question_mark_count":       0,
            "stopword_ratio":            0.0,
            "long_word_ratio":           0.0,
            "vocabulary_richness_score": 0.0,
            "citation_count":            0,
            "section_completeness":      0.0,
            "academic_word_density":     0.0,
        }


# ============================================================
# Quick smoke-test when run directly
# ============================================================
if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    analyzer = LinguisticAnalyzer()

    test_texts = [
        (
            "The importance of education cannot be overstated. Education "
            "provides individuals with the knowledge and skills necessary "
            "to succeed in life. Without proper education, many people "
            "would struggle to find meaningful employment.\n\n"
            "Furthermore, education fosters critical thinking abilities "
            "that are vital in today's rapidly changing world. It opens "
            "doors to opportunities that would otherwise be inaccessible."
        ),
        "Hello world.",
        "",
    ]

    for i, txt in enumerate(test_texts, 1):
        print("=" * 60)
        label = txt[:60] + "..." if len(txt) > 60 else txt or "(empty)"
        print(f"TEXT {i}: {label}")
        features = analyzer.analyze(txt)
        print(json.dumps(features, indent=2))
        print()
