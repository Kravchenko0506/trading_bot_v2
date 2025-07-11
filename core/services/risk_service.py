"""
Risk Service - validates trading operations against risk parameters.
CRITICAL: all financial calculations with Decimal, comprehensive validation.
"""
from decimal import Decimal
from typing import Optional
from ..interfaces.trading_interfaces import IRiskService, RiskCheckResult
from ..exceptions.trading_exceptions import RiskValidationError, InsufficientBalanceError
from utils.logger import get_trading_logger

logger = get_trading_logger()


class RiskService(IRiskService):
    """Risk management service implementation"""

    def __init__(self,
                 max_position_size: Decimal = Decimal('1000.0'),
                 max_daily_loss: Decimal = Decimal('500.0'),
                 max_trade_size: Decimal = Decimal('100.0'),
                 portfolio_service=None):
        self.max_position_size = max_position_size
        self.max_daily_loss = max_daily_loss
        self.max_trade_size = max_trade_size
        self.portfolio_service = portfolio_service
        self.daily_loss = Decimal('0.0')  # Track daily losses

        logger.info(
            f"RiskService initialized: max_position={max_position_size}, max_daily_loss={max_daily_loss}")

    async def validate_buy_order(self, symbol: str, quantity: Decimal, price: Decimal) -> RiskCheckResult:
        """Validate buy order against risk parameters"""
        try:
            logger.debug(
                f"Validating buy order: {symbol} qty={quantity} price={price}")

            # Calculate trade value
            trade_value = quantity * price

            # Check maximum trade size
            if trade_value > self.max_trade_size:
                reason = f"Trade value {trade_value} exceeds max trade size {self.max_trade_size}"
                logger.warning(f"Buy order rejected: {reason}")
                return RiskCheckResult(
                    approved=False,
                    reason=reason,
                    risk_score=Decimal('1.0')  # High risk
                )

            # Check account balance if portfolio service available
            if self.portfolio_service:
                balance = await self.portfolio_service.get_account_balance()
                if balance < trade_value:
                    reason = f"Insufficient balance: need {trade_value}, have {balance}"
                    logger.warning(f"Buy order rejected: {reason}")
                    return RiskCheckResult(
                        approved=False,
                        reason=reason,
                        risk_score=Decimal('1.0')
                    )

            # Check position size limit
            if self.portfolio_service:
                existing_position = await self.portfolio_service.get_position(symbol)
                if existing_position:
                    new_position_value = (
                        existing_position.quantity + quantity) * price
                    if new_position_value > self.max_position_size:
                        reason = f"Position size {new_position_value} would exceed limit {self.max_position_size}"
                        logger.warning(f"Buy order rejected: {reason}")
                        return RiskCheckResult(
                            approved=False,
                            reason=reason,
                            risk_score=Decimal('0.8')
                        )

            # Check daily loss limit
            if self.daily_loss > self.max_daily_loss:
                reason = f"Daily loss {self.daily_loss} exceeds limit {self.max_daily_loss}"
                logger.warning(f"Buy order rejected: {reason}")
                return RiskCheckResult(
                    approved=False,
                    reason=reason,
                    risk_score=Decimal('0.9')
                )

            # Calculate risk score based on trade size
            risk_score = trade_value / self.max_trade_size

            logger.info(
                f"Buy order approved: {symbol} risk_score={risk_score}")
            return RiskCheckResult(
                approved=True,
                reason="Risk validation passed",
                risk_score=risk_score
            )

        except Exception as e:
            logger.error(f"Risk validation error for buy order {symbol}: {e}")
            raise RiskValidationError(
                f"Buy order validation failed: {str(e)}", risk_type="buy_validation")

    async def validate_sell_order(self, symbol: str, current_price: Decimal) -> RiskCheckResult:
        """Validate sell order against risk parameters"""
        try:
            logger.debug(
                f"Validating sell order: {symbol} current_price={current_price}")

            # Check if we have position to sell
            if self.portfolio_service:
                position = await self.portfolio_service.get_position(symbol)
                if not position:
                    reason = f"No position found for {symbol} to sell"
                    logger.warning(f"Sell order rejected: {reason}")
                    return RiskCheckResult(
                        approved=False,
                        reason=reason,
                        risk_score=Decimal('1.0')
                    )

                # Calculate potential loss/profit
                potential_pnl = (
                    current_price - position.avg_price) * position.quantity

                # Check if selling would exceed daily loss limit
                if potential_pnl < 0:  # Loss
                    potential_daily_loss = self.daily_loss + abs(potential_pnl)
                    if potential_daily_loss > self.max_daily_loss:
                        reason = f"Selling would exceed daily loss limit: {potential_daily_loss} > {self.max_daily_loss}"
                        logger.warning(f"Sell order rejected: {reason}")
                        return RiskCheckResult(
                            approved=False,
                            reason=reason,
                            risk_score=Decimal('0.9')
                        )

                # Calculate risk score based on potential loss
                risk_score = abs(
                    potential_pnl) / self.max_daily_loss if potential_pnl < 0 else Decimal('0.1')
            else:
                # Medium risk without portfolio data
                risk_score = Decimal('0.5')

            logger.info(
                f"Sell order approved: {symbol} risk_score={risk_score}")
            return RiskCheckResult(
                approved=True,
                reason="Risk validation passed",
                risk_score=risk_score
            )

        except Exception as e:
            logger.error(f"Risk validation error for sell order {symbol}: {e}")
            raise RiskValidationError(
                f"Sell order validation failed: {str(e)}", risk_type="sell_validation")

    def update_daily_loss(self, loss_amount: Decimal):
        """Update daily loss tracking"""
        if loss_amount > 0:
            self.daily_loss += loss_amount
            logger.info(f"Daily loss updated: {self.daily_loss}")

    def reset_daily_loss(self):
        """Reset daily loss counter (call at start of new trading day)"""
        self.daily_loss = Decimal('0.0')
        logger.info("Daily loss counter reset")
