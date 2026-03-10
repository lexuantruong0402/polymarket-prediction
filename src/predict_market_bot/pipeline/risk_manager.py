"""Stage 4 — Risk Manager.

Runs 5 independent risk checks before any order is placed.
Computes bet sizing via fractional Kelly Criterion.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from predict_market_bot.config.settings import settings
from predict_market_bot.core.formulas import (
    fractional_kelly,
    kelly_criterion,
    max_drawdown,
    value_at_risk,
)
from predict_market_bot.core.models import Prediction, RiskCheckResult

logger = structlog.get_logger(__name__)


@dataclass
class PortfolioState:
    """Current state of the portfolio for risk evaluation."""

    bankroll: float
    current_exposure: float        # sum of outstanding bet sizes
    equity_curve: list[float]      # historical equity values
    daily_returns: list[float]     # returns within the current day


class RiskManager:
    """Gate that must pass before any trade is executed.

    Five independent checks run in sequence. If any fails, the
    prediction is rejected with a clear reason.
    """

    def __init__(
        self,
        edge_threshold: float | None = None,
        max_exposure: float | None = None,
        mdd_limit: float | None = None,
        var_limit_daily: float | None = None,
        kelly_alpha: float | None = None,
    ) -> None:
        self.edge_threshold = edge_threshold or settings.edge_threshold
        self.max_exposure = max_exposure or settings.max_exposure
        self.mdd_limit = mdd_limit or settings.mdd_limit
        self.var_limit_daily = var_limit_daily or settings.var_limit_daily
        self.kelly_alpha = kelly_alpha or settings.kelly_alpha

    # ── Public API ───────────────────────────────────────────────────

    def evaluate(
        self,
        prediction: Prediction,
        portfolio: PortfolioState,
    ) -> RiskCheckResult:
        """Run all risk checks against a prediction.

        Args:
            prediction: Output from the Predictor stage.
            portfolio: Current portfolio state.

        Returns:
            RiskCheckResult with pass/fail, sizing, and reasons.
        """
        reasons: list[str] = []

        # ── Check 1: Edge threshold ──────────────────────────────────
        if abs(prediction.edge) < self.edge_threshold:
            reasons.append(
                f"Edge {prediction.edge:.4f} < threshold {self.edge_threshold}"
            )

        # ── Check 2: Kelly sizing ────────────────────────────────────
        b = (1.0 / prediction.p_market) - 1.0 if prediction.p_market > 0 else 0.0
        full_kelly = kelly_criterion(prediction.p_model, b)
        frac_kelly = fractional_kelly(full_kelly, self.kelly_alpha)
        bet_size = frac_kelly * portfolio.bankroll

        if bet_size <= 0:
            reasons.append("Kelly fraction is non-positive — no edge")

        # ── Check 3: Exposure limit ──────────────────────────────────
        max_bet = self.max_exposure * portfolio.bankroll
        exposure_after = portfolio.current_exposure + bet_size

        if exposure_after > max_bet:
            reasons.append(
                f"Exposure after bet ({exposure_after:.2f}) > "
                f"max allowed ({max_bet:.2f})"
            )

        # ── Check 4: VaR (95%) within daily limit ────────────────────
        var_current = 0.0
        if len(portfolio.daily_returns) >= 2:
            import numpy as np

            mu = float(np.mean(portfolio.daily_returns))
            sigma = float(np.std(portfolio.daily_returns, ddof=1))
            var_current = abs(value_at_risk(mu, sigma))
            if var_current > self.var_limit_daily:
                reasons.append(
                    f"VaR (95%) {var_current:.2f} > daily limit {self.var_limit_daily:.2f}"
                )

        # ── Check 5: Max Drawdown ────────────────────────────────────
        current_mdd = max_drawdown(portfolio.equity_curve) if portfolio.equity_curve else 0.0
        if current_mdd > self.mdd_limit:
            reasons.append(
                f"MDD {current_mdd:.4f} > limit {self.mdd_limit}"
            )

        passed = len(reasons) == 0

        result = RiskCheckResult(
            passed=passed,
            reasons=reasons,
            kelly_fraction=frac_kelly,
            bet_size=bet_size if passed else 0.0,
            exposure_after=exposure_after if passed else portfolio.current_exposure,
            var_current=var_current,
        )

        log_fn = logger.info if passed else logger.warning
        log_fn(
            "risk_evaluation",
            market_id=prediction.market_id,
            passed=passed,
            edge=round(prediction.edge, 4),
            kelly=round(frac_kelly, 4),
            bet_size=round(bet_size, 2),
            reasons=reasons or None,
        )

        return result

    # ── Batch helper ─────────────────────────────────────────────────

    def evaluate_batch(
        self,
        predictions: list[Prediction],
        portfolio: PortfolioState,
    ) -> list[tuple[Prediction, RiskCheckResult]]:
        """Evaluate multiple predictions, updating exposure incrementally.

        Args:
            predictions: List of predictions to evaluate.
            portfolio: Starting portfolio state.

        Returns:
            List of (prediction, risk_result) tuples.
        """
        results: list[tuple[Prediction, RiskCheckResult]] = []
        running_exposure = portfolio.current_exposure

        for pred in predictions:
            state = PortfolioState(
                bankroll=portfolio.bankroll,
                current_exposure=running_exposure,
                equity_curve=portfolio.equity_curve,
                daily_returns=portfolio.daily_returns,
            )
            risk = self.evaluate(pred, state)
            results.append((pred, risk))

            if risk.passed:
                running_exposure = risk.exposure_after

        return results
