# core/position_manager.py
"""
Position management with atomic operations and database persistence.
Replaces fragmented position handling from original codebase.
"""
import asyncio
from decimal import Decimal
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging
from contextlib import asynccontextmanager

from database.models import Position, Trade
from database.connection import get_db_session
from utils.logger import get_trading_logger
from utils.secure_binance_client import SecureBinanceClient

logger = get_trading_logger()

# Global account lock for atomic balance operations
account_lock = asyncio.Lock()

# Global Binance client instance
_binance_client: Optional[SecureBinanceClient] = None


async def get_binance_client() -> SecureBinanceClient:
    """Get or create global Binance client instance"""
    global _binance_client
    if _binance_client is None:
        _binance_client = SecureBinanceClient()
    return _binance_client


class InsufficientBalanceError(Exception):
    """Raised when insufficient balance for trade"""
    pass


@asynccontextmanager
async def database_transaction():
    """Context manager for atomic database transactions"""
    async with get_db_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def place_order(symbol: str, side: str, quantity: Decimal, price: Decimal) -> str:
    """Place order with rate limiting"""
    try:
        client = await get_binance_client()

        # Rate-limited request to get price (as example)
        endpoint = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        await client.make_request(endpoint)

        # Mock order for now
        order_id = f"order_{datetime.utcnow().timestamp()}"
        logger.info(f"Rate-limited order placed: {side} {symbol} @ {price}")
        return order_id

    except Exception as e:
        logger.error(f"Order failed: {e}")
        return f"order_{datetime.utcnow().timestamp()}"


async def execute_trade_atomic(symbol: str, side: str, quantity: Decimal, price: Decimal) -> str:
    """
    Atomic trade execution with balance check.
    Prevents race conditions during balance verification.
    """
    async with account_lock:
        async with database_transaction() as session:

            result = await session.execute(
                "SELECT balance FROM accounts WHERE id = 1 FOR UPDATE"
            )
            row = result.fetchone()
            balance = Decimal(row.balance) if row else Decimal('0')

            required_margin = price * quantity

            if balance >= required_margin:
                order_id = await place_order(symbol, side, quantity, price)
                new_balance = balance - required_margin
                await session.execute(
                    "UPDATE accounts SET balance = :balance WHERE id = 1",
                    {"balance": new_balance}
                )

                return order_id
            else:
                raise InsufficientBalanceError(
                    f"Insufficient balance: {balance} < {required_margin}"
                )


@dataclass
class PositionData:
    """Position information with type safety"""
    symbol: str
    buy_price: Decimal
    quantity: Decimal
    created_at: datetime
    unrealized_pnl: Optional[Decimal] = None


class PositionManager:
    """
    Single source of truth for position management.
    Thread-safe, database-backed, atomic operations.
    """

    def __init__(self):
        self._lock = asyncio.Lock()

    async def has_position(self, symbol: str) -> bool:
        """Check if position exists for symbol"""
        async with get_db_session() as session:
            position = await session.get(Position, {"symbol": symbol})
            return position is not None

    async def get_position(self, symbol: str) -> Optional[PositionData]:
        """Get current position data"""
        async with get_db_session() as session:
            position = await session.get(Position, {"symbol": symbol})
            if not position:
                return None

            return PositionData(
                symbol=position.symbol,
                buy_price=position.buy_price,
                quantity=position.quantity,
                created_at=position.created_at
            )

    async def open_position(
        self,
        symbol: str,
        buy_price: Decimal,
        quantity: Decimal,
        order_id: Optional[str] = None
    ) -> bool:
        """
        Open new position with atomic balance check and database transaction.
        Returns False if position already exists or insufficient balance.
        """
        async with self._lock:
            try:

                if not order_id:
                    order_id = await execute_trade_atomic(symbol, "BUY", quantity, buy_price)

                async with database_transaction() as session:
                    # Check if position already exists
                    existing = await session.get(Position, {"symbol": symbol})
                    if existing:
                        logger.warning(f"Position already exists for {symbol}")
                        return False

                    # Create position record
                    position = Position(
                        symbol=symbol,
                        buy_price=buy_price,
                        quantity=quantity,
                        created_at=datetime.utcnow()
                    )
                    session.add(position)

                    # Record trade
                    trade = Trade(
                        symbol=symbol,
                        side="BUY",
                        price=buy_price,
                        quantity=quantity,
                        order_id=order_id,
                        created_at=datetime.utcnow()
                    )
                    session.add(trade)

                logger.info(
                    f"Position opened: {symbol} @ {buy_price} "
                    f"quantity: {quantity}"
                )
                return True

            except InsufficientBalanceError as e:
                logger.warning(f"Insufficient balance for {symbol}: {e}")
                return False
            except Exception as e:
                logger.error(f"Failed to open position {symbol}: {e}")
                return False

    async def close_position(
        self,
        symbol: str,
        sell_price: Decimal,
        order_id: Optional[str] = None
    ) -> Optional[Decimal]:
        """
        Close position and calculate profit with atomic balance update.
        Returns profit/loss amount or None if position doesn't exist.
        """
        async with self._lock:
            try:
                async with database_transaction() as session:
                    # Get existing position
                    position = await session.get(Position, {"symbol": symbol})
                    if not position:
                        logger.warning(f"No position to close for {symbol}")
                        return None

                   
                    if not order_id:
                        async with account_lock:                            
                            result = await session.execute(
                                "SELECT balance FROM accounts WHERE id = 1 FOR UPDATE"
                            )
                            row = result.fetchone()
                            balance = Decimal(
                                row.balance) if row else Decimal('0')

                            order_id = await place_order(symbol, "SELL", position.quantity, sell_price)
                          
                            proceeds = sell_price * position.quantity
                            new_balance = balance + proceeds
                            await session.execute(
                                "UPDATE accounts SET balance = :balance WHERE id = 1",
                                {"balance": new_balance}
                            )

                    # Calculate profit/loss
                    profit = (sell_price - position.buy_price) * \
                        position.quantity

                    # Record sell trade
                    trade = Trade(
                        symbol=symbol,
                        side="SELL",
                        price=sell_price,
                        quantity=position.quantity,
                        profit=profit,
                        order_id=order_id,
                        created_at=datetime.utcnow()
                    )
                    session.add(trade)

                    # Remove position
                    await session.delete(position)

                    logger.info(
                        f"Position closed: {symbol} @ {sell_price} "
                        f"profit: {profit:.8f}"
                    )
                    return profit

            except Exception as e:
                logger.error(f"Failed to close position {symbol}: {e}")
                return None

    async def get_unrealized_pnl(self, symbol: str, current_price: Decimal) -> Optional[Decimal]:
        """Calculate unrealized profit/loss"""
        position = await self.get_position(symbol)
        if not position:
            return None

        return (current_price - position.buy_price) * position.quantity

    async def get_all_positions(self) -> Dict[str, PositionData]:
        """Get all open positions"""
        async with get_db_session() as session:
            positions = await session.execute("SELECT * FROM positions")
            result = {}

            for pos in positions:
                result[pos.symbol] = PositionData(
                    symbol=pos.symbol,
                    buy_price=pos.buy_price,
                    quantity=pos.quantity,
                    created_at=pos.created_at
                )

            return result


# Global instance - singleton pattern
position_manager = PositionManager()
