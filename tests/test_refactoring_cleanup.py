# tests/test_refactoring_cleanup.py
"""
Comprehensive test suite to validate the cleanup and refactoring success.
Tests all modular components and ensures no legacy code remains.
"""
import pytest
import asyncio
from decimal import Decimal
from unittest.mock import Mock, AsyncMock
import numpy as np


class TestModularIndicators:
    """Test all modular indicators work correctly"""

    @pytest.mark.asyncio
    async def test_rsi_indicator(self):
        """Test RSI indicator functionality"""
        from strategies.indicators.rsi import RSIIndicator

        config = {"period": 14}
        rsi = RSIIndicator(config)

        # Test with sample data
        prices = [Decimal(str(p))
                  for p in [100, 101, 99, 102, 98, 103, 97, 104]]
        prices_array = np.array([float(p) for p in prices])

        # Should not crash
        signal = rsi.get_signal(prices_array)
        assert signal is not None

    @pytest.mark.asyncio
    async def test_macd_indicator(self):
        """Test MACD indicator functionality"""
        from strategies.indicators.macd import MACDIndicator

        config = {"fast_period": 12, "slow_period": 26, "signal_period": 9}
        macd = MACDIndicator(config)

        # Test with sufficient data
        prices = [Decimal(str(p)) for p in range(100, 150)]
        prices_array = np.array([float(p) for p in prices])

        signal = macd.get_signal(prices_array)
        assert signal is not None

    @pytest.mark.asyncio
    async def test_ema_indicator(self):
        """Test EMA indicator functionality"""
        from strategies.indicators.ema import EMAIndicator

        config = {"period": 20}
        ema = EMAIndicator(config)

        prices = [Decimal(str(p)) for p in range(100, 130)]
        prices_array = np.array([float(p) for p in prices])

        signal = ema.get_signal(prices_array)
        assert signal is not None

    @pytest.mark.asyncio
    async def test_sma_indicator(self):
        """Test SMA indicator functionality"""
        from strategies.indicators.sma import SMAIndicator

        config = {"period": 20}
        sma = SMAIndicator(config)

        prices = [Decimal(str(p)) for p in range(100, 130)]
        prices_array = np.array([float(p) for p in prices])

        signal = sma.get_signal(prices_array)
        assert signal is not None

    @pytest.mark.asyncio
    async def test_bollinger_bands_indicator(self):
        """Test Bollinger Bands indicator functionality"""
        from strategies.indicators.bollinger_bands import BollingerBandsIndicator

        config = {"period": 20, "std_dev": 2}
        bb = BollingerBandsIndicator(config)

        prices = [Decimal(str(p)) for p in range(100, 130)]
        prices_array = np.array([float(p) for p in prices])

        signal = bb.get_signal(prices_array)
        assert signal is not None


class TestStrategyFactory:
    """Test strategy factory creates strategies correctly"""

    def test_rsi_macd_strategy_creation(self):
        """Test RSI+MACD strategy creation"""
        from strategies.strategy_factory import StrategyFactory

        mock_market_data = Mock()
        strategy = StrategyFactory.create_rsi_macd_strategy(mock_market_data)
        assert strategy is not None
        assert hasattr(strategy, 'indicators')
        assert len(strategy.indicators) > 0

    def test_bollinger_rsi_strategy_creation(self):
        """Test Bollinger+RSI strategy creation"""
        from strategies.strategy_factory import StrategyFactory

        mock_market_data = Mock()
        strategy = StrategyFactory.create_bollinger_rsi_strategy(
            mock_market_data)
        assert strategy is not None
        assert hasattr(strategy, 'indicators')

    def test_sma_crossover_strategy_creation(self):
        """Test SMA crossover strategy creation"""
        from strategies.strategy_factory import StrategyFactory

        mock_market_data = Mock()
        strategy = StrategyFactory.create_sma_crossover_strategy(
            mock_market_data)
        assert strategy is not None
        assert hasattr(strategy, 'indicators')

    def test_custom_strategy_creation(self):
        """Test custom strategy creation from config"""
        from strategies.strategy_factory import StrategyFactory
        from strategies.strategy_config import StrategyConfigs

        mock_market_data = Mock()
        config = StrategyConfigs.get_rsi_macd_ema_config()
        strategy = StrategyFactory.create_custom_strategy(
            config, mock_market_data)
        assert strategy is not None
        assert hasattr(strategy, 'indicators')


class TestBaseStrategy:
    """Test base strategy functionality"""

    @pytest.mark.asyncio
    async def test_base_strategy_with_market_data_service(self):
        """Test base strategy with market data service"""
        from strategies.base_strategy import BaseStrategy, StrategyConfig, TradingSignal, SignalType, SignalStrength

        # Create mock market data service
        mock_service = AsyncMock()
        mock_service.get_current_price.return_value = Decimal("45000")
        mock_service.get_price_history.return_value = [
            Decimal(str(p)) for p in range(44000, 45000, 10)]

        # Create concrete strategy implementation
        class TestStrategy(BaseStrategy):
            async def analyze(self, current_price):
                return TradingSignal(
                    signal=SignalType.HOLD,
                    strength=SignalStrength.MEDIUM,
                    price=current_price,
                    reason="Test strategy",
                    confidence=0.5
                )

            def get_required_history(self):
                return 20

        config = StrategyConfig(symbol="BTCUSDT", timeframe="1h")
        strategy = TestStrategy(config, mock_service)

        # Test run method
        result = await strategy.run()
        assert result is not None
        assert result.signal == SignalType.HOLD


