# utils/rate_limiter.py
"""
Token bucket rate limiter.
"""
import asyncio
import time


class TokenBucket:
    """Simple token bucket rate limiter"""

    def __init__(self, rate: float, burst: int):
        self.rate = rate  # tokens per second
        self.burst = burst  # max tokens
        self.tokens = burst
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """Acquire tokens, blocking if necessary"""
        async with self._lock:
            await self._refill()

            while self.tokens < tokens:
                await asyncio.sleep(1.0 / self.rate)
                await self._refill()

            self.tokens -= tokens
            return True

    async def _refill(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.rate

        self.tokens = min(self.burst, self.tokens + tokens_to_add)
        self.last_refill = now
