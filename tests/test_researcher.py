"""Tests for the MarketResearcher and sentiment analysis logic."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from predict_market_bot.pipeline.researcher import MarketResearcher
from predict_market_bot.core.models import Market, Signal


class TestResearcherNLP:
    """Test the NLP processing and aggregation logic."""

    def test_sentiment_analysis(self):
        """Verify polarity detection on standard sentences."""
        researcher = MarketResearcher()
        
        bullish = "The earnings were fantastic, much better than expected."
        bearish = "The project failed miserably and outlook is grim."
        neutral = "The meeting took place on Tuesday afternoon."
        
        Score_bullish = researcher._analyze_sentiment(bullish)
        Score_bearish = researcher._analyze_sentiment(bearish)
        Score_neutral = researcher._analyze_sentiment(neutral)
        
        assert Score_bullish > 0.1
        assert Score_bearish < -0.1
        assert abs(Score_neutral) < 0.1

    def test_extract_keywords(self):
        """Verify question to query transformation."""
        researcher = MarketResearcher()
        
        q1 = "Will Jesus Christ return before GTA VI?"
        q2 = "Will MicroStrategy sell any Bitcoin by June 30, 2026?"
        
        kw1 = researcher._extract_keywords(q1)
        kw2 = researcher._extract_keywords(q2)
        
        assert "jesus" in kw1.lower()
        assert "gta" in kw1.lower()
        assert "microstrategy" in kw2.lower()
        assert "bitcoin" in kw2.lower()
        assert "?" not in kw1
        assert "will" not in kw1.lower()

    def test_aggregate_sentiment(self):
        """Verify weighted average calculation."""
        researcher = MarketResearcher()
        
        signals = [
            Signal(source="s", query="q", sentiment_score=1.0, narrative="n", relevance=1.0, timestamp=datetime.now()),
            Signal(source="s", query="q", sentiment_score=-1.0, narrative="n", relevance=0.5, timestamp=datetime.now()),
            Signal(source="s", query="q", sentiment_score=0.0, narrative="n", relevance=0.1, timestamp=datetime.now()), # should be ignored (relevance < 0.3)
        ]
        
        # Expected: (1.0 * 1.0 + -1.0 * 0.5) / (1.0 + 0.5) = 0.5 / 1.5 = 0.3333
        agg = researcher.aggregate_sentiment(signals)
        assert agg == pytest.approx(0.3333, abs=0.01)

    def test_sentiment_vs_odds(self):
        """Verify divergence calculation."""
        researcher = MarketResearcher()
        
        # Sentiment 0.0 -> Probability 0.5
        # Market P = 0.4
        # Divergence = 0.5 - 0.4 = 0.1
        div = researcher.sentiment_vs_odds(0.0, 0.4)
        assert div == pytest.approx(0.1)
        
        # Sentiment 1.0 -> Prob 1.0
        # Market P = 0.7
        # Div = 0.3
        div2 = researcher.sentiment_vs_odds(1.0, 0.7)
        assert div2 == pytest.approx(0.3)


@pytest.mark.asyncio
class TestResearcherAPI:
    """Test the API interaction (mocked)."""

    async def test_newsapi_fetch_parsing(self):
        """Verify that NewsAPI JSON is correctly parsed into Signal objects."""
        researcher = MarketResearcher()
        researcher.api_key = "fake_key"
        
        mock_resp_data = {
            "articles": [
                {
                    "title": "btc rise as Bitcoin Surges to New Highs",
                    "description": "The market is very bullish after recent adoption.",
                    "url": "http://example.com/1"
                }
            ]
        }
        
        market = Market(
            id="m1", question="Will BTC rise?", outcomes=["Y", "N"], odds={"Y": 0.5, "N": 0.5},
            volume_24h=1, liquidity=1, close_time=datetime.now()
        )

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_resp_data
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            signals = await researcher._fetch_news_api(market)
            
        assert len(signals) == 1
        assert signals[0].source == "newsapi"
        assert signals[0].sentiment_score > 0
        assert signals[0].relevance == 0.9
        assert signals[0].metadata["url"] == "http://example.com/1"
