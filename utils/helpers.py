# ============================================================
# utils/helpers.py
# General Utility Functions
# ============================================================
# Provides common utilities used across the entire project:
# random seed management, device detection, directory creation,
# timing decorators, and logging setup.
# ============================================================

import os
import sys
import time
import random
import logging
import functools
from typing import Optional

import numpy as np


def set_seed(seed: int = 42) -> None:
    """
    Set random seeds for reproducibility across all libraries.
    
    Args:
        seed: Integer seed value (default: 42)
    """
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)

    # Set PyTorch seeds if available
    try:
        import torch
        torch.manual_seed(seed)
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    except ImportError:
        pass


def get_device() -> str:
    """
    Detect the best available compute device.
    
    Returns:
        'cuda' if GPU is available, else 'cpu'
    """
    try:
        import torch
        if torch.cuda.is_available():
            device = "cuda"
            gpu_name = torch.cuda.get_device_name(0)
            print(f"✓ Using GPU: {gpu_name}")
        else:
            device = "cpu"
            print("⚠ No GPU detected. Using CPU (training will be slower).")
        return device
    except ImportError:
        print("⚠ PyTorch not installed. Using CPU.")
        return "cpu"


def ensure_dir(path: str) -> str:
    """
    Create a directory (and parents) if it doesn't exist.
    
    Args:
        path: Directory path to create
        
    Returns:
        The same path (for chaining)
    """
    os.makedirs(path, exist_ok=True)
    return path


def timer_decorator(func):
    """
    Decorator that prints the execution time of a function.
    
    Usage:
        @timer_decorator
        def my_function():
            ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start

        # Format time nicely
        if elapsed < 60:
            time_str = f"{elapsed:.2f}s"
        elif elapsed < 3600:
            mins, secs = divmod(elapsed, 60)
            time_str = f"{int(mins)}m {secs:.1f}s"
        else:
            hours, remainder = divmod(elapsed, 3600)
            mins, secs = divmod(remainder, 60)
            time_str = f"{int(hours)}h {int(mins)}m {secs:.1f}s"

        print(f"⏱ {func.__name__} completed in {time_str}")
        return result
    return wrapper


def setup_logging(
    log_level: int = logging.INFO,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Set up logging with console and optional file output.
    
    Args:
        log_level: Logging level (default: INFO)
        log_file: Optional path to log file
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("EssayScoringAI")
    logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    try:
        console_handler.encoding = 'utf-8'
    except Exception:
        pass
    console_handler.setLevel(log_level)
    console_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        ensure_dir(os.path.dirname(log_file))
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_format = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(module)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger


def truncate_text(text: str, max_words: int = 50) -> str:
    """
    Truncate text to a maximum number of words for display.
    
    Args:
        text: Input text
        max_words: Maximum number of words to keep
        
    Returns:
        Truncated text with '...' suffix if truncated
    """
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."


def format_score_display(score: float, min_score: int, max_score: int) -> str:
    """
    Format a score for user-friendly display.
    
    Args:
        score: Predicted or actual score
        min_score: Minimum possible score
        max_score: Maximum possible score
        
    Returns:
        Formatted string like "8/12"
    """
    return f"{round(score)}/{max_score}"


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safe division that returns a default value on zero denominator.
    
    Args:
        numerator: Division numerator
        denominator: Division denominator
        default: Value to return if denominator is zero
        
    Returns:
        Result of division or default
    """
    if denominator == 0:
        return default
    return numerator / denominator
