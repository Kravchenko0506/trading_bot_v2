"""
RSI (Relative Strength Index) indicator with configurable thresholds
"""
from decimal import Decimal
from typing import Dict, Any, List
import numpy as np
from .base_indicator import BaseIndicator, SignalType


class RSI(BaseIndicator):
    """Relative Strength Index indicator"""

    def validate_config(self) -> None:
        required = ['period', 'oversold_threshold', 'overbought_threshold']
        for key in required:
            if key not in self.config:
                raise ValueError(f"RSI requires {key} in config")

        if not (0 < self.config['oversold_threshold'] < self.config['overbought_threshold'] < 100):
            raise ValueError("Invalid RSI thresholds")

    async def calculate(self, prices: List[Decimal]) -> Dict[str, Any]:
        """Calculate RSI value"""
        if len(prices) < self.get_required_history_length():
            return {'value': 50.0, 'insufficient_data': True}

        np_prices = self.to_numpy(prices)
        period = self.config['period']

        # Calculate price changes
        deltas = np.diff(np_prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        # Calculate averages
        avg_gains = np.zeros_like(gains)
        avg_losses = np.zeros_like(losses)

        # Initial averages
        avg_gains[period-1] = np.mean(gains[:period])
        avg_losses[period-1] = np.mean(losses[:period])

        # Smooth the averages
        for i in range(period, len(gains)):
            avg_gains[i] = (avg_gains[i-1] * (period-1) + gains[i]) / period
            avg_losses[i] = (avg_losses[i-1] * (period-1) + losses[i]) / period

        # Calculate RSI
        rs = avg_gains / (avg_losses + 1e-10)
        rsi = 100 - (100 / (1 + rs))

        current_rsi = float(rsi[-1])

        return {
            'value': current_rsi,
            'oversold': current_rsi < self.config['oversold_threshold'],
            'overbought': current_rsi > self.config['overbought_threshold'],
            'oversold_threshold': self.config['oversold_threshold'],
            'overbought_threshold': self.config['overbought_threshold'],
            'insufficient_data': False
        }

    def get_signal(self, indicator_data: Dict[str, Any], current_price: Decimal) -> SignalType:
        """Generate RSI signal"""
        if indicator_data.get('insufficient_data'):
            return SignalType.HOLD

        if indicator_data['oversold']:
            return SignalType.BUY
        elif indicator_data['overbought']:
            return SignalType.SELL
        else:
            return SignalType.HOLD

    def get_required_history_length(self) -> int:
        return self.config['period'] + 10  # Extra buffer for smoothing
