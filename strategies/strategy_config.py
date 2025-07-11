"""
Strategy Configuration Templates - Pre-built TradingView style strategies
"""
from typing import Dict, Any


class StrategyConfigs:
    """Pre-built strategy configurations"""

    @staticmethod
    def get_rsi_macd_ema_config() -> Dict[str, Any]:
        """Classic RSI + MACD + EMA filter strategy"""
        return {
            'name': 'RSI+MACD+EMA Classic',
            'description': 'Multi-indicator strategy with trend filter',
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
                        'buy_buffer_percent': 0.2,
                        'sell_buffer_percent': 0.2
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
                    'name': 'Medium Buy Signal',
                    'condition': 'RSI.oversold AND MACD.bullish',
                    'signal_type': 'buy',
                    'strength': 'MEDIUM'
                },
                {
                    'name': 'Strong Sell Signal',
                    'condition': 'RSI.overbought AND MACD.bearish',
                    'signal_type': 'sell',
                    'strength': 'STRONG'
                },
                {
                    'name': 'Medium Sell Signal',
                    'condition': 'RSI.overbought OR MACD.bearish_crossover',
                    'signal_type': 'sell',
                    'strength': 'MEDIUM'
                }
            ],
            'strategy_config': {
                'min_confidence': 0.6,
                'max_position_size': 0.1  # 10% of portfolio
            }
        }

    @staticmethod
    def get_simple_rsi_config() -> Dict[str, Any]:
        """Simple RSI-only strategy"""
        return {
            'name': 'Simple RSI',
            'description': 'Basic RSI oversold/overbought strategy',
            'indicators': [
                {
                    'type': 'RSI',
                    'config': {
                        'period': 14,
                        'oversold_threshold': 25,
                        'overbought_threshold': 75
                    }
                }
            ],
            'rules': [
                {
                    'name': 'RSI Oversold Buy',
                    'condition': 'RSI.oversold',
                    'signal_type': 'buy',
                    'strength': 'MEDIUM'
                },
                {
                    'name': 'RSI Overbought Sell',
                    'condition': 'RSI.overbought',
                    'signal_type': 'sell',
                    'strength': 'MEDIUM'
                }
            ]
        }

    @staticmethod
    def get_macd_crossover_config() -> Dict[str, Any]:
        """MACD crossover strategy"""
        return {
            'name': 'MACD Crossover',
            'description': 'Pure MACD signal line crossover strategy',
            'indicators': [
                {
                    'type': 'MACD',
                    'config': {
                        'fast_period': 12,
                        'slow_period': 26,
                        'signal_period': 9
                    }
                }
            ],
            'rules': [
                {
                    'name': 'MACD Bullish Crossover',
                    'condition': 'MACD.bullish_crossover',
                    'signal_type': 'buy',
                    'strength': 'STRONG'
                },
                {
                    'name': 'MACD Bearish Crossover',
                    'condition': 'MACD.bearish_crossover',
                    'signal_type': 'sell',
                    'strength': 'STRONG'
                }
            ]
        }

    @staticmethod
    def get_ema_trend_config() -> Dict[str, Any]:
        """EMA trend following strategy"""
        return {
            'name': 'EMA Trend Following',
            'description': 'Pure trend following with EMA buffers',
            'indicators': [
                {
                    'type': 'EMA',
                    'config': {
                        'period': 21,
                        'buy_buffer_percent': 0.5,   # Wider buffers for trend following
                        'sell_buffer_percent': 0.5
                    }
                }
            ],
            'rules': [
                {
                    'name': 'Trend Up',
                    'condition': 'EMA.price_above_buy_threshold',
                    'signal_type': 'buy',
                    'strength': 'MEDIUM'
                },
                {
                    'name': 'Trend Down',
                    'condition': 'EMA.price_below_sell_threshold',
                    'signal_type': 'sell',
                    'strength': 'MEDIUM'
                }
            ]
        }

    @staticmethod
    def get_conservative_config() -> Dict[str, Any]:
        """Conservative multi-confirmation strategy"""
        return {
            'name': 'Conservative Multi-Confirm',
            'description': 'Requires all indicators to agree for signals',
            'indicators': [
                {
                    'type': 'RSI',
                    'config': {
                        'period': 21,  # Longer period for less noise
                        'oversold_threshold': 25,
                        'overbought_threshold': 75
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
                        'period': 100,  # Longer term trend
                        'buy_buffer_percent': 0.1,
                        'sell_buffer_percent': 0.1
                    }
                }
            ],
            'rules': [
                {
                    'name': 'Ultra Conservative Buy',
                    'condition': 'RSI.oversold AND MACD.bullish_crossover AND EMA.price_above_buy_threshold',
                    'signal_type': 'buy',
                    'strength': 'STRONG'
                },
                {
                    'name': 'Ultra Conservative Sell',
                    'condition': 'RSI.overbought AND MACD.bearish_crossover AND EMA.price_below_sell_threshold',
                    'signal_type': 'sell',
                    'strength': 'STRONG'
                }
            ],
            'strategy_config': {
                'min_confidence': 0.8,  # Higher confidence threshold
                'max_position_size': 0.05  # Smaller position sizes
            }
        }

    @staticmethod
    def get_all_strategies() -> Dict[str, Dict[str, Any]]:
        """Get all pre-built strategy configurations"""
        return {
            'rsi_macd_ema': StrategyConfigs.get_rsi_macd_ema_config(),
            'simple_rsi': StrategyConfigs.get_simple_rsi_config(),
            'macd_crossover': StrategyConfigs.get_macd_crossover_config(),
            'ema_trend': StrategyConfigs.get_ema_trend_config(),
            'conservative': StrategyConfigs.get_conservative_config()
        }
