"""Stage 6 — Trade Compounder.

Post-trade analysis: 5 analytical agents investigate losing trades,
generate prevention measures, and store insights in the knowledge base.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from predict_market_bot.core.models import Outcome, TradeInsight, TradeResult
from predict_market_bot.knowledge.store import KnowledgeStore

logger = structlog.get_logger(__name__)


# ── Analysis Agents ──────────────────────────────────────────────────────
# Each agent is a function that returns (root_cause, prevention, tags).


def _agent_edge_analysis(trade: TradeResult) -> tuple[str, str, list[str]]:
    """Agent 1: Was the model edge real or illusory?"""
    # TODO: Replace with real statistical analysis
    return (
        "Edge may have been overestimated due to stale signals",
        "Increase signal freshness requirement; add decay weighting",
        ["edge", "signal-quality"],
    )


def _agent_timing_analysis(trade: TradeResult) -> tuple[str, str, list[str]]:
    """Agent 2: Was the entry timing optimal?"""
    return (
        "Entry was too early; market continued to move against position",
        "Add momentum filter before entry; wait for trend confirmation",
        ["timing", "momentum"],
    )


def _agent_sizing_analysis(trade: TradeResult) -> tuple[str, str, list[str]]:
    """Agent 3: Was the position size appropriate?"""
    return (
        "Position size was at upper Kelly bound; drawdown amplified",
        "Reduce Kelly alpha when confidence < 0.7",
        ["sizing", "kelly"],
    )


def _agent_market_regime(trade: TradeResult) -> tuple[str, str, list[str]]:
    """Agent 4: Was the market in an unusual regime?"""
    return (
        "Market exhibited low liquidity at execution time",
        "Add real-time liquidity check before execution; abort if below threshold",
        ["regime", "liquidity"],
    )


def _agent_correlation_check(trade: TradeResult) -> tuple[str, str, list[str]]:
    """Agent 5: Were there correlated positions that increased risk?"""
    return (
        "Multiple positions in related events amplified drawdown",
        "Implement correlation matrix check across open positions",
        ["correlation", "portfolio"],
    )


_ANALYSIS_AGENTS = [
    _agent_edge_analysis,
    _agent_timing_analysis,
    _agent_sizing_analysis,
    _agent_market_regime,
    _agent_correlation_check,
]


# ── Compounder ───────────────────────────────────────────────────────────


class TradeCompounder:
    """Post-mortem analysis engine that learns from losses.

    Runs 5 independent analysis agents on each losing trade,
    consolidates insights, and persists them in the knowledge base.
    """

    def __init__(self, knowledge_store: KnowledgeStore | None = None) -> None:
        self.store = knowledge_store or KnowledgeStore()

    # ── Public API ───────────────────────────────────────────────────

    def analyze(self, trades: list[TradeResult]) -> list[TradeInsight]:
        """Analyze completed trades and store insights.

        Args:
            trades: Trades to analyze (typically after settlement).

        Returns:
            List of generated insights.
        """
        logger.info("compound_started", trade_count=len(trades))
        insights: list[TradeInsight] = []

        losses = [t for t in trades if t.pnl < 0]
        wins = [t for t in trades if t.pnl >= 0]

        logger.info("trade_breakdown", wins=len(wins), losses=len(losses))

        for trade in losses:
            trade_insights = self._run_agents(trade)
            insights.extend(trade_insights)

        # Store insights
        for insight in insights:
            self.store.add_insight(insight)

        logger.info("compound_complete", insights_generated=len(insights))

        # Log reference to similar past cases
        self._reference_past_cases(insights)

        return insights

    # ── Internal ─────────────────────────────────────────────────────

    def _run_agents(self, trade: TradeResult) -> list[TradeInsight]:
        """Run all 5 analysis agents on a losing trade.

        Args:
            trade: The losing trade to analyze.

        Returns:
            List of insights from all agents.
        """
        insights: list[TradeInsight] = []

        for i, agent in enumerate(_ANALYSIS_AGENTS, 1):
            root_cause, prevention, tags = agent(trade)

            insight = TradeInsight(
                trade_id=trade.order.order_id,
                market_id=trade.order.market_id,
                outcome=trade.outcome,
                pnl=trade.pnl,
                root_cause=root_cause,
                prevention=prevention,
                tags=tags,
                created_at=datetime.now(timezone.utc),
            )
            insights.append(insight)

            logger.debug(
                "agent_analysis",
                agent_id=i,
                trade_id=trade.order.order_id,
                root_cause=root_cause,
            )

        return insights

    def _reference_past_cases(self, current_insights: list[TradeInsight]) -> None:
        """Log references to similar past cases for learning.

        Args:
            current_insights: Insights from the current round.
        """
        all_tags: set[str] = set()
        for ins in current_insights:
            all_tags.update(ins.tags)

        if not all_tags:
            return

        similar = self.store.get_similar(list(all_tags), limit=3)
        if similar:
            logger.info(
                "similar_past_cases",
                count=len(similar),
                tags=list(all_tags),
                cases=[s.get("trade_id", "unknown") for s in similar],
            )
