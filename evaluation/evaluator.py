# ============================================================
# evaluation/evaluator.py
# Model Evaluator Module
# ============================================================
# Manages scoring predictions across all models, aggregates
# metrics, constructs comparison reports, and saves/loads results.
# ============================================================

import os
import sys
import json
import logging
from typing import Dict, List, Optional, Union, Any

import numpy as np
import pandas as pd

# --------------- Project Imports ---------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from training.config import Config
from evaluation.metrics import compute_all_metrics, compute_per_set_metrics

# --------------- Logger ---------------
logger = logging.getLogger("EssayScoringAI.Evaluator")


class ModelEvaluator:
    """
    Evaluator to compare performance of different essay scoring models.
    
    Stores evaluation metrics for multiple models, generates tabular comparisons,
    and supports saving/loading results for documentation and dashboards.
    """

    def __init__(self, config: Config):
        """
        Args:
            config: Central Config instance.
        """
        self.config = config
        self.results: Dict[str, Dict[str, Any]] = {}
        self.per_set_results: Dict[str, Dict[int, Dict[str, float]]] = {}

    def evaluate_model(
        self,
        model_name: str,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        essay_sets: np.ndarray
    ) -> Dict[str, float]:
        """
        Evaluate a single model's predictions.
        
        Args:
            model_name: Identifier for the model (e.g. 'hybrid', 'bert')
            y_true: Ground truth normalized scores in [0, 1]
            y_pred: Predicted normalized scores in [0, 1]
            essay_sets: Array of essay set IDs (1-8) matching the scores
            
        Returns:
            Dict containing overall metrics
        """
        logger.info("Evaluating model: %s", model_name)
        
        # 1. Compute per-set metrics (which denormalizes back to original score ranges)
        per_set = compute_per_set_metrics(y_true, y_pred, essay_sets, self.config)
        self.per_set_results[model_name] = per_set
        
        # 2. Compute overall metrics
        # Overall QWK is calculated by compiling the raw scores across all sets
        y_true_raw = np.array([self.config.denormalize_score(val, essay_sets[i]) for i, val in enumerate(y_true)])
        y_pred_raw = np.array([self.config.denormalize_score(val, essay_sets[i]) for i, val in enumerate(y_pred)])
        
        # Since ranges differ, we compute overall QWK by finding the mean of QWKs per set, 
        # which is the standard methodology in ASAP essay scoring literature.
        qwk_values = [metrics["qwk"] for metrics in per_set.values()]
        mean_qwk = float(np.mean(qwk_values)) if qwk_values else 0.0
        
        # Traditional regression metrics can be computed directly on the normalized [0, 1] range
        mae = float(np.mean(np.abs(y_true - y_pred)))
        rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
        
        # Correlation
        if len(y_true) >= 2:
            from scipy.stats import pearsonr
            try:
                corr, _ = pearsonr(y_true, y_pred)
                pearson = float(corr) if not np.isnan(corr) else 0.0
            except Exception:
                pearson = 0.0
        else:
            pearson = 0.0
            
        overall_metrics = {
            "qwk": mean_qwk,  # Mean of per-prompt QWKs (standard ASAP benchmark metric)
            "mae": mae,
            "rmse": rmse,
            "pearson": pearson
        }
        
        self.results[model_name] = overall_metrics
        return overall_metrics

    def get_comparison_table(self) -> pd.DataFrame:
        """
        Generate a comparison table comparing all evaluated models.
        
        Returns:
            Pandas DataFrame containing model metrics.
        """
        if not self.results:
            return pd.DataFrame()
            
        rows = []
        for model_name, metrics in self.results.items():
            display_name = self.config.model_names.get(model_name, model_name)
            row = {
                "Model ID": model_name,
                "Model Name": display_name,
                "Mean QWK": round(metrics["qwk"], 4),
                "MAE (Norm)": round(metrics["mae"], 4),
                "RMSE (Norm)": round(metrics["rmse"], 4),
                "Pearson Corr": round(metrics["pearson"], 4)
            }
            rows.append(row)
            
        df = pd.DataFrame(rows)
        return df.sort_values(by="Mean QWK", ascending=False).reset_index(drop=True)

    def get_best_model(self) -> str:
        """
        Return the model name (ID) with the highest Mean QWK.
        """
        if not self.results:
            raise ValueError("No models have been evaluated yet.")
            
        best_model = max(self.results.keys(), key=lambda k: self.results[k]["qwk"])
        return best_model

    def save_results(self, path: str) -> None:
        """
        Save results to a JSON file.
        """
        output_data = {
            "overall": self.results,
            "per_set": {model: {str(k): v for k, v in val.items()} for model, val in self.per_set_results.items()}
        }
        
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=4)
            logger.info("Evaluation results saved to %s", path)
        except Exception as e:
            logger.error("Failed to save results: %s", e)

    def load_results(self, path: str) -> None:
        """
        Load results from a JSON file.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Results file not found: {path}")
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            self.results = data.get("overall", {})
            
            # Reconstruct per-set results mapping keys back to integers
            per_set_raw = data.get("per_set", {})
            self.per_set_results = {}
            for model, sets in per_set_raw.items():
                self.per_set_results[model] = {int(k): v for k, v in sets.items()}
                
            logger.info("Evaluation results loaded from %s", path)
        except Exception as e:
            logger.error("Failed to load results: %s", e)
            raise
