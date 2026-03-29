# JAPredictBet

A system to identify potential value betting opportunities in football corner markets, using statistical analysis and machine learning models.

## 🎯 Goal

- Predict the expected number of corners per match.
- Calculate probabilities for Over/Under lines.
- Compare model probabilities with bookmaker odds to detect potential value.

## 🏛️ Architecture Overview

The system is designed around a core **Betting Engine** (`src/japredictbet/betting/engine.py`) that handles all business logic on a single-event basis.

A backtesting **Pipeline** (`src/japredictbet/pipeline/mvp_pipeline.py`) wraps this engine to process historical datasets in batch, allowing for strategy evaluation.

The flow is:
`Dataset -> Feature Engineering -> Model Prediction -> Betting Engine -> Value Bet Output`

## 🚀 How to Run

This project is now executable end-to-end.

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

### 3. Execution

To run the full backtesting pipeline:

```bash
python run.py
```

The script will print the value bets found to the console.

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
- `data/`: Datasets and other data files.
- `tests/`: Test suite for the project.
- `docs/`: Project documentation.

## 🛠️ Requirements

- Python 3.10+
- `pandas`
- `numpy`
- `scikit-learn`
- `xgboost`
- `scipy`
- `requests`
- `pytest`
- `PyYAML`

## 📜 Project Principles

- Deterministic and reproducible pipelines.
- Modular architecture with a clear separation of concerns.
- A core engine for single-event evaluation, wrapped by other components for batch processing.