"""
Market Data Service - retrieves market data from exchange.
CRITICAL: all prices as Decimal, proper error handling.
"""
from decimal import Decimal
from typing import List, Dict, Any
from ..interfaces.trading_interfaces import IMarketDataService
from ..exceptions.trading_exceptions import MarketDataError
from utils.logger import get_trading_logger

logger = get_trading_logger()


class MarketDataService(IMarketDataService):
    """Market data service implementation"""

    def __init__(self, binance_client):
        self.client = binance_client
        logger.info("MarketDataService initialized")

    async def get_current_price(self, symbol: str) -> Decimal:
        """Get current price for symbol"""
        try:
            logger.debug(f"Fetching current price for {symbol}")

            # Get price from exchange
            price_data = await self.client.get_ticker_price(symbol=symbol)
            if not price_data or 'price' not in price_data:
                raise MarketDataError(
                    f"No price data received for {symbol}", symbol=symbol, data_type="current_price")

            price = Decimal(str(price_data['price']))
            logger.debug(f"Current price for {symbol}: {price}")
            return price

        except MarketDataError:
            raise
        except Exception as e:
            logger.error(f"Failed to get current price for {symbol}: {e}")
            raise MarketDataError(
                f"Price fetch failed: {str(e)}", symbol=symbol, data_type="current_price")

    async def get_klines(self, symbol: str, interval: str, limit: int) -> List[Dict[str, Any]]:
        """Get klines for analysis"""
        try:
            logger.debug(
                f"Fetching klines for {symbol}, interval: {interval}, limit: {limit}")

            # Validate parameters
            if limit <= 0 or limit > 1000:
                raise MarketDataError(
                    f"Invalid limit: {limit}. Must be between 1 and 1000", symbol=symbol, data_type="klines")

            # Get klines from exchange
            klines = await self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
            if not klines:
                raise MarketDataError(
                    f"No klines data received for {symbol}", symbol=symbol, data_type="klines")

            # Convert to proper format with Decimal values
            processed_klines = []
            for kline in klines:
                processed_klines.append({
                    'open_time': kline[0],
                    'open': Decimal(str(kline[1])),
                    'high': Decimal(str(kline[2])),
                    'low': Decimal(str(kline[3])),
                    'close': Decimal(str(kline[4])),
                    'volume': Decimal(str(kline[5])),
                    'close_time': kline[6],
                    'quote_volume': Decimal(str(kline[7])),
                    'trades_count': kline[8],
                    'taker_buy_base_volume': Decimal(str(kline[9])),
                    'taker_buy_quote_volume': Decimal(str(kline[10]))
                })

            logger.debug(
                f"Retrieved {len(processed_klines)} klines for {symbol}")
            return processed_klines

        except MarketDataError:
            raise
        except Exception as e:
            logger.error(f"Failed to get klines for {symbol}: {e}")
            raise MarketDataError(
                f"Klines fetch failed: {str(e)}", symbol=symbol, data_type="klines")
