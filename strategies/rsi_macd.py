# strategies/rsi_macd_strategy.py
"""
RSI + MACD strategy - refactored version of original trade_logic.py.
Clean, testable, and maintainable implementation.
"""
from decimal import Decimal
from typing import Dict, Any
from dataclasses import dataclass
import numpy as np

from strategies.base_strategy import (
    BaseStrategy, StrategyConfig, TradingSignal, 
    SignalType, SignalStrength, RSI, MACD, SimpleMovingAverage
)


@dataclass
class RSIMacdConfig(StrategyConfig):
    """Configuration for RSI+MACD strategy"""
    
    # RSI parameters
    use_rsi: bool = True
    rsi_period: int = 14
    rsi_oversold: Decimal = Decimal('30')
    rsi_overbought: Decimal = Decimal('70')
    
    # MACD parameters
    use_macd: bool = True
    macd_fast_period: int = 12
    macd_slow_period: int = 26
    macd_signal_period: int = 9
    use_macd_for_buy: bool = True
    use_macd_for_sell: bool = True
    
    # EMA filter
    use_ema: bool = False
    ema_period: int = 50
    ema_buy_buffer: Decimal = Decimal('0.002')  # 0.2%
    ema_sell_buffer: Decimal = Decimal('0.002')  # 0.2%
    
    def __post_init__(self):
        """Calculate minimum history required"""
        min_required = max(
            self.rsi_period + 1 if self.use_rsi else 0,
            self.macd_slow_period + self.macd_signal_period if self.use_macd else 0,
            self.ema_period if self.use_ema else 0
        )
        self.min_history_required = max(min_required, 50)