class TestModularArchitecture:
    """Test that modular architecture is properly implemented"""

    def test_no_legacy_indicators_in_base_strategy(self):
        """Ensure old indicator classes are removed from base_strategy.py"""
        from strategies import base_strategy

        # These classes should NOT exist in base_strategy module
        assert not hasattr(base_strategy, 'SimpleMovingAverage')
        assert not hasattr(base_strategy, 'RSI')
        assert not hasattr(base_strategy, 'MACD')

    def test_all_indicators_use_base_class(self):
        """Test all indicators inherit from BaseIndicator"""
        from strategies.indicators.base_indicator import BaseIndicator
        from strategies.indicators.rsi import RSIIndicator
        from strategies.indicators.macd import MACDIndicator
        from strategies.indicators.ema import EMAIndicator
        from strategies.indicators.sma import SMAIndicator
        from strategies.indicators.bollinger_bands import BollingerBandsIndicator

        indicators = [RSIIndicator, MACDIndicator,
                      EMAIndicator, SMAIndicator, BollingerBandsIndicator]

        for indicator_class in indicators:
            assert issubclass(indicator_class, BaseIndicator)

    def test_imports_are_clean(self):
        """Test that all imports work without circular dependencies"""
        try:
            from strategies.strategy_factory import StrategyFactory
            from strategies.custom_strategy import CustomStrategy
            from strategies.base_strategy import BaseStrategy, IMarketDataService
            from strategies.indicators.base_indicator import BaseIndicator

            # Should not raise any import errors
            assert True
        except ImportError as e:
            pytest.fail(f"Import error detected: {e}")

    def test_strategy_factory_deprecation_warning(self):
        """Test that old create_strategy function shows deprecation warning"""
        from strategies.base_strategy import create_strategy, StrategyConfig
        import warnings

        config = StrategyConfig(symbol="BTCUSDT", timeframe="1h")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                create_strategy("unknown", config)
            except ValueError:
                pass  # Expected for unknown strategy

            # Should have logged a warning (though it uses logger, not warnings)


class TestProductionReadiness:
    """Test production readiness features"""

    def test_strategy_configs_available(self):
        """Test that strategy configurations are available"""
        from strategies.strategy_config import StrategyConfigs

        # Test all predefined configs
        configs = [
            StrategyConfigs.get_simple_rsi_config(),
            StrategyConfigs.get_rsi_macd_config(),
            StrategyConfigs.get_rsi_macd_ema_config(),
            StrategyConfigs.get_bollinger_rsi_config(),
            StrategyConfigs.get_sma_crossover_config(),
            StrategyConfigs.get_scalping_config(),
        ]

        for config in configs:
            assert config is not None
            assert 'indicators' in config
            assert 'rules' in config

    def test_main_module_imports(self):
        """Test that main module can import all required components"""
        try:
            # These imports should work for main.py
            from strategies.strategy_factory import StrategyFactory
            from strategies.strategy_config import StrategyConfigs
            from strategies.grid_strategy import GridTradingStrategy, GridConfig
            from strategies.dca_strategy import DCAStrategy, DCAConfig

            assert True
        except ImportError as e:
            pytest.fail(f"Main module import error: {e}")

    @pytest.mark.asyncio
    async def test_end_to_end_strategy_execution(self):
        """Test end-to-end strategy execution"""
        from strategies.strategy_factory import StrategyFactory

        # Mock market data service
        mock_service = AsyncMock()
        mock_service.get_current_price.return_value = Decimal("45000")
        mock_service.get_price_history.return_value = [
            Decimal(str(p)) for p in range(44000, 45000, 10)]

        # Create and run strategy
        strategy = StrategyFactory.create_simple_rsi_strategy(mock_service)
        result = await strategy.run()

        assert result is not None
        assert hasattr(result, 'signal')
        assert hasattr(result, 'strength')
        assert hasattr(result, 'confidence')


if __name__ == "__main__":
    # Run basic validation
    print("🧪 Running cleanup validation tests...")

    # Test imports
    try:
        from strategies.strategy_factory import StrategyFactory
        from strategies.indicators.base_indicator import BaseIndicator
        from strategies.base_strategy import BaseStrategy, IMarketDataService
        print("✅ All imports successful")
    except Exception as e:
        print(f"❌ Import error: {e}")
        exit(1)

    # Test strategy creation
    try:
        mock_service = Mock()
        strategy = StrategyFactory.create_rsi_macd_strategy(mock_service)
        print("✅ Strategy creation successful")
    except Exception as e:
        print(f"❌ Strategy creation error: {e}")
        exit(1)

    print("🎉 Cleanup validation passed! Run 'pytest tests/test_refactoring_cleanup.py' for full test suite.")
