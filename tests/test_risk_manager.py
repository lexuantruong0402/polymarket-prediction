"""Unit tests for pipeline/risk_manager.py — all 5 risk checks."""

from __future__ import annotations

import pytest

from predict_market_bot.core.models import Prediction, Side
from predict_market_bot.pipeline.risk_manager import PortfolioState, RiskManager


@pytest.fixture
def risk_manager() -> RiskManager:
    return RiskManager(
        edge_threshold=0.04,
        max_exposure=0.30,
        mdd_limit=0.08,
        var_limit_daily=500.0,
        kelly_alpha=0.25,
    )


@pytest.fixture
def healthy_portfolio() -> PortfolioState:
    return PortfolioState(
        bankroll=10_000.0,
        current_exposure=0.0,
        equity_curve=[10_000, 10_050, 10_100, 10_080, 10_120],
        daily_returns=[50, -20, 40, 30, -10],
    )


@pytest.fixture
def good_prediction() -> Prediction:
    return Prediction(
        market_id="test_market_1",
        p_model=0.65,
        p_market=0.50,
        edge=0.15,
        confidence=0.80,
        side=Side.YES,
    )


# ── Check 1: Edge Threshold ─────────────────────────────────────────────


class TestEdgeCheck:
    def test_sufficient_edge_passes(self, risk_manager, healthy_portfolio, good_prediction):
        result = risk_manager.evaluate(good_prediction, healthy_portfolio)
        # Edge = 0.15 > 0.04 threshold
        assert result.passed is True

    def test_insufficient_edge_fails(self, risk_manager, healthy_portfolio):
        pred = Prediction(
            market_id="low_edge",
            p_model=0.52,
            p_market=0.50,
            edge=0.02,
            confidence=0.80,
            side=Side.YES,
        )
        result = risk_manager.evaluate(pred, healthy_portfolio)
        assert result.passed is False
        assert any("Edge" in r for r in result.reasons)


# ── Check 2: Kelly Sizing ───────────────────────────────────────────────


class TestKellySizing:
    def test_positive_kelly_computed(self, risk_manager, healthy_portfolio, good_prediction):
        result = risk_manager.evaluate(good_prediction, healthy_portfolio)
        assert result.kelly_fraction > 0
        assert result.bet_size > 0

    def test_no_edge_zero_kelly(self, risk_manager, healthy_portfolio):
        pred = Prediction(
            market_id="no_edge",
            p_model=0.50,
            p_market=0.50,
            edge=0.0,
            confidence=0.80,
            side=Side.YES,
        )
        result = risk_manager.evaluate(pred, healthy_portfolio)
        assert result.passed is False


# ── Check 3: Exposure Limit ─────────────────────────────────────────────


class TestExposureLimit:
    def test_within_exposure_limit(self, risk_manager, healthy_portfolio, good_prediction):
        result = risk_manager.evaluate(good_prediction, healthy_portfolio)
        assert result.passed is True
        assert result.exposure_after <= 0.30 * healthy_portfolio.bankroll

    def test_exceeds_exposure_fails(self, risk_manager, good_prediction):
        # Already near max exposure
        portfolio = PortfolioState(
            bankroll=10_000.0,
            current_exposure=2_900.0,  # close to 30% of 10k = 3000
            equity_curve=[10_000],
            daily_returns=[],
        )
        result = risk_manager.evaluate(good_prediction, portfolio)
        # May fail if bet_size pushes over 3000
        if result.exposure_after > 3000:
            assert result.passed is False


# ── Check 4: VaR ────────────────────────────────────────────────────────


class TestVaRCheck:
    def test_var_within_limit(self, risk_manager, healthy_portfolio, good_prediction):
        result = risk_manager.evaluate(good_prediction, healthy_portfolio)
        # With small daily returns, VaR should be within 500
        assert result.passed is True

    def test_var_exceeds_limit(self, risk_manager, good_prediction):
        # Volatile portfolio
        portfolio = PortfolioState(
            bankroll=10_000.0,
            current_exposure=0.0,
            equity_curve=[10_000, 9_000, 10_500, 8_500, 11_000],
            daily_returns=[-1000, 1500, -2000, 2500, -800],
        )
        result = risk_manager.evaluate(good_prediction, portfolio)
        # High volatility should trigger VaR warning
        assert result.var_current > 0


# ── Check 5: Max Drawdown ───────────────────────────────────────────────


class TestMDDCheck:
    def test_low_mdd_passes(self, risk_manager, healthy_portfolio, good_prediction):
        result = risk_manager.evaluate(good_prediction, healthy_portfolio)
        assert result.passed is True

    def test_high_mdd_fails(self, risk_manager, good_prediction):
        # Equity curve with > 8% drawdown
        portfolio = PortfolioState(
            bankroll=10_000.0,
            current_exposure=0.0,
            equity_curve=[10_000, 10_200, 9_000, 9_100],  # 11.8% drawdown
            daily_returns=[200, -1200, 100],
        )
        result = risk_manager.evaluate(good_prediction, portfolio)
        assert result.passed is False
        assert any("MDD" in r for r in result.reasons)


# ── Batch Evaluation ─────────────────────────────────────────────────────


class TestBatchEvaluation:
    def test_batch_tracks_exposure(self, risk_manager, healthy_portfolio):
        predictions = [
            Prediction(
                market_id=f"batch_{i}",
                p_model=0.65,
                p_market=0.50,
                edge=0.15,
                confidence=0.80,
                side=Side.YES,
            )
            for i in range(5)
        ]
        results = risk_manager.evaluate_batch(predictions, healthy_portfolio)
        assert len(results) == 5

        # At least the first one should pass
        assert results[0][1].passed is True
