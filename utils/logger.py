# utils/logger.py
"""
Enhanced logging system with structured output and database integration.
This module provides a custom logging setup for the trading bot, including:
- Custom log handlers for console and file output
"""
import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from typing import Optional
import asyncio
from datetime import datetime
import json

from config.settings import settings


class DatabaseLogHandler(logging.Handler):
    """Custom handler to store critical logs in database"""

    def emit(self, record):
        """Store log record in database (async)"""
        if record.levelno >= logging.WARNING:
            # Only store warnings and errors in database
            asyncio.create_task(self._store_log(record))

    async def _store_log(self, record):
        """Store log in database table"""
        try:
            from database.connection import get_db_session
            from database.models import SystemLog

            async with get_db_session() as session:
                log_entry = SystemLog(
                    level=record.levelname,
                    message=record.getMessage(),
                    module=record.module if hasattr(
                        record, 'module') else record.name,
                    exception_info=self.format(
                        record) if record.exc_info else None
                )
                session.add(log_entry)
                await session.commit()
        except Exception:
            # Don't let logging errors crash the application
            pass


class CustomFormatter(logging.Formatter):
    """Custom formatter with colors and structured output"""

    # Color codes for console output
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'      # Reset
    }

    def format(self, record):
        """Format log record with colors and structure"""
        # Add timestamp
        record.timestamp = datetime.utcnow().isoformat()

        # Create base format
        if hasattr(record, 'symbol'):
            # Trading-specific logs
            base_format = "{timestamp} | {levelname:8} | {symbol:8} | {message}"
        else:
            # System logs
            base_format = "{timestamp} | {levelname:8} | {name:15} | {message}"

        # Add colors for console
        if self._is_console_handler(record):
            color = self.COLORS.get(record.levelname, '')
            reset = self.COLORS['RESET']
            base_format = f"{color}{base_format}{reset}"

        # Format the message
        formatted = base_format.format(
            timestamp=record.timestamp,
            levelname=record.levelname,
            name=record.name,
            symbol=getattr(record, 'symbol', ''),
            message=record.getMessage()
        )

        # Add exception info if present
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"

        return formatted

    def _is_console_handler(self, record):
        """Check if this is being formatted for console output"""
        return hasattr(record, '_console_output')


def setup_logger(
    name: str,
    log_file: Optional[str] = None,
    level: str = "INFO",
    include_console: bool = True,
    include_database: bool = False
) -> logging.Logger:
    """
    Setup logger with file, console, and optionally database output.

    Args:
        name: Logger name (e.g., 'trading', 'system')
        log_file: Log file path (optional)
        level: Log level
        include_console: Add console handler
        include_database: Add database handler for critical logs
    """
    logger = logging.getLogger(name)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper()))
    formatter = CustomFormatter()

    # File handler with rotation
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=settings.logging.max_file_size,
            backupCount=settings.logging.backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Console handler
    if include_console and settings.logging.console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)

        # Mark records for console-specific formatting
        def add_console_marker(record):
            record._console_output = True
            return True
        console_handler.addFilter(add_console_marker)

        logger.addHandler(console_handler)

    # Database handler for critical logs
    if include_database:
        db_handler = DatabaseLogHandler()
        logger.addHandler(db_handler)

    return logger


# Pre-configured loggers
def get_system_logger() -> logging.Logger:
    """Get system logger for application events"""
    return setup_logger(
        name="system",
        log_file=os.path.join(settings.logging.file_path, "system.log"),
        level=settings.get_log_level(),
        include_console=True,
        include_database=True
    )


def get_trading_logger() -> logging.Logger:
    """Get trading logger for market operations"""
    return setup_logger(
        name="trading",
        log_file=os.path.join(settings.logging.file_path, "trading.log"),
        level=settings.get_log_level(),
        include_console=True,
        include_database=False
    )


def get_strategy_logger() -> logging.Logger:
    """Get strategy logger for trading decisions"""
    return setup_logger(
        name="strategy",
        log_file=os.path.join(settings.logging.file_path, "strategy.log"),
        level=settings.get_log_level(),
        include_console=True,  # Enable console output for strategy logs
        include_database=False
    )


def get_telegram_logger() -> logging.Logger:
    """Get Telegram bot logger"""
    return setup_logger(
        name="telegram",
        log_file=os.path.join(settings.logging.file_path, "telegram.log"),
        level=settings.get_log_level(),
        include_console=True,
        include_database=False
    )


# Utility functions for structured logging
def log_trade_event(logger: logging.Logger, symbol: str, event: str, **kwargs):
    """Log trading event with structured data"""
    extra = {'symbol': symbol}
    data = json.dumps(kwargs, default=str)
    logger.info(f"{event}: {data}", extra=extra)


def log_error_with_context(logger: logging.Logger, error: Exception, context: dict):
    """Log error with full context information"""
    context_data = json.dumps(context, default=str)
    logger.error(
        f"Error: {str(error)} | Context: {context_data}", exc_info=True)


# Initialize logging system
system_logger = get_system_logger()
trading_logger = get_trading_logger()

# Log system startup
system_logger.info("Logging system initialized")
if settings.debug:
    system_logger.debug(
        f"Debug mode enabled. Log level: {settings.get_log_level()}")
