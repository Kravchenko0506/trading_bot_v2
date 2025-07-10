# strategies/base_strategy.py
"""
Base strategy engine with clean interface for trading decisions.
Provides common functionality for all strategies.
"""
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Any, List, Optional, NamedTuple
from dataclasses import dataclass
from enum import Enum
import numpy as np

from utils.logger import get_strategy_logger

logger = get_strategy_logger()


class SignalType(Enum):
    """Trading signal types"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class SignalStrength(Enum):
    """Signal strength levels"""
    WEAK = 1
    MEDIUM = 2
    STRONG = 3


@dataclass
class TradingSignal:
    """Trading signal with context"""
    signal: SignalType
    strength: SignalStrength
    price: Decimal
    reason: str
    confidence: float  # 0.0 to 1.0
    indicators: Dict[str, Any] = None


@dataclass
class StrategyConfig:
    """Base strategy configuration"""
    symbol: str
    timeframe: str
    min_history_required: int = 50

    # Risk parameters
    max_position_size: Decimal = Decimal('100')
    stop_loss_pct: Decimal = Decimal('-0.02')
    take_profit_pct: Decimal = Decimal('0.05')


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    Provides clean interface and common functionality.
    """

    def __init__(self, config: StrategyConfig):
        self.config = config
        self.logger = logger
        self.name = self.__class__.__name__

        # Price history for indicators
        self.price_history: List[Decimal] = []
        self.max_history_length = 500  # Keep last 500 candles

        self.logger.info(
            f"Strategy initialized: {self.name} for {config.symbol}")

    @abstractmethod
    async def analyze(self, current_price: Decimal) -> TradingSignal:
        """
        Analyze market conditions and return trading signal.
        Must be implemented by concrete strategies.
        """
        pass

    @abstractmethod
    def get_required_history(self) -> int:
        """Return minimum price history required for analysis"""
        pass

    def add_price(self, price: Decimal):
        """Add new price to history"""
        self.price_history.append(price)

        # Maintain max history length
        if len(self.price_history) > self.max_history_length:
            self.price_history = self.price_history[-self.max_history_length:]

        self.logger.debug(
            f"Price added: {price} (history length: {len(self.price_history)})")

    def has_sufficient_history(self) -> bool:
        """Check if we have enough price history for analysis"""
        required = max(self.get_required_history(),
                       self.config.min_history_required)
        sufficient = len(self.price_history) >= required

        if not sufficient:
            self.logger.debug(
                f"Insufficient history: {len(self.price_history)}/{required}"
            )

        return sufficient

    def get_price_array(self) -> np.ndarray:
        """Get price history as numpy array for calculations"""
        return np.array([float(p) for p in self.price_history])

    async def should_buy(self, current_price: Decimal) -> TradingSignal:
        """Check if strategy suggests buying"""
        signal = await self.analyze(current_price)

        if signal.signal == SignalType.BUY:
            self.logger.info(
                f"BUY signal: {self.name} - {signal.reason} "
                f"(strength: {signal.strength.name}, confidence: {signal.confidence:.2f})"
            )

        return signal

    async def should_sell(self, current_price: Decimal) -> TradingSignal:
        """Check if strategy suggests selling"""
        signal = await self.analyze(current_price)

        if signal.signal == SignalType.SELL:
            self.logger.info(
                f"SELL signal: {self.name} - {signal.reason} "
                f"(strength: {signal.strength.name}, confidence: {signal.confidence:.2f})"
            )

        return signal

    def validate_config(self) -> bool:
        """Validate strategy configuration"""
        try:
            if not self.config.symbol:
                raise ValueError("Symbol is required")

            if not self.config.timeframe:
                raise ValueError("Timeframe is required")

            if self.config.min_history_required < 1:
                raise ValueError("Min history must be positive")

            return True

        except Exception as e:
            self.logger.error(f"Config validation failed: {e}")
            return False


class SimpleMovingAverage:
    """Helper class for SMA calculations"""

    @staticmethod
    def calculate(prices: np.ndarray, period: int) -> np.ndarray:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return np.array([])

        return np.convolve(prices, np.ones(period), 'valid') / period


class RSI:
    """Helper class for RSI calculations"""

    @staticmethod
    def calculate(prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return np.array([])

        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gains = np.zeros_like(gains)
        avg_losses = np.zeros_like(losses)

        # Initial averages
        avg_gains[period-1] = np.mean(gains[:period])
        avg_losses[period-1] = np.mean(losses[:period])

        # Smooth the averages
        for i in range(period, len(gains)):
            avg_gains[i] = (avg_gains[i-1] * (period-1) + gains[i]) / period
            avg_losses[i] = (avg_losses[i-1] * (period-1) + losses[i]) / period

        rs = avg_gains / (avg_losses + 1e-10)  # Avoid division by zero
        rsi = 100 - (100 / (1 + rs))

        return rsi[period-1:]


class MACD:
    """Helper class for MACD calculations"""

    @staticmethod
    def calculate(
        prices: np.ndarray,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calculate MACD line, signal line, and histogram"""
        if len(prices) < slow_period:
            return np.array([]), np.array([]), np.array([])

        # Calculate EMAs
        ema_fast = MACD._ema(prices, fast_period)
        ema_slow = MACD._ema(prices, slow_period)

        # MACD line
        macd_line = ema_fast - ema_slow

        # Signal line (EMA of MACD)
        signal_line = MACD._ema(macd_line, signal_period)

        # Histogram
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    @staticmethod
    def _ema(prices: np.ndarray, period: int) -> np.ndarray:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return np.array([])

        alpha = 2.0 / (period + 1)
        ema = np.zeros_like(prices)
        ema[0] = prices[0]

        for i in range(1, len(prices)):
            ema[i] = alpha * prices[i] + (1 - alpha) * ema[i-1]

        return ema


# Strategy factory function
def create_strategy(strategy_name: str, config: StrategyConfig) -> BaseStrategy:
    """Factory function to create strategy instances"""

    # Import strategies here to avoid circular imports
    if strategy_name.lower() == "rsi_macd":
        from strategies.rsi_macd import RSIMacdStrategy
        return RSIMacdStrategy(config)

    elif strategy_name.lower() == "grid":
        from strategies.grid_strategy import GridStrategy
        return GridStrategy(config)

    elif strategy_name.lower() == "dca":
        from strategies.dca_strategy import DCAStrategy
        return DCAStrategy(config)

    else:
        raise ValueError(f"Unknown strategy: {strategy_name}")
