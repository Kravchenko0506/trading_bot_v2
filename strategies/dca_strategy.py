# strategies/dca_strategy.py
"""
DCA (Dollar Cost Averaging) Strategy - Risk reduction through position averaging.
Automatically buys more when price drops to reduce average cost basis.
"""
from decimal import Decimal
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import numpy as np

from strategies.base_strategy import (
    BaseStrategy, StrategyConfig, TradingSignal, 
    SignalType, SignalStrength
)


@dataclass
class DCAConfig(StrategyConfig):
    """Configuration for DCA Strategy"""
    
    # DCA parameters
    initial_buy_amount: Decimal = Decimal('50')  # Initial position size in USDT
    dca_amount: Decimal = Decimal('25')  # Amount to DCA each time
    max_dca_orders: int = 5  # Maximum number of DCA orders
    
    # Trigger conditions
    dca_trigger_percent: Decimal = Decimal('0.05')  # 5% drop triggers DCA
    min_time_between_dca: int = 60  # Minimum minutes between DCA orders
    
    # Exit conditions
    profit_target_percent: Decimal = Decimal('0.03')  # 3% profit target
    stop_loss_percent: Decimal = Decimal('0.15')  # 15% stop loss from average
    
    # Market condition filters
    rsi_oversold_threshold: Decimal = Decimal('40')  # Only DCA when RSI < 40
    volume_spike_threshold: Decimal = Decimal('1.5')  # 1.5x avg volume
    
    # Risk management
    max_total_investment: Decimal = Decimal('300')  # Max total investment
    emergency_exit_percent: Decimal = Decimal('0.25')  # 25% emergency exit
    
    def __post_init__(self):
        """Validate DCA configuration"""
        if self.initial_buy_amount <= 0:
            raise ValueError("Initial buy amount must be positive")
        if self.dca_amount <= 0:
            raise ValueError("DCA amount must be positive")
        if self.max_dca_orders < 1:
            raise ValueError("Max DCA orders must be at least 1")
        
        # Calculate minimum history needed
        self.min_history_required = max(50, 14)  # For RSI calculation


@dataclass
class DCAEntry:
    """Individual DCA entry record"""
    price: Decimal
    quantity: Decimal
    amount: Decimal
    timestamp: datetime
    order_type: str  # 'initial', 'dca', 'emergency'


