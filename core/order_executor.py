# core/order_executor.py
"""
Clean order execution with proper error handling and atomic operations.
Integrates with PositionManager and RiskManager for full trading lifecycle.
"""
import asyncio
from decimal import Decimal, ROUND_DOWN
from typing import Optional, Dict, Any, NamedTuple
from dataclasses import dataclass
from enum import Enum

from core.position_manager import position_manager
from core.risk_manager import risk_manager, RiskConfig, RiskDecision
from core.trading_modes import trading_mode_manager
from utils.binance_client import BinanceClient
from utils.logger import get_trading_logger, log_trade_event

logger = get_trading_logger()


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    REJECTED = "rejected"


@dataclass
class OrderRequest:
    """Order request data structure"""
    symbol: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    quantity: Optional[Decimal] = None
    price: Optional[Decimal] = None
    force: bool = False  # Override risk checks


class OrderResult(NamedTuple):
    """Order execution result"""
    status: OrderStatus
    message: str
    order_id: Optional[str] = None
    executed_price: Optional[Decimal] = None
    executed_quantity: Optional[Decimal] = None
    profit: Optional[Decimal] = None


class OrderExecutor:
    """
    Clean order execution with proper validation and error handling.
    Integrates with PositionManager and RiskManager.
    """
    
    def __init__(self, binance_client: BinanceClient):
        self.client = binance_client
        self.logger = logger
    
    async def execute_order(
        self, 
        request: OrderRequest, 
        risk_config: RiskConfig
    ) -> OrderResult:
        """
        Execute order with full validation and error handling.
        Main entry point for all trading operations.
        """
        try:
            # Log order request
            log_trade_event(
                self.logger, 
                request.symbol, 
                "ORDER_REQUESTED",
                side=request.side.value,
                type=request.order_type.value,
                quantity=str(request.quantity) if request.quantity else "auto",
                price=str(request.price) if request.price else "market"
            )
            
            if request.side == OrderSide.BUY:
                return await self._execute_buy_order(request, risk_config)
            else:
                return await self._execute_sell_order(request, risk_config)
                
        except Exception as e:
            self.logger.error(f"Order execution failed for {request.symbol}: {e}", exc_info=True)
            return OrderResult(
                status=OrderStatus.FAILED,
                message=f"Execution error: {str(e)}"
            )
    
    async def _execute_buy_order(
        self, 
        request: OrderRequest, 
        risk_config: RiskConfig
    ) -> OrderResult:
        """Execute BUY order with validation"""
        symbol = request.symbol
        
        # Get current market price if not provided
        if request.price is None:
            current_price = await self.client.get_current_price(symbol)
            if not current_price:
                return OrderResult(
                    status=OrderStatus.FAILED,
                    message=f"Unable to get market price for {symbol}"
                )
        else:
            current_price = request.price
        
        # Calculate quantity if not provided (use max available balance)
        if request.quantity is None:
            quote_asset = self._extract_quote_asset(symbol)
            available_balance = await self.client.get_balance(quote_asset)
            
            if not available_balance or available_balance <= 0:
                return OrderResult(
                    status=OrderStatus.FAILED,
                    message=f"No {quote_asset} balance available"
                )
            
            # Calculate quantity based on available balance
            # Leave small buffer for fees
            usable_balance = available_balance * Decimal('0.999')
            calculated_quantity = usable_balance / current_price
            
            # Round to proper precision
            lot_info = await self.client.get_lot_size_info(symbol)
            if not lot_info:
                return OrderResult(
                    status=OrderStatus.FAILED,
                    message=f"Unable to get lot size info for {symbol}"
                )
            
            request.quantity = self._round_quantity(calculated_quantity, lot_info)
        
        # Risk validation
        if not request.force:
            risk_result = await risk_manager.validate_buy_order(
                symbol=symbol,
                quantity=request.quantity,
                price=current_price,
                available_balance=await self.client.get_balance(self._extract_quote_asset(symbol)),
                config=risk_config
            )
            
            if risk_result.decision != RiskDecision.ALLOW:
                return OrderResult(
                    status=OrderStatus.REJECTED,
                    message=risk_result.message
                )
        
        # Execute order on Binance
        binance_result = await self.client.place_market_buy_order(
            symbol=symbol,
            quantity=request.quantity
        )
        
        if not binance_result or binance_result.get('status') != 'FILLED':
            return OrderResult(
                status=OrderStatus.FAILED,
                message=f"Binance order failed: {binance_result}"
            )
        
        # Extract execution details
        executed_qty = Decimal(binance_result['executedQty'])
        avg_price = self._calculate_average_price(binance_result)
        order_id = binance_result.get('orderId')
        
        # Update position manager
        position_success = await position_manager.open_position(
            symbol=symbol,
            buy_price=avg_price,
            quantity=executed_qty,
            order_id=str(order_id) if order_id else None
        )
        
        if not position_success:
            self.logger.error(f"Position update failed after successful buy order: {symbol}")
        
        log_trade_event(
            self.logger,
            symbol,
            "BUY_EXECUTED",
            price=str(avg_price),
            quantity=str(executed_qty),
            order_id=str(order_id)
        )
        
        return OrderResult(
            status=OrderStatus.SUCCESS,
            message=f"Buy order executed: {executed_qty} {symbol} @ {avg_price}",
            order_id=str(order_id) if order_id else None,
            executed_price=avg_price,
            executed_quantity=executed_qty
        )
    
    async def _execute_sell_order(
        self, 
        request: OrderRequest, 
        risk_config: RiskConfig
    ) -> OrderResult:
        """Execute SELL order with validation"""
        symbol = request.symbol
        
        # Get current market price
        current_price = await self.client.get_current_price(symbol)
        if not current_price:
            return OrderResult(
                status=OrderStatus.FAILED,
                message=f"Unable to get market price for {symbol}"
            )
        
        # Get quantity from position if not provided
        if request.quantity is None:
            position = await position_manager.get_position(symbol)
            if not position:
                return OrderResult(
                    status=OrderStatus.FAILED,
                    message=f"No position found for {symbol}"
                )
            request.quantity = position.quantity
        
        # Risk validation
        if not request.force:
            risk_result = await risk_manager.validate_sell_order(
                symbol=symbol,
                current_price=current_price,
                config=risk_config,
                force_sell=False
            )
            
            # Handle different risk decisions
            if risk_result.decision == RiskDecision.BLOCK_NO_POSITION:
                return OrderResult(
                    status=OrderStatus.REJECTED,
                    message=risk_result.message
                )
            elif risk_result.decision in [
                RiskDecision.BLOCK_STOP_LOSS,
                RiskDecision.BLOCK_TAKE_PROFIT,
                RiskDecision.BLOCK_MIN_PROFIT
            ]:
                # These are actually triggers to sell, not blocks
                self.logger.info(f"Risk trigger activated for {symbol}: {risk_result.message}")
            elif risk_result.decision != RiskDecision.ALLOW:
                return OrderResult(
                    status=OrderStatus.REJECTED,
                    message=risk_result.message
                )
        
        # Execute order on Binance
        binance_result = await self.client.place_market_sell_order(
            symbol=symbol,
            quantity=request.quantity
        )
        
        if not binance_result or binance_result.get('status') != 'FILLED':
            return OrderResult(
                status=OrderStatus.FAILED,
                message=f"Binance order failed: {binance_result}"
            )
        
        # Extract execution details
        executed_qty = Decimal(binance_result['executedQty'])
        avg_price = self._calculate_average_price(binance_result)
        order_id = binance_result.get('orderId')
        
        # Update position manager and calculate profit
        profit = await position_manager.close_position(
            symbol=symbol,
            sell_price=avg_price,
            order_id=str(order_id) if order_id else None
        )
        
        log_trade_event(
            self.logger,
            symbol,
            "SELL_EXECUTED",
            price=str(avg_price),
            quantity=str(executed_qty),
            profit=str(profit) if profit else "0",
            order_id=str(order_id)
        )
        
        return OrderResult(
            status=OrderStatus.SUCCESS,
            message=f"Sell order executed: {executed_qty} {symbol} @ {avg_price} (P&L: {profit})",
            order_id=str(order_id) if order_id else None,
            executed_price=avg_price,
            executed_quantity=executed_qty,
            profit=profit
        )
    
    def _calculate_average_price(self, binance_result: Dict[str, Any]) -> Decimal:
        """Calculate average execution price from Binance fills"""
        fills = binance_result.get('fills', [])
        if not fills:
            # Fallback to price field if available
            return Decimal(binance_result.get('price', '0'))
        
        total_qty = Decimal('0')
        total_cost = Decimal('0')
        
        for fill in fills:
            qty = Decimal(fill['qty'])
            price = Decimal(fill['price'])
            total_qty += qty
            total_cost += qty * price
        
        if total_qty > 0:
            return total_cost / total_qty
        
        return Decimal('0')
    
    def _round_quantity(self, quantity: Decimal, lot_info: Dict[str, Any]) -> Decimal:
        """Round quantity to valid step size"""
        step_size = Decimal(lot_info['stepSize'])
        min_qty = Decimal(lot_info['minQty'])
        
        # Round down to step size
        rounded = (quantity / step_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * step_size
        
        # Ensure minimum quantity
        if rounded < min_qty:
            return Decimal('0')  # Will be caught by validation
        
        return rounded
    
    def _extract_quote_asset(self, symbol: str) -> str:
        """Extract quote asset from symbol (e.g., XRPUSDT -> USDT)"""
        for quote in ['USDT', 'BUSD', 'BTC', 'ETH', 'BNB']:
            if symbol.endswith(quote):
                return quote
        # Fallback
        return 'USDT'
    
    def _extract_base_asset(self, symbol: str) -> str:
        """Extract base asset from symbol (e.g., XRPUSDT -> XRP)"""
        quote = self._extract_quote_asset(symbol)
        return symbol[:-len(quote)]


# Factory function for easy initialization
def create_order_executor() -> OrderExecutor:
    """Create configured order executor instance"""
    from utils.binance_client import create_binance_client
    
    client = create_binance_client()
    return OrderExecutor(client)