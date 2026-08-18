# ============================================================
# feature_engineering/transformer_embeddings.py
# Transformer-based Embedding Extraction for Essay Scoring
# ============================================================
# Extracts dense [CLS]-token embeddings from a HuggingFace
# transformer model (default: roberta-base, 768-dim).
#
# Key capabilities:
#   - Auto-detect device (CUDA / CPU)
#   - Handle long texts by chunking into 512-token segments
#     and mean-pooling the per-chunk [CLS] embeddings
#   - Batched inference with tqdm progress bar
#   - Disk caching via .npy files
# ============================================================

import os
import sys
import logging
from typing import List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from training.config import Config

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports for torch & transformers — keeps module importable even
# when these heavy dependencies are missing (e.g., for static analysis).
# ---------------------------------------------------------------------------
_torch = None
_transformers = None


def _ensure_torch():
    """Import torch lazily and cache the module."""
    global _torch
    if _torch is None:
        try:
            import torch
            _torch = torch
        except ImportError:
            raise ImportError(
                "PyTorch is required for transformer embeddings.  "
                "Install with: pip install torch"
            )
    return _torch


def _ensure_transformers():
    """Import transformers lazily and cache the module."""
    global _transformers
    if _transformers is None:
        try:
            import transformers
            _transformers = transformers
        except ImportError:
            raise ImportError(
                "HuggingFace Transformers is required.  "
                "Install with: pip install transformers"
            )
    return _transformers


