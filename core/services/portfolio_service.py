"""
Portfolio Service - manages portfolio positions and account balance.
CRITICAL: atomic operations, accurate balance tracking, Decimal precision.
"""
from decimal import Decimal
from typing import Optional, Dict
from ..interfaces.trading_interfaces import IPortfolioService, PositionData
from ..exceptions.trading_exceptions import PositionNotFoundError, ExchangeConnectionError
from utils.logger import get_trading_logger

logger = get_trading_logger()


class PortfolioService(IPortfolioService):
    """Portfolio management service implementation"""

    def __init__(self, binance_client):
        self.client = binance_client
        self._position_cache: Dict[str, PositionData] = {}
        self._balance_cache: Optional[Decimal] = None
        self._cache_timestamp = 0
        self._cache_ttl = 30  # 30 seconds cache TTL

        logger.info("PortfolioService initialized")

    async def get_position(self, symbol: str) -> Optional[PositionData]:
        """Get position by symbol"""
        try:
            logger.debug(f"Getting position for {symbol}")

            # Check cache first
            if self._is_cache_valid() and symbol in self._position_cache:
                logger.debug(f"Position cache hit for {symbol}")
                return self._position_cache[symbol]

            # Fetch from exchange
            await self._refresh_positions()

            position = self._position_cache.get(symbol)
            if position:
                logger.debug(
                    f"Position found for {symbol}: qty={position.quantity}")
            else:
                logger.debug(f"No position found for {symbol}")

            return position

        except Exception as e:
            logger.error(f"Failed to get position for {symbol}: {e}")
            raise ExchangeConnectionError(f"Position fetch failed: {str(e)}")

    async def get_account_balance(self) -> Decimal:
        """Get account balance (USDT)"""
        try:
            logger.debug("Getting account balance")

            # Check cache first
            if self._is_cache_valid() and self._balance_cache is not None:
                logger.debug(f"Balance cache hit: {self._balance_cache}")
                return self._balance_cache

            # Fetch from exchange
            account_info = await self.client.get_account()

            if not account_info or 'balances' not in account_info:
                raise ExchangeConnectionError("Invalid account info received")

            # Find USDT balance
            usdt_balance = Decimal('0.0')
            for balance in account_info['balances']:
                if balance['asset'] == 'USDT':
                    usdt_balance = Decimal(str(balance['free']))
                    break

            # Update cache
            self._balance_cache = usdt_balance
            self._update_cache_timestamp()

            logger.debug(f"Account balance: {usdt_balance} USDT")
            return usdt_balance

        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
            raise ExchangeConnectionError(f"Balance fetch failed: {str(e)}")

    async def has_position(self, symbol: str) -> bool:
        """Check if position exists"""
        try:
            position = await self.get_position(symbol)
            has_pos = position is not None and position.quantity > 0
            logger.debug(f"Position check for {symbol}: {has_pos}")
            return has_pos

        except Exception as e:
            logger.error(f"Failed to check position for {symbol}: {e}")
            return False

    async def get_all_positions(self) -> Dict[str, PositionData]:
        """Get all open positions"""
        try:
            logger.debug("Getting all positions")

            # Check cache first
            if self._is_cache_valid():
                logger.debug("All positions cache hit")
                return self._position_cache.copy()

            # Refresh from exchange
            await self._refresh_positions()
            return self._position_cache.copy()

        except Exception as e:
            logger.error(f"Failed to get all positions: {e}")
            raise ExchangeConnectionError(f"Positions fetch failed: {str(e)}")

    async def get_total_portfolio_value(self) -> Decimal:
        """Get total portfolio value in USDT"""
        try:
            logger.debug("Calculating total portfolio value")

            # Get account balance
            balance = await self.get_account_balance()
            total_value = balance

            # Add value of all positions
            positions = await self.get_all_positions()
            for symbol, position in positions.items():
                # Get current price for position valuation
                try:
                    current_price = await self._get_current_price(symbol)
                    position_value = position.quantity * current_price
                    total_value += position_value
                    logger.debug(f"Position {symbol} value: {position_value}")
                except Exception as e:
                    logger.warning(f"Failed to get price for {symbol}: {e}")

            logger.info(f"Total portfolio value: {total_value} USDT")
            return total_value

        except Exception as e:
            logger.error(f"Failed to calculate portfolio value: {e}")
            raise ExchangeConnectionError(
                f"Portfolio value calculation failed: {str(e)}")

    async def _refresh_positions(self):
        """Refresh positions from exchange"""
        try:
            logger.debug("Refreshing positions from exchange")

            account_info = await self.client.get_account()
            if not account_info or 'balances' not in account_info:
                raise ExchangeConnectionError("Invalid account info received")

            # Clear cache
            self._position_cache.clear()

            # Process balances
            for balance in account_info['balances']:
                asset = balance['asset']
                free_amount = Decimal(str(balance['free']))
                locked_amount = Decimal(str(balance['locked']))
                total_amount = free_amount + locked_amount

                # Only track positions with significant amounts (> 0.001)
                if total_amount > Decimal('0.001') and asset != 'USDT':
                    # For spot trading, we'll use a simplified position structure
                    # In real implementation, you might want to get avg price from trade history
                    symbol = f"{asset}USDT"

                    position = PositionData(
                        symbol=symbol,
                        quantity=total_amount,
                        # Would need to calculate from trade history
                        avg_price=Decimal('0.0'),
                        # Would need current price to calculate
                        unrealized_pnl=Decimal('0.0')
                    )

                    self._position_cache[symbol] = position
                    logger.debug(
                        f"Cached position: {symbol} qty={total_amount}")

            self._update_cache_timestamp()
            logger.debug(f"Refreshed {len(self._position_cache)} positions")

        except Exception as e:
            logger.error(f"Failed to refresh positions: {e}")
            raise ExchangeConnectionError(f"Position refresh failed: {str(e)}")

    async def _get_current_price(self, symbol: str) -> Decimal:
        """Get current price for symbol"""
        try:
            ticker = await self.client.get_ticker_price(symbol=symbol)
            if ticker and 'price' in ticker:
                return Decimal(str(ticker['price']))
            else:
                raise ExchangeConnectionError(f"No price data for {symbol}")
        except Exception as e:
            logger.error(f"Failed to get current price for {symbol}: {e}")
            raise ExchangeConnectionError(f"Price fetch failed: {str(e)}")

    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
        import time
        return (time.time() - self._cache_timestamp) < self._cache_ttl

    def _update_cache_timestamp(self):
        """Update cache timestamp"""
        import time
        self._cache_timestamp = time.time()

    def invalidate_cache(self):
        """Manually invalidate cache"""
        self._position_cache.clear()
        self._balance_cache = None
        self._cache_timestamp = 0
        logger.debug("Portfolio cache invalidated")

    def set_cache_ttl(self, ttl_seconds: int):
        """Set cache time-to-live"""
        self._cache_ttl = ttl_seconds
        logger.info(f"Cache TTL set to {ttl_seconds} seconds")
