"""Stage 5 — Order Executor.

Places orders via CLOB API, monitors slippage, and supports
auto-hedging when conditions change before settlement.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import structlog

from predict_market_bot.config.settings import settings
from predict_market_bot.core.models import (
    Order,
    OrderStatus,
    Outcome,
    Prediction,
    RiskCheckResult,
    Side,
    TradeResult,
)

logger = structlog.get_logger(__name__)


class OrderExecutor:
    """Execute trades on prediction market CLOB."""

    MAX_SLIPPAGE = 0.02  # 2% max acceptable slippage

    def __init__(self, api_base_url: str | None = None, api_key: str | None = None) -> None:
        self.api_base_url = api_base_url or settings.api_base_url
        self.api_key = api_key or settings.api_key

    # ── Public API ───────────────────────────────────────────────────

    async def execute(
        self,
        prediction: Prediction,
        risk_result: RiskCheckResult,
    ) -> TradeResult:
        """Place an order and return the trade result.

        Args:
            prediction: The prediction to act on.
            risk_result: Approved risk check with sizing info.

        Returns:
            TradeResult capturing the order and outcome status.
        """
        order = Order(
            market_id=prediction.market_id,
            side=prediction.side,
            size=risk_result.bet_size,
            price=prediction.p_market,
            order_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
        )

        logger.info(
            "order_placing",
            order_id=order.order_id,
            market_id=order.market_id,
            side=order.side.value,
            size=round(order.size, 2),
            price=round(order.price, 4),
        )

        # Submit to exchange
        order = await self._submit_order(order)

        # Check slippage
        if order.slippage > self.MAX_SLIPPAGE:
            logger.warning(
                "slippage_exceeded",
                order_id=order.order_id,
                slippage=round(order.slippage, 4),
                max_slippage=self.MAX_SLIPPAGE,
            )
            # Attempt hedge
            await self._auto_hedge(order)

        result = TradeResult(order=order)
        logger.info(
            "order_complete",
            order_id=order.order_id,
            status=order.status.value,
            slippage=round(order.slippage, 4),
        )

        return result

    async def execute_batch(
        self,
        approved: list[tuple[Prediction, RiskCheckResult]],
    ) -> list[TradeResult]:
        """Execute multiple approved trades sequentially.

        Sequential execution ensures each order's impact is accounted for
        before placing the next.

        Args:
            approved: List of (prediction, risk_result) tuples.

        Returns:
            List of trade results.
        """
        results: list[TradeResult] = []
        for prediction, risk_result in approved:
            result = await self.execute(prediction, risk_result)
            results.append(result)
        return results

    # ── Exchange stubs ───────────────────────────────────────────────

    async def _submit_order(self, order: Order) -> Order:
        """Submit order to the CLOB API.

        **Stub implementation** — replace with real on-chain API call.

        Args:
            order: The order to submit.

        Returns:
            Updated order with fill status and slippage.
        """
        # TODO: Replace with real httpx call to CLOB API
        await asyncio.sleep(0.01)  # simulate latency

        # Simulate fill with minor slippage
        order.status = OrderStatus.FILLED
        order.slippage = abs(hash(order.order_id) % 100) / 5000.0  # 0–0.02
        return order

    async def _auto_hedge(self, order: Order) -> None:
        """Place a hedging order when slippage exceeds threshold.

        **Stub implementation** — replace with real hedge logic.

        Args:
            order: The order that experienced excessive slippage.
        """
        # TODO: Implement real hedging via opposite-side order
        hedge_side = Side.NO if order.side == Side.YES else Side.YES
        logger.info(
            "auto_hedge_triggered",
            original_order=order.order_id,
            hedge_side=hedge_side.value,
            market_id=order.market_id,
        )
        await asyncio.sleep(0.01)  # simulate hedge execution
