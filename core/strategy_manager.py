# core/strategy_manager.py
"""
Strategy and profile management system.
Handles loading, validation, and creation of trading profiles and strategies.
"""
import json
from decimal import Decimal
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from core.risk_manager import RiskConfig
from strategies.base_strategy import BaseStrategy, StrategyConfig
from strategies.rsi_macd import RSIMacdStrategy, RSIMacdConfig
from database.connection import get_db_session
from database.models import TradingProfile as DBTradingProfile
from utils.logger import get_system_logger

logger = get_system_logger()


@dataclass
class TradingProfile:
    """Trading profile configuration"""
    name: str
    symbol: str
    strategy_name: str
    timeframe: str
    
    # Strategy configuration
    strategy_config: Dict[str, Any]
    
    # Risk management
    risk_config: RiskConfig
    
    # Status
    is_active: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'name': self.name,
            'symbol': self.symbol,
            'strategy_name': self.strategy_name,
            'timeframe': self.timeframe,
            'strategy_config': self.strategy_config,
            'risk_config': asdict(self.risk_config),
            'is_active': self.is_active
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradingProfile':
        """Create from dictionary"""
        risk_data = data.get('risk_config', {})
        risk_config = RiskConfig(
            use_stop_loss=risk_data.get('use_stop_loss', True),
            stop_loss_ratio=Decimal(str(risk_data.get('stop_loss_ratio', '-0.02'))),
            use_take_profit=risk_data.get('use_take_profit', True),
            take_profit_ratio=Decimal(str(risk_data.get('take_profit_ratio', '0.05'))),
            use_min_profit=risk_data.get('use_min_profit', True),
            min_profit_ratio=Decimal(str(risk_data.get('min_profit_ratio', '0.01'))),
            max_position_size=Decimal(str(risk_data.get('max_position_size', '100'))),
            min_trade_amount=Decimal(str(risk_data.get('min_trade_amount', '10'))),
            allow_loss_sells=risk_data.get('allow_loss_sells', False)
        )
        
        return cls(
            name=data['name'],
            symbol=data['symbol'],
            strategy_name=data['strategy_name'],
            timeframe=data['timeframe'],
            strategy_config=data.get('strategy_config', {}),
            risk_config=risk_config,
            is_active=data.get('is_active', False)
        )


