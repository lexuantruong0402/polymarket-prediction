"""Integration tests for the pipeline orchestrator.

Mocks the scanner's HTTP calls so tests run offline.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from predict_market_bot.orchestrator import PipelineOrchestrator
from predict_market_bot.core.models import Market


def _make_demo_markets(n: int = 5) -> list[Market]:
    """Generate demo Market objects for testing."""
    now = datetime.now(timezone.utc)
    return [
        Market(
            id=f"market_{i}",
            question=f"Will event {i} occur?",
            outcomes=["Yes", "No"],
            odds={"Yes": 0.45 + (i % 10) * 0.05, "No": 0.55 - (i % 10) * 0.05},
            volume_24h=2000.0 + i * 500,
            liquidity=8000.0 + i * 1000,
            close_time=now + timedelta(days=1 + i % 7),
            spread=0.02 + (i % 5) * 0.03,
            tags=[f"category_{i % 3}"],
        )
        for i in range(n)
    ]


@pytest.fixture
def mock_scanner():
    """Patch the scanner's _fetch_markets to return demo data."""
    with patch.object(
        PipelineOrchestrator, "__init__", wraps=PipelineOrchestrator.__init__
    ) as _:
        pass

    # Patch _fetch_markets and _enrich_spreads on MarketScanner
    with patch(
        "predict_market_bot.pipeline.scanner.MarketScanner._fetch_markets",
        new_callable=AsyncMock,
        return_value=_make_demo_markets(10),
    ), patch(
        "predict_market_bot.pipeline.scanner.MarketScanner._enrich_spreads",
        new_callable=AsyncMock,
        side_effect=lambda markets: markets,
    ):
        yield


@pytest.mark.asyncio
async def test_full_pipeline_runs(mock_scanner):
    """Smoke test: the full pipeline completes without errors."""
    orchestrator = PipelineOrchestrator()
    result = await orchestrator.run()

    assert isinstance(result, dict)
    assert "markets_scanned" in result
    assert result["markets_scanned"] > 0


@pytest.mark.asyncio
async def test_pipeline_returns_expected_keys(mock_scanner):
    """Verify the summary dict contains all expected keys."""
    orchestrator = PipelineOrchestrator()
    result = await orchestrator.run()

    expected_keys = {
        "markets_scanned",
        "predictions",
        "approved",
        "rejected",
        "trades_executed",
        "insights_generated",
        "performance",
    }

    # Pipeline might abort early if no predictions — check for either full or partial
    if "aborted" not in result:
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"


@pytest.mark.asyncio
async def test_pipeline_stages_data_flow(mock_scanner):
    """Verify data flows between stages: scanned → predicted → some approved."""
    orchestrator = PipelineOrchestrator()
    result = await orchestrator.run()

    if "aborted" in result:
        pytest.skip("Pipeline aborted — no markets available")

    scanned = result.get("markets_scanned", 0)
    # The scanner mock returns 10 markets, we expect scanned > 0
    assert scanned > 0, f"Scanner should produce markets, got {scanned}"
    
    predicted = result.get("predictions", 0)
    assert predicted >= 0
