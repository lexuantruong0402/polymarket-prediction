"""Script to run a backtest simulation."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path if needed
sys.path.append(str(Path(__file__).parent.parent / "src"))

from predict_market_bot.pipeline.backtester import Backtester


async def main():
    data_path = Path(__file__).parent.parent / "data" / "historical_sample.json"
    
    if not data_path.exists():
        print(f"Error: Sample data not found at {data_path}")
        return

    backtester = Backtester(data_path)
    print(f"Starting backtest with data from {data_path}...")
    
    try:
        results = await backtester.run(confidence_threshold=0.3)
        
        print("\n" + "=" * 60)
        print("  BACKTEST RESULTS")
        print("=" * 60)
        
        bt_stats = results.get("backtest", {})
        print(f"  Total Trades: {bt_stats.get('trades_count')}")
        print(f"  Total PnL:    ${bt_stats.get('total_pnl'):.2f}")
        print(f"  Win Rate:     {bt_stats.get('win_rate') * 100:.1f}%")
        
        print("\n  Pipeline Summary:")
        print(f"    Markets Scanned: {results.get('markets_scanned')}")
        print(f"    Approved:        {results.get('approved')}")
        print(f"    Rejected:        {results.get('rejected')}")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"Backtest failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