class RSIMacdStrategy(BaseStrategy):
    """
    RSI + MACD combination strategy.
    Clean refactor of original scattered logic.
    """
    
    def __init__(self, config: RSIMacdConfig):
        super().__init__(config)
        self.config: RSIMacdConfig = config
        
        # Validate configuration
        if not self.validate_config():
            raise ValueError("Invalid strategy configuration")
    
    def get_required_history(self) -> int:
        """Return minimum history required for this strategy"""
        return self.config.min_history_required
    
    async def analyze(self, current_price: Decimal) -> TradingSignal:
        """
        Main analysis method - replaces check_buy_sell_signals from original code.
        Returns trading signal based on RSI, MACD, and EMA conditions.
        """
        if not self.has_sufficient_history():
            return TradingSignal(
                signal=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                price=current_price,
                reason="Insufficient price history for analysis",
                confidence=0.0
            )
        
        # Get price array for calculations
        prices = self.get_price_array()
        
        # Calculate indicators
        indicators = self._calculate_indicators(prices)
        
        # Determine signal based on strategy logic
        signal_info = self._evaluate_signals(current_price, indicators)
        
        return TradingSignal(
            signal=signal_info['signal'],
            strength=signal_info['strength'],
            price=current_price,
            reason=signal_info['reason'],
            confidence=signal_info['confidence'],
            indicators=indicators
        )
    
    def _calculate_indicators(self, prices: np.ndarray) -> Dict[str, Any]:
        """Calculate all required indicators"""
        indicators = {}
        
        # RSI calculation
        if self.config.use_rsi:
            rsi_values = RSI.calculate(prices, self.config.rsi_period)
            indicators['rsi'] = {
                'values': rsi_values,
                'current': float(rsi_values[-1]) if len(rsi_values) > 0 else None,
                'oversold_threshold': float(self.config.rsi_oversold),
                'overbought_threshold': float(self.config.rsi_overbought)
            }
        
        # MACD calculation
        if self.config.use_macd:
            macd_line, signal_line, histogram = MACD.calculate(
                prices,
                self.config.macd_fast_period,
                self.config.macd_slow_period,
                self.config.macd_signal_period
            )
            
            indicators['macd'] = {
                'macd_line': macd_line,
                'signal_line': signal_line,
                'histogram': histogram,
                'current_macd': float(macd_line[-1]) if len(macd_line) > 0 else None,
                'current_signal': float(signal_line[-1]) if len(signal_line) > 0 else None,
                'current_histogram': float(histogram[-1]) if len(histogram) > 0 else None
            }
        
        # EMA calculation
        if self.config.use_ema:
            ema_values = SimpleMovingAverage.calculate(prices, self.config.ema_period)
            indicators['ema'] = {
                'values': ema_values,
                'current': float(ema_values[-1]) if len(ema_values) > 0 else None,
                'buy_buffer': float(self.config.ema_buy_buffer),
                'sell_buffer': float(self.config.ema_sell_buffer)
            }
        
        return indicators
    
    def _evaluate_signals(self, current_price: Decimal, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate trading signals based on indicators.
        Replaces the complex conditional logic from original code.
        """
        buy_signals = []
        sell_signals = []
        confidence_factors = []
        
        # RSI signals
        if self.config.use_rsi and indicators.get('rsi', {}).get('current') is not None:
            rsi_current = indicators['rsi']['current']
            
            if rsi_current < indicators['rsi']['oversold_threshold']:
                buy_signals.append("RSI oversold")
                confidence_factors.append(0.7)
            elif rsi_current > indicators['rsi']['overbought_threshold']:
                sell_signals.append("RSI overbought")
                confidence_factors.append(0.7)
        
        # MACD signals
        if self.config.use_macd and indicators.get('macd', {}).get('current_macd') is not None:
            macd_data = indicators['macd']
            current_macd = macd_data['current_macd']
            current_signal = macd_data['current_signal']
            
            # MACD line above signal line = bullish
            if current_macd > current_signal:
                if self.config.use_macd_for_buy:
                    buy_signals.append("MACD bullish crossover")
                    confidence_factors.append(0.6)
            # MACD line below signal line = bearish
            elif current_macd < current_signal:
                if self.config.use_macd_for_sell:
                    sell_signals.append("MACD bearish crossover")
                    confidence_factors.append(0.6)
        
        # EMA filter
        ema_blocks_buy = False
        ema_blocks_sell = False
        
        if self.config.use_ema and indicators.get('ema', {}).get('current') is not None:
            ema_current = indicators['ema']['current']
            ema_buy_threshold = ema_current * (1 - indicators['ema']['buy_buffer'])
            ema_sell_threshold = ema_current * (1 + indicators['ema']['sell_buffer'])
            
            # EMA filter logic
            if float(current_price) < ema_buy_threshold:
                ema_blocks_buy = True
            if float(current_price) > ema_sell_threshold:
                ema_blocks_sell = True
        
        # Determine final signal
        signal_type = SignalType.HOLD
        reason_parts = []
        final_confidence = 0.0
        
        # Buy logic
        if buy_signals and not ema_blocks_buy:
            # Require RSI signal for buy
            if self.config.use_rsi and "RSI oversold" in buy_signals:
                if not self.config.use_macd_for_buy or "MACD bullish crossover" in buy_signals:
                    signal_type = SignalType.BUY
                    reason_parts = buy_signals
        
        # Sell logic
        elif sell_signals and not ema_blocks_sell:
            # Require RSI signal for sell
            if self.config.use_rsi and "RSI overbought" in sell_signals:
                if not self.config.use_macd_for_sell or "MACD bearish crossover" in sell_signals:
                    signal_type = SignalType.SELL
                    reason_parts = sell_signals
        
        # Calculate confidence and strength
        if confidence_factors:
            final_confidence = min(sum(confidence_factors) / len(confidence_factors), 1.0)
        
        if signal_type != SignalType.HOLD:
            if final_confidence >= 0.8:
                strength = SignalStrength.STRONG
            elif final_confidence >= 0.6:
                strength = SignalStrength.MEDIUM
            else:
                strength = SignalStrength.WEAK
        else:
            strength = SignalStrength.WEAK
        
        # Build reason string
        if reason_parts:
            reason = " + ".join(reason_parts)
        elif ema_blocks_buy and buy_signals:
            reason = f"EMA filter blocked buy: {', '.join(buy_signals)}"
        elif ema_blocks_sell and sell_signals:
            reason = f"EMA filter blocked sell: {', '.join(sell_signals)}"
        else:
            reason = "No clear signal from indicators"
        
        return {
            'signal': signal_type,
            'strength': strength,
            'reason': reason,
            'confidence': final_confidence
        }
    
    def validate_config(self) -> bool:
        """Validate strategy-specific configuration"""
        if not super().validate_config():
            return False
        
        try:
            # RSI validation
            if self.config.use_rsi:
                if self.config.rsi_period < 1:
                    raise ValueError("RSI period must be positive")
                if not (0 < self.config.rsi_oversold < self.config.rsi_overbought < 100):
                    raise ValueError("Invalid RSI thresholds")
            
            # MACD validation
            if self.config.use_macd:
                if self.config.macd_fast_period >= self.config.macd_slow_period:
                    raise ValueError("MACD fast period must be less than slow period")
                if self.config.macd_signal_period < 1:
                    raise ValueError("MACD signal period must be positive")
            
            # EMA validation
            if self.config.use_ema:
                if self.config.ema_period < 1:
                    raise ValueError("EMA period must be positive")
                if self.config.ema_buy_buffer < 0 or self.config.ema_sell_buffer < 0:
                    raise ValueError("EMA buffers must be non-negative")
            
            # At least one indicator must be enabled
            if not (self.config.use_rsi or self.config.use_macd):
                raise ValueError("At least RSI or MACD must be enabled")
            
            return True
            
        except Exception as e:
            self.logger.error(f"RSI+MACD config validation failed: {e}")
            return False