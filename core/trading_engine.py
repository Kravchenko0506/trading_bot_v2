"""
Trading Engine - clean orchestration layer.
CRITICAL: only coordinates services, no business logic, proper error handling.
"""
from decimal import Decimal
from typing import Optional
from .interfaces.trading_interfaces import (
    IMarketDataService, IRiskService, IOrderService,
    INotificationService, IPortfolioService, OrderSide, OrderStatus
)
from .exceptions.trading_exceptions import TradingError, RiskValidationError, OrderExecutionError
from utils.logger import get_trading_logger

logger = get_trading_logger()


class TradingEngine:
    """Clean orchestration layer - only coordinates services"""

    def __init__(self,
                 market_data: IMarketDataService,
                 risk_service: IRiskService,
                 order_service: IOrderService,
                 notification_service: INotificationService,
                 portfolio_service: IPortfolioService):

        # Dependency injection - all services injected via constructor
        self.market_data = market_data
        self.risk_service = risk_service
        self.order_service = order_service
        self.notifications = notification_service
        self.portfolio = portfolio_service

        logger.info("TradingEngine initialized with dependency injection")

    async def execute_buy_signal(self, symbol: str, quantity: Decimal, price: Decimal) -> bool:
        """Execute buy order with full validation pipeline"""
        try:
            logger.info(
                f"Processing buy signal: {symbol} qty={quantity} price={price}")

            # 1. Risk validation
            risk_check = await self.risk_service.validate_buy_order(symbol, quantity, price)
            if not risk_check.approved:
                logger.warning(
                    f"Buy order rejected by risk management: {risk_check.reason}")
                await self.notifications.send_error_alert(
                    f"Buy order rejected: {risk_check.reason}",
                    "RISK_REJECTION"
                )
                return False

            # 2. Execute order
            result = await self.order_service.execute_buy_order(symbol, quantity, price)
            if result.status != OrderStatus.SUCCESS:
                logger.error(f"Buy order execution failed: {result.message}")
                await self.notifications.send_error_alert(
                    f"Buy order failed: {result.message}",
                    "ORDER_EXECUTION_ERROR"
                )
                return False

            # 3. Send success notification
            await self.notifications.send_trade_alert(symbol, OrderSide.BUY, result.executed_price)

            logger.info(
                f"Buy order completed successfully: {symbol} @ {result.executed_price}")
            return True

        except RiskValidationError as e:
            logger.error(f"Risk validation error in buy signal: {e}")
            await self.notifications.send_error_alert(str(e), "RISK_ERROR")
            return False
        except OrderExecutionError as e:
            logger.error(f"Order execution error in buy signal: {e}")
            await self.notifications.send_error_alert(str(e), "EXECUTION_ERROR")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in buy signal: {e}", exc_info=True)
            await self.notifications.send_error_alert(str(e), "UNEXPECTED_ERROR")
            return False

    async def execute_sell_signal(self, symbol: str, current_price: Optional[Decimal] = None) -> bool:
        """Execute sell order with full validation pipeline"""
        try:
            # Get current price if not provided
            if current_price is None:
                current_price = await self.market_data.get_current_price(symbol)

            logger.info(
                f"Processing sell signal: {symbol} price={current_price}")

            # 1. Check if we have position to sell
            position = await self.portfolio.get_position(symbol)
            if not position or position.quantity <= 0:
                logger.warning(f"No position found to sell for {symbol}")
                return False

            # 2. Risk validation
            risk_check = await self.risk_service.validate_sell_order(symbol, current_price)
            if not risk_check.approved:
                logger.warning(
                    f"Sell order rejected by risk management: {risk_check.reason}")
                await self.notifications.send_error_alert(
                    f"Sell order rejected: {risk_check.reason}",
                    "RISK_REJECTION"
                )
                return False

            # 3. Execute sell order
            result = await self.order_service.execute_sell_order(symbol, position.quantity, current_price)
            if result.status != OrderStatus.SUCCESS:
                logger.error(f"Sell order execution failed: {result.message}")
                await self.notifications.send_error_alert(
                    f"Sell order failed: {result.message}",
                    "ORDER_EXECUTION_ERROR"
                )
                return False

            # 4. Calculate profit/loss
            profit = None
            if position.avg_price > 0:
                profit = (result.executed_price - position.avg_price) * \
                    result.executed_quantity

                # Update daily loss tracking if it's a loss
                if profit < 0:
                    self.risk_service.update_daily_loss(abs(profit))

            # 5. Send success notification
            await self.notifications.send_trade_alert(symbol, OrderSide.SELL, result.executed_price, profit)

            logger.info(
                f"Sell order completed successfully: {symbol} @ {result.executed_price} (P&L: {profit})")
            return True

        except Exception as e:
            logger.error(
                f"Unexpected error in sell signal: {e}", exc_info=True)
            await self.notifications.send_error_alert(str(e), "SELL_ERROR")
            return False

    async def get_portfolio_status(self) -> dict:
        """Get comprehensive portfolio status"""
        try:
            balance = await self.portfolio.get_account_balance()
            positions = await self.portfolio.get_all_positions()
            total_value = await self.portfolio.get_total_portfolio_value()

            return {
                "balance_usdt": balance,
                "total_positions": len(positions),
                "total_portfolio_value": total_value,
                "positions": {symbol: {
                    "quantity": pos.quantity,
                    "avg_price": pos.avg_price,
                    "unrealized_pnl": pos.unrealized_pnl
                } for symbol, pos in positions.items()}
            }

        except Exception as e:
            logger.error(f"Failed to get portfolio status: {e}")
            return {}

    async def check_market_conditions(self, symbol: str) -> dict:
        """Check current market conditions for symbol"""
        try:
            current_price = await self.market_data.get_current_price(symbol)
            # Last 24 hours
            klines = await self.market_data.get_klines(symbol, "1h", 24)

            return {
                "symbol": symbol,
                "current_price": current_price,
                "24h_high": max(kline['high'] for kline in klines),
                "24h_low": min(kline['low'] for kline in klines),
                "24h_volume": sum(kline['volume'] for kline in klines),
                "price_change_24h": current_price - klines[0]['open'] if klines else Decimal('0')
            }

        except Exception as e:
            logger.error(
                f"Failed to check market conditions for {symbol}: {e}")
            return {}

    async def send_daily_summary(self) -> bool:
        """Send daily trading summary"""
        try:
            # This would typically pull data from a database of completed trades
            # For now, we'll use placeholder values
            total_trades = 0
            total_profit = Decimal('0.0')
            win_rate = Decimal('0.0')

            return await self.notifications.send_daily_summary(total_trades, total_profit, win_rate)

        except Exception as e:
            logger.error(f"Failed to send daily summary: {e}")
            return False

    async def start(self):
        """Start trading engine (placeholder for main trading loop)"""
        logger.info("Trading engine started")
        # This would contain the main trading loop
        # For now, just log that the engine is ready

    async def stop(self):
        """Stop trading engine gracefully"""
        logger.info("Trading engine stopping...")
        # Cleanup operations would go here
        logger.info("Trading engine stopped")
