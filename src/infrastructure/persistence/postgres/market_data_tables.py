from sqlalchemy import Column, String, Integer, Float, DateTime, BigInteger, Index, UniqueConstraint, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from decimal import Decimal

Base = declarative_base()

class KlineData(Base):
    __tablename__ = 'kline_data'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    interval = Column(String(10), nullable=False)
    open_time = Column(DateTime, nullable=False)
    close_time = Column(DateTime, nullable=False)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    quote_volume = Column(Float, nullable=False)
    number_of_trades = Column(Integer)
    taker_buy_base_volume = Column(Float)
    taker_buy_quote_volume = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('symbol', 'interval', 'open_time', name='unique_kline'),
        Index('idx_symbol_interval_time', 'symbol', 'interval', 'open_time'),
        Index('idx_open_time', 'open_time'),
    )

class OrderBookSnapshot(Base):
    __tablename__ = 'orderbook_snapshots'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    update_id = Column(BigInteger, nullable=False)
    bids_json = Column(String, nullable=False)  # JSON string of bid levels [[price, quantity], ...]
    asks_json = Column(String, nullable=False)  # JSON string of ask levels [[price, quantity], ...]
    best_bid_price = Column(Float)
    best_bid_qty = Column(Float)
    best_ask_price = Column(Float)
    best_ask_qty = Column(Float)
    spread = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_orderbook_symbol_time', 'symbol', 'timestamp'),
        Index('idx_orderbook_timestamp', 'timestamp'),
    )

class TradeData(Base):
    __tablename__ = 'trade_data'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    trade_id = Column(BigInteger, nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    quote_quantity = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    is_buyer_maker = Column(Integer)  # 1 if buyer is maker, 0 if taker
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('symbol', 'trade_id', name='unique_trade'),
        Index('idx_trade_symbol_time', 'symbol', 'timestamp'),
        Index('idx_trade_timestamp', 'timestamp'),
    )

class IndicatorValue(Base):
    __tablename__ = 'indicator_values'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    indicator_name = Column(String(50), nullable=False)
    timeframe = Column(String(10), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    value = Column(Float, nullable=False)
    parameters = Column(String)  # JSON string of indicator parameters
    additional_values = Column(String)  # JSON string for multi-value indicators (e.g., MACD signal, histogram)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('symbol', 'indicator_name', 'timeframe', 'timestamp', name='unique_indicator'),
        Index('idx_indicator_symbol_name_time', 'symbol', 'indicator_name', 'timestamp'),
        Index('idx_indicator_timestamp', 'timestamp'),
    )

class MarketMetrics(Base):
    __tablename__ = 'market_metrics'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    price_24h_change = Column(Float)
    volume_24h = Column(Float)
    high_24h = Column(Float)
    low_24h = Column(Float)
    open_interest = Column(Float)
    funding_rate = Column(Float)
    mark_price = Column(Float)
    index_price = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('symbol', 'timestamp', name='unique_market_metrics'),
        Index('idx_metrics_symbol_time', 'symbol', 'timestamp'),
    )

class SymbolInfo(Base):
    __tablename__ = 'symbol_info'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), unique=True, nullable=False)
    base_asset = Column(String(20), nullable=False)
    quote_asset = Column(String(20), nullable=False)
    price_precision = Column(Integer)
    quantity_precision = Column(Integer)
    min_quantity = Column(Float)
    max_quantity = Column(Float)
    step_size = Column(Float)
    min_notional = Column(Float)
    contract_type = Column(String(20))  # PERPETUAL, CURRENT_QUARTER, etc.
    status = Column(String(20))  # TRADING, HALT, etc.
    listed_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_symbol_info_symbol', 'symbol'),
    )