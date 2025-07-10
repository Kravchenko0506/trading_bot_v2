# core/market_data.py
"""
Real-time market data streaming with pure asyncio WebSocket client.

"""
import asyncio
import json
from decimal import Decimal
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from utils.logger import get_trading_logger

logger = get_trading_logger()


@dataclass
class KlineData:
    """Kline/candlestick data structure"""
    symbol: str
    open_time: datetime
    close_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal
    is_closed: bool  # True when kline is finalized


@dataclass
class StreamConfig:
    """WebSocket stream configuration"""
    symbol: str
    interval: str  # 1m, 5m, 1h, etc.
    base_url: str = "wss://stream.binance.com:9443/ws"
    reconnect_delay: int = 5  # seconds
    max_reconnects: int = 10
    ping_interval: int = 30  # seconds


class MarketDataStream:
    """
    Pure asyncio WebSocket client for Binance market data.
    No threading, no race conditions, clean error handling.
    """
    
    def __init__(self, config: StreamConfig):
        self.config = config
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.is_running = False
        self._reconnect_count = 0
        self._handlers: Dict[str, Callable] = {}
        
        # Build WebSocket URL
        stream_name = f"{config.symbol.lower()}@kline_{config.interval}"
        self.ws_url = f"{config.base_url}/{stream_name}"
        
        logger.info(f"Market data stream initialized: {stream_name}")
    
    def add_handler(self, event_type: str, handler: Callable):
        """Add event handler for stream data"""
        self._handlers[event_type] = handler
        logger.debug(f"Added handler for {event_type}")
    
    async def start(self) -> bool:
        """Start WebSocket stream with auto-reconnect"""
        if self.is_running:
            logger.warning("Stream already running")
            return False
        
        self.is_running = True
        self._reconnect_count = 0
        
        try:
            await self._connect_and_listen()
            return True
        except Exception as e:
            logger.error(f"Failed to start stream: {e}")
            self.is_running = False
            return False
    
    async def stop(self):
        """Stop WebSocket stream gracefully"""
        self.is_running = False
        
        if self.websocket:
            await self.websocket.close()
            logger.info("WebSocket connection closed")
    
    async def _connect_and_listen(self):
        """Main connection loop with reconnect logic"""
        while self.is_running:
            try:
                logger.info(f"Connecting to {self.ws_url}")
                
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=self.config.ping_interval,
                    ping_timeout=10,
                    close_timeout=10
                ) as websocket:
                    self.websocket = websocket
                    self._reconnect_count = 0
                    
                    logger.info(f"WebSocket connected: {self.config.symbol}")
                    
                    # Listen for messages
                    await self._listen_messages()
                    
            except ConnectionClosed:
                if self.is_running:
                    logger.warning("WebSocket connection closed, reconnecting...")
                    await self._handle_reconnect()
                else:
                    logger.info("WebSocket connection closed (requested)")
                    break
                    
            except WebSocketException as e:
                logger.error(f"WebSocket error: {e}")
                if self.is_running:
                    await self._handle_reconnect()
                else:
                    break
                    
            except Exception as e:
                logger.error(f"Error processing kline data: {e}")
    
    async def _handle_reconnect(self):
        """Handle reconnection with exponential backoff"""
        if self._reconnect_count >= self.config.max_reconnects:
            logger.error(f"Max reconnection attempts reached ({self.config.max_reconnects})")
            self.is_running = False
            return
        
        self._reconnect_count += 1
        delay = min(self.config.reconnect_delay * (2 ** (self._reconnect_count - 1)), 60)
        
        logger.info(f"Reconnecting in {delay}s (attempt {self._reconnect_count})")
        await asyncio.sleep(delay)


class PriceStreamManager:
    """
    Manager for multiple price streams with simplified interface.
    Replaces complex stream management from original codebase.
    """
    
    def __init__(self):
        self.streams: Dict[str, MarketDataStream] = {}
        self.price_callbacks: Dict[str, Callable] = {}
        
    async def subscribe_to_price(
        self, 
        symbol: str, 
        interval: str, 
        callback: Callable[[Decimal], None]
    ) -> bool:
        """
        Subscribe to price updates for symbol.
        Callback receives close price when kline closes.
        """
        stream_key = f"{symbol}_{interval}"
        
        if stream_key in self.streams:
            logger.warning(f"Already subscribed to {stream_key}")
            return False
        
        # Store callback
        self.price_callbacks[stream_key] = callback
        
        # Create stream config
        config = StreamConfig(symbol=symbol, interval=interval)
        stream = MarketDataStream(config)
        
        # Add kline handler
        async def on_kline_closed(kline: KlineData):
            """Handle closed kline - send price to callback"""
            try:
                await callback(kline.close_price)
                logger.debug(f"Price update sent: {symbol} @ {kline.close_price}")
            except Exception as e:
                logger.error(f"Error in price callback for {symbol}: {e}")
        
        stream.add_handler('kline_closed', on_kline_closed)
        
        # Start stream
        success = await stream.start()
        if success:
            self.streams[stream_key] = stream
            logger.info(f"Subscribed to price stream: {stream_key}")
            return True
        else:
            logger.error(f"Failed to start stream for {stream_key}")
            return False
    
    async def unsubscribe_from_price(self, symbol: str, interval: str):
        """Unsubscribe from price updates"""
        stream_key = f"{symbol}_{interval}"
        
        if stream_key in self.streams:
            await self.streams[stream_key].stop()
            del self.streams[stream_key]
            del self.price_callbacks[stream_key]
            logger.info(f"Unsubscribed from price stream: {stream_key}")
    
    async def stop_all_streams(self):
        """Stop all active streams"""
        for stream_key, stream in self.streams.items():
            await stream.stop()
            logger.info(f"Stopped stream: {stream_key}")
        
        self.streams.clear()
        self.price_callbacks.clear()
    
    def get_active_streams(self) -> list[str]:
        """Get list of active stream keys"""
        return list(self.streams.keys())
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all active streams"""
        health_status = {}
        
        for stream_key, stream in self.streams.items():
            # Check if stream is running and connected
            is_healthy = (
                stream.is_running and 
                stream.websocket is not None and 
                not stream.websocket.closed
            )
            health_status[stream_key] = is_healthy
        
        return health_status


# Utility functions for easy usage
async def create_price_stream(
    symbol: str, 
    interval: str, 
    price_queue: asyncio.Queue
) -> MarketDataStream:
    """
    Create simple price stream that puts prices into queue.
    Drop-in replacement for original listen_klines function.
    """
    config = StreamConfig(symbol=symbol, interval=interval)
    stream = MarketDataStream(config)
    
    async def on_price_update(kline: KlineData):
        """Put price into queue when kline closes"""
        if kline.is_closed:
            try:
                await price_queue.put(kline.close_price)
                logger.debug(f"Price queued: {symbol} @ {kline.close_price}")
            except Exception as e:
                logger.error(f"Failed to queue price for {symbol}: {e}")
    
    stream.add_handler('kline_closed', on_price_update)
    return stream


# Global price stream manager instance
price_stream_manager = PriceStreamManager()


# Legacy compatibility function
async def listen_klines(
    symbol: str,
    interval: str,
    price_queue: asyncio.Queue,
    stop_event: Optional[asyncio.Event] = None
):
    """
    Legacy compatibility function for original codebase.
    Creates stream and manages it until stop_event is set.
    """
    stream = await create_price_stream(symbol, interval, price_queue)
    
    try:
        # Start stream
        await stream.start()
        
        # Wait for stop event if provided
        if stop_event:
            while not stop_event.is_set():
                await asyncio.sleep(0.1)
        else:
            # Run forever
            while stream.is_running:
                await asyncio.sleep(1)
    
    finally:
        await stream.stop()
        logger.info(f"Stream stopped for {symbol}")
    
    async def _listen_messages(self):
        """Listen for WebSocket messages"""
        async for message in self.websocket:
            try:
                if not self.is_running:
                    break
                
                data = json.loads(message)
                await self._process_message(data)
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {e}")
                continue
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                continue
    
    async def _process_message(self, data: Dict[str, Any]):
        """Process incoming WebSocket message"""
        try:
            # Binance kline data structure
            if 'e' in data and data['e'] == 'kline':
                kline_info = data['k']
                
                # Parse kline data
                kline = KlineData(
                    symbol=kline_info['s'],
                    open_time=datetime.fromtimestamp(kline_info['t'] / 1000),
                    close_time=datetime.fromtimestamp(kline_info['T'] / 1000),
                    open_price=Decimal(kline_info['o']),
                    high_price=Decimal(kline_info['h']),
                    low_price=Decimal(kline_info['l']),
                    close_price=Decimal(kline_info['c']),
                    volume=Decimal(kline_info['v']),
                    is_closed=kline_info['x']  # True when kline is finalized
                )
                
                # Call handlers
                if kline.is_closed and 'kline_closed' in self._handlers:
                    await self._handlers['kline_closed'](kline)
                
                if 'kline_update' in self._handlers:
                    await self._handlers['kline_update'](kline)
                
                # Log closed klines
                if kline.is_closed:
                    logger.debug(
                        f"Kline closed: {kline.symbol} @ {kline.close_price} "
                        f"({kline.close_time.strftime('%H:%M:%S')}"
                    )
            
        except Exception as e:
            logger.error(f"Error processing kline data: {e}")