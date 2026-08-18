# ============================================================
# explainability/feature_importance.py
# Feature Importance & Natural Language Score Explainers
# ============================================================
# Analyzes SHAP values by feature category and builds human-readable
# explanations (strengths, weaknesses, structural feedback) for
# student essays.
# ============================================================

import os
import sys
import logging
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

# --------------- Project Imports ---------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from training.config import Config

# --------------- Logger ---------------
logger = logging.getLogger("EssayScoringAI.FeatureImportance")


class FeatureImportanceAnalyzer:
    """
    Categorizes SHAP contributions and generates natural language explanations 
    detailing the specific linguistic strengths and weaknesses of an essay.
    """

    def __init__(
        self,
        feature_names: List[str],
        feature_categories: Optional[Dict[str, str]] = None
    ):
        """
        Args:
            feature_names: Ordered list of feature names.
            feature_categories: Dictionary mapping feature name -> category label.
        """
        self.feature_names = feature_names
        
        # Build default mapping if not provided
        if feature_categories is None:
            self.feature_categories = {}
            for name in feature_names:
                name_lower = name.lower()
                if "pca" in name_lower:
                    self.feature_categories[name] = "Semantic Context (RoBERTa)"
                elif "grammar" in name_lower or "spelling" in name_lower or "error" in name_lower:
                    self.feature_categories[name] = "Grammar & Spelling"
                elif "readability" in name_lower or "flesch" in name_lower or "fog" in name_lower or "smog" in name_lower or "index" in name_lower or "grade" in name_lower:
                    self.feature_categories[name] = "Readability & Complexity"
                elif "vocabulary" in name_lower or "richness" in name_lower or "lexical" in name_lower or "mtld" in name_lower or "ratio" in name_lower or "noun" in name_lower or "verb" in name_lower or "adj" in name_lower or "adv" in name_lower or "stopword" in name_lower:
                    self.feature_categories[name] = "Vocabulary & Diversity"
                elif "count" in name_lower or "length" in name_lower or "sentence" in name_lower or "word" in name_lower or "entity" in name_lower:
                    self.feature_categories[name] = "Structure & Length"
                else:
                    self.feature_categories[name] = "Other Features"
        else:
            self.feature_categories = feature_categories

    def get_category_breakdown(
        self,
        shap_values: np.ndarray,
        feature_names: List[str]
    ) -> Dict[str, float]:
        """
        Aggregate SHAP values by feature category.
        
        Returns:
            Dict mapping category_name -> total absolute SHAP contribution.
        """
        breakdown = {}
        for name, val in zip(feature_names, shap_values):
            category = self.feature_categories.get(name, "Other Features")
            breakdown[category] = breakdown.get(category, 0.0) + abs(val)
            
        # Normalize to percentages
        total = sum(breakdown.values())
        if total > 0:
            for k in breakdown:
                breakdown[k] = (breakdown[k] / total) * 100
                
        return breakdown

    def get_strengths_and_weaknesses(
        self,
        shap_values: np.ndarray,
        feature_values: np.ndarray,
        feature_names: List[str],
        top_k: int = 3
    ) -> Tuple[List[str], List[str]]:
        """
        Identify specific strengths (highly positive SHAP) and weaknesses (negative SHAP).
        
        Returns:
            Tuple of (list of strengths descriptions, list of weaknesses descriptions)
        """
        # Map feature names to their raw values and SHAP values
        features_dict = {name: val for name, val in zip(feature_names, feature_values)}
        shap_dict = {name: val for name, val in zip(feature_names, shap_values)}
        
        strengths_list = []
        weaknesses_list = []
        
        # --- Helper for human readable descriptions ---
        def describe_feature(name: str, raw_val: float, is_positive: bool) -> str:
            name_lower = name.lower()
            if "grammar_score" in name_lower:
                return "Excellent grammatical accuracy" if is_positive else "Needs grammar refinement"
            elif "grammar_error_count" in name_lower:
                return f"Very few grammatical mistakes ({int(raw_val)} errors)" if is_positive else f"High number of grammar errors ({int(raw_val)} detected)"
            elif "spelling_error_count" in name_lower:
                return f"Excellent spelling" if is_positive else f"Spelling issues found ({int(raw_val)} errors)"
            elif "composite_readability_score" in name_lower:
                return "Well-suited readability level" if is_positive else "Readability is too simplistic or overly complex"
            elif "flesch_kincaid_grade" in name_lower:
                return f"Strong grade-level reading complexity (Grade {raw_val:.1f})" if is_positive else f"Inappropriate grade complexity (Grade {raw_val:.1f})"
            elif "vocabulary_richness_score" in name_lower:
                return "Rich and varied vocabulary" if is_positive else "Repetitive or limited vocabulary"
            elif "word_count" in name_lower:
                return f"Detailed essay length ({int(raw_val)} words)" if is_positive else f"Essay length is too short ({int(raw_val)} words)"
            elif "avg_sentence_length" in name_lower:
                return "Good sentence length balance" if is_positive else f"Sentences are overly long or short (avg {raw_val:.1f} words)"
            elif "lexical_diversity_mtld" in name_lower:
                return "High lexical diversity" if is_positive else "Low vocabulary variance"
            elif "type_token_ratio" in name_lower:
                return "High unique word usage" if is_positive else "High repetition of common words"
            elif "named_entity_count" in name_lower:
                return f"Good usage of specific examples and entities ({int(raw_val)} named entities)" if is_positive else "Lacks concrete named entities and examples"
            elif "pca" in name_lower:
                return "Strong thematic coherence" if is_positive else "Weak thematic consistency"
            return f"{name.replace('_', ' ').title()} support" if is_positive else f"{name.replace('_', ' ').title()} improvement needed"

        # Sort features by SHAP value
        sorted_by_shap = sorted(shap_dict.items(), key=lambda x: x[1], reverse=True)
        
        # Filter out PCA features from natural descriptions if possible, since they aren't easily actionable
        filtered_pos = [item for item in sorted_by_shap if "pca" not in item[0].lower() and item[1] > 0.005]
        filtered_neg = [item for item in sorted_by_shap if "pca" not in item[0].lower() and item[1] < -0.005]
        
        # Strengths (highest positive SHAP values)
        for name, val in filtered_pos[:top_k]:
            raw_val = features_dict[name]
            strengths_list.append(describe_feature(name, raw_val, True))
            
        # Weaknesses (most negative SHAP values)
        # Reverse to get most negative first
        filtered_neg.sort(key=lambda x: x[1])
        for name, val in filtered_neg[:top_k]:
            raw_val = features_dict[name]
            weaknesses_list.append(describe_feature(name, raw_val, False))
            
        return strengths_list, weaknesses_list

    def generate_explanation(
        self,
        shap_values: np.ndarray,
        feature_values: np.ndarray,
        feature_names: List[str],
        score: float,
        essay_set: int,
        config: Config
    ) -> str:
        """
        Generate a comprehensive natural language explanation for an essay score.
        
        Args:
            shap_values: 1D SHAP values array for the essay.
            feature_values: 1D raw feature values array.
            feature_names: Ordered list of feature names.
            score: The final integer score predicted.
            essay_set: The essay set index (1-8).
            config: Config instance.
            
        Returns:
            Natural language feedback paragraph.
        """
        min_score, max_score = config.score_ranges[essay_set]
        
        # 1. Strengths and weaknesses lists
        strengths, weaknesses = self.get_strengths_and_weaknesses(
            shap_values, feature_values, feature_names, top_k=2
        )
        
        # 2. Category breakdowns
        breakdown = self.get_category_breakdown(shap_values, feature_names)
        
        # Find dominant category
        dominant_cat = max(breakdown.keys(), key=lambda k: breakdown[k])
        
        # 3. Build text
        score_percent = (score - min_score) / (max_score - min_score) if max_score > min_score else 0.0
        
        if score_percent >= 0.8:
            rating_text = "excellent performance"
            opening = f"This essay demonstrates an {rating_text}, scoring a predicted **{score}/{max_score}**."
        elif score_percent >= 0.6:
            rating_text = "solid performance"
            opening = f"This essay shows a {rating_text} with room for refinement, scoring a predicted **{score}/{max_score}**."
        elif score_percent >= 0.4:
            rating_text = "moderate performance"
            opening = f"This essay represents a {rating_text} with several areas for improvement, scoring a predicted **{score}/{max_score}**."
        else:
            rating_text = "developing writing proficiency"
            opening = f"This essay shows {rating_text} that requires substantial revision, scoring a predicted **{score}/{max_score}**."

        # Category emphasis sentence
        impact_sentence = f"The score was most heavily influenced by the **{dominant_cat}** aspect of your writing (accounting for {breakdown[dominant_cat]:.1f}% of model variance)."
        
        # Strengths sentence
        if strengths:
            strengths_str = " and ".join(strengths)
            strengths_sentence = f"Key strengths driving the score include: **{strengths_str}**."
        else:
            strengths_sentence = "No major positive deviations from average writing patterns were detected."

        # Weaknesses sentence
        if weaknesses:
            weaknesses_str = " and ".join(weaknesses)
            weaknesses_sentence = f"To improve your score, focus on: **{weaknesses_str}**."
        else:
            weaknesses_sentence = "The model did not identify any major negative constraints on your writing quality."
            
        explanation = f"{opening} {impact_sentence} \n\n- **What went well:** {strengths_sentence} \n- **Suggestions for improvement:** {weaknesses_sentence}"
        
        return explanation
