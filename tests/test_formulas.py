"""Unit tests for core/formulas.py — all 12 trading math functions."""

from __future__ import annotations

import math

import numpy as np
import pytest

from predict_market_bot.core.formulas import (
    arbitrage_check,
    bayes_update,
    brier_score,
    expected_value,
    fractional_kelly,
    kelly_criterion,
    market_edge,
    max_drawdown,
    mispricing_score,
    profit_factor,
    sharpe_ratio,
    value_at_risk,
)


# ── Expected Value ───────────────────────────────────────────────────────


class TestExpectedValue:
    def test_positive_ev(self):
        # p=0.6, b=1.0  →  0.6*1 - 0.4 = 0.2
        assert expected_value(0.6, 1.0) == pytest.approx(0.2)

    def test_negative_ev(self):
        # p=0.3, b=1.0  →  0.3 - 0.7 = -0.4
        assert expected_value(0.3, 1.0) == pytest.approx(-0.4)

    def test_zero_ev(self):
        # p=0.5, b=1.0  →  0.5 - 0.5 = 0
        assert expected_value(0.5, 1.0) == pytest.approx(0.0)

    def test_high_payout(self):
        # p=0.2, b=5.0  →  1.0 - 0.8 = 0.2
        assert expected_value(0.2, 5.0) == pytest.approx(0.2)


# ── Market Edge ──────────────────────────────────────────────────────────


class TestMarketEdge:
    def test_positive_edge(self):
        assert market_edge(0.65, 0.50) == pytest.approx(0.15)

    def test_negative_edge(self):
        assert market_edge(0.40, 0.55) == pytest.approx(-0.15)

    def test_zero_edge(self):
        assert market_edge(0.50, 0.50) == pytest.approx(0.0)


# ── Bayes Update ─────────────────────────────────────────────────────────


class TestBayesUpdate:
    def test_basic_update(self):
        # P(H)=0.5, P(E|H)=0.8, P(E)=0.5 → 0.8
        assert bayes_update(0.5, 0.8, 0.5) == pytest.approx(0.8)

    def test_zero_evidence_raises(self):
        with pytest.raises(ZeroDivisionError):
            bayes_update(0.5, 0.8, 0.0)

    def test_full_certainty(self):
        assert bayes_update(1.0, 1.0, 1.0) == pytest.approx(1.0)


# ── Brier Score ──────────────────────────────────────────────────────────


class TestBrierScore:
    def test_perfect_predictions(self):
        assert brier_score([1.0, 0.0], [1, 0]) == pytest.approx(0.0)

    def test_worst_predictions(self):
        assert brier_score([0.0, 1.0], [1, 0]) == pytest.approx(1.0)

    def test_mixed(self):
        # (0.7-1)^2 + (0.3-0)^2 = 0.09 + 0.09 = 0.18 / 2 = 0.09
        assert brier_score([0.7, 0.3], [1, 0]) == pytest.approx(0.09)

    def test_empty(self):
        assert brier_score([], []) == pytest.approx(0.0)


# ── Kelly Criterion ──────────────────────────────────────────────────────


class TestKellyCriterion:
    def test_positive_edge(self):
        # p=0.6, b=1.0 → (0.6*1 - 0.4)/1 = 0.2
        assert kelly_criterion(0.6, 1.0) == pytest.approx(0.2)

    def test_no_edge(self):
        # p=0.5, b=1.0 → 0.0
        assert kelly_criterion(0.5, 1.0) == pytest.approx(0.0)

    def test_negative_edge_clamped(self):
        # p=0.3, b=1.0 → negative, clamped to 0
        assert kelly_criterion(0.3, 1.0) == 0.0

    def test_zero_payout(self):
        assert kelly_criterion(0.6, 0.0) == 0.0


class TestFractionalKelly:
    def test_quarter_kelly(self):
        assert fractional_kelly(0.2, 0.25) == pytest.approx(0.05)

    def test_half_kelly(self):
        assert fractional_kelly(0.2, 0.5) == pytest.approx(0.1)

    def test_clamp_negative(self):
        assert fractional_kelly(-0.1, 0.25) == 0.0


# ── Value at Risk ────────────────────────────────────────────────────────


class TestValueAtRisk:
    def test_default_95(self):
        # mu=0.05, sigma=0.02 → 0.05 - 1.645*0.02 = 0.0171
        assert value_at_risk(0.05, 0.02) == pytest.approx(0.0171)

    def test_custom_z(self):
        # 99% → z=2.326
        assert value_at_risk(0.05, 0.02, z=2.326) == pytest.approx(0.05 - 2.326 * 0.02)


# ── Max Drawdown ─────────────────────────────────────────────────────────


class TestMaxDrawdown:
    def test_no_drawdown(self):
        assert max_drawdown([100, 110, 120]) == pytest.approx(0.0)

    def test_simple_drawdown(self):
        # Peak=100, Trough=80 → 20%
        assert max_drawdown([100, 80, 90]) == pytest.approx(0.2)

    def test_empty(self):
        assert max_drawdown([]) == 0.0

    def test_single_value(self):
        assert max_drawdown([100]) == 0.0


# ── Arbitrage ────────────────────────────────────────────────────────────


class TestArbitrageCheck:
    def test_arb_exists(self):
        # 1/3 + 1/3 = 0.667 < 1 → arbitrage
        assert arbitrage_check([3.0, 3.0]) is True

    def test_no_arb(self):
        # 1/1.5 + 1/1.5 = 1.333 > 1
        assert arbitrage_check([1.5, 1.5]) is False

    def test_fair_market(self):
        # 1/2 + 1/2 = 1.0 — exactly fair, no arb
        assert arbitrage_check([2.0, 2.0]) is False

    def test_empty(self):
        assert arbitrage_check([]) is False

    def test_zero_odds(self):
        assert arbitrage_check([0, 2.0]) is False


# ── Mispricing Score ─────────────────────────────────────────────────────


class TestMispricingScore:
    def test_positive_mispricing(self):
        assert mispricing_score(0.7, 0.5, 0.1) == pytest.approx(2.0)

    def test_zero_sigma_raises(self):
        with pytest.raises(ZeroDivisionError):
            mispricing_score(0.7, 0.5, 0.0)


# ── Sharpe Ratio ─────────────────────────────────────────────────────────


class TestSharpeRatio:
    def test_positive_sharpe(self):
        returns = [0.1, 0.15, 0.12, 0.08, 0.11]
        sr = sharpe_ratio(returns)
        assert sr > 0

    def test_empty_returns(self):
        assert sharpe_ratio([]) == 0.0

    def test_constant_returns(self):
        # All same → std=0 → 0
        assert sharpe_ratio([0.1, 0.1, 0.1]) == 0.0


# ── Profit Factor ────────────────────────────────────────────────────────


class TestProfitFactor:
    def test_profitable(self):
        assert profit_factor(1500, 1000) == pytest.approx(1.5)

    def test_no_losses(self):
        assert profit_factor(100, 0) == float("inf")

    def test_no_profit_no_loss(self):
        assert profit_factor(0, 0) == 0.0

    def test_breakeven(self):
        assert profit_factor(100, 100) == pytest.approx(1.0)
