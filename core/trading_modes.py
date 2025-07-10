# core/trading_modes.py
"""
Trading mode management system - Live vs Paper trading.
Clean separation of real and simulated trading without affecting core logic.
"""
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from utils.logger import get_trading_logger

logger = get_trading_logger()


class TradingMode(Enum):
    """Available trading modes"""
    LIVE = "live"
    PAPER = "paper"


@dataclass
class TradeResult:
    """Standardized trade result for both modes"""
    success: bool
    order_id: Optional[str]
    executed_price: Decimal
    executed_quantity: Decimal
    commission: Decimal
    message: str
    raw_response: Dict[str, Any] = None


class BaseTradingMode(ABC):
    """Abstract base for trading mode implementations"""
    
    @abstractmethod
    async def execute_buy(self, symbol: str, quantity: Decimal, price: Decimal) -> TradeResult:
        """Execute buy order in this mode"""
        pass
    
    @abstractmethod
    async def execute_sell(self, symbol: str, quantity: Decimal, price: Decimal) -> TradeResult:
        """Execute sell order in this mode"""
        pass
    
    @abstractmethod
    async def get_balance(self, asset: str) -> Decimal:
        """Get balance for asset"""
        pass
    
    @abstractmethod
    async def has_position(self, symbol: str) -> bool:
        """Check if position exists"""
        pass


class LiveTradingMode(BaseTradingMode):
    """Live trading mode using real Binance API"""
    
    def __init__(self, binance_client):
        self.client = binance_client
        self.mode = TradingMode.LIVE
        logger.info("💰 Live trading mode initialized - REAL MONEY")
    
    async def execute_buy(self, symbol: str, quantity: Decimal, price: Decimal) -> TradeResult:
        """Execute real buy order on Binance"""
        try:
            response = await self.client.place_market_buy_order(symbol, quantity)
            
            if not response or response.get('status') != 'FILLED':
                return TradeResult(
                    success=False,
                    order_id=None,
                    executed_price=Decimal('0'),
                    executed_quantity=Decimal('0'),
                    commission=Decimal('0'),
                    message=f"Buy order failed: {response}",
                    raw_response=response
                )
            
            # Extract execution details
            executed_qty = Decimal(response['executedQty'])
            avg_price = self._calculate_avg_price(response)
            commission = self._calculate_commission(response)
            
            return TradeResult(
                success=True,
                order_id=str(response.get('orderId')),
                executed_price=avg_price,
                executed_quantity=executed_qty,
                commission=commission,
                message=f"Live BUY executed: {executed_qty} {symbol} @ {avg_price}",
                raw_response=response
            )
            
        except Exception as e:
            logger.error(f"Live buy order failed: {e}")
            return TradeResult(
                success=False,
                order_id=None,
                executed_price=Decimal('0'),
                executed_quantity=Decimal('0'),
                commission=Decimal('0'),
                message=f"Buy execution error: {str(e)}"
            )
    
    async def execute_sell(self, symbol: str, quantity: Decimal, price: Decimal) -> TradeResult:
        """Execute real sell order on Binance"""
        try:
            response = await self.client.place_market_sell_order(symbol, quantity)
            
            if not response or response.get('status') != 'FILLED':
                return TradeResult(
                    success=False,
                    order_id=None,
                    executed_price=Decimal('0'),
                    executed_quantity=Decimal('0'),
                    commission=Decimal('0'),
                    message=f"Sell order failed: {response}",
                    raw_response=response
                )
            
            # Extract execution details
            executed_qty = Decimal(response['executedQty'])
            avg_price = self._calculate_avg_price(response)
            commission = self._calculate_commission(response)
            
            return TradeResult(
                success=True,
                order_id=str(response.get('orderId')),
                executed_price=avg_price,
                executed_quantity=executed_qty,
                commission=commission,
                message=f"Live SELL executed: {executed_qty} {symbol} @ {avg_price}",
                raw_response=response
            )
            
        except Exception as e:
            logger.error(f"Live sell order failed: {e}")
            return TradeResult(
                success=False,
                order_id=None,
                executed_price=Decimal('0'),
                executed_quantity=Decimal('0'),
                commission=Decimal('0'),
                message=f"Sell execution error: {str(e)}"
            )
    
    async def get_balance(self, asset: str) -> Decimal:
        """Get real balance from Binance"""
        return await self.client.get_balance(asset) or Decimal('0')
    
    async def has_position(self, symbol: str) -> bool:
        """Check real position via position manager"""
        from core.position_manager import position_manager
        return await position_manager.has_position(symbol)
    
    def _calculate_avg_price(self, response: Dict[str, Any]) -> Decimal:
        """Calculate average execution price from fills"""
        fills = response.get('fills', [])
        if not fills:
            return Decimal(response.get('price', '0'))
        
        total_qty = Decimal('0')
        total_cost = Decimal('0')
        
        for fill in fills:
            qty = Decimal(fill['qty'])
            price = Decimal(fill['price'])
            total_qty += qty
            total_cost += qty * price
        
        return total_cost / total_qty if total_qty > 0 else Decimal('0')
    
    def _calculate_commission(self, response: Dict[str, Any]) -> Decimal:
        """Calculate total commission from fills"""
        fills = response.get('fills', [])
        total_commission = Decimal('0')
        
        for fill in fills:
            total_commission += Decimal(fill.get('commission', '0'))
        
        return total_commission


