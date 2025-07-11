"""
Trading Bot Factory - dependency injection container.
CRITICAL: proper service wiring, configuration validation, error handling.
"""
from decimal import Decimal
from typing import Optional
from config.settings import Settings
from utils.binance_client import BinanceClient
from .services.market_data_service import MarketDataService
from .services.risk_service import RiskService
from .services.order_service import OrderService
from .services.notification_service import NotificationService
from .services.portfolio_service import PortfolioService
from .trading_engine import TradingEngine
from .exceptions.trading_exceptions import ConfigurationError
from utils.logger import get_system_logger

logger = get_system_logger()


class TradingBotFactory:
    """Factory for creating fully configured trading bot with dependency injection"""

    def __init__(self):
        self._binance_client: Optional[BinanceClient] = None
        self._market_data_service: Optional[MarketDataService] = None
        self._portfolio_service: Optional[PortfolioService] = None
        self._risk_service: Optional[RiskService] = None
        self._order_service: Optional[OrderService] = None
        self._notification_service: Optional[NotificationService] = None

        logger.info("TradingBotFactory initialized")

    def create_trading_engine(self, settings: Settings) -> TradingEngine:
        """Create trading engine with all dependencies"""
        try:
            logger.info("Creating trading engine with dependency injection")

            # Validate configuration
            self._validate_settings(settings)

            # Create HTTP client
            binance_client = self._create_binance_client(settings)

            # Create services in dependency order
            market_data_service = self._create_market_data_service(
                binance_client)
            portfolio_service = self._create_portfolio_service(binance_client)
            risk_service = self._create_risk_service(
                settings, portfolio_service)
            order_service = self._create_order_service(
                binance_client, market_data_service)
            notification_service = self._create_notification_service(settings)

            # Create trading engine
            trading_engine = TradingEngine(
                market_data=market_data_service,
                risk_service=risk_service,
                order_service=order_service,
                notification_service=notification_service,
                portfolio_service=portfolio_service
            )

            logger.info(
                "Trading engine created successfully with all dependencies")
            return trading_engine

        except Exception as e:
            logger.error(f"Failed to create trading engine: {e}")
            raise ConfigurationError(
                f"Trading engine creation failed: {str(e)}")

    def _validate_settings(self, settings: Settings):
        """Validate critical settings"""
        logger.debug("Validating settings")

        # Validate Binance settings
        if not settings.binance.api_key:
            raise ConfigurationError(
                "Binance API key is required", config_key="binance.api_key")

        if not settings.binance.api_secret:
            raise ConfigurationError(
                "Binance API secret is required", config_key="binance.api_secret")

        # Validate trading settings - ИСПРАВЛЯЕМ ОБРАЩЕНИЯ
        if settings.trading.max_position_size <= 0:
            raise ConfigurationError(
                "Max position size must be positive", config_key="trading.max_position_size")

        if settings.trading.max_daily_loss <= 0:
            raise ConfigurationError(
                "Max daily loss must be positive", config_key="trading.max_daily_loss")

        if settings.trading.max_trade_size <= 0:
            raise ConfigurationError(
                "Max trade size must be positive", config_key="trading.max_trade_size")

        logger.debug("Settings validation passed")

    def _create_binance_client(self, settings: Settings) -> BinanceClient:
        """Create and configure Binance client"""
        logger.debug("Creating Binance client")

        if self._binance_client is None:
            self._binance_client = BinanceClient(
                api_key=settings.binance.api_key,
                api_secret=settings.binance.api_secret,
                testnet=settings.binance.testnet,
                rate_limit_per_minute=settings.binance.rate_limit_per_minute
            )
            logger.info(
                f"Binance client created (testnet: {settings.binance.testnet})")

        return self._binance_client

    def _create_market_data_service(self, binance_client: BinanceClient) -> MarketDataService:
        """Create market data service"""
        logger.debug("Creating MarketDataService")

        if self._market_data_service is None:
            self._market_data_service = MarketDataService(binance_client)
            logger.info("MarketDataService created")

        return self._market_data_service

    def _create_portfolio_service(self, binance_client: BinanceClient) -> PortfolioService:
        """Create portfolio service"""
        logger.debug("Creating PortfolioService")

        if self._portfolio_service is None:
            self._portfolio_service = PortfolioService(binance_client)
            logger.info("PortfolioService created")

        return self._portfolio_service

    def _create_risk_service(self, settings: Settings, portfolio_service: PortfolioService) -> RiskService:
        """Create risk service"""
        logger.debug("Creating RiskService")

        if self._risk_service is None:
            self._risk_service = RiskService(
                max_position_size=settings.trading.max_position_size,  # Убираем Decimal()
                max_daily_loss=settings.trading.max_daily_loss,        # Убираем Decimal()
                max_trade_size=settings.trading.max_trade_size,        # Убираем Decimal()
                portfolio_service=portfolio_service
            )
            logger.info("RiskService created with portfolio dependency")

        return self._risk_service

    def _create_order_service(self, binance_client: BinanceClient, market_data_service: MarketDataService) -> OrderService:
        """Create order service"""
        logger.debug("Creating OrderService")

        if self._order_service is None:
            self._order_service = OrderService(
                binance_client, market_data_service)
            logger.info("OrderService created with market data dependency")

        return self._order_service

    def _create_notification_service(self, settings: Settings) -> NotificationService:
        """Create notification service"""
        logger.debug("Creating NotificationService")

        if self._notification_service is None:
            telegram_token = getattr(settings.telegram, 'token', None) if hasattr(
                settings, 'telegram') else None
            chat_id = getattr(settings.telegram, 'chat_id', None) if hasattr(
                settings, 'telegram') else None

            self._notification_service = NotificationService(
                telegram_token=telegram_token,
                chat_id=chat_id
            )
            logger.info("NotificationService created")

        return self._notification_service

    def create_strategy_engine(self, settings: Settings, strategy_name: str):
        """Create strategy-specific trading engine"""
        try:
            logger.info(f"Creating strategy engine: {strategy_name}")

            # Create base trading engine
            trading_engine = self.create_trading_engine(settings)

            # Load strategy-specific configuration
            strategy_config = getattr(settings.strategies, strategy_name, None)
            if not strategy_config:
                raise ConfigurationError(
                    f"Strategy configuration not found: {strategy_name}")

            # Configure risk parameters for strategy
            if hasattr(strategy_config, 'max_position_size'):
                trading_engine.risk_service.max_position_size = Decimal(
                    str(strategy_config.max_position_size))

            if hasattr(strategy_config, 'max_trade_size'):
                trading_engine.risk_service.max_trade_size = Decimal(
                    str(strategy_config.max_trade_size))

            logger.info(f"Strategy engine created: {strategy_name}")
            return trading_engine

        except Exception as e:
            logger.error(
                f"Failed to create strategy engine {strategy_name}: {e}")
            raise ConfigurationError(
                f"Strategy engine creation failed: {str(e)}")

    def reset_services(self):
        """Reset all cached services (for testing or reconfiguration)"""
        logger.info("Resetting all services")

        self._binance_client = None
        self._market_data_service = None
        self._portfolio_service = None
        self._risk_service = None
        self._order_service = None
        self._notification_service = None

        logger.info("All services reset")

    def get_service_status(self) -> dict:
        """Get status of all services for health checks"""
        return {
            "binance_client": self._binance_client is not None,
            "market_data_service": self._market_data_service is not None,
            "portfolio_service": self._portfolio_service is not None,
            "risk_service": self._risk_service is not None,
            "order_service": self._order_service is not None,
            "notification_service": self._notification_service is not None
        }


# Global factory instance
trading_factory = TradingBotFactory()


def create_trading_engine(settings: Settings) -> TradingEngine:
    """Convenience function to create trading engine"""
    return trading_factory.create_trading_engine(settings)


def create_strategy_engine(settings: Settings, strategy_name: str) -> TradingEngine:
    """Convenience function to create strategy-specific engine"""
    return trading_factory.create_strategy_engine(settings, strategy_name)
