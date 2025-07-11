# Advanced Trading Bot v2 - Modular Architecture

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Status](https://img.shields.io/badge/status-production%20ready-green.svg)
![Architecture](https://img.shields.io/badge/architecture-modular-orange.svg)

Professional-grade cryptocurrency trading bot with **modular indicator system** inspired by TradingView. Built with clean architecture principles and production-ready features.

## 🚀 Key Features

### ✨ Modular Indicator System (TradingView-style)
- **5 Built-in Indicators**: RSI, MACD, EMA, SMA, Bollinger Bands
- **Rule-based Strategy Engine**: Combine any indicators with AND/OR logic
- **Strategy Factory**: Pre-configured templates for common strategies  
- **Configuration-driven**: Create strategies without coding

### 🏗️ Clean Architecture
- **Dependency Injection**: Proper IoC container with service interfaces
- **Protocol-based Design**: IMarketDataService for clean abstractions
- **Factory Pattern**: StrategyFactory for dynamic strategy creation
- **Observer Pattern**: Event-driven architecture for notifications

### 📊 Advanced Strategies
- **RSI + MACD**: Momentum and trend following
- **Bollinger Bands + RSI**: Mean reversion with momentum filter
- **SMA Crossover**: Classic trend following
- **Grid Trading**: Profit from sideways markets
- **DCA (Dollar Cost Averaging)**: Risk reduction through averaging
- **Custom Strategies**: User-defined indicator combinations

### 🔧 Production Features
- **Real Binance API**: Live market data and trading
- **Async Architecture**: High-performance concurrent processing
- **Database Integration**: SQLAlchemy with async support  
- **Telegram Integration**: Real-time notifications and Mini App
- **Comprehensive Logging**: Structured logging with multiple levels
- **Error Handling**: Graceful failure recovery and monitoring
- **Testing Suite**: Full test coverage with pytest

## 📁 Project Structure

```
trading_bot_v2/
├── 📋 Core Framework
│   ├── core/                    # Trading engine and interfaces
│   ├── config/                  # Configuration management
│   ├── database/                # Database models and connection
│   └── utils/                   # Shared utilities
│
├── 🧠 Modular Strategy System
│   ├── strategies/
│   │   ├── indicators/          # Modular indicator library
│   │   │   ├── base_indicator.py    # Abstract base class
│   │   │   ├── rsi.py              # RSI indicator
│   │   │   ├── macd.py             # MACD indicator  
│   │   │   ├── ema.py              # EMA indicator
│   │   │   ├── sma.py              # SMA indicator
│   │   │   └── bollinger_bands.py  # Bollinger Bands
│   │   ├── base_strategy.py     # Strategy base class
│   │   ├── custom_strategy.py   # Rule-based strategy engine
│   │   ├── strategy_factory.py  # Strategy creation factory
│   │   ├── strategy_config.py   # Pre-defined configurations
│   │   ├── grid_strategy.py     # Grid trading implementation
│   │   └── dca_strategy.py      # DCA strategy implementation
│   │
├── 🤖 Telegram Integration
│   ├── telegram_bot/            # Telegram bot and Mini App
│   └── tests/                   # Comprehensive test suite
│
└── 📋 Configuration
    ├── requirements.txt         # Production dependencies
    ├── requirements-prod.txt    # Optimized production setup
    └── main.py                 # Application entry point
```

## 🎯 Quick Start

### 1. Installation
```bash
# Clone repository
git clone <repository-url>
cd trading_bot_v2

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration
```bash
# Copy environment template
cp .env.example .env

# Configure your settings
# BINANCE_API_KEY=your_api_key
# BINANCE_SECRET_KEY=your_secret_key
# TELEGRAM_BOT_TOKEN=your_bot_token
```

### 3. Run Strategies

#### Pre-configured Strategies
```bash
# RSI + MACD momentum strategy
python main.py --strategy rsi_macd

# Bollinger Bands + RSI mean reversion
python main.py --strategy bollinger_rsi

# SMA crossover trend following
python main.py --strategy sma_crossover

# Grid trading for sideways markets
python main.py --strategy grid

# DCA for risk reduction
python main.py --strategy dca
```

#### Custom Strategy Example
```python
from strategies.strategy_factory import StrategyFactory
from strategies.strategy_config import StrategyConfigs

# Load pre-configured strategy
config = StrategyConfigs.get_rsi_macd_ema_config()
strategy = StrategyFactory.create_custom_strategy(config, market_data_service)

# Or create custom configuration
custom_config = {
    "indicators": [
        {"name": "rsi", "config": {"period": 14}},
        {"name": "bollinger_bands", "config": {"period": 20, "std_dev": 2}}
    ],
    "rules": [
        "rsi < 30 AND bollinger_bands == 'OVERSOLD'"
    ]
}
strategy = StrategyFactory.create_custom_strategy(custom_config, market_data_service)
```

### 4. System Commands
```bash
# Health check
python main.py --health-check

# Portfolio status  
python main.py --portfolio-status

# Test notifications
python main.py --test-notification
```

## 🧪 Testing

```bash
# Run cleanup validation
python tests/test_refactoring_cleanup.py

# Full test suite
pytest tests/

# Test specific components
pytest tests/test_refactoring_cleanup.py::TestModularIndicators
```

## 🏗️ Architecture Overview

### Modular Indicator System
```python
# Each indicator implements BaseIndicator interface
class RSIIndicator(BaseIndicator):
    def calculate(self, prices: np.ndarray) -> np.ndarray
    def get_signal(self, prices: np.ndarray) -> SignalType
    def validate_config(self) -> bool
```

### Strategy Factory Pattern
```python
# Create strategies from configuration
strategy = StrategyFactory.create_rsi_macd_strategy(market_data_service)

# Or use custom configuration
config = {"indicators": [...], "rules": [...]}
strategy = StrategyFactory.create_custom_strategy(config, market_data_service)
```

### Dependency Injection
```python
# Clean interfaces for testability
class IMarketDataService(Protocol):
    async def get_current_price(self, symbol: str) -> Decimal
    async def get_price_history(self, symbol: str, limit: int) -> List[Decimal]

# Strategies receive dependencies
strategy = CustomStrategy(config, market_data_service)
```

## 📈 Available Indicators

| Indicator | Purpose | Parameters |
|-----------|---------|------------|
| **RSI** | Momentum oscillator | `period: int` |
| **MACD** | Trend and momentum | `fast_period, slow_period, signal_period` |
| **EMA** | Exponential moving average | `period: int` |
| **SMA** | Simple moving average | `period: int` |
| **Bollinger Bands** | Volatility and mean reversion | `period: int, std_dev: float` |

## 🛡️ Production Features

### Error Handling
- Graceful API failure recovery
- Circuit breaker pattern for external services
- Comprehensive error logging and alerting

### Performance
- Async/await throughout
- Connection pooling for APIs
- Efficient numpy calculations
- Memory-optimized data structures

### Monitoring
- Structured logging with correlation IDs
- Performance metrics collection
- Health check endpoints
- Telegram alerts for critical events

### Security
- Environment-based configuration
- Secure API key management
- Rate limiting for external APIs
- Input validation and sanitization

## 🔄 Migration from Legacy

The codebase has been completely refactored from hardcoded strategies to a modular architecture:

### Before (Legacy)
```python
# Fixed RSI+MACD strategy in rsi_macd.py
class RSIMACDStrategy:
    def __init__(self):
        self.rsi_period = 14  # Hardcoded
        self.macd_fast = 12   # Hardcoded
        # Tightly coupled indicator calculations
```

### After (Modular)
```python
# Flexible configuration-driven approach
config = {
    "indicators": [
        {"name": "rsi", "config": {"period": 14}},
        {"name": "macd", "config": {"fast_period": 12, "slow_period": 26}}
    ],
    "rules": ["rsi < 30 AND macd_histogram > 0"]
}
strategy = StrategyFactory.create_custom_strategy(config, market_data_service)
```

## 📋 Dependencies

### Core
- `python-binance>=1.0.19` - Binance API client
- `numpy>=1.24.0` - Numerical computations
- `pandas>=2.0.0` - Data analysis
- `sqlalchemy[asyncio]>=2.0.0` - Async database ORM

### Production
- `structlog>=23.2.0` - Structured logging
- `sentry-sdk>=1.39.0` - Error monitoring
- `aiohttp>=3.9.0` - Async HTTP client
- `aiogram>=3.1.0` - Telegram bot framework

### Development
- `pytest>=7.4.0` - Testing framework
- `black>=23.9.0` - Code formatting
- `mypy>=1.6.0` - Type checking
- `ruff>=0.1.5` - Fast linting

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/new-indicator`
3. Add indicator to `strategies/indicators/`
4. Update `StrategyFactory` to support new indicator
5. Add tests in `tests/test_indicators.py`
6. Submit pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

- 📧 Issues: Use GitHub Issues for bug reports
- 💬 Discussions: GitHub Discussions for questions
- 📱 Telegram: Join our trading community

---

**⚠️ Disclaimer**: This software is for educational purposes. Cryptocurrency trading involves significant risk. Always test with paper trading first.
