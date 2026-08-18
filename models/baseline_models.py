# ============================================================
# models/baseline_models.py
# Baseline Machine Learning Models for Essay Scoring
# ============================================================
# Provides three traditional ML baselines that operate on
# pre-extracted feature vectors:
#   1. LinearRegressionScorer  – simple linear baseline
#   2. RandomForestScorer      – ensemble tree baseline
#   3. CARTScorer              – single decision tree (interpretable)
#
# Both models predict normalized scores in [0, 1] and share
# a consistent interface: train(), predict(), save(), load().
# ============================================================

import os
import sys
import logging
import copy

import numpy as np
import joblib
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.tree import DecisionTreeRegressor

# --------------- Project Imports ---------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from utils.helpers import ensure_dir

# --------------- Logger ---------------
logger = logging.getLogger("EssayScoringAI.BaselineModels")


# ============================================================
#  Linear Regression Scorer
# ============================================================

class LinearRegressionScorer:
    """
    Simple linear regression baseline for essay scoring.

    Wraps sklearn's LinearRegression to predict normalized essay
    scores in the [0, 1] range.  Useful as a lower-bound baseline
    to benchmark more complex models against.

    Attributes:
        model (LinearRegression): The underlying sklearn model.
        is_fitted (bool): Whether the model has been trained.
    """

    def __init__(self):
        """Initialize the Linear Regression scorer."""
        self.model = LinearRegression()
        self.is_fitted = False
        logger.info("LinearRegressionScorer initialized.")

    # ----------------------------------------------------------
    #  Training
    # ----------------------------------------------------------

    def train(self, X_train: np.ndarray, y_train: np.ndarray) -> dict:
        """
        Fit the linear regression model on training data.

        Args:
            X_train: Feature matrix of shape (n_samples, n_features).
            y_train: Target scores of shape (n_samples,), in [0, 1].

        Returns:
            Dictionary with training metadata (n_samples, n_features,
            r_squared on training data).

        Raises:
            ValueError: If input arrays have incompatible shapes.
        """
        try:
            X_train = np.asarray(X_train, dtype=np.float64)
            y_train = np.asarray(y_train, dtype=np.float64)

            if X_train.shape[0] != y_train.shape[0]:
                raise ValueError(
                    f"X_train rows ({X_train.shape[0]}) != "
                    f"y_train length ({y_train.shape[0]})"
                )

            logger.info(
                "Training LinearRegression on %d samples, %d features…",
                X_train.shape[0], X_train.shape[1],
            )

            self.model.fit(X_train, y_train)
            self.is_fitted = True

            r2 = self.model.score(X_train, y_train)
            logger.info("Training complete. R² on train set: %.4f", r2)

            return {
                "n_samples": X_train.shape[0],
                "n_features": X_train.shape[1],
                "train_r_squared": round(r2, 4),
            }

        except Exception as exc:
            logger.error("LinearRegression training failed: %s", exc)
            raise

    # ----------------------------------------------------------
    #  Prediction
    # ----------------------------------------------------------

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict essay scores and clip to [0, 1].

        Args:
            X: Feature matrix of shape (n_samples, n_features).

        Returns:
            Numpy array of predicted scores clipped to [0, 1].

        Raises:
            RuntimeError: If the model has not been trained yet.
        """
        if not self.is_fitted:
            raise RuntimeError(
                "Model has not been trained. Call train() first."
            )

        X = np.asarray(X, dtype=np.float64)
        predictions = self.model.predict(X)

        # Clip to valid score range
        predictions = np.clip(predictions, 0.0, 1.0)

        logger.debug("Generated %d predictions.", len(predictions))
        return predictions

    # ----------------------------------------------------------
    #  Persistence
    # ----------------------------------------------------------

    def save(self, path: str) -> None:
        """
        Save the trained model to disk using joblib.

        Args:
            path: File path for the saved model (.joblib).
        """
        try:
            ensure_dir(os.path.dirname(path))
            save_data = {
                "model": self.model,
                "is_fitted": self.is_fitted,
                "model_type": "LinearRegressionScorer",
            }
            joblib.dump(save_data, path)
            logger.info("LinearRegressionScorer saved to %s", path)
        except Exception as exc:
            logger.error("Failed to save model: %s", exc)
            raise

    def load(self, path: str) -> None:
        """
        Load a previously saved model from disk.

        Args:
            path: Path to the saved model file.

        Raises:
            FileNotFoundError: If the model file does not exist.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model file not found: {path}")

        try:
            save_data = joblib.load(path)
            self.model = save_data["model"]
            self.is_fitted = save_data["is_fitted"]
            logger.info("LinearRegressionScorer loaded from %s", path)
        except Exception as exc:
            logger.error("Failed to load model: %s", exc)
            raise


