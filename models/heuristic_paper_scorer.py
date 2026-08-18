import logging

logger = logging.getLogger(__name__)

class HeuristicPaperScorer:
    """
    Grades a research paper on a 100-point scale using heuristics based on
    linguistic and readability features.
    """
    def __init__(self):
        pass

    def predict(self, linguistic_features, readability_features):
        score = 0.0
        details = {}
        
        # 1. Section Completeness (Max 30)
        sections = linguistic_features.get("section_completeness", 0.0)
        section_score = min(30.0, sections * 30.0)
        score += section_score
        details['section_score'] = section_score
        
        # 2. Citations (Max 20) - Expecting at least 15 citations for full marks
        citations = linguistic_features.get("citation_count", 0)
        citation_score = min(20.0, (citations / 15.0) * 20.0)
        score += citation_score
        details['citation_score'] = citation_score
        
        # 3. Vocabulary Richness & Academic Tone (Max 30)
        # Academic word density usually around 0.05 to 0.15 in heavy texts
        academic_density = linguistic_features.get("academic_word_density", 0.0)
        academic_score = min(15.0, (academic_density / 0.10) * 15.0)
        
        richness = linguistic_features.get("vocabulary_richness_score", 0.0)
        richness_score = min(15.0, richness * 15.0)
        
        score += academic_score + richness_score
        details['academic_score'] = academic_score
        details['richness_score'] = richness_score
        
        # 4. Readability (Max 20) - Uses the adjusted metrics rewarding complexity
        readability = readability_features.get("composite_readability_score", 0.5)
        readability_score = min(20.0, readability * 20.0)
        score += readability_score
        details['readability_score'] = readability_score
        
        details['total_score'] = round(score, 2)
        
        # Grade category
        if score >= 85:
            details['grade'] = "Accept"
        elif score >= 70:
            details['grade'] = "Minor Revision"
        elif score >= 50:
            details['grade'] = "Major Revision"
        else:
            details['grade'] = "Reject"
            
        return score, details
