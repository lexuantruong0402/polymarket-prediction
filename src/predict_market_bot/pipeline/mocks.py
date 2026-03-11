"""Mock stages for backtesting and simulation."""

from __future__ import annotations

from typing import Any

from predict_market_bot.core.models import Market, Order, Outcome, Prediction, RiskCheckResult, Side, TradeResult
from predict_market_bot.pipeline.executor import OrderExecutor
from predict_market_bot.pipeline.scanner import MarketScanner
from predict_market_bot.pipeline.researcher import MarketResearcher


class MockScanner(MarketScanner):
    """Scanner that returns pre-defined historical markets."""

    def __init__(self, markets: list[Market]):
        # No need to call super().__init__ if it tries to init API clients
        self.markets = markets

    async def scan(self) -> list[Market]:
        return self.markets


class MockExecutor(OrderExecutor):
    """Executor that simulates order placement and immediate settlement."""

    def __init__(self, outcomes: dict[str, Outcome]):
        self.outcomes = outcomes
        self.executed_trades: list[TradeResult] = []

    async def execute_batch(
        self, approved: list[tuple[Prediction, RiskCheckResult]]
    ) -> list[TradeResult]:
        results: list[TradeResult] = []
        
        for pred, risk in approved:
            market_id = pred.market_id
            outcome = self.outcomes.get(market_id, Outcome.PENDING)
            
            size = risk.bet_size
            price = pred.p_market
            side = pred.side
            
            # Simple settlement:
            # If we bet YES and outcome is WIN -> pnl > 0
            # If we bet NO and outcome is LOSS -> pnl > 0 (Wait, Outcome.WIN usually means the event happened)
            # Standard Polymarket: 1 share of YES pays $1 if YES, 0 if NO.
            # 1 share of NO pays $1 if NO, 0 if YES.
            
            pnl = 0.0
            if outcome != Outcome.PENDING and outcome != Outcome.VOID:
                # Assuming WIN means YES happened, LOSS means NO happened.
                if (side == Side.YES and outcome == Outcome.WIN) or \
                   (side == Side.NO and outcome == Outcome.LOSS):
                    # Win: pnl = size * (1/price - 1)
                    pnl = size * (1.0 / price - 1.0)
                else:
                    # Loss
                    pnl = -size
                
            order = Order(
                market_id=market_id,
                side=side,
                size=size,
                price=price,
                order_id=f"mock_{market_id}"
            )
            
            res = TradeResult(
                order=order,
                outcome=outcome,
                pnl=pnl
            )
            results.append(res)
            
        self.executed_trades.extend(results)
        return results


class MockResearcher(MarketResearcher):
    """Researcher that returns pre-defined historical signals."""

    def __init__(self, signals_map: dict[str, list[Signal]]):
        self.signals_map = signals_map

    async def research(self, markets: list[Market]) -> dict[str, list[Signal]]:
        return self.signals_map
