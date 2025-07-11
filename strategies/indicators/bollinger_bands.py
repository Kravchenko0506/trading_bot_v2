from decimal import Decimal
from typing import Dict, Any, List
import numpy as np
from .base_indicator import BaseIndicator, SignalType


class BollingerBands(BaseIndicator):
    """Bollinger Bands indicator"""

    def validate_config(self) -> None:
        required = ['period', 'std_multiplier']
        for key in required:
            if key not in self.config:
                raise ValueError(f"BollingerBands requires {key} in config")

        # Set default squeeze threshold if not provided
        if 'squeeze_threshold_percent' not in self.config:
            # 2% default squeeze threshold
            self.config['squeeze_threshold_percent'] = 2.0

        if self.config['period'] < 2:
            raise ValueError("BollingerBands period must be >= 2")
        if self.config['std_multiplier'] <= 0:
            raise ValueError("BollingerBands std_multiplier must be positive")

    async def calculate(self, prices: List[Decimal]) -> Dict[str, Any]:
        """Calculate Bollinger Bands values"""
        if len(prices) < self.get_required_history_length():
            current_price = float(prices[-1])
            return {
                'middle_band': current_price,
                'upper_band': current_price,
                'lower_band': current_price,
                'insufficient_data': True
            }

        np_prices = self.to_numpy(prices)
        period = self.config['period']
        std_multiplier = self.config['std_multiplier']

        # Calculate Simple Moving Average (middle band)
        sma_values = []
        std_values = []

        for i in range(period - 1, len(np_prices)):
            window = np_prices[i - period + 1:i + 1]
            sma_value = np.mean(window)
            std_value = np.std(window, ddof=0)  # Population standard deviation

            sma_values.append(sma_value)
            std_values.append(std_value)

        current_sma = sma_values[-1]
        current_std = std_values[-1]
        current_price = float(prices[-1])

        # Calculate bands
        upper_band = current_sma + (std_multiplier * current_std)
        lower_band = current_sma - (std_multiplier * current_std)
        middle_band = current_sma

        # Calculate band width and position
        band_width = upper_band - lower_band
        band_width_percent = (band_width / middle_band) * 100

        # %B indicator (position within bands)
        if band_width > 0:
            percent_b = (current_price - lower_band) / band_width
        else:
            percent_b = 0.5  # Middle if no volatility

        # Squeeze detection
        squeeze_threshold = self.config['squeeze_threshold_percent']
        is_squeeze = band_width_percent < squeeze_threshold

        return {
            'upper_band': float(upper_band),
            'middle_band': float(middle_band),
            'lower_band': float(lower_band),
            'band_width': float(band_width),
            'band_width_percent': float(band_width_percent),
            'percent_b': float(percent_b),
            'std_multiplier': std_multiplier,
            'squeeze_threshold_percent': squeeze_threshold,
            'is_squeeze': is_squeeze,
            'price_above_upper': current_price > upper_band,
            'price_below_lower': current_price < lower_band,
            'price_near_upper': percent_b > 0.8,  # Within 20% of upper band
            'price_near_lower': percent_b < 0.2,  # Within 20% of lower band
            'price_in_middle': 0.4 <= percent_b <= 0.6,  # Middle 20% of bands
            'oversold': percent_b < 0.1,  # Very close to lower band
            'overbought': percent_b > 0.9,  # Very close to upper band
            'insufficient_data': False
        }

    def get_signal(self, indicator_data: Dict[str, Any], current_price: Decimal) -> SignalType:
        """Generate Bollinger Bands signal"""
        if indicator_data.get('insufficient_data'):
            return SignalType.HOLD

        # Bollinger Bands signals based on price position
        if indicator_data['oversold']:
            # Price touching lower band = potential bounce up
            return SignalType.BUY
        elif indicator_data['overbought']:
            # Price touching upper band = potential pullback
            return SignalType.SELL
        elif indicator_data['price_below_lower']:
            # Price broke below lower band = strong sell signal
            return SignalType.SELL
        elif indicator_data['price_above_upper']:
            # Price broke above upper band = strong buy signal (breakout)
            return SignalType.BUY
        else:
            # Price within bands = no clear signal
            return SignalType.HOLD

    def get_required_history_length(self) -> int:
        # Need extra data for accurate standard deviation
        return self.config['period'] + 10
