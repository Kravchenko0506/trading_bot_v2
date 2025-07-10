# main.py
"""
Main entry point for the trading bot.
This script provides a command line interface to start the trading bot,
show status, list profiles, create demo profiles, and stop the bot.
"""
import asyncio
import sys
import argparse
from pathlib import Path
from decimal import Decimal

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.trading_engine import trading_engine, setup_signal_handlers
from core.strategy_manager import strategy_manager
from core.trading_modes import trading_mode_manager, TradingMode
from core.risk_manager import RiskConfig
from utils.binance_client import create_binance_client
from config.settings import settings
from utils.logger import get_system_logger
from database.connection import init_database

logger = get_system_logger()


async def start_trading_bot(profile_name: str, trading_mode: str = "paper"):
    """Start trading bot with specified profile and mode"""
    try:
        logger.info(f"Starting trading bot: profile={profile_name}, mode={trading_mode}")
        
        # Initialize database
        await init_database(settings.database.url)
        
        # Load trading profiles
        success = await strategy_manager.load_profiles()
        if not success:
            logger.error("Failed to load trading profiles")
            return False
        
        # Get trading profile
        profile = strategy_manager.get_profile(profile_name)
        if not profile:
            logger.error(f"Profile '{profile_name}' not found")
            print(f"❌ Profile '{profile_name}' not found")
            print("Available profiles:")
            for name in strategy_manager.list_profiles():
                print(f"  • {name}")
            return False
        
        # Setup trading mode
        if trading_mode.lower() == "live":
            print("⚠️  LIVE TRADING MODE - REAL MONEY WILL BE USED")
            confirm = input("Type 'CONFIRM' to proceed with live trading: ")
            if confirm != "CONFIRM":
                print("❌ Live trading cancelled")
                return False
            
            # Initialize Binance client and set live mode
            binance_client = create_binance_client()
            if not await binance_client.test_connectivity():
                logger.error("Failed to connect to Binance API")
                print("❌ Cannot connect to Binance API")
                return False
            
            trading_mode_manager.set_live_mode(binance_client)
            print("🔴 LIVE TRADING MODE ACTIVE")
        
        else:
            # Paper trading mode
            initial_balance = Decimal('1000')  # $1000 starting balance
            trading_mode_manager.set_paper_mode(initial_balance)
            print(f"🟢 PAPER TRADING MODE ACTIVE (${initial_balance} virtual balance)")
        
        # Setup signal handlers for graceful shutdown
        setup_signal_handlers()
        
        # Start trading engine
        success = await trading_engine.start(profile)
        if not success:
            logger.error("Failed to start trading engine")
            print("❌ Failed to start trading engine")
            return False
        
        print(f"✅ Trading bot started successfully!")
        print(f"   Profile: {profile.name}")
        print(f"   Symbol: {profile.symbol}")
        print(f"   Strategy: {profile.strategy_name}")
        print(f"   Mode: {trading_mode.upper()}")
        print("\nPress Ctrl+C to stop gracefully...")
        
        # Keep running until stopped
        try:
            while trading_engine.state.value == "running":
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            print("\n🛑 Stopping trading bot...")
        
        return True
        
    except Exception as e:
        logger.error(f"Critical error in trading bot: {e}", exc_info=True)
        print(f"❌ Critical error: {e}")
        return False
    
    finally:
        # Ensure engine is stopped
        await trading_engine.stop()
        print("✅ Trading bot stopped safely")


async def show_status():
    """Show current trading engine status"""
    try:
        status = await trading_engine.get_status()
        
        print("\n" + "="*50)
        print("🤖 TRADING BOT STATUS")
        print("="*50)
        
        # Basic status
        state_icon = "🟢" if status['state'] == 'running' else "🔴"
        print(f"State: {state_icon} {status['state'].upper()}")
        
        # Trading mode
        if trading_mode_manager.is_live_mode():
            print(f"Mode: 🔴 LIVE TRADING")
        elif trading_mode_manager.is_paper_mode():
            print(f"Mode: 🟢 PAPER TRADING")
        else:
            print(f"Mode: ⚪ Not set")
        
        # Profile info
        if status.get('profile'):
            print(f"Profile: {status['profile']}")
            print(f"Symbol: {status['symbol']}")
            print(f"Strategy: {status['strategy']}")
        
        # Runtime info
        if status.get('uptime'):
            uptime_mins = int(status['uptime'] / 60)
            uptime_hours = uptime_mins // 60
            uptime_mins = uptime_mins % 60
            print(f"Uptime: {uptime_hours}h {uptime_mins}m")
        
        print(f"Trades executed: {status['stats']['trades_executed']}")
        
        # Position info
        if 'position' in status:
            pos = status['position']
            pnl_icon = "📈" if pos['unrealized_pnl'] > 0 else "📉"
            print(f"\n📊 CURRENT POSITION:")
            print(f"  Buy price: ${pos['buy_price']:.6f}")
            print(f"  Current price: ${pos['current_price']:.6f}")
            print(f"  Quantity: {pos['quantity']:.6f}")
            print(f"  P&L: {pnl_icon} ${pos['unrealized_pnl']:.2f}")
        else:
            print(f"\n📊 No open position")
        
        # Paper trading summary
        if trading_mode_manager.is_paper_mode() and hasattr(trading_mode_manager.current_mode, 'get_portfolio_summary'):
            portfolio = trading_mode_manager.current_mode.get_portfolio_summary({})
            print(f"\n📝 PAPER TRADING SUMMARY:")
            print(f"  Cash balance: ${portfolio['cash_balance']:.2f}")
            print(f"  Total value: ${portfolio['total_value']:.2f}")
            if portfolio['unrealized_pnl'] != 0:
                pnl_icon = "📈" if portfolio['unrealized_pnl'] > 0 else "📉"
                print(f"  Total P&L: {pnl_icon} ${portfolio['unrealized_pnl']:.2f}")
        
        print("="*50)
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        print(f"❌ Error getting status: {e}")


