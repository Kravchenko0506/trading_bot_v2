"""
Strategy Factory - TradingView style strategy configuration system
"""
from typing import Dict, Any, List
from decimal import Decimal

from .custom_strategy import CustomStrategy, StrategyRule
from .indicators.rsi import RSI
from .indicators.macd import MACD
from .indicators.ema import EMA
from .indicators.sma import SMA
from .indicators.bollinger_bands import BollingerBands
from .base_strategy import SignalType, SignalStrength
from core.interfaces.trading_interfaces import IMarketDataService
from utils.logger import get_strategy_logger

logger = get_strategy_logger()


class StrategyFactory:
    """Factory for creating strategies from configuration"""

    INDICATOR_CLASSES = {
        'RSI': RSI,
        'MACD': MACD,
        'EMA': EMA,
        'SMA': SMA,
        'BollingerBands': BollingerBands,
    }

    @classmethod
    def create_custom_strategy(cls,
                               strategy_config: Dict[str, Any],
                               market_data: IMarketDataService) -> CustomStrategy:
        """Create custom strategy from configuration"""

        # Create indicators
        indicators = []
        for indicator_config in strategy_config['indicators']:
            indicator_type = indicator_config['type']
            indicator_class = cls.INDICATOR_CLASSES.get(indicator_type)

            if not indicator_class:
                raise ValueError(f"Unknown indicator type: {indicator_type}")

            indicator = indicator_class(indicator_config['config'])
            indicators.append(indicator)
            logger.info(f"Created indicator: {indicator.get_config_summary()}")

        # Create rules
        rules = []
        for rule_config in strategy_config['rules']:
            # Convert string strength to enum value
            strength_str = rule_config.get('strength', 'MEDIUM')
            if strength_str == 'WEAK':
                strength = SignalStrength.WEAK
            elif strength_str == 'STRONG':
                strength = SignalStrength.STRONG
            else:
                strength = SignalStrength.MEDIUM

            rule = StrategyRule(
                name=rule_config['name'],
                condition=rule_config['condition'],
                signal_type=SignalType(rule_config['signal_type']),
                strength=strength
            )
            rules.append(rule)
            logger.info(
                f"Created rule: {rule.name} -> {rule.signal_type.value}")

        # Create strategy
        strategy = CustomStrategy(
            config=strategy_config.get('strategy_config', {}),
            market_data=market_data,
            indicators=indicators,
            rules=rules
        )

        logger.info(
            f"Custom strategy created: {strategy_config.get('name', 'Unnamed')}")
        return strategy

    @classmethod
    def create_rsi_macd_strategy(cls, market_data: IMarketDataService) -> CustomStrategy:
        """Create the classic RSI+MACD strategy with EMA filter"""
        config = {
            'name': 'RSI+MACD+EMA Strategy',
            'indicators': [
                {
                    'type': 'RSI',
                    'config': {
                        'period': 14,
                        'oversold_threshold': 30,
                        'overbought_threshold': 70
                    }
                },
                {
                    'type': 'MACD',
                    'config': {
                        'fast_period': 12,
                        'slow_period': 26,
                        'signal_period': 9
                    }
                },
                {
                    'type': 'EMA',
                    'config': {
                        'period': 50,
                        'buy_buffer_percent': 0.2,   # 0.2% buffer
                        'sell_buffer_percent': 0.2   # 0.2% buffer
                    }
                }
            ],
            'rules': [
                {
                    'name': 'Strong Buy Signal',
                    'condition': 'RSI.oversold AND MACD.bullish AND EMA.price_above_buy_threshold',
                    'signal_type': 'buy',
                    'strength': 'STRONG'
                },
                {
                    'name': 'Strong Sell Signal',
                    'condition': 'RSI.overbought AND MACD.bearish',
                    'signal_type': 'sell',
                    'strength': 'STRONG'
                }
            ]
        }

        return cls.create_custom_strategy(config, market_data)

    @classmethod
    def get_available_indicators(cls) -> Dict[str, Dict[str, Any]]:
        """Get list of available indicators with their config schemas"""
        return {
            'RSI': {
                'description': 'Relative Strength Index - momentum oscillator',
                'required_config': ['period', 'oversold_threshold', 'overbought_threshold'],
                'default_config': {
                    'period': 14,
                    'oversold_threshold': 30,
                    'overbought_threshold': 70
                },
                'config_description': {
                    'period': 'Number of periods for RSI calculation',
                    'oversold_threshold': 'RSI level considered oversold (0-100)',
                    'overbought_threshold': 'RSI level considered overbought (0-100)'
                }
            },
            'MACD': {
                'description': 'Moving Average Convergence Divergence - trend indicator',
                'required_config': ['fast_period', 'slow_period', 'signal_period'],
                'default_config': {
                    'fast_period': 12,
                    'slow_period': 26,
                    'signal_period': 9
                },
                'config_description': {
                    'fast_period': 'Fast EMA period',
                    'slow_period': 'Slow EMA period',
                    'signal_period': 'Signal line EMA period'
                }
            },
            'EMA': {
                'description': 'Exponential Moving Average - trend filter with buffers',
                'required_config': ['period'],
                'default_config': {
                    'period': 50,
                    'buy_buffer_percent': 0.2,
                    'sell_buffer_percent': 0.2
                },
                'config_description': {
                    'period': 'EMA period',
                    'buy_buffer_percent': 'Buffer above EMA for buy signals (%)',
                    'sell_buffer_percent': 'Buffer below EMA for sell signals (%)'
                }
            },
            'SMA': {
                'description': 'Simple Moving Average - trend filter with buffers',
                'required_config': ['period'],
                'default_config': {
                    'period': 20,
                    'buy_buffer_percent': 0.0,
                    'sell_buffer_percent': 0.0
                },
                'config_description': {
                    'period': 'SMA period',
                    'buy_buffer_percent': 'Buffer below SMA for buy signals (%)',
                    'sell_buffer_percent': 'Buffer above SMA for sell signals (%)'
                }
            },
            'BollingerBands': {
                'description': 'Bollinger Bands - volatility and mean reversion indicator',
                'required_config': ['period', 'std_multiplier'],
                'default_config': {
                    'period': 20,
                    'std_multiplier': 2.0,
                    'squeeze_threshold_percent': 2.0
                },
                'config_description': {
                    'period': 'Period for SMA and standard deviation',
                    'std_multiplier': 'Standard deviation multiplier for bands',
                    'squeeze_threshold_percent': 'Threshold for squeeze detection (%)'
                }
            }
        }

    @classmethod
    def create_simple_rsi_strategy(cls, market_data: IMarketDataService) -> CustomStrategy:
        """Create simple RSI-only strategy"""
        config = {
            'name': 'Simple RSI Strategy',
            'indicators': [
                {
                    'type': 'RSI',
                    'config': {
                        'period': 14,
                        'oversold_threshold': 30,
                        'overbought_threshold': 70
                    }
                }
            ],
            'rules': [
                {
                    'name': 'RSI Buy Signal',
                    'condition': 'RSI.oversold',
                    'signal_type': 'buy',
                    'strength': 'MEDIUM'
                },
                {
                    'name': 'RSI Sell Signal',
                    'condition': 'RSI.overbought',
                    'signal_type': 'sell',
                    'strength': 'MEDIUM'
                }
            ]
        }

        return cls.create_custom_strategy(config, market_data)

    @classmethod
    def create_bollinger_rsi_strategy(cls, market_data: IMarketDataService) -> CustomStrategy:
        """Create Bollinger Bands + RSI strategy"""
        config = {
            'name': 'Bollinger Bands + RSI Strategy',
            'indicators': [
                {
                    'type': 'BollingerBands',
                    'config': {
                        'period': 20,
                        'std_multiplier': 2.0,
                        'squeeze_threshold_percent': 2.0
                    }
                },
                {
                    'type': 'RSI',
                    'config': {
                        'period': 14,
                        'oversold_threshold': 30,
                        'overbought_threshold': 70
                    }
                }
            ],
            'rules': [
                {
                    'name': 'BB Oversold + RSI Oversold',
                    'condition': 'BollingerBands.oversold AND RSI.oversold',
                    'signal_type': 'buy',
                    'strength': 'STRONG'
                },
                {
                    'name': 'BB Overbought + RSI Overbought',
                    'condition': 'BollingerBands.overbought AND RSI.overbought',
                    'signal_type': 'sell',
                    'strength': 'STRONG'
                },
                {
                    'name': 'BB Breakout Up',
                    'condition': 'BollingerBands.price_above_upper',
                    'signal_type': 'buy',
                    'strength': 'MEDIUM'
                },
                {
                    'name': 'BB Breakdown',
                    'condition': 'BollingerBands.price_below_lower',
                    'signal_type': 'sell',
                    'strength': 'MEDIUM'
                }
            ]
        }

        return cls.create_custom_strategy(config, market_data)

    @classmethod
    def create_sma_crossover_strategy(cls, market_data: IMarketDataService) -> CustomStrategy:
        """Create SMA crossover strategy with fast and slow SMA"""
        config = {
            'name': 'SMA Crossover Strategy',
            'indicators': [
                {
                    'type': 'SMA',
                    'config': {
                        'period': 10,  # Fast SMA
                        'buy_buffer_percent': 0.1,
                        'sell_buffer_percent': 0.1
                    }
                },
                {
                    'type': 'SMA',
                    'config': {
                        'period': 30,  # Slow SMA
                        'buy_buffer_percent': 0.0,
                        'sell_buffer_percent': 0.0
                    }
                },
                {
                    'type': 'RSI',
                    'config': {
                        'period': 14,
                        'oversold_threshold': 40,  # More conservative
                        'overbought_threshold': 60
                    }
                }
            ],
            'rules': [
                {
                    'name': 'SMA Bullish + RSI Confirm',
                    'condition': 'SMA.price_above_buy_threshold AND RSI.oversold',
                    'signal_type': 'buy',
                    'strength': 'STRONG'
                },
                {
                    'name': 'SMA Bearish + RSI Confirm',
                    'condition': 'SMA.price_below_sell_threshold AND RSI.overbought',
                    'signal_type': 'sell',
                    'strength': 'STRONG'
                }
            ]
        }

        return cls.create_custom_strategy(config, market_data)
