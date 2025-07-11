"""
Trading exceptions - all custom exceptions for trading operations.
CRITICAL: comprehensive error handling with rollback capabilities.
"""
from datetime import datetime
from typing import Dict, Any, Optional
from decimal import Decimal


class TradingError(Exception):
    """Base exception for all trading errors"""

    def __init__(self, message: str, error_code: str = None, context: Dict[str, Any] = None):
        super().__init__(message)
        self.error_code = error_code
        self.context = context or {}
        self.timestamp = datetime.utcnow()

    def __str__(self) -> str:
        base_msg = super().__str__()
        if self.error_code:
            return f"[{self.error_code}] {base_msg}"
        return base_msg


class InsufficientBalanceError(TradingError):
    """Raised when account balance is insufficient for operation"""

    def __init__(self, required: Decimal, available: Decimal, symbol: str = ""):
        message = f"Insufficient balance for {symbol}: need {required}, have {available}"
        super().__init__(message, error_code="INSUFFICIENT_BALANCE")
        self.required = required
        self.available = available
        self.symbol = symbol


class OrderExecutionError(TradingError):
    """Raised when order execution fails on exchange"""

    def __init__(self, message: str, order_id: Optional[str] = None, exchange_error: Optional[str] = None):
        super().__init__(message, error_code="ORDER_EXECUTION_FAILED")
        self.order_id = order_id
        self.exchange_error = exchange_error


class RiskValidationError(TradingError):
    """Raised when risk validation fails"""

    def __init__(self, message: str, risk_type: str = "", risk_score: Decimal = Decimal('0')):
        super().__init__(message, error_code="RISK_VALIDATION_FAILED")
        self.risk_type = risk_type
        self.risk_score = risk_score


class MarketDataError(TradingError):
    """Raised when market data retrieval fails"""

    def __init__(self, message: str, symbol: str = "", data_type: str = ""):
        super().__init__(message, error_code="MARKET_DATA_ERROR")
        self.symbol = symbol
        self.data_type = data_type


class PositionNotFoundError(TradingError):
    """Raised when position is not found"""

    def __init__(self, symbol: str):
        message = f"Position not found for symbol: {symbol}"
        super().__init__(message, error_code="POSITION_NOT_FOUND")
        self.symbol = symbol


class ConfigurationError(TradingError):
    """Raised when configuration is invalid"""

    def __init__(self, message: str, config_key: str = ""):
        super().__init__(message, error_code="CONFIGURATION_ERROR")
        self.config_key = config_key


class ExchangeConnectionError(TradingError):
    """Raised when exchange connection fails"""

    def __init__(self, message: str, exchange_name: str = ""):
        super().__init__(message, error_code="EXCHANGE_CONNECTION_ERROR")
        self.exchange_name = exchange_name


class RateLimitError(TradingError):
    """Raised when API rate limit is exceeded"""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message, error_code="RATE_LIMIT_EXCEEDED")
        self.retry_after = retry_after
