# ============================================================
# models/roberta_model.py
# RoBERTa Fine-tuned Model for Essay Scoring
# ============================================================
# Fine-tunes a pre-trained RoBERTa model (roberta-base) for
# essay score regression. Architecture:
#
#   Text → RobertaTokenizer → RoBERTa → <s> representation
#        → Dropout → Linear(768, 1) → Sigmoid → score ∈ [0,1]
#
# Uses AdamW with linear warmup, gradient clipping, and early
# stopping to prevent over-fitting.
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
    RobertaModel,
    RobertaTokenizer,
    get_linear_schedule_with_warmup,
)

# --------------- Project Imports ---------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from utils.helpers import ensure_dir, get_device

# --------------- Logger ---------------
logger = logging.getLogger("EssayScoringAI.RoBERTaModel")


# ============================================================
#  RoBERTa For Scoring  (nn.Module)
# ============================================================

class RoBERTaForScoring(nn.Module):
    """
    RoBERTa-based regression head for essay scoring.

    Architecture
    ------------
    RobertaModel('roberta-base')
        ↓  last_hidden_state[:, 0, :] (<s> token): (batch, 768)
    Dropout(p)
        ↓
    Linear(768, 1)
        ↓
    Sigmoid → score ∈ [0, 1]
    """

    def __init__(
        self,
        model_name: str = "roberta-base",
        dropout: float = 0.1,
    ):
        """
        Args:
            model_name: HuggingFace model identifier.
            dropout: Dropout probability before the output layer.
        """
        super().__init__()

        self.roberta = RobertaModel.from_pretrained(model_name)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(
            self.roberta.config.hidden_size, 1
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
        outputs = self.roberta(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )

        # RoBERTa uses <s> as the first token (index 0)
        # last_hidden_state has shape (batch, seq_len, hidden_size)
        cls_rep = outputs.last_hidden_state[:, 0, :]  # (batch, 768)

        cls_rep = self.dropout(cls_rep)
        logit = self.classifier(cls_rep)              # (batch, 1)
        score = self.sigmoid(logit)                   # (batch, 1)

        return score.squeeze(-1)                      # (batch,)


# ============================================================
#  RoBERTa Scorer Wrapper
# ============================================================

class RoBERTaScorer:
    """
    High-level wrapper for fine-tuning RoBERTa on essay scoring.

    Manages tokenization, DataLoader creation, the training loop
    (AdamW + linear warmup + early stopping), prediction, and
    model serialization.

    Attributes:
        config: Project Config dataclass.
        tokenizer (RobertaTokenizer): HuggingFace tokenizer.
        model (RoBERTaForScoring): The scoring network.
        device (str): 'cuda' or 'cpu'.
    """

    def __init__(self, config, device: Optional[str] = None):
        """
        Load the RoBERTa tokenizer and initialize the scoring model.

        Args:
            config: Config dataclass with RoBERTa hyperparameters.
            device: Compute device ('cuda' / 'cpu'). Auto-detected
                if None.
        """
        self.config = config
        self.device = device or get_device()

        # Tokenizer
        self.tokenizer = RobertaTokenizer.from_pretrained(
            config.roberta_model_name
        )

        # Model
        self.model = RoBERTaForScoring(
            model_name=config.roberta_model_name,
            dropout=config.finetune_dropout,
        ).to(self.device)

        logger.info(
            "RoBERTaScorer initialized (model=%s, device=%s).",
            config.roberta_model_name, self.device,
        )

    def _create_dataloader(
        self,
        texts: List[str],
        scores: np.ndarray,
        batch_size: int,
        shuffle: bool = True,
    ) -> DataLoader:
        """
        Tokenize texts and wrap them in a PyTorch DataLoader.
        """
        encodings = self.tokenizer(
            list(texts),
            padding=True,
            truncation=True,
            max_length=self.config.roberta_max_length,
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

    def train(
        self,
        train_texts: List[str],
        train_scores: np.ndarray,
        val_texts: List[str],
        val_scores: np.ndarray,
    ) -> Dict[str, list]:
        """
        Fine-tune RoBERTa on essay scoring data with early stopping.
        """
        epochs = self.config.finetune_epochs
        batch_size = self.config.finetune_batch_size
        patience = self.config.early_stopping_patience

        train_loader = self._create_dataloader(
            train_texts, train_scores, batch_size, shuffle=True,
        )
        val_loader = self._create_dataloader(
            val_texts, val_scores, batch_size, shuffle=False,
        )

        # Optimizer and Scheduler
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

        best_loss = float("inf")
        best_model_wts = copy.deepcopy(self.model.state_dict())
        epochs_no_improve = 0

        history = {"train_loss": [], "val_loss": []}

        for epoch in range(1, epochs + 1):
            # --- Training Epoch ---
            self.model.train()
            train_loss = 0.0

            progress_bar = tqdm(
                train_loader, desc=f"RoBERTa Epoch {epoch}/{epochs}"
            )
            for batch_ids, batch_mask, batch_scores in progress_bar:
                batch_ids = batch_ids.to(self.device)
                batch_mask = batch_mask.to(self.device)
                batch_scores = batch_scores.to(self.device)

                optimizer.zero_grad()

                preds = self.model(batch_ids, batch_mask)
                loss = criterion(preds, batch_scores)

                loss.backward()

                # Gradient clipping
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)

                optimizer.step()
                scheduler.step()

                train_loss += loss.item() * len(batch_scores)
                progress_bar.set_postfix({"loss": f"{loss.item():.4f}"})

            epoch_train_loss = train_loss / len(train_texts)

            # --- Validation Epoch ---
            self.model.eval()
            val_loss = 0.0

            with torch.no_grad():
                for batch_ids, batch_mask, batch_scores in val_loader:
                    batch_ids = batch_ids.to(self.device)
                    batch_mask = batch_mask.to(self.device)
                    batch_scores = batch_scores.to(self.device)

                    preds = self.model(batch_ids, batch_mask)
                    loss = criterion(preds, batch_scores)
                    val_loss += loss.item() * len(batch_scores)

            epoch_val_loss = val_loss / len(val_texts)

            history["train_loss"].append(epoch_train_loss)
            history["val_loss"].append(epoch_val_loss)

            logger.info(
                "Epoch %d: Train Loss = %.4f | Val Loss = %.4f",
                epoch, epoch_train_loss, epoch_val_loss,
            )

            # --- Early Stopping check ---
            if epoch_val_loss < best_loss:
                best_loss = epoch_val_loss
                best_model_wts = copy.deepcopy(self.model.state_dict())
                epochs_no_improve = 0
            else:
                epochs_no_improve += 1
                if epochs_no_improve >= patience:
                    logger.info("Early stopping triggered after %d epochs.", epoch)
                    break

        # Load best weights
        self.model.load_state_dict(best_model_wts)
        return history

    def predict(self, texts: List[str]) -> np.ndarray:
        """
        Predict essay scores.
        """
        self.model.eval()
        batch_size = self.config.finetune_batch_size

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

    def save(self, path: str) -> None:
        """
        Save the fine-tuned model and tokenizer.
        """
        try:
            ensure_dir(path)
            model_path = os.path.join(path, "roberta_scorer.pt")
            torch.save(self.model.state_dict(), model_path)
            self.tokenizer.save_pretrained(path)
            logger.info("RoBERTaScorer saved to %s", path)
        except Exception as exc:
            logger.error("Failed to save RoBERTaScorer: %s", exc)
            raise

    def load(self, path: str) -> None:
        """
        Load a previously saved model and tokenizer.
        """
        model_path = os.path.join(path, "roberta_scorer.pt")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model checkpoint not found: {model_path}")

        try:
            self.tokenizer = RobertaTokenizer.from_pretrained(path)
            state_dict = torch.load(model_path, map_location=self.device)
            self.model.load_state_dict(state_dict)
            self.model.eval()
            logger.info("RoBERTaScorer loaded from %s", path)
        except Exception as exc:
            logger.error("Failed to load RoBERTaScorer: %s", exc)
            raise
