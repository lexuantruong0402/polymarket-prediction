import json
import os
from typing import Any

import httpx
import numpy as np
import structlog
import xgboost as xgb

from predict_market_bot.config.settings import settings
from predict_market_bot.core.formulas import market_edge
from predict_market_bot.core.models import Market, Prediction, Side, Signal

logger = structlog.get_logger(__name__)


class MarketPredictor:
    """Produce calibrated probability estimates using XGBoost + Gemini LLM."""

    def __init__(self, confidence_threshold: float | None = None) -> None:
        self.confidence_threshold = confidence_threshold or settings.confidence_threshold
        self.gemini_key = settings.gemini_api_key
        self._model: xgb.Booster | None = None
        self._load_model()

    def _load_model(self) -> None:
        """Load the XGBoost model from the configured path."""
        path = settings.model_path
        if os.path.exists(path):
            try:
                self._model = xgb.Booster()
                self._model.load_model(path)
                logger.info("xgboost_model_loaded", path=path)
            except Exception as e:
                logger.error("xgboost_load_failed", path=path, error=str(e))
        else:
            logger.warning("xgboost_model_not_found", path=path, status="falling_back_to_heuristic")

    # ── Public API ───────────────────────────────────────────────────

    async def predict(
        self,
        markets: list[Market],
        signals_map: dict[str, list[Signal]],
    ) -> list[Prediction]:
        """Generate predictions for markets that pass the confidence gate."""
        logger.info("prediction_started", market_count=len(markets))
        predictions: list[Prediction] = []

        for market in markets:
            signals = signals_map.get(market.id, [])
            features = self._extract_features(market, signals)
            
            # 1. Statistical Prediction (XGBoost)
            p_raw = self._xgboost_predict(features)
            
            # 2. Expert Calibration (LLM)
            p_calibrated = await self._llm_calibrate(p_raw, market, signals)
            
            # 3. Confidence Gating
            confidence = self._compute_confidence(features, p_calibrated)

            if confidence < self.confidence_threshold:
                logger.debug(
                    "prediction_skipped",
                    market_id=market.id,
                    confidence=round(confidence, 4),
                    threshold=self.confidence_threshold,
                )
                continue

            p_market = market.odds.get("YES", 0.5)
            edge = market_edge(p_calibrated, p_market)
            side = Side.YES if edge > 0 else Side.NO

            pred = Prediction(
                market_id=market.id,
                p_model=p_calibrated,
                p_market=p_market,
                edge=edge,
                confidence=confidence,
                side=side,
                features=features,
            )
            predictions.append(pred)
            logger.info(
                "prediction_generated",
                market_id=market.id,
                p_model=round(p_calibrated, 4),
                p_market=round(p_market, 4),
                edge=round(edge, 4),
                confidence=round(confidence, 4),
            )

        logger.info("prediction_complete", predictions=len(predictions))
        return predictions

    # ── Feature Engineering ──────────────────────────────────────────

    def _extract_features(self, market: Market, signals: list[Signal]) -> dict[str, float]:
        """Build feature vector from market data and signals."""
        avg_sentiment = 0.0
        if signals:
            relevant_signals = [s for s in signals if s.relevance > 0.3]
            if relevant_signals:
                avg_sentiment = sum(s.sentiment_score for s in relevant_signals) / len(relevant_signals)

        return {
            "yes_odds": market.odds.get("YES", 0.5),
            "no_odds": market.odds.get("NO", 0.5),
            "spread": market.spread,
            "volume_24h": market.volume_24h,
            "liquidity": market.liquidity,
            "avg_sentiment": avg_sentiment,
            "signal_count": float(len(signals)),
            "anomaly_flag": float(market.anomaly_flag),
        }

    # ── Inference Engine ─────────────────────────────────────────────

    def _xgboost_predict(self, features: dict[str, float]) -> float:
        """Run XGBoost inference or fallback heuristic."""
        if self._model:
            # Prepare feature vector for XGBoost
            # Note: Feature order must match training data
            feat_names = [
                "yes_odds", "no_odds", "spread", "volume_24h", 
                "liquidity", "avg_sentiment", "signal_count", "anomaly_flag"
            ]
            vals = [features.get(name, 0.0) for name in feat_names]
            data = xgb.DMatrix(np.array([vals]), feature_names=feat_names)
            preds = self._model.predict(data)
            return float(preds[0])
        else:
            # Fallback heuristic: Statistical bayesian-like update
            # Start with market odds and drift toward sentiment
            base = features.get("yes_odds", 0.5)
            sentiment = features.get("avg_sentiment", 0.0)
            
            # Simple drift model
            drift = sentiment * 0.15 * (1.0 - abs(base - 0.5))
            return float(np.clip(base + drift, 0.01, 0.99))

    async def _llm_calibrate(
        self,
        p_raw: float,
        market: Market,
        signals: list[Signal],
    ) -> float:
        """Calibrate probability using Google Gemini Pro."""
        if not self.gemini_key:
            logger.warning("gemini_key_missing", status="skipping_calibration")
            return p_raw

        # Prepare context for LLM
        narratives = "\n".join([f"- {s.source}: {s.narrative}" for s in signals[:5]])
        
        prompt = f"""
        Role: Expert Prediction Market Analyst
        Context: You are calibrating an automated prediction.
        
        Market: {market.question}
        Current Market Odds (YES): {market.odds.get('YES', 0.5):.2%}
        Statistical Model Prediction: {p_raw:.2%}
        
        Recent News/Research:
        {narratives if narratives else "No recent news found."}
        
        Task:
        1. Consider the statistical model's output as a baseline.
        2. Evaluate the research narratives for hidden risks or catalysts not captured by price.
        3. Provide a FINAL calibrated probability (0.0 to 1.0) for the 'YES' outcome.
        
        Return ONLY a JSON object:
        {{"calibrated_p": 0.XX, "reasoning": "summary under 20 words"}}
        """

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={self.gemini_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"}
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                result = resp.json()
                
                content = result['candidates'][0]['content']['parts'][0]['text']
                data = json.loads(content)
                
                calibrated = float(data.get("calibrated_p", p_raw))
                logger.info(
                    "llm_calibration_success",
                    market_id=market.id,
                    p_raw=round(p_raw, 4),
                    p_calibrated=round(calibrated, 4),
                    reasoning=data.get("reasoning")
                )
                return np.clip(calibrated, 0.01, 0.99)

        except Exception as e:
            logger.error("llm_calibration_failed", error=str(e), market_id=market.id)
            return p_raw

    @staticmethod
    def _compute_confidence(features: dict[str, float], p_calibrated: float) -> float:
        """Estimate model confidence (0–1)."""
        signal_count = features.get("signal_count", 0)
        # More signals → higher confidence
        signal_confidence = min(signal_count / 3.0, 1.0)
        
        # High liquidity + low spread → higher market efficiency confidence
        liquidity = features.get("liquidity", 0)
        liquidity_score = min(liquidity / 50000.0, 1.0)
        
        # Directional strength
        directional = abs(p_calibrated - 0.5) * 2.0
        
        return (signal_confidence * 0.4 + liquidity_score * 0.3 + directional * 0.3)
