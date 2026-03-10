# Phase 7: External API Integration — Market Predictor

This phase makes the `MarketPredictor` functional by integrating XGBoost for statistical inference and Google Gemini for expert-level probability calibration.

## User Review Required

> [!IMPORTANT]
> **API Keys Required**: To use the LLM calibration, a **Google Gemini** API key is required. 
> **XGBoost Model**: The system will look for a trained model at `data/models/xgboost_market_v1.json`. If not found, it will use a structured heuristic as a fallback.

## Proposed Changes

### [predict-market-bot]

#### [MODIFY] [settings.py](file:///home/truonglx1/predict/src/predict_market_bot/config/settings.py)
- Add `gemini_api_key` to `BotSettings`.
- Add `xgboost_model_path` setting.

#### [MODIFY] [predictor.py](file:///home/truonglx1/predict/src/predict_market_bot/pipeline/predictor.py)
- Implement `_predict_xgboost()` using the `xgboost` library and `DMatrix`.
- Implement `_calibrate_llm()` using Google Gemini API (`httpx`).
- Refine `_extract_features()` to ensure all inputs for XGBoost are present.
- Implement robust error handling for API timeouts/failures.

## Verification Plan

### Automated Tests
- `tests/test_predictor.py`: Unit tests for feature extraction and calibration logic (mocked Gemini/XGBoost).
- `scripts/try_predictor.py`: Demo script to show the full "Scan -> Research -> Predict" flow for a live market.

### Manual Verification
- Run the demo script with a real Gemini API key to see "Reasoning" from the LLM.