async def list_profiles():
    """List available trading profiles"""
    try:
        await strategy_manager.load_profiles()
        profiles = strategy_manager.list_profiles()
        
        print("\n" + "="*50)
        print("📋 AVAILABLE TRADING PROFILES")
        print("="*50)
        
        if not profiles:
            print("📭 No profiles found")
            print("\nTo create a profile, you can:")
            print("1. Use the old manage_profiles.py script")
            print("2. Create manually via strategy_manager")
            print("3. Use the Telegram bot interface")
        else:
            for profile_name in profiles:
                profile = strategy_manager.get_profile(profile_name)
                if profile:
                    status = "🟢 Active" if profile.is_active else "⚪ Inactive"
                    print(f"• {profile.name}")
                    print(f"  Symbol: {profile.symbol}")
                    print(f"  Strategy: {profile.strategy_name}")
                    print(f"  Timeframe: {profile.timeframe}")
                    print(f"  Status: {status}")
                    print(f"  Max position: ${profile.risk_config.max_position_size}")
                    print()
        
        print("="*50)
        
    except Exception as e:
        logger.error(f"Error listing profiles: {e}")
        print(f"❌ Error listing profiles: {e}")


async def create_demo_profile():
    """Create a demo profile for testing"""
    try:
        # Demo RSI+MACD profile
        strategy_config = strategy_manager.get_default_strategy_config('rsi_macd')
        risk_config = strategy_manager.get_default_risk_config()
        
        success = strategy_manager.create_profile(
            name="demo_xrp",
            symbol="XRPUSDT",
            strategy_name="rsi_macd",
            timeframe="5m",
            strategy_config=strategy_config,
            risk_config=risk_config
        )
        
        if success:
            await strategy_manager.save_profiles()
            print("✅ Created demo profile: demo_xrp")
            print("   Symbol: XRPUSDT")
            print("   Strategy: RSI + MACD")
            print("   Timeframe: 5m")
        else:
            print("❌ Failed to create demo profile")
            
    except Exception as e:
        logger.error(f"Error creating demo profile: {e}")
        print(f"❌ Error creating demo profile: {e}")


def create_arg_parser():
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description="Advanced Cryptocurrency Trading Bot v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py start demo_xrp                    # Start paper trading
  python main.py start demo_xrp --mode live        # Start live trading  
  python main.py status                            # Show current status
  python main.py profiles                          # List profiles
  python main.py create-demo                       # Create demo profile
  python main.py stop                              # Stop trading
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Start command
    start_parser = subparsers.add_parser('start', help='Start trading bot')
    start_parser.add_argument('profile', help='Trading profile name')
    start_parser.add_argument('--mode', choices=['paper', 'live'], default='paper',
                            help='Trading mode (default: paper)')
    
    # Other commands
    subparsers.add_parser('status', help='Show bot status')
    subparsers.add_parser('profiles', help='List available profiles')
    subparsers.add_parser('create-demo', help='Create demo profile')
    subparsers.add_parser('stop', help='Stop running bot')
    
    return parser


async def main():
    """Main entry point"""
    parser = create_arg_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Validate configuration
    if not settings.validate():
        logger.error("Configuration validation failed. Check your .env file.")
        print("❌ Configuration validation failed")
        print("Required: BINANCE_API_KEY, BINANCE_API_SECRET, TELEGRAM_TOKEN")
        sys.exit(1)
    
    try:
        if args.command == 'start':
            success = await start_trading_bot(args.profile, args.mode)
            sys.exit(0 if success else 1)
        
        elif args.command == 'status':
            await show_status()
        
        elif args.command == 'profiles':
            await list_profiles()
        
        elif args.command == 'create-demo':
            await create_demo_profile()
        
        elif args.command == 'stop':
            if trading_engine.state.value != "stopped":
                print("🛑 Stopping trading bot...")
                await trading_engine.stop()
                print("✅ Trading bot stopped")
            else:
                print("ℹ️  Trading bot is not running")
        
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        print("\n👋 Goodbye!")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Configure asyncio for Windows compatibility
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Run main function
    asyncio.run(main())