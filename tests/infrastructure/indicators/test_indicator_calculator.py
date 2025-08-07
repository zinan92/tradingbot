import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.infrastructure.indicators.indicator_calculator import IndicatorCalculator

class TestIndicatorCalculator:
    
    def setup_method(self):
        self.calculator = IndicatorCalculator()
        
        # Create sample OHLCV data
        dates = pd.date_range(start='2024-01-01', periods=100, freq='1h')
        np.random.seed(42)
        
        # Generate realistic price data
        close_prices = 50000 + np.cumsum(np.random.randn(100) * 100)
        
        self.sample_df = pd.DataFrame({
            'open': close_prices + np.random.randn(100) * 50,
            'high': close_prices + abs(np.random.randn(100) * 100),
            'low': close_prices - abs(np.random.randn(100) * 100),
            'close': close_prices,
            'volume': np.random.randint(100, 1000, 100)
        }, index=dates)
    
    def test_calculate_sma(self):
        # Act
        sma = self.calculator.calculate_sma(self.sample_df['close'], period=20)
        
        # Assert
        assert isinstance(sma, pd.Series)
        assert len(sma) == len(self.sample_df)
        assert sma.iloc[19:].notna().all()  # SMA should have values after period
        assert sma.iloc[:19].isna().all()  # Should be NaN before period
    
    def test_calculate_ema(self):
        # Act
        ema = self.calculator.calculate_ema(self.sample_df['close'], period=12)
        
        # Assert
        assert isinstance(ema, pd.Series)
        assert len(ema) == len(self.sample_df)
        assert ema.notna().any()
    
    def test_calculate_rsi(self):
        # Act
        rsi = self.calculator.calculate_rsi(self.sample_df['close'], period=14)
        
        # Assert
        assert isinstance(rsi, pd.Series)
        assert len(rsi) == len(self.sample_df)
        # RSI should be between 0 and 100
        valid_rsi = rsi[rsi.notna()]
        assert (valid_rsi >= 0).all()
        assert (valid_rsi <= 100).all()
    
    def test_calculate_macd(self):
        # Act
        macd_result = self.calculator.calculate_macd(self.sample_df['close'])
        
        # Assert
        assert 'macd' in macd_result
        assert 'signal' in macd_result
        assert 'histogram' in macd_result
        assert isinstance(macd_result['macd'], pd.Series)
        assert len(macd_result['macd']) == len(self.sample_df)
    
    def test_calculate_bollinger_bands(self):
        # Act
        bb = self.calculator.calculate_bollinger_bands(self.sample_df['close'])
        
        # Assert
        assert 'upper' in bb
        assert 'middle' in bb
        assert 'lower' in bb
        assert 'width' in bb
        assert 'percent' in bb
        
        # Upper band should be above lower band
        valid_idx = bb['upper'].notna() & bb['lower'].notna()
        assert (bb['upper'][valid_idx] > bb['lower'][valid_idx]).all()
    
    def test_calculate_stochastic(self):
        # Act
        stoch = self.calculator.calculate_stochastic(
            self.sample_df['high'],
            self.sample_df['low'],
            self.sample_df['close']
        )
        
        # Assert
        assert 'k' in stoch
        assert 'd' in stoch
        
        # Stochastic should be between 0 and 100
        valid_k = stoch['k'][stoch['k'].notna()]
        assert (valid_k >= 0).all()
        assert (valid_k <= 100).all()
    
    def test_calculate_atr(self):
        # Act
        atr = self.calculator.calculate_atr(
            self.sample_df['high'],
            self.sample_df['low'],
            self.sample_df['close']
        )
        
        # Assert
        assert isinstance(atr, pd.Series)
        assert len(atr) == len(self.sample_df)
        # ATR should be positive
        valid_atr = atr[atr.notna()]
        assert (valid_atr >= 0).all()
    
    def test_calculate_obv(self):
        # Act
        obv = self.calculator.calculate_obv(
            self.sample_df['close'],
            self.sample_df['volume']
        )
        
        # Assert
        assert isinstance(obv, pd.Series)
        assert len(obv) == len(self.sample_df)
        assert obv.notna().all()
    
    def test_calculate_vwap(self):
        # Act
        vwap = self.calculator.calculate_vwap(
            self.sample_df['high'],
            self.sample_df['low'],
            self.sample_df['close'],
            self.sample_df['volume']
        )
        
        # Assert
        assert isinstance(vwap, pd.Series)
        assert len(vwap) == len(self.sample_df)
        assert vwap.notna().any()
    
    def test_calculate_adx(self):
        # Act
        adx_result = self.calculator.calculate_adx(
            self.sample_df['high'],
            self.sample_df['low'],
            self.sample_df['close']
        )
        
        # Assert
        assert 'adx' in adx_result
        assert 'di_plus' in adx_result
        assert 'di_minus' in adx_result
        
        # ADX should be between 0 and 100
        valid_adx = adx_result['adx'][adx_result['adx'].notna()]
        assert (valid_adx >= 0).all()
        assert (valid_adx <= 100).all()
    
    def test_calculate_pivot_points(self):
        # Arrange
        high = 58000
        low = 56000
        close = 57000
        
        # Act
        pivots = self.calculator.calculate_pivot_points(high, low, close)
        
        # Assert
        assert 'pivot' in pivots
        assert 'r1' in pivots
        assert 'r2' in pivots
        assert 's1' in pivots
        assert 's2' in pivots
        
        # Pivot should be between high and low
        assert low <= pivots['pivot'] <= high
        # Resistance levels should be above pivot
        assert pivots['r1'] > pivots['pivot']
        assert pivots['r2'] > pivots['r1']
        # Support levels should be below pivot
        assert pivots['s1'] < pivots['pivot']
        assert pivots['s2'] < pivots['s1']
    
    def test_calculate_fibonacci_retracement(self):
        # Arrange
        high = 60000
        low = 50000
        
        # Act
        fib_levels = self.calculator.calculate_fibonacci_retracement(high, low)
        
        # Assert
        assert fib_levels['level_0'] == high
        assert fib_levels['level_1000'] == low
        assert fib_levels['level_236'] > fib_levels['level_382']
        assert fib_levels['level_382'] > fib_levels['level_500']
        assert fib_levels['level_500'] > fib_levels['level_618']
    
    def test_prepare_dataframe(self):
        # Arrange
        kline_data = [
            {
                'open_price': 57000,
                'high_price': 57500,
                'low_price': 56500,
                'close_price': 57100,
                'volume': 100,
                'open_time': datetime(2024, 1, 1, 0, 0)
            },
            {
                'open_price': 57100,
                'high_price': 57600,
                'low_price': 57000,
                'close_price': 57400,
                'volume': 150,
                'open_time': datetime(2024, 1, 1, 1, 0)
            }
        ]
        
        # Act
        df = self.calculator.prepare_dataframe(kline_data)
        
        # Assert
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert 'open' in df.columns
        assert 'high' in df.columns
        assert 'low' in df.columns
        assert 'close' in df.columns
        assert 'volume' in df.columns
        assert isinstance(df.index, pd.DatetimeIndex)
    
    def test_calculate_all_indicators(self):
        # Act
        indicators = self.calculator.calculate_all_indicators(self.sample_df)
        
        # Assert
        assert isinstance(indicators, dict)
        # Check key indicators are present
        assert 'sma_20' in indicators
        assert 'rsi' in indicators
        assert 'macd' in indicators
        assert 'bb_upper' in indicators
        assert 'atr' in indicators
        assert 'adx' in indicators
        
        # All indicators should be Series with same length as input
        for name, series in indicators.items():
            if isinstance(series, pd.Series):
                assert len(series) == len(self.sample_df)
    
    def test_get_latest_indicators(self):
        # Act
        latest = self.calculator.get_latest_indicators(self.sample_df)
        
        # Assert
        assert isinstance(latest, dict)
        # Should contain numeric values
        for name, value in latest.items():
            assert isinstance(value, (int, float))
            assert not pd.isna(value)