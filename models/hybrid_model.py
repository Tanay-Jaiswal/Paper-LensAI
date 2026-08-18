# ============================================================
# models/hybrid_model.py
# Proposed Hybrid Model (RoBERTa Embeddings + Linguistic Features + XGBoost)
# ============================================================
# Fuses transformer representations with explicit linguistic and
# readability metrics, compresses embeddings using PCA, and trains
# an XGBoost regressor for final grading. Includes SHAP support.
# ============================================================

import os
import sys
import logging
import joblib
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

# --------------- Project Imports ---------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from training.config import Config
from utils.helpers import ensure_dir
from feature_engineering.grammar_features import GrammarAnalyzer
from feature_engineering.readability_features import ReadabilityAnalyzer
from feature_engineering.linguistic_features import LinguisticAnalyzer
from feature_engineering.transformer_embeddings import TransformerEmbedder

# --------------- Logger ---------------
logger = logging.getLogger("EssayScoringAI.HybridModel")


class HybridScorer:
    """
    Hybrid scoring model combining transformer embeddings and linguistic features.
    
    Architecture:
    1. Extract RoBERTa CLS embeddings (768-dim) and reduce to 128-dim via PCA.
    2. Extract ~26 handcrafted grammar, readability, and linguistic features.
    3. Scale handcrafted features using StandardScaler.
    4. Concatenate PCA embeddings and scaled features.
    5. Predict score using XGBoost Regressor.
    """

    def __init__(self, config: Config):
        """
        Initialize the hybrid scorer.
        
        Args:
            config: Config instance with hyperparameters.
        """
        self.config = config
        
        # Analyzers
        self.embedder = TransformerEmbedder(
            model_name=config.roberta_model_name
        )
        self.grammar_analyzer = GrammarAnalyzer()
        self.readability_analyzer = ReadabilityAnalyzer()
        self.linguistic_analyzer = LinguisticAnalyzer()
        
        # ML components
        self.pca = PCA(n_components=config.pca_components, random_state=config.random_seed)
        self.scaler = StandardScaler()
        self.model = XGBRegressor(
            n_estimators=config.xgb_n_estimators,
            max_depth=config.xgb_max_depth,
            learning_rate=config.xgb_learning_rate,
            subsample=config.xgb_subsample,
            colsample_bytree=config.xgb_colsample_bytree,
            random_state=config.random_seed,
            n_jobs=-1
        )
        
        # Feature name cache
        self.handcrafted_names = [
            'grammar_error_count', 'spelling_error_count', 'error_rate', 'grammar_score',
            'flesch_reading_ease', 'flesch_kincaid_grade', 'gunning_fog', 'smog_index',
            'coleman_liau_index', 'automated_readability_index', 'composite_readability_score',
            'word_count', 'sentence_count', 'avg_word_length', 'avg_sentence_length',
            'type_token_ratio', 'hapax_legomena_ratio', 'lexical_diversity_mtld',
            'noun_ratio', 'verb_ratio', 'adj_ratio', 'adv_ratio',
            'named_entity_count', 'stopword_ratio', 'long_word_ratio', 'vocabulary_richness_score'
        ]
        
        self.pca_names = [f"pca_dim_{i}" for i in range(config.pca_components)]
        self.all_feature_names = self.pca_names + self.handcrafted_names

    def _extract_handcrafted(self, text: str) -> np.ndarray:
        """Helper to extract handcrafted features for a single text."""
        features = {}
        
        # Grammar
        try:
            gram = self.grammar_analyzer.analyze(text)
            features.update({
                'grammar_error_count': gram.get('grammar_error_count', 0),
                'spelling_error_count': gram.get('spelling_error_count', 0),
                'error_rate': gram.get('error_rate', 0.0),
                'grammar_score': gram.get('grammar_score', 1.0),
            })
        except Exception:
            features.update({'grammar_error_count': 0, 'spelling_error_count': 0, 'error_rate': 0.0, 'grammar_score': 1.0})
            
        # Readability
        try:
            read = self.readability_analyzer.analyze(text)
            features.update({
                'flesch_reading_ease': read.get('flesch_reading_ease', 50.0),
                'flesch_kincaid_grade': read.get('flesch_kincaid_grade', 8.0),
                'gunning_fog': read.get('gunning_fog', 10.0),
                'smog_index': read.get('smog_index', 8.0),
                'coleman_liau_index': read.get('coleman_liau_index', 8.0),
                'automated_readability_index': read.get('automated_readability_index', 8.0),
                'composite_readability_score': read.get('composite_readability_score', 0.5),
            })
        except Exception:
            features.update({
                'flesch_reading_ease': 50.0, 'flesch_kincaid_grade': 8.0, 'gunning_fog': 10.0,
                'smog_index': 8.0, 'coleman_liau_index': 8.0, 'automated_readability_index': 8.0,
                'composite_readability_score': 0.5
            })
            
        # Linguistic
        try:
            ling = self.linguistic_analyzer.analyze(text)
            features.update({
                'word_count': ling.get('word_count', 0),
                'sentence_count': ling.get('sentence_count', 0),
                'avg_word_length': ling.get('avg_word_length', 4.0),
                'avg_sentence_length': ling.get('avg_sentence_length', 15.0),
                'type_token_ratio': ling.get('type_token_ratio', 0.5),
                'hapax_legomena_ratio': ling.get('hapax_legomena_ratio', 0.5),
                'lexical_diversity_mtld': ling.get('lexical_diversity_mtld', 50.0),
                'noun_ratio': ling.get('noun_ratio', 0.2),
                'verb_ratio': ling.get('verb_ratio', 0.15),
                'adj_ratio': ling.get('adj_ratio', 0.1),
                'adv_ratio': ling.get('adv_ratio', 0.05),
                'named_entity_count': ling.get('named_entity_count', 0),
                'stopword_ratio': ling.get('stopword_ratio', 0.4),
                'long_word_ratio': ling.get('long_word_ratio', 0.2),
                'vocabulary_richness_score': ling.get('vocabulary_richness_score', 0.5),
            })
        except Exception:
            features.update({
                'word_count': 0, 'sentence_count': 0, 'avg_word_length': 4.0, 'avg_sentence_length': 15.0,
                'type_token_ratio': 0.5, 'hapax_legomena_ratio': 0.5, 'lexical_diversity_mtld': 50.0,
                'noun_ratio': 0.2, 'verb_ratio': 0.15, 'adj_ratio': 0.1, 'adv_ratio': 0.05,
                'named_entity_count': 0, 'stopword_ratio': 0.4, 'long_word_ratio': 0.2,
                'vocabulary_richness_score': 0.5
            })
            
        return np.array([features[name] for name in self.handcrafted_names], dtype=np.float32)

    def extract_all_features(
        self,
        texts: List[str],
        show_progress: bool = True
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Extract embeddings and handcrafted features for all texts.
        
        Returns:
            Tuple of (embeddings, handcrafted_features, feature_names)
        """
        logger.info("Extracting transformer embeddings...")
        embeddings = self.embedder.extract_batch_embeddings(
            texts, batch_size=16, show_progress=show_progress
        )
        
        logger.info("Extracting handcrafted linguistic features...")
        handcrafted = []
        for text in texts:
            handcrafted.append(self._extract_handcrafted(text))
            
        handcrafted = np.array(handcrafted, dtype=np.float32)
        handcrafted = np.nan_to_num(handcrafted, 0.0)
        
        return embeddings, handcrafted, self.all_feature_names

    def train(
        self,
        train_texts: List[str],
        train_scores: np.ndarray,
        val_texts: List[str],
        val_scores: np.ndarray,
        train_essay_sets: Optional[np.ndarray] = None,
        val_essay_sets: Optional[np.ndarray] = None
    ) -> Dict[str, list]:
        """
        Train the hybrid pipeline: PCA, scaler, and XGBoost regressor.
        """
        # 1. Feature Extraction
        tr_embeds, tr_hand, _ = self.extract_all_features(train_texts)
        val_embeds, val_hand, _ = self.extract_all_features(val_texts)
        
        # 2. Fit and Apply PCA on embeddings
        logger.info("Fitting PCA on embeddings...")
        n_samples = tr_embeds.shape[0]
        n_features = tr_embeds.shape[1]
        max_possible_components = min(n_samples, n_features)
        
        if self.config.pca_components > max_possible_components:
            adjusted_components = max(1, max_possible_components - 1)
            logger.warning(
                "Adjusting PCA n_components from %d to %d to match sample size.",
                self.config.pca_components, adjusted_components
            )
            self.pca.n_components = adjusted_components
        else:
            self.pca.n_components = self.config.pca_components
            
        tr_pca = self.pca.fit_transform(tr_embeds)
        val_pca = self.pca.transform(val_embeds)
        
        # Update feature names to match actual PCA dimensions
        actual_pca_components = tr_pca.shape[1]
        self.pca_names = [f"pca_dim_{i}" for i in range(actual_pca_components)]
        self.all_feature_names = self.pca_names + self.handcrafted_names
        
        # 3. Fit and Apply Scaler on handcrafted features
        logger.info("Scaling handcrafted features...")
        tr_scaled_hand = self.scaler.fit_transform(tr_hand)
        val_scaled_hand = self.scaler.transform(val_hand)
        
        # 4. Concatenate
        X_train = np.hstack([tr_pca, tr_scaled_hand])
        X_val = np.hstack([val_pca, val_scaled_hand])
        
        # Add essay set code if provided to assist model generalization
        if train_essay_sets is not None and val_essay_sets is not None:
            # We append essay set as an extra feature or one-hot vector.
            # But let's keep it simple: just concatenate normalized essay set identifier.
            # Normalizing essay set to [0,1]
            tr_sets = (train_essay_sets.reshape(-1, 1) - 1.0) / 7.0
            val_sets = (val_essay_sets.reshape(-1, 1) - 1.0) / 7.0
            X_train = np.hstack([X_train, tr_sets])
            X_val = np.hstack([X_val, val_sets])
            if "essay_set_code" not in self.all_feature_names:
                self.all_feature_names.append("essay_set_code")
        
        logger.info("Training XGBoost Regressor...")
        self.model.fit(
            X_train, train_scores,
            eval_set=[(X_val, val_scores)],
            verbose=True
        )
        
        # Return training history structure
        evals_result = self.model.evals_result()
        history = {
            "train_loss": evals_result.get("validation_0", {}).get("rmse", [0.0]),
            "val_loss": evals_result.get("validation_0", {}).get("rmse", [0.0])
        }
        return history

    def predict(
        self,
        texts: List[str],
        essay_sets: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Predict scores for a list of essays.
        """
        X = self.get_feature_matrix(texts, essay_sets)
        preds = self.model.predict(X)
        return np.clip(preds, 0.0, 1.0)

    def get_feature_matrix(
        self,
        texts: List[str],
        essay_sets: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Get the fully processed feature matrix (PCA embeddings + scaled features) for input texts.
        Used for predictions and SHAP explanations.
        """
        embeds, hand, _ = self.extract_all_features(texts, show_progress=False)
        pca_feats = self.pca.transform(embeds)
        scaled_hand = self.scaler.transform(hand)
        X = np.hstack([pca_feats, scaled_hand])
        
        if essay_sets is not None:
            sets = (essay_sets.reshape(-1, 1) - 1.0) / 7.0
            X = np.hstack([X, sets])
        elif "essay_set_code" in self.all_feature_names:
            # If model was trained with essay sets, append dummy set code (e.g. Set 1 = 0)
            dummy_sets = np.zeros((len(texts), 1), dtype=np.float32)
            X = np.hstack([X, dummy_sets])
            
        return X

    def get_feature_names(self) -> List[str]:
        """Return the list of all feature names."""
        return self.all_feature_names

    def get_model(self) -> XGBRegressor:
        """Return the trained XGBoost model."""
        return self.model

    def save(self, path: str) -> None:
        """Save the entire hybrid pipeline to the given directory."""
        try:
            ensure_dir(path)
            
            # Save embedder state separately if needed, but since it is loaded from HF name,
            # we just need to save the scikit-learn and xgboost components.
            joblib.dump(self.pca, os.path.join(path, "pca.joblib"))
            joblib.dump(self.scaler, os.path.join(path, "scaler.joblib"))
            joblib.dump(self.model, os.path.join(path, "xgb_model.joblib"))
            joblib.dump(self.all_feature_names, os.path.join(path, "feature_names.joblib"))
            
            logger.info("HybridScorer pipeline saved successfully to %s", path)
        except Exception as e:
            logger.error("Failed to save HybridScorer: %s", e)
            raise

    def load(self, path: str) -> None:
        """Load the hybrid pipeline from the given directory."""
        try:
            self.pca = joblib.load(os.path.join(path, "pca.joblib"))
            self.scaler = joblib.load(os.path.join(path, "scaler.joblib"))
            self.model = joblib.load(os.path.join(path, "xgb_model.joblib"))
            self.all_feature_names = joblib.load(os.path.join(path, "feature_names.joblib"))
            
            logger.info("HybridScorer pipeline loaded successfully from %s", path)
        except Exception as e:
            logger.error("Failed to load HybridScorer: %s", e)
            raise
