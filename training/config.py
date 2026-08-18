# ============================================================
# training/config.py
# Centralized Configuration for the Essay Scoring System
# ============================================================
# This module holds all hyperparameters, file paths, and
# model settings in a single dataclass. Every other module
# imports Config to stay in sync.
# ============================================================

import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class Config:
    """
    Centralized configuration for the entire essay scoring pipeline.
    
    Attributes are grouped into sections:
      - Paths: file and directory locations
      - Dataset: ASAP dataset parameters
      - Preprocessing: text cleaning settings
      - Feature Engineering: feature extraction parameters
      - Transformer: RoBERTa/BERT embedding settings
      - Models: hyperparameters for each model type
      - Training: learning rate, epochs, batch size, etc.
      - Evaluation: metrics to compute
      - Explainability: SHAP settings
    """

    # ---- Project Root ----
    project_root: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # ---- Paths ----
    dataset_path: str = ""
    models_dir: str = ""
    outputs_dir: str = ""
    graphs_dir: str = ""
    results_dir: str = ""
    embeddings_cache_dir: str = ""

    # ---- Dataset Settings ----
    # ASAP dataset has 8 essay sets with different score ranges
    essay_sets: List[int] = field(default_factory=lambda: [1, 2, 3, 4, 5, 6, 7, 8])

    # Score ranges for each essay set (min, max)
    score_ranges: Dict[int, tuple] = field(default_factory=lambda: {
        1: (2, 12),
        2: (1, 6),
        3: (0, 3),
        4: (0, 3),
        5: (0, 4),
        6: (0, 4),
        7: (0, 30),
        8: (0, 60),
    })

    # Human-readable prompt type descriptions for each essay set
    essay_set_names: Dict[int, str] = field(default_factory=lambda: {
        1: "Persuasive Essay (Grade 8) — Score Range: 2–12",
        2: "Persuasive Essay (Grade 10) — Score Range: 1–6",
        3: "Source-Based Essay A (Grade 10) — Score Range: 0–3",
        4: "Source-Based Essay B (Grade 10) — Score Range: 0–3",
        5: "Source-Based Essay C (Grade 8) — Score Range: 0–4",
        6: "Source-Based Essay D (Grade 10) — Score Range: 0–4",
        7: "Narrative Essay A (Grade 7) — Score Range: 0–30",
        8: "Narrative Essay B (Grade 10) — Score Range: 0–60",
    })

    # Data split ratios
    train_ratio: float = 0.70
    val_ratio: float = 0.15
    test_ratio: float = 0.15
    random_seed: int = 42

    # ---- Preprocessing ----
    max_essay_length: int = 1024  # Max tokens to consider
    min_essay_length: int = 10   # Minimum words for valid essay

    # ---- Feature Engineering ----
    # Number of handcrafted features extracted per essay
    num_linguistic_features: int = 25

    # ---- Transformer Settings ----
    # RoBERTa-base configuration
    roberta_model_name: str = "roberta-base"
    roberta_max_length: int = 512       # RoBERTa's max token limit
    roberta_embedding_dim: int = 768    # [CLS] embedding dimension

    # BERT-base configuration
    bert_model_name: str = "bert-base-uncased"
    bert_max_length: int = 512
    bert_embedding_dim: int = 768

    # PCA reduction for hybrid model
    pca_components: int = 128  # Reduce 768-dim to 128-dim

    # ---- Baseline Model Settings ----
    # CART (Decision Tree)
    cart_max_depth: int = 10
    cart_min_samples_split: int = 5
    cart_min_samples_leaf: int = 3

    # Random Forest
    rf_n_estimators: int = 200
    rf_max_depth: Optional[int] = None
    rf_min_samples_split: int = 5

    # XGBoost (used in hybrid model)
    xgb_n_estimators: int = 300
    xgb_max_depth: int = 6
    xgb_learning_rate: float = 0.1
    xgb_subsample: float = 0.8
    xgb_colsample_bytree: float = 0.8

    # ---- LSTM Settings ----
    lstm_embedding_dim: int = 300       # GloVe embedding dimension
    lstm_hidden_dim: int = 128          # LSTM hidden state size
    lstm_num_layers: int = 2            # Number of LSTM layers
    lstm_dropout: float = 0.3
    lstm_bidirectional: bool = True
    lstm_vocab_size: int = 50000        # Max vocabulary size

    # ---- Fine-tuning Settings (BERT/RoBERTa) ----
    finetune_epochs: int = 5
    finetune_batch_size: int = 16
    finetune_learning_rate: float = 2e-5
    finetune_warmup_steps: int = 100
    finetune_weight_decay: float = 0.01
    finetune_dropout: float = 0.1

    # ---- General Training Settings ----
    batch_size: int = 32
    epochs: int = 50
    learning_rate: float = 0.001
    early_stopping_patience: int = 5
    num_workers: int = 0  # DataLoader workers (0 for Windows compatibility)

    # ---- Evaluation ----
    metrics: List[str] = field(default_factory=lambda: [
        "qwk",           # Quadratic Weighted Kappa
        "mae",           # Mean Absolute Error
        "rmse",          # Root Mean Squared Error
        "pearson",       # Pearson Correlation Coefficient
    ])

    # ---- Explainability ----
    shap_max_samples: int = 100   # Max samples for SHAP computation
    shap_background_size: int = 50  # Background dataset size for KernelSHAP

    # ---- Model Names for Display ----
    model_names: Dict[str, str] = field(default_factory=lambda: {
        "linear_regression": "Linear Regression",
        "cart": "CART (Decision Tree)",
        "random_forest": "Random Forest",
        "lstm": "BiLSTM + Attention",
        "bert": "BERT (Fine-tuned)",
        "roberta": "RoBERTa (Fine-tuned)",
        "hybrid": "Hybrid (RoBERTa + Features + XGBoost)",
    })

    def __post_init__(self):
        """Set up derived paths after initialization."""
        self.dataset_path = os.path.join(self.project_root, "dataset", "training_set_rel3.tsv")
        self.models_dir = os.path.join(self.project_root, "models", "saved")
        self.outputs_dir = os.path.join(self.project_root, "outputs")
        self.graphs_dir = os.path.join(self.outputs_dir, "graphs")
        self.results_dir = os.path.join(self.outputs_dir, "results")
        self.embeddings_cache_dir = os.path.join(self.project_root, "cache", "embeddings")

        # Create directories
        for dir_path in [
            self.models_dir, self.graphs_dir,
            self.results_dir, self.embeddings_cache_dir
        ]:
            os.makedirs(dir_path, exist_ok=True)

    def normalize_score(self, score: float, essay_set: int) -> float:
        """
        Normalize a raw score to [0, 1] range based on the essay set's range.
        
        Args:
            score: Raw essay score
            essay_set: Essay set number (1-8)
            
        Returns:
            Normalized score in [0, 1]
        """
        min_score, max_score = self.score_ranges[essay_set]
        if max_score == min_score:
            return 0.0
        return (score - min_score) / (max_score - min_score)

    def denormalize_score(self, normalized_score: float, essay_set: int) -> float:
        """
        Convert a normalized [0, 1] score back to the original range.
        
        Args:
            normalized_score: Score in [0, 1]
            essay_set: Essay set number (1-8)
            
        Returns:
            Score in original range, rounded to nearest integer
        """
        min_score, max_score = self.score_ranges[essay_set]
        raw = normalized_score * (max_score - min_score) + min_score
        return round(max(min_score, min(max_score, raw)))
