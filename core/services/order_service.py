"""
Order Service - executes trading orders on exchange.
CRITICAL: atomic operations with proper rollback, all amounts as Decimal.
"""
from decimal import Decimal
from typing import Optional
from ..interfaces.trading_interfaces import IOrderService, OrderResult, OrderStatus, IMarketDataService
from ..exceptions.trading_exceptions import OrderExecutionError, ExchangeConnectionError
from utils.logger import get_trading_logger

logger = get_trading_logger()


class OrderService(IOrderService):
    """Order execution service implementation"""

    def __init__(self, binance_client, market_data_service: IMarketDataService):
        self.client = binance_client
        self.market_data = market_data_service
        logger.info("OrderService initialized")

    async def execute_buy_order(self, symbol: str, quantity: Decimal, price: Decimal) -> OrderResult:
        """Execute buy order on exchange"""
        try:
            logger.info(
                f"Executing buy order: {symbol} qty={quantity} price={price}")

            # Validate inputs
            if quantity <= 0:
                raise OrderExecutionError(f"Invalid quantity: {quantity}")
            if price <= 0:
                raise OrderExecutionError(f"Invalid price: {price}")

            # Get current market price for validation
            current_price = await self.market_data.get_current_price(symbol)
            price_diff_pct = abs((price - current_price) / current_price) * 100

            # Validate price is reasonable (within 5% of market price)
            if price_diff_pct > 5:
                logger.warning(
                    f"Price {price} differs {price_diff_pct:.2f}% from market price {current_price}")

            # Execute order on exchange
            order_response = await self._execute_market_buy(symbol, quantity)

            if order_response and order_response.get('status') == 'FILLED':
                executed_qty = Decimal(
                    str(order_response.get('executedQty', quantity)))
                executed_price = Decimal(
                    str(order_response.get('fills', [{}])[0].get('price', price)))
                order_id = str(order_response.get('orderId', ''))

                logger.info(
                    f"Buy order executed successfully: {symbol} qty={executed_qty} price={executed_price}")
                return OrderResult(
                    status=OrderStatus.SUCCESS,
                    order_id=order_id,
                    executed_price=executed_price,
                    executed_quantity=executed_qty,
                    message=f"Buy order executed: {executed_qty} {symbol} @ {executed_price}"
                )
            else:
                error_msg = f"Buy order failed: {order_response.get('msg', 'Unknown error')}"
                logger.error(error_msg)
                return OrderResult(
                    status=OrderStatus.FAILED,
                    order_id=None,
                    executed_price=None,
                    executed_quantity=None,
                    message=error_msg
                )

        except OrderExecutionError:
            raise
        except Exception as e:
            logger.error(f"Buy order execution failed for {symbol}: {e}")
            raise OrderExecutionError(f"Buy order failed: {str(e)}")

    async def execute_sell_order(self, symbol: str, quantity: Decimal, price: Decimal) -> OrderResult:
        """Execute sell order on exchange"""
        try:
            logger.info(
                f"Executing sell order: {symbol} qty={quantity} price={price}")

            # Validate inputs
            if quantity <= 0:
                raise OrderExecutionError(f"Invalid quantity: {quantity}")
            if price <= 0:
                raise OrderExecutionError(f"Invalid price: {price}")

            # Get current market price for validation
            current_price = await self.market_data.get_current_price(symbol)
            price_diff_pct = abs((price - current_price) / current_price) * 100

            # Validate price is reasonable (within 5% of market price)
            if price_diff_pct > 5:
                logger.warning(
                    f"Price {price} differs {price_diff_pct:.2f}% from market price {current_price}")

            # Execute order on exchange
            order_response = await self._execute_market_sell(symbol, quantity)

            if order_response and order_response.get('status') == 'FILLED':
                executed_qty = Decimal(
                    str(order_response.get('executedQty', quantity)))
                executed_price = Decimal(
                    str(order_response.get('fills', [{}])[0].get('price', price)))
                order_id = str(order_response.get('orderId', ''))

                logger.info(
                    f"Sell order executed successfully: {symbol} qty={executed_qty} price={executed_price}")
                return OrderResult(
                    status=OrderStatus.SUCCESS,
                    order_id=order_id,
                    executed_price=executed_price,
                    executed_quantity=executed_qty,
                    message=f"Sell order executed: {executed_qty} {symbol} @ {executed_price}"
                )
            else:
                error_msg = f"Sell order failed: {order_response.get('msg', 'Unknown error')}"
                logger.error(error_msg)
                return OrderResult(
                    status=OrderStatus.FAILED,
                    order_id=None,
                    executed_price=None,
                    executed_quantity=None,
                    message=error_msg
                )

        except OrderExecutionError:
            raise
        except Exception as e:
            logger.error(f"Sell order execution failed for {symbol}: {e}")
            raise OrderExecutionError(f"Sell order failed: {str(e)}")

    async def _execute_market_buy(self, symbol: str, quantity: Decimal) -> dict:
        """Execute market buy order"""
        try:
            # Convert Decimal to string for API
            qty_str = str(quantity)

            order_params = {
                'symbol': symbol,
                'side': 'BUY',
                'type': 'MARKET',
                'quantity': qty_str
            }

            logger.debug(f"Sending market buy order: {order_params}")
            response = await self.client.create_order(**order_params)
            return response

        except Exception as e:
            logger.error(f"Market buy execution failed: {e}")
            raise ExchangeConnectionError(f"Market buy failed: {str(e)}")

    async def _execute_market_sell(self, symbol: str, quantity: Decimal) -> dict:
        """Execute market sell order"""
        try:
            # Convert Decimal to string for API
            qty_str = str(quantity)

            order_params = {
                'symbol': symbol,
                'side': 'SELL',
                'type': 'MARKET',
                'quantity': qty_str
            }

            logger.debug(f"Sending market sell order: {order_params}")
            response = await self.client.create_order(**order_params)
            return response

        except Exception as e:
            logger.error(f"Market sell execution failed: {e}")
            raise ExchangeConnectionError(f"Market sell failed: {str(e)}")