class StrategyManager:
    """
    Manages trading strategies and profiles.
    Handles creation, validation, loading, and storage.
    """
    
    def __init__(self):
        self.profiles: Dict[str, TradingProfile] = {}
        self.available_strategies = {
            'rsi_macd': 'RSI + MACD combination strategy',
            'grid': 'Grid trading for sideways markets',
            'dca': 'Dollar Cost Averaging strategy'
        }
        self.config_file = Path('config/profiles.json')
        
        logger.info("Strategy manager initialized")
    
    async def load_profiles(self) -> bool:
        """Load all profiles from database and config file"""
        try:
            # Try loading from database first
            success = await self._load_from_database()
            if success and self.profiles:
                logger.info(f"Loaded {len(self.profiles)} profiles from database")
                return True
            
            # Fallback to JSON file
            success = await self._load_from_json()
            if success:
                logger.info(f"Loaded {len(self.profiles)} profiles from JSON file")
                # Migrate to database if needed
                await self._migrate_to_database()
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to load profiles: {e}")
            return False
    
    async def save_profiles(self) -> bool:
        """Save all profiles to database"""
        try:
            async with get_db_session() as session:
                # Clear existing profiles
                await session.execute("DELETE FROM profiles")
                
                # Save current profiles
                for profile in self.profiles.values():
                    db_profile = DBTradingProfile(
                        name=profile.name,
                        symbol=profile.symbol,
                        strategy=profile.strategy_name,
                        timeframe=profile.timeframe,
                        config=json.dumps(profile.strategy_config),
                        use_stop_loss=profile.risk_config.use_stop_loss,
                        stop_loss_ratio=profile.risk_config.stop_loss_ratio,
                        use_take_profit=profile.risk_config.use_take_profit,
                        take_profit_ratio=profile.risk_config.take_profit_ratio,
                        min_profit_ratio=profile.risk_config.min_profit_ratio,
                        max_position_size=profile.risk_config.max_position_size,
                        is_active=profile.is_active
                    )
                    session.add(db_profile)
                
                await session.commit()
                logger.info(f"Saved {len(self.profiles)} profiles to database")
                return True
        
        except Exception as e:
            logger.error(f"Failed to save profiles: {e}")
            return False
    
    def get_profile(self, name: str) -> Optional[TradingProfile]:
        """Get profile by name"""
        return self.profiles.get(name)
    
    def list_profiles(self) -> List[str]:
        """Get list of profile names"""
        return list(self.profiles.keys())
    
    def create_profile(
        self,
        name: str,
        symbol: str,
        strategy_name: str,
        timeframe: str,
        strategy_config: Dict[str, Any],
        risk_config: RiskConfig
    ) -> bool:
        """Create new trading profile"""
        try:
            # Validate inputs
            if not self._validate_profile_data(name, symbol, strategy_name, timeframe):
                return False
            
            # Check if profile already exists
            if name in self.profiles:
                logger.warning(f"Profile '{name}' already exists")
                return False
            
            # Create profile
            profile = TradingProfile(
                name=name,
                symbol=symbol,
                strategy_name=strategy_name,
                timeframe=timeframe,
                strategy_config=strategy_config,
                risk_config=risk_config
            )
            
            # Validate strategy config
            if not self._validate_strategy_config(strategy_name, strategy_config):
                return False
            
            self.profiles[name] = profile
            logger.info(f"Created profile: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create profile '{name}': {e}")
            return False
    
    def update_profile(
        self,
        name: str,
        **updates
    ) -> bool:
        """Update existing profile"""
        try:
            if name not in self.profiles:
                logger.error(f"Profile '{name}' not found")
                return False
            
            profile = self.profiles[name]
            
            # Update fields
            for key, value in updates.items():
                if key == 'risk_config' and isinstance(value, dict):
                    # Update risk config
                    for risk_key, risk_value in value.items():
                        if hasattr(profile.risk_config, risk_key):
                            setattr(profile.risk_config, risk_key, risk_value)
                elif hasattr(profile, key):
                    setattr(profile, key, value)
            
            logger.info(f"Updated profile: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update profile '{name}': {e}")
            return False
    
    def delete_profile(self, name: str) -> bool:
        """Delete profile"""
        try:
            if name not in self.profiles:
                logger.error(f"Profile '{name}' not found")
                return False
            
            # Check if profile is active
            if self.profiles[name].is_active:
                logger.error(f"Cannot delete active profile '{name}'")
                return False
            
            del self.profiles[name]
            logger.info(f"Deleted profile: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete profile '{name}': {e}")
            return False
    
    def create_strategy(self, profile: TradingProfile) -> Optional[BaseStrategy]:
        """Create strategy instance from profile"""
        try:
            strategy_name = profile.strategy_name.lower()
            
            if strategy_name == 'rsi_macd':
                from strategies.rsi_macd import RSIMacdStrategy, RSIMacdConfig
                config = RSIMacdConfig(
                    symbol=profile.symbol,
                    timeframe=profile.timeframe,
                    **profile.strategy_config
                )
                return RSIMacdStrategy(config)
            
            elif strategy_name == 'grid':
                from strategies.grid_strategy import GridTradingStrategy, GridConfig
                config = GridConfig(
                    symbol=profile.symbol,
                    timeframe=profile.timeframe,
                    **profile.strategy_config
                )
                return GridTradingStrategy(config)
            
            elif strategy_name == 'dca':
                from strategies.dca_strategy import DCAStrategy, DCAConfig
                config = DCAConfig(
                    symbol=profile.symbol,
                    timeframe=profile.timeframe,
                    **profile.strategy_config
                )
                return DCAStrategy(config)
            
            else:
                logger.error(f"Unknown strategy: {strategy_name}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create strategy for profile '{profile.name}': {e}")
            return None
    
    def get_default_strategy_config(self, strategy_name: str) -> Dict[str, Any]:
        """Get default configuration for strategy"""
        if strategy_name.lower() == 'rsi_macd':
            return {
                'use_rsi': True,
                'rsi_period': 14,
                'rsi_oversold': '30',
                'rsi_overbought': '70',
                'use_macd': True,
                'macd_fast_period': 12,
                'macd_slow_period': 26,
                'macd_signal_period': 9,
                'use_macd_for_buy': True,
                'use_macd_for_sell': True,
                'use_ema': False,
                'ema_period': 50,
                'ema_buy_buffer': '0.002',
                'ema_sell_buffer': '0.002'
            }
        
        elif strategy_name.lower() == 'grid':
            return {
                'grid_size': 5,
                'grid_spacing': '0.01',
                'position_per_grid': '20',
                'max_drawdown': '0.15',
                'rebalance_threshold': '0.05',
                'volatility_threshold': '0.02',
                'trend_filter_period': 50,
                'max_trend_strength': '0.03'
            }
        
        elif strategy_name.lower() == 'dca':
            return {
                'initial_buy_amount': '50',
                'dca_amount': '25',
                'max_dca_orders': 5,
                'dca_trigger_percent': '0.05',
                'min_time_between_dca': 60,
                'profit_target_percent': '0.03',
                'stop_loss_percent': '0.15',
                'rsi_oversold_threshold': '40',
                'volume_spike_threshold': '1.5',
                'max_total_investment': '300',
                'emergency_exit_percent': '0.25'
            }
        
        return {}
    
    def get_default_risk_config(self) -> RiskConfig:
        """Get default risk configuration"""
        return RiskConfig(
            use_stop_loss=True,
            stop_loss_ratio=Decimal('-0.02'),
            use_take_profit=True,
            take_profit_ratio=Decimal('0.05'),
            use_min_profit=True,
            min_profit_ratio=Decimal('0.01'),
            max_position_size=Decimal('100'),
            min_trade_amount=Decimal('10'),
            allow_loss_sells=False
        )
    
    async def _load_from_database(self) -> bool:
        """Load profiles from database"""
        try:
            async with get_db_session() as session:
                result = await session.execute("SELECT * FROM profiles")
                rows = result.fetchall()
                
                for row in rows:
                    strategy_config = json.loads(row.config) if row.config else {}
                    
                    risk_config = RiskConfig(
                        use_stop_loss=row.use_stop_loss,
                        stop_loss_ratio=row.stop_loss_ratio,
                        use_take_profit=row.use_take_profit,
                        take_profit_ratio=row.take_profit_ratio,
                        min_profit_ratio=row.min_profit_ratio,
                        max_position_size=row.max_position_size,
                        min_trade_amount=Decimal('10'),  # Default
                        allow_loss_sells=False  # Default
                    )
                    
                    profile = TradingProfile(
                        name=row.name,
                        symbol=row.symbol,
                        strategy_name=row.strategy,
                        timeframe=row.timeframe,
                        strategy_config=strategy_config,
                        risk_config=risk_config,
                        is_active=row.is_active
                    )
                    
                    self.profiles[row.name] = profile
                
                return True
                
        except Exception as e:
            logger.warning(f"Could not load from database: {e}")
            return False
    
    async def _load_from_json(self) -> bool:
        """Load profiles from JSON file (legacy)"""
        try:
            if not self.config_file.exists():
                logger.info("No JSON config file found")
                return True
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for name, config in data.items():
                # Convert legacy format to new format
                profile_data = self._convert_legacy_config(name, config)
                profile = TradingProfile.from_dict(profile_data)
                self.profiles[name] = profile
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load JSON config: {e}")
            return False
    
    async def _migrate_to_database(self):
        """Migrate profiles from JSON to database"""
        if self.profiles:
            await self.save_profiles()
            logger.info("Migrated profiles from JSON to database")
    
    def _validate_profile_data(self, name: str, symbol: str, strategy_name: str, timeframe: str) -> bool:
        """Validate basic profile data"""
        if not name or not name.strip():
            logger.error("Profile name cannot be empty")
            return False
        
        if not symbol or not symbol.strip():
            logger.error("Symbol cannot be empty")
            return False
        
        if strategy_name not in self.available_strategies:
            logger.error(f"Unknown strategy: {strategy_name}")
            return False
        
        valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d']
        if timeframe not in valid_timeframes:
            logger.error(f"Invalid timeframe: {timeframe}")
            return False
        
        return True
    
    def _validate_strategy_config(self, strategy_name: str, config: Dict[str, Any]) -> bool:
        """Validate strategy-specific configuration"""
        try:
            if strategy_name.lower() == 'rsi_macd':
                # Create temp config to validate
                temp_config = RSIMacdConfig(
                    symbol="TEST",
                    timeframe="5m",
                    **config
                )
                # If no exception raised, config is valid
                return True
            
            return True
            
        except Exception as e:
            logger.error(f"Invalid strategy config: {e}")
            return False
    
    def _convert_legacy_config(self, name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Convert legacy JSON config to new format"""
        # Extract strategy config
        strategy_config = {}
        risk_config = {}
        
        # Map legacy fields to new structure
        strategy_fields = [
            'use_rsi', 'rsi_period', 'rsi_oversold', 'rsi_overbought',
            'use_macd', 'macd_fast_period', 'macd_slow_period', 'macd_signal_period',
            'use_macd_for_buy', 'use_macd_for_sell', 'use_ema', 'ema_period'
        ]
        
        risk_fields = [
            'use_stop_loss', 'stop_loss_ratio', 'use_take_profit', 'take_profit_ratio',
            'min_profit_ratio', 'max_position_size', 'min_trade_amount'
        ]
        
        for field in strategy_fields:
            if field in config:
                strategy_config[field] = config[field]
        
        for field in risk_fields:
            if field in config:
                risk_config[field] = config[field]
        
        return {
            'name': name,
            'symbol': config.get('symbol', ''),
            'strategy_name': 'rsi_macd',  # Default for legacy
            'timeframe': config.get('timeframe', '5m'),
            'strategy_config': strategy_config,
            'risk_config': risk_config,
            'is_active': False
        }


# Global instance
strategy_manager = StrategyManager()