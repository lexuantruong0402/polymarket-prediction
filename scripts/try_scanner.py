"""Simple script to test the MarketScanner independently."""

import asyncio
import json
from datetime import datetime
from predict_market_bot.pipeline.scanner import MarketScanner
from predict_market_bot.config.settings import settings

async def main():
    print(f"--- Market Scanner Demo ---")
    print(f"Target: {settings.api_base_url}")
    print(f"Liquidity Min: ${settings.min_liquidity}")
    print(f"Volume Min: ${settings.min_volume}")
    print(f"---------------------------\n")

    scanner = MarketScanner()
    try:
        markets = await scanner.scan()
        
        if not markets:
            print("No markets found matching the filters.")
            return

        print(f"Found {len(markets)} markets:\n")
        
        for i, m in enumerate(markets[:10]):  # Show top 10
            status = "[!] ANOMALY" if m.anomaly_flag else "[ ]"
            print(f"{i+1}. {status} {m.question}")
            print(f"   ID: {m.id}")
            print(f"   Liquidity: ${m.liquidity:,.2f} | Volume 24h: ${m.volume_24h:,.2f}")
            print(f"   Spread: {m.spread:.4f}")
            print(f"   Odds: {m.odds}")
            print(f"   Closes: {m.close_time}")
            print("-" * 40)
            
        if len(markets) > 10:
            print(f"... and {len(markets) - 10} more.")

    except Exception as e:
        print(f"Error during scan: {e}")

if __name__ == "__main__":
    asyncio.run(main())
