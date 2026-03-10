"""Integration demo: Scanner -> Researcher -> Predictor."""

import asyncio
from datetime import datetime, timezone
import structlog

from predict_market_bot.pipeline.scanner import MarketScanner
from predict_market_bot.pipeline.researcher import MarketResearcher
from predict_market_bot.pipeline.predictor import MarketPredictor
from predict_market_bot.config.settings import settings

async def main():
    print("--- Full Pipeline Demo (Scan -> Research -> Predict) ---")
    print(f"NewsAPI Key: {'PRESENT' if settings.news_api_key else 'MISSING'}")
    print(f"Gemini Key:  {'PRESENT' if settings.gemini_api_key else 'MISSING'}")
    print("-------------------------------------------------------\n")

    # 1. Initialize stages
    scanner = MarketScanner()
    researcher = MarketResearcher()
    predictor = MarketPredictor(confidence_threshold=0.1)

    # 2. Run Scanner
    print("[1/3] Scanning Polymarket...")
    markets = await scanner.scan()
    top_markets = markets[:3] # Limit for demo speed
    print(f"      Scanned {len(markets)} markets. Researching top {len(top_markets)}.\n")

    # 3. Run Researcher
    print("[2/3] Researching Narratives & Sentiment...")
    signals_map = await researcher.research(top_markets)
    print(f"      Found signals for {len(signals_map)} markets.\n")

    # 4. Run Predictor
    print("[3/3] Generating Calibrated Predictions...")
    predictions = await predictor.predict(top_markets, signals_map)
    
    print("\n" + "="*50)
    print(f"{'MARKET QUESTION':<35} | {'EDGE':<8} | {'CONF'}")
    print("-" * 50)
    
    for pred in predictions:
        # Find original market to get question
        m = next(m for m in top_markets if m.id == pred.market_id)
        q_short = (m.question[:32] + '..') if len(m.question) > 32 else m.question
        print(f"{q_short:<35} | {pred.edge:>+7.2%} | {pred.confidence:.2f}")
    
    print("="*50)

if __name__ == "__main__":
    # Ensure logs aren't too noisy for demo
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(20), # INFO
    )
    asyncio.run(main())
