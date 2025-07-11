"""
Base class for all technical indicators - TradingView style modular system
"""
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Any, List
from enum import Enum
import numpy as np


class SignalType(Enum):
    """Trading signal types"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class BaseIndicator(ABC):
    """Base class for all technical indicators"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
        self.validate_config()

    @abstractmethod
    def validate_config(self) -> None:
        """Validate indicator configuration"""
        pass

    @abstractmethod
    async def calculate(self, prices: List[Decimal]) -> Dict[str, Any]:
        """Calculate indicator values"""
        pass

    @abstractmethod
    def get_signal(self, indicator_data: Dict[str, Any], current_price: Decimal) -> SignalType:
        """Generate trading signal from indicator data"""
        pass

    @abstractmethod
    def get_required_history_length(self) -> int:
        """Return minimum price history required"""
        pass

    def to_numpy(self, prices: List[Decimal]) -> np.ndarray:
        """Convert Decimal prices to numpy array"""
        return np.array([float(p) for p in prices])

    def get_config_summary(self) -> str:
        """Get human-readable config summary"""
        return f"{self.name}({', '.join(f'{k}={v}' for k, v in self.config.items())})"