class DCAStrategy(BaseStrategy):
    """
    Dollar Cost Averaging Strategy Implementation.
    
    How it works:
    1. Makes initial buy based on technical signals
    2. If price drops by trigger percent, makes additional DCA buy
    3. Continues DCA until max orders reached or profit target hit
    4. Sells entire position when profit target is reached
    5. Emergency exit if losses exceed threshold
    """
    
    def __init__(self, config: DCAConfig):
        super().__init__(config)
        self.config: DCAConfig = config
        
        # DCA state tracking
        self.dca_entries: List[DCAEntry] = []
        self.average_price: Optional[Decimal] = None
        self.total_quantity: Decimal = Decimal('0')
        self.total_invested: Decimal = Decimal('0')
        self.last_dca_time: Optional[datetime] = None
        
        # Performance metrics
        self.unrealized_pnl: Decimal = Decimal('0')
        self.max_drawdown: Decimal = Decimal('0')
        self.dca_count: int = 0
        
        # Market analysis buffers
        self.rsi_values = []
        self.volume_buffer = []
        
        if not self.validate_config():
            raise ValueError("Invalid DCA strategy configuration")
    
    def get_required_history(self) -> int:
        """Return minimum history required"""
        return self.config.min_history_required
    
    async def analyze(self, current_price: Decimal) -> TradingSignal:
        """
        Analyze market and return DCA trading signal.
        DCA strategy makes decisions based on position state and market conditions.
        """
        if not self.has_sufficient_history():
            return TradingSignal(
                signal=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                price=current_price,
                reason="Insufficient price history for DCA analysis",
                confidence=0.0
            )
        
        # Update market analysis
        self._update_market_analysis(current_price)
        
        # Update position metrics
        self._update_position_metrics(current_price)
        
        # Check for emergency exit conditions
        emergency_signal = self._check_emergency_exit(current_price)
        if emergency_signal:
            return emergency_signal
        
        # If no position, check for initial entry
        if not self.dca_entries:
            return self._check_initial_entry(current_price)
        
        # If we have position, check for DCA or exit signals
        dca_signal = self._check_dca_trigger(current_price)
        if dca_signal.signal != SignalType.HOLD:
            return dca_signal
        
        exit_signal = self._check_exit_conditions(current_price)
        if exit_signal.signal != SignalType.HOLD:
            return exit_signal
        
        # Default: hold position
        return TradingSignal(
            signal=SignalType.HOLD,
            strength=SignalStrength.WEAK,
            price=current_price,
            reason=f"DCA position held: {self.dca_count} entries, avg: ${self.average_price:.4f}",
            confidence=0.6,
            indicators=self._get_position_indicators(current_price)
        )
    
    def _update_market_analysis(self, current_price: Decimal):
        """Update RSI and volume analysis"""
        if len(self.price_history) < 14:
            return
        
        # Calculate RSI
        prices = np.array([float(p) for p in self.price_history[-14:]])
        if len(prices) >= 14:
            rsi = self._calculate_rsi(prices, 14)
            if len(rsi) > 0:
                self.rsi_values.append(rsi[-1])
                if len(self.rsi_values) > 10:
                    self.rsi_values.pop(0)
        
        # Volume analysis would go here if we had volume data
        # For now, simulate volume analysis
        if len(self.price_history) >= 20:
            recent_volatility = np.std([float(p) for p in self.price_history[-20:]])
            self.volume_buffer.append(recent_volatility)
            if len(self.volume_buffer) > 20:
                self.volume_buffer.pop(0)
    
    def _update_position_metrics(self, current_price: Decimal):
        """Update position metrics and P&L"""
        if not self.dca_entries:
            self.average_price = None
            self.total_quantity = Decimal('0')
            self.total_invested = Decimal('0')
            self.unrealized_pnl = Decimal('0')
            return
        
        # Calculate average price and total position
        total_cost = sum(entry.amount for entry in self.dca_entries)
        total_qty = sum(entry.quantity for entry in self.dca_entries)
        
        if total_qty > 0:
            self.average_price = total_cost / total_qty
            self.total_quantity = total_qty
            self.total_invested = total_cost
            
            # Calculate unrealized P&L
            current_value = self.total_quantity * current_price
            self.unrealized_pnl = current_value - self.total_invested
            
            # Update max drawdown
            pnl_percent = self.unrealized_pnl / self.total_invested
            if pnl_percent < self.max_drawdown:
                self.max_drawdown = pnl_percent
    
    def _check_emergency_exit(self, current_price: Decimal) -> Optional[TradingSignal]:
        """Check for emergency exit conditions"""
        if not self.dca_entries or not self.average_price:
            return None
        
        # Emergency exit if loss exceeds threshold
        loss_percent = (self.average_price - current_price) / self.average_price
        if loss_percent > self.config.emergency_exit_percent:
            return TradingSignal(
                signal=SignalType.SELL,
                strength=SignalStrength.STRONG,
                price=current_price,
                reason=f"EMERGENCY EXIT: Loss {loss_percent:.1%} exceeds {self.config.emergency_exit_percent:.1%}",
                confidence=0.95,
                indicators={'emergency_exit': True, 'loss_percent': float(loss_percent)}
            )
        
        # Emergency exit if max investment exceeded
        if self.total_invested > self.config.max_total_investment:
            return TradingSignal(
                signal=SignalType.SELL,
                strength=SignalStrength.STRONG,
                price=current_price,
                reason=f"EMERGENCY EXIT: Investment ${self.total_invested} exceeds limit ${self.config.max_total_investment}",
                confidence=0.95,
                indicators={'emergency_exit': True, 'over_investment': True}
            )
        
        return None
    
    def _check_initial_entry(self, current_price: Decimal) -> TradingSignal:
        """Check conditions for initial position entry"""
        
        # Check RSI oversold condition
        if self.rsi_values:
            current_rsi = self.rsi_values[-1]
            if current_rsi > float(self.config.rsi_oversold_threshold):
                return TradingSignal(
                    signal=SignalType.HOLD,
                    strength=SignalStrength.WEAK,
                    price=current_price,
                    reason=f"Waiting for better entry: RSI {current_rsi:.1f} > {self.config.rsi_oversold_threshold}",
                    confidence=0.3
                )
        
        # Check for volume spike (simulated)
        volume_condition = True
        if self.volume_buffer and len(self.volume_buffer) >= 10:
            avg_volume = sum(self.volume_buffer[-10:]) / 10
            current_volume = self.volume_buffer[-1]
            if current_volume < avg_volume * float(self.config.volume_spike_threshold):
                volume_condition = False
        
        if not volume_condition:
            return TradingSignal(
                signal=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                price=current_price,
                reason="Waiting for volume confirmation",
                confidence=0.4
            )
        
        # All conditions met for initial entry
        return TradingSignal(
            signal=SignalType.BUY,
            strength=SignalStrength.STRONG,
            price=current_price,
            reason=f"DCA initial entry: RSI oversold, good volume",
            confidence=0.8,
            indicators={
                'entry_type': 'initial',
                'amount': float(self.config.initial_buy_amount),
                'rsi': self.rsi_values[-1] if self.rsi_values else None
            }
        )
    
    def _check_dca_trigger(self, current_price: Decimal) -> TradingSignal:
        """Check if conditions are met for additional DCA entry"""
        
        # Check if we've reached max DCA orders
        if len(self.dca_entries) >= self.config.max_dca_orders:
            return TradingSignal(
                signal=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                price=current_price,
                reason=f"Max DCA orders reached ({self.config.max_dca_orders})",
                confidence=0.5
            )
        
        # Check time since last DCA
        if self.last_dca_time:
            time_since_last = datetime.utcnow() - self.last_dca_time
            min_time = timedelta(minutes=self.config.min_time_between_dca)
            if time_since_last < min_time:
                return TradingSignal(
                    signal=SignalType.HOLD,
                    strength=SignalStrength.WEAK,
                    price=current_price,
                    reason=f"Too soon for next DCA (wait {min_time - time_since_last})",
                    confidence=0.3
                )
        
        # Check if price has dropped enough to trigger DCA
        if not self.average_price:
            return TradingSignal(signal=SignalType.HOLD, strength=SignalStrength.WEAK, price=current_price, reason="No average price", confidence=0.0)
        
        price_drop = (self.average_price - current_price) / self.average_price
        if price_drop < self.config.dca_trigger_percent:
            return TradingSignal(
                signal=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                price=current_price,
                reason=f"Price drop {price_drop:.1%} < trigger {self.config.dca_trigger_percent:.1%}",
                confidence=0.4
            )
        
        # Check total investment limit
        projected_investment = self.total_invested + self.config.dca_amount
        if projected_investment > self.config.max_total_investment:
            return TradingSignal(
                signal=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                price=current_price,
                reason=f"DCA would exceed investment limit",
                confidence=0.2
            )
        
        # All conditions met for DCA
        return TradingSignal(
            signal=SignalType.BUY,
            strength=SignalStrength.STRONG,
            price=current_price,
            reason=f"DCA trigger: {price_drop:.1%} drop from avg ${self.average_price:.4f}",
            confidence=0.85,
            indicators={
                'entry_type': 'dca',
                'amount': float(self.config.dca_amount),
                'price_drop': float(price_drop),
                'dca_number': len(self.dca_entries) + 1
            }
        )
    
    def _check_exit_conditions(self, current_price: Decimal) -> TradingSignal:
        """Check conditions for exiting entire position"""
        
        if not self.average_price:
            return TradingSignal(signal=SignalType.HOLD, strength=SignalStrength.WEAK, price=current_price, reason="No position", confidence=0.0)
        
        # Check profit target
        profit_percent = (current_price - self.average_price) / self.average_price
        if profit_percent >= self.config.profit_target_percent:
            return TradingSignal(
                signal=SignalType.SELL,
                strength=SignalStrength.STRONG,
                price=current_price,
                reason=f"PROFIT TARGET: {profit_percent:.1%} >= {self.config.profit_target_percent:.1%}",
                confidence=0.9,
                indicators={
                    'exit_type': 'profit_target',
                    'profit_percent': float(profit_percent),
                    'total_profit': float(self.unrealized_pnl)
                }
            )
        
        # Check stop loss
        loss_percent = (self.average_price - current_price) / self.average_price
        if loss_percent >= self.config.stop_loss_percent:
            return TradingSignal(
                signal=SignalType.SELL,
                strength=SignalStrength.STRONG,
                price=current_price,
                reason=f"STOP LOSS: {loss_percent:.1%} >= {self.config.stop_loss_percent:.1%}",
                confidence=0.95,
                indicators={
                    'exit_type': 'stop_loss',
                    'loss_percent': float(loss_percent),
                    'total_loss': float(self.unrealized_pnl)
                }
            )
        
        return TradingSignal(signal=SignalType.HOLD, strength=SignalStrength.WEAK, price=current_price, reason="No exit conditions met", confidence=0.5)
    
    def add_dca_entry(self, price: Decimal, quantity: Decimal, amount: Decimal, entry_type: str = 'dca'):
        """Add new DCA entry to position"""
        entry = DCAEntry(
            price=price,
            quantity=quantity,
            amount=amount,
            timestamp=datetime.utcnow(),
            order_type=entry_type
        )
        self.dca_entries.append(entry)
        self.last_dca_time = datetime.utcnow()
        self.dca_count = len(self.dca_entries)
        
        self.logger.info(f"DCA entry added: ${amount} @ ${price:.4f} (entry #{self.dca_count})")
    
    def clear_position(self):
        """Clear all DCA entries (after sell)"""
        self.logger.info(f"DCA position cleared: {self.dca_count} entries, final P&L: ${self.unrealized_pnl:.2f}")
        
        self.dca_entries = []
        self.average_price = None
        self.total_quantity = Decimal('0')
        self.total_invested = Decimal('0')
        self.unrealized_pnl = Decimal('0')
        self.last_dca_time = None
        self.dca_count = 0
    
    def _get_position_indicators(self, current_price: Decimal) -> Dict[str, Any]:
        """Get current position indicators for signal"""
        return {
            'dca_entries': self.dca_count,
            'average_price': float(self.average_price) if self.average_price else 0,
            'total_invested': float(self.total_invested),
            'unrealized_pnl': float(self.unrealized_pnl),
            'pnl_percent': float(self.unrealized_pnl / self.total_invested) if self.total_invested > 0 else 0,
            'max_drawdown': float(self.max_drawdown),
            'current_rsi': self.rsi_values[-1] if self.rsi_values else None
        }
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate RSI indicator"""
        if len(prices) < period + 1:
            return np.array([])
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gains = np.zeros_like(gains)
        avg_losses = np.zeros_like(losses)
        
        avg_gains[period-1] = np.mean(gains[:period])
        avg_losses[period-1] = np.mean(losses[:period])
        
        for i in range(period, len(gains)):
            avg_gains[i] = (avg_gains[i-1] * (period-1) + gains[i]) / period
            avg_losses[i] = (avg_losses[i-1] * (period-1) + losses[i]) / period
        
        rs = avg_gains / (avg_losses + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi[period-1:]
    
    def validate_config(self) -> bool:
        """Validate DCA-specific configuration"""
        if not super().validate_config():
            return False
        
        try:
            if self.config.initial_buy_amount <= 0:
                raise ValueError("Initial buy amount must be positive")
            
            if self.config.dca_amount <= 0:
                raise ValueError("DCA amount must be positive")
            
            if self.config.max_dca_orders < 1:
                raise ValueError("Max DCA orders must be at least 1")
            
            if self.config.dca_trigger_percent <= 0:
                raise ValueError("DCA trigger percent must be positive")
            
            if self.config.profit_target_percent <= 0:
                raise ValueError("Profit target must be positive")
            
            return True
            
        except Exception as e:
            self.logger.error(f"DCA strategy config validation failed: {e}")
            return False