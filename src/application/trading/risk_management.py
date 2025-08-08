"""
Risk Management System

Comprehensive risk management for live trading including position sizing,
exposure limits, drawdown protection, and emergency controls.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level classifications"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RiskMetrics:
    """Current risk metrics"""
    total_exposure: float
    position_count: int
    unrealized_pnl: float
    realized_pnl: float
    daily_pnl: float
    max_drawdown: float
    current_drawdown: float
    risk_level: RiskLevel
    var_95: float  # Value at Risk 95%
    sharpe_ratio: float
    timestamp: datetime


@dataclass
class RiskLimits:
    """Risk limit configuration"""
    max_position_size_pct: float = 0.10  # Max 10% per position
    max_total_exposure_pct: float = 0.95  # Max 95% total exposure
    max_daily_loss_pct: float = 0.02  # Max 2% daily loss
    max_drawdown_pct: float = 0.10  # Max 10% drawdown
    max_positions: int = 10  # Maximum concurrent positions
    max_correlation: float = 0.7  # Maximum correlation between positions
    min_free_margin_pct: float = 0.20  # Minimum 20% free margin
    max_leverage: float = 3.0  # Maximum leverage


class RiskManagementSystem:
    """
    Comprehensive risk management system for live trading
    """
    
    def __init__(
        self,
        initial_capital: float,
        risk_limits: Optional[RiskLimits] = None,
        emergency_stop_loss: float = 0.15  # 15% emergency stop
    ):
        """
        Initialize risk management system
        
        Args:
            initial_capital: Starting capital amount
            risk_limits: Risk limit configuration
            emergency_stop_loss: Emergency stop loss percentage
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.risk_limits = risk_limits or RiskLimits()
        self.emergency_stop_loss = emergency_stop_loss
        
        # Position tracking
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.position_correlations: pd.DataFrame = pd.DataFrame()
        
        # P&L tracking
        self.daily_pnl_history: List[float] = []
        self.peak_capital = initial_capital
        self.max_drawdown = 0.0
        self.current_drawdown = 0.0
        
        # Risk metrics history
        self.metrics_history: List[RiskMetrics] = []
        self.last_reset_date = datetime.now().date()
        
        # Emergency controls
        self.trading_enabled = True
        self.emergency_triggered = False
        self.risk_warnings: List[str] = []
        
        logger.info(f"Risk Management System initialized with ${initial_capital:.2f}")
    
    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss_price: float,
        account_risk_pct: float = 0.01  # Risk 1% per trade
    ) -> float:
        """
        Calculate optimal position size using Kelly Criterion and risk limits
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            stop_loss_price: Stop loss price
            account_risk_pct: Percentage of account to risk
            
        Returns:
            Optimal position size
        """
        try:
            # Calculate risk per unit
            risk_per_unit = abs(entry_price - stop_loss_price)
            
            # Calculate position size based on account risk
            risk_amount = self.current_capital * account_risk_pct
            position_size = risk_amount / risk_per_unit
            
            # Apply position size limits
            max_position_value = self.current_capital * self.risk_limits.max_position_size_pct
            max_position_size = max_position_value / entry_price
            
            # Use the smaller of the two
            position_size = min(position_size, max_position_size)
            
            # Check total exposure
            current_exposure = self._calculate_total_exposure()
            new_exposure = current_exposure + (position_size * entry_price)
            max_exposure = self.current_capital * self.risk_limits.max_total_exposure_pct
            
            if new_exposure > max_exposure:
                # Reduce position size to fit within exposure limit
                available_exposure = max_exposure - current_exposure
                if available_exposure > 0:
                    position_size = available_exposure / entry_price
                else:
                    logger.warning("Maximum exposure reached, cannot open new position")
                    return 0
            
            # Check position count limit
            if len(self.positions) >= self.risk_limits.max_positions:
                logger.warning("Maximum position count reached")
                return 0
            
            logger.info(f"Calculated position size: {position_size:.4f} for {symbol}")
            return position_size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0
    
    def check_risk_limits(self) -> bool:
        """
        Check if any risk limits are breached
        
        Returns:
            True if trading can continue, False if limits breached
        """
        try:
            self.risk_warnings.clear()
            
            # Check daily loss limit
            daily_loss_pct = abs(self._get_daily_pnl() / self.initial_capital)
            if daily_loss_pct > self.risk_limits.max_daily_loss_pct:
                self.risk_warnings.append(f"Daily loss limit breached: {daily_loss_pct:.2%}")
                self.trading_enabled = False
                return False
            
            # Check maximum drawdown
            if self.current_drawdown > self.risk_limits.max_drawdown_pct:
                self.risk_warnings.append(f"Max drawdown breached: {self.current_drawdown:.2%}")
                self.trading_enabled = False
                return False
            
            # Check emergency stop loss
            total_loss_pct = (self.initial_capital - self.current_capital) / self.initial_capital
            if total_loss_pct > self.emergency_stop_loss:
                self.risk_warnings.append(f"Emergency stop loss triggered: {total_loss_pct:.2%}")
                self.emergency_triggered = True
                self.trading_enabled = False
                return False
            
            # Check free margin
            free_margin_pct = self._calculate_free_margin()
            if free_margin_pct < self.risk_limits.min_free_margin_pct:
                self.risk_warnings.append(f"Low free margin: {free_margin_pct:.2%}")
                # Don't disable trading, but warn
            
            # Check total exposure
            exposure_pct = self._calculate_total_exposure() / self.current_capital
            if exposure_pct > self.risk_limits.max_total_exposure_pct:
                self.risk_warnings.append(f"Exposure limit reached: {exposure_pct:.2%}")
                # Don't open new positions
            
            return self.trading_enabled
            
        except Exception as e:
            logger.error(f"Error checking risk limits: {e}")
            return False
    
    def update_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        current_price: float,
        side: str = 'LONG'
    ):
        """Update or add a position"""
        try:
            if symbol in self.positions:
                # Update existing position
                position = self.positions[symbol]
                position['current_price'] = current_price
                
                # Calculate P&L
                if side == 'LONG':
                    position['unrealized_pnl'] = (current_price - entry_price) * quantity
                else:
                    position['unrealized_pnl'] = (entry_price - current_price) * quantity
                
                position['pnl_pct'] = position['unrealized_pnl'] / (entry_price * quantity) * 100
            else:
                # Add new position
                self.positions[symbol] = {
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'entry_time': datetime.now(),
                    'unrealized_pnl': 0,
                    'pnl_pct': 0
                }
            
            # Update drawdown
            self._update_drawdown()
            
        except Exception as e:
            logger.error(f"Error updating position: {e}")
    
    def close_position(self, symbol: str, exit_price: float) -> float:
        """
        Close a position and calculate realized P&L
        
        Returns:
            Realized P&L amount
        """
        try:
            if symbol not in self.positions:
                logger.warning(f"Position {symbol} not found")
                return 0
            
            position = self.positions[symbol]
            quantity = position['quantity']
            entry_price = position['entry_price']
            
            # Calculate realized P&L
            if position['side'] == 'LONG':
                realized_pnl = (exit_price - entry_price) * quantity
            else:
                realized_pnl = (entry_price - exit_price) * quantity
            
            # Update capital
            self.current_capital += realized_pnl
            
            # Update daily P&L
            self._update_daily_pnl(realized_pnl)
            
            # Remove position
            del self.positions[symbol]
            
            logger.info(f"Closed {symbol}: P&L=${realized_pnl:.2f}")
            return realized_pnl
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return 0
    
    def _calculate_total_exposure(self) -> float:
        """Calculate total market exposure"""
        total = 0
        for position in self.positions.values():
            total += position['quantity'] * position['current_price']
        return total
    
    def _calculate_free_margin(self) -> float:
        """Calculate free margin percentage"""
        total_exposure = self._calculate_total_exposure()
        used_margin = total_exposure / self.risk_limits.max_leverage
        free_margin = self.current_capital - used_margin
        return free_margin / self.current_capital if self.current_capital > 0 else 0
    
    def _get_daily_pnl(self) -> float:
        """Get current daily P&L"""
        # Reset if new day
        if datetime.now().date() > self.last_reset_date:
            self.daily_pnl_history.append(self._calculate_current_daily_pnl())
            self.last_reset_date = datetime.now().date()
            return 0
        
        return self._calculate_current_daily_pnl()
    
    def _calculate_current_daily_pnl(self) -> float:
        """Calculate current daily P&L including unrealized"""
        daily_pnl = 0
        for position in self.positions.values():
            daily_pnl += position.get('unrealized_pnl', 0)
        return daily_pnl
    
    def _update_daily_pnl(self, realized_pnl: float):
        """Update daily P&L with realized amount"""
        # This would be tracked properly in a production system
        pass
    
    def _update_drawdown(self):
        """Update drawdown metrics"""
        # Update peak capital
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital
        
        # Calculate current drawdown
        if self.peak_capital > 0:
            self.current_drawdown = (self.peak_capital - self.current_capital) / self.peak_capital
        
        # Update maximum drawdown
        if self.current_drawdown > self.max_drawdown:
            self.max_drawdown = self.current_drawdown
    
    def calculate_var(self, confidence_level: float = 0.95) -> float:
        """
        Calculate Value at Risk
        
        Args:
            confidence_level: Confidence level (e.g., 0.95 for 95% VaR)
            
        Returns:
            VaR amount
        """
        try:
            if len(self.daily_pnl_history) < 20:
                # Not enough history
                return self.current_capital * 0.02  # Default 2%
            
            # Calculate historical VaR
            returns = pd.Series(self.daily_pnl_history) / self.initial_capital
            var_percentile = (1 - confidence_level) * 100
            var = np.percentile(returns, var_percentile)
            
            return abs(var * self.current_capital)
            
        except Exception as e:
            logger.error(f"Error calculating VaR: {e}")
            return self.current_capital * 0.02
    
    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        try:
            if len(self.daily_pnl_history) < 20:
                return 0
            
            returns = pd.Series(self.daily_pnl_history) / self.initial_capital
            excess_returns = returns - risk_free_rate / 365
            
            if returns.std() > 0:
                return np.sqrt(365) * excess_returns.mean() / returns.std()
            
            return 0
            
        except Exception as e:
            logger.error(f"Error calculating Sharpe ratio: {e}")
            return 0
    
    def get_risk_metrics(self) -> RiskMetrics:
        """Get current risk metrics"""
        # Determine risk level
        if self.emergency_triggered:
            risk_level = RiskLevel.CRITICAL
        elif self.current_drawdown > 0.08:
            risk_level = RiskLevel.HIGH
        elif self.current_drawdown > 0.05:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW
        
        metrics = RiskMetrics(
            total_exposure=self._calculate_total_exposure(),
            position_count=len(self.positions),
            unrealized_pnl=sum(p.get('unrealized_pnl', 0) for p in self.positions.values()),
            realized_pnl=self.current_capital - self.initial_capital,
            daily_pnl=self._get_daily_pnl(),
            max_drawdown=self.max_drawdown,
            current_drawdown=self.current_drawdown,
            risk_level=risk_level,
            var_95=self.calculate_var(0.95),
            sharpe_ratio=self.calculate_sharpe_ratio(),
            timestamp=datetime.now()
        )
        
        # Store in history
        self.metrics_history.append(metrics)
        
        return metrics
    
    def should_close_all_positions(self) -> bool:
        """Check if all positions should be closed immediately"""
        return self.emergency_triggered or not self.trading_enabled
    
    def reset_daily_limits(self):
        """Reset daily limits (call at start of new trading day)"""
        self.last_reset_date = datetime.now().date()
        
        # Re-enable trading if daily loss was the only issue
        if not self.emergency_triggered and self.current_drawdown < self.risk_limits.max_drawdown_pct:
            self.trading_enabled = True
            logger.info("Daily limits reset, trading re-enabled")
    
    def get_risk_report(self) -> Dict[str, Any]:
        """Generate comprehensive risk report"""
        metrics = self.get_risk_metrics()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'risk_level': metrics.risk_level.value,
            'trading_enabled': self.trading_enabled,
            'emergency_triggered': self.emergency_triggered,
            'capital': {
                'initial': self.initial_capital,
                'current': self.current_capital,
                'peak': self.peak_capital
            },
            'positions': {
                'count': len(self.positions),
                'total_exposure': metrics.total_exposure,
                'exposure_pct': metrics.total_exposure / self.current_capital if self.current_capital > 0 else 0
            },
            'pnl': {
                'unrealized': metrics.unrealized_pnl,
                'realized': metrics.realized_pnl,
                'daily': metrics.daily_pnl,
                'total': metrics.unrealized_pnl + metrics.realized_pnl
            },
            'risk_metrics': {
                'current_drawdown': f"{metrics.current_drawdown:.2%}",
                'max_drawdown': f"{metrics.max_drawdown:.2%}",
                'var_95': metrics.var_95,
                'sharpe_ratio': metrics.sharpe_ratio
            },
            'limits': {
                'max_position_size': f"{self.risk_limits.max_position_size_pct:.1%}",
                'max_exposure': f"{self.risk_limits.max_total_exposure_pct:.1%}",
                'max_daily_loss': f"{self.risk_limits.max_daily_loss_pct:.1%}",
                'max_drawdown': f"{self.risk_limits.max_drawdown_pct:.1%}"
            },
            'warnings': self.risk_warnings
        }