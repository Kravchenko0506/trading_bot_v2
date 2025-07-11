"""
Notification Service - sends trade alerts and notifications.
CRITICAL: reliable delivery, proper error handling, non-blocking operations.
"""
from decimal import Decimal
from typing import Optional
from ..interfaces.trading_interfaces import INotificationService, OrderSide
from ..exceptions.trading_exceptions import TradingError
from utils.logger import get_trading_logger

logger = get_trading_logger()


class NotificationService(INotificationService):
    """Notification service implementation"""

    def __init__(self, telegram_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.enabled = bool(telegram_token and chat_id)

        if self.enabled:
            logger.info("NotificationService initialized with Telegram")
        else:
            logger.warning(
                "NotificationService initialized without Telegram (notifications disabled)")

    async def send_trade_alert(self, symbol: str, side: OrderSide, price: Decimal, profit: Optional[Decimal] = None) -> bool:
        """Send trade notification"""
        try:
            if not self.enabled:
                logger.debug(
                    f"Notifications disabled, skipping alert for {symbol}")
                return True

            # Prepare message
            side_emoji = "🟢" if side == OrderSide.BUY else "🔴"
            side_text = "BUY" if side == OrderSide.BUY else "SELL"

            message = f"{side_emoji} **{side_text} EXECUTED**\n"
            message += f"Symbol: {symbol}\n"
            message += f"Price: ${price}\n"

            if profit is not None:
                if profit > 0:
                    message += f"Profit: +${profit} 📈\n"
                elif profit < 0:
                    message += f"Loss: ${profit} 📉\n"
                else:
                    message += f"Break-even: ${profit}\n"

            message += f"Time: {self._get_current_time()}"

            # Send via Telegram
            success = await self._send_telegram_message(message)

            if success:
                logger.info(
                    f"Trade alert sent successfully: {symbol} {side_text}")
            else:
                logger.error(
                    f"Failed to send trade alert: {symbol} {side_text}")

            return success

        except Exception as e:
            logger.error(f"Notification error for {symbol} {side}: {e}")
            # Don't raise exception - notifications should not break trading
            return False

    async def send_error_alert(self, error_message: str, error_type: str = "TRADING_ERROR") -> bool:
        """Send error notification"""
        try:
            if not self.enabled:
                return True

            message = f"🚨 **{error_type}**\n"
            message += f"Error: {error_message}\n"
            message += f"Time: {self._get_current_time()}"

            success = await self._send_telegram_message(message)

            if success:
                logger.info(f"Error alert sent: {error_type}")
            else:
                logger.error(f"Failed to send error alert: {error_type}")

            return success

        except Exception as e:
            logger.error(f"Error notification failed: {e}")
            return False

    async def send_daily_summary(self, total_trades: int, total_profit: Decimal, win_rate: Decimal) -> bool:
        """Send daily trading summary"""
        try:
            if not self.enabled:
                return True

            profit_emoji = "📈" if total_profit > 0 else "📉" if total_profit < 0 else "➡️"

            message = f"📊 **DAILY SUMMARY**\n"
            message += f"Total Trades: {total_trades}\n"
            message += f"Total P&L: {profit_emoji} ${total_profit}\n"
            message += f"Win Rate: {win_rate:.1f}%\n"
            message += f"Date: {self._get_current_date()}"

            success = await self._send_telegram_message(message)

            if success:
                logger.info("Daily summary sent successfully")
            else:
                logger.error("Failed to send daily summary")

            return success

        except Exception as e:
            logger.error(f"Daily summary notification failed: {e}")
            return False

    async def _send_telegram_message(self, message: str) -> bool:
        """Send message via Telegram Bot API"""
        try:
            import aiohttp

            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"

            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("ok", False)
                    else:
                        logger.error(f"Telegram API error: {response.status}")
                        return False

        except ImportError:
            logger.error("aiohttp not available for Telegram notifications")
            return False
        except Exception as e:
            logger.error(f"Telegram message send failed: {e}")
            return False

    def _get_current_time(self) -> str:
        """Get current time formatted for notifications"""
        from datetime import datetime
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    def _get_current_date(self) -> str:
        """Get current date formatted for notifications"""
        from datetime import datetime
        return datetime.utcnow().strftime("%Y-%m-%d")

    def set_telegram_config(self, token: str, chat_id: str):
        """Update Telegram configuration"""
        self.telegram_token = token
        self.chat_id = chat_id
        self.enabled = True
        logger.info("Telegram configuration updated")

    def disable_notifications(self):
        """Disable all notifications"""
        self.enabled = False
        logger.info("Notifications disabled")

    def enable_notifications(self):
        """Enable notifications (if properly configured)"""
        if self.telegram_token and self.chat_id:
            self.enabled = True
            logger.info("Notifications enabled")
        else:
            logger.warning(
                "Cannot enable notifications: missing Telegram configuration")
