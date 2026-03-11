"""Historical Market Fetcher — retrieves closed markets and outcomes from Polymarket."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from predict_market_bot.config.settings import settings
from predict_market_bot.core.models import Market, Outcome

logger = structlog.get_logger(__name__)

_GAMMA_EVENTS_PATH = "/events"
_PAGE_SIZE = 100

class HistoricalFetcher:
    """Fetches closed markets and their outcomes for backtesting."""

    def __init__(self) -> None:
        self._gamma_base = settings.api_base_url.rstrip("/")

    async def fetch_history(self, limit: int = 50) -> dict[str, Any]:
        """Fetch recently closed markets and their outcomes.

        Args:
            limit: Maximum number of markets to fetch.

        Returns:
            Dict identifying "markets" and "outcomes" compatible with Backtester.
        """
        logger.info("fetching_historical_markets", limit=limit)
        
        all_markets: list[Market] = []
        outcomes: dict[str, str] = {}
        offset = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            while len(all_markets) < limit:
                params = {
                    "closed": "true",
                    "limit": min(_PAGE_SIZE, limit - len(all_markets)),
                    "offset": offset,
                    "order": "closedTime",
                    "ascending": "false"
                }
                
                url = f"{self._gamma_base}{_GAMMA_EVENTS_PATH}"
                try:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                    events = resp.json()
                except Exception as e:
                    logger.error("gamma_fetch_failed", error=str(e), error_type=type(e).__name__)
                    # If it's a redirect or something, maybe it's the URL?
                    if hasattr(e, 'response'):
                        logger.error("gamma_error_details", status=e.response.status_code, text=e.response.text[:200])
                    break

                if not events:
                    logger.warning("no_events_found", params=params)
                    break

                for event in events:
                    event_markets = event.get("markets", [])
                    event_tags = [t.get("label", "") for t in event.get("tags", []) if t.get("label")]
                    
                    for raw in event_markets:
                        # Only keep resolved/closed markets
                        if not raw.get("closed"):
                            continue
                            
                        # NewsAPI free tier only allows last 30 days of history
                        # Let's filter for markets closed within last 28 days for safety
                        now = datetime.now(timezone.utc)
                        end_date_str = raw.get("endDate", "")
                        if end_date_str:
                            try:
                                close_time = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                                days_diff = (now - close_time).days
                                if days_diff > 28:
                                    logger.debug("skipping_old_market", id=raw.get("id"), date=end_date_str)
                                    continue
                            except ValueError:
                                continue
                        else:
                            continue

                        # Outcome detection logic
                        outcome_str = "PENDING"
                        prices_raw = raw.get("outcomePrices", [])
                        if isinstance(prices_raw, str):
                            try:
                                prices = json.loads(prices_raw)
                            except json.JSONDecodeError:
                                continue
                        else:
                            prices = prices_raw
                            
                        if prices and len(prices) >= 2:
                            try:
                                # Outcome prices in Gamma API are strings of floats
                                p0 = float(prices[0])
                                p1 = float(prices[1])
                                if p0 > 0.95: # Use 0.95 for robustness
                                    outcome_str = "WIN"
                                elif p1 > 0.95:
                                    outcome_str = "LOSS"
                                else:
                                    # Not fully resolved or split outcome
                                    continue 
                            except (ValueError, TypeError):
                                continue
                        else:
                            # Could be resolution via 'winner' field?
                            continue

                        market = self._parse_market(raw, event_tags)
                        if market:
                            all_markets.append(market)
                            outcomes[market.id] = outcome_str
                            logger.debug("historical_market_added", id=market.id, outcome=outcome_str)
                            
                        if len(all_markets) >= limit:
                            break
                    
                    if len(all_markets) >= limit:
                        break
                        
                offset += len(events)
                await asyncio.sleep(0.1)

        logger.info("fetch_complete", markets=len(all_markets))
        return {
            "markets": [self._market_to_dict(m) for m in all_markets],
            "outcomes": outcomes
        }

    def _parse_market(self, raw: dict, tags: list[str]) -> Market | None:
        """Reuse parsing logic from scanner (simplified)."""
        market_id = raw.get("id", "")
        question = raw.get("question", "")
        if not market_id or not question:
            return None

        outcomes_raw = raw.get("outcomes", "[]")
        if isinstance(outcomes_raw, str):
            outcomes = json.loads(outcomes_raw)
        else:
            outcomes = outcomes_raw

        # For historical data, "odds" during the trade period are what we need.
        # But for backtesting, we might just assume 0.5 or look at volume.
        # Ideally we'd have historical order books, but Gamma only gives status.
        # We'll use a snapshot of 'odds' if available, otherwise 0.5.
        
        # Note: 'odds' in closed markets might be 1.0 or 0.0.
        # In a real backtest, we'd need prices AT THE TIME of the trade.
        # Since we don't have time-series here, we'll randomize or use a neutral value
        # to test the predictor's ability to 'correct' it.
        
        odds = {o: 0.5 for o in outcomes} if len(outcomes) == 2 else {}

        end_date_str = raw.get("endDate", "")
        close_time = datetime.now(timezone.utc)
        if end_date_str:
            try:
                close_time = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        return Market(
            id=market_id,
            question=question,
            outcomes=outcomes,
            odds=odds,
            volume_24h=float(raw.get("volume24hr", 0) or 0),
            liquidity=float(raw.get("liquidityNum", 0) or 0),
            close_time=close_time,
            tags=tags
        )

    def _market_to_dict(self, m: Market) -> dict:
        """Convert Market object back to dict for JSON export."""
        return {
            "id": m.id,
            "question": m.question,
            "outcomes": m.outcomes,
            "odds": m.odds,
            "volume_24h": m.volume_24h,
            "liquidity": m.liquidity,
            "close_time": m.close_time.isoformat(),
            "tags": m.tags
        }
