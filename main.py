"""
Main entry point for the trading bot.
CRITICAL: proper DI initialization, database setup, graceful shutdown.
"""
import asyncio
import sys
import signal
from pathlib import Path
from config.settings import settings
from core.factory import create_trading_engine
from database.connection import init_database
from utils.logger import get_system_logger

logger = get_system_logger()

# Global trading engine instance
trading_engine = None


async def initialize_system():
    """Initialize database and core systems"""
    try:
        logger.info("Initializing trading bot system...")

        # Initialize database connection
        if hasattr(settings, 'database') and settings.database.url:
            await init_database(settings.database.url)
            logger.info("Database initialized successfully")
        else:
            logger.warning(
                "No database configuration found, running without persistence")

        logger.info("System initialization completed")

    except Exception as e:
        logger.error(f"System initialization failed: {e}")
        raise


async def create_bot():
    """Create trading bot with proper dependency injection"""
    global trading_engine

    try:
        logger.info("Creating trading bot with dependency injection...")

        # Create trading engine through factory
        trading_engine = create_trading_engine(settings)

        logger.info("Trading bot created successfully")
        return trading_engine

    except Exception as e:
        logger.error(f"Failed to create trading bot: {e}")
        raise


async def start_trading():
    """Start the main trading loop"""
    try:
        logger.info("Starting trading operations...")

        # Start trading engine
        await trading_engine.start()

        # Keep running until shutdown signal
        while True:
            try:
                # Check portfolio status periodically
                portfolio_status = await trading_engine.get_portfolio_status()
                logger.debug(f"Portfolio status: {portfolio_status}")

                # Sleep for a short interval
                await asyncio.sleep(10)

            except KeyboardInterrupt:
                logger.info("Shutdown requested by user")
                break
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying

    except Exception as e:
        logger.error(f"Trading loop failed: {e}")
        raise


async def shutdown_gracefully():
    """Graceful shutdown of trading bot"""
    try:
        logger.info("Initiating graceful shutdown...")

        if trading_engine:
            await trading_engine.stop()

        # Close database connections
        # await close_database_connections()

        logger.info("Graceful shutdown completed")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        # Set a flag or raise an exception to break the main loop
        asyncio.create_task(shutdown_gracefully())
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def run_strategy(strategy_name: str):
    """Run specific trading strategy"""
    try:
        logger.info(f"Running strategy: {strategy_name}")

        # Import strategy module dynamically
        if strategy_name == "rsi_macd":
            from strategies.rsi_macd import RSIMACDStrategy
            strategy = RSIMACDStrategy(trading_engine)
        elif strategy_name == "grid":
            from strategies.grid_strategy import GridStrategy
            strategy = GridStrategy(trading_engine)
        elif strategy_name == "dca":
            from strategies.dca_strategy import DCAStrategy
            strategy = DCAStrategy(trading_engine)
        elif strategy_name == "scalping":
            # Scalping strategy removed - use DCA as default
            logger.warning(f"Scalping strategy deprecated, using DCA instead")
            from strategies.dca_strategy import DCAStrategy
            strategy = DCAStrategy(trading_engine)
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")

        # Run strategy
        await strategy.run()

    except Exception as e:
        logger.error(f"Strategy {strategy_name} failed: {e}")
        raise


async def health_check():
    """Perform system health check"""
    try:
        logger.info("Performing health check...")

        if not trading_engine:
            logger.error("Trading engine not initialized")
            return False

        # Check market data connectivity
        try:
            btc_price = await trading_engine.market_data.get_current_price("BTCUSDT")
            logger.info(f"Market data check passed: BTC price = {btc_price}")
        except Exception as e:
            logger.error(f"Market data check failed: {e}")
            return False

        # Check account balance
        try:
            balance = await trading_engine.portfolio.get_account_balance()
            logger.info(f"Account balance check passed: {balance} USDT")
        except Exception as e:
            logger.error(f"Account balance check failed: {e}")
            return False

        logger.info("Health check completed successfully")
        return True

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return False


async def send_test_notification():
    """Send test notification"""
    try:
        logger.info("Sending test notification...")

        if not trading_engine:
            logger.error("Trading engine not initialized")
            return False

        from core.interfaces.trading_interfaces import OrderSide
        from decimal import Decimal

        success = await trading_engine.notifications.send_trade_alert(
            "BTCUSDT",
            OrderSide.BUY,
            Decimal("50000.0")
        )

        if success:
            logger.info("Test notification sent successfully")
        else:
            logger.error("Test notification failed")

        return success

    except Exception as e:
        logger.error(f"Test notification failed: {e}")
        return False


async def main():
    """Main entry point with proper error handling and DI"""
    try:
        # Setup signal handlers
        setup_signal_handlers()

        # Initialize system
        await initialize_system()

        # Create trading bot
        await create_bot()

        # Parse command line arguments
        import argparse
        parser = argparse.ArgumentParser(description="Advanced Trading Bot")
        parser.add_argument("--strategy", type=str, help="Strategy to run")
        parser.add_argument(
            "--health-check", action="store_true", help="Perform health check")
        parser.add_argument("--test-notification",
                            action="store_true", help="Send test notification")
        parser.add_argument("--portfolio-status",
                            action="store_true", help="Show portfolio status")

        args = parser.parse_args()

        # Handle different commands
        if args.health_check:
            success = await health_check()
            sys.exit(0 if success else 1)

        elif args.test_notification:
            success = await send_test_notification()
            sys.exit(0 if success else 1)

        elif args.portfolio_status:
            status = await trading_engine.get_portfolio_status()
            print(f"Portfolio Status: {status}")
            sys.exit(0)

        elif args.strategy:
            await run_strategy(args.strategy)

        else:
            # Default: start main trading loop
            await start_trading()

    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Critical error in main: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await shutdown_gracefully()


if __name__ == "__main__":
    # Run main with proper event loop handling
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application failed: {e}")
        sys.exit(1)
