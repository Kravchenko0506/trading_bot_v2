"""
EMA (Exponential Moving Average) with configurable buffer zones
"""
from decimal import Decimal
from typing import Dict, Any, List
import numpy as np
from .base_indicator import BaseIndicator, SignalType


class EMA(BaseIndicator):
    """Exponential Moving Average with configurable buffer"""

    def validate_config(self) -> None:
        required = ['period']
        for key in required:
            if key not in self.config:
                raise ValueError(f"EMA requires {key} in config")

        # Set default buffers if not provided
        if 'buy_buffer_percent' not in self.config:
            self.config['buy_buffer_percent'] = 0.2  # 0.2% default
        if 'sell_buffer_percent' not in self.config:
            self.config['sell_buffer_percent'] = 0.2  # 0.2% default

        if self.config['period'] < 1:
            raise ValueError("EMA period must be positive")

    async def calculate(self, prices: List[Decimal]) -> Dict[str, Any]:
        """Calculate EMA value"""
        if len(prices) < self.get_required_history_length():
            return {'value': float(prices[-1]), 'insufficient_data': True}

        np_prices = self.to_numpy(prices)
        period = self.config['period']

        # Calculate EMA
        alpha = 2.0 / (period + 1)
        ema = np.zeros_like(np_prices)
        ema[0] = np_prices[0]

        for i in range(1, len(np_prices)):
            ema[i] = alpha * np_prices[i] + (1 - alpha) * ema[i-1]

        current_ema = float(ema[-1])
        current_price = float(prices[-1])

        # Calculate buffer zones
        buy_buffer = self.config['buy_buffer_percent'] / 100
        sell_buffer = self.config['sell_buffer_percent'] / 100

        buy_threshold = current_ema * (1 - buy_buffer)
        sell_threshold = current_ema * (1 + sell_buffer)

        return {
            'value': current_ema,
            'buy_threshold': buy_threshold,
            'sell_threshold': sell_threshold,
            'buy_buffer_percent': self.config['buy_buffer_percent'],
            'sell_buffer_percent': self.config['sell_buffer_percent'],
            'price_above_buy_threshold': current_price > buy_threshold,
            'price_below_sell_threshold': current_price < sell_threshold,
            'insufficient_data': False
        }

    def get_signal(self, indicator_data: Dict[str, Any], current_price: Decimal) -> SignalType:
        """Generate EMA filter signal"""
        if indicator_data.get('insufficient_data'):
            return SignalType.HOLD

        current_price_float = float(current_price)

        # EMA acts as a filter, not a signal generator
        # Return BUY if price is above buy threshold
        # Return SELL if price is below sell threshold
        # Return HOLD if price is in between (neutral zone)

        if current_price_float > indicator_data['buy_threshold']:
            return SignalType.BUY  # Price above EMA + buffer = bullish
        elif current_price_float < indicator_data['sell_threshold']:
            return SignalType.SELL  # Price below EMA - buffer = bearish
        else:
            return SignalType.HOLD  # Price near EMA = neutral

    def get_required_history_length(self) -> int:
        # Need enough data for EMA convergence
        return max(self.config['period'] * 2, 20)
