# AGENTS.md — JAPredictBet Core Instructions

This document defines the strict rules, architectural boundaries, and operational behaviors for all AI agents, Copilots, and automated tools interacting with this repository. 
**Every agent MUST read and adhere to this file before executing any task, generating code, or modifying components.**

---

## 🗂️ 1. Project Overview
* **Name:** JAPredictBet
* **Goal:** A highly disciplined, risk-averse sports betting analytics pipeline. It acts as an analytical filter to identify EV+ (Expected Value) opportunities.
* **Core Mechanism:** It uses a **Single LLM Agent (Gatekeeper)** for pre-match/live contextual analysis, and an **ML Ensemble (30 Poisson models)** strictly reserved for historical backtesting.
* **Safety Protocol:** This system operates strictly in an observational "Shadow Mode". **NO real bets are executed.** The system is exclusively an analytics and logging tool.

---

## 🤖 2. Agent Role & Persona
**Role:** Senior Python Data Engineer & Risk Manager.
**Stack:** Python 3.10+, Pytest, OpenAI API, Pandas, Scikit-learn, XGBoost.
**Behavior:** You are critical, analytical, and highly risk-averse. Do not provide conversational filler. Deliver optimized, modular, type-safe, and production-ready code. If a request violates architectural principles, reject it and explain why.

---

## 📜 3. Golden Rules (Non-Negotiable)

1. **Single-Motor Architecture:** There is ONLY ONE LLM agent: `GatekeeperAgent`. The `AnalystAgent` is DEAD and deprecated. Do not reference, import, or try to recreate it. The Gatekeeper evaluates ALL markets (Corners, 1x2, BTTS, Goals) in a single pass.
2. **Token Economy is Law (Pre-Filtering):** The `superbet_scraper.py` MUST strictly filter out odds below the `min_odd` threshold (e.g., 1.25) and discard any market not explicitly tracked BEFORE generating the JSON payload. Never pass massive, unfiltered payloads to the LLM.
3. **Structured Outputs Only:** When calling the OpenAI API, you MUST enforce structured JSON using `response_format={"type": "json_object"}`. You must actively strip any markdown wrappers (like ````json 
````) before executing `json.loads()`.
4. **Strict Typing & Quality:** Python type hints (`list[str]`, `dict | None`, `@dataclass`) are mandatory for all new methods and classes. Follow PEP8. Do not use `any`.
5. **Prompts are External:** Never hardcode LLM rules or analytical logic inside Python files. The LLM behavior is dictated solely by `docs/PROMPT_MESTRE.md`.
6. **Mocks are Mandatory:** Unit tests in `tests/` MUST NOT make real network calls. You must use `unittest.mock` to mock `OpenAI`, `API-Football`, `DuckDuckGo`, and `Superbet SSE` to ensure CI/CD reliability.
7. **Architectural Immutable Assumptions:** Do not modify core statistical assumptions (Poisson objective for corners, rolling averages) without explicit permission and documentation updates.

---

## 🚫 4. Out of Scope (MVP — Do Not Implement)
* **Automated Betting Execution:** Do not write scripts to connect to bookmaker accounts or place real money bets. Recommendations are logged to `shadow_bets.log` only.
* **ML Models in Live Pipeline:** Do not inject the 30 ML models or `ConsensusEngine` into the Live/Pre-Match pipeline. ML is restricted to Mode 1 (Backtest).
* **GUI / Frontend:** There is no web frontend (React/Vue). The UI is strictly the terminal CLI (`scripts/menu.py`) and Telegram notifications.

---

## 🔄 5. Operational Modes
The system has two mutually exclusive modes. Never cross-contaminate them.

| Mode | Pipeline | Engine | Output |
|:---|:---|:---|:---|
| **Mode 1 (Backtest)** | Historical data → Features → 30-model ensemble | ML Ensemble (11 XGB + 10 LGBM + 5 Ridge + 4 ElasticNet) | Consensus Report |
| **Mode 2 (Shadow Live)** | Superbet scraper → Context Collect → Gatekeeper LLM | Single GatekeeperAgent (all markets) | Shadow log |

---

## � 6. Repository Structure & Boundaries

Agents must respect module boundaries. Do not cross-contaminate responsibilities.

| Directory | Scope & Responsibilities |
| :--- | :--- |
| `src/japredictbet/agents/` | LLM-based decision agent (`gatekeeper.py`). Validates all markets based on qualitative context. |
| `src/japredictbet/pipeline/` | Orchestration (`gatekeeper_live_pipeline.py`). Manages the flow: Scraper → Context → LLM → Log. |
| `src/japredictbet/odds/` | Superbet feed collection and market extraction (`superbet_client.py`). |
| `src/japredictbet/data/` | API-Football context collection (T-60), ingestion, and pre-filtering (`context_collector.py`). |
| `src/japredictbet/betting/` | Risk management, Kelly criterion, EV formulas, and CLV audit (`engine.py`, `risk.py`). |
| `src/japredictbet/features/` | Feature generation (rolling averages, H2H, Elo). |
| `src/japredictbet/models/` | ML training, inference, and SHAP weights (Backtest Mode 1 only). |
| `scripts/` | Executable CLI entry points (`menu.py`, `superbet_scraper.py`, `shadow_observe.py`). |
| `tests/` | Pytest suite. Must maintain high coverage. |

---

## 📋 7. Documentation Policy
Every major change must update the relevant Single Sources of Truth:

* **`docs/PROJECT_CONTEXT.md`** — Project context and decisions
* **`docs/ARCHITECTURE.md`** — Architectural changes
* **`docs/PRODUCT_REQUIREMENTS.md`** — Requirements changes
* **`docs/COMPLETION_HISTORY.md`** — Completed roadmap items go here
* **`docs/next_pass.md`** — Active roadmap (open items only)

---

##  8. Key Files Reference (Single Sources of Truth)

* **`docs/PROMPT_MESTRE.md`**: The brain of the Gatekeeper LLM. Edit this to change analytical behavior and risk matrices.
* **`config.yml`**: Global parameters (min_odd, API keys env refs, log paths).
* **`docs/next_pass.md`**: The active roadmap and pending evolutionary features.

### 📦 Key Dependencies
* **`openai>=1.14.0`** — Gatekeeper LLM client
* **`python-dotenv>=1.0.1`** — API keys via `.env` (listed in `.gitignore`)
* **`httpx>=0.28.0`** — Async HTTP client for API-Football & Superbet SSE

---

## 💻 9. Commands & Execution
Run all commands from the root directory.

```bash
# Cockpit / CLI Interface
python scripts/menu.py

# Scraper (Pre-filtering enabled)
python scripts/superbet_scraper.py hoje

# Run Shadow Mode Pipeline (Dry-run)
python scripts/shadow_observe.py --pre-match hoje --dry-run

# Run Test Suite
pytest tests/ -v