class PaperTradingMode(BaseTradingMode):
    """Paper trading mode with simulated execution"""
    
    def __init__(self, initial_balance: Decimal = Decimal('1000')):
        self.mode = TradingMode.PAPER
        self.cash_balance = initial_balance
        self.positions: Dict[str, Dict[str, Decimal]] = {}  # symbol -> {quantity, avg_price}
        self.trade_history = []
        self.order_counter = 1000
        self.commission_rate = Decimal('0.001')  # 0.1%
        
        logger.info(f"📝 Paper trading mode initialized - Starting with ${initial_balance}")
    
    async def execute_buy(self, symbol: str, quantity: Decimal, price: Decimal) -> TradeResult:
        """Simulate buy order execution"""
        try:
            # Calculate costs
            cost = quantity * price
            commission = cost * self.commission_rate
            total_cost = cost + commission
            
            # Check balance
            if self.cash_balance < total_cost:
                return TradeResult(
                    success=False,
                    order_id=None,
                    executed_price=price,
                    executed_quantity=Decimal('0'),
                    commission=Decimal('0'),
                    message=f"Insufficient balance: need ${total_cost:.2f}, have ${self.cash_balance:.2f}"
                )
            
            # Execute simulated trade
            self.cash_balance -= total_cost
            
            # Update position
            if symbol in self.positions:
                # Average existing position
                existing_qty = self.positions[symbol]['quantity']
                existing_price = self.positions[symbol]['avg_price']
                
                total_qty = existing_qty + quantity
                avg_price = ((existing_price * existing_qty) + (price * quantity)) / total_qty
                
                self.positions[symbol] = {
                    'quantity': total_qty,
                    'avg_price': avg_price
                }
            else:
                # New position
                self.positions[symbol] = {
                    'quantity': quantity,
                    'avg_price': price
                }
            
            # Record trade
            self.order_counter += 1
            trade_record = {
                'order_id': str(self.order_counter),
                'symbol': symbol,
                'side': 'BUY',
                'quantity': quantity,
                'price': price,
                'commission': commission,
                'timestamp': datetime.utcnow(),
                'cash_after': self.cash_balance
            }
            self.trade_history.append(trade_record)
            
            logger.info(
                f"📝 Paper BUY: {quantity} {symbol} @ ${price} "
                f"(cost: ${total_cost:.2f}, cash left: ${self.cash_balance:.2f})"
            )
            
            return TradeResult(
                success=True,
                order_id=str(self.order_counter),
                executed_price=price,
                executed_quantity=quantity,
                commission=commission,
                message=f"Paper BUY executed: {quantity} {symbol} @ ${price}"
            )
            
        except Exception as e:
            logger.error(f"Paper buy simulation failed: {e}")
            return TradeResult(
                success=False,
                order_id=None,
                executed_price=price,
                executed_quantity=Decimal('0'),
                commission=Decimal('0'),
                message=f"Paper buy error: {str(e)}"
            )
    
    async def execute_sell(self, symbol: str, quantity: Decimal, price: Decimal) -> TradeResult:
        """Simulate sell order execution"""
        try:
            # Check position
            if symbol not in self.positions:
                return TradeResult(
                    success=False,
                    order_id=None,
                    executed_price=price,
                    executed_quantity=Decimal('0'),
                    commission=Decimal('0'),
                    message=f"No position to sell in {symbol}"
                )
            
            position = self.positions[symbol]
            if position['quantity'] < quantity:
                return TradeResult(
                    success=False,
                    order_id=None,
                    executed_price=price,
                    executed_quantity=Decimal('0'),
                    commission=Decimal('0'),
                    message=f"Insufficient quantity: need {quantity}, have {position['quantity']}"
                )
            
            # Calculate proceeds
            proceeds = quantity * price
            commission = proceeds * self.commission_rate
            net_proceeds = proceeds - commission
            
            # Calculate P&L
            buy_cost = quantity * position['avg_price']
            profit = proceeds - buy_cost - commission
            
            # Execute simulated trade
            self.cash_balance += net_proceeds
            
            # Update position
            if position['quantity'] == quantity:
                # Close entire position
                del self.positions[symbol]
            else:
                # Partial close
                position['quantity'] -= quantity
            
            # Record trade
            self.order_counter += 1
            trade_record = {
                'order_id': str(self.order_counter),
                'symbol': symbol,
                'side': 'SELL',
                'quantity': quantity,
                'price': price,
                'commission': commission,
                'profit': profit,
                'timestamp': datetime.utcnow(),
                'cash_after': self.cash_balance
            }
            self.trade_history.append(trade_record)
            
            profit_emoji = "📈" if profit > 0 else "📉"
            logger.info(
                f"📝 Paper SELL: {quantity} {symbol} @ ${price} "
                f"(profit: ${profit:.2f} {profit_emoji}, cash: ${self.cash_balance:.2f})"
            )
            
            return TradeResult(
                success=True,
                order_id=str(self.order_counter),
                executed_price=price,
                executed_quantity=quantity,
                commission=commission,
                message=f"Paper SELL executed: {quantity} {symbol} @ ${price} (P&L: ${profit:.2f})"
            )
            
        except Exception as e:
            logger.error(f"Paper sell simulation failed: {e}")
            return TradeResult(
                success=False,
                order_id=None,
                executed_price=price,
                executed_quantity=Decimal('0'),
                commission=Decimal('0'),
                message=f"Paper sell error: {str(e)}"
            )
    
    async def get_balance(self, asset: str) -> Decimal:
        """Get simulated balance"""
        if asset == 'USDT':
            return self.cash_balance
        
        # For other assets, check positions
        for symbol, position in self.positions.items():
            if symbol.startswith(asset):
                return position['quantity']
        
        return Decimal('0')
    
    async def has_position(self, symbol: str) -> bool:
        """Check if simulated position exists"""
        return symbol in self.positions
    
    def get_portfolio_summary(self, current_prices: Dict[str, Decimal]) -> Dict[str, Any]:
        """Get complete portfolio summary"""
        total_value = self.cash_balance
        unrealized_pnl = Decimal('0')
        
        position_details = []
        for symbol, pos in self.positions.items():
            current_price = current_prices.get(symbol, pos['avg_price'])
            position_value = pos['quantity'] * current_price
            position_pnl = (current_price - pos['avg_price']) * pos['quantity']
            
            total_value += position_value
            unrealized_pnl += position_pnl
            
            position_details.append({
                'symbol': symbol,
                'quantity': float(pos['quantity']),
                'avg_price': float(pos['avg_price']),
                'current_price': float(current_price),
                'value': float(position_value),
                'pnl': float(position_pnl)
            })
        
        return {
            'mode': 'paper',
            'cash_balance': float(self.cash_balance),
            'total_value': float(total_value),
            'unrealized_pnl': float(unrealized_pnl),
            'total_trades': len(self.trade_history),
            'positions': position_details
        }


