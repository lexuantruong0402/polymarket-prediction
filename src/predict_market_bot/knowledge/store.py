"""JSON-backed knowledge store for trade insights and post-mortem analysis."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from predict_market_bot.core.models import TradeInsight


_DEFAULT_PATH = Path("data/knowledge_base.json")


class KnowledgeStore:
    """Persistent store for trade post-mortem insights.

    Data is persisted as a JSON array so it survives between runs and
    can be referenced by the Compounder and Scanner stages.
    """

    def __init__(self, path: Path | str = _DEFAULT_PATH) -> None:
        self._path = Path(path)
        self._insights: list[dict] = []
        self._load()

    # ── CRUD ─────────────────────────────────────────────────────────

    def add_insight(self, insight: TradeInsight) -> None:
        """Persist a new trade insight.

        Args:
            insight: The trade insight to store.
        """
        record = {
            "trade_id": insight.trade_id,
            "market_id": insight.market_id,
            "outcome": insight.outcome.value,
            "pnl": insight.pnl,
            "root_cause": insight.root_cause,
            "prevention": insight.prevention,
            "tags": insight.tags,
            "created_at": insight.created_at.isoformat(),
        }
        self._insights.append(record)
        self._save()

    def get_all(self) -> list[dict]:
        """Return every stored insight."""
        return list(self._insights)

    def get_similar(self, tags: list[str], limit: int = 5) -> list[dict]:
        """Find insights sharing at least one tag with the query.

        Args:
            tags: Tags to search for.
            limit: Max results to return.

        Returns:
            Matching insights sorted by recency (newest first).
        """
        tag_set = set(tags)
        matches = [
            ins for ins in self._insights if tag_set & set(ins.get("tags", []))
        ]
        # Sort newest first
        matches.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return matches[:limit]

    def get_losses(self, limit: int = 10) -> list[dict]:
        """Return the most recent losing trades.

        Args:
            limit: Max results.

        Returns:
            Insights where pnl < 0, newest first.
        """
        losses = [ins for ins in self._insights if ins.get("pnl", 0) < 0]
        losses.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return losses[:limit]

    # ── Persistence ──────────────────────────────────────────────────

    def _load(self) -> None:
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as f:
                self._insights = json.load(f)
        else:
            self._insights = []

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._insights, f, indent=2, ensure_ascii=False)
