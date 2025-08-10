import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging
import ta

logger = logging.getLogger(__name__)

class IndicatorCalculator:
    
    @staticmethod
    def calculate_sma(prices: pd.Series, period: int) -> pd.Series:
        """Simple Moving Average"""
        return prices.rolling(window=period).mean()
    
    @staticmethod
    def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average"""
        return prices.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index"""
        return ta.momentum.RSIIndicator(close=prices, window=period).rsi()
    
    @staticmethod
    def calculate_macd(prices: pd.Series, 
                      fast_period: int = 12,
                      slow_period: int = 26,
                      signal_period: int = 9) -> Dict[str, pd.Series]:
        """MACD (Moving Average Convergence Divergence)"""
        macd_indicator = ta.trend.MACD(
            close=prices,
            window_slow=slow_period,
            window_fast=fast_period,
            window_sign=signal_period
        )
        
        return {
            'macd': macd_indicator.macd(),
            'signal': macd_indicator.macd_signal(),
            'histogram': macd_indicator.macd_diff()
        }
    
    @staticmethod
    def calculate_bollinger_bands(prices: pd.Series,
                                 period: int = 20,
                                 std_dev: int = 2) -> Dict[str, pd.Series]:
        """Bollinger Bands"""
        bb = ta.volatility.BollingerBands(
            close=prices,
            window=period,
            window_dev=std_dev
        )
        
        return {
            'upper': bb.bollinger_hband(),
            'middle': bb.bollinger_mavg(),
            'lower': bb.bollinger_lband(),
            'width': bb.bollinger_wband(),
            'percent': bb.bollinger_pband()
        }
    
    @staticmethod
    def calculate_stochastic(high: pd.Series,
                           low: pd.Series,
                           close: pd.Series,
                           k_period: int = 14,
                           d_period: int = 3) -> Dict[str, pd.Series]:
        """Stochastic Oscillator"""
        stoch = ta.momentum.StochasticOscillator(
            high=high,
            low=low,
            close=close,
            window=k_period,
            smooth_window=d_period
        )
        
        return {
            'k': stoch.stoch(),
            'd': stoch.stoch_signal()
        }
    
    @staticmethod
    def calculate_atr(high: pd.Series,
                     low: pd.Series,
                     close: pd.Series,
                     period: int = 14) -> pd.Series:
        """Average True Range"""
        return ta.volatility.AverageTrueRange(
            high=high,
            low=low,
            close=close,
            window=period
        ).average_true_range()
    
    @staticmethod
    def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """On-Balance Volume"""
        return ta.volume.OnBalanceVolumeIndicator(
            close=close,
            volume=volume
        ).on_balance_volume()
    
    @staticmethod
    def calculate_vwap(high: pd.Series,
                      low: pd.Series,
                      close: pd.Series,
                      volume: pd.Series) -> pd.Series:
        """Volume Weighted Average Price"""
        typical_price = (high + low + close) / 3
        return (typical_price * volume).cumsum() / volume.cumsum()
    
    @staticmethod
    def calculate_adx(high: pd.Series,
                     low: pd.Series,
                     close: pd.Series,
                     period: int = 14) -> Dict[str, pd.Series]:
        """Average Directional Index"""
        adx = ta.trend.ADXIndicator(
            high=high,
            low=low,
            close=close,
            window=period
        )
        
        return {
            'adx': adx.adx(),
            'di_plus': adx.adx_pos(),
            'di_minus': adx.adx_neg()
        }
    
    @staticmethod
    def calculate_cci(high: pd.Series,
                     low: pd.Series,
                     close: pd.Series,
                     period: int = 20) -> pd.Series:
        """Commodity Channel Index"""
        return ta.trend.CCIIndicator(
            high=high,
            low=low,
            close=close,
            window=period
        ).cci()
    
    @staticmethod
    def calculate_williams_r(high: pd.Series,
                           low: pd.Series,
                           close: pd.Series,
                           period: int = 14) -> pd.Series:
        """Williams %R"""
        return ta.momentum.WilliamsRIndicator(
            high=high,
            low=low,
            close=close,
            lbp=period
        ).williams_r()
    
    @staticmethod
    def calculate_pivot_points(high: float,
                              low: float,
                              close: float) -> Dict[str, float]:
        """Calculate Pivot Points (Classic)"""
        pivot = (high + low + close) / 3
        
        return {
            'pivot': pivot,
            'r1': 2 * pivot - low,
            'r2': pivot + (high - low),
            'r3': pivot + 2 * (high - low),
            's1': 2 * pivot - high,
            's2': pivot - (high - low),
            's3': pivot - 2 * (high - low)
        }
    
    @staticmethod
    def calculate_fibonacci_retracement(high: float, low: float) -> Dict[str, float]:
        """Calculate Fibonacci Retracement Levels"""
        diff = high - low
        
        return {
            'level_0': high,
            'level_236': high - 0.236 * diff,
            'level_382': high - 0.382 * diff,
            'level_500': high - 0.500 * diff,
            'level_618': high - 0.618 * diff,
            'level_786': high - 0.786 * diff,
            'level_1000': low
        }
    
    @staticmethod
    def calculate_ichimoku(high: pd.Series,
                          low: pd.Series,
                          close: pd.Series,
                          conversion_period: int = 9,
                          base_period: int = 26,
                          span_b_period: int = 52,
                          displacement: int = 26) -> Dict[str, pd.Series]:
        """Ichimoku Cloud"""
        ichimoku = ta.trend.IchimokuIndicator(
            high=high,
            low=low,
            window1=conversion_period,
            window2=base_period,
            window3=span_b_period
        )
        
        return {
            'conversion_line': ichimoku.ichimoku_conversion_line(),
            'base_line': ichimoku.ichimoku_base_line(),
            'span_a': ichimoku.ichimoku_a(),
            'span_b': ichimoku.ichimoku_b()
        }
    
    def calculate_all_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate all indicators for a DataFrame with OHLCV data
        
        Args:
            df: DataFrame with columns: open, high, low, close, volume
        
        Returns:
            Dictionary with all calculated indicators
        """
        try:
            indicators = {}
            
            # Trend Indicators
            indicators['sma_20'] = self.calculate_sma(df['close'], 20)
            indicators['sma_50'] = self.calculate_sma(df['close'], 50)
            indicators['sma_200'] = self.calculate_sma(df['close'], 200)
            indicators['ema_12'] = self.calculate_ema(df['close'], 12)
            indicators['ema_26'] = self.calculate_ema(df['close'], 26)
            
            # MACD
            macd_data = self.calculate_macd(df['close'])
            indicators['macd'] = macd_data['macd']
            indicators['macd_signal'] = macd_data['signal']
            indicators['macd_histogram'] = macd_data['histogram']
            
            # Momentum Indicators
            indicators['rsi'] = self.calculate_rsi(df['close'])
            
            # Stochastic
            stoch_data = self.calculate_stochastic(df['high'], df['low'], df['close'])
            indicators['stoch_k'] = stoch_data['k']
            indicators['stoch_d'] = stoch_data['d']
            
            # Volatility Indicators
            bb_data = self.calculate_bollinger_bands(df['close'])
            indicators['bb_upper'] = bb_data['upper']
            indicators['bb_middle'] = bb_data['middle']
            indicators['bb_lower'] = bb_data['lower']
            indicators['bb_width'] = bb_data['width']
            indicators['bb_percent'] = bb_data['percent']
            
            indicators['atr'] = self.calculate_atr(df['high'], df['low'], df['close'])
            
            # Volume Indicators
            if 'volume' in df.columns and df['volume'].sum() > 0:
                indicators['obv'] = self.calculate_obv(df['close'], df['volume'])
                indicators['vwap'] = self.calculate_vwap(
                    df['high'], df['low'], df['close'], df['volume']
                )
            
            # Other Indicators
            adx_data = self.calculate_adx(df['high'], df['low'], df['close'])
            indicators['adx'] = adx_data['adx']
            indicators['di_plus'] = adx_data['di_plus']
            indicators['di_minus'] = adx_data['di_minus']
            
            indicators['cci'] = self.calculate_cci(df['high'], df['low'], df['close'])
            indicators['williams_r'] = self.calculate_williams_r(
                df['high'], df['low'], df['close']
            )
            
            # Ichimoku
            ichimoku_data = self.calculate_ichimoku(df['high'], df['low'], df['close'])
            indicators['ichimoku_conversion'] = ichimoku_data['conversion_line']
            indicators['ichimoku_base'] = ichimoku_data['base_line']
            indicators['ichimoku_span_a'] = ichimoku_data['span_a']
            indicators['ichimoku_span_b'] = ichimoku_data['span_b']
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            raise
    
    def prepare_dataframe(self, kline_data: List[Dict]) -> pd.DataFrame:
        """
        Prepare DataFrame from kline data for indicator calculation
        
        Args:
            kline_data: List of kline dictionaries
        
        Returns:
            DataFrame with OHLCV columns and datetime index
        """
        try:
            df = pd.DataFrame(kline_data)
            
            # Ensure required columns
            required_columns = ['open_price', 'high_price', 'low_price', 
                              'close_price', 'volume', 'open_time']
            
            for col in required_columns:
                if col not in df.columns:
                    raise ValueError(f"Missing required column: {col}")
            
            # Rename columns
            df = df.rename(columns={
                'open_price': 'open',
                'high_price': 'high',
                'low_price': 'low',
                'close_price': 'close'
            })
            
            # Set datetime index
            df['datetime'] = pd.to_datetime(df['open_time'])
            df = df.set_index('datetime')
            
            # Sort by time
            df = df.sort_index()
            
            # Convert to numeric
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
            
        except Exception as e:
            logger.error(f"Error preparing dataframe: {e}")
            raise
    
    def get_latest_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """Get the latest value of all indicators"""
        indicators = self.calculate_all_indicators(df)
        latest = {}
        
        for name, series in indicators.items():
            if isinstance(series, pd.Series) and not series.empty:
                # Get the last non-NaN value
                last_valid = series.last_valid_index()
                if last_valid is not None:
                    latest[name] = float(series.loc[last_valid])
        
        return latest