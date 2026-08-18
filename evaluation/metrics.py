# ============================================================
# evaluation/metrics.py
# Standard Evaluation Metrics for Essay Scoring
# ============================================================
# Implements QWK (Quadratic Weighted Kappa) from scratch,
# alongside standard regression metrics (MAE, RMSE, Pearson).
# Supports calculation per essay set and overall.
# ============================================================

import os
import sys
import numpy as np
from scipy.stats import pearsonr
from typing import Dict, Union

# --------------- Project Imports ---------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def quadratic_weighted_kappa(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    min_score: int,
    max_score: int
) -> float:
    """
    Compute the Quadratic Weighted Kappa (QWK) between true and predicted ratings.
    
    QWK measures the agreement between two raters, factoring in the scale of disagreement.
    
    Args:
        y_true: True ratings (integer array)
        y_pred: Predicted ratings (integer or float array, will be rounded)
        min_score: Minimum possible rating score
        max_score: Maximum possible rating score
        
    Returns:
        The QWK score in range [-1, 1], where 1 is perfect agreement.
    """
    # Round predictions and cast to integers
    y_true = np.asarray(y_true, dtype=np.int32)
    y_pred = np.asarray(np.round(y_pred), dtype=np.int32)
    
    # Clip values to valid range just in case
    y_true = np.clip(y_true, min_score, max_score)
    y_pred = np.clip(y_pred, min_score, max_score)
    
    # Shift values to start from 0 for index mapping
    y_true = y_true - min_score
    y_pred = y_pred - min_score
    
    num_ratings = max_score - min_score + 1
    
    if num_ratings <= 1:
        return 1.0
        
    # 1. Compute Confusion Matrix (Observed Agreement Matrix)
    observed = np.zeros((num_ratings, num_ratings), dtype=np.float64)
    for t, p in zip(y_true, y_pred):
        observed[t, p] += 1.0
        
    # 2. Compute Expected Agreement Matrix
    # Vector of true score counts
    hist_true = np.zeros(num_ratings, dtype=np.float64)
    for t in y_true:
        hist_true[t] += 1.0
        
    # Vector of predicted score counts
    hist_pred = np.zeros(num_ratings, dtype=np.float64)
    for p in y_pred:
        hist_pred[p] += 1.0
        
    # Expected matrix is the outer product normalized by sum
    total_elements = len(y_true)
    expected = np.outer(hist_true, hist_pred) / float(total_elements)
    
    # 3. Compute Weight Matrix (Quadratic Weights)
    weights = np.zeros((num_ratings, num_ratings), dtype=np.float64)
    for i in range(num_ratings):
        for j in range(num_ratings):
            weights[i, j] = float((i - j) ** 2) / float((num_ratings - 1) ** 2)
            
    # 4. Compute QWK
    numerator = np.sum(weights * observed)
    denominator = np.sum(weights * expected)
    
    if denominator == 0:
        return 1.0 if numerator == 0 else 0.0
        
    qwk = 1.0 - (numerator / denominator)
    return float(qwk)


def compute_mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Compute Mean Absolute Error."""
    return float(np.mean(np.abs(y_true - y_pred)))


def compute_rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Compute Root Mean Squared Error."""
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def compute_pearson(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Compute Pearson Correlation Coefficient."""
    if len(y_true) < 2:
        return 0.0
    try:
        corr, _ = pearsonr(y_true, y_pred)
        if np.isnan(corr):
            return 0.0
        return float(corr)
    except Exception:
        return 0.0


def compute_all_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    min_score: int = 0,
    max_score: int = 1
) -> Dict[str, float]:
    """
    Compute all evaluation metrics.
    If predictions are normalized in [0, 1], this measures raw regression performance.
    
    Args:
        y_true: Array of true scores
        y_pred: Array of predicted scores
        min_score: Minimum score on the target scale (for QWK)
        max_score: Maximum score on the target scale (for QWK)
        
    Returns:
        Dict of metric names mapped to their values
    """
    # For general regression (overall or per set normalized)
    mae = compute_mae(y_true, y_pred)
    rmse = compute_rmse(y_true, y_pred)
    pearson = compute_pearson(y_true, y_pred)
    
    # QWK is scale-sensitive, so we pass rounded/original range values.
    # If values are normalized, QWK is still calculated on integers.
    qwk = quadratic_weighted_kappa(y_true, y_pred, min_score, max_score)
    
    return {
        "qwk": qwk,
        "mae": mae,
        "rmse": rmse,
        "pearson": pearson
    }


def compute_per_set_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    essay_sets: np.ndarray,
    config
) -> Dict[int, Dict[str, float]]:
    """
    Compute metrics separately for each essay set, using original score ranges.
    
    Args:
        y_true: True normalized scores [0, 1]
        y_pred: Predicted normalized scores [0, 1]
        essay_sets: Array of essay set IDs (1-8)
        config: Config instance with score_ranges
        
    Returns:
        Dict mapping essay_set_id -> dict of metrics
    """
    per_set_results = {}
    unique_sets = np.unique(essay_sets)
    
    for essay_set in unique_sets:
        mask = (essay_sets == essay_set)
        if not np.any(mask):
            continue
            
        y_true_subset_norm = y_true[mask]
        y_pred_subset_norm = y_pred[mask]
        
        # Denormalize to get scores back on the correct integer scales
        y_true_raw = np.array([config.denormalize_score(val, essay_set) for val in y_true_subset_norm])
        y_pred_raw = np.array([config.denormalize_score(val, essay_set) for val in y_pred_subset_norm])
        
        min_score, max_score = config.score_ranges[essay_set]
        
        metrics = compute_all_metrics(
            y_true=y_true_raw,
            y_pred=y_pred_raw,
            min_score=min_score,
            max_score=max_score
        )
        
        # Add normalized regression metrics for reference
        metrics["normalized_mae"] = compute_mae(y_true_subset_norm, y_pred_subset_norm)
        metrics["normalized_rmse"] = compute_rmse(y_true_subset_norm, y_pred_subset_norm)
        
        per_set_results[int(essay_set)] = metrics
        
    return per_set_results
