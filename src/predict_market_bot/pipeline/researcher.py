import asyncio
import re
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from textblob import TextBlob

from predict_market_bot.config.settings import settings
from predict_market_bot.core.models import Market, Signal

logger = structlog.get_logger(__name__)


class MarketResearcher:
    """Collect external signals and score sentiment for each market using NewsAPI."""

    SOURCES = ("newsapi",)

    def __init__(self) -> None:
        self.api_key = settings.news_api_key

    # ── Public API ───────────────────────────────────────────────────

    async def research(self, markets: list[Market]) -> dict[str, list[Signal]]:
        """Gather signals for every market in parallel.

        Args:
            markets: Markets to research.

        Returns:
            Mapping of market_id → list of signals.
        """
        if not self.api_key:
            logger.warning("researcher_api_key_missing", status="using_mocks")

        logger.info("research_started", market_count=len(markets))

        tasks = [self._research_market(m) for m in markets]
        results = await asyncio.gather(*tasks)

        signals_map: dict[str, list[Signal]] = {}
        for market, signals in zip(markets, results):
            signals_map[market.id] = signals

        total_signals = sum(len(s) for s in signals_map.values())
        logger.info("research_complete", total_signals=total_signals)

        return signals_map

    # ── Per-market research ──────────────────────────────────────────

    async def _research_market(self, market: Market) -> list[Signal]:
        """Fan-out to sources for a single market.

        Args:
            market: The market to gather signals for.

        Returns:
            Combined list of signals from all sources.
        """
        # If no API key, revert to mock for this market
        if not self.api_key:
            return await self._fetch_mock(market)

        tasks = [self._fetch_source(source, market) for source in self.SOURCES]
        nested = await asyncio.gather(*tasks)
        return [sig for group in nested for sig in group]

    # ── Source fetchers ──────────────────────────────────────────────

    async def _fetch_source(self, source: str, market: Market) -> list[Signal]:
        """Fetch data from a single source and run NLP."""
        if source == "newsapi":
            return await self._fetch_news_api(market)
        return []

    async def _fetch_news_api(self, market: Market) -> list[Signal]:
        """Fetch relevant articles from NewsAPI.org."""
        query = self._extract_keywords(market.question)
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "sortBy": "relevancy",
            "pageSize": 5,
            "apiKey": self.api_key,
            "language": "en",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 429:
                    logger.warning("newsapi_rate_limit", market_id=market.id)
                    return []
                resp.raise_for_status()
                data = resp.json()

            signals = []
            for article in data.get("articles", []):
                text = f"{article.get('title', '')}. {article.get('description', '')}"
                sentiment = self._analyze_sentiment(text)
                
                # Simple relevance score based on query presence in title
                relevance = 0.5
                if query.lower() in article.get("title", "").lower():
                    relevance = 0.9

                signals.append(
                    Signal(
                        source="newsapi",
                        query=query,
                        sentiment_score=sentiment,
                        narrative=article.get("title", "No Title"),
                        relevance=relevance,
                        timestamp=datetime.now(timezone.utc),
                        metadata={"url": article.get("url")},
                    )
                )
            return signals

        except Exception as e:
            logger.error("newsapi_error", market_id=market.id, error=str(e))
            return []

    async def _fetch_mock(self, market: Market) -> list[Signal]:
        """Fallback mock signals when API key is missing."""
        sentiment = self._mock_sentiment(market.question, "mock")
        return [
            Signal(
                source="mock",
                query=market.question,
                sentiment_score=sentiment,
                narrative=f"Mock analysis for: {market.question}",
                relevance=0.8,
                timestamp=datetime.now(timezone.utc),
            )
        ]

    # ── NLP Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _analyze_sentiment(text: str) -> float:
        """Calculate sentiment polarity using TextBlob.

        Returns:
            Polarity score in [-1.0, 1.0].
        """
        blob = TextBlob(text)
        return float(blob.sentiment.polarity)

    @staticmethod
    def _extract_keywords(question: str) -> str:
        """Simple cleanup to extract a search query from market question."""
        # Remove common prefix/suffix like "Will ... occur by ...?"
        q = question.lower()
        q = re.sub(r"will\s+", "", q)
        q = re.sub(r"\s+by\s+.+\?", "", q)
        q = re.sub(r"\?", "", q)
        
        # Keep only alpha-numeric and spaces
        q = re.sub(r"[^a-zA-Z0-9\s]", "", q)
        
        # Limit to first 5 words if too long
        words = q.split()
        return " ".join(words[:6])

    @staticmethod
    def _mock_sentiment(question: str, source: str) -> float:
        h = hash(f"{question}:{source}") % 200
        return (h - 100) / 100.0

    # ── Analysis helpers ─────────────────────────────────────────────

    @staticmethod
    def aggregate_sentiment(signals: list[Signal]) -> float:
        """Compute weighted average sentiment across signals."""
        if not signals:
            return 0.0
        
        # Filter for high relevance
        valid_signals = [s for s in signals if s.relevance > 0.3]
        if not valid_signals:
            return 0.0

        total_weight = sum(s.relevance for s in valid_signals)
        return sum(s.sentiment_score * s.relevance for s in valid_signals) / total_weight

    @staticmethod
    def sentiment_vs_odds(sentiment: float, market_yes_odds: float) -> float:
        """Compare aggregate sentiment to market implied probability.

        Positive delta means sentiment is more bullish than the market.
        """
        # [Sentiment -1 to 1] -> [0 to 1]
        normalized = (sentiment + 1.0) / 2.0
        return normalized - market_yes_odds
