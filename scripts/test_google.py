import asyncio
from datetime import datetime, timezone
import os
import sys

# Add src to path just in case
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

try:
    from predict_market_bot.pipeline.researcher import MarketResearcher
    from predict_market_bot.core.models import Market
    import structlog
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer()
        ],
    )
except ImportError:
    print("Failed to import app modules")
    sys.exit(1)

async def test_google_search():
    print("\nTesting via MarketResearcher (uses DuckDuckGo implicitly)...")
    researcher = MarketResearcher()
    market = Market(
        id="test-market",
        question="Will SpaceX launch Starship to Mars in 2026?",
        outcomes=["Yes", "No"],
        odds={"Yes": 0.5, "No": 0.5},
        volume_24h=10000.0,
        liquidity=5000.0,
        close_time=datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
    )
    signals = await researcher._fetch_google_search(market)
    print(f"Fetched {len(signals)} signals!")
    for s in signals:
        print(f"Title: {s.narrative}")
        print(f"URL: {s.metadata.get('url')}")
        print(f"Relevance: {s.relevance}")
        print(f"Sentiment: {s.sentiment_score}")
        print("---")

if __name__ == "__main__":
    asyncio.run(test_google_search())
