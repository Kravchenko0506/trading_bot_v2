from decimal import Decimal
from typing import Dict, Any, List
import numpy as np
from .base_indicator import BaseIndicator, SignalType


class SMA(BaseIndicator):
    """Simple Moving Average indicator"""

    def validate_config(self) -> None:
        required = ['period']
        for key in required:
            if key not in self.config:
                raise ValueError(f"SMA requires {key} in config")

        # Set default buffers if not provided
        if 'buy_buffer_percent' not in self.config:
            self.config['buy_buffer_percent'] = 0.0  # No buffer by default
        if 'sell_buffer_percent' not in self.config:
            self.config['sell_buffer_percent'] = 0.0  # No buffer by default

        if self.config['period'] < 1:
            raise ValueError("SMA period must be positive")

    async def calculate(self, prices: List[Decimal]) -> Dict[str, Any]:
        """Calculate SMA value"""
        if len(prices) < self.get_required_history_length():
            return {'value': float(prices[-1]), 'insufficient_data': True}

        np_prices = self.to_numpy(prices)
        period = self.config['period']

        # Calculate Simple Moving Average
        sma_values = []
        for i in range(period - 1, len(np_prices)):
            sma_value = np.mean(np_prices[i - period + 1:i + 1])
            sma_values.append(sma_value)

        current_sma = float(sma_values[-1])
        current_price = float(prices[-1])

        # Calculate buffer zones
        buy_buffer = self.config['buy_buffer_percent'] / 100
        sell_buffer = self.config['sell_buffer_percent'] / 100

        buy_threshold = current_sma * (1 - buy_buffer)
        sell_threshold = current_sma * (1 + sell_buffer)

        return {
            'value': current_sma,
            'buy_threshold': buy_threshold,
            'sell_threshold': sell_threshold,
            'buy_buffer_percent': self.config['buy_buffer_percent'],
            'sell_buffer_percent': self.config['sell_buffer_percent'],
            'price_above_sma': current_price > current_sma,
            'price_below_sma': current_price < current_sma,
            'price_above_buy_threshold': current_price > buy_threshold,
            'price_below_sell_threshold': current_price < sell_threshold,
            'distance_from_sma_percent': ((current_price - current_sma) / current_sma) * 100,
            'insufficient_data': False
        }

    def get_signal(self, indicator_data: Dict[str, Any], current_price: Decimal) -> SignalType:
        """Generate SMA signal"""
        if indicator_data.get('insufficient_data'):
            return SignalType.HOLD

        current_price_float = float(current_price)

        # SMA acts as support/resistance and trend filter
        if current_price_float > indicator_data['buy_threshold']:
            return SignalType.BUY  # Price above SMA + buffer = bullish
        elif current_price_float < indicator_data['sell_threshold']:
            return SignalType.SELL  # Price below SMA - buffer = bearish
        else:
            return SignalType.HOLD  # Price near SMA = neutral

    def get_required_history_length(self) -> int:
        # Need period + buffer for accurate calculation
        return self.config['period'] + 5
