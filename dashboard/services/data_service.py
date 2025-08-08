"""
Data Service for Dashboard
Handles all communication with the trading system backend
"""

import requests
import json
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import yaml
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataService:
    """Service for fetching data from backend APIs and database"""
    
    def __init__(self):
        """Initialize data service with API and database connections"""
        # API configuration
        self.api_base_url = "http://localhost:8000/api/v1"
        self.headers = {"Content-Type": "application/json"}
        
        # Database configuration
        self.db_config = self._load_db_config()
        
        # Cache for frequently accessed data
        self.cache = {}
        self.cache_ttl = 5  # seconds
        self.last_cache_update = {}
    
    def _load_db_config(self) -> Dict:
        """Load database configuration from config file"""
        try:
            config_path = Path(__file__).parent.parent.parent / "config" / "live_trading_config.yaml"
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            db_config = config.get('data', {}).get('database', {})
            return {
                'host': db_config.get('host', 'localhost'),
                'port': db_config.get('port', 5432),
                'database': db_config.get('name', 'tradingbot'),
                'user': db_config.get('user'),
                'password': db_config.get('password')
            }
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {
                'host': 'localhost',
                'port': 5432,
                'database': 'tradingbot'
            }
    
    def _get_db_connection(self):
        """Get database connection"""
        try:
            # Filter out None values
            conn_params = {k: v for k, v in self.db_config.items() if v is not None}
            return psycopg2.connect(**conn_params)
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return None
    
    # ==================== System Status ====================
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        try:
            # Try API first
            response = requests.get(f"{self.api_base_url}/live-trading/session/status", timeout=2)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        
        # Fallback to database/file check
        try:
            # Check if there's a running process
            config_path = Path(__file__).parent.parent.parent / "config" / "live_trading_config.yaml"
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Get active strategy
            active_strategy = None
            for strategy, settings in config.get('strategy', {}).items():
                if settings.get('enabled'):
                    active_strategy = strategy
                    break
            
            return {
                'trading_enabled': False,  # Default to stopped
                'current_capital': config.get('capital', {}).get('initial_capital', 0),
                'position_count': 0,
                'active_strategy': active_strategy
            }
        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return {}
    
    # ==================== Positions & PnL ====================
    
    def get_positions(self) -> List[Dict]:
        """Get current open positions"""
        # Check cache first
        if self._is_cache_valid('positions'):
            return self.cache.get('positions', [])
        
        try:
            # Try API
            response = requests.get(f"{self.api_base_url}/live-trading/positions", timeout=2)
            if response.status_code == 200:
                positions = response.json()
                self._update_cache('positions', positions)
                return positions
        except:
            pass
        
        # Fallback to database
        try:
            conn = self._get_db_connection()
            if conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            symbol,
                            side,
                            quantity,
                            entry_price,
                            current_price,
                            unrealized_pnl,
                            realized_pnl,
                            created_at
                        FROM positions
                        WHERE status = 'OPEN'
                        ORDER BY created_at DESC
                    """)
                    positions = cur.fetchall()
                    
                    # Convert to serializable format
                    for pos in positions:
                        pos['entry_price'] = float(pos['entry_price']) if pos['entry_price'] else 0
                        pos['current_price'] = float(pos['current_price']) if pos['current_price'] else 0
                        pos['quantity'] = float(pos['quantity']) if pos['quantity'] else 0
                        pos['unrealized_pnl'] = float(pos['unrealized_pnl']) if pos['unrealized_pnl'] else 0
                        pos['realized_pnl'] = float(pos['realized_pnl']) if pos['realized_pnl'] else 0
                        pos['created_at'] = pos['created_at'].isoformat() if pos['created_at'] else None
                        
                        # Calculate PnL percentage
                        if pos['entry_price'] > 0:
                            pos['pnl_pct'] = ((pos['current_price'] - pos['entry_price']) / pos['entry_price']) * 100
                        else:
                            pos['pnl_pct'] = 0
                    
                    conn.close()
                    self._update_cache('positions', positions)
                    return positions
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
        
        return []
    
    def get_pnl_summary(self) -> Dict[str, float]:
        """Get PnL summary"""
        try:
            positions = self.get_positions()
            trades = self.get_recent_trades(limit=100)
            
            # Calculate metrics
            total_unrealized = sum(p.get('unrealized_pnl', 0) for p in positions)
            total_realized = sum(t.get('pnl', 0) for t in trades if t.get('status') == 'FILLED')
            
            # Daily PnL (trades from today)
            today = datetime.now().date()
            daily_pnl = sum(
                t.get('pnl', 0) for t in trades 
                if t.get('status') == 'FILLED' and 
                datetime.fromisoformat(t.get('filled_at', '')).date() == today
            )
            
            # Win rate
            winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
            total_trades = len([t for t in trades if t.get('status') == 'FILLED'])
            win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
            
            return {
                'total_pnl': total_unrealized + total_realized,
                'unrealized_pnl': total_unrealized,
                'realized_pnl': total_realized,
                'daily_pnl': daily_pnl,
                'win_rate': win_rate,
                'total_trades': total_trades,
                'open_positions': len(positions)
            }
        except Exception as e:
            logger.error(f"Failed to get PnL summary: {e}")
            return {
                'total_pnl': 0,
                'unrealized_pnl': 0,
                'realized_pnl': 0,
                'daily_pnl': 0,
                'win_rate': 0,
                'total_trades': 0,
                'open_positions': 0
            }
    
    def get_recent_trades(self, limit: int = 50) -> List[Dict]:
        """Get recent trades"""
        try:
            conn = self._get_db_connection()
            if conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            id,
                            symbol,
                            side,
                            quantity,
                            price,
                            status,
                            filled_quantity,
                            filled_price,
                            fee,
                            created_at,
                            filled_at
                        FROM orders
                        WHERE status IN ('FILLED', 'PARTIALLY_FILLED')
                        ORDER BY created_at DESC
                        LIMIT %s
                    """, (limit,))
                    
                    trades = cur.fetchall()
                    
                    # Convert to serializable format
                    for trade in trades:
                        for key in ['quantity', 'price', 'filled_quantity', 'filled_price', 'fee']:
                            if trade.get(key):
                                trade[key] = float(trade[key])
                        
                        for key in ['created_at', 'filled_at']:
                            if trade.get(key):
                                trade[key] = trade[key].isoformat()
                        
                        # Calculate simple PnL (this is simplified, real PnL calculation is more complex)
                        if trade.get('filled_price') and trade.get('price'):
                            if trade['side'] == 'BUY':
                                trade['pnl'] = 0  # PnL calculated on sell
                            else:
                                trade['pnl'] = (trade['filled_price'] - trade['price']) * trade.get('filled_quantity', 0)
                    
                    conn.close()
                    return trades
        except Exception as e:
            logger.error(f"Failed to get recent trades: {e}")
        
        return []
    
    # ==================== Risk Metrics ====================
    
    def get_risk_metrics(self) -> Dict[str, Any]:
        """Get current risk metrics"""
        try:
            response = requests.get(f"{self.api_base_url}/live-trading/risk-metrics", timeout=2)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        
        # Calculate basic metrics from positions
        try:
            positions = self.get_positions()
            config = self.load_config()
            
            initial_capital = config.get('capital', {}).get('initial_capital', 10000)
            total_exposure = sum(p.get('quantity', 0) * p.get('current_price', 0) for p in positions)
            
            return {
                'total_exposure': total_exposure,
                'exposure_pct': (total_exposure / initial_capital * 100) if initial_capital > 0 else 0,
                'position_count': len(positions),
                'max_position_size': config.get('risk_management', {}).get('max_position_size_pct', 10),
                'max_drawdown': config.get('risk_management', {}).get('max_drawdown_pct', 10),
                'current_drawdown': 0,  # Would need historical data to calculate
                'risk_level': 'MEDIUM' if total_exposure > initial_capital * 0.5 else 'LOW'
            }
        except Exception as e:
            logger.error(f"Failed to get risk metrics: {e}")
            return {}
    
    # ==================== Strategy Management ====================
    
    def load_config(self) -> Dict:
        """Load current configuration"""
        try:
            config_path = Path(__file__).parent.parent.parent / "config" / "live_trading_config.yaml"
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def save_config(self, config: Dict) -> bool:
        """Save configuration"""
        try:
            config_path = Path(__file__).parent.parent.parent / "config" / "live_trading_config.yaml"
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def deploy_strategy(self, strategy_config: Dict) -> bool:
        """Deploy a new strategy configuration"""
        try:
            # Update config file
            config = self.load_config()
            
            # Disable all strategies first
            for strategy in config.get('strategy', {}).values():
                if isinstance(strategy, dict):
                    strategy['enabled'] = False
            
            # Enable selected strategy
            strategy_type = strategy_config.get('type')
            if strategy_type in config.get('strategy', {}):
                config['strategy'][strategy_type]['enabled'] = True
                
                # Update strategy parameters
                if 'symbols' in config['strategy'][strategy_type]:
                    # Update first symbol (for now)
                    config['strategy'][strategy_type]['symbols'][0].update(strategy_config.get('params', {}))
            
            # Update capital and risk settings
            if 'capital' in strategy_config:
                config['capital']['initial_capital'] = strategy_config['capital']
            
            if 'risk_limits' in strategy_config:
                config['risk_management'].update(strategy_config['risk_limits'])
            
            # Save config
            if self.save_config(config):
                # Restart trading service (would need actual implementation)
                logger.info("Strategy deployed successfully")
                return True
        except Exception as e:
            logger.error(f"Failed to deploy strategy: {e}")
        
        return False
    
    # ==================== Trading Controls ====================
    
    def start_trading(self) -> bool:
        """Start trading"""
        try:
            response = requests.post(f"{self.api_base_url}/live-trading/session/start")
            return response.status_code == 200
        except:
            return False
    
    def stop_trading(self) -> bool:
        """Stop trading"""
        try:
            response = requests.post(f"{self.api_base_url}/live-trading/session/stop")
            return response.status_code == 200
        except:
            return False
    
    def pause_trading(self) -> bool:
        """Pause trading"""
        try:
            response = requests.post(f"{self.api_base_url}/live-trading/session/pause")
            return response.status_code == 200
        except:
            return False
    
    def resume_trading(self) -> bool:
        """Resume trading"""
        try:
            response = requests.post(f"{self.api_base_url}/live-trading/session/resume")
            return response.status_code == 200
        except:
            return False
    
    def emergency_stop(self) -> bool:
        """Emergency stop - close all positions"""
        try:
            response = requests.post(f"{self.api_base_url}/live-trading/emergency-stop")
            return response.status_code == 200
        except:
            return False
    
    def close_position(self, position_id: str) -> bool:
        """Close a specific position"""
        try:
            response = requests.post(
                f"{self.api_base_url}/live-trading/positions/{position_id}/close"
            )
            return response.status_code == 200
        except:
            return False
    
    # ==================== Historical Data ====================
    
    def get_performance_history(self, days: int = 30) -> pd.DataFrame:
        """Get historical performance data"""
        try:
            conn = self._get_db_connection()
            if conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            DATE(created_at) as date,
                            COUNT(*) as trades,
                            SUM(CASE WHEN side = 'SELL' AND filled_price > price THEN 1 ELSE 0 END) as wins,
                            SUM(filled_quantity * filled_price - filled_quantity * price) as daily_pnl
                        FROM orders
                        WHERE status = 'FILLED'
                        AND created_at >= NOW() - INTERVAL '%s days'
                        GROUP BY DATE(created_at)
                        ORDER BY date
                    """, (days,))
                    
                    data = cur.fetchall()
                    conn.close()
                    
                    if data:
                        df = pd.DataFrame(data)
                        df['date'] = pd.to_datetime(df['date'])
                        df['cumulative_pnl'] = df['daily_pnl'].cumsum()
                        df['win_rate'] = (df['wins'] / df['trades'] * 100).round(2)
                        return df
        except Exception as e:
            logger.error(f"Failed to get performance history: {e}")
        
        # Return empty dataframe
        return pd.DataFrame(columns=['date', 'trades', 'wins', 'daily_pnl', 'cumulative_pnl', 'win_rate'])
    
    # ==================== Cache Management ====================
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache is still valid"""
        if key not in self.cache:
            return False
        
        last_update = self.last_cache_update.get(key, datetime.min)
        return (datetime.now() - last_update).total_seconds() < self.cache_ttl
    
    def _update_cache(self, key: str, data: Any):
        """Update cache with new data"""
        self.cache[key] = data
        self.last_cache_update[key] = datetime.now()