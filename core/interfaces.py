# core/interfaces.py
"""
Trading system interfaces for dependency injection.
"""
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Any, Optional


class IOrderExecutor(ABC):
    @abstractmethod
    async def execute_order(self, symbol: str, side: str, quantity: Decimal, price: Decimal) -> str:
        pass


class IRiskManager(ABC):
    @abstractmethod
    async def validate_trade(self, symbol: str, quantity: Decimal, price: Decimal) -> bool:
        pass


class IMarketData(ABC):
    @abstractmethod
    async def get_price(self, symbol: str) -> Decimal:
        pass
