# Walkthrough — Predict Market Bot Repository

## Summary

Built a complete Python repository for a 6-stage prediction market trading bot at `/home/truonglx1/predict/`. The bot analyzes, forecasts, and executes trades on prediction markets with full risk controls.

## Architecture

```
Scan → Research → Predict → Risk → Execute → Compound
 (1)      (2)       (3)      (4)      (5)       (6)
```

## Files Created (22 files)

### Project Config
| File | Purpose |
|------|---------|
| [pyproject.toml](file:///home/truonglx1/predict/pyproject.toml) | Build config, deps, entry point |
| [.env.example](file:///home/truonglx1/predict/.env.example) | All configurable parameters |
| [.gitignore](file:///home/truonglx1/predict/.gitignore) | Standard Python gitignore |
| [README.md](file:///home/truonglx1/predict/README.md) | Full documentation |

### Core Layer
| File | Purpose |
|------|---------|
| [settings.py](file:///home/truonglx1/predict/src/predict_market_bot/config/settings.py) | Pydantic Settings with validation |
| [models.py](file:///home/truonglx1/predict/src/predict_market_bot/core/models.py) | 8 dataclasses + 3 enums |
| [formulas.py](file:///home/truonglx1/predict/src/predict_market_bot/core/formulas.py) | 12 pure math functions |

### Pipeline Stages
| File | Stage | Mode |
|------|-------|------|
| [scanner.py](file:///home/truonglx1/predict/src/predict_market_bot/pipeline/scanner.py) | 1. Scan | Sequential |
| [researcher.py](file:///home/truonglx1/predict/src/predict_market_bot/pipeline/researcher.py) | 2. Research | Parallel |
| [predictor.py](file:///home/truonglx1/predict/src/predict_market_bot/pipeline/predictor.py) | 3. Predict | Domain Intel |
| [risk_manager.py](file:///home/truonglx1/predict/src/predict_market_bot/pipeline/risk_manager.py) | 4. Risk | Context-Aware |
| [executor.py](file:///home/truonglx1/predict/src/predict_market_bot/pipeline/executor.py) | 5. Execute | Sequential |
| [compounder.py](file:///home/truonglx1/predict/src/predict_market_bot/pipeline/compounder.py) | 6. Compound | Iterative |

### Orchestration & Utilities
| File | Purpose |
|------|---------|
| [orchestrator.py](file:///home/truonglx1/predict/src/predict_market_bot/orchestrator.py) | Pipeline coordinator + CLI |
| [store.py](file:///home/truonglx1/predict/src/predict_market_bot/knowledge/store.py) | JSON trade knowledge base |
| [logger.py](file:///home/truonglx1/predict/src/predict_market_bot/utils/logger.py) | Structured logging (structlog) |
| [metrics.py](file:///home/truonglx1/predict/src/predict_market_bot/utils/metrics.py) | Performance tracker vs targets |

## Real API Integration — Phase 7 ✅

### 1. Market Scanner (Polymarket)
- **Gamma API**: Paginated market discovery.
- **CLOB API**: Real-time spread enrichment.

### 3. Market Predictor (XGBoost + Gemini) ✅
- **Statistical Inference**: Integrated `xgboost` with a feature vector including odds, volume, liquidity, and sentiment.
- **Expert Calibration**: Implemented Google Gemini Pro integration for narrative-aware probability adjustment.
- **Fallback Logic**: Robust statistical drift heuristic when models or API keys are missing.
- **Confidence Gating**: Multi-factor confidence score to filter out uncertain predictions.

## Test Results — 74/74 Passed ✅

```
tests/test_formulas.py      — 41 passed 
tests/test_risk_manager.py  — 11 passed 
tests/test_scanner.py       —  9 passed 
tests/test_researcher.py    —  5 passed 
tests/test_predictor.py     —  5 passed (NEW: XGBoost & Gemini)
tests/test_orchestrator.py  —  3 passed 
──────────────────────────────────────────────────────────────
Total: 74 passed in 5.62s
```

## Key Design Decisions

1. **Statistical & Expert Hybrid**: The predictor uses XGBoost for raw numbers and an LLM for "reading between the lines" of news.
2. **Feature Mapping**: Unified the feature vector to 8 core dimensions to ensure consistent model input.
3. **Timezone Uniformity**: All `Signal` and `Market` timestamps now use `timezone.utc` to prevent drift in time-sensitive predictions.

## Key Design Decisions

1. **Keyword-Based Search**: Researcher now transforms long market questions (e.g., "Will ... by ...?") into clean keyword queries to maximize NewsAPI relevancy.
2. **Relevance Gating**: Signals with relevance < 0.3 are ignored during sentiment aggregation to prevent noise from unrelated news.
3. **Timezone-Aware Timestamps**: Unified all models to use `datetime.now(timezone.utc)` for consistent logging across distributed sources.
## 5. Data Persistence (Mock Data Creation)

To avoid repeated API calls, you can now save real-world historical data into a local JSON file to be reused as mock data.

### [NEW] [export_historical_data.py](file:///home/truonglx1/predict/scripts/export_historical_data.py)
This utility fetches the latest resolved markets from Polymarket and persists them to disk.

```bash
# Fetch 20 latest markets and save to data/historical_latest.json
python3 scripts/export_historical_data.py 20 data/historical_latest.json
```

Once saved, move the file to the `data/` directory (if not already there) and run:
```bash
python3 scripts/run_backtest.py data/historical_latest.json
```

This allows for much faster iteration and repeatable tests without relying on the network.

## How to Run

```bash
cd /home/truonglx1/predict
pip install -e ".[dev]"    # Install
predict-bot                # Run pipeline
python3 -m pytest tests/ -v  # Run tests
```
