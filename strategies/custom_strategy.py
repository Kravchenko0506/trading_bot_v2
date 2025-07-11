"""
Custom Strategy - TradingView style strategy builder with rules
"""
from decimal import Decimal
from typing import Dict, Any, List
from dataclasses import dataclass

from .base_strategy import BaseStrategy, TradingSignal, SignalType, SignalStrength, StrategyConfig
from .indicators.base_indicator import BaseIndicator
from core.interfaces.trading_interfaces import IMarketDataService
from utils.logger import get_strategy_logger

logger = get_strategy_logger()


@dataclass
class StrategyRule:
    """Rule for combining indicator signals"""
    name: str
    condition: str  # e.g., "RSI.oversold AND MACD.bullish AND EMA.price_above_buy_threshold"
    signal_type: SignalType
    strength: SignalStrength


class CustomStrategy(BaseStrategy):
    """Strategy builder that combines multiple indicators"""

    def __init__(self,
                 config: Dict[str, Any],
                 market_data: IMarketDataService,
                 indicators: List[BaseIndicator],
                 rules: List[StrategyRule]):

        # Create StrategyConfig from dict
        strategy_config = StrategyConfig(
            symbol=config.get('symbol', 'BTCUSDT'),
            timeframe=config.get('timeframe', '1h'),
            min_history_required=config.get('min_history_required', 100)
        )

        super().__init__(strategy_config)
        self.market_data = market_data
        self.indicators = indicators
        self.rules = rules
        self.indicator_data = {}

        logger.info(
            f"Custom strategy created with {len(indicators)} indicators and {len(rules)} rules")
        for indicator in indicators:
            logger.info(f"  - {indicator.get_config_summary()}")

    def get_required_history(self) -> int:
        """Return maximum history required by any indicator"""
        if not self.indicators:
            return 50
        return max(indicator.get_required_history_length() for indicator in self.indicators)

    async def analyze(self, current_price: Decimal) -> TradingSignal:
        """Analyze using all indicators and rules"""
        if not self.has_sufficient_history():
            return TradingSignal(
                signal=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                price=current_price,
                reason="Insufficient price history",
                confidence=0.0
            )

        # Calculate all indicator values
        await self._calculate_all_indicators()

        # Evaluate rules to find matching signal
        for rule in self.rules:
            if self._evaluate_rule_condition(rule.condition):
                reason = self._build_reason_string(rule)
                confidence = self._calculate_confidence(rule)

                logger.info(
                    f"Rule matched: {rule.name} -> {rule.signal_type.value}")

                return TradingSignal(
                    signal=rule.signal_type,
                    strength=rule.strength,
                    price=current_price,
                    reason=reason,
                    confidence=confidence,
                    indicators=self.indicator_data.copy()
                )

        # No rules matched
        return TradingSignal(
            signal=SignalType.HOLD,
            strength=SignalStrength.WEAK,
            price=current_price,
            reason="No trading rules matched current conditions",
            confidence=0.5,
            indicators=self.indicator_data.copy()
        )

    async def _calculate_all_indicators(self):
        """Calculate values for all indicators"""
        prices = self.price_history

        for indicator in self.indicators:
            try:
                indicator_result = await indicator.calculate(prices)
                signal = indicator.get_signal(indicator_result, prices[-1])

                self.indicator_data[indicator.name] = {
                    'data': indicator_result,
                    'signal': signal,
                    'config': indicator.config
                }

            except Exception as e:
                logger.error(f"Error calculating {indicator.name}: {e}")
                self.indicator_data[indicator.name] = {
                    'data': {'error': str(e)},
                    'signal': SignalType.HOLD,
                    'config': indicator.config
                }

    def _evaluate_rule_condition(self, condition: str) -> bool:
        """Evaluate rule condition string"""
        try:
            # Replace indicator references with actual values
            # Example: "RSI.oversold AND MACD.bullish AND SMA.price_above_buy_threshold"

            evaluation_string = condition

            # Create a list of all patterns to replace to avoid conflicts
            replacements = []

            # First pass: Collect all boolean data field replacements
            for indicator_name, indicator_info in self.indicator_data.items():
                data = indicator_info['data']

                # Replace data field references - check all boolean fields in data
                for key, value in data.items():
                    if isinstance(value, bool):
                        pattern = f"{indicator_name}.{key}"
                        if pattern in evaluation_string:
                            replacements.append((pattern, str(value)))

            # Second pass: Collect signal references (bullish/bearish map to buy/sell)
            for indicator_name, indicator_info in self.indicator_data.items():
                signal = indicator_info['signal']

                bullish_pattern = f"{indicator_name}.bullish"
                bearish_pattern = f"{indicator_name}.bearish"

                if bullish_pattern in evaluation_string:
                    replacements.append(
                        (bullish_pattern, str(signal == SignalType.BUY)))
                if bearish_pattern in evaluation_string:
                    replacements.append(
                        (bearish_pattern, str(signal == SignalType.SELL)))

            # Sort replacements by pattern length (longest first) to avoid partial replacements
            replacements.sort(key=lambda x: len(x[0]), reverse=True)

            # Apply all replacements
            for pattern, replacement in replacements:
                evaluation_string = evaluation_string.replace(
                    pattern, replacement)

            # Replace logical operators
            evaluation_string = evaluation_string.replace(" AND ", " and ")
            evaluation_string = evaluation_string.replace(" OR ", " or ")
            evaluation_string = evaluation_string.replace(" NOT ", " not ")

            # Safely evaluate the condition
            return eval(evaluation_string)

        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {e}")
            return False

    def _build_reason_string(self, rule: StrategyRule) -> str:
        """Build human-readable reason for signal"""
        active_conditions = []

        for indicator_name, indicator_info in self.indicator_data.items():
            signal = indicator_info['signal']
            data = indicator_info['data']

            if signal == SignalType.BUY:
                if indicator_name == "RSI" and data.get('oversold'):
                    active_conditions.append(
                        f"RSI oversold ({data['value']:.1f})")
                elif indicator_name == "MACD" and data.get('bullish_crossover'):
                    active_conditions.append("MACD bullish crossover")
                elif indicator_name == "EMA" and data.get('price_above_buy_threshold'):
                    active_conditions.append(f"Price above EMA+buffer")

            elif signal == SignalType.SELL:
                if indicator_name == "RSI" and data.get('overbought'):
                    active_conditions.append(
                        f"RSI overbought ({data['value']:.1f})")
                elif indicator_name == "MACD" and data.get('bearish_crossover'):
                    active_conditions.append("MACD bearish crossover")
                elif indicator_name == "EMA" and data.get('price_below_sell_threshold'):
                    active_conditions.append(f"Price below EMA-buffer")

        return f"{rule.name}: {' + '.join(active_conditions)}"

    def _calculate_confidence(self, rule: StrategyRule) -> float:
        """Calculate confidence based on how many indicators agree"""
        total_indicators = len(self.indicators)
        agreeing_indicators = 0

        for indicator_info in self.indicator_data.values():
            if indicator_info['signal'] == rule.signal_type:
                agreeing_indicators += 1

        # Base confidence from agreement ratio
        agreement_confidence = agreeing_indicators / total_indicators

        # Boost confidence for strong signals
        if rule.strength == SignalStrength.STRONG:
            agreement_confidence *= 1.2
        elif rule.strength == SignalStrength.WEAK:
            agreement_confidence *= 0.8

        return min(agreement_confidence, 1.0)

    async def run(self):
        """Run the custom strategy with real market data"""
        logger.info(f"Starting {self.name} strategy for {self.config.symbol}")

        try:
            # Get current price from market data
            logger.info("Getting current price...")
            current_price = await self.market_data.get_current_price(self.config.symbol)
            logger.info(f"Current price: {current_price}")

            # Get historical data for indicators
            logger.info("Getting historical kline data...")
            klines = await self.market_data.get_klines(self.config.symbol, self.config.timeframe, 100)
            if klines:
                prices = [Decimal(str(kline['close'])) for kline in klines]
                self.update_price_history(prices)
                logger.info(f"Loaded {len(prices)} price candles")
            else:
                logger.warning("No kline data received")
                return

            # Analyze with indicators
            logger.info("Starting strategy analysis...")
            signal = await self.analyze(current_price)
            logger.info("Analysis completed")

            logger.info(f"Strategy analysis result: {signal.signal.value} "
                        f"(strength: {signal.strength.name}, confidence: {signal.confidence:.2f})")
            logger.info(f"Reason: {signal.reason}")

            if signal.indicators:
                logger.info("Indicator states:")
                for name, data in signal.indicators.items():
                    logger.info(
                        f"  {name}: {data['signal'].value} - {data['data']}")

            logger.info("Strategy run completed successfully")

        except Exception as e:
            logger.error(f"Error in strategy run: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
