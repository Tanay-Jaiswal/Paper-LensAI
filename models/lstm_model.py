# ============================================================
# models/lstm_model.py
# Bidirectional LSTM with Attention for Essay Scoring
# ============================================================
# Implements a BiLSTM with a learned attention mechanism that
# scores essays end-to-end from raw text.  The architecture is:
#
#   Text → Tokenize → Embedding → BiLSTM → Attention → FC → σ
#
# The LSTMScorer wrapper handles vocabulary construction,
# text-to-sequence conversion, training with early stopping,
# and serialization.
# ============================================================

import os
import sys
import copy
import logging
from collections import Counter
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import TensorDataset, DataLoader

# --------------- Project Imports ---------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from utils.helpers import ensure_dir, get_device

# --------------- Logger ---------------
logger = logging.getLogger("EssayScoringAI.LSTMModel")


# ============================================================
#  BiLSTM + Attention  (nn.Module)
# ============================================================

class BiLSTMAttention(nn.Module):
    """
    Bidirectional LSTM with a learned additive attention mechanism.

    Architecture
    ------------
    Embedding(vocab_size, embedding_dim)
        ↓
    BiLSTM(embedding_dim, hidden_dim, num_layers)
        ↓  outputs: (batch, seq_len, hidden_dim * 2)
    Attention  (learned context vector)
        ↓  context: (batch, hidden_dim * 2)
    Dropout → Linear(hidden_dim * 2, 1) → Sigmoid
        ↓
    score ∈ [0, 1]
    """

    def __init__(
        self,
        vocab_size: int,
        embedding_dim: int = 300,
        hidden_dim: int = 128,
        num_layers: int = 2,
        dropout: float = 0.3,
        bidirectional: bool = True,
    ):
        """
        Args:
            vocab_size: Size of the vocabulary (including <PAD>, <UNK>).
            embedding_dim: Dimension of word embeddings.
            hidden_dim: Hidden-state size per LSTM direction.
            num_layers: Number of stacked LSTM layers.
            dropout: Dropout probability applied between layers and
                before the final linear layer.
            bidirectional: If True, use a bidirectional LSTM.
        """
        super().__init__()

        self.hidden_dim = hidden_dim
        self.num_directions = 2 if bidirectional else 1
        self.output_dim = hidden_dim * self.num_directions

        # ---- Layers ----
        self.embedding = nn.Embedding(
            num_embeddings=vocab_size,
            embedding_dim=embedding_dim,
            padding_idx=0,  # <PAD> token index
        )

        self.lstm = nn.LSTM(
            input_size=embedding_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
            bidirectional=bidirectional,
        )

        # Attention components
        self.attention_linear = nn.Linear(self.output_dim, self.output_dim)
        self.attention_tanh = nn.Tanh()
        # Learned context vector for computing attention scores
        self.context_vector = nn.Parameter(
            torch.randn(self.output_dim)
        )

        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(self.output_dim, 1)
        self.sigmoid = nn.Sigmoid()

    # ----------------------------------------------------------

    def _attention(self, lstm_outputs: torch.Tensor) -> torch.Tensor:
        """
        Compute attention-weighted context vector.

        Args:
            lstm_outputs: (batch, seq_len, output_dim)

        Returns:
            context: (batch, output_dim)
        """
        # energy: (batch, seq_len, output_dim)
        energy = self.attention_tanh(
            self.attention_linear(lstm_outputs)
        )

        # scores: (batch, seq_len) — dot product with context vector
        scores = torch.matmul(energy, self.context_vector)

        # attention weights: (batch, seq_len)
        attention_weights = F.softmax(scores, dim=1)

        # context: (batch, output_dim) — weighted sum of LSTM outputs
        context = torch.sum(
            lstm_outputs * attention_weights.unsqueeze(-1), dim=1
        )

        return context

    # ----------------------------------------------------------

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass from token indices to a score in [0, 1].

        Args:
            x: LongTensor of shape (batch, seq_len) with token indices.

        Returns:
            Tensor of shape (batch,) with scores in [0, 1].
        """
        # Embedding: (batch, seq_len) → (batch, seq_len, embedding_dim)
        embedded = self.embedding(x)

        # BiLSTM: → (batch, seq_len, hidden_dim * 2)
        lstm_out, _ = self.lstm(embedded)

        # Attention: → (batch, hidden_dim * 2)
        context = self._attention(lstm_out)

        # Classification head
        context = self.dropout(context)
        logit = self.fc(context)           # (batch, 1)
        score = self.sigmoid(logit)        # (batch, 1)

        return score.squeeze(-1)           # (batch,)


# ============================================================
#  LSTM Scorer Wrapper
# ============================================================

class LSTMScorer:
    """
    High-level wrapper around BiLSTMAttention for essay scoring.

    Handles vocabulary construction, text→sequence conversion,
    the full training loop (with validation and early stopping),
    prediction, and model serialization.

    Usage
    -----
    >>> from training.config import Config
    >>> scorer = LSTMScorer(Config())
    >>> history = scorer.train(train_texts, train_scores,
    ...                        val_texts, val_scores)
    >>> preds = scorer.predict(test_texts)

    Attributes:
        config: Project-wide Config dataclass.
        word2idx (dict): Mapping from word → integer index.
        model (BiLSTMAttention | None): The neural network.
        device (str): 'cuda' or 'cpu'.
    """

    def __init__(self, config):
        """
        Initialize the LSTM scorer.

        Args:
            config: Config dataclass containing hyperparameters
                (lstm_embedding_dim, lstm_hidden_dim, etc.).
        """
        self.config = config
        self.word2idx: Dict[str, int] = {}
        self.model: Optional[BiLSTMAttention] = None
        self.device = get_device()

        logger.info("LSTMScorer initialized (device=%s).", self.device)

    # ----------------------------------------------------------
    #  Vocabulary
    # ----------------------------------------------------------

    def build_vocab(
        self,
        texts: List[str],
        max_vocab: int = 50000,
    ) -> None:
        """
        Build a word-to-index vocabulary from training texts.

        Special tokens:
          - <PAD> → 0  (padding)
          - <UNK> → 1  (unknown / out-of-vocabulary words)

        Args:
            texts: List of raw essay strings.
            max_vocab: Maximum vocabulary size (excluding specials).
        """
        word_counts: Counter = Counter()

        for text in texts:
            tokens = text.lower().split()
            word_counts.update(tokens)

        # Reserve indices 0 and 1 for special tokens
        self.word2idx = {"<PAD>": 0, "<UNK>": 1}

        # Add the most frequent words
        for word, _ in word_counts.most_common(max_vocab):
            self.word2idx[word] = len(self.word2idx)

        logger.info(
            "Vocabulary built: %d unique tokens (max_vocab=%d).",
            len(self.word2idx), max_vocab,
        )

    # ----------------------------------------------------------
    #  Text → Sequence Conversion
    # ----------------------------------------------------------

    def texts_to_sequences(
        self,
        texts: List[str],
        max_len: int = 512,
    ) -> torch.Tensor:
        """
        Convert a list of texts into a padded integer tensor.

        Each word is mapped to its vocabulary index; unknown words
        map to <UNK> (1).  Sequences are truncated or padded to
        ``max_len``.

        Args:
            texts: List of raw essay strings.
            max_len: Maximum sequence length.

        Returns:
            LongTensor of shape (n_texts, max_len).
        """
        unk_idx = self.word2idx.get("<UNK>", 1)
        sequences = []

        for text in texts:
            tokens = text.lower().split()
            indices = [
                self.word2idx.get(tok, unk_idx) for tok in tokens
            ]

            # Truncate or pad
            if len(indices) >= max_len:
                indices = indices[:max_len]
            else:
                indices += [0] * (max_len - len(indices))

            sequences.append(indices)

        return torch.LongTensor(sequences)

    # ----------------------------------------------------------
    #  Training Loop
    # ----------------------------------------------------------

    def train(
        self,
        X_texts: List[str],
        y_scores: np.ndarray,
        val_texts: List[str],
        val_scores: np.ndarray,
        epochs: Optional[int] = None,
        batch_size: Optional[int] = None,
    ) -> Dict[str, list]:
        """
        Train the BiLSTM+Attention model with early stopping.

        Args:
            X_texts: Training essay texts.
            y_scores: Training normalized scores in [0, 1].
            val_texts: Validation essay texts.
            val_scores: Validation normalized scores.
            epochs: Number of training epochs (default from config).
            batch_size: Batch size (default from config).

        Returns:
            History dictionary with keys:
              - 'train_loss': list of average training losses per epoch
              - 'val_loss':   list of average validation losses per epoch
        """
        epochs = epochs or self.config.epochs
        batch_size = batch_size or self.config.batch_size
        patience = self.config.early_stopping_patience

        # ---- Build vocabulary if not yet built ----
        if not self.word2idx:
            self.build_vocab(X_texts, max_vocab=self.config.lstm_vocab_size)

        # ---- Initialize the model ----
        vocab_size = len(self.word2idx)
        self.model = BiLSTMAttention(
            vocab_size=vocab_size,
            embedding_dim=self.config.lstm_embedding_dim,
            hidden_dim=self.config.lstm_hidden_dim,
            num_layers=self.config.lstm_num_layers,
            dropout=self.config.lstm_dropout,
            bidirectional=self.config.lstm_bidirectional,
        ).to(self.device)

        logger.info(
            "BiLSTMAttention created: vocab=%d, embed=%d, "
            "hidden=%d, layers=%d, bidir=%s",
            vocab_size, self.config.lstm_embedding_dim,
            self.config.lstm_hidden_dim, self.config.lstm_num_layers,
            self.config.lstm_bidirectional,
        )

        # ---- Prepare data ----
        max_len = self.config.max_essay_length
        X_train_seq = self.texts_to_sequences(X_texts, max_len)
        X_val_seq = self.texts_to_sequences(val_texts, max_len)

        y_train_t = torch.FloatTensor(np.asarray(y_scores, dtype=np.float32))
        y_val_t = torch.FloatTensor(np.asarray(val_scores, dtype=np.float32))

        train_dataset = TensorDataset(X_train_seq, y_train_t)
        val_dataset = TensorDataset(X_val_seq, y_val_t)

        train_loader = DataLoader(
            train_dataset, batch_size=batch_size, shuffle=True,
            num_workers=self.config.num_workers,
        )
        val_loader = DataLoader(
            val_dataset, batch_size=batch_size, shuffle=False,
            num_workers=self.config.num_workers,
        )

        # ---- Optimizer & Loss ----
        optimizer = torch.optim.Adam(
            self.model.parameters(), lr=self.config.learning_rate,
        )
        criterion = nn.MSELoss()

        # ---- Training loop ----
        history: Dict[str, list] = {"train_loss": [], "val_loss": []}
        best_val_loss = float("inf")
        best_model_state = None
        patience_counter = 0

        logger.info(
            "Starting training: %d epochs, batch_size=%d, lr=%.5f",
            epochs, batch_size, self.config.learning_rate,
        )

        for epoch in range(1, epochs + 1):
            # ---- Train ----
            self.model.train()
            epoch_train_loss = 0.0
            n_train_batches = 0

            for batch_X, batch_y in train_loader:
                batch_X = batch_X.to(self.device)
                batch_y = batch_y.to(self.device)

                optimizer.zero_grad()
                predictions = self.model(batch_X)
                loss = criterion(predictions, batch_y)
                loss.backward()
                # Gradient clipping to prevent exploding gradients
                torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(), max_norm=1.0
                )
                optimizer.step()

                epoch_train_loss += loss.item()
                n_train_batches += 1

            avg_train_loss = epoch_train_loss / max(n_train_batches, 1)

            # ---- Validate ----
            self.model.eval()
            epoch_val_loss = 0.0
            n_val_batches = 0

            with torch.no_grad():
                for batch_X, batch_y in val_loader:
                    batch_X = batch_X.to(self.device)
                    batch_y = batch_y.to(self.device)

                    predictions = self.model(batch_X)
                    loss = criterion(predictions, batch_y)

                    epoch_val_loss += loss.item()
                    n_val_batches += 1

            avg_val_loss = epoch_val_loss / max(n_val_batches, 1)

            history["train_loss"].append(avg_train_loss)
            history["val_loss"].append(avg_val_loss)

            logger.info(
                "Epoch %d/%d — train_loss: %.4f, val_loss: %.4f",
                epoch, epochs, avg_train_loss, avg_val_loss,
            )

            # ---- Early Stopping ----
            if avg_val_loss < best_val_loss:
                best_val_loss = avg_val_loss
                best_model_state = copy.deepcopy(self.model.state_dict())
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
                "Restored best model (val_loss=%.4f).", best_val_loss,
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

        Raises:
            RuntimeError: If the model has not been trained.
        """
        if self.model is None:
            raise RuntimeError(
                "Model has not been trained. Call train() first."
            )

        max_len = self.config.max_essay_length
        sequences = self.texts_to_sequences(texts, max_len).to(self.device)

        self.model.eval()
        with torch.no_grad():
            predictions = self.model(sequences)

        return predictions.cpu().numpy()

    # ----------------------------------------------------------
    #  Persistence
    # ----------------------------------------------------------

    def save(self, path: str) -> None:
        """
        Save model weights, vocabulary, and config to disk.

        Args:
            path: File path for the checkpoint (.pt).
        """
        if self.model is None:
            raise RuntimeError("No model to save. Train first.")

        try:
            ensure_dir(os.path.dirname(path))
            checkpoint = {
                "model_state_dict": self.model.state_dict(),
                "word2idx": self.word2idx,
                "model_type": "LSTMScorer",
                # Store hyper-params so we can reconstruct the model
                "vocab_size": len(self.word2idx),
                "embedding_dim": self.config.lstm_embedding_dim,
                "hidden_dim": self.config.lstm_hidden_dim,
                "num_layers": self.config.lstm_num_layers,
                "dropout": self.config.lstm_dropout,
                "bidirectional": self.config.lstm_bidirectional,
                "max_essay_length": self.config.max_essay_length,
            }
            torch.save(checkpoint, path)
            logger.info("LSTMScorer saved to %s", path)
        except Exception as exc:
            logger.error("Failed to save LSTMScorer: %s", exc)
            raise

    def load(self, path: str) -> None:
        """
        Load a previously saved LSTM checkpoint.

        Args:
            path: Path to the saved checkpoint file.

        Raises:
            FileNotFoundError: If the checkpoint does not exist.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Checkpoint not found: {path}")

        try:
            checkpoint = torch.load(path, map_location=self.device)

            self.word2idx = checkpoint["word2idx"]

            # Reconstruct the model architecture
            self.model = BiLSTMAttention(
                vocab_size=checkpoint["vocab_size"],
                embedding_dim=checkpoint["embedding_dim"],
                hidden_dim=checkpoint["hidden_dim"],
                num_layers=checkpoint["num_layers"],
                dropout=checkpoint["dropout"],
                bidirectional=checkpoint["bidirectional"],
            ).to(self.device)

            self.model.load_state_dict(checkpoint["model_state_dict"])
            self.model.eval()

            logger.info(
                "LSTMScorer loaded from %s (vocab=%d).",
                path, len(self.word2idx),
            )
        except Exception as exc:
            logger.error("Failed to load LSTMScorer: %s", exc)
            raise
