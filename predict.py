# ============================================================
# predict.py
# Prediction CLI Entry Point
# ============================================================
# Usage:
#   python predict.py --essay "Your essay text here" --set 1
#   python predict.py --file essay.txt --set 2
#   python predict.py --essay "..." --model hybrid --explain
# ============================================================

import argparse
import os
import sys
import json

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
from utils.helpers import set_seed, format_score_display


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="AI-Based Automated Essay Scoring - Prediction Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python predict.py --essay "Your essay text here..." --set 1
  python predict.py --file my_essay.txt --set 2 --model hybrid
  python predict.py --essay "..." --set 1 --explain
        """
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--essay', '-e',
        type=str,
        help='Essay text to score (as a string)'
    )
    input_group.add_argument(
        '--file', '-f',
        type=str,
        help='Path to a text file containing the essay'
    )

    parser.add_argument(
        '--set', '-s',
        type=int,
        required=True,
        choices=[1, 2, 3, 4, 5, 6, 7, 8],
        help='Essay set number (1-8) — determines the scoring rubric'
    )

    parser.add_argument(
        '--model', '-m',
        type=str,
        default='hybrid',
        choices=['linear_regression', 'random_forest', 'cart', 'lstm',
                 'bert', 'roberta', 'hybrid'],
        help='Model to use for prediction (default: hybrid)'
    )

    parser.add_argument(
        '--explain',
        action='store_true',
        help='Show detailed SHAP-based explanation of the score'
    )

    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )

    return parser.parse_args()


def load_model(model_name: str, config: Config):
    """
    Load a trained model from disk.
    
    Args:
        model_name: Name of the model to load
        config: Configuration instance
        
    Returns:
        Loaded model instance
    """
    folder_name = model_name
    if model_name in ['lstm', 'bert', 'roberta', 'hybrid']:
        folder_name = f"{model_name}_model"
    model_path = os.path.join(config.models_dir, folder_name)

    if model_name == 'linear_regression':
        from models.baseline_models import LinearRegressionScorer
        model = LinearRegressionScorer()
        model.load(model_path + ".pkl")
    elif model_name == 'random_forest':
        from models.baseline_models import RandomForestScorer
        model = RandomForestScorer()
        model.load(model_path + ".pkl")
    elif model_name == 'cart':
        from models.baseline_models import CARTScorer
        model = CARTScorer()
        model.load(model_path + ".pkl")
    elif model_name == 'lstm':
        from models.lstm_model import LSTMScorer
        model = LSTMScorer(config)
        model.load(model_path)
    elif model_name == 'bert':
        from models.bert_model import BERTScorer
        model = BERTScorer(config)
        model.load(model_path)
    elif model_name == 'roberta':
        from models.roberta_model import RoBERTaScorer
        model = RoBERTaScorer(config)
        model.load(model_path)
    elif model_name == 'hybrid':
        from models.hybrid_model import HybridScorer
        model = HybridScorer(config)
        model.load(model_path)
    else:
        raise ValueError(f"Unknown model: {model_name}")

    return model


def get_features_and_analysis(essay_text: str) -> dict:
    """
    Extract all features and analysis from an essay.
    
    Args:
        essay_text: Raw essay text
        
    Returns:
        Dictionary with grammar, readability, and linguistic analysis
    """
    from preprocessing.text_cleaner import TextCleaner
    from feature_engineering.grammar_features import GrammarAnalyzer
    from feature_engineering.readability_features import ReadabilityAnalyzer
    from feature_engineering.linguistic_features import LinguisticAnalyzer

    cleaner = TextCleaner()
    cleaned = cleaner.clean(essay_text)

    grammar = GrammarAnalyzer()
    readability = ReadabilityAnalyzer()
    linguistic = LinguisticAnalyzer()

    return {
        'cleaned_text': cleaned,
        'grammar': grammar.analyze(cleaned),
        'readability': readability.analyze(cleaned),
        'linguistic': linguistic.analyze(cleaned),
    }


def main():
    """Main prediction entry point."""
    args = parse_args()
    config = Config()
    set_seed(config.random_seed)

    # Get essay text
    if args.file:
        if not os.path.exists(args.file):
            print(f"❌ File not found: {args.file}")
            sys.exit(1)
        with open(args.file, 'r', encoding='utf-8') as f:
            essay_text = f.read()
    else:
        essay_text = args.essay

    if len(essay_text.strip()) < 10:
        print("❌ Essay text is too short. Please provide a longer essay.")
        sys.exit(1)

    if not args.json:
        print("=" * 65)
        print("  🎓 AI-Based Automated Essay Scoring System")
        print("=" * 65)
        print()

    # Load model
    try:
        model = load_model(args.model, config)
    except FileNotFoundError:
        print(f"❌ Trained model '{args.model}' not found.")
        print(f"   Please train the model first: python train.py --model {args.model}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        sys.exit(1)

    # Get analysis
    analysis = get_features_and_analysis(essay_text)

    # Get prediction
    if args.model in ['linear_regression', 'random_forest', 'cart']:
        import numpy as np
        handcrafted_names = [
            'grammar_error_count', 'spelling_error_count', 'error_rate', 'grammar_score',
            'flesch_reading_ease', 'flesch_kincaid_grade', 'gunning_fog', 'smog_index',
            'coleman_liau_index', 'automated_readability_index', 'composite_readability_score',
            'word_count', 'sentence_count', 'avg_word_length', 'avg_sentence_length',
            'type_token_ratio', 'hapax_legomena_ratio', 'lexical_diversity_mtld',
            'noun_ratio', 'verb_ratio', 'adj_ratio', 'adv_ratio',
            'named_entity_count', 'stopword_ratio', 'long_word_ratio', 'vocabulary_richness_score'
        ]
        features = {}
        features.update(analysis['grammar'])
        features.update(analysis['readability'])
        features.update(analysis['linguistic'])
        feature_values = [features.get(name, 0.0) for name in handcrafted_names]
        prediction = model.predict(np.array([feature_values]))[0]
    else:
        prediction = model.predict([essay_text])[0]

    # Convert to original score range
    min_score, max_score = config.score_ranges[args.set]
    raw_score = config.denormalize_score(prediction, args.set)

    # Prepare results
    results = {
        'essay_set': args.set,
        'model_used': config.model_names.get(args.model, args.model),
        'predicted_score': raw_score,
        'score_range': f"{min_score}-{max_score}",
        'normalized_score': round(float(prediction), 4),
        'word_count': analysis['linguistic'].get('word_count', 0),
        'sentence_count': analysis['linguistic'].get('sentence_count', 0),
        'grammar_score': round(analysis['grammar'].get('grammar_score', 0) * 100, 1),
        'grammar_errors': analysis['grammar'].get('grammar_error_count', 0),
        'readability_score': round(
            analysis['readability'].get('composite_readability_score', 0) * 100, 1
        ),
        'vocabulary_richness': round(
            analysis['linguistic'].get('vocabulary_richness_score', 0) * 100, 1
        ),
        'readability_grade': analysis['readability'].get('flesch_kincaid_grade', 0),
    }

    # Output
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"📝 Essay Set: {args.set} (Score Range: {min_score}-{max_score})")
        print(f"🤖 Model: {results['model_used']}")
        print()
        print(f"  🎯 Predicted Score:      {raw_score} / {max_score}")
        print(f"  📊 Normalized Score:     {results['normalized_score']}")
        print()
        print(f"  ✏️  Grammar Score:        {results['grammar_score']}%  ({results['grammar_errors']} errors)")
        print(f"  📖 Readability Score:    {results['readability_score']}%  (Grade {results['readability_grade']})")
        print(f"  📚 Vocabulary Richness:  {results['vocabulary_richness']}%")
        print(f"  📏 Word Count:           {results['word_count']}")
        print(f"  📋 Sentence Count:       {results['sentence_count']}")
        print()

    # SHAP Explanation
    if args.explain and args.model == 'hybrid':
        try:
            from explainability.shap_explainer import SHAPExplainer
            from explainability.feature_importance import FeatureImportanceAnalyzer

            print("🔍 Generating SHAP Explanation...")
            print("-" * 40)

            xgb_model = model.get_model()
            feature_names = model.get_feature_names()
            feature_matrix = model.get_feature_matrix([essay_text])

            explainer = SHAPExplainer(xgb_model, feature_names)
            explanation = explainer.explain_single(feature_matrix[0])

            # Show top features
            top_features = explainer.get_top_features(feature_matrix[0], top_k=10)
            print("\nTop 10 Most Influential Features:")
            for i, (name, value) in enumerate(top_features, 1):
                direction = "↑" if value > 0 else "↓"
                print(f"  {i:2d}. {name:30s} {direction} {abs(value):.4f}")

            # Natural language explanation
            analyzer = FeatureImportanceAnalyzer(feature_names)
            nl_explanation = analyzer.generate_explanation(
                explanation['shap_values'],
                feature_matrix[0],
                feature_names,
                raw_score, args.set, config
            )
            print(f"\n💬 AI Feedback:\n{nl_explanation}")

        except Exception as e:
            print(f"⚠ Could not generate explanation: {e}")

    elif args.explain and args.model != 'hybrid':
        print("⚠ SHAP explanations are only available for the hybrid model.")
        print("  Use: python predict.py --essay '...' --set 1 --model hybrid --explain")


if __name__ == "__main__":
    main()
