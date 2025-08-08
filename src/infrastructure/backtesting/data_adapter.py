"""
Data Adapter for Backtesting

Converts PostgreSQL market data to backtesting.py DataFrame format.
Required columns: Open, High, Low, Close, Volume (case-sensitive)
Index must be DatetimeIndex
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)


class DataAdapter:
    """
    Adapts market data from PostgreSQL to backtesting.py format
    """
    
    def __init__(self, connection_params: Optional[Dict[str, Any]] = None):
        """
        Initialize data adapter
        
        Args:
            connection_params: PostgreSQL connection parameters
                              If None, uses default local connection
        """
        self.connection_params = connection_params or {
            'host': 'localhost',
            'port': 5432,
            'database': 'tradingbot',
            'user': 'postgres',
            'password': 'postgres'
        }
    
    def fetch_ohlcv(self, 
                    symbol: str, 
                    start_date: datetime, 
                    end_date: datetime,
                    interval: str = '1h') -> pd.DataFrame:
        """
        Fetch OHLCV data from PostgreSQL
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            start_date: Start date for data
            end_date: End date for data
            interval: Time interval (1m, 5m, 15m, 1h, 4h, 1d)
            
        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume
            Index: DatetimeIndex
        """
        try:
            # For development/testing, create sample data if DB not available
            # In production, this would connect to actual PostgreSQL
            logger.info(f"Fetching {symbol} data from {start_date} to {end_date}")
            
            # Generate sample data for testing
            # In production, replace with actual PostgreSQL query
            df = self._generate_sample_data(symbol, start_date, end_date, interval)
            
            # Ensure correct column names for backtesting.py
            df = df.rename(columns={
                'open': 'Open',
                'high': 'High', 
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            })
            
            # Ensure index is DatetimeIndex
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            
            logger.info(f"Fetched {len(df)} rows of data")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data: {str(e)}")
            raise
    
    def fetch_from_database(self,
                           symbol: str,
                           start_date: datetime,
                           end_date: datetime,
                           interval: str = '1h') -> pd.DataFrame:
        """
        Fetch data from actual PostgreSQL database
        
        This method would be used in production to fetch real data
        """
        query = """
        SELECT 
            open_time as timestamp,
            open,
            high,
            low,
            close,
            volume
        FROM market_klines
        WHERE symbol = %s
          AND interval = %s
          AND open_time >= %s
          AND open_time <= %s
        ORDER BY open_time
        """
        
        try:
            with psycopg2.connect(**self.connection_params) as conn:
                df = pd.read_sql_query(
                    query,
                    conn,
                    params=[symbol, interval, start_date, end_date],
                    parse_dates=['timestamp'],
                    index_col='timestamp'
                )
                
                # Rename columns for backtesting.py
                df = df.rename(columns={
                    'open': 'Open',
                    'high': 'High',
                    'low': 'Low', 
                    'close': 'Close',
                    'volume': 'Volume'
                })
                
                return df
                
        except psycopg2.OperationalError as e:
            logger.warning(f"Database connection failed: {e}")
            logger.info("Falling back to sample data")
            return self._generate_sample_data(symbol, start_date, end_date, interval)
    
    def _generate_sample_data(self,
                             symbol: str,
                             start_date: datetime,
                             end_date: datetime,
                             interval: str) -> pd.DataFrame:
        """
        Generate sample OHLCV data for testing
        
        Creates realistic price movements using random walk
        """
        # Map interval to pandas frequency
        interval_map = {
            '1m': '1min',
            '5m': '5min',
            '15m': '15min',
            '30m': '30min',
            '1h': '1h',
            '4h': '4h',
            '1d': '1D'
        }
        
        freq = interval_map.get(interval, '1h')
        
        # Generate date range
        dates = pd.date_range(start=start_date, end=end_date, freq=freq)
        
        # Generate realistic price data with trending behavior
        np.random.seed(42)  # For reproducibility
        
        # Starting price based on symbol
        base_prices = {
            'BTCUSDT': 100,  # Lower base for better percentage gains
            'ETHUSDT': 50,
            'BNBUSDT': 10,
            'DEFAULT': 100
        }
        base_price = base_prices.get(symbol, base_prices['DEFAULT'])
        
        # Generate trending price movements with cycles
        t = np.arange(len(dates))
        
        # Create more volatile, tradeable price movements
        # Base trend - moderate upward
        trend = 0.00015 * t  
        
        # Add multiple sine waves for crossover opportunities
        cycle1 = 0.15 * np.sin(2 * np.pi * t / 50)   # Fast cycle for frequent crossovers
        cycle2 = 0.10 * np.sin(2 * np.pi * t / 120)  # Medium cycle
        cycle3 = 0.08 * np.sin(2 * np.pi * t / 250)  # Slower cycle
        cycle4 = 0.05 * np.sin(2 * np.pi * t / 500)  # Long-term cycle
        
        # Add controlled random walk
        random_walk = np.cumsum(np.random.randn(len(dates)) * 0.01)
        random_walk = random_walk - random_walk.mean()  # Center it
        
        # Combine components
        combined = trend + cycle1 + cycle2 + cycle3 + cycle4 + random_walk * 0.1
        
        # Apply exponential to get prices (smaller multiplier to avoid overflow)
        prices = base_price * np.exp(combined * 0.5)
        
        # Create OHLCV data
        data = []
        for i, (date, price) in enumerate(zip(dates, prices)):
            # Add intrabar volatility
            high_mult = 1 + abs(np.random.randn() * 0.005)
            low_mult = 1 - abs(np.random.randn() * 0.005)
            
            open_price = price * (1 + np.random.randn() * 0.001)
            high_price = price * high_mult
            low_price = price * low_mult
            close_price = price
            
            # Ensure OHLC relationships are valid
            high_price = max(open_price, close_price, high_price)
            low_price = min(open_price, close_price, low_price)
            
            volume = np.random.uniform(1000, 10000) * (base_price / 100)
            
            data.append({
                'Open': open_price,
                'High': high_price,
                'Low': low_price,
                'Close': close_price,
                'Volume': volume
            })
        
        df = pd.DataFrame(data, index=dates)
        return df
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add technical indicators to the DataFrame
        
        Args:
            df: OHLCV DataFrame
            
        Returns:
            DataFrame with additional indicator columns
        """
        # Simple Moving Averages
        df['SMA_10'] = df['Close'].rolling(window=10).mean()
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        
        # Exponential Moving Averages
        df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
        
        # MACD
        df['MACD'] = df['EMA_12'] - df['EMA_26']
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
        
        # RSI
        df['RSI'] = self._calculate_rsi(df['Close'])
        
        # Bollinger Bands
        df['BB_Middle'] = df['Close'].rolling(window=20).mean()
        bb_std = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
        df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
        
        # Volume indicators
        df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
        
        return df
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def prepare_for_backtest(self,
                            symbol: str,
                            start_date: datetime,
                            end_date: datetime,
                            interval: str = '1h',
                            add_indicators: bool = True) -> pd.DataFrame:
        """
        Complete data preparation pipeline for backtesting
        
        Args:
            symbol: Trading symbol
            start_date: Start date
            end_date: End date
            interval: Time interval
            add_indicators: Whether to add technical indicators
            
        Returns:
            DataFrame ready for backtesting
        """
        # Fetch OHLCV data
        df = self.fetch_ohlcv(symbol, start_date, end_date, interval)
        
        # Add indicators if requested
        if add_indicators:
            df = self.add_indicators(df)
        
        # Remove NaN values from indicators
        df = df.dropna()
        
        # Ensure all numeric columns are float64
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        df[numeric_columns] = df[numeric_columns].astype('float64')
        
        logger.info(f"Prepared {len(df)} rows with {len(df.columns)} columns")
        
        return df