# ============================================================
#  Random Forest Scorer
# ============================================================

class RandomForestScorer:
    """
    Random Forest regression model for essay scoring.

    An ensemble of decision trees that provides:
      - Robust predictions clipped to [0, 1]
      - Feature importance scores for interpretability
      - Persistence via joblib

    Attributes:
        model (RandomForestRegressor): The underlying sklearn model.
        is_fitted (bool): Whether the model has been trained.
        n_estimators (int): Number of trees in the forest.
        max_depth (int | None): Maximum tree depth.
        min_samples_split (int): Minimum samples to split a node.
    """

    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: int = None,
        min_samples_split: int = 5,
    ):
        """
        Initialize the Random Forest scorer.

        Args:
            n_estimators: Number of trees (default 200).
            max_depth: Max depth per tree (None = unlimited).
            min_samples_split: Min samples required to split an
                internal node (default 5).
        """
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split

        self.model = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            random_state=42,
            n_jobs=-1,       # Use all CPU cores
            verbose=0,
        )
        self.is_fitted = False

        logger.info(
            "RandomForestScorer initialized (n_estimators=%d, "
            "max_depth=%s, min_samples_split=%d).",
            n_estimators, max_depth, min_samples_split,
        )

    # ----------------------------------------------------------
    #  Training
    # ----------------------------------------------------------

    def train(self, X_train: np.ndarray, y_train: np.ndarray) -> dict:
        """
        Fit the Random Forest model on training data.

        Args:
            X_train: Feature matrix of shape (n_samples, n_features).
            y_train: Target scores of shape (n_samples,), in [0, 1].

        Returns:
            Dictionary with training metadata (n_samples, n_features,
            oob_score if available, r_squared).

        Raises:
            ValueError: If input arrays have incompatible shapes.
        """
        try:
            X_train = np.asarray(X_train, dtype=np.float64)
            y_train = np.asarray(y_train, dtype=np.float64)

            if X_train.shape[0] != y_train.shape[0]:
                raise ValueError(
                    f"X_train rows ({X_train.shape[0]}) != "
                    f"y_train length ({y_train.shape[0]})"
                )

            logger.info(
                "Training RandomForest on %d samples, %d features "
                "(n_estimators=%d)…",
                X_train.shape[0], X_train.shape[1], self.n_estimators,
            )

            self.model.fit(X_train, y_train)
            self.is_fitted = True

            r2 = self.model.score(X_train, y_train)
            logger.info("Training complete. R² on train set: %.4f", r2)

            return {
                "n_samples": X_train.shape[0],
                "n_features": X_train.shape[1],
                "n_estimators": self.n_estimators,
                "train_r_squared": round(r2, 4),
            }

        except Exception as exc:
            logger.error("RandomForest training failed: %s", exc)
            raise

    # ----------------------------------------------------------
    #  Prediction
    # ----------------------------------------------------------

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict essay scores and clip to [0, 1].

        Args:
            X: Feature matrix of shape (n_samples, n_features).

        Returns:
            Numpy array of predicted scores clipped to [0, 1].

        Raises:
            RuntimeError: If the model has not been trained yet.
        """
        if not self.is_fitted:
            raise RuntimeError(
                "Model has not been trained. Call train() first."
            )

        X = np.asarray(X, dtype=np.float64)
        predictions = self.model.predict(X)

        # Clip to valid score range
        predictions = np.clip(predictions, 0.0, 1.0)

        logger.debug("Generated %d predictions.", len(predictions))
        return predictions

    # ----------------------------------------------------------
    #  Feature Importance
    # ----------------------------------------------------------

    def get_feature_importance(self) -> np.ndarray:
        """
        Return feature importance scores from the trained forest.

        Returns:
            Numpy array of shape (n_features,) with importance
            values summing to 1.0.

        Raises:
            RuntimeError: If the model has not been trained yet.
        """
        if not self.is_fitted:
            raise RuntimeError(
                "Model has not been trained. Call train() first."
            )

        importances = self.model.feature_importances_
        logger.debug(
            "Top-5 feature importance indices: %s",
            np.argsort(importances)[-5:][::-1],
        )
        return importances

    # ----------------------------------------------------------
    #  Persistence
    # ----------------------------------------------------------

    def save(self, path: str) -> None:
        """
        Save the trained model to disk using joblib.

        Args:
            path: File path for the saved model (.joblib).
        """
        try:
            ensure_dir(os.path.dirname(path))
            save_data = {
                "model": self.model,
                "is_fitted": self.is_fitted,
                "n_estimators": self.n_estimators,
                "max_depth": self.max_depth,
                "min_samples_split": self.min_samples_split,
                "model_type": "RandomForestScorer",
            }
            joblib.dump(save_data, path)
            logger.info("RandomForestScorer saved to %s", path)
        except Exception as exc:
            logger.error("Failed to save model: %s", exc)
            raise

    def load(self, path: str) -> None:
        """
        Load a previously saved model from disk.

        Args:
            path: Path to the saved model file.

        Raises:
            FileNotFoundError: If the model file does not exist.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model file not found: {path}")

        try:
            save_data = joblib.load(path)
            self.model = save_data["model"]
            self.is_fitted = save_data["is_fitted"]
            self.n_estimators = save_data.get("n_estimators", 200)
            self.max_depth = save_data.get("max_depth", None)
            self.min_samples_split = save_data.get("min_samples_split", 5)
            logger.info("RandomForestScorer loaded from %s", path)
        except Exception as exc:
            logger.error("Failed to load model: %s", exc)
            raise


