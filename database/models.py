# database/models.py
"""
Database models replacing JSON file storage.
Type-safe, validated, with proper relationships.
"""
from sqlalchemy import Column, String, Numeric, DateTime, Boolean, Text, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from decimal import Decimal

Base = declarative_base()


class Position(Base):
    """Current open positions - replaces last_buy_price JSON files"""
    __tablename__ = "positions"
    
    symbol = Column(String(20), primary_key=True)  # e.g., "XRPUSDT"
    buy_price = Column(Numeric(18, 8), nullable=False)
    quantity = Column(Numeric(18, 8), nullable=False)
    created_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<Position(symbol='{self.symbol}', price={self.buy_price})>"


class Trade(Base):
    """Complete trading history with profit tracking"""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    side = Column(String(4), nullable=False)  # "BUY" or "SELL"
    price = Column(Numeric(18, 8), nullable=False)
    quantity = Column(Numeric(18, 8), nullable=False)
    profit = Column(Numeric(18, 8), nullable=True)  # Only for SELL trades
    strategy = Column(String(50), nullable=True)  # Which strategy made this trade
    order_id = Column(String(50), nullable=True)  # Binance order ID
    created_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<Trade({self.side} {self.symbol} @ {self.price})>"


class TradingProfile(Base):
    """Trading profiles - replaces profiles.json"""
    __tablename__ = "profiles"
    
    name = Column(String(50), primary_key=True)
    symbol = Column(String(20), nullable=False)
    strategy = Column(String(50), nullable=False)
    timeframe = Column(String(10), nullable=False)  # "1m", "5m", "1h", etc.
    
    # Strategy parameters as JSON
    config = Column(Text, nullable=False)  # JSON string with strategy config
    
    # Risk management
    use_stop_loss = Column(Boolean, default=True)
    stop_loss_ratio = Column(Numeric(6, 4), default=Decimal('-0.02'))  # -2%
    use_take_profit = Column(Boolean, default=True)
    take_profit_ratio = Column(Numeric(6, 4), default=Decimal('0.05'))  # 5%
    min_profit_ratio = Column(Numeric(6, 4), default=Decimal('0.01'))  # 1%
    
    # Position sizing
    max_position_size = Column(Numeric(10, 2), default=Decimal('100'))  # Max USDT per trade
    
    # Status
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Profile(name='{self.name}', symbol='{self.symbol}')>"


class TelegramUser(Base):
    """Authorized Telegram users - replaces auth.json"""
    __tablename__ = "telegram_users"
    
    user_id = Column(String(20), primary_key=True)
    username = Column(String(50), nullable=True)
    first_name = Column(String(100), nullable=True)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    last_seen = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<User(id={self.user_id}, username='{self.username}')>"


class SystemLog(Base):
    """System events and errors for debugging"""
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(String(10), nullable=False)  # INFO, WARNING, ERROR, CRITICAL
    message = Column(Text, nullable=False)
    module = Column(String(50), nullable=True)  # Which module logged this
    exception_info = Column(Text, nullable=True)  # Stack trace if error
    created_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<Log({self.level}: {self.message[:50]}...)>"