# core/paper_trading.py
"""
Paper trading engine for safe testing without real money.
Simulates all trading operations with virtual portfolio.
"""
import asyncio
from decimal import Decimal
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid

from core.order_executor import OrderResult, OrderStatus, OrderSide
from utils.logger import get_trading_logger

logger = get_trading_logger()


@dataclass
class PaperBalance:
    """Virtual balance for paper trading"""
    asset: str
    free: Decimal = Decimal('0')
    locked: Decimal = Decimal('0')
    
    @property
    def total(self) -> Decimal:
        return self.free + self.locked


@dataclass
class PaperOrder:
    """Virtual order for paper trading"""
    order_id: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    status: str = "FILLED"
    created_at: datetime = field(default_factory=datetime.utcnow)


class PaperTradingEngine:
    """
    Simulates real trading operations without actual money.
    Perfect for testing strategies and parameters.
    """
    
    def __init__(self, initial_usdt: Decimal = Decimal('1000')):
        self.balances: Dict[str, PaperBalance] = {
            'USDT': PaperBalance('USDT', free=initial_usdt)
        }
        self.orders: list[PaperOrder] = []
        self.trade_count = 0
        self.total_fees = Decimal('0')
        self.fee_rate = Decimal('0.001')  # 0.1% fee
        
        logger.info(f"Paper trading initialized with {initial_usdt} USDT")
    
    async def get_balance(self, asset: str) -> Decimal:
        """Get available balance for asset"""
        balance = self.balances.get(asset, PaperBalance(asset))
        logger.debug(f"Paper balance {asset}: {balance.free}")
        return balance.free
    
    async def get_current_price(self, symbol: str) -> Optional[Decimal]:
        """Get current market price (delegates to real Binance API)"""
        from utils.binance_client import create_binance_client
        
        try:
            client = create_binance_client()
            price = await client.get_current_price(symbol)
            return price
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return None
    
    async def place_market_buy_order(
        self, 
        symbol: str, 
        quantity: Decimal
    ) -> Optional[Dict[str, Any]]:
        """Simulate market buy order"""
        try:
            # Get current market price
            current_price = await self.get_current_price(symbol)
            if not current_price:
                return None
            
            # Calculate cost
            cost = quantity * current_price
            fee = cost * self.fee_rate
            total_cost = cost + fee
            
            # Extract assets
            base_asset = self._extract_base_asset(symbol)
            quote_asset = self._extract_quote_asset(symbol)
            
            # Check balance
            quote_balance = await self.get_balance(quote_asset)
            if quote_balance < total_cost:
                logger.error(
                    f"Insufficient {quote_asset} balance: need {total_cost}, have {quote_balance}"
                )
                return None
            
            # Execute trade
            order_id = str(uuid.uuid4())[:8]
            
            # Update balances
            self._update_balance(quote_asset, -total_cost)
            self._update_balance(base_asset, quantity)
            
            # Record order
            order = PaperOrder(
                order_id=order_id,
                symbol=symbol,
                side="BUY",
                quantity=quantity,
                price=current_price
            )
            self.orders.append(order)
            self.trade_count += 1
            self.total_fees += fee
            
            logger.info(
                f"Paper BUY: {quantity} {symbol} @ {current_price} "
                f"(cost: {cost}, fee: {fee})"
            )
            
            # Return Binance-like response
            return {
                'orderId': order_id,
                'symbol': symbol,
                'status': 'FILLED',
                'side': 'BUY',
                'executedQty': str(quantity),
                'cummulativeQuoteQty': str(cost),
                'fills': [{
                    'price': str(current_price),
                    'qty': str(quantity),
                    'commission': str(fee),
                    'commissionAsset': quote_asset
                }]
            }
            
        except Exception as e:
            logger.error(f"Paper buy order failed: {e}")
            return None
    
    async def place_market_sell_order(
        self, 
        symbol: str, 
        quantity: Decimal
    ) -> Optional[Dict[str, Any]]:
        """Simulate market sell order"""
        try:
            # Get current market price
            current_price = await self.get_current_price(symbol)
            if not current_price:
                return None
            
            # Calculate proceeds
            proceeds = quantity * current_price
            fee = proceeds * self.fee_rate
            net_proceeds = proceeds - fee
            
            # Extract assets
            base_asset = self._extract_base_asset(symbol)
            quote_asset = self._extract_quote_asset(symbol)
            
            # Check balance
            base_balance = await self.get_balance(base_asset)
            if base_balance < quantity:
                logger.error(
                    f"Insufficient {base_asset} balance: need {quantity}, have {base_balance}"
                )
                return None
            
            # Execute trade
            order_id = str(uuid.uuid4())[:8]
            
            # Update balances
            self._update_balance(base_asset, -quantity)
            self._update_balance(quote_asset, net_proceeds)
            
            # Record order
            order = PaperOrder(
                order_id=order_id,
                symbol=symbol,
                side="SELL",
                quantity=quantity,
                price=current_price
            )
            self.orders.append(order)
            self.trade_count += 1
            self.total_fees += fee
            
            logger.info(
                f"Paper SELL: {quantity} {symbol} @ {current_price} "
                f"(proceeds: {proceeds}, fee: {fee})"
            )
            
            # Return Binance-like response
            return {
                'orderId': order_id,
                'symbol': symbol,
                'status': 'FILLED',
                'side': 'SELL',
                'executedQty': str(quantity),
                'cummulativeQuoteQty': str(proceeds),
                'fills': [{
                    'price': str(current_price),
                    'qty': str(quantity),
                    'commission': str(fee),
                    'commissionAsset': quote_asset
                }]
            }
            
        except Exception as e:
            logger.error(f"Paper sell order failed: {e}")
            return None
    
    async def get_lot_size_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get lot size info (delegates to real Binance API)"""
        from utils.binance_client import create_binance_client
        
        try:
            client = create_binance_client()
            return await client.get_lot_size_info(symbol)
        except Exception as e:
            logger.error(f"Failed to get lot size info for {symbol}: {e}")
            return None
    
    def _update_balance(self, asset: str, amount: Decimal):
        """Update balance for asset"""
        if asset not in self.balances:
            self.balances[asset] = PaperBalance(asset)
        
        self.balances[asset].free += amount
        
        # Ensure balance doesn't go negative
        if self.balances[asset].free < 0:
            logger.warning(f"Negative balance for {asset}: {self.balances[asset].free}")
            self.balances[asset].free = Decimal('0')
    
    def _extract_base_asset(self, symbol: str) -> str:
        """Extract base asset from symbol"""
        for quote in ['USDT', 'BUSD', 'BTC', 'ETH', 'BNB']:
            if symbol.endswith(quote):
                return symbol[:-len(quote)]
        return symbol[:3]
    
    def _extract_quote_asset(self, symbol: str) -> str:
        """Extract quote asset from symbol"""
        for quote in ['USDT', 'BUSD', 'BTC', 'ETH', 'BNB']:
            if symbol.endswith(quote):
                return quote
        return 'USDT'
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get current portfolio summary"""
        total_usdt_value = Decimal('0')
        assets = []
        
        for asset, balance in self.balances.items():
            if balance.free > 0:
                asset_info = {
                    'asset': asset,
                    'free': float(balance.free),
                    'usdt_value': float(balance.free) if asset == 'USDT' else 0
                }
                assets.append(asset_info)
                total_usdt_value += balance.free if asset == 'USDT' else Decimal('0')
        
        return {
            'total_usdt_value': float(total_usdt_value),
            'total_trades': self.trade_count,
            'total_fees_paid': float(self.total_fees),
            'assets': assets,
            'recent_orders': [
                {
                    'symbol': order.symbol,
                    'side': order.side,
                    'quantity': float(order.quantity),
                    'price': float(order.price),
                    'time': order.created_at.isoformat()
                }
                for order in self.orders[-10:]  # Last 10 orders
            ]
        }


# Global paper trading instance
paper_engine = PaperTradingEngine()