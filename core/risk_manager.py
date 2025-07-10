# core/risk_manager.py
"""
Centralized risk management replacing scattered profit/loss checks.
All trading safety logic consolidated here.
"""
from decimal import Decimal
from typing import Optional, Dict, Any, NamedTuple
from dataclasses import dataclass
from enum import Enum
import logging

from core.position_manager import position_manager, PositionData
from utils.logger import get_trading_logger

logger = get_trading_logger()


class RiskDecision(Enum):
    """Risk check results"""
    ALLOW = "allow"
    BLOCK_STOP_LOSS = "block_stop_loss"
    BLOCK_TAKE_PROFIT = "block_take_profit"
    BLOCK_MIN_PROFIT = "block_min_profit"
    BLOCK_POSITION_SIZE = "block_position_size"
    BLOCK_INSUFFICIENT_BALANCE = "block_insufficient_balance"
    BLOCK_POSITION_EXISTS = "block_position_exists"
    BLOCK_NO_POSITION = "block_no_position"


@dataclass
class RiskConfig:
    """Risk management configuration per profile"""
    # Stop loss settings
    use_stop_loss: bool = True
    stop_loss_ratio: Decimal = Decimal('-0.02')  # -2%
    
    # Take profit settings
    use_take_profit: bool = True
    take_profit_ratio: Decimal = Decimal('0.05')  # 5%
    
    # Minimum profit settings
    use_min_profit: bool = True
    min_profit_ratio: Decimal = Decimal('0.01')  # 1%
    
    # Position sizing
    max_position_size: Decimal = Decimal('100')  # Max USDT per trade
    min_trade_amount: Decimal = Decimal('10')    # Min USDT per trade
    
    # Additional safety
    allow_loss_sells: bool = False  # Allow selling at loss without stop-loss trigger


class RiskCheckResult(NamedTuple):
    """Result of risk validation"""
    decision: RiskDecision
    message: str
    current_pnl: Optional[Decimal] = None
    risk_ratio: Optional[Decimal] = None


