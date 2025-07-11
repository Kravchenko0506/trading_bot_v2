"""
Trading interfaces - all interfaces for dependency injection.
CRITICAL: all financial operations ONLY through Decimal!
"""
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class OrderSide(Enum):
    """Order direction"""
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    """Order execution status"""
    SUCCESS = "success"
    FAILED = "failed"
    REJECTED = "rejected"


@dataclass
class OrderResult:
    """Order execution result"""
    status: OrderStatus
    order_id: Optional[str]
    executed_price: Optional[Decimal]
    executed_quantity: Optional[Decimal]
    message: str
    profit: Optional[Decimal] = None


@dataclass
class RiskCheckResult:
    """Risk validation result"""
    approved: bool
    reason: str
    risk_score: Decimal = Decimal('0')


@dataclass
class PositionData:
    """Position data"""
    symbol: str
    quantity: Decimal
    avg_price: Decimal
    unrealized_pnl: Decimal


class IMarketDataService(ABC):
    """Interface for market data retrieval"""

    @abstractmethod
    async def get_current_price(self, symbol: str) -> Decimal:
        """Get current price for symbol"""
        pass

    @abstractmethod
    async def get_klines(self, symbol: str, interval: str, limit: int) -> List[Dict[str, Any]]:
        """Get klines for analysis"""
        pass


class IRiskService(ABC):
    """Interface for risk management"""

    @abstractmethod
    async def validate_buy_order(self, symbol: str, quantity: Decimal, price: Decimal) -> RiskCheckResult:
        """Validate buy order"""
        pass

    @abstractmethod
    async def validate_sell_order(self, symbol: str, current_price: Decimal) -> RiskCheckResult:
        """Validate sell order"""
        pass


class IOrderService(ABC):
    """Interface for order execution"""

    @abstractmethod
    async def execute_buy_order(self, symbol: str, quantity: Decimal, price: Decimal) -> OrderResult:
        """Execute buy order"""
        pass

    @abstractmethod
    async def execute_sell_order(self, symbol: str, quantity: Decimal, price: Decimal) -> OrderResult:
        """Execute sell order"""
        pass


class INotificationService(ABC):
    """Interface for notifications"""

    @abstractmethod
    async def send_trade_alert(self, symbol: str, side: OrderSide, price: Decimal, profit: Optional[Decimal] = None) -> bool:
        """Send trade notification"""
        pass


class IPortfolioService(ABC):
    """Interface for portfolio management"""

    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[PositionData]:
        """Get position by symbol"""
        pass

    @abstractmethod
    async def get_account_balance(self) -> Decimal:
        """Get account balance"""
        pass

    @abstractmethod
    async def has_position(self, symbol: str) -> bool:
        """Check if position exists"""
        pass
