# strategies/base_strategy.py
"""
Base strategy engine with clean interface for trading decisions.
Provides common functionality for all strategies in the modular architecture.
"""
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Any, List, Optional, Protocol
from dataclasses import dataclass
from enum import Enum
import numpy as np

from utils.logger import get_strategy_logger

logger = get_strategy_logger()


class IMarketDataService(Protocol):
    """Protocol for market data service interface"""

    async def get_current_price(self, symbol: str) -> Decimal:
        """Get current market price for symbol"""
        ...

    async def get_price_history(self, symbol: str, limit: int) -> List[Decimal]:
        """Get historical prices for symbol"""
        ...


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
    Provides clean interface and common functionality for modular architecture.
    """

    def __init__(self, config: StrategyConfig, market_data_service: Optional[IMarketDataService] = None):
        self.config = config
        self.market_data_service = market_data_service
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

    def update_price_history(self, new_prices: List[Decimal]):
        """Update price history with new data"""
        if new_prices:
            # Extend history with new prices
            self.price_history.extend(new_prices)

            # Keep only the last max_history_length prices
            if len(self.price_history) > self.max_history_length:
                self.price_history = self.price_history[-self.max_history_length:]

            logger.debug(
                f"Updated price history: {len(self.price_history)} candles")

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

    async def run(self):
        """
        Basic strategy run loop with market data integration.
        Concrete strategies can override this for custom behavior.
        """
        logger.info(f"Starting {self.name} strategy for {self.config.symbol}")

        try:
            # Get current market price if service is available
            if self.market_data_service:
                current_price = await self.market_data_service.get_current_price(self.config.symbol)
                logger.info(f"Current market price: {current_price}")
            else:
                current_price = Decimal('100000')  # Fallback for testing
                logger.warning("No market data service - using fallback price")

            # Ensure we have sufficient price history
            if not self.has_sufficient_history() and self.market_data_service:
                logger.info("Loading price history...")
                history = await self.market_data_service.get_price_history(
                    self.config.symbol,
                    self.get_required_history()
                )
                self.update_price_history(history)

            # Run analysis
            signal = await self.analyze(current_price)

            logger.info(f"Strategy analysis result: {signal.signal.value} "
                        f"(strength: {signal.strength.name}, confidence: {signal.confidence:.2f})")
            logger.info(f"Reason: {signal.reason}")

            return signal

        except Exception as e:
            logger.error(f"Error in strategy run: {e}")
            raise


# Strategy factory function (DEPRECATED - use StrategyFactory instead)
def create_strategy(strategy_name: str, config: StrategyConfig) -> BaseStrategy:
    """
    Factory function to create strategy instances.
    DEPRECATED: Use strategies.strategy_factory.StrategyFactory for modular indicator-based strategies.
    """
    logger.warning(
        "create_strategy is deprecated. Use StrategyFactory for modular strategies.")

    # Import strategies here to avoid circular imports
    if strategy_name.lower() == "grid":
        from strategies.grid_strategy import GridStrategy
        return GridStrategy(config)

    elif strategy_name.lower() == "dca":
        from strategies.dca_strategy import DCAStrategy
        return DCAStrategy(config)

    else:
        raise ValueError(
            f"Unknown strategy: {strategy_name}. Use StrategyFactory for modular strategies.")
