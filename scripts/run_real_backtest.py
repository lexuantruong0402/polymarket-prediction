"""Script to run a real backtest using Polymarket's closed markets."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from predict_market_bot.pipeline.backtester import Backtester


async def main():
    # Initialize without a data path to trigger live fetching
    backtester = Backtester()
    
    print("=" * 60)
    print("  REAL-WORLD BACKTEST — Polymarket Live History")
    print("=" * 60)
    print("  1. Fetching recently closed markets from Gamma API...")
    
    # Fetch 5 recent closed markets for a quick demo
    # In production you could increase this to 50 or 100
    await backtester.fetch_recent_history(limit=10)
    
    print(f"  2. Successfully loaded {len(backtester.markets)} markets.")
    print("  3. Starting backtest with REAL historical news signals...")
    print("     (This will fetch news from the week leading up to each market's close)")
    
    try:
        # use_real_news=True triggers news fetching for each historical market
        results = await backtester.run(confidence_threshold=0.3, use_real_news=True)
        
        print("\n" + "=" * 60)
        print("  BACKTEST RESULTS (REAL DATA)")
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
        print(f"\nBacktest failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
