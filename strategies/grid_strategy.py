# strategies/grid_strategy.py
"""
Grid Trading Strategy - Profits from sideways market movements.
Places buy/sell orders at fixed intervals to capture price oscillations.
"""
from decimal import Decimal
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import numpy as np

from strategies.base_strategy import (
    BaseStrategy, StrategyConfig, TradingSignal,
    SignalType, SignalStrength, IMarketDataService
)


@dataclass
class GridConfig(StrategyConfig):
    """Configuration for Grid Trading strategy"""

    # Grid parameters
    grid_size: int = 5  # Number of grid levels
    grid_spacing: Decimal = Decimal('0.01')  # 1% spacing between levels

    # Position sizing
    position_per_grid: Decimal = Decimal('20')  # USDT per grid level

    # Grid bounds (auto-calculated if not set)
    upper_bound: Optional[Decimal] = None
    lower_bound: Optional[Decimal] = None

    # Risk management
    max_drawdown: Decimal = Decimal('0.15')  # 15% max drawdown
    rebalance_threshold: Decimal = Decimal(
        '0.05')  # 5% price move to rebalance

    # Market condition filters
    volatility_threshold: Decimal = Decimal(
        '0.02')  # Min 2% volatility for activation
    trend_filter_period: int = 50  # Period for trend detection
    max_trend_strength: Decimal = Decimal(
        '0.03')  # Max 3% trend to stay active

    def __post_init__(self):
        """Validate grid configuration"""
        if self.grid_size < 3:
            raise ValueError("Grid size must be at least 3")
        if self.grid_spacing <= 0:
            raise ValueError("Grid spacing must be positive")
        if self.position_per_grid <= 0:
            raise ValueError("Position per grid must be positive")

        self.min_history_required = max(self.trend_filter_period, 50)


@dataclass
class GridLevel:
    """Individual grid level"""
    price: Decimal
    is_filled: bool = False
    order_id: Optional[str] = None
    quantity: Decimal = Decimal('0')


