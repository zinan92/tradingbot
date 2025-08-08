"""
Live Strategy Runner for Real-Time Trading

Bridges backtested strategies with live market execution on Binance Futures.
Monitors real-time data and executes trades based on strategy signals.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Type
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np

from src.infrastructure.binance_client import BinanceClient
from src.infrastructure.market_data.websocket_manager import WebSocketManager
from src.infrastructure.database.db_manager import DatabaseManager
from src.infrastructure.backtesting.strategy_adapter import BaseStrategy

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Trading signal types"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE = "CLOSE"


@dataclass
class TradingSignal:
    """Trading signal with metadata"""
    timestamp: datetime
    symbol: str
    signal_type: SignalType
    price: float
    quantity: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: float = 1.0
    reason: str = ""


@dataclass
class Position:
    """Active position tracking"""
    symbol: str
    side: str  # LONG or SHORT
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    entry_time: datetime
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


class LiveStrategyRunner:
    """
    Executes trading strategies in real-time with live market data.
    Manages positions, risk, and order execution.
    """
    
    def __init__(
        self,
        binance_client: BinanceClient,
        db_manager: DatabaseManager,
        strategy_class: Type[BaseStrategy],
        strategy_params: Dict[str, Any],
        symbol: str,
        interval: str = "5m",
        initial_capital: float = 10000,
        max_position_size: float = 0.95,  # Max 95% of capital
        max_daily_loss: float = 0.02,  # Max 2% daily loss
        use_testnet: bool = True
    ):
        """
        Initialize live strategy runner
        
        Args:
            binance_client: Binance API client
            db_manager: Database manager for data and tracking
            strategy_class: Strategy class to run
            strategy_params: Strategy parameters
            symbol: Trading symbol (e.g., 'BTCUSDT')
            interval: Timeframe for strategy
            initial_capital: Starting capital
            max_position_size: Maximum position size as % of capital
            max_daily_loss: Maximum daily loss as % of capital
            use_testnet: Whether to use testnet (safety for initial testing)
        """
        self.client = binance_client
        self.db = db_manager
        self.strategy_class = strategy_class
        self.strategy_params = strategy_params
        self.symbol = symbol
        self.interval = interval
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.max_position_size = max_position_size
        self.max_daily_loss = max_daily_loss
        self.use_testnet = use_testnet
        
        # Position tracking
        self.positions: Dict[str, Position] = {}
        self.pending_orders: Dict[str, Any] = {}
        
        # Performance tracking
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.trade_count = 0
        self.win_count = 0
        
        # Risk management
        self.is_trading_enabled = True
        self.last_signal_time = None
        self.min_time_between_trades = 60  # seconds
        
        # Data buffer for strategy
        self.data_buffer = pd.DataFrame()
        self.buffer_size = 500  # Keep last 500 candles
        
        # WebSocket manager for real-time data
        self.ws_manager = None
        
        # Strategy instance
        self.strategy = None
        
        logger.info(f"LiveStrategyRunner initialized for {symbol} with {strategy_class.__name__}")
    
    async def initialize(self):
        """Initialize components and load historical data"""
        try:
            # Load historical data for strategy initialization
            await self._load_historical_data()
            
            # Initialize strategy with data
            self._initialize_strategy()
            
            # Setup WebSocket for real-time data
            await self._setup_websocket()
            
            # Check account balance
            await self._update_account_balance()
            
            logger.info(f"Live trading initialized. Capital: ${self.current_capital:.2f}")
            
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            raise
    
    async def _load_historical_data(self):
        """Load historical data for strategy warm-up"""
        try:
            # Calculate how much data we need
            lookback_periods = max(
                self.strategy_params.get('fast_period', 20),
                self.strategy_params.get('slow_period', 50),
                100  # Minimum 100 periods
            )
            
            # Fetch from database
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=lookback_periods)
            
            query = """
            SELECT 
                open_time as timestamp,
                open_price as Open,
                high_price as High,
                low_price as Low,
                close_price as Close,
                volume as Volume
            FROM kline_data
            WHERE symbol = %s
              AND interval = %s
              AND open_time >= %s
              AND open_time <= %s
            ORDER BY open_time
            """
            
            data = await self.db.fetch_dataframe(
                query,
                (self.symbol, self.interval, start_time, end_time)
            )
            
            if len(data) > 0:
                data.set_index('timestamp', inplace=True)
                self.data_buffer = data
                logger.info(f"Loaded {len(data)} historical candles for {self.symbol}")
            else:
                logger.warning(f"No historical data found for {self.symbol}")
                # Fetch from Binance API as fallback
                await self._fetch_from_binance(lookback_periods)
                
        except Exception as e:
            logger.error(f"Error loading historical data: {e}")
            raise
    
    async def _fetch_from_binance(self, periods: int):
        """Fetch historical data from Binance API"""
        try:
            klines = await self.client.get_klines(
                symbol=self.symbol,
                interval=self.interval,
                limit=periods
            )
            
            # Convert to DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'Open', 'High', 'Low', 'Close', 'Volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Keep only OHLCV
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)
            
            self.data_buffer = df
            logger.info(f"Fetched {len(df)} candles from Binance API")
            
        except Exception as e:
            logger.error(f"Error fetching from Binance: {e}")
            raise
    
    def _initialize_strategy(self):
        """Initialize strategy instance with historical data"""
        try:
            # Create strategy instance
            # Note: We need to adapt the strategy for live trading
            # The backtesting strategies expect certain methods
            
            # For now, we'll create a simple adapter
            class LiveStrategyAdapter:
                def __init__(self, data, params):
                    self.data = data
                    self.params = params
                    self.last_signal = SignalType.HOLD
                    
                    # Initialize indicators based on strategy type
                    self._init_indicators()
                
                def _init_indicators(self):
                    """Initialize technical indicators"""
                    # Example for EMA strategy
                    if 'fast_period' in self.params:
                        self.ema_fast = self.data['Close'].ewm(
                            span=self.params['fast_period'], adjust=False
                        ).mean()
                        self.ema_slow = self.data['Close'].ewm(
                            span=self.params['slow_period'], adjust=False
                        ).mean()
                
                def get_signal(self) -> SignalType:
                    """Generate trading signal based on current data"""
                    if len(self.data) < 2:
                        return SignalType.HOLD
                    
                    # Example EMA crossover logic
                    if 'fast_period' in self.params:
                        if self.ema_fast.iloc[-1] > self.ema_slow.iloc[-1] and \
                           self.ema_fast.iloc[-2] <= self.ema_slow.iloc[-2]:
                            return SignalType.BUY
                        elif self.ema_fast.iloc[-1] < self.ema_slow.iloc[-1] and \
                             self.ema_fast.iloc[-2] >= self.ema_slow.iloc[-2]:
                            return SignalType.SELL
                    
                    return SignalType.HOLD
                
                def update(self, new_data):
                    """Update strategy with new data"""
                    self.data = pd.concat([self.data, new_data]).tail(500)
                    self._init_indicators()
            
            self.strategy = LiveStrategyAdapter(self.data_buffer, self.strategy_params)
            logger.info("Strategy initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing strategy: {e}")
            raise
    
    async def _setup_websocket(self):
        """Setup WebSocket connection for real-time data"""
        try:
            self.ws_manager = WebSocketManager(use_testnet=self.use_testnet)
            
            # Subscribe to kline/candlestick stream
            stream = f"{self.symbol.lower()}@kline_{self.interval}"
            
            await self.ws_manager.subscribe_stream(
                stream,
                callback=self._on_kline_update
            )
            
            logger.info(f"WebSocket connected for {stream}")
            
        except Exception as e:
            logger.error(f"Error setting up WebSocket: {e}")
            raise
    
    async def _on_kline_update(self, data: Dict):
        """Handle real-time kline updates"""
        try:
            kline = data['k']
            
            # Check if candle is closed
            if kline['x']:  # Candle closed
                # Create new candle data
                new_candle = pd.DataFrame([{
                    'Open': float(kline['o']),
                    'High': float(kline['h']),
                    'Low': float(kline['l']),
                    'Close': float(kline['c']),
                    'Volume': float(kline['v'])
                }], index=[pd.Timestamp(kline['t'], unit='ms')])
                
                # Update strategy data
                self.strategy.update(new_candle)
                
                # Generate signal
                signal = self.strategy.get_signal()
                
                # Execute signal if valid
                await self._process_signal(signal, float(kline['c']))
            
            # Update current price for position tracking
            await self._update_positions(float(kline['c']))
            
        except Exception as e:
            logger.error(f"Error processing kline update: {e}")
    
    async def _process_signal(self, signal: SignalType, current_price: float):
        """Process trading signal and execute orders"""
        try:
            # Check if trading is enabled
            if not self.is_trading_enabled:
                logger.warning("Trading disabled due to risk limits")
                return
            
            # Check minimum time between trades
            if self.last_signal_time:
                time_diff = (datetime.now() - self.last_signal_time).seconds
                if time_diff < self.min_time_between_trades:
                    return
            
            # Process signal
            if signal == SignalType.BUY:
                await self._open_long_position(current_price)
            elif signal == SignalType.SELL:
                await self._open_short_position(current_price)
            elif signal == SignalType.CLOSE:
                await self._close_all_positions()
            
            self.last_signal_time = datetime.now()
            
        except Exception as e:
            logger.error(f"Error processing signal: {e}")
    
    async def _open_long_position(self, current_price: float):
        """Open a long position"""
        try:
            # Check if we already have a position
            if self.symbol in self.positions:
                logger.info("Already have an open position")
                return
            
            # Calculate position size
            position_size = self._calculate_position_size(current_price)
            
            if position_size <= 0:
                logger.warning("Position size too small")
                return
            
            # Calculate stop loss and take profit
            stop_loss = current_price * (1 - self.strategy_params.get('stop_loss_pct', 0.02))
            take_profit = current_price * (1 + self.strategy_params.get('take_profit_pct', 0.05))
            
            # Place market order
            order = await self.client.place_order(
                symbol=self.symbol,
                side='BUY',
                order_type='MARKET',
                quantity=position_size
            )
            
            if order['status'] == 'FILLED':
                # Create position record
                position = Position(
                    symbol=self.symbol,
                    side='LONG',
                    entry_price=float(order['avgPrice']),
                    quantity=float(order['executedQty']),
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    entry_time=datetime.now()
                )
                
                self.positions[self.symbol] = position
                self.trade_count += 1
                
                # Place stop loss and take profit orders
                await self._place_exit_orders(position)
                
                logger.info(f"Opened LONG position: {position.quantity} @ ${position.entry_price:.2f}")
                logger.info(f"SL: ${stop_loss:.2f}, TP: ${take_profit:.2f}")
            
        except Exception as e:
            logger.error(f"Error opening long position: {e}")
    
    async def _open_short_position(self, current_price: float):
        """Open a short position"""
        try:
            # Check if we already have a position
            if self.symbol in self.positions:
                # Close existing long position first
                if self.positions[self.symbol].side == 'LONG':
                    await self._close_position(self.symbol)
                else:
                    logger.info("Already have a short position")
                    return
            
            # Calculate position size
            position_size = self._calculate_position_size(current_price)
            
            if position_size <= 0:
                logger.warning("Position size too small")
                return
            
            # Calculate stop loss and take profit
            stop_loss = current_price * (1 + self.strategy_params.get('stop_loss_pct', 0.02))
            take_profit = current_price * (1 - self.strategy_params.get('take_profit_pct', 0.05))
            
            # Place market order
            order = await self.client.place_order(
                symbol=self.symbol,
                side='SELL',
                order_type='MARKET',
                quantity=position_size
            )
            
            if order['status'] == 'FILLED':
                # Create position record
                position = Position(
                    symbol=self.symbol,
                    side='SHORT',
                    entry_price=float(order['avgPrice']),
                    quantity=float(order['executedQty']),
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    entry_time=datetime.now()
                )
                
                self.positions[self.symbol] = position
                self.trade_count += 1
                
                # Place stop loss and take profit orders
                await self._place_exit_orders(position)
                
                logger.info(f"Opened SHORT position: {position.quantity} @ ${position.entry_price:.2f}")
                logger.info(f"SL: ${stop_loss:.2f}, TP: ${take_profit:.2f}")
            
        except Exception as e:
            logger.error(f"Error opening short position: {e}")
    
    async def _place_exit_orders(self, position: Position):
        """Place stop loss and take profit orders"""
        try:
            # Place stop loss order
            sl_side = 'SELL' if position.side == 'LONG' else 'BUY'
            sl_order = await self.client.place_order(
                symbol=position.symbol,
                side=sl_side,
                order_type='STOP_MARKET',
                quantity=position.quantity,
                stopPrice=position.stop_loss
            )
            
            # Place take profit order
            tp_side = 'SELL' if position.side == 'LONG' else 'BUY'
            tp_order = await self.client.place_order(
                symbol=position.symbol,
                side=tp_side,
                order_type='TAKE_PROFIT_MARKET',
                quantity=position.quantity,
                stopPrice=position.take_profit
            )
            
            logger.info(f"Exit orders placed: SL={sl_order['orderId']}, TP={tp_order['orderId']}")
            
        except Exception as e:
            logger.error(f"Error placing exit orders: {e}")
    
    async def _close_position(self, symbol: str):
        """Close a specific position"""
        try:
            if symbol not in self.positions:
                return
            
            position = self.positions[symbol]
            
            # Place market order to close
            close_side = 'SELL' if position.side == 'LONG' else 'BUY'
            order = await self.client.place_order(
                symbol=symbol,
                side=close_side,
                order_type='MARKET',
                quantity=position.quantity
            )
            
            if order['status'] == 'FILLED':
                # Calculate P&L
                exit_price = float(order['avgPrice'])
                if position.side == 'LONG':
                    pnl = (exit_price - position.entry_price) * position.quantity
                else:
                    pnl = (position.entry_price - exit_price) * position.quantity
                
                # Update statistics
                self.total_pnl += pnl
                self.daily_pnl += pnl
                if pnl > 0:
                    self.win_count += 1
                
                # Remove position
                del self.positions[symbol]
                
                logger.info(f"Closed {position.side} position: P&L=${pnl:.2f}")
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
    
    async def _close_all_positions(self):
        """Close all open positions"""
        for symbol in list(self.positions.keys()):
            await self._close_position(symbol)
    
    def _calculate_position_size(self, current_price: float) -> float:
        """Calculate appropriate position size based on risk management"""
        try:
            # Get available capital
            available_capital = self.current_capital * self.max_position_size
            
            # Calculate position size in base currency
            position_size = available_capital / current_price
            
            # Apply minimum order size (Binance specific)
            min_order_size = 0.001  # Example for BTC
            if position_size < min_order_size:
                return 0
            
            # Round to appropriate precision
            precision = 3  # Example precision
            position_size = round(position_size, precision)
            
            return position_size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0
    
    async def _update_positions(self, current_price: float):
        """Update unrealized P&L for open positions"""
        for symbol, position in self.positions.items():
            if position.side == 'LONG':
                position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
            else:
                position.unrealized_pnl = (position.entry_price - current_price) * position.quantity
    
    async def _update_account_balance(self):
        """Update account balance from Binance"""
        try:
            account = await self.client.get_account()
            
            # Find USDT balance
            for balance in account['balances']:
                if balance['asset'] == 'USDT':
                    self.current_capital = float(balance['free']) + float(balance['locked'])
                    break
            
            logger.info(f"Account balance updated: ${self.current_capital:.2f}")
            
        except Exception as e:
            logger.error(f"Error updating account balance: {e}")
    
    async def check_risk_limits(self):
        """Check if risk limits are breached"""
        try:
            # Check daily loss limit
            daily_loss_pct = abs(self.daily_pnl / self.initial_capital)
            if daily_loss_pct > self.max_daily_loss:
                logger.warning(f"Daily loss limit breached: {daily_loss_pct:.2%}")
                self.is_trading_enabled = False
                await self._close_all_positions()
                return False
            
            # Check total drawdown
            total_loss_pct = abs(self.total_pnl / self.initial_capital)
            if total_loss_pct > 0.10:  # 10% total loss
                logger.warning(f"Total loss limit breached: {total_loss_pct:.2%}")
                self.is_trading_enabled = False
                await self._close_all_positions()
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking risk limits: {e}")
            return False
    
    async def run(self):
        """Main trading loop"""
        logger.info(f"Starting live trading for {self.symbol}")
        
        try:
            # Initialize components
            await self.initialize()
            
            # Main trading loop
            while True:
                # Check risk limits
                if not await self.check_risk_limits():
                    logger.error("Risk limits breached, stopping trading")
                    break
                
                # Log status every minute
                if datetime.now().second == 0:
                    self._log_status()
                
                # Sleep briefly
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Trading stopped by user")
        except Exception as e:
            logger.error(f"Trading error: {e}")
        finally:
            # Cleanup
            await self.shutdown()
    
    def _log_status(self):
        """Log current trading status"""
        positions_str = f"{len(self.positions)} positions" if self.positions else "No positions"
        win_rate = (self.win_count / self.trade_count * 100) if self.trade_count > 0 else 0
        
        logger.info(
            f"Status: {positions_str} | "
            f"P&L: ${self.total_pnl:.2f} | "
            f"Daily: ${self.daily_pnl:.2f} | "
            f"Trades: {self.trade_count} | "
            f"Win Rate: {win_rate:.1f}%"
        )
    
    async def shutdown(self):
        """Shutdown trading and cleanup"""
        logger.info("Shutting down live trading...")
        
        # Close all positions
        await self._close_all_positions()
        
        # Close WebSocket
        if self.ws_manager:
            await self.ws_manager.close()
        
        # Log final statistics
        logger.info(f"Final P&L: ${self.total_pnl:.2f}")
        logger.info(f"Total Trades: {self.trade_count}")
        logger.info(f"Win Rate: {(self.win_count / self.trade_count * 100) if self.trade_count > 0 else 0:.1f}%")