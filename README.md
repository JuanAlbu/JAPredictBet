# JAPredictBet

A system to identify potential value betting opportunities in football corner markets, using statistical analysis and machine learning models.

**Status:** ✅ MVP Entregue + P0 100% + P1 100% Completo (03-APR-2026)

## 🎯 Goal

- Predict the expected number of corners per match.
- Calculate probabilities for Over/Under lines.
- Compare model probabilities with bookmaker odds to detect potential value.
- Apply ensemble consensus (30 models) for safer predictions.

## 🏛️ Architecture Overview

The system is designed around a core **Betting Engine** (`src/japredictbet/betting/engine.py`) that handles all business logic on a single-event basis.

A backtesting **Pipeline** (`src/japredictbet/pipeline/mvp_pipeline.py`) wraps this engine to process historical datasets in batch, allowing for strategy evaluation.

The decision layer uses **ensemble consensus** (30 models: 70% boosting + 30% linear) with dynamic thresholds:
- Base: 45%
- Tight margin (<0.5): 50% (automatic)

The flow is:
`Dataset -> Feature Engineering -> Model Prediction (30 ensemble) -> Consensus Voting -> Betting Engine -> Value Bet Output`

## 🚀 How to Run

### 1. Installation

Ensure you have Python 3.10+ installed.

```bash
# Install dependencies
python -m pip install -r requirements.txt

# Install the project in editable mode
python -m pip install -e .
```

### 2. Configuration

The pipeline is configured via the `config.yml` file. You can adjust paths, model parameters, and thresholds in this file. By default, it reads from `data/raw/dataset.csv` and uses a mock odds file.

### 3. Execution - Production Pipeline

To run the full backtesting pipeline:

```bash
python run.py
```

The script prints consensus decisions, threshold-level ROI/Yield summary, and best threshold balance (ROI x volume).

### 4. Execution - Experimental Testing (P0 Validated)

For sensitivity testing with cli full control:

```bash
# Default: dynamic lines (mean_lambda per match)
python scripts/consensus_accuracy_report.py --config config.yml

# Fixed line (A/B testing)
python scripts/consensus_accuracy_report.py --config config.yml --fixed-line 9.5

# Random lines for stress testing
python scripts/consensus_accuracy_report.py --config config.yml \
  --random-lines --line-min 5.5 --line-max 11.5

# Custom consensus threshold
python scripts/consensus_accuracy_report.py --config config.yml \
  --consensus-threshold 0.60 \
  --edge-threshold 0.02

# Full list of options
python scripts/consensus_accuracy_report.py --help
```

Reports are saved to `log-test/` with timestamp.

## 📁 Project Structure

- `run.py`: Main entrypoint to execute the pipeline.
- `config.yml`: Configuration file for the pipeline.
- `pyproject.toml`: Project configuration for packaging and installation.
- `src/japredictbet/`: Main source code package.
  - `betting/engine.py`: **Core logic** for probability, EV, and value calculation.
  - `features/`: Feature engineering modules.
  - `models/`: Model training and prediction.
  - `odds/`: Odds collection.
  - `pipeline/`: End-to-end pipeline orchestration for backtesting.
  - `artifacts/models/`: Optional pre-trained ensemble artifacts auto-discovered by `run.py`.
- `data/`: Datasets and other data files.
- `tests/`: Test suite for the project.
- `docs/`: Project documentation.

## 🛠️ Requirements

- Python 3.10+
- `pandas`
- `numpy`
- `scikit-learn`
- `xgboost`
- `lightgbm`
- `scipy`
- `requests`
- `optuna`
- `shap`
- `pytest`
- `PyYAML`

## ✅ P0 + P1 Completion Status

**P0 - 100% COMPLETE** (30-MAR-2026)  
**P0-FIX - 100% COMPLETE** (03-APR-2026) — 6 bugs críticos corrigidos  
**P1 - 100% COMPLETE** (03-APR-2026) — 158/158 testes passando (17 arquivos)

All 9 P0 items successfully implemented and validated with real data:

| Item | Task | Status |
|------|------|--------|
| P0.1 | Remove CLI hardcodes | ✅ |
| P0.2 | Ensemble consensus (30 models) | ✅ |
| P0.3 | Dynamic margin rule | ✅ |
| P0.4 | Feature randomization | ✅ |
| P0.5 | Parallel training | ✅ |
| P0.6 | Temporal holdout (~25%) | ✅ |
| P0.7 | Model artifact versioning | ✅ |
| P0.8 | Model audit logging | ✅ |
| P0.9 | Full CLI parametrization | ✅ |

### Real-World Validation Results

**Full Dataset Test (101 Matches):**
- ✅ 30 models trained successfully
- ✅ Sigma: 0.45 (low ensemble dispersal)
- ✅ Consensus voting: 2 bets, 2 wins (100% accuracy)
- 📁 Report: `log-test/consensus_test_report_20260330_212639.txt`

**Recent Season Test (50 Matches):**
- ✅ 13 matches in holdout with proper historical context
- ✅ Sigma: 0.93 (healthy ensemble variance)
- 📁 Report: `log-test/test_50matches_20260330_215502.txt`

**Random Line Stress Test:**
- ✅ Lines varied 5.5-11.5 with uniform distribution
- ✅ 7 unique line values observed across 13 matches
- 📁 Report: `log-test/test_random_lines_20260330_225446.txt`

## 📜 Project Principles

- Deterministic and reproducible pipelines.
- Modular architecture with a clear separation of concerns.
- A core engine for single-event evaluation, wrapped by other components for batch processing.
- Strictly an **analytics tool** — no real betting or bookmaker connections.
