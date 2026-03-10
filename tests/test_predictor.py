"""Tests for the MarketPredictor, XGBoost inference and Gemini calibration logic."""

from __future__ import annotations

import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
from predict_market_bot.pipeline.predictor import MarketPredictor
from predict_market_bot.core.models import Market, Signal, Side


class TestPredictorLogic:
    """Test feature extraction and confidence calculation."""

    def test_extract_features(self):
        """Verify feature vector construction."""
        predictor = MarketPredictor()
        market = Market(
            id="m1", question="Q", outcomes=["Y", "N"], 
            odds={"YES": 0.6, "NO": 0.4},
            volume_24h=10000, liquidity=50000, 
            close_time=datetime.now(), spread=0.01,
            anomaly_flag=True
        )
        signals = [
            Signal(source="s", query="q", sentiment_score=0.8, narrative="n", relevance=0.9),
            Signal(source="s", query="q", sentiment_score=-0.2, narrative="n", relevance=0.1), # low relevance
        ]
        
        feats = predictor._extract_features(market, signals)
        
        assert feats["yes_odds"] == 0.6
        assert feats["avg_sentiment"] == 0.8 # only first signal counts
        assert feats["anomaly_flag"] == 1.0
        assert feats["signal_count"] == 2.0

    def test_compute_confidence(self):
        """Verify confidence scoring logic."""
        predictor = MarketPredictor()
        
        # High signal count + High liquidity + Directional conviction
        feats_high = {"signal_count": 5.0, "liquidity": 100000.0}
        conf_high = predictor._compute_confidence(feats_high, 0.9)
        
        # Low signal count + Low liquidity + Indecision
        feats_low = {"signal_count": 0.0, "liquidity": 1000.0}
        conf_low = predictor._compute_confidence(feats_low, 0.5)
        
        assert conf_high > 0.7
        assert conf_low < 0.3

    def test_xgboost_predict_fallback(self):
        """Verify fallback heuristic when no model exists."""
        predictor = MarketPredictor()
        predictor._model = None # ensure fallback
        
        # Market YES=0.6, Sentiment=1.0 -> should drift UP
        feats = {"yes_odds": 0.6, "avg_sentiment": 1.0}
        p = predictor._xgboost_predict(feats)
        assert p > 0.6
        
        # Market YES=0.6, Sentiment=-1.0 -> should drift DOWN
        feats = {"yes_odds": 0.6, "avg_sentiment": -1.0}
        p = predictor._xgboost_predict(feats)
        assert p < 0.6


@pytest.mark.asyncio
class TestPredictorAPI:
    """Test API interactions (Gemini)."""

    async def test_gemini_calibration_success(self):
        """Verify Gemini JSON parsing and calibration logic."""
        predictor = MarketPredictor()
        predictor.gemini_key = "fake_key"
        
        market = Market(
            id="m1", question="Will X happen?", outcomes=["Y", "N"], 
            odds={"YES": 0.5}, volume_24h=1, liquidity=1, close_time=datetime.now()
        )
        
        mock_resp_data = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": json.dumps({"calibrated_p": 0.72, "reasoning": "Strong news supports YES"})
                    }]
                }
            }]
        }
        
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_resp_data
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            p = await predictor._llm_calibrate(0.65, market, [])
            
        assert p == 0.72

    async def test_gemini_calibration_failure_fallback(self):
        """Verify fallback to raw probability on API error."""
        predictor = MarketPredictor()
        predictor.gemini_key = "fake_key"
        
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("API Down")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        market = Market(
            id="m1", question="Will X happen?", outcomes=["Y", "N"], 
            odds={"YES": 0.5}, volume_24h=1, liquidity=1, close_time=datetime.now()
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            p = await predictor._llm_calibrate(0.65, market, [])
            
        assert p == 0.65 # fallbacks to p_raw
