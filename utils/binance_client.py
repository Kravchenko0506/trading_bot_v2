# utils/binance_client.py
"""
Binance API client wrapper with async support and error handling.
Provides methods for trading operations with rate limiting and retry logic.
This module is designed to be used with asyncio and provides a clean interface
"""
import asyncio
import time
from decimal import Decimal
from typing import Optional, Dict, Any, List
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException

from config.settings import settings
from utils.logger import get_trading_logger

logger = get_trading_logger()


class BinanceClient:
    """
    Async wrapper for Binance API with proper error handling and rate limiting.
    Provides clean interface for trading operations.
    """
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.client = Client(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet
        )
        self.testnet = testnet
        self._last_request_time = 0
        self._rate_limit_delay = 0.1  # 100ms between requests
        
        logger.info(f"Binance client initialized (testnet: {testnet})")
    
    async def _rate_limit(self):
        """Simple rate limiting to avoid API limits"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - time_since_last)
        
        self._last_request_time = time.time()
    
    async def _execute_with_retry(self, func, *args, max_retries: int = 3, **kwargs):
        """Execute API call with retry logic"""
        await self._rate_limit()
        
        for attempt in range(max_retries):
            try:
                # Run sync API call in thread pool
                result = await asyncio.to_thread(func, *args, **kwargs)
                return result
                
            except BinanceAPIException as e:
                if e.code == -1021:  # Timestamp out of sync
                    logger.warning("Timestamp out of sync, retrying...")
                    await asyncio.sleep(1)
                    continue
                elif e.code == -2010:  # Insufficient balance
                    logger.error(f"Insufficient balance: {e.message}")
                    return None
                elif e.code == -1013:  # Filter failure (lot size, etc.)
                    logger.error(f"Order filter failure: {e.message}")
                    return None
                else:
                    logger.error(f"Binance API error (code {e.code}): {e.message}")
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)
                    
            except Exception as e:
                logger.error(f"Unexpected error in API call: {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
        
        return None
    
    async def get_current_price(self, symbol: str) -> Optional[Decimal]:
        """Get current market price for symbol"""
        try:
            ticker = await self._execute_with_retry(
                self.client.get_symbol_ticker,
                symbol=symbol
            )
            
            if ticker and 'price' in ticker:
                price = Decimal(ticker['price'])
                logger.debug(f"Current price {symbol}: {price}")
                return price
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return None
    
    async def get_balance(self, asset: str) -> Optional[Decimal]:
        """Get available balance for asset"""
        try:
            account = await self._execute_with_retry(self.client.get_account)
            
            if not account or 'balances' not in account:
                return None
            
            for balance in account['balances']:
                if balance['asset'] == asset:
                    free_balance = Decimal(balance['free'])
                    logger.debug(f"Balance {asset}: {free_balance}")
                    return free_balance
            
            # Asset not found in balances
            return Decimal('0')
            
        except Exception as e:
            logger.error(f"Failed to get balance for {asset}: {e}")
            return None
    
    async def get_lot_size_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get lot size and precision info for symbol"""
        try:
            exchange_info = await self._execute_with_retry(self.client.get_exchange_info)
            
            if not exchange_info or 'symbols' not in exchange_info:
                return None
            
            for symbol_info in exchange_info['symbols']:
                if symbol_info['symbol'] == symbol:
                    # Extract LOT_SIZE filter
                    lot_size_filter = None
                    for filter_info in symbol_info['filters']:
                        if filter_info['filterType'] == 'LOT_SIZE':
                            lot_size_filter = filter_info
                            break
                    
                    if not lot_size_filter:
                        continue
                    
                    return {
                        'symbol': symbol,
                        'baseAsset': symbol_info['baseAsset'],
                        'quoteAsset': symbol_info['quoteAsset'],
                        'stepSize': lot_size_filter['stepSize'],
                        'minQty': lot_size_filter['minQty'],
                        'maxQty': lot_size_filter['maxQty'],
                        'baseAssetPrecision': symbol_info['baseAssetPrecision'],
                        'quotePrecision': symbol_info['quotePrecision']
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get lot size info for {symbol}: {e}")
            return None
    
    async def place_market_buy_order(
        self, 
        symbol: str, 
        quantity: Decimal
    ) -> Optional[Dict[str, Any]]:
        """Place market buy order"""
        try:
            # Get precision info
            lot_info = await self.get_lot_size_info(symbol)
            if not lot_info:
                logger.error(f"Cannot get lot size info for {symbol}")
                return None
            
            # Format quantity to proper precision
            precision = int(lot_info['baseAssetPrecision'])
            formatted_qty = f"{quantity:.{precision}f}"
            
            logger.info(f"Placing BUY order: {symbol} quantity={formatted_qty}")
            
            order = await self._execute_with_retry(
                self.client.order_market_buy,
                symbol=symbol,
                quantity=formatted_qty
            )
            
            if order:
                logger.info(f"BUY order successful: {order.get('orderId')}")
            
            return order
            
        except BinanceOrderException as e:
            logger.error(f"Buy order failed for {symbol}: {e.message}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error placing buy order for {symbol}: {e}")
            return None
    
    async def place_market_sell_order(
        self, 
        symbol: str, 
        quantity: Decimal
    ) -> Optional[Dict[str, Any]]:
        """Place market sell order"""
        try:
            # Get precision info
            lot_info = await self.get_lot_size_info(symbol)
            if not lot_info:
                logger.error(f"Cannot get lot size info for {symbol}")
                return None
            
            # Format quantity to proper precision
            precision = int(lot_info['baseAssetPrecision'])
            formatted_qty = f"{quantity:.{precision}f}"
            
            logger.info(f"Placing SELL order: {symbol} quantity={formatted_qty}")
            
            order = await self._execute_with_retry(
                self.client.order_market_sell,
                symbol=symbol,
                quantity=formatted_qty
            )
            
            if order:
                logger.info(f"SELL order successful: {order.get('orderId')}")
            
            return order
            
        except BinanceOrderException as e:
            logger.error(f"Sell order failed for {symbol}: {e.message}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error placing sell order for {symbol}: {e}")
            return None
    
    async def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trades for symbol"""
        try:
            trades = await self._execute_with_retry(
                self.client.get_my_trades,
                symbol=symbol,
                limit=limit
            )
            
            return trades or []
            
        except Exception as e:
            logger.error(f"Failed to get recent trades for {symbol}: {e}")
            return []
    
    async def get_klines(
        self, 
        symbol: str, 
        interval: str, 
        limit: int = 100
    ) -> List[List[Any]]:
        """Get kline/candlestick data"""
        try:
            klines = await self._execute_with_retry(
                self.client.get_klines,
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            
            return klines or []
            
        except Exception as e:
            logger.error(f"Failed to get klines for {symbol}: {e}")
            return []
    
    async def test_connectivity(self) -> bool:
        """Test API connectivity and credentials"""
        try:
            # Test basic connectivity
            server_time = await self._execute_with_retry(self.client.get_server_time)
            if not server_time:
                return False
            
            # Test authenticated endpoint
            account = await self._execute_with_retry(self.client.get_account)
            if not account:
                return False
            
            logger.info("Binance API connectivity test passed")
            return True
            
        except Exception as e:
            logger.error(f"Binance connectivity test failed: {e}")
            return False


def create_binance_client() -> BinanceClient:
    """Create configured Binance client instance"""
    return BinanceClient(
        api_key=settings.binance.api_key,
        api_secret=settings.binance.api_secret,
        testnet=settings.binance.testnet
    )