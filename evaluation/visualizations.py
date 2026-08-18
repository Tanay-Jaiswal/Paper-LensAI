# ============================================================
# evaluation/visualizations.py
# Visualization Suite for Essay Scoring Results
# ============================================================
# Generates professional comparison charts, error heatmaps,
# confusion matrices, and training history plots.
# Also provides Plotly helpers for Streamlit.
# ============================================================

import os
import sys
import logging
from typing import Dict, List, Optional, Union, Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px

# --------------- Project Imports ---------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from training.config import Config
from utils.helpers import ensure_dir

# --------------- Logger ---------------
logger = logging.getLogger("EssayScoringAI.Visualizer")

# Set styling for matplotlib
try:
    plt.style.use('seaborn-v0_8-whitegrid')
except Exception:
    try:
        plt.style.use('seaborn-whitegrid')
    except Exception:
        pass

sns.set_theme(style="whitegrid", context="talk")


class ResultVisualizer:
    """
    Visualization engine for generating plots of training and evaluation metrics.
    Supports offline matplotlib output and interactive Plotly figures.
    """

    def __init__(self, save_dir: str):
        """
        Args:
            save_dir: Directory where generated image files will be saved.
        """
        self.save_dir = ensure_dir(save_dir)
        logger.info("Visualizer initialized. Saving plots to: %s", save_dir)

    def plot_model_comparison(
        self,
        results_df: pd.DataFrame,
        metric: str = 'qwk',
        save: bool = True
    ) -> plt.Figure:
        """
        Create a bar chart comparing models on a specific metric.
        
        Args:
            results_df: Tabular results from ModelEvaluator.get_comparison_table()
            metric: Key to plot (e.g. 'Mean QWK' or 'MAE (Norm)')
            save: Whether to save to disk
            
        Returns:
            Matplotlib Figure object
        """
        # Map metric argument to column name
        col_map = {
            'qwk': 'Mean QWK',
            'mae': 'MAE (Norm)',
            'rmse': 'RMSE (Norm)',
            'pearson': 'Pearson Corr'
        }
        metric_col = col_map.get(metric.lower(), metric)
        if metric_col not in results_df.columns:
            # Fallback to whatever matches
            metric_col = results_df.columns[2]

        fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
        
        # Draw bars
        colors = sns.color_palette("viridis", len(results_df))
        bars = ax.bar(results_df["Model Name"], results_df[metric_col], color=colors, edgecolor='grey', alpha=0.95)
        
        # Annotate values on top of bars
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.4f}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=12, fontweight='bold')
                        
        ax.set_title(f"Model Comparison: {metric_col}", fontsize=18, pad=15)
        ax.set_ylabel(metric_col, fontsize=14)
        ax.set_xlabel("Model Architecture", fontsize=14)
        plt.xticks(rotation=15, ha='right')
        plt.tight_layout()
        
        if save:
            save_path = os.path.join(self.save_dir, f"model_comparison_{metric.lower()}.png")
            plt.savefig(save_path, bbox_inches='tight')
            plt.close(fig)
            logger.info("Saved model comparison plot to %s", save_path)
            
        return fig

    def plot_all_metrics_comparison(
        self,
        results_df: pd.DataFrame,
        save: bool = True
    ) -> plt.Figure:
        """
        Grouped bar chart displaying QWK, MAE, RMSE, Pearson for all models.
        """
        if results_df.empty:
            return None
            
        # Melt dataframe for seaborn plotting
        melted = results_df.melt(
            id_vars=["Model Name"],
            value_vars=["Mean QWK", "MAE (Norm)", "RMSE (Norm)", "Pearson Corr"],
            var_name="Metric",
            value_name="Value"
        )
        
        fig, ax = plt.subplots(figsize=(14, 8), dpi=150)
        sns.barplot(
            data=melted,
            x="Model Name",
            y="Value",
            hue="Metric",
            palette="muted",
            ax=ax
        )
        
        ax.set_title("Overall Performance Summary Across Metrics", fontsize=18, pad=15)
        ax.set_xlabel("Model Name", fontsize=14)
        ax.set_ylabel("Metric Value", fontsize=14)
        plt.xticks(rotation=15, ha='right')
        plt.legend(title="Metric", bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        
        if save:
            save_path = os.path.join(self.save_dir, "model_comparison_all_metrics.png")
            plt.savefig(save_path, bbox_inches='tight')
            plt.close(fig)
            
        return fig

    def plot_per_set_performance(
        self,
        per_set_results: Dict[str, Dict[int, Dict[str, float]]],
        save: bool = True
    ) -> plt.Figure:
        """
        Heatmap comparing models (rows) against essay sets (columns) for QWK.
        """
        if not per_set_results:
            return None
            
        # Reshape data into a matrix
        matrix_data = {}
        for model_name, sets in per_set_results.items():
            model_disp = model_name.replace('_', ' ').title()
            matrix_data[model_disp] = {set_id: metrics["qwk"] for set_id, metrics in sets.items()}
            
        df = pd.DataFrame(matrix_data).T  # Models as rows, sets as columns
        df.columns = [f"Set {c}" for c in df.columns]
        
        fig, ax = plt.subplots(figsize=(12, 6), dpi=150)
        sns.heatmap(
            df,
            annot=True,
            cmap="YlGnBu",
            fmt=".3f",
            linewidths=.5,
            cbar_kws={'label': 'Quadratic Weighted Kappa (QWK)'},
            ax=ax
        )
        
        ax.set_title("QWK Generalization Across Essay Prompts (1-8)", fontsize=18, pad=15)
        plt.tight_layout()
        
        if save:
            save_path = os.path.join(self.save_dir, "per_prompt_qwk_heatmap.png")
            plt.savefig(save_path, bbox_inches='tight')
            plt.close(fig)
            
        return fig

    def plot_predicted_vs_actual(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        model_name: str,
        save: bool = True
    ) -> plt.Figure:
        """
        Scatter plot of predicted vs actual scores with ideal fit line.
        """
        fig, ax = plt.subplots(figsize=(8, 8), dpi=150)
        
        # Calculate regression fit line
        r2 = np.corrcoef(y_true, y_pred)[0, 1] ** 2 if len(y_true) > 1 else 0
        
        ax.scatter(y_true, y_pred, color='purple', alpha=0.4, edgecolors='none', label='Essay Predictions')
        
        # Draw perfect prediction line
        ax.plot([0, 1], [0, 1], color='red', linestyle='--', linewidth=2, label='Perfect Prediction')
        
        ax.set_title(f"Predicted vs Actual Scores ({model_name})", fontsize=16, pad=15)
        ax.set_xlabel("True Normalized Score", fontsize=14)
        ax.set_ylabel("Predicted Normalized Score", fontsize=14)
        ax.set_xlim(-0.05, 1.05)
        ax.set_ylim(-0.05, 1.05)
        
        # Annotation box
        ax.annotate(f"R² = {r2:.4f}", xy=(0.05, 0.90), fontsize=14, fontweight='bold',
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8))
                    
        ax.legend(loc='lower right')
        plt.tight_layout()
        
        if save:
            save_path = os.path.join(self.save_dir, f"{model_name}_pred_vs_actual.png")
            plt.savefig(save_path, bbox_inches='tight')
            plt.close(fig)
            
        return fig

    def plot_residual_distribution(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        model_name: str,
        save: bool = True
    ) -> plt.Figure:
        """
        Histogram plot of prediction residuals (errors).
        """
        residuals = y_true - y_pred
        
        fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
        sns.histplot(residuals, kde=True, color='teal', ax=ax)
        
        ax.set_title(f"Residual Distribution ({model_name})", fontsize=16, pad=15)
        ax.set_xlabel("Residual (Actual - Predicted)", fontsize=14)
        ax.set_ylabel("Density", fontsize=14)
        ax.axvline(0, color='red', linestyle='--', linewidth=1.5)
        plt.tight_layout()
        
        if save:
            save_path = os.path.join(self.save_dir, f"{model_name}_residuals.png")
            plt.savefig(save_path, bbox_inches='tight')
            plt.close(fig)
            
        return fig

    def plot_confusion_matrix(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        model_name: str,
        labels: Optional[List[int]] = None,
        save: bool = True
    ) -> plt.Figure:
        """
        Plot rounded confusion matrix.
        """
        from sklearn.metrics import confusion_matrix
        
        y_true_rnd = np.round(y_true).astype(int)
        y_pred_rnd = np.round(y_pred).astype(int)
        
        cm = confusion_matrix(y_true_rnd, y_pred_rnd, labels=labels)
        
        fig, ax = plt.subplots(figsize=(10, 8), dpi=150)
        sns.heatmap(
            cm,
            annot=True,
            fmt="d",
            cmap="Purples",
            xticklabels=labels if labels else "auto",
            yticklabels=labels if labels else "auto",
            ax=ax
        )
        
        ax.set_title(f"Confusion Matrix ({model_name})", fontsize=16, pad=15)
        ax.set_xlabel("Predicted Integer Rating", fontsize=14)
        ax.set_ylabel("True Integer Rating", fontsize=14)
        plt.tight_layout()
        
        if save:
            save_path = os.path.join(self.save_dir, f"{model_name}_confusion_matrix.png")
            plt.savefig(save_path, bbox_inches='tight')
            plt.close(fig)
            
        return fig

    def plot_training_history(
        self,
        history: Dict[str, list],
        model_name: str,
        save: bool = True
    ) -> plt.Figure:
        """
        Plot training & validation loss curves.
        """
        if not history or "train_loss" not in history:
            return None
            
        fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
        epochs = range(1, len(history["train_loss"]) + 1)
        
        ax.plot(epochs, history["train_loss"], label="Training Loss", color="#1f77b4", linewidth=2)
        if "val_loss" in history:
            ax.plot(epochs, history["val_loss"], label="Validation Loss", color="#ff7f0e", linewidth=2)
            
        ax.set_title(f"Training History ({model_name})", fontsize=16, pad=15)
        ax.set_xlabel("Epoch", fontsize=14)
        ax.set_ylabel("Loss (MSE / RMSE)", fontsize=14)
        ax.legend()
        plt.tight_layout()
        
        if save:
            save_path = os.path.join(self.save_dir, f"{model_name}_training_history.png")
            plt.savefig(save_path, bbox_inches='tight')
            plt.close(fig)
            
        return fig

    def plot_score_distribution(
        self,
        scores: np.ndarray,
        essay_set: int,
        save: bool = True
    ) -> plt.Figure:
        """
        Plot distribution of essay scores for a given set.
        """
        fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
        sns.countplot(x=scores, color='cornflowerblue', ax=ax)
        
        ax.set_title(f"Score Distribution - Essay Set {essay_set}", fontsize=16, pad=15)
        ax.set_xlabel("Grade Score", fontsize=14)
        ax.set_ylabel("Number of Essays", fontsize=14)
        plt.tight_layout()
        
        if save:
            save_path = os.path.join(self.save_dir, f"essay_set_{essay_set}_score_dist.png")
            plt.savefig(save_path, bbox_inches='tight')
            plt.close(fig)
            
        return fig

    # ============================================================
    #  Plotly Helpers for Streamlit
    # ============================================================

    def create_plotly_gauge(
        self,
        score: float,
        min_score: int,
        max_score: int,
        title: str = 'Essay Score'
    ) -> go.Figure:
        """
        Create a Plotly gauge chart. Returns the raw figure for Streamlit integration.
        """
        # Calculate percentage to select color threshold
        pct = (score - min_score) / (max_score - min_score) if max_score > min_score else 0.0
        
        if pct >= 0.75:
            color = "#2ecc71"  # green
        elif pct >= 0.40:
            color = "#f39c12"  # orange
        else:
            color = "#e74c3c"  # red
            
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            title={'text': title, 'font': {'size': 18, 'family': 'Inter'}},
            number={'suffix': f"/{max_score}", 'font': {'size': 36}},
            gauge={
                'axis': {'range': [min_score, max_score]},
                'bar': {'color': color},
                'steps': [
                    {'range': [min_score, min_score + (max_score - min_score)*0.4], 'color': "lightgray"},
                    {'range': [min_score + (max_score - min_score)*0.4, min_score + (max_score - min_score)*0.75], 'color': "gray"}
                ]
            }
        ))
        fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor="rgba(0,0,0,0)")
        return fig

    def create_plotly_bar(
        self,
        feature_names: List[str],
        importances: List[float],
        title: str = 'Feature Importance'
    ) -> go.Figure:
        """
        Create horizontal bar plot for feature importance in Plotly.
        """
        df = pd.DataFrame({
            'Feature': [f.replace('_', ' ').title() for f in feature_names],
            'Importance': importances
        }).sort_values(by='Importance', ascending=True)
        
        fig = px.bar(
            df,
            x='Importance',
            y='Feature',
            orientation='h',
            title=title,
            color='Importance',
            color_continuous_scale=px.colors.sequential.Viridis
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(size=11),
            margin=dict(l=10, r=10, t=40, b=20),
            height=400
        )
        return fig