# ============================================================
#  CART (Decision Tree) Scorer
# ============================================================

class CARTScorer:
    """
    CART (Classification and Regression Trees) model for essay scoring.

    Uses sklearn's DecisionTreeRegressor to build a single interpretable
    decision tree that recursively partitions the feature space using
    binary splits based on Gini impurity / MSE minimization.

    CART is inherently interpretable — the tree structure itself
    explains the model's reasoning.  It also serves as a baseline to
    understand the contribution of ensemble methods (Random Forest,
    XGBoost) that aggregate many such trees.

    Attributes:
        model (DecisionTreeRegressor): The underlying sklearn model.
        is_fitted (bool): Whether the model has been trained.
        max_depth (int | None): Maximum tree depth.
        min_samples_split (int): Minimum samples to split a node.
        min_samples_leaf (int): Minimum samples at a leaf node.
    """

    def __init__(
        self,
        max_depth: int = 10,
        min_samples_split: int = 5,
        min_samples_leaf: int = 3,
    ):
        """
        Initialize the CART scorer.

        Args:
            max_depth: Max depth of the tree (default 10).
                       Controls overfitting — deeper trees memorize data.
            min_samples_split: Min samples required to split an
                internal node (default 5).
            min_samples_leaf: Min samples required at a leaf node
                (default 3).
        """
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf

        self.model = DecisionTreeRegressor(
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            min_samples_leaf=min_samples_leaf,
            random_state=42,
            criterion="squared_error",
        )
        self.is_fitted = False

        logger.info(
            "CARTScorer initialized (max_depth=%s, "
            "min_samples_split=%d, min_samples_leaf=%d).",
            max_depth, min_samples_split, min_samples_leaf,
        )

    # ----------------------------------------------------------
    #  Training
    # ----------------------------------------------------------

    def train(self, X_train: np.ndarray, y_train: np.ndarray) -> dict:
        """
        Fit the CART decision tree on training data.

        Args:
            X_train: Feature matrix of shape (n_samples, n_features).
            y_train: Target scores of shape (n_samples,), in [0, 1].

        Returns:
            Dictionary with training metadata (n_samples, n_features,
            tree_depth, n_leaves, r_squared).

        Raises:
            ValueError: If input arrays have incompatible shapes.
        """
        try:
            X_train = np.asarray(X_train, dtype=np.float64)
            y_train = np.asarray(y_train, dtype=np.float64)

            if X_train.shape[0] != y_train.shape[0]:
                raise ValueError(
                    f"X_train rows ({X_train.shape[0]}) != "
                    f"y_train length ({y_train.shape[0]})"
                )

            logger.info(
                "Training CART on %d samples, %d features "
                "(max_depth=%s)…",
                X_train.shape[0], X_train.shape[1], self.max_depth,
            )

            self.model.fit(X_train, y_train)
            self.is_fitted = True

            r2 = self.model.score(X_train, y_train)
            tree_depth = self.model.get_depth()
            n_leaves = self.model.get_n_leaves()

            logger.info(
                "Training complete. R² on train set: %.4f | "
                "Tree depth: %d | Leaves: %d",
                r2, tree_depth, n_leaves,
            )

            return {
                "n_samples": X_train.shape[0],
                "n_features": X_train.shape[1],
                "tree_depth": tree_depth,
                "n_leaves": n_leaves,
                "train_r_squared": round(r2, 4),
            }

        except Exception as exc:
            logger.error("CART training failed: %s", exc)
            raise

    # ----------------------------------------------------------
    #  Prediction
    # ----------------------------------------------------------

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict essay scores and clip to [0, 1].

        Args:
            X: Feature matrix of shape (n_samples, n_features).

        Returns:
            Numpy array of predicted scores clipped to [0, 1].

        Raises:
            RuntimeError: If the model has not been trained yet.
        """
        if not self.is_fitted:
            raise RuntimeError(
                "Model has not been trained. Call train() first."
            )

        X = np.asarray(X, dtype=np.float64)
        predictions = self.model.predict(X)

        # Clip to valid score range
        predictions = np.clip(predictions, 0.0, 1.0)

        logger.debug("Generated %d predictions.", len(predictions))
        return predictions

    # ----------------------------------------------------------
    #  Feature Importance
    # ----------------------------------------------------------

    def get_feature_importance(self) -> np.ndarray:
        """
        Return feature importance scores from the trained tree.

        Returns:
            Numpy array of shape (n_features,) with importance
            values summing to 1.0.

        Raises:
            RuntimeError: If the model has not been trained yet.
        """
        if not self.is_fitted:
            raise RuntimeError(
                "Model has not been trained. Call train() first."
            )

        importances = self.model.feature_importances_
        logger.debug(
            "Top-5 feature importance indices: %s",
            np.argsort(importances)[-5:][::-1],
        )
        return importances

    # ----------------------------------------------------------
    #  Persistence
    # ----------------------------------------------------------

    def save(self, path: str) -> None:
        """
        Save the trained model to disk using joblib.

        Args:
            path: File path for the saved model (.pkl).
        """
        try:
            ensure_dir(os.path.dirname(path))
            save_data = {
                "model": self.model,
                "is_fitted": self.is_fitted,
                "max_depth": self.max_depth,
                "min_samples_split": self.min_samples_split,
                "min_samples_leaf": self.min_samples_leaf,
                "model_type": "CARTScorer",
            }
            joblib.dump(save_data, path)
            logger.info("CARTScorer saved to %s", path)
        except Exception as exc:
            logger.error("Failed to save model: %s", exc)
            raise

    def load(self, path: str) -> None:
        """
        Load a previously saved model from disk.

        Args:
            path: Path to the saved model file.

        Raises:
            FileNotFoundError: If the model file does not exist.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model file not found: {path}")

        try:
            save_data = joblib.load(path)
            self.model = save_data["model"]
            self.is_fitted = save_data["is_fitted"]
            self.max_depth = save_data.get("max_depth", 10)
            self.min_samples_split = save_data.get("min_samples_split", 5)
            self.min_samples_leaf = save_data.get("min_samples_leaf", 3)
            logger.info("CARTScorer loaded from %s", path)
        except Exception as exc:
            logger.error("Failed to load model: %s", exc)
            raise