class GridTradingStrategy(BaseStrategy):
    """
    Grid Trading Strategy Implementation.

    How it works:
    1. Creates grid of buy/sell levels around current price
    2. Places buy orders below current price, sell orders above
    3. When price hits a level, executes trade and places opposite order
    4. Profits from price oscillations in sideways markets
    """

    def __init__(self, config: GridConfig, market_data_service: Optional[IMarketDataService] = None):
        super().__init__(config, market_data_service)
        self.config: GridConfig = config

        # Grid state
        self.grid_levels: List[GridLevel] = []
        self.grid_center: Optional[Decimal] = None
        self.is_grid_active = False

        # Performance tracking
        self.total_grid_profit = Decimal('0')
        self.completed_cycles = 0
        self.max_drawdown_seen = Decimal('0')

        # Market analysis
        self.volatility_buffer = []
        self.trend_buffer = []

        if not self.validate_config():
            raise ValueError("Invalid grid strategy configuration")

    def get_required_history(self) -> int:
        """Return minimum history required"""
        return self.config.min_history_required

    async def analyze(self, current_price: Decimal) -> TradingSignal:
        """
        Analyze market and return grid trading signal.
        Grid strategy works differently - it manages multiple levels.
        """
        if not self.has_sufficient_history():
            return TradingSignal(
                signal=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                price=current_price,
                reason="Insufficient price history for grid analysis",
                confidence=0.0
            )

        # Update market analysis
        self._update_market_analysis(current_price)

        # Check if market conditions are suitable for grid trading
        market_check = self._check_market_conditions(current_price)
        if not market_check['suitable']:
            return TradingSignal(
                signal=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                price=current_price,
                reason=f"Market not suitable for grid: {market_check['reason']}",
                confidence=0.0
            )

        # Initialize grid if not active
        if not self.is_grid_active:
            self._initialize_grid(current_price)
            return TradingSignal(
                signal=SignalType.HOLD,
                strength=SignalStrength.MEDIUM,
                price=current_price,
                reason="Grid initialized, waiting for price movement",
                confidence=0.7,
                indicators={'grid_levels': len(self.grid_levels)}
            )

        # Check for grid triggers
        grid_signal = self._check_grid_triggers(current_price)

        # Check if grid needs rebalancing
        if self._needs_rebalancing(current_price):
            self._rebalance_grid(current_price)

        return grid_signal

    def _update_market_analysis(self, current_price: Decimal):
        """Update volatility and trend analysis"""
        if len(self.price_history) < 2:
            return

        # Calculate volatility (rolling standard deviation)
        if len(self.price_history) >= 20:
            recent_prices = np.array([float(p)
                                     for p in self.price_history[-20:]])
            returns = np.diff(recent_prices) / recent_prices[:-1]
            volatility = np.std(returns)

            self.volatility_buffer.append(volatility)
            if len(self.volatility_buffer) > 10:
                self.volatility_buffer.pop(0)

        # Calculate trend strength
        if len(self.price_history) >= self.config.trend_filter_period:
            trend_period = self.config.trend_filter_period
            start_price = self.price_history[-trend_period]
            end_price = current_price
            trend_strength = (end_price - start_price) / start_price

            self.trend_buffer.append(abs(trend_strength))
            if len(self.trend_buffer) > 5:
                self.trend_buffer.pop(0)

    def _check_market_conditions(self, current_price: Decimal) -> Dict[str, Any]:
        """Check if market conditions are suitable for grid trading"""

        # Check volatility
        if self.volatility_buffer:
            avg_volatility = sum(self.volatility_buffer) / \
                len(self.volatility_buffer)
            if avg_volatility < float(self.config.volatility_threshold):
                return {
                    'suitable': False,
                    'reason': f"Low volatility ({avg_volatility:.3f} < {self.config.volatility_threshold})"
                }

        # Check trend strength
        if self.trend_buffer:
            avg_trend = sum(self.trend_buffer) / len(self.trend_buffer)
            if avg_trend > float(self.config.max_trend_strength):
                return {
                    'suitable': False,
                    'reason': f"Strong trend detected ({avg_trend:.3f} > {self.config.max_trend_strength})"
                }

        return {'suitable': True, 'reason': 'Market conditions favorable for grid trading'}

    def _initialize_grid(self, current_price: Decimal):
        """Initialize grid levels around current price"""
        self.grid_center = current_price
        self.grid_levels = []

        # Calculate grid bounds if not set
        if not self.config.upper_bound or not self.config.lower_bound:
            price_range = current_price * self.config.grid_spacing * self.config.grid_size
            self.config.upper_bound = current_price + price_range
            self.config.lower_bound = current_price - price_range

        # Create grid levels
        total_range = self.config.upper_bound - self.config.lower_bound
        level_spacing = total_range / (self.config.grid_size - 1)

        for i in range(self.config.grid_size):
            level_price = self.config.lower_bound + (level_spacing * i)
            self.grid_levels.append(GridLevel(price=level_price))

        self.is_grid_active = True
        self.logger.info(
            f"Grid initialized: {self.config.grid_size} levels "
            f"from {self.config.lower_bound:.6f} to {self.config.upper_bound:.6f}"
        )

    def _check_grid_triggers(self, current_price: Decimal) -> TradingSignal:
        """Check if current price triggers any grid level"""

        for i, level in enumerate(self.grid_levels):
            price_diff = abs(current_price - level.price)
            trigger_threshold = level.price * \
                Decimal('0.001')  # 0.1% threshold

            if price_diff <= trigger_threshold and not level.is_filled:
                # Determine if this should be a buy or sell
                if current_price <= self.grid_center:
                    # Below center - this is a buy level
                    return TradingSignal(
                        signal=SignalType.BUY,
                        strength=SignalStrength.STRONG,
                        price=current_price,
                        reason=f"Grid buy trigger at level {i+1}/{self.config.grid_size}",
                        confidence=0.9,
                        indicators={
                            'grid_level': i,
                            'grid_price': float(level.price),
                            'grid_type': 'buy'
                        }
                    )
                else:
                    # Above center - this is a sell level (if we have position)
                    return TradingSignal(
                        signal=SignalType.SELL,
                        strength=SignalStrength.STRONG,
                        price=current_price,
                        reason=f"Grid sell trigger at level {i+1}/{self.config.grid_size}",
                        confidence=0.9,
                        indicators={
                            'grid_level': i,
                            'grid_price': float(level.price),
                            'grid_type': 'sell'
                        }
                    )

        return TradingSignal(
            signal=SignalType.HOLD,
            strength=SignalStrength.WEAK,
            price=current_price,
            reason="No grid levels triggered",
            confidence=0.5,
            indicators={'active_grid_levels': len(
                [l for l in self.grid_levels if not l.is_filled])}
        )

    def _needs_rebalancing(self, current_price: Decimal) -> bool:
        """Check if grid needs rebalancing due to price movement"""
        if not self.grid_center:
            return False

        center_deviation = abs(
            current_price - self.grid_center) / self.grid_center
        return center_deviation > self.config.rebalance_threshold

    def _rebalance_grid(self, current_price: Decimal):
        """Rebalance grid around new price center"""
        self.logger.info(
            f"Rebalancing grid around new center: {current_price:.6f}")

        # Save performance stats
        old_center = self.grid_center
        if old_center:
            move_distance = abs(current_price - old_center) / old_center
            if move_distance > self.config.rebalance_threshold:
                self.completed_cycles += 1

        # Reset and reinitialize
        self.is_grid_active = False
        self._initialize_grid(current_price)

    def mark_level_filled(self, level_index: int, order_id: str, quantity: Decimal):
        """Mark a grid level as filled after order execution"""
        if 0 <= level_index < len(self.grid_levels):
            self.grid_levels[level_index].is_filled = True
            self.grid_levels[level_index].order_id = order_id
            self.grid_levels[level_index].quantity = quantity

    def mark_level_unfilled(self, level_index: int):
        """Mark a grid level as unfilled (order cancelled or reversed)"""
        if 0 <= level_index < len(self.grid_levels):
            self.grid_levels[level_index].is_filled = False
            self.grid_levels[level_index].order_id = None
            self.grid_levels[level_index].quantity = Decimal('0')

    def get_grid_status(self) -> Dict[str, Any]:
        """Get current grid status for monitoring"""
        if not self.is_grid_active:
            return {'active': False}

        filled_levels = sum(1 for level in self.grid_levels if level.is_filled)
        total_investment = sum(
            level.quantity * level.price
            for level in self.grid_levels
            if level.is_filled
        )

        return {
            'active': True,
            'center_price': float(self.grid_center) if self.grid_center else 0,
            'total_levels': len(self.grid_levels),
            'filled_levels': filled_levels,
            'completion_ratio': filled_levels / len(self.grid_levels) if self.grid_levels else 0,
            'total_investment': float(total_investment),
            'completed_cycles': self.completed_cycles,
            'total_profit': float(self.total_grid_profit),
            'upper_bound': float(self.config.upper_bound) if self.config.upper_bound else 0,
            'lower_bound': float(self.config.lower_bound) if self.config.lower_bound else 0
        }

    def validate_config(self) -> bool:
        """Validate grid-specific configuration"""
        if not super().validate_config():
            return False

        try:
            if self.config.grid_size < 3:
                raise ValueError("Grid size must be at least 3")

            if self.config.grid_spacing <= 0:
                raise ValueError("Grid spacing must be positive")

            if self.config.position_per_grid <= 0:
                raise ValueError("Position per grid must be positive")

            if self.config.max_drawdown <= 0 or self.config.max_drawdown >= 1:
                raise ValueError("Max drawdown must be between 0 and 1")

            return True

        except Exception as e:
            self.logger.error(f"Grid strategy config validation failed: {e}")
            return False
