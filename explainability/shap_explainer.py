# ============================================================
# explainability/shap_explainer.py
# SHAP Explainer Module for Hybrid Model
# ============================================================
# Connects to the hybrid model's XGBoost regressor, computes
# Shapley values (using TreeSHAP), and generates visualizations
# (waterfall, summary, bar) and Plotly representations.
# ============================================================

import os
import sys
import logging
from typing import Dict, List, Optional, Tuple, Union, Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import shap
import plotly.graph_objects as go

# --------------- Project Imports ---------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from utils.helpers import ensure_dir

# --------------- Logger ---------------
logger = logging.getLogger("EssayScoringAI.SHAPExplainer")


class SHAPExplainer:
    """
    Wrapper for SHAP explainability on XGBoost hybrid essay scorer models.
    Supports local file saving and Streamlit HTML/Plotly rendering.
    """

    def __init__(
        self,
        model: Any,
        feature_names: List[str],
        background_data: Optional[np.ndarray] = None
    ):
        """
        Args:
            model: Trained model (expected to be XGBoost or compatible).
            feature_names: List of all feature names in training order.
            background_data: Representative background dataset for KernelSHAP.
        """
        self.model = model
        self.feature_names = feature_names
        
        # Determine explainer type
        # For XGBoost, we use TreeExplainer (extremely fast, exact)
        # For general models, fallback to KernelExplainer
        try:
            from xgboost import XGBRegressor
            if isinstance(model, XGBRegressor) or hasattr(model, "get_booster"):
                self.explainer = shap.TreeExplainer(model)
                self.explainer_type = "tree"
            else:
                self.explainer_type = "kernel"
        except ImportError:
            self.explainer_type = "kernel"
            
        if self.explainer_type == "kernel":
            logger.info("Initializing KernelExplainer (this may be slower)...")
            # If no background data is provided, use dummy zeros
            if background_data is None:
                background_data = np.zeros((1, len(feature_names)))
            # Truncate background data size to keep it fast
            if len(background_data) > 50:
                background_data = shap.kmeans(background_data, 50)
            self.explainer = shap.KernelExplainer(model.predict, background_data)
        else:
            logger.info("TreeExplainer successfully initialized for XGBoost model.")

    def explain_single(self, features_array: np.ndarray) -> Dict[str, Any]:
        """
        Explain a single essay prediction.
        
        Args:
            features_array: 1D array of shape (num_features,)
            
        Returns:
            Dict containing:
                - 'shap_values': SHAP values (num_features,)
                - 'base_value': Expected model output (float)
                - 'feature_contributions': List of (feature_name, shap_value) sorted by impact
        """
        # Ensure 2D shape (1, num_features)
        X = features_array.reshape(1, -1)
        
        # Calculate SHAP values
        shap_values_raw = self.explainer.shap_values(X)
        
        # Handle shape differences between shap versions and explainers
        if isinstance(shap_values_raw, list):
            # For classification or multi-output models, select first output
            shap_values = shap_values_raw[0][0]
        elif len(shap_values_raw.shape) == 3:
            shap_values = shap_values_raw[0, :, 0]
        elif len(shap_values_raw.shape) == 2:
            shap_values = shap_values_raw[0]
        else:
            shap_values = shap_values_raw
            
        # Get base value
        if hasattr(self.explainer, "expected_value"):
            base_value = self.explainer.expected_value
            if isinstance(base_value, (list, np.ndarray)):
                base_value = float(base_value[0])
        else:
            base_value = 0.5  # default fallback
            
        # Map feature names to contributions
        contributions = []
        for name, val in zip(self.feature_names, shap_values):
            contributions.append((name, float(val)))
            
        # Sort contributions by absolute value (descending)
        contributions.sort(key=lambda x: abs(x[1]), reverse=True)
        
        return {
            "shap_values": shap_values,
            "base_value": float(base_value),
            "feature_contributions": contributions
        }

    def explain_batch(self, features_array: np.ndarray, max_samples: int = 100) -> np.ndarray:
        """
        Explain predictions for a batch of essays.
        """
        X = features_array[:max_samples]
        shap_values = self.explainer.shap_values(X)
        return shap_values

    def get_top_features(self, features_array: np.ndarray, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Return the top-K features with the highest absolute influence on this prediction.
        """
        explanation = self.explain_single(features_array)
        return explanation["feature_contributions"][:top_k]

    def plot_waterfall(self, features_array: np.ndarray, save_path: Optional[str] = None) -> plt.Figure:
        """
        Generate a SHAP waterfall plot for a single prediction.
        """
        explanation = self.explain_single(features_array)
        shap_val = explanation["shap_values"]
        base_val = explanation["base_value"]
        
        # Build a Explanation object for newer SHAP versions
        exp = shap.Explanation(
            values=shap_val,
            base_values=base_val,
            data=features_array,
            feature_names=self.feature_names
        )
        
        fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
        shap.plots.waterfall(exp, max_display=10, show=False)
        plt.tight_layout()
        
        if save_path:
            ensure_dir(os.path.dirname(save_path))
            plt.savefig(save_path, bbox_inches='tight')
            plt.close(fig)
            
        return fig

    def plot_summary(self, features_array: np.ndarray, save_path: Optional[str] = None) -> plt.Figure:
        """
        Generate a SHAP summary plot (beeswarm).
        """
        fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
        shap.summary_plot(
            self.explainer.shap_values(features_array),
            features_array,
            feature_names=self.feature_names,
            show=False
        )
        plt.tight_layout()
        
        if save_path:
            ensure_dir(os.path.dirname(save_path))
            plt.savefig(save_path, bbox_inches='tight')
            plt.close(fig)
            
        return fig

    def create_plotly_waterfall(self, features_array: np.ndarray) -> go.Figure:
        """
        Generate an interactive Plotly waterfall chart representing SHAP values.
        Suitable for embedding directly into Streamlit UI.
        
        Args:
            features_array: 1D array of shape (num_features,)
            
        Returns:
            Plotly Figure object
        """
        explanation = self.explain_single(features_array)
        base_val = explanation["base_value"]
        shap_vals = explanation["shap_values"]
        
        # Sort features by absolute contribution, keeping top 10
        pairs = list(zip(self.feature_names, shap_vals, features_array))
        pairs.sort(key=lambda x: abs(x[1]), reverse=True)
        top_pairs = pairs[:9]  # Take top 9
        
        # Remaining features get combined into 'Other Features'
        other_shap = sum(p[1] for p in pairs[9:])
        
        # Prepare Plotly lists
        # We start with the base value, add individual steps, and end at predicted score
        x_labels = ["Base Value"]
        y_values = [base_val]
        measures = ["absolute"]
        text_labels = [f"{base_val:.4f}"]
        
        running_sum = base_val
        for name, val, raw in top_pairs:
            disp_name = name.replace('_', ' ').title()
            # Show a snippet of raw value if it is handcrafted
            if "pca" not in name.lower() and isinstance(raw, (int, float)):
                x_labels.append(f"{disp_name} ({raw:.1f})")
            else:
                x_labels.append(disp_name)
            y_values.append(val)
            measures.append("relative")
            running_sum += val
            text_labels.append(f"{val:+.4f}")
            
        if len(pairs) > 9:
            x_labels.append("Other Features")
            y_values.append(other_shap)
            measures.append("relative")
            running_sum += other_shap
            text_labels.append(f"{other_shap:+.4f}")
            
        # Final prediction score
        x_labels.append("Predicted Score")
        y_values.append(running_sum)
        measures.append("total")
        text_labels.append(f"{running_sum:.4f}")
        
        # Build Figure
        fig = go.Figure(go.Waterfall(
            name="SHAP",
            orientation="v",
            measure=measures,
            x=x_labels,
            textposition="outside",
            text=text_labels,
            y=y_values,
            connector={"line": {"color": "rgb(63, 63, 63)"}},
            decreasing={"marker": {"color": "#ff6b6b"}},
            increasing={"marker": {"color": "#38ef7d"}},
            totals={"marker": {"color": "#667eea"}},
        ))
        
        fig.update_layout(
            title="SHAP Attribution (Waterfall Chart)",
            xaxis_title="Features",
            yaxis_title="Model Output Score [0, 1]",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter", color="#ccc"),
            height=500,
            margin=dict(l=20, r=20, t=50, b=100)
        )
        
        return fig
