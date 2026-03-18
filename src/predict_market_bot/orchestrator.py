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
            logger.warning("pipeline_aborted", reason="No markets found")
            await report_progress("SCAN", {"status": "aborted", "reason": "no_markets"})
            return {"aborted": True, "reason": "no_markets"}
        
        # Limit to top 4 markets by YES odds (robust to case and common labels)
        def get_yes_odds(m):
            for label in ["Yes", "YES", "True", "TRUE"]:
                if label in m.odds:
                    return m.odds[label]
            return 0.0

        markets = sorted(markets, key=get_yes_odds, reverse=True)[:4]
        
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
        
        # ── Summary ──────────────────────────────────────────────────
        def get_status(p):
            if p.confidence < settings.confidence_threshold:
                return "Not enough confident"
            return "Yes" if p.edge > 0 else "No"

        summary = {
            "markets_scanned": len(markets),
            "predictions": [
                {
                    "market_id": p.market_id,
                    "question": next((m.question for m in markets if m.id == p.market_id), "Unknown"),
                    "p_model": p.p_model,
                    "p_market": p.p_market,
                    "edge": p.edge,
                    "confidence": p.confidence,
                    "status": get_status(p),
                    "side": p.side.value if hasattr(p.side, 'value') else p.side,
                    "reasoning": p.features.get("llm_reasoning", "No reasoning provided")
                } for p in predictions
            ],
            "research": {
                m.id: [
                    {
                        "source": s.source,
                        "narrative": s.narrative,
                        "sentiment": s.sentiment_score,
                        "url": s.metadata.get("url")
                    } for s in signals_map.get(m.id, [])
                ] for m in markets
            },
            "performance": self.tracker.summary(),
        }

        logger.info("pipeline_complete", predictions=len(predictions))
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
