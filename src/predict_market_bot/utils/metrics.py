"""Live performance tracking against target KPIs."""

from __future__ import annotations

from dataclasses import dataclass, field

from predict_market_bot.core.formulas import max_drawdown, profit_factor, sharpe_ratio


# Performance targets from spec
_TARGETS = {
    "win_rate": 0.65,
    "sharpe_ratio": 2.0,
    "profit_factor": 1.5,
    "max_drawdown": 0.08,
}


@dataclass
class PerformanceTracker:
    """Accumulates trade results and computes live performance metrics."""

    wins: int = 0
    losses: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    returns: list[float] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)

    # ── Recording ────────────────────────────────────────────────────

    def record_trade(self, pnl: float, equity: float) -> None:
        """Record the P&L of a settled trade.

        Args:
            pnl: Profit (positive) or loss (negative) of the trade.
            equity: Portfolio value after the trade settles.
        """
        if pnl >= 0:
            self.wins += 1
            self.gross_profit += pnl
        else:
            self.losses += 1
            self.gross_loss += abs(pnl)

        self.returns.append(pnl)
        self.equity_curve.append(equity)

    # ── Metrics ──────────────────────────────────────────────────────

    @property
    def total_trades(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.wins / self.total_trades

    @property
    def current_sharpe(self) -> float:
        return sharpe_ratio(self.returns)

    @property
    def current_profit_factor(self) -> float:
        return profit_factor(self.gross_profit, self.gross_loss)

    @property
    def current_mdd(self) -> float:
        return max_drawdown(self.equity_curve)

    # ── Summary ──────────────────────────────────────────────────────

    def summary(self) -> dict[str, dict[str, float]]:
        """Return current metrics vs targets.

        Returns:
            Dict with ``actual`` and ``target`` sub-dicts.
        """
        return {
            "actual": {
                "win_rate": self.win_rate,
                "sharpe_ratio": self.current_sharpe,
                "profit_factor": self.current_profit_factor,
                "max_drawdown": self.current_mdd,
                "total_trades": float(self.total_trades),
            },
            "target": {k: float(v) for k, v in _TARGETS.items()},
        }

    def meets_targets(self) -> bool:
        """Check if all performance targets are met."""
        return (
            self.win_rate >= _TARGETS["win_rate"]
            and self.current_sharpe >= _TARGETS["sharpe_ratio"]
            and self.current_profit_factor >= _TARGETS["profit_factor"]
            and self.current_mdd <= _TARGETS["max_drawdown"]
        )
