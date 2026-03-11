"""Stage 1 — Market Scanner.

Scans prediction markets via the Polymarket Gamma API,
filters by liquidity/volume/close-time, enriches with CLOB spread data,
and flags anomalies (wide spreads, volume spikes).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from predict_market_bot.config.settings import settings
from predict_market_bot.core.models import Market

logger = structlog.get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────

_GAMMA_EVENTS_PATH = "/events"
_GAMMA_MARKETS_PATH = "/markets"
_CLOB_SPREAD_PATH = "/spread"
_CLOB_MIDPOINT_PATH = "/midpoint"
_DEFAULT_TIMEOUT = 30.0
_PAGE_SIZE = 100  # Gamma API max per page


class MarketScanner:
    """Fetch and filter active prediction markets from Polymarket."""

    def __init__(
        self,
        min_liquidity: float | None = None,
        min_volume: float | None = None,
        scan_limit: int | None = None,
        exclude_tag_id: int | None = None,
        spread_anomaly_threshold: float = 0.10,
        volume_spike_factor: float = 3.0,
    ) -> None:
        self.min_liquidity = min_liquidity or settings.min_liquidity
        self.min_volume = min_volume or settings.min_volume
        self.scan_limit = scan_limit or settings.scan_limit
        self.exclude_tag_id = exclude_tag_id or settings.exclude_tag_id
        self.spread_anomaly_threshold = spread_anomaly_threshold
        self.volume_spike_factor = volume_spike_factor

        self._gamma_base = settings.api_base_url.rstrip("/")
        self._clob_base = settings.clob_api_url.rstrip("/")

    # ── Public API ───────────────────────────────────────────────────

    async def scan(self) -> list[Market]:
        """Fetch markets from Polymarket, apply filters, flag anomalies.

        Returns:
            Filtered and annotated list of markets.
        """
        logger.info("scan_started", limit=self.scan_limit)

        raw_markets = await self._fetch_markets()
        logger.info("markets_fetched", count=len(raw_markets))

        filtered = self._apply_filters(raw_markets)
        logger.info("markets_filtered", count=len(filtered))

        # Enrich with CLOB spread data
        enriched = await self._enrich_spreads(filtered)

        annotated = self._flag_anomalies(enriched)
        anomaly_count = sum(1 for m in annotated if m.anomaly_flag)
        logger.info("anomalies_flagged", anomalies=anomaly_count)

        return annotated

    # ── Polymarket Gamma API ─────────────────────────────────────────

    async def _fetch_markets(self) -> list[Market]:
        """Fetch active markets from the Polymarket Gamma API.

        Uses the ``/events`` endpoint with pagination to collect markets.
        Each event may contain multiple sub-markets; we flatten them into
        individual :class:`Market` objects.

        Returns:
            List of parsed Market objects.
        """
        all_markets: list[Market] = []
        offset = 0

        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            while len(all_markets) < self.scan_limit:
                remaining = self.scan_limit - len(all_markets)
                limit = min(_PAGE_SIZE, remaining)

                params: dict[str, Any] = {
                    "closed": "false",
                    "active": "true",
                    "limit": limit,
                    "offset": offset,
                    "liquidity_min": str(int(self.min_liquidity)),
                    "volume_min": str(int(self.min_volume)),
                }
                if self.exclude_tag_id:
                    params["exclude_tag_id"] = str(self.exclude_tag_id)

                url = f"{self._gamma_base}{_GAMMA_EVENTS_PATH}"
                
                # Retry loop for intermittent connection issues
                events = None
                for attempt in range(3):
                    try:
                        resp = await client.get(url, params=params)
                        resp.raise_for_status()
                        events = resp.json()
                        break
                    except (httpx.RequestError, json.JSONDecodeError) as exc:
                        if attempt < 2:
                            logger.warning("gamma_retry", attempt=attempt+1, error=str(exc))
                            await asyncio.sleep(0.5 * (attempt + 1))
                            continue
                        logger.error("gamma_request_failed", error=str(exc), error_type=type(exc).__name__)
                        return all_markets # Return what we have so far
                    except httpx.HTTPStatusError as exc:
                        logger.error("gamma_api_error", status=exc.response.status_code)
                        return all_markets

                if not events:
                    break

                for event in events:
                    parsed = self._parse_event(event)
                    all_markets.extend(parsed)

                offset += len(events)
                await asyncio.sleep(0.1)

        logger.info("gamma_fetch_complete", total_markets=len(all_markets))
        return all_markets[: self.scan_limit]

    def _parse_event(self, event: dict) -> list[Market]:
        """Parse a Gamma API event object into Market objects.

        An event may contain multiple sub-markets (e.g. different date
        thresholds for the same question). We only keep markets that
        are active, not closed, and have order book enabled.

        Args:
            event: Raw event dict from Gamma API.

        Returns:
            List of Market objects extracted from the event.
        """
        markets: list[Market] = []
        raw_markets = event.get("markets", [])

        # Extract event-level tags
        event_tags = [
            tag.get("label", "")
            for tag in event.get("tags", [])
            if tag.get("label")
        ]

        for raw in raw_markets:
            # Skip closed or inactive markets
            if raw.get("closed", True) or not raw.get("active", False):
                continue

            # Skip markets without order book
            if not raw.get("enableOrderBook", False):
                continue

            # Skip markets not accepting orders
            if not raw.get("acceptingOrders", False):
                continue

            try:
                market = self._parse_market(raw, event_tags)
                if market is not None:
                    markets.append(market)
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning(
                    "market_parse_error",
                    market_id=raw.get("id", "unknown"),
                    error=str(exc),
                )

        return markets

    def _parse_market(self, raw: dict, tags: list[str]) -> Market | None:
        """Parse a single market dict into a Market dataclass.

        Args:
            raw: Raw market dict from Gamma API.
            tags: Event-level tags.

        Returns:
            Parsed Market object, or None if critical data is missing.
        """
        market_id = raw.get("id", "")
        question = raw.get("question", "")
        if not market_id or not question:
            return None

        # Parse outcomes and prices
        outcomes_raw = raw.get("outcomes", "[]")
        prices_raw = raw.get("outcomePrices", "[]")

        if isinstance(outcomes_raw, str):
            outcomes = json.loads(outcomes_raw)
        else:
            outcomes = outcomes_raw

        if isinstance(prices_raw, str):
            prices = json.loads(prices_raw)
        else:
            prices = prices_raw

        # Build odds dict (outcome label → implied probability)
        odds: dict[str, float] = {}
        for i, outcome in enumerate(outcomes):
            try:
                odds[outcome] = float(prices[i]) if i < len(prices) else 0.0
            except (ValueError, IndexError):
                odds[outcome] = 0.0

        # Volume (prefer 24h, fallback to total)
        volume_24h = float(raw.get("volume24hr", 0) or raw.get("volume24hrClob", 0) or 0)

        # Liquidity
        liquidity = float(raw.get("liquidityNum", 0) or raw.get("liquidityClob", 0) or 0)

        # Parse close time
        end_date_str = raw.get("endDate", "")
        if end_date_str:
            try:
                close_time = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            except ValueError:
                close_time = datetime.now(timezone.utc)
        else:
            close_time = datetime.now(timezone.utc)

        # Spread from Gamma (fallback; enriched later from CLOB)
        spread = float(raw.get("spread", 0) or 0)

        # Best bid/ask for more accurate spread
        best_bid = float(raw.get("bestBid", 0) or 0)
        best_ask = float(raw.get("bestAsk", 0) or 0)
        if best_bid > 0 and best_ask > 0:
            spread = best_ask - best_bid

        return Market(
            id=market_id,
            question=question,
            outcomes=outcomes,
            odds=odds,
            volume_24h=volume_24h,
            liquidity=liquidity,
            close_time=close_time,
            spread=spread,
            anomaly_flag=False,
            tags=tags,
        )

    # ── CLOB Spread Enrichment ───────────────────────────────────────

    async def _enrich_spreads(self, markets: list[Market]) -> list[Market]:
        """Enrich markets with live spread data from the CLOB API.

        Fetches spread for each market's first token ID. Falls back to
        the Gamma-provided spread if the CLOB call fails.

        Args:
            markets: Markets to enrich.

        Returns:
            Same markets with updated spread values.
        """
        if not markets:
            return markets

        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            # Process in batches to avoid overwhelming the API
            batch_size = 10
            for i in range(0, len(markets), batch_size):
                batch = markets[i : i + batch_size]
                tasks = [self._fetch_clob_spread(client, m) for m in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for market, result in zip(batch, results):
                    if isinstance(result, float) and result >= 0:
                        market.spread = result

                if i + batch_size < len(markets):
                    await asyncio.sleep(0.05)  # rate limiting

        return markets

    async def _fetch_clob_spread(
        self, client: httpx.AsyncClient, market: Market
    ) -> float:
        """Fetch the spread for a market from the CLOB API.

        Args:
            client: HTTP client.
            market: Market to query.

        Returns:
            Spread value, or -1.0 on failure.
        """
        # The CLOB API uses token_id; we use market.id as a proxy
        # In production, you'd use the clobTokenIds from the Gamma response
        url = f"{self._clob_base}{_CLOB_SPREAD_PATH}"
        try:
            resp = await client.get(url, params={"token_id": market.id})
            resp.raise_for_status()
            data = resp.json()
            return float(data.get("spread", -1.0))
        except (httpx.HTTPStatusError, httpx.RequestError, ValueError, KeyError):
            return -1.0

    # ── Filters & Anomalies ──────────────────────────────────────────

    def _apply_filters(self, markets: list[Market]) -> list[Market]:
        """Filter by liquidity, volume and whether the market is still open."""
        now = datetime.now(timezone.utc)
        return [
            m
            for m in markets
            if m.liquidity >= self.min_liquidity
            and m.volume_24h >= self.min_volume
            and m.close_time > now
        ]

    def _flag_anomalies(self, markets: list[Market]) -> list[Market]:
        """Flag markets with unusually wide spread or volume spikes."""
        if not markets:
            return markets

        avg_volume = sum(m.volume_24h for m in markets) / len(markets)

        for market in markets:
            wide_spread = market.spread > self.spread_anomaly_threshold
            volume_spike = market.volume_24h > avg_volume * self.volume_spike_factor
            if wide_spread or volume_spike:
                market.anomaly_flag = True
                logger.debug(
                    "anomaly_detected",
                    market_id=market.id,
                    spread=market.spread,
                    volume=market.volume_24h,
                    wide_spread=wide_spread,
                    volume_spike=volume_spike,
                )

        return markets