class TransformerEmbedder:
    """
    Extract [CLS]-token embeddings from a HuggingFace transformer model.

    Usage::

        embedder = TransformerEmbedder()                     # roberta-base
        vec      = embedder.extract_embedding(essay_text)    # (768,) ndarray
        vecs     = embedder.extract_batch_embeddings(texts)  # (N, 768)

    Long texts (> 512 tokens) are automatically chunked and
    mean-pooled so no information is silently truncated.

    Attributes:
        model_name (str):  HuggingFace model identifier.
        device (torch.device): Inference device.
        max_length (int):  Maximum token length per chunk (512).
        embedding_dim (int): Output embedding dimension (768 for base).
    """

    def __init__(
        self,
        model_name: str = "roberta-base",
        device: Optional[str] = None,
    ) -> None:
        """
        Load the tokenizer and model.

        Args:
            model_name: HuggingFace model identifier
                        (default ``'roberta-base'``).
            device:     ``'cuda'``, ``'cpu'``, or ``None`` for auto-detect.
        """
        torch = _ensure_torch()
        transformers = _ensure_transformers()

        self.model_name: str = model_name

        # --- Device selection ---
        if device is not None:
            self.device = torch.device(device)
        elif torch.cuda.is_available():
            self.device = torch.device("cuda")
            logger.info(
                "CUDA available — using GPU: %s",
                torch.cuda.get_device_name(0),
            )
        else:
            self.device = torch.device("cpu")
            logger.info("CUDA not available — using CPU.")

        # --- Load tokenizer & model ---
        logger.info("Loading tokenizer for '%s' ...", model_name)
        self.tokenizer = transformers.AutoTokenizer.from_pretrained(model_name)

        logger.info("Loading model '%s' ...", model_name)
        self.model = transformers.AutoModel.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()  # Inference mode

        # --- Derived constants ---
        self.max_length: int = self.tokenizer.model_max_length
        # Guard: some tokenizers report a huge default max_length
        if self.max_length > 100_000:
            self.max_length = 512

        self.embedding_dim: int = self.model.config.hidden_size

        logger.info(
            "TransformerEmbedder ready — model=%s, device=%s, "
            "max_length=%d, embedding_dim=%d",
            model_name, self.device, self.max_length, self.embedding_dim,
        )

    # ================================================================
    # Single-text embedding
    # ================================================================

    def extract_embedding(self, text: str) -> np.ndarray:
        """
        Extract a single embedding vector from *text*.

        For texts that tokenize to more than ``max_length`` tokens,
        the text is split into overlapping chunks.  Each chunk's
        [CLS] embedding is extracted, and the results are
        mean-pooled into a single vector.

        Args:
            text: Essay text.

        Returns:
            1-D NumPy array of shape ``(embedding_dim,)``.
        """
        torch = _ensure_torch()

        if not isinstance(text, str) or not text.strip():
            logger.warning("Empty text — returning zero embedding.")
            return np.zeros(self.embedding_dim, dtype=np.float32)

        # Tokenize the full text (no truncation) to check length
        full_encoding = self.tokenizer(
            text,
            add_special_tokens=False,
            return_attention_mask=False,
        )
        token_ids: List[int] = full_encoding["input_ids"]

        # --- Short text: single forward pass ---
        # Reserve 2 tokens for [CLS] and [SEP] (or equivalent)
        usable_length = self.max_length - 2

        if len(token_ids) <= usable_length:
            return self._forward_single(text)

        # --- Long text: chunk and mean-pool ---
        chunks = self._chunk_token_ids(token_ids, usable_length)
        cls_embeddings: List[np.ndarray] = []

        for chunk_ids in chunks:
            chunk_text = self.tokenizer.decode(
                chunk_ids, skip_special_tokens=True
            )
            emb = self._forward_single(chunk_text)
            cls_embeddings.append(emb)

        # Mean-pool across all chunk [CLS] vectors
        return np.mean(cls_embeddings, axis=0).astype(np.float32)

    # ================================================================
    # Batch embedding
    # ================================================================

    def extract_batch_embeddings(
        self,
        texts: List[str],
        batch_size: int = 16,
        show_progress: bool = True,
    ) -> np.ndarray:
        """
        Extract embeddings for a list of texts with batching.

        Args:
            texts:         List of essay texts.
            batch_size:    Number of texts per batch (default 16).
            show_progress: Show a tqdm progress bar (default ``True``).

        Returns:
            2-D NumPy array of shape ``(len(texts), embedding_dim)``.
        """
        if not texts:
            return np.empty((0, self.embedding_dim), dtype=np.float32)

        # Optional tqdm import
        if show_progress:
            try:
                from tqdm import tqdm
            except ImportError:
                logger.warning(
                    "tqdm not installed — progress bar disabled."
                )
                show_progress = False

        all_embeddings: List[np.ndarray] = []

        # Build iterator (with or without progress bar)
        total_batches = (len(texts) + batch_size - 1) // batch_size
        indices = range(0, len(texts), batch_size)
        if show_progress:
            indices = tqdm(
                indices,
                total=total_batches,
                desc="Extracting embeddings",
                unit="batch",
            )

        for start in indices:
            batch_texts = texts[start: start + batch_size]
            for txt in batch_texts:
                emb = self.extract_embedding(txt)
                all_embeddings.append(emb)

        return np.vstack(all_embeddings).astype(np.float32)

    # ================================================================
    # Caching
    # ================================================================

    def cache_embeddings(
        self,
        texts: List[str],
        ids: List[Any],
        cache_path: str,
        batch_size: int = 16,
    ) -> np.ndarray:
        """
        Extract embeddings and save to disk as a ``.npy`` file.

        A companion ``*_ids.npy`` file is saved alongside so the
        embeddings can be matched back to their essay IDs.

        Args:
            texts:      List of essay texts.
            ids:        List of essay IDs (same length as *texts*).
            cache_path: Path to save the ``.npy`` file.
            batch_size: Batch size for extraction.

        Returns:
            The extracted embeddings array ``(N, embedding_dim)``.
        """
        logger.info("Extracting embeddings for %d texts ...", len(texts))
        embeddings = self.extract_batch_embeddings(
            texts, batch_size=batch_size
        )

        # Ensure parent directory exists
        os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)

        # Save embeddings
        np.save(cache_path, embeddings)
        logger.info("Embeddings saved to '%s' (%s).", cache_path, embeddings.shape)

        # Save companion IDs file
        ids_path = cache_path.replace(".npy", "_ids.npy")
        np.save(ids_path, np.array(ids))
        logger.info("IDs saved to '%s'.", ids_path)

        return embeddings

    @staticmethod
    def load_cached_embeddings(
        cache_path: str,
    ) -> Optional[Tuple[np.ndarray, Optional[np.ndarray]]]:
        """
        Load cached embeddings (and IDs) from disk.

        Args:
            cache_path: Path to the ``.npy`` embeddings file.

        Returns:
            Tuple ``(embeddings, ids)`` if the cache exists, else
            ``None``.  ``ids`` may be ``None`` if the companion file
            is missing.
        """
        if not os.path.isfile(cache_path):
            logger.info("Cache file not found: '%s'.", cache_path)
            return None

        embeddings = np.load(cache_path)
        logger.info(
            "Loaded cached embeddings from '%s' (%s).",
            cache_path, embeddings.shape,
        )

        # Try to load companion IDs
        ids_path = cache_path.replace(".npy", "_ids.npy")
        ids = None
        if os.path.isfile(ids_path):
            ids = np.load(ids_path, allow_pickle=True)
            logger.info("Loaded cached IDs from '%s'.", ids_path)

        return embeddings, ids

    # ================================================================
    # Internal helpers
    # ================================================================

    def _forward_single(self, text: str) -> np.ndarray:
        """
        Run a single forward pass and return the [CLS] embedding.

        Args:
            text: Text that fits within ``max_length`` tokens.

        Returns:
            1-D NumPy array of shape ``(embedding_dim,)``.
        """
        torch = _ensure_torch()

        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_length,
            padding=True,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)

        # [CLS] token is always at position 0
        cls_embedding = outputs.last_hidden_state[:, 0, :]
        return cls_embedding.squeeze(0).cpu().numpy().astype(np.float32)

    @staticmethod
    def _chunk_token_ids(
        token_ids: List[int],
        chunk_size: int,
        overlap: int = 50,
    ) -> List[List[int]]:
        """
        Split a list of token IDs into overlapping chunks.

        Args:
            token_ids:  Full list of token IDs.
            chunk_size: Maximum tokens per chunk (excluding special tokens).
            overlap:    Number of overlapping tokens between consecutive
                        chunks (default 50).

        Returns:
            List of token-ID lists.
        """
        chunks: List[List[int]] = []
        step = max(chunk_size - overlap, 1)

        for start in range(0, len(token_ids), step):
            chunk = token_ids[start: start + chunk_size]
            chunks.append(chunk)

            # Stop if we've consumed all tokens
            if start + chunk_size >= len(token_ids):
                break

        return chunks


