"""Script to fetch and save real historical data from Polymarket."""

import asyncio
import sys
from pathlib import Path
from predict_market_bot.pipeline.backtester import Backtester

async def main():
    limit = 20
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
        
    output_file = "data/historical_latest.json"
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
        
    print(f"Fetching {limit} recent resolved markets...")
    backtester = Backtester()
    await backtester.fetch_recent_history(limit=limit)
    
    if not backtester.markets:
        print("No markets found. Check your API connection.")
        return
        
    backtester.save_to_file(output_file)
    print(f"Successfully saved {len(backtester.markets)} markets to {output_file}")
    print(f"You can now run backtests using: python3 scripts/run_backtest.py {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
