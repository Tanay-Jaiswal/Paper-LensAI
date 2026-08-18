# ============================================================
# feature_engineering/readability_features.py
# Readability Metrics for Essay Scoring
# ============================================================
# Wraps the `textstat` library to extract a comprehensive set of
# readability metrics from essay text.  A composite readability
# score (0-1) is computed by normalising and averaging the
# individual metrics.
#
# Edge cases handled:
#   - Empty / whitespace-only text
#   - Very short text (< 10 words)
# ============================================================

import os
import sys
import logging
from typing import Dict, Any

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
# textstat import
# ---------------------------------------------------------------------------
try:
    import textstat
except ImportError:
    textstat = None
    logger.error(
        "textstat is not installed.  "
        "Install with: pip install textstat"
    )


class ReadabilityAnalyzer:
    """
    Extract readability metrics from essay text using `textstat`.

    Usage::

        analyzer = ReadabilityAnalyzer()
        features = analyzer.analyze(essay_text)

    The returned dictionary contains 10 standard readability measures
    plus a ``composite_readability_score`` in [0, 1].
    """

    # ----------------------------------------------------------------
    # Normalisation helpers for the composite score
    # ----------------------------------------------------------------
    # Each metric is mapped to an approximate "readable text" range
    # so that we can normalize to [0, 1] before averaging.
    #
    # Format: (min_expected, max_expected, higher_is_better)
    # ----------------------------------------------------------------
    _METRIC_RANGES = {
        "flesch_reading_ease":          (0.0,   50.0, False), # Lower is more difficult (academic)
        "flesch_kincaid_grade":         (10.0,  20.0, True),  # Higher grade level = better
        "gunning_fog":                  (10.0,  20.0, True),
        "smog_index":                   (10.0,  20.0, True),
        "coleman_liau_index":           (10.0,  20.0, True),
        "automated_readability_index":  (10.0,  20.0, True),
        "dale_chall_readability":       (8.0,   12.0, True),
        "linsear_write_formula":        (10.0,  20.0, True),
    }

    # ================================================================
    # Public: analyze
    # ================================================================

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Compute readability metrics for *text*.

        Args:
            text: Essay text (cleaned or raw).

        Returns:
            Dictionary with the following keys:

            - ``flesch_reading_ease`` (float)
            - ``flesch_kincaid_grade`` (float)
            - ``gunning_fog`` (float)
            - ``smog_index`` (float)
            - ``coleman_liau_index`` (float)
            - ``automated_readability_index`` (float)
            - ``dale_chall_readability`` (float)
            - ``linsear_write_formula`` (float)
            - ``text_standard`` (str): Consensus grade level string.
            - ``composite_readability_score`` (float): Normalised
              average of the numeric metrics, in [0, 1].

        Notes:
            - Returns all-zero values (with ``composite = 0.5``) for
              empty text.
            - For very short texts (< 10 words), metrics may be
              unreliable; a warning is logged.
        """
        # --- Guard: textstat not installed ---
        if textstat is None:
            logger.warning(
                "textstat not available — returning default readability values."
            )
            return self._default_result()

        # --- Guard: empty text ---
        if not isinstance(text, str) or not text.strip():
            return self._default_result()

        # --- Guard: very short text ---
        word_count = len(text.split())
        if word_count < 10:
            logger.warning(
                "Text has only %d words; readability metrics may be "
                "unreliable.",
                word_count,
            )

        # --- Compute metrics ---
        try:
            flesch_reading_ease = textstat.flesch_reading_ease(text)
        except Exception:
            flesch_reading_ease = 0.0

        try:
            flesch_kincaid_grade = textstat.flesch_kincaid_grade(text)
        except Exception:
            flesch_kincaid_grade = 0.0

        try:
            gunning_fog = textstat.gunning_fog(text)
        except Exception:
            gunning_fog = 0.0

        try:
            smog_index = textstat.smog_index(text)
        except Exception:
            smog_index = 0.0

        try:
            coleman_liau_index = textstat.coleman_liau_index(text)
        except Exception:
            coleman_liau_index = 0.0

        try:
            automated_readability_index = textstat.automated_readability_index(text)
        except Exception:
            automated_readability_index = 0.0

        try:
            dale_chall_readability = textstat.dale_chall_readability_score(text)
        except Exception:
            dale_chall_readability = 0.0

        try:
            linsear_write_formula = textstat.linsear_write_formula(text)
        except Exception:
            linsear_write_formula = 0.0

        try:
            text_standard = textstat.text_standard(text, float_output=False)
        except Exception:
            text_standard = "N/A"

        # --- Assemble raw results dict ---
        raw_metrics: Dict[str, float] = {
            "flesch_reading_ease":         flesch_reading_ease,
            "flesch_kincaid_grade":        flesch_kincaid_grade,
            "gunning_fog":                 gunning_fog,
            "smog_index":                  smog_index,
            "coleman_liau_index":          coleman_liau_index,
            "automated_readability_index": automated_readability_index,
            "dale_chall_readability":      dale_chall_readability,
            "linsear_write_formula":       linsear_write_formula,
        }

        # --- Composite score (normalised average) ---
        composite = self._compute_composite(raw_metrics)

        result: Dict[str, Any] = {**raw_metrics}
        result["text_standard"] = text_standard
        result["composite_readability_score"] = round(composite, 4)

        return result

    # ================================================================
    # Internal helpers
    # ================================================================

    def _compute_composite(self, metrics: Dict[str, float]) -> float:
        """
        Normalise each metric to [0, 1] using predefined ranges, then
        take the mean to produce a single composite score.

        For metrics where *lower* values indicate better readability
        (e.g. grade levels), the normalised value is inverted.

        Args:
            metrics: Dict of metric_name → raw value.

        Returns:
            Composite readability score in [0, 1].
        """
        normalised_values = []

        for name, (lo, hi, higher_is_better) in self._METRIC_RANGES.items():
            raw = metrics.get(name, 0.0)

            # Clamp to expected range
            clamped = max(lo, min(hi, raw))

            if hi == lo:
                norm = 0.5
            else:
                norm = (clamped - lo) / (hi - lo)

            # Invert if lower is better (grade-level metrics)
            if not higher_is_better:
                norm = 1.0 - norm

            normalised_values.append(norm)

        if not normalised_values:
            return 0.5

        return sum(normalised_values) / len(normalised_values)

    @staticmethod
    def _default_result() -> Dict[str, Any]:
        """Return a zero-initialised result dict for edge cases."""
        return {
            "flesch_reading_ease":          0.0,
            "flesch_kincaid_grade":         0.0,
            "gunning_fog":                  0.0,
            "smog_index":                   0.0,
            "coleman_liau_index":           0.0,
            "automated_readability_index":  0.0,
            "dale_chall_readability":       0.0,
            "linsear_write_formula":        0.0,
            "text_standard":               "N/A",
            "composite_readability_score":  0.5,
        }


# ============================================================
# Quick smoke-test when run directly
# ============================================================
if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    analyzer = ReadabilityAnalyzer()

    test_texts = [
        # Normal text
        (
            "The importance of education cannot be overstated. Education "
            "provides individuals with the knowledge and skills necessary "
            "to succeed in life. Without proper education, many people "
            "would struggle to find meaningful employment. Furthermore, "
            "education fosters critical thinking abilities that are vital "
            "in today's rapidly changing world."
        ),
        # Simple text
        "The cat sat on the mat. It was a good day.",
        # Empty
        "",
        # Very short
        "Hello world.",
    ]

    for i, txt in enumerate(test_texts, 1):
        print("=" * 60)
        label = txt[:60] + "..." if len(txt) > 60 else txt or "(empty)"
        print(f"TEXT {i}: {label}")
        results = analyzer.analyze(txt)
        print(json.dumps(results, indent=2))
        print()