class TradingModeManager:
    """Manager for switching between trading modes"""
    
    def __init__(self):
        self.current_mode: Optional[BaseTradingMode] = None
        self.mode_type: Optional[TradingMode] = None
    
    def set_live_mode(self, binance_client):
        """Switch to live trading mode"""
        self.current_mode = LiveTradingMode(binance_client)
        self.mode_type = TradingMode.LIVE
        logger.warning("🔴 LIVE TRADING MODE ACTIVE - REAL MONEY AT RISK")
    
    def set_paper_mode(self, initial_balance: Decimal = Decimal('1000')):
        """Switch to paper trading mode"""
        self.current_mode = PaperTradingMode(initial_balance)
        self.mode_type = TradingMode.PAPER
        logger.info(f"🟢 PAPER TRADING MODE ACTIVE - Safe simulation mode")
    
    def is_live_mode(self) -> bool:
        """Check if currently in live mode"""
        return self.mode_type == TradingMode.LIVE
    
    def is_paper_mode(self) -> bool:
        """Check if currently in paper mode"""
        return self.mode_type == TradingMode.PAPER
    
    async def execute_buy(self, symbol: str, quantity: Decimal, price: Decimal) -> TradeResult:
        """Execute buy in current mode"""
        if not self.current_mode:
            raise RuntimeError("No trading mode set")
        return await self.current_mode.execute_buy(symbol, quantity, price)
    
    async def execute_sell(self, symbol: str, quantity: Decimal, price: Decimal) -> TradeResult:
        """Execute sell in current mode"""
        if not self.current_mode:
            raise RuntimeError("No trading mode set")
        return await self.current_mode.execute_sell(symbol, quantity, price)
    
    async def get_balance(self, asset: str) -> Decimal:
        """Get balance in current mode"""
        if not self.current_mode:
            raise RuntimeError("No trading mode set")
        return await self.current_mode.get_balance(asset)
    
    async def has_position(self, symbol: str) -> bool:
        """Check position in current mode"""
        if not self.current_mode:
            raise RuntimeError("No trading mode set")
        return await self.current_mode.has_position(symbol)


# Global instance
trading_mode_manager = TradingModeManager()