# ============================================================
# models/bert_model.py
# BERT Fine-tuned Model for Essay Scoring
# ============================================================
# Fine-tunes a pre-trained BERT model (bert-base-uncased) for
# essay score regression.  Architecture:
#
#   Text → BertTokenizer → BERT → [CLS] pooler_output
#        → Dropout → Linear(768, 1) → Sigmoid → score ∈ [0,1]
#
# Uses AdamW with linear warmup, gradient clipping, and early
# stopping to prevent over-fitting on small essay datasets.
# ============================================================

import os
import sys
import copy
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from tqdm import tqdm

from transformers import (
    BertModel,
    BertTokenizer,
    get_linear_schedule_with_warmup,
)

# --------------- Project Imports ---------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from utils.helpers import ensure_dir, get_device

# --------------- Logger ---------------
logger = logging.getLogger("EssayScoringAI.BERTModel")


# ============================================================
#  BERT For Scoring  (nn.Module)
# ============================================================

class BERTForScoring(nn.Module):
    """
    BERT-based regression head for essay scoring.

    Architecture
    ------------
    BertModel('bert-base-uncased')
        ↓  pooler_output: (batch, 768)
    Dropout(p)
        ↓
    Linear(768, 1)
        ↓
    Sigmoid → score ∈ [0, 1]
    """

    def __init__(
        self,
        model_name: str = "bert-base-uncased",
        dropout: float = 0.1,
    ):
        """
        Args:
            model_name: HuggingFace model identifier.
            dropout: Dropout probability before the output layer.
        """
        super().__init__()

        self.bert = BertModel.from_pretrained(model_name)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(
            self.bert.config.hidden_size, 1
        )
        self.sigmoid = nn.Sigmoid()

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> torch.Tensor:
        """
        Forward pass.

        Args:
            input_ids: (batch, seq_len) token indices.
            attention_mask: (batch, seq_len) attention mask.

        Returns:
            Tensor of shape (batch,) with scores in [0, 1].
        """
        outputs = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )

        # [CLS] representation via the built-in pooler
        pooled = outputs.pooler_output        # (batch, 768)

        pooled = self.dropout(pooled)
        logit = self.classifier(pooled)       # (batch, 1)
        score = self.sigmoid(logit)           # (batch, 1)

        return score.squeeze(-1)              # (batch,)


# ============================================================
#  BERT Scorer Wrapper
# ============================================================

