# core/trading_engine.py
"""
Trading engine with dependency injection and event-driven architecture.
Decoupled from specific implementations.
"""
import asyncio
from decimal import Decimal
from typing import Optional, Dict, Any

from core.interfaces import IOrderExecutor, IRiskManager, IMarketData
from core.event_bus import event_bus
from utils.logger import get_trading_logger

logger = get_trading_logger()


class TradingEngine:
    def __init__(self,
                 order_executor: IOrderExecutor,
                 risk_manager: IRiskManager,
                 market_data: Optional[IMarketData] = None):
        self.order_executor = order_executor
        self.risk_manager = risk_manager
        self.market_data = market_data

        # Subscribe to events
        event_bus.subscribe("order_request", self._handle_order_request)
        event_bus.subscribe("price_update", self._handle_price_update)

    async def execute_trade(self, symbol: str, side: str, quantity: Decimal, price: Decimal) -> bool:
        """Execute trade with risk validation"""
        try:
            # Risk validation
            if not await self.risk_manager.validate_trade(symbol, quantity, price):
                await event_bus.publish("trade_rejected", {
                    "symbol": symbol, "reason": "risk_validation_failed"
                })
                return False

            # Execute order
            order_id = await self.order_executor.execute_order(symbol, side, quantity, price)

            # Publish success event
            await event_bus.publish("trade_executed", {
                "symbol": symbol, "side": side, "quantity": quantity,
                "price": price, "order_id": order_id
            })

            return True

        except Exception as e:
            await event_bus.publish("trade_failed", {
                "symbol": symbol, "error": str(e)
            })
            return False

    async def _handle_order_request(self, data: Dict[str, Any]):
        """Handle incoming order requests via events"""
        await self.execute_trade(
            data["symbol"], data["side"],
            data["quantity"], data["price"]
        )

    async def _handle_price_update(self, data: Dict[str, Any]):
        """Handle price updates"""
        logger.debug(f"Price update: {data}")


# Concrete implementations
class OrderExecutor(IOrderExecutor):
    """Concrete order executor using position manager"""

    def __init__(self, position_manager):
        self.position_manager = position_manager

    async def execute_order(self, symbol: str, side: str, quantity: Decimal, price: Decimal) -> str:
        from core.position_manager import place_order
        return await place_order(symbol, side, quantity, price)


class RiskManager(IRiskManager):
    """Simple risk manager implementation"""

    def __init__(self, max_position_size: Decimal = Decimal('1000')):
        self.max_position_size = max_position_size

    async def validate_trade(self, symbol: str, quantity: Decimal, price: Decimal) -> bool:
        trade_value = quantity * price

        if trade_value > self.max_position_size:
            logger.warning(
                f"Trade value {trade_value} exceeds max position size")
            return False

        return True


class MarketData(IMarketData):
    """Market data provider"""

    async def get_price(self, symbol: str) -> Decimal:
        return Decimal('50000.0')


# Factory function
def create_trading_engine() -> TradingEngine:
    """Create trading engine with injected dependencies"""
    from core.position_manager import position_manager

    order_executor = OrderExecutor(position_manager)
    risk_manager = RiskManager()
    market_data = MarketData()

    return TradingEngine(order_executor, risk_manager, market_data)
