"""Simple script to test the MarketResearcher independently."""

import asyncio
from datetime import datetime, timezone
from predict_market_bot.pipeline.researcher import MarketResearcher
from predict_market_bot.core.models import Market
from predict_market_bot.config.settings import settings

async def main():
    print(f"--- Market Researcher Demo ---")
    print(f"NewsAPI Key: {'PRESENT' if settings.news_api_key else 'MISSING (Using Mocks)'}")
    print(f"-------------------------------\n")

    researcher = MarketResearcher()
    
    # Create some test markets
    test_markets = [
        Market(
            id="mkt_1",
            question="Will Jesus Christ return before GTA VI?",
            outcomes=["Yes", "No"],
            odds={"Yes": 0.485, "No": 0.515},
            volume_24h=21000,
            liquidity=750000,
            close_time=datetime.now(timezone.utc),
        ),
        Market(
            id="mkt_2",
            question="Will MicroStrategy sell any Bitcoin by June 30, 2026?",
            outcomes=["Yes", "No"],
            odds={"Yes": 0.055, "No": 0.945},
            volume_24h=15000,
            liquidity=149000,
            close_time=datetime.now(timezone.utc),
        )
    ]

    try:
        signals_map = await researcher.research(test_markets)
        
        for market in test_markets:
            signals = signals_map.get(market.id, [])
            avg_sentiment = researcher.aggregate_sentiment(signals)
            divergence = researcher.sentiment_vs_odds(avg_sentiment, market.odds["Yes"])
            
            print(f"Market: {market.question}")
            print(f"  Signal Count: {len(signals)}")
            print(f"  Avg Sentiment: {avg_sentiment:+.4f} (Polarity)")
            print(f"  Market Probability: {market.odds['Yes']:.2%}")
            print(f"  Divergence: {divergence:+.4%}")
            
            if signals:
                print("  Top Articles/Signals:")
                for s in signals[:2]:
                    print(f"    - [{s.source}] {s.narrative[:60]}... (Score: {s.sentiment_score:+.2f})")
            print("-" * 40)

    except Exception as e:
        print(f"Error during research: {e}")

if __name__ == "__main__":
    asyncio.run(main())