class RiskManager:
    """
    Centralized risk management for all trading operations.
    Replaces fragmented risk checks from original codebase.
    """
    
    def __init__(self):
        self.logger = logger
    
    async def validate_buy_order(
        self, 
        symbol: str, 
        quantity: Decimal, 
        price: Decimal,
        available_balance: Decimal,
        config: RiskConfig
    ) -> RiskCheckResult:
        """
        Validate BUY order before execution.
        Checks: position existence, balance, position size limits.
        """
        # Check if position already exists
        if await position_manager.has_position(symbol):
            return RiskCheckResult(
                RiskDecision.BLOCK_POSITION_EXISTS,
                f"Position already exists for {symbol}. Cannot buy again."
            )
        
        # Calculate total cost
        total_cost = quantity * price
        
        # Check minimum trade amount
        if total_cost < config.min_trade_amount:
            return RiskCheckResult(
                RiskDecision.BLOCK_POSITION_SIZE,
                f"Trade amount {total_cost} below minimum {config.min_trade_amount}"
            )
        
        # Check maximum position size
        if total_cost > config.max_position_size:
            return RiskCheckResult(
                RiskDecision.BLOCK_POSITION_SIZE,
                f"Trade amount {total_cost} exceeds maximum {config.max_position_size}"
            )
        
        # Check available balance
        if total_cost > available_balance:
            return RiskCheckResult(
                RiskDecision.BLOCK_INSUFFICIENT_BALANCE,
                f"Insufficient balance. Need {total_cost}, have {available_balance}"
            )
        
        self.logger.info(
            f"BUY validation passed: {symbol} quantity={quantity} "
            f"price={price} cost={total_cost}"
        )
        
        return RiskCheckResult(
            RiskDecision.ALLOW,
            f"BUY order validated: {symbol} @ {price}"
        )
    
    async def validate_sell_order(
        self, 
        symbol: str, 
        current_price: Decimal,
        config: RiskConfig,
        force_sell: bool = False
    ) -> RiskCheckResult:
        """
        Validate SELL order before execution.
        Checks: position existence, profit/loss conditions, risk thresholds.
        """
        # Check if position exists
        position = await position_manager.get_position(symbol)
        if not position:
            return RiskCheckResult(
                RiskDecision.BLOCK_NO_POSITION,
                f"No position exists for {symbol}. Cannot sell."
            )
        
        # Calculate current P&L
        pnl = await position_manager.get_unrealized_pnl(symbol, current_price)
        if pnl is None:
            return RiskCheckResult(
                RiskDecision.BLOCK_NO_POSITION,
                f"Unable to calculate P&L for {symbol}"
            )
        
        # Calculate price change ratio
        price_change_ratio = (current_price - position.buy_price) / position.buy_price
        
        # If force_sell is True (manual override), allow with warning
        if force_sell:
            self.logger.warning(
                f"FORCE SELL activated for {symbol}. "
                f"P&L: {pnl:.8f}, Ratio: {price_change_ratio:.4f}"
            )
            return RiskCheckResult(
                RiskDecision.ALLOW,
                f"Force sell: {symbol} @ {current_price} (P&L: {pnl:.8f})",
                current_pnl=pnl,
                risk_ratio=price_change_ratio
            )
        
        # Check stop-loss trigger
        if config.use_stop_loss:
            if price_change_ratio <= config.stop_loss_ratio:
                self.logger.warning(
                    f"STOP LOSS triggered for {symbol}: "
                    f"current={current_price}, buy={position.buy_price}, "
                    f"ratio={price_change_ratio:.4f}, threshold={config.stop_loss_ratio}"
                )
                return RiskCheckResult(
                    RiskDecision.BLOCK_STOP_LOSS,
                    f"Stop-loss triggered: {symbol} @ {current_price}",
                    current_pnl=pnl,
                    risk_ratio=price_change_ratio
                )
        
        # Check take-profit trigger
        if config.use_take_profit:
            if price_change_ratio >= config.take_profit_ratio:
                self.logger.info(
                    f"TAKE PROFIT triggered for {symbol}: "
                    f"current={current_price}, buy={position.buy_price}, "
                    f"ratio={price_change_ratio:.4f}, threshold={config.take_profit_ratio}"
                )
                return RiskCheckResult(
                    RiskDecision.BLOCK_TAKE_PROFIT,
                    f"Take-profit triggered: {symbol} @ {current_price}",
                    current_pnl=pnl,
                    risk_ratio=price_change_ratio
                )
        
        # Check minimum profit requirement
        if config.use_min_profit:
            if price_change_ratio >= config.min_profit_ratio:
                self.logger.info(
                    f"MINIMUM PROFIT achieved for {symbol}: "
                    f"current={current_price}, buy={position.buy_price}, "
                    f"ratio={price_change_ratio:.4f}, threshold={config.min_profit_ratio}"
                )
                return RiskCheckResult(
                    RiskDecision.BLOCK_MIN_PROFIT,
                    f"Minimum profit achieved: {symbol} @ {current_price}",
                    current_pnl=pnl,
                    risk_ratio=price_change_ratio
                )
        
        # Block sell at loss unless explicitly allowed
        if price_change_ratio < 0 and not config.allow_loss_sells:
            self.logger.info(
                f"SELL BLOCKED - Loss protection: {symbol} "
                f"current={current_price}, buy={position.buy_price}, "
                f"loss={price_change_ratio:.4f}"
            )
            return RiskCheckResult(
                RiskDecision.ALLOW,  # Allow but with warning
                f"Sell at loss blocked (protection): {symbol} @ {current_price}",
                current_pnl=pnl,
                risk_ratio=price_change_ratio
            )
        
        # Default: allow sell
        self.logger.info(
            f"SELL validation passed: {symbol} @ {current_price} "
            f"P&L: {pnl:.8f}, ratio: {price_change_ratio:.4f}"
        )
        
        return RiskCheckResult(
            RiskDecision.ALLOW,
            f"Sell order validated: {symbol} @ {current_price}",
            current_pnl=pnl,
            risk_ratio=price_change_ratio
        )
    
    def should_trigger_stop_loss(
        self, 
        buy_price: Decimal, 
        current_price: Decimal, 
        config: RiskConfig
    ) -> bool:
        """Check if stop-loss should trigger"""
        if not config.use_stop_loss:
            return False
        
        price_change_ratio = (current_price - buy_price) / buy_price
        return price_change_ratio <= config.stop_loss_ratio
    
    def should_trigger_take_profit(
        self, 
        buy_price: Decimal, 
        current_price: Decimal, 
        config: RiskConfig
    ) -> bool:
        """Check if take-profit should trigger"""
        if not config.use_take_profit:
            return False
        
        price_change_ratio = (current_price - buy_price) / buy_price
        return price_change_ratio >= config.take_profit_ratio
    
    def has_min_profit(
        self, 
        buy_price: Decimal, 
        current_price: Decimal, 
        config: RiskConfig
    ) -> bool:
        """Check if minimum profit is achieved"""
        if not config.use_min_profit:
            return True
        
        price_change_ratio = (current_price - buy_price) / buy_price
        return price_change_ratio >= config.min_profit_ratio
    
    async def get_position_summary(self, symbol: str, current_price: Decimal) -> Dict[str, Any]:
        """Get complete position risk summary"""
        position = await position_manager.get_position(symbol)
        if not position:
            return {"error": "No position found"}
        
        pnl = await position_manager.get_unrealized_pnl(symbol, current_price)
        price_change_ratio = (current_price - position.buy_price) / position.buy_price
        
        return {
            "symbol": symbol,
            "buy_price": float(position.buy_price),
            "current_price": float(current_price),
            "quantity": float(position.quantity),
            "unrealized_pnl": float(pnl) if pnl else 0,
            "price_change_ratio": float(price_change_ratio),
            "price_change_percent": float(price_change_ratio * 100),
            "position_value": float(current_price * position.quantity),
            "created_at": position.created_at.isoformat()
        }


# Global instance
risk_manager = RiskManager()