# ============================================================
# preprocessing/data_loader.py
# Data Loading, Normalization & Splitting for Essay Scoring
# ============================================================
# Responsibilities:
#   - Read the ASAP TSV dataset (with encoding fallback)
#   - Normalize raw scores to [0, 1] per essay set
#   - Stratified train / val / test splits
#   - Dataset statistics & exploratory summaries
#   - Synthetic sample data for unit testing
# ============================================================

import os
import sys
import logging
from typing import Tuple, Dict, Any, Optional

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

# ---------------------------------------------------------------------------
# Path setup — ensure the project root is on sys.path so that
# ``from training.config import Config`` works regardless of CWD.
# ---------------------------------------------------------------------------
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from training.config import Config

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)


class DataLoader:
    """
    Loads, normalises and splits the ASAP essay-scoring dataset.

    Typical workflow::

        loader = DataLoader()
        config = Config()

        df = loader.load_dataset(config.dataset_path)
        df = loader.normalize_scores(df, config)
        train, val, test = loader.split_data(df)
        stats = loader.get_dataset_stats(train)
    """

    # ================================================================
    # 1.  Load the raw TSV dataset
    # ================================================================

    @staticmethod
    def load_dataset(path: str) -> pd.DataFrame:
        """
        Read the ASAP TSV file into a pandas DataFrame.

        The method tries UTF-8 first and falls back to Latin-1 if a
        ``UnicodeDecodeError`` is raised.  Only the four columns needed
        by the scoring pipeline are retained:

        - ``essay_id``
        - ``essay_set``
        - ``essay``
        - ``domain1_score``

        Args:
            path: Absolute or relative path to the TSV file.

        Returns:
            DataFrame with the four selected columns.

        Raises:
            FileNotFoundError: If *path* does not exist.
            KeyError:          If expected columns are missing from the file.
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(
                f"Dataset file not found: {path}\n"
                "Download the ASAP dataset and place 'training_set_rel3.tsv' "
                "in the 'dataset/' directory."
            )

        # --- Try UTF-8 first, fall back to Latin-1 -----------------------
        for encoding in ("utf-8", "latin-1"):
            try:
                df = pd.read_csv(path, sep="\t", encoding=encoding)
                logger.info(
                    "Loaded dataset from '%s' with encoding='%s' (%d rows).",
                    path, encoding, len(df),
                )
                break
            except UnicodeDecodeError:
                logger.warning(
                    "UTF-8 decoding failed for '%s'; retrying with Latin-1.",
                    path,
                )
                continue
        else:
            # Neither encoding worked
            raise ValueError(
                f"Could not decode '{path}' with UTF-8 or Latin-1."
            )

        # --- Select required columns --------------------------------------
        required_columns = ["essay_id", "essay_set", "essay", "domain1_score"]
        missing = [c for c in required_columns if c not in df.columns]
        if missing:
            raise KeyError(
                f"Missing columns in dataset: {missing}. "
                f"Available: {list(df.columns)}"
            )

        df = df[required_columns].copy()

        # --- Basic sanity checks ------------------------------------------
        df.dropna(subset=["essay", "domain1_score"], inplace=True)
        df["essay"] = df["essay"].astype(str)
        df["domain1_score"] = pd.to_numeric(df["domain1_score"], errors="coerce")
        df.dropna(subset=["domain1_score"], inplace=True)
        df["domain1_score"] = df["domain1_score"].astype(int)

        logger.info(
            "Dataset ready: %d essays across %d essay sets.",
            len(df), df["essay_set"].nunique(),
        )
        return df.reset_index(drop=True)

    # ================================================================
    # 2.  Score normalisation
    # ================================================================

    @staticmethod
    def normalize_scores(
        df: pd.DataFrame,
        config: Optional[Config] = None,
    ) -> pd.DataFrame:
        """
        Add a ``normalized_score`` column using min-max normalisation
        per essay set.

        The score ranges come from ``Config.score_ranges``.  If *config*
        is ``None``, a default ``Config()`` is instantiated.

        Formula::

            normalised = (raw - min) / (max - min)

        Args:
            df:     DataFrame with ``essay_set`` and ``domain1_score``.
            config: Config instance holding ``score_ranges``.

        Returns:
            The same DataFrame with the additional ``normalized_score`` column.
        """
        if config is None:
            config = Config()

        def _normalize_row(row: pd.Series) -> float:
            essay_set = int(row["essay_set"])
            score = float(row["domain1_score"])

            if essay_set not in config.score_ranges:
                logger.warning(
                    "Unknown essay_set %d — returning raw score.", essay_set
                )
                return score

            min_score, max_score = config.score_ranges[essay_set]
            if max_score == min_score:
                return 0.0
            return (score - min_score) / (max_score - min_score)

        df["normalized_score"] = df.apply(_normalize_row, axis=1)

        # Clamp to [0, 1] for safety
        df["normalized_score"] = df["normalized_score"].clip(0.0, 1.0)

        logger.info("Added 'normalized_score' column (min-max per essay_set).")
        return df

    # ================================================================
    # 3.  Stratified train / val / test split
    # ================================================================

    @staticmethod
    def split_data(
        df: pd.DataFrame,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        seed: int = 42,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Split the dataset into train / validation / test sets, stratified
        by ``essay_set`` so each split has the same proportion of sets.

        Args:
            df:          Full DataFrame to split.
            train_ratio: Fraction for training   (default 0.70).
            val_ratio:   Fraction for validation  (default 0.15).
            test_ratio:  Fraction for testing     (default 0.15).
            seed:        Random seed for reproducibility.

        Returns:
            Tuple ``(train_df, val_df, test_df)``.

        Raises:
            ValueError: If the ratios do not sum to ~1.0.
        """
        total = train_ratio + val_ratio + test_ratio
        if not (0.99 <= total <= 1.01):
            raise ValueError(
                f"Split ratios must sum to 1.0, got {total:.4f}."
            )

        # First split: train vs. (val + test)
        val_test_ratio = val_ratio + test_ratio
        
        # Check if we have enough samples per class for stratification
        min_class_count = df["essay_set"].value_counts().min()
        use_stratify = (min_class_count >= 3) and (len(df) >= 30)
        
        if not use_stratify:
            logger.warning(
                "Disabling stratification because some essay sets have too few samples (min count = %d) or dataset is too small.",
                min_class_count
            )
            
        train_df, temp_df = train_test_split(
            df,
            test_size=val_test_ratio,
            random_state=seed,
            stratify=df["essay_set"] if use_stratify else None,
        )

        # Second split: val vs. test (from the remainder)
        relative_test_ratio = test_ratio / val_test_ratio
        
        # Check if temp_df has enough samples per class for stratification
        temp_use_stratify = use_stratify and (temp_df["essay_set"].value_counts().min() >= 2)
        
        val_df, test_df = train_test_split(
            temp_df,
            test_size=relative_test_ratio,
            random_state=seed,
            stratify=temp_df["essay_set"] if temp_use_stratify else None,
        )

        logger.info(
            "Split complete — Train: %d | Val: %d | Test: %d",
            len(train_df), len(val_df), len(test_df),
        )
        return (
            train_df.reset_index(drop=True),
            val_df.reset_index(drop=True),
            test_df.reset_index(drop=True),
        )

    # ================================================================
    # 4.  Dataset statistics
    # ================================================================

    @staticmethod
    def get_dataset_stats(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Compute descriptive statistics for the dataset.

        Returns a dict with:
            - ``total_essays``: Total number of essays.
            - ``essay_sets``:  Dict mapping set id → count.
            - ``score_distributions``: Dict mapping set id → score
              value-counts dict.
            - ``avg_essay_length``: Mean word count across all essays.
            - ``median_essay_length``: Median word count.
            - ``min_essay_length``: Shortest essay (word count).
            - ``max_essay_length``: Longest essay (word count).

        Args:
            df: DataFrame to analyse (must have ``essay``, ``essay_set``,
                ``domain1_score`` columns).

        Returns:
            Dictionary of statistics.
        """
        # Word counts
        word_counts = df["essay"].astype(str).apply(lambda t: len(t.split()))

        # Per-set score distributions
        score_distributions = {}
        for essay_set, group in df.groupby("essay_set"):
            score_distributions[int(essay_set)] = (
                group["domain1_score"]
                .value_counts()
                .sort_index()
                .to_dict()
            )

        stats: Dict[str, Any] = {
            "total_essays":       len(df),
            "essay_sets":         df["essay_set"].value_counts().sort_index().to_dict(),
            "score_distributions": score_distributions,
            "avg_essay_length":   round(word_counts.mean(), 2),
            "median_essay_length": int(word_counts.median()),
            "min_essay_length":   int(word_counts.min()),
            "max_essay_length":   int(word_counts.max()),
        }

        logger.info("Dataset stats computed for %d essays.", len(df))
        return stats

    # ================================================================
    # 5.  Synthetic sample data for testing
    # ================================================================

    @staticmethod
    def create_sample_data(n_rows: int = 20) -> pd.DataFrame:
        """
        Create a small synthetic DataFrame that mimics the structure of
        the real ASAP dataset.  Useful for unit tests and quick sanity
        checks when the full dataset is not available.

        The synthetic essays are short but structurally realistic —
        they contain multiple sentences, varied vocabulary, and some
        intentional grammar errors so feature extractors have
        something to work with.

        Args:
            n_rows: Number of sample rows (default 20).

        Returns:
            DataFrame with columns: essay_id, essay_set, essay,
            domain1_score.
        """
        sample_essays = [
            (
                "The importance of education cannot be overstated. "
                "Education provides individuals with the knowledge and skills "
                "necessary to succeed in life. Without proper education, "
                "many people would struggle to find meaningful employment. "
                "Furthermore, education fosters critical thinking abilities."
            ),
            (
                "I believe that computers have changed our lives dramatically. "
                "We use computers for everything from communication to "
                "entertainment. Some people argue that too much screen time "
                "is harmful, but I think the benefits outweigh the risks."
            ),
            (
                "Dear editor, I am writing to express my concern about the "
                "proposed changes to our local park. The park has been a "
                "gathering place for families for over fifty years. Removing "
                "the playground would negatively impact our community."
            ),
            (
                "In the story, the main character faces a difficult decision. "
                "She must choose between following her dreams and staying "
                "close to her family. This conflict is relatable because many "
                "young people experience similar struggles."
            ),
            (
                "Technology has revolutionized the way we learn. Online "
                "courses allow students to study at their own pace and from "
                "any location. However, some students lack the discipline "
                "needed for self-directed learning."
            ),
            (
                "Climate change is one of the most pressing issues of our "
                "time. Scientists have shown that human activities contribute "
                "to global warming. We must take action now to reduce carbon "
                "emissions and protect our planet for future generations."
            ),
            (
                "The author uses vivid imagery to describe the setting. "
                "The dark forest represents the unknown challenges ahead. "
                "Through symbolism, the reader understands the protagonist's "
                "fear and determination."
            ),
            (
                "Physical fitness is essential for a healthy lifestyle. "
                "Regular exercise helps maintain a healthy weight, strengthens "
                "muscles, and improves mental health. Schools should require "
                "daily physical education for all students."
            ),
            (
                "Social media has both positive and negative effects on "
                "teenagers. It allows them to stay connected with friends "
                "but can also lead to cyberbullying and low self-esteem. "
                "Parents should monitor their children's online activity."
            ),
            (
                "In conclusion, the experiment demonstrated that plants "
                "grow faster when exposed to classical music. This finding "
                "supports the hypothesis that sound vibrations can influence "
                "plant growth. More research is needed to confirm these results."
            ),
            (
                "Reading books is one of the best ways to expand your "
                "vocabulary and improve your writing skills. Many successful "
                "people credit their love of reading as a key factor in "
                "their success."
            ),
            (
                "The school lunch program needs improvement. Currently, the "
                "meals are high in sugar and low in nutritional value. By "
                "offering healthier options, we can help students focus "
                "better in class and develop good eating habits."
            ),
            (
                "Space exploration has led to many technological advances. "
                "Satellite technology, for example, has improved weather "
                "forecasting and global communication. Investing in space "
                "research benefits society in unexpected ways."
            ),
            (
                "Volunteering teaches young people valuable life skills. "
                "When students volunteer at local shelters or food banks, "
                "they learn empathy, teamwork, and responsibility. "
                "Community service should be a graduation requirement."
            ),
            (
                "The poem conveys a sense of nostalgia through its imagery "
                "and tone. The speaker reflects on childhood memories with "
                "both joy and sadness. This duality makes the poem deeply "
                "moving and relatable."
            ),
            (
                "Recycling is a simple but effective way to protect the "
                "environment. By sorting our waste and reusing materials, "
                "we can reduce the amount of trash in landfills. Everyone "
                "should make recycling a daily habit."
            ),
            (
                "Homework is a controversial topic among educators. Some "
                "believe it reinforces learning, while others argue it "
                "causes unnecessary stress. A balanced approach that limits "
                "homework to meaningful assignments would be most effective."
            ),
            (
                "The Industrial Revolution transformed society in profound "
                "ways. Factories replaced small workshops, and cities grew "
                "rapidly as people moved from rural areas. These changes "
                "brought both progress and new social challenges."
            ),
            (
                "Music education should be a core part of every school "
                "curriculum. Studies have shown that learning an instrument "
                "improves math skills, memory, and emotional intelligence. "
                "Cutting music programs is a disservice to students."
            ),
            (
                "In my opinion, zoos play an important role in conservation. "
                "They protect endangered species and educate the public about "
                "wildlife. However, animals should be kept in environments "
                "that closely resemble their natural habitats."
            ),
        ]

        rng = np.random.RandomState(42)

        # Default score ranges from Config
        score_ranges = {
            1: (2, 12), 2: (1, 6), 3: (0, 3), 4: (0, 3),
            5: (0, 4),  6: (0, 4), 7: (0, 30), 8: (0, 60),
        }

        rows = []
        for i in range(n_rows):
            essay_set = rng.randint(1, 9)  # 1-8 inclusive
            min_s, max_s = score_ranges[essay_set]
            score = rng.randint(min_s, max_s + 1)
            essay_text = sample_essays[i % len(sample_essays)]

            rows.append(
                {
                    "essay_id": i + 1,
                    "essay_set": essay_set,
                    "essay": essay_text,
                    "domain1_score": score,
                }
            )

        df = pd.DataFrame(rows)
        logger.info("Created synthetic sample dataset with %d rows.", n_rows)
        return df


# ============================================================
# Quick smoke-test when run directly
# ============================================================
if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    loader = DataLoader()

    # --- Synthetic data demo ---
    print("=" * 60)
    print("CREATING SYNTHETIC SAMPLE DATA")
    print("=" * 60)
    sample_df = loader.create_sample_data(20)
    print(sample_df.head(10).to_string(index=False))

    # --- Normalise scores ---
    print("\n" + "=" * 60)
    print("NORMALIZING SCORES")
    print("=" * 60)
    sample_df = loader.normalize_scores(sample_df)
    print(
        sample_df[["essay_id", "essay_set", "domain1_score", "normalized_score"]]
        .head(10)
        .to_string(index=False)
    )

    # --- Split ---
    print("\n" + "=" * 60)
    print("SPLITTING DATA")
    print("=" * 60)
    train, val, test = loader.split_data(sample_df)
    print(f"Train: {len(train)} | Val: {len(val)} | Test: {len(test)}")

    # --- Stats ---
    print("\n" + "=" * 60)
    print("DATASET STATISTICS")
    print("=" * 60)
    stats = loader.get_dataset_stats(sample_df)
    print(json.dumps(stats, indent=2))
    print("=" * 60)
