# config/settings.py
"""
Application configuration with validation and environment support.
This module defines the settings for the trading bot, including Binance API credentials,
database connection, Telegram bot configuration, trading parameters, and logging settings.
"""
import os
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class BinanceConfig:
    """Binance API configuration"""
    api_key: str
    api_secret: str
    testnet: bool = False
    
    def __post_init__(self):
        if not self.api_key or not self.api_secret:
            raise ValueError("Binance API credentials are required")


@dataclass
class DatabaseConfig:
    """Database configuration"""
    url: Optional[str] = None
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False
    
    def __post_init__(self):
        if self.url is None:
            # Default to SQLite
            os.makedirs("data", exist_ok=True)
            self.url = "sqlite+aiosqlite:///data/trading_bot.db"


@dataclass
class TelegramConfig:
    """Telegram bot configuration"""
    token: str
    admin_ids: list[str]
    webhook_url: Optional[str] = None
    
    def __post_init__(self):
        if not self.token:
            raise ValueError("Telegram bot token is required")


@dataclass
class TradingConfig:
    """Default trading parameters"""
    # Order limits
    min_trade_amount: Decimal = Decimal('10')
    max_position_size: Decimal = Decimal('100')
    price_precision: int = 8
    quantity_precision: int = 8
    
    # Risk management defaults
    default_stop_loss: Decimal = Decimal('-0.02')  # -2%
    default_take_profit: Decimal = Decimal('0.05')  # 5%
    default_min_profit: Decimal = Decimal('0.01')   # 1%
    
    # Commission
    commission_rate: Decimal = Decimal('0.001')  # 0.1%
    
    # Safety settings
    allow_concurrent_positions: bool = False
    max_daily_trades: int = 50
    cooldown_between_trades: int = 60  # seconds
    
    def __post_init__(self):
        # Validate ranges
        if self.default_stop_loss >= 0:
            raise ValueError("Stop loss must be negative")
        if self.default_take_profit <= 0:
            raise ValueError("Take profit must be positive")
        if self.min_trade_amount <= 0:
            raise ValueError("Minimum trade amount must be positive")


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    file_path: str = "logs"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    console_output: bool = True
    
    def __post_init__(self):
        os.makedirs(self.file_path, exist_ok=True)


class Settings:
    """Main application settings"""
    
    def __init__(self):
        self.binance = BinanceConfig(
            api_key=os.getenv('BINANCE_API_KEY', ''),
            api_secret=os.getenv('BINANCE_API_SECRET', ''),
            testnet=os.getenv('BINANCE_TESTNET', 'false').lower() == 'true'
        )
        
        self.database = DatabaseConfig(
            url=os.getenv('DATABASE_URL'),
            echo=os.getenv('DB_ECHO', 'false').lower() == 'true'
        )
        
        self.telegram = TelegramConfig(
            token=os.getenv('TELEGRAM_TOKEN', ''),
            admin_ids=os.getenv('TELEGRAM_ADMIN_IDS', '').split(',')
        )
        
        self.trading = TradingConfig()
        self.logging = LoggingConfig()
        
        # Environment
        self.environment = os.getenv('ENVIRONMENT', 'development')
        self.debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    def validate(self) -> bool:
        """Validate all configuration"""
        try:
            # Validate each config section
            if not self.binance.api_key:
                raise ValueError("Binance API key missing")
            
            if not self.telegram.token:
                raise ValueError("Telegram token missing")
            
            return True
            
        except Exception as e:
            print(f"Configuration validation failed: {e}")
            return False
    
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment.lower() == 'production'
    
    def get_log_level(self) -> str:
        """Get effective log level"""
        if self.debug:
            return "DEBUG"
        return self.logging.level


# Global settings instance
settings = Settings()


# Helper functions for backward compatibility
def get_binance_client():
    """Get configured Binance client"""
    from binance.client import Client
    
    return Client(
        api_key=settings.binance.api_key,
        api_secret=settings.binance.api_secret,
        testnet=settings.binance.testnet
    )


def load_environment_config():
    """Load configuration from environment (for deployment)"""
    return {
        'database_url': settings.database.url,
        'binance_testnet': settings.binance.testnet,
        'debug_mode': settings.debug,
        'log_level': settings.get_log_level()
    }


# Validation on import
if not settings.validate():
    print("⚠️  Configuration validation failed. Check your .env file.")
    print("Required variables: BINANCE_API_KEY, BINANCE_API_SECRET, TELEGRAM_TOKEN")