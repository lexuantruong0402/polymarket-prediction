"""Core mathematical formulas for prediction market trading.

Every function is pure, stateless, and unit-testable.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike


# ── Expected Value & Edge ────────────────────────────────────────────────


def expected_value(p: float, b: float) -> float:
    """Calculate expected value of a bet.

    EV = p · b - (1 - p)

    Args:
        p: Probability of winning (0–1).
        b: Net payout on a $1 bet (e.g. 1.0 for even money).

    Returns:
        Expected value per unit wagered.
    """
    return p * b - (1.0 - p)


def market_edge(p_model: float, p_market: float) -> float:
    """Edge = model probability − market implied probability.

    Args:
        p_model: Model-estimated true probability.
        p_market: Market implied probability.

    Returns:
        The edge; positive means model sees an opportunity.
    """
    return p_model - p_market


# ── Bayesian Inference ───────────────────────────────────────────────────


def bayes_update(prior: float, likelihood: float, evidence: float) -> float:
    """Bayes' theorem: P(H|E) = P(E|H) · P(H) / P(E).

    Args:
        prior: P(H) — prior probability of hypothesis.
        likelihood: P(E|H) — probability of evidence given hypothesis.
        evidence: P(E) — total probability of evidence.

    Returns:
        Posterior probability P(H|E).

    Raises:
        ZeroDivisionError: If evidence is zero.
    """
    if evidence == 0.0:
        raise ZeroDivisionError("P(E) cannot be zero for Bayes update")
    return (likelihood * prior) / evidence


# ── Scoring ──────────────────────────────────────────────────────────────


def brier_score(predictions: ArrayLike, outcomes: ArrayLike) -> float:
    """Brier Score: BS = (1/n) Σ(p_i - o_i)².

    Lower is better; 0 = perfect, 1 = worst.

    Args:
        predictions: Predicted probabilities (0–1).
        outcomes: Actual outcomes (0 or 1).

    Returns:
        Mean squared error between predictions and outcomes.
    """
    p = np.asarray(predictions, dtype=np.float64)
    o = np.asarray(outcomes, dtype=np.float64)
    if p.size == 0:
        return 0.0
    return float(np.mean((p - o) ** 2))


# ── Kelly Criterion ──────────────────────────────────────────────────────


def kelly_criterion(p: float, b: float) -> float:
    """Full Kelly fraction: f* = (p·b - q) / b, where q = 1 - p.

    Args:
        p: Win probability (0–1).
        b: Net payout multiplier.

    Returns:
        Optimal fraction of bankroll to wager (clamped ≥ 0).
    """
    if b <= 0:
        return 0.0
    q = 1.0 - p
    f_star = (p * b - q) / b
    return max(f_star, 0.0)


def fractional_kelly(f_star: float, alpha: float = 0.25) -> float:
    """Conservative Kelly: f = α · f*.

    Args:
        f_star: Full Kelly fraction.
        alpha: Scaling factor ∈ [0.25, 0.5].

    Returns:
        Reduced bet fraction (clamped ≥ 0).
    """
    return max(alpha * f_star, 0.0)


# ── Risk Metrics ─────────────────────────────────────────────────────────


def value_at_risk(mu: float, sigma: float, z: float = 1.645) -> float:
    """VaR at given confidence: VaR = μ − z · σ.

    Default is 95% confidence (z = 1.645).

    Args:
        mu: Expected return (mean).
        sigma: Standard deviation of returns.
        z: Z-score for confidence level.

    Returns:
        Value-at-Risk threshold.
    """
    return mu - z * sigma


def max_drawdown(equity_curve: ArrayLike) -> float:
    """Maximum Drawdown: MDD = (Peak − Trough) / Peak.

    Args:
        equity_curve: Sequence of portfolio values over time.

    Returns:
        Max drawdown as a fraction (0–1). Returns 0.0 for empty input.
    """
    eq = np.asarray(equity_curve, dtype=np.float64)
    if eq.size < 2:
        return 0.0
    running_max = np.maximum.accumulate(eq)
    drawdowns = (running_max - eq) / np.where(running_max == 0, 1.0, running_max)
    return float(np.max(drawdowns))


# ── Arbitrage & Mispricing ───────────────────────────────────────────────


def arbitrage_check(odds_list: ArrayLike) -> bool:
    """Check arbitrage condition: Σ(1/odds_i) < 1.

    Args:
        odds_list: Decimal odds for each outcome.

    Returns:
        True if an arbitrage opportunity exists.
    """
    odds = np.asarray(odds_list, dtype=np.float64)
    if odds.size == 0 or np.any(odds <= 0):
        return False
    return bool(np.sum(1.0 / odds) < 1.0)


def mispricing_score(p_model: float, p_market: float, sigma: float) -> float:
    """Mispricing z-score: δ = (p_model − p_market) / σ.

    Args:
        p_model: Model probability.
        p_market: Market implied probability.
        sigma: Standard deviation of model error.

    Returns:
        Number of standard deviations the market is mispriced.

    Raises:
        ZeroDivisionError: If sigma is zero.
    """
    if sigma == 0.0:
        raise ZeroDivisionError("sigma cannot be zero for mispricing score")
    return (p_model - p_market) / sigma


# ── Performance ──────────────────────────────────────────────────────────


def sharpe_ratio(returns: ArrayLike, rf: float = 0.0) -> float:
    """Sharpe Ratio: SR = (E[R] − Rf) / σ(R).

    Args:
        returns: Array of period returns.
        rf: Risk-free rate per period.

    Returns:
        Sharpe ratio. Returns 0.0 if std is zero or input is empty.
    """
    r = np.asarray(returns, dtype=np.float64)
    if r.size == 0:
        return 0.0
    std = float(np.std(r, ddof=1)) if r.size > 1 else 0.0
    if std < 1e-12:
        return 0.0
    return float((np.mean(r) - rf) / std)


def profit_factor(gross_profit: float, gross_loss: float) -> float:
    """Profit Factor: PF = gross_profit / gross_loss.

    Args:
        gross_profit: Sum of all winning trades.
        gross_loss: Sum of all losing trades (as positive number).

    Returns:
        Profit factor. Returns inf if no losses, 0.0 if no profits.
    """
    if gross_loss == 0.0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss
