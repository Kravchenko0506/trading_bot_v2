# utils/secure_binance_client.py
"""
Binance client with rate limiting and connection pooling.
"""
import asyncio
import aiohttp
from typing import Optional

from utils.rate_limiter import TokenBucket
from utils.logger import get_trading_logger

logger = get_trading_logger()


class ConnectionPool:
    def __init__(self, max_connections: int = 10):
        self.connector = aiohttp.TCPConnector(limit=max_connections)
        self.session: Optional[aiohttp.ClientSession] = None

    async def get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(connector=self.connector)
        return self.session

    async def close(self):
        if self.session:
            await self.session.close()


class SecureBinanceClient:
    def __init__(self):
        self.rate_limiter = TokenBucket(rate=20, burst=50)
        self.connection_pool = ConnectionPool(max_connections=10)

    async def make_request(self, endpoint: str, max_retries: int = 3):
        await self.rate_limiter.acquire()

        for attempt in range(max_retries):
            try:
                session = await self.connection_pool.get_session()
                async with session.get(endpoint) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.warning(
                            f"Request failed with status {response.status}")

            except Exception as e:
                logger.error(f"Request attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

        raise Exception("Max retries exceeded")

    async def close(self):
        await self.connection_pool.close()
