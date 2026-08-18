# ============================================================
# train.py
# Main Training CLI Entry Point
# ============================================================
# Usage:
#   python train.py                          # Train all models
#   python train.py --model hybrid           # Train only hybrid model
#   python train.py --model all --sample     # Quick test with sample data
#   python train.py --model baseline         # Train only baselines
# ============================================================

import argparse
import os
import sys

# Ensure UTF-8 output encoding for terminals supporting it (prevents CP1252 UnicodeEncodeError for emojis)
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from training.config import Config
from training.trainer import Trainer
from utils.helpers import set_seed


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="AI-Based Automated Essay Scoring System - Training Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python train.py                              Train all 6 models
  python train.py --model hybrid               Train only the hybrid model
  python train.py --model baseline             Train Linear Regression + Random Forest
  python train.py --model lstm bert            Train LSTM and BERT
  python train.py --sample                     Use synthetic sample data (no dataset needed)
  python train.py --model hybrid --sample      Quick test of hybrid model with sample data
        """
    )

    parser.add_argument(
        '--model', '-m',
        nargs='+',
        default=['all'],
        choices=['all', 'linear_regression', 'random_forest', 'cart', 'baseline',
                 'lstm', 'bert', 'roberta', 'hybrid'],
        help='Which model(s) to train. "baseline" = LR + RF + CART. Default: all'
    )

    parser.add_argument(
        '--sample', '-s',
        action='store_true',
        help='Use synthetic sample data instead of real dataset (for testing)'
    )

    parser.add_argument(
        '--epochs', '-e',
        type=int,
        default=None,
        help='Override number of training epochs'
    )

    parser.add_argument(
        '--batch-size', '-b',
        type=int,
        default=None,
        help='Override batch size'
    )

    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed for reproducibility (default: 42)'
    )

    parser.add_argument(
        '--dataset', '-d',
        type=str,
        default=None,
        help='Path to dataset TSV file (overrides default path)'
    )

    return parser.parse_args()


def main():
    """Main training entry point."""
    args = parse_args()

    # Banner
    print("=" * 65)
    print("  🎓 AI-Based Automated Essay Scoring System")
    print("     Using Transformer Embeddings & Explainable NLP Metrics")
    print("=" * 65)
    print()

    # Initialize configuration
    config = Config()
    config.random_seed = args.seed

    # Apply overrides
    if args.epochs:
        config.epochs = args.epochs
        config.finetune_epochs = min(args.epochs, config.finetune_epochs)

    if args.batch_size:
        config.batch_size = args.batch_size
        config.finetune_batch_size = args.batch_size

    if args.dataset:
        config.dataset_path = args.dataset

    # Expand 'baseline' shorthand
    models_to_train = []
    for m in args.model:
        if m == 'baseline':
            models_to_train.extend(['linear_regression', 'random_forest', 'cart'])
        else:
            models_to_train.append(m)

    # Check dataset exists (unless using sample data)
    if not args.sample and not os.path.exists(config.dataset_path):
        print(f"⚠ Dataset not found at: {config.dataset_path}")
        print()
        print("Options:")
        print("  1. Download the ASAP dataset from Kaggle and place it at the path above")
        print("  2. Run with --sample flag to use synthetic sample data for testing:")
        print("     python train.py --sample")
        print()
        print("To download the dataset:")
        print("  - Visit: https://www.kaggle.com/c/asap-aes/data")
        print("  - Download 'training_set_rel3.tsv'")
        print(f"  - Place it in: {os.path.dirname(config.dataset_path)}")
        sys.exit(1)

    # Set seed
    set_seed(config.random_seed)

    # Initialize trainer and run
    trainer = Trainer(config)
    comparison_df = trainer.run_full_pipeline(
        use_sample=args.sample,
        models_to_train=models_to_train
    )

    # Print final comparison
    print("\n" + "=" * 65)
    print("📊 Final Model Comparison (Test Set)")
    print("=" * 65)
    print(comparison_df.to_string())
    print()

    best = trainer.evaluator.get_best_model()
    print(f"🏆 Best Model: {config.model_names.get(best, best)}")
    print(f"📁 Results saved to: {config.results_dir}")
    print(f"📈 Graphs saved to: {config.graphs_dir}")
    print(f"💾 Models saved to: {config.models_dir}")
    print()
    print("To launch the Streamlit UI:")
    print("  streamlit run streamlit_app.py")
    print()


if __name__ == "__main__":
    main()
