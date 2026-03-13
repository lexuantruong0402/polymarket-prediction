"""Pipeline Orchestrator — coordinates all 6 stages end-to-end."""

from __future__ import annotations

import asyncio
import sys
from typing import Any, Callable

import structlog

from predict_market_bot.config.settings import settings
from predict_market_bot.knowledge.store import KnowledgeStore
from predict_market_bot.pipeline.compounder import TradeCompounder
from predict_market_bot.pipeline.executor import OrderExecutor
from predict_market_bot.pipeline.predictor import MarketPredictor
from predict_market_bot.pipeline.researcher import MarketResearcher
from predict_market_bot.pipeline.risk_manager import PortfolioState, RiskManager
from predict_market_bot.pipeline.scanner import MarketScanner
from predict_market_bot.utils.logger import get_logger, setup_logging
from predict_market_bot.utils.metrics import PerformanceTracker

logger: structlog.stdlib.BoundLogger = None  # type: ignore[assignment]


class PipelineOrchestrator:
    """Chains the 6-stage prediction market pipeline.

    Pipeline flow::

        Scan → Research → Predict → Risk → Execute → Compound
    """

    def __init__(
        self,
        scanner: MarketScanner | None = None,
        researcher: MarketResearcher | None = None,
        predictor: MarketPredictor | None = None,
        risk_manager: RiskManager | None = None,
        executor: OrderExecutor | None = None,
        knowledge_store: KnowledgeStore | None = None,
    ) -> None:
        # Pipeline stages (injectable)
        self.scanner = scanner or MarketScanner()
        self.researcher = researcher or MarketResearcher()
        self.predictor = predictor or MarketPredictor()
        self.risk_manager = risk_manager or RiskManager()
        self.executor = executor or OrderExecutor()
        self.knowledge_store = knowledge_store or KnowledgeStore()
        self.compounder = TradeCompounder(self.knowledge_store)

        # State tracking
        self.tracker = PerformanceTracker()
        self.portfolio = PortfolioState(
            bankroll=settings.bankroll,
            current_exposure=0.0,
            equity_curve=[settings.bankroll],
            daily_returns=[],
        )

    async def run(self, slug: str | None = None, callback: Callable[[dict], Any] | None = None) -> dict:
        """Execute the full pipeline.

        Args:
            slug: Optional Polymarket slug to process a specific market.
            callback: Optional async callback to report stage progress.

        Returns:
            Summary dict with stage counts and performance metrics.
        """
        global logger
        setup_logging()
        logger = get_logger("orchestrator")

        logger.info("pipeline_started", bankroll=settings.bankroll, slug=slug)

        async def report_progress(stage: str, data: dict):
            if callback:
                payload = {"stage": stage, "data": data}
                if asyncio.iscoroutinefunction(callback):
                    await callback(payload)
                else:
                    callback(payload)

        # ── Stage 1: Scan ────────────────────────────────────────────
        logger.info("stage", name="1/6 SCAN")
        await report_progress("SCAN", {"status": "started", "slug": slug})
        
        if slug:
            markets = await self.scanner.fetch_by_slug(slug)
        else:
            markets = await self.scanner.scan()

        if not markets:
            logger.warning("pipeline_aborted", reason="No markets passed scan filters")
            await report_progress("SCAN", {"status": "aborted", "reason": "no_markets"})
            return {"aborted": True, "reason": "no_markets"}
        
        await report_progress("SCAN", {"status": "complete", "count": len(markets)})

        # ── Stage 2: Research ────────────────────────────────────────
        logger.info("stage", name="2/6 RESEARCH")
        await report_progress("RESEARCH", {"status": "started"})
        signals_map = await self.researcher.research(markets)
        await report_progress("RESEARCH", {"status": "complete", "signals": len(signals_map)})

        # ── Stage 3: Predict ─────────────────────────────────────────
        logger.info("stage", name="3/6 PREDICT")
        await report_progress("PREDICT", {"status": "started"})
        predictions = await self.predictor.predict(markets, signals_map)
        await report_progress("PREDICT", {"status": "complete", "predictions": len(predictions)})
        
        if not predictions:
            logger.info("pipeline_complete", reason="No predictions above confidence threshold")
            summary = {
                "markets_scanned": len(markets),
                "predictions": 0,
                "approved": 0,
                "rejected": 0,
                "trades_executed": 0,
                "insights_generated": 0,
                "performance": self.tracker.summary(),
            }
            await report_progress("COMPLETE", summary)
            return summary

        # ── Stage 4: Risk ────────────────────────────────────────────
        logger.info("stage", name="4/6 RISK")
        await report_progress("RISK", {"status": "started"})
        evaluated = self.risk_manager.evaluate_batch(predictions, self.portfolio)
        approved = [(pred, risk) for pred, risk in evaluated if risk.passed]
        rejected = [(pred, risk) for pred, risk in evaluated if not risk.passed]

        logger.info(
            "risk_summary",
            approved=len(approved),
            rejected=len(rejected),
        )
        await report_progress("RISK", {"status": "complete", "approved": len(approved), "rejected": len(rejected)})

        if not approved:
            logger.info("pipeline_complete", reason="All predictions rejected by risk checks")
            summary = {
                "markets_scanned": len(markets),
                "predictions": len(predictions),
                "approved": 0,
                "rejected": len(rejected),
                "trades_executed": 0,
                "insights_generated": 0,
                "performance": self.tracker.summary(),
            }
            await report_progress("COMPLETE", summary)
            return summary

        # ── Stage 5: Execute ─────────────────────────────────────────
        logger.info("stage", name="5/6 EXECUTE")
        await report_progress("EXECUTE", {"status": "started"})
        trade_results = await self.executor.execute_batch(approved)

        # Update portfolio state
        for result in trade_results:
            self.portfolio.current_exposure += result.order.size
        
        await report_progress("EXECUTE", {"status": "complete", "trades": len(trade_results)})

        # ── Stage 6: Compound ────────────────────────────────────────
        logger.info("stage", name="6/6 COMPOUND")
        await report_progress("COMPOUND", {"status": "started"})
        insights = self.compounder.analyze(trade_results)
        await report_progress("COMPOUND", {"status": "complete", "insights": len(insights)})

        # ── Summary ──────────────────────────────────────────────────
        summary = {
            "markets_scanned": len(markets),
            "predictions": len(predictions),
            "approved": len(approved),
            "rejected": len(rejected),
            "trades_executed": len(trade_results),
            "insights_generated": len(insights),
            "performance": self.tracker.summary(),
        }

        logger.info("pipeline_complete", **summary)
        await report_progress("COMPLETE", summary)
        return summary


def main() -> None:
    """CLI entry point."""
    orchestrator = PipelineOrchestrator()
    result = asyncio.run(orchestrator.run())

    # Print summary
    print("\n" + "=" * 60)
    print("  PREDICT MARKET BOT — Pipeline Complete")
    print("=" * 60)
    for key, value in result.items():
        if isinstance(value, dict):
            print(f"\n  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")
    print("=" * 60)


if __name__ == "__main__":
    main()
