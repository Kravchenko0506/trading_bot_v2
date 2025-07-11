"""
MACD (Moving Average Convergence Divergence) indicator
"""
from decimal import Decimal
from typing import Dict, Any, List
import numpy as np
from .base_indicator import BaseIndicator, SignalType


class MACD(BaseIndicator):
    """MACD (Moving Average Convergence Divergence) indicator"""

    def validate_config(self) -> None:
        required = ['fast_period', 'slow_period', 'signal_period']
        for key in required:
            if key not in self.config:
                raise ValueError(f"MACD requires {key} in config")

        if self.config['fast_period'] >= self.config['slow_period']:
            raise ValueError("MACD fast period must be less than slow period")

    async def calculate(self, prices: List[Decimal]) -> Dict[str, Any]:
        """Calculate MACD values"""
        if len(prices) < self.get_required_history_length():
            return {'macd_line': 0.0, 'signal_line': 0.0, 'histogram': 0.0, 'insufficient_data': True}

        np_prices = self.to_numpy(prices)
        fast_period = self.config['fast_period']
        slow_period = self.config['slow_period']
        signal_period = self.config['signal_period']

        # Calculate EMAs
        ema_fast = self._calculate_ema(np_prices, fast_period)
        ema_slow = self._calculate_ema(np_prices, slow_period)

        # MACD line
        macd_line = ema_fast - ema_slow

        # Signal line (EMA of MACD)
        signal_line = self._calculate_ema(macd_line, signal_period)

        # Histogram
        histogram = macd_line - signal_line

        return {
            'macd_line': float(macd_line[-1]),
            'signal_line': float(signal_line[-1]),
            'histogram': float(histogram[-1]),
            'bullish_crossover': macd_line[-1] > signal_line[-1] and macd_line[-2] <= signal_line[-2],
            'bearish_crossover': macd_line[-1] < signal_line[-1] and macd_line[-2] >= signal_line[-2],
            'bullish': macd_line[-1] > signal_line[-1],
            'bearish': macd_line[-1] < signal_line[-1],
            'insufficient_data': False
        }

    def get_signal(self, indicator_data: Dict[str, Any], current_price: Decimal) -> SignalType:
        """Generate MACD signal"""
        if indicator_data.get('insufficient_data'):
            return SignalType.HOLD

        if indicator_data['bullish_crossover']:
            return SignalType.BUY
        elif indicator_data['bearish_crossover']:
            return SignalType.SELL
        elif indicator_data['macd_line'] > indicator_data['signal_line']:
            return SignalType.BUY  # MACD above signal = bullish
        elif indicator_data['macd_line'] < indicator_data['signal_line']:
            return SignalType.SELL  # MACD below signal = bearish
        else:
            return SignalType.HOLD

    def get_required_history_length(self) -> int:
        return self.config['slow_period'] + self.config['signal_period'] + 10

    def _calculate_ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        """Calculate Exponential Moving Average"""
        alpha = 2.0 / (period + 1)
        ema = np.zeros_like(prices)
        ema[0] = prices[0]

        for i in range(1, len(prices)):
            ema[i] = alpha * prices[i] + (1 - alpha) * ema[i-1]

        return ema