class BERTScorer:
    """
    High-level wrapper for fine-tuning BERT on essay scoring.

    Manages tokenization, DataLoader creation, the training loop
    (AdamW + linear warmup + early stopping), prediction, and
    model serialization.

    Usage
    -----
    >>> from training.config import Config
    >>> scorer = BERTScorer(Config())
    >>> history = scorer.train(train_texts, train_scores,
    ...                        val_texts, val_scores)
    >>> preds = scorer.predict(test_texts)

    Attributes:
        config: Project Config dataclass.
        tokenizer (BertTokenizer): HuggingFace tokenizer.
        model (BERTForScoring): The scoring network.
        device (str): 'cuda' or 'cpu'.
    """

    def __init__(self, config, device: Optional[str] = None):
        """
        Load the BERT tokenizer and initialize the scoring model.

        Args:
            config: Config dataclass with BERT hyperparameters.
            device: Compute device ('cuda' / 'cpu').  Auto-detected
                if None.
        """
        self.config = config
        self.device = device or get_device()

        # Tokenizer
        self.tokenizer = BertTokenizer.from_pretrained(
            config.bert_model_name
        )

        # Model
        self.model = BERTForScoring(
            model_name=config.bert_model_name,
            dropout=config.finetune_dropout,
        ).to(self.device)

        logger.info(
            "BERTScorer initialized (model=%s, device=%s).",
            config.bert_model_name, self.device,
        )

    # ----------------------------------------------------------
    #  DataLoader Helper
    # ----------------------------------------------------------

    def _create_dataloader(
        self,
        texts: List[str],
        scores: np.ndarray,
        batch_size: int,
        shuffle: bool = True,
    ) -> DataLoader:
        """
        Tokenize texts and wrap them in a PyTorch DataLoader.

        Args:
            texts: Raw essay strings.
            scores: Corresponding normalized scores.
            batch_size: Batch size for the DataLoader.
            shuffle: Whether to shuffle every epoch.

        Returns:
            DataLoader yielding (input_ids, attention_mask, scores).
        """
        # Tokenize all texts at once
        encodings = self.tokenizer(
            list(texts),
            padding=True,
            truncation=True,
            max_length=self.config.bert_max_length,
            return_tensors="pt",
        )

        input_ids = encodings["input_ids"]
        attention_mask = encodings["attention_mask"]
        score_tensor = torch.FloatTensor(
            np.asarray(scores, dtype=np.float32)
        )

        dataset = TensorDataset(input_ids, attention_mask, score_tensor)

        return DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=shuffle,
            num_workers=self.config.num_workers,
        )

    # ----------------------------------------------------------
    #  Training Loop
    # ----------------------------------------------------------

    def train(
        self,
        train_texts: List[str],
        train_scores: np.ndarray,
        val_texts: List[str],
        val_scores: np.ndarray,
    ) -> Dict[str, list]:
        """
        Fine-tune BERT on essay scoring data with early stopping.

        Uses AdamW with linear warmup and gradient clipping.
        The best model (by validation loss) is retained.

        Args:
            train_texts: Training essay texts.
            train_scores: Training normalized scores.
            val_texts: Validation essay texts.
            val_scores: Validation normalized scores.

        Returns:
            History dictionary with keys:
              - 'train_loss': per-epoch average training loss
              - 'val_loss':   per-epoch average validation loss
        """
        epochs = self.config.finetune_epochs
        batch_size = self.config.finetune_batch_size
        patience = self.config.early_stopping_patience

        # ---- DataLoaders ----
        train_loader = self._create_dataloader(
            train_texts, train_scores, batch_size, shuffle=True,
        )
        val_loader = self._create_dataloader(
            val_texts, val_scores, batch_size, shuffle=False,
        )

        # ---- Optimizer & Scheduler ----
        optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.config.finetune_learning_rate,
            weight_decay=self.config.finetune_weight_decay,
        )

        total_steps = len(train_loader) * epochs
        scheduler = get_linear_schedule_with_warmup(
            optimizer,
            num_warmup_steps=self.config.finetune_warmup_steps,
            num_training_steps=total_steps,
        )

        criterion = nn.MSELoss()

        # ---- Training state ----
        history: Dict[str, list] = {"train_loss": [], "val_loss": []}
        best_val_loss = float("inf")
        best_model_state = None
        patience_counter = 0

        logger.info(
            "Starting BERT fine-tuning: %d epochs, batch=%d, "
            "lr=%.1e, warmup=%d steps.",
            epochs, batch_size, self.config.finetune_learning_rate,
            self.config.finetune_warmup_steps,
        )

        for epoch in range(1, epochs + 1):
            # ---- Train phase ----
            self.model.train()
            epoch_loss = 0.0
            n_batches = 0

            progress = tqdm(
                train_loader,
                desc=f"Epoch {epoch}/{epochs} [Train]",
                leave=False,
            )
            for batch_ids, batch_mask, batch_scores in progress:
                batch_ids = batch_ids.to(self.device)
                batch_mask = batch_mask.to(self.device)
                batch_scores = batch_scores.to(self.device)

                optimizer.zero_grad()

                preds = self.model(batch_ids, batch_mask)
                loss = criterion(preds, batch_scores)
                loss.backward()

                # Gradient clipping
                torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(), max_norm=1.0,
                )

                optimizer.step()
                scheduler.step()

                epoch_loss += loss.item()
                n_batches += 1
                progress.set_postfix(loss=f"{loss.item():.4f}")

            avg_train_loss = epoch_loss / max(n_batches, 1)

            # ---- Validation phase ----
            self.model.eval()
            val_loss = 0.0
            n_val = 0

            with torch.no_grad():
                for batch_ids, batch_mask, batch_scores in val_loader:
                    batch_ids = batch_ids.to(self.device)
                    batch_mask = batch_mask.to(self.device)
                    batch_scores = batch_scores.to(self.device)

                    preds = self.model(batch_ids, batch_mask)
                    loss = criterion(preds, batch_scores)

                    val_loss += loss.item()
                    n_val += 1

            avg_val_loss = val_loss / max(n_val, 1)

            history["train_loss"].append(avg_train_loss)
            history["val_loss"].append(avg_val_loss)

            logger.info(
                "Epoch %d/%d — train_loss: %.4f, val_loss: %.4f",
                epoch, epochs, avg_train_loss, avg_val_loss,
            )

            # ---- Early stopping ----
            if avg_val_loss < best_val_loss:
                best_val_loss = avg_val_loss
                best_model_state = copy.deepcopy(
                    self.model.state_dict()
                )
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logger.info(
                        "Early stopping at epoch %d (patience=%d).",
                        epoch, patience,
                    )
                    break

        # Restore best model
        if best_model_state is not None:
            self.model.load_state_dict(best_model_state)
            logger.info(
                "Restored best BERT model (val_loss=%.4f).",
                best_val_loss,
            )

        return history

    # ----------------------------------------------------------
    #  Prediction
    # ----------------------------------------------------------

    def predict(self, texts: List[str]) -> np.ndarray:
        """
        Predict essay scores for a list of texts.

        Args:
            texts: List of raw essay strings.

        Returns:
            Numpy array of shape (n_texts,) with scores in [0, 1].
        """
        self.model.eval()
        batch_size = self.config.finetune_batch_size

        # Create a dummy score array for the dataloader
        dummy_scores = np.zeros(len(texts), dtype=np.float32)
        loader = self._create_dataloader(
            texts, dummy_scores, batch_size, shuffle=False,
        )

        all_preds = []
        with torch.no_grad():
            for batch_ids, batch_mask, _ in loader:
                batch_ids = batch_ids.to(self.device)
                batch_mask = batch_mask.to(self.device)

                preds = self.model(batch_ids, batch_mask)
                all_preds.append(preds.cpu().numpy())

        return np.concatenate(all_preds, axis=0)

    # ----------------------------------------------------------
    #  Persistence
    # ----------------------------------------------------------

    def save(self, path: str) -> None:
        """
        Save the fine-tuned model and tokenizer.

        Args:
            path: Directory path to save the model into.
        """
        try:
            ensure_dir(path)

            # Save PyTorch model state
            model_path = os.path.join(path, "bert_scorer.pt")
            torch.save(self.model.state_dict(), model_path)

            # Save tokenizer alongside the model
            self.tokenizer.save_pretrained(path)

            logger.info("BERTScorer saved to %s", path)
        except Exception as exc:
            logger.error("Failed to save BERTScorer: %s", exc)
            raise

    def load(self, path: str) -> None:
        """
        Load a previously saved model and tokenizer.

        Args:
            path: Directory containing the saved model.

        Raises:
            FileNotFoundError: If the path does not exist.
        """
        model_path = os.path.join(path, "bert_scorer.pt")
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Model checkpoint not found: {model_path}"
            )

        try:
            # Reload tokenizer
            self.tokenizer = BertTokenizer.from_pretrained(path)

            # Reload model weights
            state_dict = torch.load(
                model_path, map_location=self.device,
            )
            self.model.load_state_dict(state_dict)
            self.model.eval()

            logger.info("BERTScorer loaded from %s", path)
        except Exception as exc:
            logger.error("Failed to load BERTScorer: %s", exc)
            raise