# ============================================================
# Quick smoke-test when run directly
# ============================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    config = Config()

    print("=" * 60)
    print(f"Initialising TransformerEmbedder (model={config.roberta_model_name})")
    print("=" * 60)

    embedder = TransformerEmbedder(model_name=config.roberta_model_name)

    # --- Single embedding ---
    sample_text = (
        "The importance of education cannot be overstated. Education "
        "provides individuals with the knowledge and skills necessary "
        "to succeed in life."
    )
    embedding = embedder.extract_embedding(sample_text)
    print(f"\nSingle embedding shape: {embedding.shape}")
    print(f"First 10 values: {embedding[:10]}")

    # --- Batch embeddings ---
    batch_texts = [
        "This is the first sample essay for testing.",
        "Another essay about technology and its impact.",
        "A short essay.",
    ]
    batch_embeddings = embedder.extract_batch_embeddings(
        batch_texts, batch_size=2, show_progress=True
    )
    print(f"\nBatch embedding shape: {batch_embeddings.shape}")

    # --- Caching ---
    cache_dir = config.embeddings_cache_dir
    cache_path = os.path.join(cache_dir, "test_cache.npy")

    embedder.cache_embeddings(
        batch_texts,
        ids=[1, 2, 3],
        cache_path=cache_path,
    )

    # --- Load from cache ---
    loaded = TransformerEmbedder.load_cached_embeddings(cache_path)
    if loaded is not None:
        embs, ids = loaded
        print(f"\nLoaded from cache: embeddings={embs.shape}, ids={ids}")
    print("=" * 60)
