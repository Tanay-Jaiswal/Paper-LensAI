# ============================================================
# training/trainer.py
# Unified Training Orchestrator
# ============================================================
# This module coordinates the entire training pipeline:
# data loading → feature extraction → model training → evaluation.
# It supports training all 6 models and comparing results.
# ============================================================

import os
import sys
import json
import time
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple

# Project imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training.config import Config
from utils.helpers import set_seed, get_device, ensure_dir, timer_decorator, setup_logging
from preprocessing.data_loader import DataLoader
from preprocessing.text_cleaner import TextCleaner
from feature_engineering.grammar_features import GrammarAnalyzer
from feature_engineering.readability_features import ReadabilityAnalyzer
from feature_engineering.linguistic_features import LinguisticAnalyzer
from feature_engineering.transformer_embeddings import TransformerEmbedder
from evaluation.metrics import compute_all_metrics, compute_per_set_metrics
from evaluation.evaluator import ModelEvaluator
from evaluation.visualizations import ResultVisualizer


class Trainer:
    """
    Unified training orchestrator for all essay scoring models.
    
    Coordinates the full pipeline: data loading, feature extraction,
    model training, evaluation, and result visualization.
    
    Usage:
        config = Config()
        trainer = Trainer(config)
        trainer.run_full_pipeline()
    """

    def __init__(self, config: Config):
        """
        Initialize the trainer with configuration.
        
        Args:
            config: Config instance with all hyperparameters and paths
        """
        self.config = config
        self.device = get_device()
        self.logger = setup_logging(log_file=os.path.join(config.outputs_dir, "training.log"))

        # Initialize components
        self.data_loader = DataLoader()
        self.text_cleaner = TextCleaner()
        self.evaluator = ModelEvaluator(config)
        self.visualizer = ResultVisualizer(config.graphs_dir)

        # Data storage
        self.train_df = None
        self.val_df = None
        self.test_df = None
        self.handcrafted_features_train = None
        self.handcrafted_features_val = None
        self.handcrafted_features_test = None
        self.feature_names = None

        # Trained models
        self.trained_models = {}
        self.training_histories = {}

        self.logger.info("Trainer initialized successfully")

    @timer_decorator
    def load_and_prepare_data(self, use_sample: bool = False) -> None:
        """
        Load, clean, and split the dataset.
        
        Args:
            use_sample: If True, use synthetic sample data instead of real dataset
        """
        self.logger.info("=" * 60)
        self.logger.info("PHASE 1: Loading and Preparing Data")
        self.logger.info("=" * 60)

        # Load dataset
        if use_sample:
            self.logger.info("Using sample (synthetic) data for testing")
            df = self.data_loader.create_sample_data()
        else:
            self.logger.info(f"Loading dataset from: {self.config.dataset_path}")
            df = self.data_loader.load_dataset(self.config.dataset_path)

        # Display dataset statistics
        stats = self.data_loader.get_dataset_stats(df)
        self.logger.info(f"Total essays loaded: {stats['total_essays']}")
        for essay_set, count in stats.get('essays_per_set', {}).items():
            self.logger.info(f"  Essay Set {essay_set}: {count} essays")

        # Clean text
        self.logger.info("Cleaning essay texts...")
        df = self.text_cleaner.clean_dataframe(df, text_column='essay')

        # Normalize scores
        self.logger.info("Normalizing scores to [0, 1] range...")
        df = self.data_loader.normalize_scores(df, self.config)

        # Split data
        self.logger.info(
            f"Splitting data: {self.config.train_ratio:.0%} train / "
            f"{self.config.val_ratio:.0%} val / {self.config.test_ratio:.0%} test"
        )
        self.train_df, self.val_df, self.test_df = self.data_loader.split_data(
            df,
            train_ratio=self.config.train_ratio,
            val_ratio=self.config.val_ratio,
            test_ratio=self.config.test_ratio,
            seed=self.config.random_seed
        )

        self.logger.info(f"Train: {len(self.train_df)} | Val: {len(self.val_df)} | Test: {len(self.test_df)}")

    @timer_decorator
    def extract_handcrafted_features(self) -> None:
        """
        Extract grammar, readability, and linguistic features for all splits.
        """
        self.logger.info("=" * 60)
        self.logger.info("PHASE 2: Extracting Handcrafted Features")
        self.logger.info("=" * 60)

        grammar = GrammarAnalyzer()
        readability = ReadabilityAnalyzer()
        linguistic = LinguisticAnalyzer()

        def extract_features_for_split(df: pd.DataFrame, split_name: str) -> np.ndarray:
            """Extract all handcrafted features for a data split."""
            self.logger.info(f"Extracting features for {split_name} ({len(df)} essays)...")
            features_list = []
            feature_names = []

            for idx, row in df.iterrows():
                text = row['essay']
                features = {}

                # Grammar features
                try:
                    gram = grammar.analyze(text)
                    features.update({
                        'grammar_error_count': gram.get('grammar_error_count', 0),
                        'spelling_error_count': gram.get('spelling_error_count', 0),
                        'error_rate': gram.get('error_rate', 0),
                        'grammar_score': gram.get('grammar_score', 1.0),
                    })
                except Exception as e:
                    features.update({
                        'grammar_error_count': 0, 'spelling_error_count': 0,
                        'error_rate': 0, 'grammar_score': 1.0,
                    })

                # Readability features
                try:
                    read = readability.analyze(text)
                    features.update({
                        'flesch_reading_ease': read.get('flesch_reading_ease', 50),
                        'flesch_kincaid_grade': read.get('flesch_kincaid_grade', 8),
                        'gunning_fog': read.get('gunning_fog', 10),
                        'smog_index': read.get('smog_index', 8),
                        'coleman_liau_index': read.get('coleman_liau_index', 8),
                        'automated_readability_index': read.get('automated_readability_index', 8),
                        'composite_readability_score': read.get('composite_readability_score', 0.5),
                    })
                except Exception as e:
                    features.update({
                        'flesch_reading_ease': 50, 'flesch_kincaid_grade': 8,
                        'gunning_fog': 10, 'smog_index': 8,
                        'coleman_liau_index': 8, 'automated_readability_index': 8,
                        'composite_readability_score': 0.5,
                    })

                # Linguistic features
                try:
                    ling = linguistic.analyze(text)
                    features.update({
                        'word_count': ling.get('word_count', 0),
                        'sentence_count': ling.get('sentence_count', 0),
                        'avg_word_length': ling.get('avg_word_length', 4),
                        'avg_sentence_length': ling.get('avg_sentence_length', 15),
                        'type_token_ratio': ling.get('type_token_ratio', 0.5),
                        'hapax_legomena_ratio': ling.get('hapax_legomena_ratio', 0.5),
                        'lexical_diversity_mtld': ling.get('lexical_diversity_mtld', 50),
                        'noun_ratio': ling.get('noun_ratio', 0.2),
                        'verb_ratio': ling.get('verb_ratio', 0.15),
                        'adj_ratio': ling.get('adj_ratio', 0.1),
                        'adv_ratio': ling.get('adv_ratio', 0.05),
                        'named_entity_count': ling.get('named_entity_count', 0),
                        'stopword_ratio': ling.get('stopword_ratio', 0.4),
                        'long_word_ratio': ling.get('long_word_ratio', 0.2),
                        'vocabulary_richness_score': ling.get('vocabulary_richness_score', 0.5),
                    })
                except Exception as e:
                    features.update({
                        'word_count': 0, 'sentence_count': 0,
                        'avg_word_length': 4, 'avg_sentence_length': 15,
                        'type_token_ratio': 0.5, 'hapax_legomena_ratio': 0.5,
                        'lexical_diversity_mtld': 50, 'noun_ratio': 0.2,
                        'verb_ratio': 0.15, 'adj_ratio': 0.1, 'adv_ratio': 0.05,
                        'named_entity_count': 0, 'stopword_ratio': 0.4,
                        'long_word_ratio': 0.2, 'vocabulary_richness_score': 0.5,
                    })

                features_list.append(features)

            # Convert to DataFrame then numpy array
            features_df = pd.DataFrame(features_list)
            feature_names = list(features_df.columns)
            return features_df.values, feature_names

        # Extract for all splits
        self.handcrafted_features_train, self.feature_names = extract_features_for_split(
            self.train_df, "train"
        )
        self.handcrafted_features_val, _ = extract_features_for_split(
            self.val_df, "validation"
        )
        self.handcrafted_features_test, _ = extract_features_for_split(
            self.test_df, "test"
        )

        self.logger.info(f"Extracted {len(self.feature_names)} handcrafted features per essay")
        self.logger.info(f"Features: {', '.join(self.feature_names[:10])}...")

        # Replace NaN with 0
        self.handcrafted_features_train = np.nan_to_num(self.handcrafted_features_train, 0)
        self.handcrafted_features_val = np.nan_to_num(self.handcrafted_features_val, 0)
        self.handcrafted_features_test = np.nan_to_num(self.handcrafted_features_test, 0)

    @timer_decorator
    def train_baseline_models(self) -> None:
        """
        Train Linear Regression and Random Forest baselines on handcrafted features.
        """
        self.logger.info("-" * 40)
        self.logger.info("Training Baseline Models")
        self.logger.info("-" * 40)

        from models.baseline_models import LinearRegressionScorer, RandomForestScorer, CARTScorer

        y_train = self.train_df['normalized_score'].values
        y_val = self.val_df['normalized_score'].values

        # --- Linear Regression ---
        self.logger.info("Training Linear Regression...")
        lr_model = LinearRegressionScorer()
        lr_model.train(self.handcrafted_features_train, y_train)
        lr_pred_val = lr_model.predict(self.handcrafted_features_val)
        lr_metrics = compute_all_metrics(y_val, lr_pred_val)
        self.logger.info(f"  Val QWK: {lr_metrics.get('qwk', 0):.4f} | MAE: {lr_metrics.get('mae', 0):.4f}")

        self.trained_models['linear_regression'] = lr_model
        lr_model.save(os.path.join(self.config.models_dir, "linear_regression.pkl"))

        # --- Random Forest ---
        self.logger.info("Training Random Forest...")
        rf_model = RandomForestScorer(
            n_estimators=self.config.rf_n_estimators,
            max_depth=self.config.rf_max_depth,
            min_samples_split=self.config.rf_min_samples_split
        )
        rf_model.train(self.handcrafted_features_train, y_train)
        rf_pred_val = rf_model.predict(self.handcrafted_features_val)
        rf_metrics = compute_all_metrics(y_val, rf_pred_val)
        self.logger.info(f"  Val QWK: {rf_metrics.get('qwk', 0):.4f} | MAE: {rf_metrics.get('mae', 0):.4f}")

        self.trained_models['random_forest'] = rf_model
        rf_model.save(os.path.join(self.config.models_dir, "random_forest.pkl"))

        # --- CART (Decision Tree) ---
        self.logger.info("Training CART (Decision Tree)...")
        cart_model = CARTScorer(
            max_depth=self.config.cart_max_depth,
            min_samples_split=self.config.cart_min_samples_split,
            min_samples_leaf=self.config.cart_min_samples_leaf,
        )
        cart_model.train(self.handcrafted_features_train, y_train)
        cart_pred_val = cart_model.predict(self.handcrafted_features_val)
        cart_metrics = compute_all_metrics(y_val, cart_pred_val)
        self.logger.info(f"  Val QWK: {cart_metrics.get('qwk', 0):.4f} | MAE: {cart_metrics.get('mae', 0):.4f}")

        self.trained_models['cart'] = cart_model
        cart_model.save(os.path.join(self.config.models_dir, "cart.pkl"))

    @timer_decorator
    def train_lstm_model(self) -> None:
        """Train BiLSTM with Attention model."""
        self.logger.info("-" * 40)
        self.logger.info("Training BiLSTM + Attention Model")
        self.logger.info("-" * 40)

        from models.lstm_model import LSTMScorer

        train_texts = self.train_df['essay'].tolist()
        train_scores = self.train_df['normalized_score'].values
        val_texts = self.val_df['essay'].tolist()
        val_scores = self.val_df['normalized_score'].values

        lstm_model = LSTMScorer(self.config)
        history = lstm_model.train(
            train_texts, train_scores,
            val_texts, val_scores,
            epochs=self.config.epochs,
            batch_size=self.config.batch_size
        )

        self.trained_models['lstm'] = lstm_model
        self.training_histories['lstm'] = history
        lstm_model.save(os.path.join(self.config.models_dir, "lstm_model"))

        val_pred = lstm_model.predict(val_texts)
        metrics = compute_all_metrics(val_scores, val_pred)
        self.logger.info(f"  Val QWK: {metrics.get('qwk', 0):.4f} | MAE: {metrics.get('mae', 0):.4f}")

    @timer_decorator
    def train_bert_model(self) -> None:
        """Train fine-tuned BERT model."""
        self.logger.info("-" * 40)
        self.logger.info("Training BERT (Fine-tuned) Model")
        self.logger.info("-" * 40)

        from models.bert_model import BERTScorer

        train_texts = self.train_df['essay'].tolist()
        train_scores = self.train_df['normalized_score'].values
        val_texts = self.val_df['essay'].tolist()
        val_scores = self.val_df['normalized_score'].values

        bert_model = BERTScorer(self.config, device=self.device)
        history = bert_model.train(train_texts, train_scores, val_texts, val_scores)

        self.trained_models['bert'] = bert_model
        self.training_histories['bert'] = history
        bert_model.save(os.path.join(self.config.models_dir, "bert_model"))

        val_pred = bert_model.predict(val_texts)
        metrics = compute_all_metrics(val_scores, val_pred)
        self.logger.info(f"  Val QWK: {metrics.get('qwk', 0):.4f} | MAE: {metrics.get('mae', 0):.4f}")

    @timer_decorator
    def train_roberta_model(self) -> None:
        """Train fine-tuned RoBERTa model."""
        self.logger.info("-" * 40)
        self.logger.info("Training RoBERTa (Fine-tuned) Model")
        self.logger.info("-" * 40)

        from models.roberta_model import RoBERTaScorer

        train_texts = self.train_df['essay'].tolist()
        train_scores = self.train_df['normalized_score'].values
        val_texts = self.val_df['essay'].tolist()
        val_scores = self.val_df['normalized_score'].values

        roberta_model = RoBERTaScorer(self.config, device=self.device)
        history = roberta_model.train(train_texts, train_scores, val_texts, val_scores)

        self.trained_models['roberta'] = roberta_model
        self.training_histories['roberta'] = history
        roberta_model.save(os.path.join(self.config.models_dir, "roberta_model"))

        val_pred = roberta_model.predict(val_texts)
        metrics = compute_all_metrics(val_scores, val_pred)
        self.logger.info(f"  Val QWK: {metrics.get('qwk', 0):.4f} | MAE: {metrics.get('mae', 0):.4f}")

    @timer_decorator
    def train_hybrid_model(self) -> None:
        """Train the proposed Hybrid model (RoBERTa + Features + XGBoost)."""
        self.logger.info("-" * 40)
        self.logger.info("Training Hybrid Model (RoBERTa + Features + XGBoost) ⭐")
        self.logger.info("-" * 40)

        from models.hybrid_model import HybridScorer

        train_texts = self.train_df['essay'].tolist()
        train_scores = self.train_df['normalized_score'].values
        val_texts = self.val_df['essay'].tolist()
        val_scores = self.val_df['normalized_score'].values
        train_sets = self.train_df['essay_set'].values
        val_sets = self.val_df['essay_set'].values

        hybrid_model = HybridScorer(self.config)
        history = hybrid_model.train(
            train_texts, train_scores,
            val_texts, val_scores,
            train_essay_sets=train_sets,
            val_essay_sets=val_sets
        )

        self.trained_models['hybrid'] = hybrid_model
        self.training_histories['hybrid'] = history
        hybrid_model.save(os.path.join(self.config.models_dir, "hybrid_model"))

        val_pred = hybrid_model.predict(val_texts)
        metrics = compute_all_metrics(val_scores, val_pred)
        self.logger.info(f"  Val QWK: {metrics.get('qwk', 0):.4f} | MAE: {metrics.get('mae', 0):.4f}")

    @timer_decorator
    def evaluate_all_models(self) -> pd.DataFrame:
        """
        Evaluate all trained models on the test set and generate comparison.
        
        Returns:
            DataFrame with comparison results
        """
        self.logger.info("=" * 60)
        self.logger.info("PHASE 4: Evaluating All Models on Test Set")
        self.logger.info("=" * 60)

        y_test = self.test_df['normalized_score'].values
        test_texts = self.test_df['essay'].tolist()
        test_sets = self.test_df['essay_set'].values

        results = {}

        for model_name, model in self.trained_models.items():
            self.logger.info(f"Evaluating {self.config.model_names.get(model_name, model_name)}...")

            # Get predictions
            if model_name in ['linear_regression', 'random_forest', 'cart']:
                y_pred = model.predict(self.handcrafted_features_test)
            elif model_name in ['lstm', 'bert', 'roberta']:
                y_pred = model.predict(test_texts)
            elif model_name == 'hybrid':
                y_pred = model.predict(test_texts)
            else:
                continue

            # Compute metrics
            metrics = self.evaluator.evaluate_model(model_name, y_test, y_pred, test_sets)
            results[model_name] = metrics

            self.logger.info(
                f"  QWK: {metrics.get('qwk', 0):.4f} | "
                f"MAE: {metrics.get('mae', 0):.4f} | "
                f"RMSE: {metrics.get('rmse', 0):.4f} | "
                f"Pearson: {metrics.get('pearson', 0):.4f}"
            )

        # Generate comparison table
        comparison_df = self.evaluator.get_comparison_table()
        self.logger.info("\n" + comparison_df.to_string())

        # Save results
        self.evaluator.save_results(os.path.join(self.config.results_dir, "evaluation_results.json"))

        return comparison_df

    @timer_decorator
    def generate_visualizations(self) -> None:
        """Generate all comparison charts and plots."""
        self.logger.info("=" * 60)
        self.logger.info("PHASE 5: Generating Visualizations")
        self.logger.info("=" * 60)

        comparison_df = self.evaluator.get_comparison_table()

        # Model comparison charts
        self.visualizer.plot_model_comparison(comparison_df, metric='qwk')
        self.visualizer.plot_all_metrics_comparison(comparison_df)

        # Training history plots
        for model_name, history in self.training_histories.items():
            self.visualizer.plot_training_history(history, model_name)

        # Predicted vs Actual for each model
        y_test = self.test_df['normalized_score'].values
        test_texts = self.test_df['essay'].tolist()

        for model_name, model in self.trained_models.items():
            try:
                if model_name in ['linear_regression', 'random_forest', 'cart']:
                    y_pred = model.predict(self.handcrafted_features_test)
                else:
                    y_pred = model.predict(test_texts)
                self.visualizer.plot_predicted_vs_actual(y_test, y_pred, model_name)
                self.visualizer.plot_residual_distribution(y_test, y_pred, model_name)
            except Exception as e:
                self.logger.warning(f"Could not generate plots for {model_name}: {e}")

        self.logger.info(f"Visualizations saved to: {self.config.graphs_dir}")

    @timer_decorator
    def run_full_pipeline(
        self,
        use_sample: bool = False,
        models_to_train: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Run the complete training and evaluation pipeline.
        
        Args:
            use_sample: If True, use synthetic sample data
            models_to_train: List of model names to train.
                              Options: 'linear_regression', 'random_forest', 'cart',
                              'lstm', 'bert', 'roberta', 'hybrid', 'all'
                             Default: all models
                             
        Returns:
            Comparison DataFrame with evaluation results
        """
        set_seed(self.config.random_seed)

        if models_to_train is None or 'all' in models_to_train:
            models_to_train = [
                'linear_regression', 'random_forest', 'cart',
                'lstm', 'bert', 'roberta', 'hybrid'
            ]

        self.logger.info("🚀 Starting Full Training Pipeline")
        self.logger.info(f"Models to train: {', '.join(models_to_train)}")

        # Phase 1: Data
        self.load_and_prepare_data(use_sample=use_sample)

        # Phase 2: Features
        self.extract_handcrafted_features()

        # Phase 3: Training
        self.logger.info("=" * 60)
        self.logger.info("PHASE 3: Training Models")
        self.logger.info("=" * 60)

        model_train_functions = {
            'linear_regression': self.train_baseline_models,
            'random_forest': self.train_baseline_models,
            'cart': self.train_baseline_models,
            'lstm': self.train_lstm_model,
            'bert': self.train_bert_model,
            'roberta': self.train_roberta_model,
            'hybrid': self.train_hybrid_model,
        }

        # Track which functions we've already called (baselines share one function)
        called_functions = set()
        for model_name in models_to_train:
            func = model_train_functions.get(model_name)
            if func and id(func) not in called_functions:
                try:
                    func()
                    called_functions.add(id(func))
                except Exception as e:
                    self.logger.error(f"Failed to train {model_name}: {e}")
                    import traceback
                    traceback.print_exc()

        # Phase 4: Evaluation
        comparison_df = self.evaluate_all_models()

        # Phase 5: Visualizations
        self.generate_visualizations()

        # Summary
        best_model = self.evaluator.get_best_model()
        self.logger.info("=" * 60)
        self.logger.info("🏆 TRAINING COMPLETE")
        self.logger.info(f"Best Model: {self.config.model_names.get(best_model, best_model)}")
        self.logger.info(f"Results saved to: {self.config.results_dir}")
        self.logger.info(f"Graphs saved to: {self.config.graphs_dir}")
        self.logger.info(f"Models saved to: {self.config.models_dir}")
        self.logger.info("=" * 60)

        return comparison_df
