# 🎓 AI-Based Automated Essay Scoring System

### Using Transformer Embeddings and Explainable NLP Metrics

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.1%2B-red.svg)](https://pytorch.org/)
[![Transformers](https://img.shields.io/badge/HuggingFace-Transformers-yellow.svg)](https://huggingface.co/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-ff4b4b.svg)](https://streamlit.io/)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Installation](#installation)
- [Dataset Setup](#dataset-setup)
- [Quick Start](#quick-start)
- [Training](#training)
- [Prediction](#prediction)
- [Streamlit UI](#streamlit-ui)
- [Project Structure](#project-structure)
- [Models Compared](#models-compared)
- [Evaluation Metrics](#evaluation-metrics)
- [Explainability](#explainability)
- [Sample Outputs](#sample-outputs)
- [Tech Stack](#tech-stack)
- [Future Scope](#future-scope)

---

## Overview

This project implements an **AI-powered automated essay scoring system** that:

1. **Predicts essay scores** comparable to human evaluators
2. **Explains predictions** using SHAP (SHapley Additive exPlanations)
3. **Combines transformer embeddings** with handcrafted linguistic features

Unlike conventional approaches that simply fine-tune a pre-trained model, this system introduces a **hybrid approach** that fuses:
- RoBERTa transformer embeddings (deep semantic understanding)
- Grammar analysis (error detection)
- Readability metrics (Flesch, Gunning Fog, etc.)
- Vocabulary richness (TTR, MTLD, Hapax Legomena)
- Explainable AI (SHAP feature importance)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Essay Input                           │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              Text Preprocessing                         │
│  • Lowercase  • Remove noise  • Handle ASAP tags       │
└──────────────────────┬──────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          │                         │
          ▼                         ▼
┌───────────────────┐   ┌───────────────────────────────┐
│   RoBERTa-base    │   │   Feature Extraction          │
│   Embedding       │   │   • Grammar (LanguageTool)    │
│   (768-dim)       │   │   • Readability (textstat)    │
│                   │   │   • Linguistics (spaCy)       │
│   → PCA (128-dim) │   │   • 25+ handcrafted features │
└────────┬──────────┘   └──────────────┬────────────────┘
         │                             │
         └──────────┬──────────────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  Feature Fusion     │
         │  (153-dim vector)   │
         └─────────┬───────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │  XGBoost Regressor  │
         └─────────┬───────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │  Predicted Score    │
         └─────────┬───────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │  SHAP Explainer     │
         │  (TreeSHAP)         │
         └─────────────────────┘
```

---

## Features

| Feature | Description |
|:---|:---|
| 🤖 **6 Models Compared** | Linear Regression, Random Forest, BiLSTM, BERT, RoBERTa, Hybrid |
| 📊 **Comprehensive Metrics** | QWK, MAE, RMSE, Pearson Correlation |
| 🔍 **Explainable AI** | SHAP-based feature importance and natural language explanations |
| 📝 **25+ Linguistic Features** | Grammar, readability, vocabulary, structure |
| 🎨 **Premium Streamlit UI** | Dark theme, glassmorphism, interactive charts |
| 📈 **Visualization Suite** | Comparison charts, confusion matrices, training curves |

---

## Installation

### Prerequisites
- Python 3.9 or higher
- pip (Python package manager)
- Java Runtime (optional, for LanguageTool grammar checking)

### Step 1: Clone/Navigate to the project
```bash
cd EssayScoringAI
```

### Step 2: Create a virtual environment (recommended)
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### Step 3: Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Download NLP models
```bash
python -m spacy download en_core_web_sm
python -m nltk.downloader punkt averaged_perceptron_tagger stopwords
```

---

## Dataset Setup

This project uses the **ASAP (Automated Student Assessment Prize)** dataset from Kaggle.

### Download the Dataset

1. Visit: https://www.kaggle.com/c/asap-aes/data
2. Download `training_set_rel3.tsv`
3. Place it in the `dataset/` folder:
   ```
   EssayScoringAI/dataset/training_set_rel3.tsv
   ```

### Alternative: Kaggle CLI
```bash
pip install kaggle
kaggle competitions download -c asap-aes
```

### Dataset Overview

| Essay Set | Type | Score Range | Essays |
|:---:|:---|:---:|:---:|
| 1 | Argumentative | 2-12 | ~1,783 |
| 2 | Argumentative | 1-6 | ~1,800 |
| 3 | Source-Dependent | 0-3 | ~1,726 |
| 4 | Source-Dependent | 0-3 | ~1,772 |
| 5 | Source-Dependent | 0-4 | ~1,805 |
| 6 | Source-Dependent | 0-4 | ~1,800 |
| 7 | Narrative | 0-30 | ~1,569 |
| 8 | Narrative | 0-60 | ~723 |

---

## Quick Start

### Test with Sample Data (No dataset needed)
```bash
python train.py --sample --model baseline
```

### Full Training Pipeline
```bash
python train.py --model all
```

### Run Streamlit UI
```bash
streamlit run streamlit_app.py
```

---

## Training

### Train All Models
```bash
python train.py
```

### Train Specific Models
```bash
# Only baselines (fast)
python train.py --model baseline

# Only the hybrid model
python train.py --model hybrid

# LSTM and BERT
python train.py --model lstm bert

# With custom epochs
python train.py --model hybrid --epochs 100
```

### Training Output
- Trained models saved to `models/saved/`
- Evaluation results saved to `outputs/results/`
- Comparison charts saved to `outputs/graphs/`

---

## Prediction

### Score a Single Essay
```bash
python predict.py --essay "Your essay text here..." --set 1
```

### Score from File
```bash
python predict.py --file essay.txt --set 2 --model hybrid
```

### With SHAP Explanation
```bash
python predict.py --essay "..." --set 1 --model hybrid --explain
```

### JSON Output
```bash
python predict.py --essay "..." --set 1 --json
```

---

## Streamlit UI

Launch the premium web interface:
```bash
streamlit run streamlit_app.py
```

The UI provides:
- 📝 Essay input (type or upload)
- 🎯 Predicted score with gauge chart
- 📊 Score breakdown (grammar, readability, vocabulary, structure, coherence)
- 💬 AI-generated feedback with strengths and weaknesses
- 🔍 SHAP feature importance chart
- 📋 Detailed metrics table

---

## Project Structure

```
EssayScoringAI/
├── dataset/                     # Dataset files
│   ├── download_dataset.py      # Kaggle download helper
│   └── training_set_rel3.tsv    # ASAP dataset (user-provided)
├── preprocessing/               # Text preprocessing
│   ├── text_cleaner.py          # Text cleaning pipeline
│   └── data_loader.py           # Dataset loading & splitting
├── feature_engineering/         # Feature extraction
│   ├── grammar_features.py      # Grammar error detection
│   ├── readability_features.py  # Readability metrics
│   ├── linguistic_features.py   # Vocabulary & structure features
│   └── transformer_embeddings.py# RoBERTa/BERT embedding extraction
├── models/                      # Model definitions
│   ├── baseline_models.py       # Linear Regression, Random Forest
│   ├── lstm_model.py            # BiLSTM with Attention
│   ├── bert_model.py            # BERT fine-tuned scorer
│   ├── roberta_model.py         # RoBERTa fine-tuned scorer
│   └── hybrid_model.py          # Proposed hybrid model ⭐
├── training/                    # Training pipeline
│   ├── config.py                # Centralized configuration
│   └── trainer.py               # Training orchestrator
├── evaluation/                  # Evaluation & visualization
│   ├── metrics.py               # QWK, MAE, RMSE, Pearson
│   ├── evaluator.py             # Model evaluation pipeline
│   └── visualizations.py        # Charts and plots
├── explainability/              # Explainable AI
│   ├── shap_explainer.py        # SHAP-based explanations
│   └── feature_importance.py    # Feature importance analysis
├── utils/                       # Utilities
│   └── helpers.py               # Helper functions
├── docs/                        # Documentation
│   └── documentation.md         # Full academic documentation
├── outputs/                     # Generated outputs
│   ├── graphs/                  # Plots and charts
│   └── results/                 # Evaluation results
├── streamlit_app.py             # Streamlit web interface
├── train.py                     # Training CLI
├── predict.py                   # Prediction CLI
├── requirements.txt             # Dependencies
└── README.md                    # This file
```

---

## Models Compared

| # | Model | Type | Input | Key Idea |
|:---:|:---|:---|:---|:---|
| 1 | Linear Regression | Traditional ML | Handcrafted features | Baseline |
| 2 | Random Forest | Traditional ML | Handcrafted features | Ensemble baseline |
| 3 | BiLSTM + Attention | Deep Learning | Word embeddings | Sequence modeling |
| 4 | BERT (Fine-tuned) | Transformer | Raw text | Contextual embeddings |
| 5 | RoBERTa (Fine-tuned) | Transformer | Raw text | Improved BERT |
| 6 | **Hybrid** ⭐ | Novel | Text + Features | Our contribution |

---

## Evaluation Metrics

| Metric | Description | Range |
|:---|:---|:---|
| **QWK** | Quadratic Weighted Kappa — agreement with human raters | -1 to 1 (1 = perfect) |
| **MAE** | Mean Absolute Error | 0+ (0 = perfect) |
| **RMSE** | Root Mean Squared Error | 0+ (0 = perfect) |
| **Pearson** | Pearson Correlation Coefficient | -1 to 1 (1 = perfect) |

---

## Explainability

The system uses **SHAP (SHapley Additive exPlanations)** to explain predictions:

- **TreeSHAP** for the hybrid model (fast, exact Shapley values)
- **Feature importance bar charts** showing which features pushed the score up/down
- **Natural language explanations** describing strengths and weaknesses
- **Category breakdown** (grammar, readability, vocabulary, embeddings)

---

## Tech Stack

| Category | Technologies |
|:---|:---|
| **Language** | Python 3.9+ |
| **Deep Learning** | PyTorch, HuggingFace Transformers |
| **NLP** | spaCy, NLTK, textstat, LanguageTool |
| **ML** | scikit-learn, XGBoost |
| **Visualization** | Matplotlib, Seaborn, Plotly |
| **Explainability** | SHAP |
| **Web UI** | Streamlit |
| **Data** | Pandas, NumPy |

---

## Future Scope

1. **Multi-Task Learning** — Predict sub-scores (organization, grammar, content) simultaneously
2. **Cross-Prompt Generalization** — Train a model that works across unseen essay prompts
3. **LLM Integration** — Use GPT-4/Llama for generating detailed feedback
4. **Attention Visualization** — Highlight important words/sentences in the essay
5. **Fairness Analysis** — Evaluate scoring bias across demographic groups
6. **Real-Time Feedback** — Provide suggestions while the student writes

---

## License

This project is for academic and research purposes.

---

## Acknowledgments

- **Dataset**: The Hewlett Foundation, ASAP Competition on Kaggle
- **Pre-trained Models**: HuggingFace Model Hub (BERT, RoBERTa)
- **Explainability**: SHAP library by Scott Lundberg
