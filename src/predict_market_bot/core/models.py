"""Domain data models for the prediction market bot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Side(str, Enum):
    """Order side."""

    YES = "YES"
    NO = "NO"


class OrderStatus(str, Enum):
    """Lifecycle status of an order."""

    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class Outcome(str, Enum):
    """Resolution outcome."""

    WIN = "WIN"
    LOSS = "LOSS"
    VOID = "VOID"
    PENDING = "PENDING"


# ── Stage 1: Scanner ────────────────────────────────────────────────────


@dataclass
class Market:
    """A single prediction market fetched from the exchange."""

    id: str
    question: str
    outcomes: list[str]
    odds: dict[str, float]          # outcome_label → implied probability
    volume_24h: float
    liquidity: float
    close_time: datetime
    spread: float = 0.0
    anomaly_flag: bool = False
    tags: list[str] = field(default_factory=list)


# ── Stage 2: Researcher ─────────────────────────────────────────────────


@dataclass
class Signal:
    """A processed research signal from an external data source."""

    source: str                     # "twitter" | "reddit" | "rss"
    query: str
    sentiment_score: float          # -1.0 … +1.0
    narrative: str
    relevance: float = 0.0         # 0 … 1
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Stage 3: Predictor ──────────────────────────────────────────────────


@dataclass
class Prediction:
    """Model-calibrated probability for a market."""

    market_id: str
    p_model: float                  # calibrated probability
    p_market: float                 # current implied probability from odds
    edge: float                     # p_model - p_market
    confidence: float               # model confidence 0…1
    side: Side = Side.YES
    features: dict[str, float] = field(default_factory=dict)


# ── Stage 4: Risk Manager ───────────────────────────────────────────────


@dataclass
class RiskCheckResult:
    """Outcome of the multi-agent risk gate."""

    passed: bool
    reasons: list[str] = field(default_factory=list)
    kelly_fraction: float = 0.0
    bet_size: float = 0.0
    exposure_after: float = 0.0
    var_current: float = 0.0


# ── Stage 5: Executor ───────────────────────────────────────────────────


@dataclass
class Order:
    """An order to be placed on the CLOB."""

    market_id: str
    side: Side
    size: float
    price: float
    status: OrderStatus = OrderStatus.PENDING
    order_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    slippage: float = 0.0


@dataclass
class TradeResult:
    """Result of a completed trade including P&L."""

    order: Order
    outcome: Outcome = Outcome.PENDING
    pnl: float = 0.0
    brier_contribution: float = 0.0
    resolved_at: datetime | None = None


# ── Stage 6: Compounder ─────────────────────────────────────────────────


@dataclass
class TradeInsight:
    """Post-mortem insight stored in the knowledge base."""

    trade_id: str
    market_id: str
    outcome: Outcome
    pnl: float
    root_cause: str
    prevention: str
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
