# ============================================================
# streamlit_app.py
# Streamlit Web Interface for AI Essay Scoring System
# ============================================================
# A premium, modern dashboard that allows users to:
# - Upload or type essays
# - Get AI-predicted scores with detailed breakdowns
# - View SHAP-based explanations
# - Explore feature importance
#
# Run with: streamlit run streamlit_app.py
# ============================================================

import os
import sys
import json
import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from training.config import Config

# ---- Page Configuration ----
st.set_page_config(
    page_title="EssayScoringAI | Smart Essay Grading",
    page_icon="A",
    layout="wide"
)

def inject_custom_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap');

    .stApp {
        font-family: 'Poppins', sans-serif;
        background-color: #f7f9fc;
        color: #333333;
    }

    .hero-header {
        background: linear-gradient(135deg, #4A90D9 0%, #9B59B6 100%);
        padding: 2.5rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        box-shadow: 0 10px 20px rgba(74, 144, 217, 0.2);
        color: white;
        text-align: center;
    }
    .hero-header h1 {
        color: white;
        font-size: 2.5rem;
        font-weight: 800;
        margin: 0 0 10px 0;
    }
    .hero-header p {
        font-size: 1.1rem;
        margin: 0;
        opacity: 0.9;
    }
    
    .how-it-works {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        margin-top: 1.5rem;
    }
    
    .score-card {
        background: white;
        padding: 2.5rem;
        border-radius: 20px;
        text-align: center;
        box-shadow: 0 8px 30px rgba(0,0,0,0.08);
        border-top: 8px solid #7ED321;
    }
    .score-value {
        font-size: 4rem;
        font-weight: 800;
        color: #333;
        line-height: 1;
    }
    .letter-grade {
        font-size: 2.5rem;
        font-weight: 700;
        color: #7ED321;
        margin-top: 10px;
    }
    
    .metric-box {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        text-align: center;
        border: 2px solid #f0f0f0;
        transition: transform 0.2s;
    }
    .metric-box:hover {
        transform: translateY(-5px);
        border-color: #4A90D9;
    }
    .metric-title {
        font-weight: 600;
        color: #555;
        font-size: 1.1rem;
    }
    .metric-icon {
        font-size: 1.2rem;
        font-weight: 700;
        color: #4A90D9;
        margin-bottom: 10px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    .report-card {
        background: white;
        padding: 2rem;
        border-radius: 20px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.08);
    }
    .strength-card {
        background: #e8f5e9;
        border-left: 4px solid #7ED321;
        padding: 1rem;
        border-radius: 0 8px 8px 0;
        margin-bottom: 1rem;
        color: #2e7d32;
    }
    .weakness-card {
        background: #fff3e0;
        border-left: 4px solid #F5A623;
        padding: 1rem;
        border-radius: 0 8px 8px 0;
        margin-bottom: 1rem;
        color: #e65100;
    }
    .recommendation-box {
        background: #e3f2fd;
        border-left: 4px solid #4A90D9;
        padding: 1.5rem;
        border-radius: 0 12px 12px 0;
        margin-top: 1.5rem;
        color: #1565c0;
        font-weight: 500;
    }
    
    [data-testid="stSidebar"] {
        background-color: white;
        box-shadow: 2px 0 10px rgba(0,0,0,0.05);
    }
    
    h2, h3 {
        color: #4A90D9;
        font-weight: 700;
    }
    </style>
    """, unsafe_allow_html=True)

@st.cache_resource
def load_config():
    """Load and cache the configuration."""
    return Config()

@st.cache_resource
def load_essay_scorer():
    """Load and cache the trained hybrid model."""
    config = load_config()
    model_path = os.path.join(config.models_dir, "hybrid_model")

    if not os.path.exists(model_path) and not os.path.exists(model_path + ".pkl"):
        return None

    try:
        from models.hybrid_model import HybridScorer
        model = HybridScorer(config)
        model.load(model_path)
        return model
    except Exception as e:
        st.error(f"Error loading model: {e}")
        return None

def analyze_essay(essay_text: str) -> dict:
    """
    Run full analysis on an essay: grammar, readability, linguistics.
    
    Args:
        essay_text: Raw essay text
        
    Returns:
        Dictionary with all analysis results
    """
    from preprocessing.text_cleaner import TextCleaner
    from feature_engineering.grammar_features import GrammarAnalyzer
    from feature_engineering.readability_features import ReadabilityAnalyzer
    from feature_engineering.linguistic_features import LinguisticAnalyzer

    cleaner = TextCleaner()
    cleaned_text = cleaner.clean(essay_text)

    grammar = GrammarAnalyzer()
    readability = ReadabilityAnalyzer()
    linguistic = LinguisticAnalyzer()

    return {
        'cleaned_text': cleaned_text,
        'grammar': grammar.analyze(cleaned_text),
        'readability': readability.analyze(cleaned_text),
        'linguistic': linguistic.analyze(cleaned_text),
    }

SAMPLE_ESSAYS = {
    "High Quality Essay": """
    The impact of technology on modern education cannot be overstated. Over the past decade,
    digital tools have fundamentally transformed how students learn, how teachers instruct,
    and how educational institutions operate. From interactive whiteboards to personalized
    learning platforms, technology has created unprecedented opportunities for engagement
    and accessibility.

    One of the most significant advantages of educational technology is its ability to
    personalize learning experiences. Adaptive learning platforms can assess individual
    student performance in real-time and adjust the difficulty and pace of content accordingly.
    This ensures that advanced students remain challenged while struggling students receive
    additional support, effectively addressing the diverse learning needs within a single
    classroom.

    Furthermore, technology has democratized access to education. Online courses, digital
    textbooks, and virtual laboratories have made quality educational resources available
    to students regardless of their geographical location or socioeconomic status. Students
    in rural areas can now access the same caliber of instruction as those in major
    metropolitan centers, significantly reducing educational inequality.

    However, the integration of technology in education is not without challenges. Digital
    distraction remains a persistent concern, as students may be tempted to engage with
    social media or entertainment during study time. Additionally, the digital divide—the
    gap between those with access to technology and those without—continues to be a
    significant barrier to equitable education.

    In conclusion, while technology presents remarkable opportunities for enhancing
    education, it is crucial that educators, policymakers, and technologists work
    collaboratively to address the associated challenges. By doing so, we can ensure
    that technology serves as a bridge to knowledge rather than a barrier.
    """,

    "Medium Quality Essay": """
    Technology is very important in schools today. Many students use computers and
    tablets to learn new things. Teachers also use technology to make their classes
    more interesting.

    One good thing about technology is that students can look up information quickly
    on the internet. They dont have to go to the library every time they need to
    find something. This saves a lot of time and makes homework easier.

    But there are also some problems with using technology in schools. Some students
    get distracted by games and social media when they should be studying. Also not
    every student has a computer at home which is not fair.

    I think technology is good for education but teachers need to make sure students
    use it properly. Schools should also make sure all students have access to computers.
    """,

    "Low Quality Essay": """
    technology is good i think. we use it alot in school. computers are cool and stuff.
    my teacher use projector in class. i like watching videos in class better than reading
    books. sometimes the internet dont work and its annoying. i think we need more
    technology in schools thats all i have to say about it.
    """
}

def get_letter_grade(score, max_score):
    pct = score / max_score
    if pct >= 0.9: return "A+", "#7ED321"
    elif pct >= 0.8: return "A", "#7ED321"
    elif pct >= 0.7: return "B+", "#8BC34A"
    elif pct >= 0.6: return "B", "#CDDC39"
    elif pct >= 0.5: return "C", "#FFEB3B"
    elif pct >= 0.4: return "D", "#F5A623"
    else: return "F", "#E74C3C"

def get_feedback_label(score):
    if score >= 80: return "Excellent", "#7ED321"
    elif score >= 60: return "Good", "#F5A623"
    else: return "Needs Work", "#E74C3C"

def main():
    inject_custom_css()
    config = load_config()

    with st.sidebar:
        st.markdown("## Settings")
        st.markdown("---")
        
        st.markdown("### Essay Prompt & Rubric Scale")
        essay_set = st.selectbox(
            "Select Prompt Type",
            options=list(range(1, 9)),
            format_func=lambda x: config.essay_set_names.get(x, f"Set {x}"),
            help="Select the prompt type to match your essay's grading scale (e.g. Persuasive, Narrative, or Source-Based)."
        )
        min_score, max_score = config.score_ranges[essay_set]
        st.caption(
            "**Note:** In benchmark essay datasets, different assignment types have different max scores "
            f"(e.g., out of 6 vs 60). Selected scale: **{min_score} to {max_score}**."
        )
        
        st.markdown("### Scoring Model")
        model_choice = st.selectbox(
            "Model",
            options=['hybrid', 'roberta', 'bert', 'random_forest', 'cart'],
            format_func=lambda x: config.model_names.get(x, x),
            help="The AI model used to score your essay."
        )
        
        st.markdown("### Sample Essays")
        sample_choice = st.selectbox(
            "Load a sample essay",
            options=["(None)"] + list(SAMPLE_ESSAYS.keys())
        )
        
        st.markdown("---")
        st.markdown("### About")
        st.info(
            "This project was built to explore how AI can assist in essay grading. "
            "It uses transformer-based NLP models combined with traditional linguistic features. \n\n"
            "**Technologies:** Python, RoBERTa, XGBoost, SHAP, Streamlit"
        )

    st.markdown("""
    <div class="hero-header">
        <h1>EssayScoringAI</h1>
        <p>Automated Essay Scoring using Transformer Embeddings and Explainable NLP</p>
    </div>
    """, unsafe_allow_html=True)
    
    default_text = SAMPLE_ESSAYS.get(sample_choice, "") if sample_choice != "(None)" else ""
    
    upload_file = st.file_uploader("Upload your Research Paper (PDF)", type=["pdf"])
    if upload_file is not None:
        from preprocessing.pdf_parser import extract_text_from_pdf
        essay_text = extract_text_from_pdf(upload_file.read())
        st.success("PDF extracted successfully!")
    else:
        essay_text = st.text_area("Or write/paste your research paper here:", value=default_text, height=300)
    
    col_btn_1, col_btn_2, col_btn_3 = st.columns([1, 2, 1])
    with col_btn_2:
        analyze_clicked = st.button("Analyze Essay", use_container_width=True, type="primary")
        
    if analyze_clicked and essay_text and len(essay_text.strip()) > 10:
        with st.spinner("Analyzing essay..."):
            analysis = analyze_essay(essay_text)
            
            grammar_data = analysis['grammar']
            readability_data = analysis['readability']
            linguistic_data = analysis['linguistic']
            
            grammar_score = grammar_data.get('grammar_score', 0.8) * 100
            readability_score = readability_data.get('composite_readability_score', 0.5) * 100
            vocabulary_score = linguistic_data.get('vocabulary_richness_score', 0.5) * 100
            
            word_count = linguistic_data.get('word_count', 0)
            sentence_count = linguistic_data.get('sentence_count', 0)
            avg_sent_len = linguistic_data.get('avg_sentence_length', 15)
            structure_score = min(100, max(0, 100 - abs(avg_sent_len - 18) * 5))
            
            ttr = linguistic_data.get('type_token_ratio', 0.5)
            mtld = linguistic_data.get('lexical_diversity_mtld', 50)
            coherence_score = min(100, (ttr * 50 + min(mtld, 100) * 0.5))

            from models.heuristic_paper_scorer import HeuristicPaperScorer
            scorer = HeuristicPaperScorer()
            predicted_score, details = scorer.predict(linguistic_data, readability_data)
            min_score, max_score = 0, 100
                
        st.markdown("---")
        
        letter, color = get_letter_grade(predicted_score - min_score, max_score - min_score)
        
        col_score, col_report = st.columns([1, 2])
        with col_score:
            st.markdown(f"""
            <div class="score-card" style="border-top-color: {color};">
                <h3 style="margin-top:0; color:#555;">Predicted Score</h3>
                <div class="score-value">{predicted_score}<span style="font-size:1.5rem; color:#aaa;">/{max_score}</span></div>
                <div class="letter-grade" style="color: {color};">{letter}</div>
                <p style="margin-top:15px; color:#888;">For Essay Set {essay_set}</p>
            </div>
            """, unsafe_allow_html=True)
            
            progress_pct = (predicted_score - min_score) / (max_score - min_score) if max_score > min_score else 0
            st.progress(progress_pct)
            
        with col_report:
            st.markdown("""
            <div class="report-card">
                <h3 style="margin-top:0;">Writing Assessment</h3>
            """, unsafe_allow_html=True)
            
            strengths = []
            if details.get('section_score', 0) >= 25: strengths.append("Excellent structural completeness.")
            if details.get('citation_score', 0) >= 15: strengths.append("Good use of citations and references.")
            if details.get('academic_score', 0) >= 10: strengths.append("Strong academic vocabulary usage.")
            
            weaknesses = []
            if details.get('section_score', 0) < 20: weaknesses.append("Missing key sections like Abstract or Methodology.")
            if details.get('citation_score', 0) < 10: weaknesses.append("Insufficient citations. Ensure all claims are backed by research.")
            if details.get('academic_score', 0) < 8: weaknesses.append("Academic tone could be improved.")
            
            if not strengths: strengths.append("The paper demonstrates effort in research.")
            
            for s in strengths[:3]:
                st.markdown(f'<div class="strength-card"><b>Strength:</b> {s}</div>', unsafe_allow_html=True)
                
            for w in weaknesses[:2]:
                st.markdown(f'<div class="weakness-card"><b>Area for Improvement:</b> {w}</div>', unsafe_allow_html=True)
                
            st.markdown("""
                <div class="recommendation-box">
                    <b>Recommendation:</b> Reading your essay aloud before submission can help identify awkward phrasing and overlooked errors.
                </div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("### Score Breakdown by Category")
        
        c1, c2, c3, c4, c5 = st.columns(5)
        
        def render_metric(col, title, score, desc):
            label, metric_color = get_feedback_label(score)
            with col:
                st.markdown(f"""
                <div class="metric-box">
                    <div class="metric-icon">{title}</div>
                    <div style="font-size:1.8rem; font-weight:700; color:{metric_color};">{score:.0f}%</div>
                    <div style="font-size:0.9rem; color:#666; margin-top:5px;">{label}</div>
                    <div style="font-size:0.8rem; color:#888; margin-top:5px;">{desc}</div>
                </div>
                """, unsafe_allow_html=True)
                st.progress(score / 100.0)
                
        render_metric(c1, "Grammar", grammar_score, "Correctness of grammar and spelling")
        render_metric(c2, "Readability", readability_score, "Clarity and ease of reading")
        render_metric(c3, "Vocabulary", vocabulary_score, "Diversity of word choice")
        render_metric(c4, "Structure", structure_score, "Sentence and paragraph organization")
        render_metric(c5, "Coherence", coherence_score, "Logical flow of ideas")
        
        with st.expander("What do these scores mean?"):
            st.markdown("""
            * **Grammar** — Evaluates adherence to grammatical rules and spelling accuracy using language-tool-python.
            * **Readability** — Composite score from Flesch-Kincaid, Gunning Fog, and other standard readability indices.
            * **Vocabulary** — Measures lexical diversity through type-token ratio, hapax legomena, and MTLD.
            * **Structure** — Assesses sentence length variation and paragraph organization.
            * **Coherence** — Proxy metric combining lexical diversity with type-token ratio to gauge idea flow.
            """)

        st.markdown("### Feature Importance (SHAP Analysis)")
        try:
            model = load_essay_scorer()
            if model is not None:
                feature_matrix = model.get_feature_matrix([essay_text])
                feature_names = model.get_feature_names()
                xgb_model = model.get_model()

                from explainability.shap_explainer import SHAPExplainer
                explainer = SHAPExplainer(xgb_model, feature_names)
                explanation = explainer.explain_single(feature_matrix[0])

                shap_values = explanation['shap_values']
                
                pairs = sorted(zip(feature_names, shap_values), key=lambda x: abs(x[1]), reverse=True)[:10]
                pairs.reverse()
                names = [p[0].replace('_', ' ').title() for p in pairs]
                vals = [p[1] for p in pairs]
                colors = ['#7ED321' if v >= 0 else '#F5A623' for v in vals]
                
                fig = go.Figure(go.Bar(
                    x=vals, y=names, orientation='h', marker_color=colors,
                    text=[f"{v:+.2f}" for v in vals], textposition='outside'
                ))
                fig.update_layout(
                    title="Top Feature Contributions to Predicted Score",
                    height=350, margin=dict(l=10, r=40, t=40, b=40),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

                from explainability.feature_importance import FeatureImportanceAnalyzer
                analyzer = FeatureImportanceAnalyzer(feature_names)
                nl_explanation = analyzer.generate_explanation(
                    shap_values, feature_matrix[0], feature_names,
                    predicted_score, essay_set, config
                )
                st.info(f"**Interpretation:** {nl_explanation}")
            else:
                st.caption("SHAP-based explanations require a trained hybrid model. Run `python train.py --model hybrid` to enable.")
        except Exception as e:
            st.warning(f"Feature importance unavailable: {e}")
            
        st.markdown("### Detailed Feature Metrics")
        st.markdown("Complete feature values extracted from the essay, grouped by category.")
        
        metrics_data = {
            "Category": [
                "Length", "Length", "Length", "Length",
                "Vocabulary", "Vocabulary", "Vocabulary", "Vocabulary", "Vocabulary", "Vocabulary",
                "Readability", "Readability", "Readability",
                "Grammar", "Grammar", "Grammar"
            ],
            "Metric": [
                "Word Count", "Sentence Count", "Avg Word Length", "Avg Sentence Length",
                "Type-Token Ratio", "Lexical Diversity (MTLD)", "Noun Ratio", "Verb Ratio", "Adjective Ratio", "Long Word Ratio",
                "Flesch Reading Ease", "Flesch-Kincaid Grade", "Gunning Fog Index",
                "Grammar Errors", "Spelling Errors", "Grammar Score"
            ],
            "Value": [
                word_count, sentence_count, f"{linguistic_data.get('avg_word_length', 0):.2f}", f"{avg_sent_len:.1f}",
                f"{linguistic_data.get('type_token_ratio', 0):.3f}", f"{linguistic_data.get('lexical_diversity_mtld', 0):.1f}", 
                f"{linguistic_data.get('noun_ratio', 0):.3f}", f"{linguistic_data.get('verb_ratio', 0):.3f}", 
                f"{linguistic_data.get('adj_ratio', 0):.3f}", f"{linguistic_data.get('long_word_ratio', 0):.3f}",
                f"{readability_data.get('flesch_reading_ease', 0):.1f}", f"{readability_data.get('flesch_kincaid_grade', 0):.1f}", 
                f"{readability_data.get('gunning_fog', 0):.1f}",
                grammar_data.get('grammar_error_count', 0), grammar_data.get('spelling_error_count', 0), f"{grammar_score:.1f}%"
            ]
        }
        metrics_df = pd.DataFrame(metrics_data)
        
        def color_categories(val):
            color = '#f9f9f9'
            if val == 'Length': color = '#e3f2fd'
            elif val == 'Vocabulary': color = '#f3e5f5'
            elif val == 'Readability': color = '#e8f5e9'
            elif val == 'Grammar': color = '#fff3e0'
            return f'background-color: {color}'
            
        styled_df = metrics_df.style.map(color_categories, subset=['Category'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("### System Pipeline")
        st.markdown("The scoring pipeline processes essays through five stages:")
        c_pipe1, c_pipe2, c_pipe3, c_pipe4, c_pipe5 = st.columns(5)
        with c_pipe1: st.info("**1. Input**\nRaw essay text is received.")
        with c_pipe2: st.info("**2. Preprocessing**\nText normalization and cleaning.")
        with c_pipe3: st.info("**3. Feature Extraction**\n26 linguistic, readability, and grammar features.")
        with c_pipe4: st.info("**4. Model Inference**\nML model predicts a normalized score.")
        with c_pipe5: st.info("**5. Analysis Report**\nScore and detailed feedback generated.")

if __name__ == "__main__":
    main()
