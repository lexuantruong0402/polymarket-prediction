"""Tests for the MarketScanner with mocked Polymarket API."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from predict_market_bot.core.models import Market
from predict_market_bot.pipeline.scanner import MarketScanner


# ── Fixtures ─────────────────────────────────────────────────────────────

def _make_gamma_event(
    event_id: str = "1",
    title: str = "Test Event",
    markets_data: list[dict] | None = None,
) -> dict:
    """Create a mock Gamma API event response."""
    if markets_data is None:
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=30)
        markets_data = [
            {
                "id": f"mkt_{event_id}_1",
                "question": f"Will {title} happen?",
                "outcomes": '["Yes", "No"]',
                "outcomePrices": '["0.65", "0.35"]',
                "volume": "50000.0",
                "volume24hr": 5000.0,
                "volume24hrClob": 5000.0,
                "liquidityNum": 20000.0,
                "liquidityClob": 20000.0,
                "active": True,
                "closed": False,
                "enableOrderBook": True,
                "acceptingOrders": True,
                "endDate": end.isoformat(),
                "spread": 0.02,
                "bestBid": 0.64,
                "bestAsk": 0.66,
            }
        ]

    return {
        "id": event_id,
        "title": title,
        "active": True,
        "closed": False,
        "markets": markets_data,
        "tags": [{"label": "TestTag"}],
    }


def _make_mock_response(data: list[dict], status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    return resp


# ── Tests ────────────────────────────────────────────────────────────────


class TestFetchMarkets:
    """Test _fetch_markets with mocked HTTP client."""

    @pytest.mark.asyncio
    async def test_fetches_and_parses_events(self):
        """Verify that events are fetched and parsed into Market objects."""
        events = [_make_gamma_event("1"), _make_gamma_event("2")]

        mock_client = AsyncMock()
        mock_client.get.side_effect = [
            _make_mock_response(events),
            _make_mock_response([]),
        ]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            scanner = MarketScanner(scan_limit=10)
            markets = await scanner._fetch_markets()

        assert len(markets) == 2
        assert all(isinstance(m, Market) for m in markets)
        assert markets[0].question == "Will Test Event happen?"
        assert markets[0].outcomes == ["Yes", "No"]

    @pytest.mark.asyncio
    async def test_skips_closed_markets(self):
        """Verify closed markets are skipped during parsing."""
        now = datetime.now(timezone.utc)
        closed_market = {
            "id": "closed_1",
            "question": "Already resolved?",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["1", "0"]',
            "volume": "100.0",
            "active": True,
            "closed": True,  # <-- closed
            "enableOrderBook": True,
            "acceptingOrders": False,
            "endDate": (now + timedelta(days=1)).isoformat(),
        }
        events = [_make_gamma_event("1", markets_data=[closed_market])]

        mock_client = AsyncMock()
        mock_client.get.side_effect = [
            _make_mock_response(events),
            _make_mock_response([]),
        ]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            scanner = MarketScanner(scan_limit=10)
            markets = await scanner._fetch_markets()

        assert len(markets) == 0

    @pytest.mark.asyncio
    async def test_respects_scan_limit(self):
        """Verify scan_limit caps the number of markets returned."""
        events = [_make_gamma_event(str(i)) for i in range(20)]

        mock_client = AsyncMock()
        # First page returns all, second returns empty
        mock_client.get.side_effect = [
            _make_mock_response(events),
            _make_mock_response([]),
        ]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            scanner = MarketScanner(scan_limit=5)
            markets = await scanner._fetch_markets()

        assert len(markets) <= 5

    @pytest.mark.asyncio
    async def test_handles_api_error_gracefully(self):
        """Verify scanner handles HTTP errors without crashing."""
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_resp,
        )
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            scanner = MarketScanner(scan_limit=10)
            markets = await scanner._fetch_markets()

        assert markets == []


class TestParseMarket:
    """Test individual market parsing logic."""

    def test_parses_odds_correctly(self):
        """Verify outcomes/prices are mapped to odds dict."""
        scanner = MarketScanner()
        raw = {
            "id": "test_1",
            "question": "Test?",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.70", "0.30"]',
            "volume24hr": 1000.0,
            "liquidityNum": 5000.0,
            "endDate": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "spread": 0.03,
            "bestBid": 0,
            "bestAsk": 0,
        }
        market = scanner._parse_market(raw, tags=["Finance"])

        assert market is not None
        assert market.odds["Yes"] == pytest.approx(0.70)
        assert market.odds["No"] == pytest.approx(0.30)
        assert market.tags == ["Finance"]

    def test_calculates_spread_from_bid_ask(self):
        """Verify spread is computed from bestBid/bestAsk when available."""
        scanner = MarketScanner()
        raw = {
            "id": "spread_1",
            "question": "Spread test?",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.50", "0.50"]',
            "volume24hr": 2000.0,
            "liquidityNum": 10000.0,
            "endDate": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "spread": 0.10,  # Gamma-provided (should be overridden)
            "bestBid": 0.48,
            "bestAsk": 0.52,
        }
        market = scanner._parse_market(raw, tags=[])

        assert market is not None
        assert market.spread == pytest.approx(0.04)  # bestAsk - bestBid

    def test_returns_none_for_missing_id(self):
        """Verify None is returned when market_id is empty."""
        scanner = MarketScanner()
        market = scanner._parse_market({"id": "", "question": "Q?"}, tags=[])
        assert market is None


class TestApplyFilters:
    """Test filtering logic."""

    def test_filters_by_liquidity_and_volume(self):
        """Verify markets below thresholds are excluded."""
        now = datetime.now(timezone.utc)
        markets = [
            Market(
                id="high",
                question="High?",
                outcomes=["Yes", "No"],
                odds={"Yes": 0.5, "No": 0.5},
                volume_24h=10000,
                liquidity=20000,
                close_time=now + timedelta(days=7),
            ),
            Market(
                id="low",
                question="Low?",
                outcomes=["Yes", "No"],
                odds={"Yes": 0.5, "No": 0.5},
                volume_24h=100,  # below min
                liquidity=200,   # below min
                close_time=now + timedelta(days=7),
            ),
        ]
        scanner = MarketScanner(min_liquidity=1000, min_volume=500)
        filtered = scanner._apply_filters(markets)

        assert len(filtered) == 1
        assert filtered[0].id == "high"


class TestFlagAnomalies:
    """Test anomaly detection."""

    def test_flags_wide_spread(self):
        """Markets with spread > threshold are flagged."""
        now = datetime.now(timezone.utc)
        markets = [
            Market(
                id="normal",
                question="Normal?",
                outcomes=["Yes", "No"],
                odds={"Yes": 0.5, "No": 0.5},
                volume_24h=5000,
                liquidity=10000,
                close_time=now + timedelta(days=7),
                spread=0.02,
            ),
            Market(
                id="wide",
                question="Wide?",
                outcomes=["Yes", "No"],
                odds={"Yes": 0.5, "No": 0.5},
                volume_24h=5000,
                liquidity=10000,
                close_time=now + timedelta(days=7),
                spread=0.15,
            ),
        ]
        scanner = MarketScanner(spread_anomaly_threshold=0.10)
        result = scanner._flag_anomalies(markets)

        assert result[0].anomaly_flag is False
        assert result[1].anomaly_flag is True
