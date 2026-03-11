"""Backtesting engine for evaluating strategies on historical data."""

from datetime import datetime
import json
from pathlib import Path

import structlog

from predict_market_bot.core.models import Market, Outcome, Signal
from predict_market_bot.orchestrator import PipelineOrchestrator
from predict_market_bot.pipeline.fetcher import HistoricalFetcher
from predict_market_bot.pipeline.predictor import MarketPredictor
from predict_market_bot.pipeline.mocks import MockExecutor, MockResearcher, MockScanner

logger = structlog.get_logger(__name__)


class Backtester:
    """Orchestrates a backtest run using historical data."""

    def __init__(self, data_path: str | Path | None = None):
        self.data_path = Path(data_path) if data_path else None
        self.markets: list[Market] = []
        self.outcomes: dict[str, Outcome] = {}
        self.signals_map: dict[str, list[Signal]] = {}
        self.fetcher = HistoricalFetcher()

    def load_data(self) -> None:
        """Load historical markets, outcomes, and signals from JSON."""
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_path}")

        logger.info("loading_backtest_data", path=str(self.data_path))
        with open(self.data_path, "r") as f:
            data = json.load(f)

        # 1. Markets
        for m_data in data.get("markets", []):
            if "close_time" in m_data and isinstance(m_data["close_time"], str):
                dt_str = m_data["close_time"].replace("Z", "+00:00")
                m_data["close_time"] = datetime.fromisoformat(dt_str)
            
            market = Market(**m_data)
            self.markets.append(market)

        # 2. Outcomes
        for m_id, out_str in data.get("outcomes", {}).items():
            self.outcomes[m_id] = Outcome(out_str)

        # 3. Signals (optional)
        for m_id, sigs_data in data.get("signals", {}).items():
            self.signals_map[m_id] = [Signal(**s) for s in sigs_data]

        logger.info(
            "data_loaded", 
            markets=len(self.markets), 
            outcomes=len(self.outcomes),
            signals=len(self.signals_map)
        )

    async def fetch_recent_history(self, limit: int = 20) -> None:
        """Fetch real history from Polymarket API."""
        data = await self.fetcher.fetch_history(limit=limit)
        
        # Parse data into objects
        for m_data in data["markets"]:
            dt_str = m_data["close_time"]
            m_data["close_time"] = datetime.fromisoformat(dt_str)
            self.markets.append(Market(**m_data))
            
        for m_id, out_str in data["outcomes"].items():
            self.outcomes[m_id] = Outcome(out_str)
            
        logger.info("real_history_fetched", markets=len(self.markets))

    def save_to_file(self, path: str | Path) -> None:
        """Save current markets and outcomes to a JSON file for reuse."""
        import json
        from dataclasses import asdict
        
        # Convert markets to dicts for JSON serialization
        data = {
            "markets": [asdict(m) for m in self.markets],
            "outcomes": {k: v.value for k, v in self.outcomes.items()},
            "signals": {k: [asdict(s) for s in v] for k, v in self.signals_map.items()}
        }
        
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            # Use default=str to handle any remaining datetime objects if any
            json.dump(data, f, indent=2, default=str)
        
        logger.info("data_saved_to_file", path=str(output_path), markets=len(self.markets))

    async def run(
        self, 
        confidence_threshold: float | None = None,
        use_real_news: bool = False
    ) -> dict:
        """Run the backtest using the orchestrated pipeline."""
        if not self.markets and self.data_path:
            self.load_data()
        
        if not self.markets:
            logger.warning("no_data_for_backtest", status="fetching_recent_real_history")
            await self.fetch_recent_history()

        # Initialize pipeline with mocks
        scanner = MockScanner(self.markets)
        executor = MockExecutor(self.outcomes)
        predictor = MarketPredictor(confidence_threshold=confidence_threshold)
        
        # If use_real_news is True, we use a real Researcher but with historical dates.
        # This requires Orchestrator support or manual signal fetching here.
        if use_real_news:
            from predict_market_bot.pipeline.researcher import MarketResearcher
            researcher = MarketResearcher()
            
            logger.info("fetching_historical_news_for_backtest")
            # We'll pre-fetch signals using the historical dates to keep Orchestrator simple
            for market in self.markets:
                # Fetch news ending at market close_time
                signals = await researcher.research([market], reference_date=market.close_time)
                self.signals_map.update(signals)
        
        researcher_mock = MockResearcher(self.signals_map)
        
        # Isolated knowledge base for backtesting
        from predict_market_bot.knowledge.store import KnowledgeStore
        backtest_store = KnowledgeStore(path="data/knowledge_base_backtest.json")
        
        orchestrator = PipelineOrchestrator(
            scanner=scanner,
            researcher=researcher_mock,
            executor=executor,
            predictor=predictor,
            knowledge_store=backtest_store
        )

        logger.info("backtest_started")
        result = await orchestrator.run()
        
        # Add backtest-specific stats
        trades = executor.executed_trades
        total_pnl = sum(t.pnl for t in trades)
        win_rate = len([t for t in trades if t.pnl > 0]) / len(trades) if trades else 0
        
        result["backtest"] = {
            "total_pnl": total_pnl,
            "win_rate": win_rate,
            "trades_count": len(trades)
        }
        
        logger.info("backtest_complete", pnl=total_pnl, win_rate=win_rate)
        return result
