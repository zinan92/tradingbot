"""
Risk Port

Abstract interface for risk management operations.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
from enum import Enum


class RiskAction(Enum):
    """Risk validation actions"""
    ALLOW = "allow"
    ADJUST = "adjust"
    BLOCK = "block"


class RiskPort(ABC):
    """Abstract interface for risk management operations"""
    
    @abstractmethod
    async def validate_trade(
        self,
        order: Dict[str, Any],
        portfolio_state: Dict[str, Any]
    ) -> Tuple[RiskAction, str, Optional[Dict[str, Any]]]:
        """
        Validate a trade against risk rules
        
        Args:
            order: Order details to validate
            portfolio_state: Current portfolio state including:
                - positions: List of open positions
                - balance: Available balance
                - equity: Total equity
                - margin_used: Margin in use
                - exposure: Current market exposure
                
        Returns:
            Tuple of:
                - action: RiskAction (allow, adjust, or block)
                - reason: Explanation for the action
                - adjustments: Optional dictionary of suggested adjustments
        """
        pass
    
    @abstractmethod
    async def calculate_position_size(
        self,
        symbol: str,
        entry_price: Decimal,
        stop_loss: Optional[Decimal],
        portfolio_value: Decimal,
        risk_per_trade: Decimal
    ) -> Decimal:
        """
        Calculate optimal position size based on risk parameters
        
        Args:
            symbol: Trading pair symbol
            entry_price: Planned entry price
            stop_loss: Stop loss price (if applicable)
            portfolio_value: Total portfolio value
            risk_per_trade: Maximum risk per trade (as decimal, e.g., 0.02 for 2%)
            
        Returns:
            Recommended position size
        """
        pass
    
    @abstractmethod
    async def check_exposure_limits(
        self,
        portfolio_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check current exposure against limits
        
        Args:
            portfolio_state: Current portfolio state
            
        Returns:
            Dictionary with exposure metrics and limit violations
        """
        pass
    
    @abstractmethod
    async def calculate_var(
        self,
        positions: List[Dict[str, Any]],
        confidence_level: float = 0.95,
        time_horizon: int = 1
    ) -> Decimal:
        """
        Calculate Value at Risk
        
        Args:
            positions: List of position dictionaries
            confidence_level: VaR confidence level (default 95%)
            time_horizon: Time horizon in days
            
        Returns:
            Value at Risk amount
        """
        pass
    
    @abstractmethod
    async def get_risk_metrics(
        self,
        portfolio_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get comprehensive risk metrics for the portfolio
        
        Returns:
            Dictionary containing:
                - total_exposure: Total market exposure
                - leverage: Current leverage ratio
                - max_drawdown: Maximum drawdown
                - sharpe_ratio: Sharpe ratio
                - risk_score: Overall risk score
        """
        pass
    
    @abstractmethod
    async def validate_stop_loss(
        self,
        symbol: str,
        entry_price: Decimal,
        stop_loss: Decimal,
        position_side: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate stop loss placement
        
        Args:
            symbol: Trading pair symbol
            entry_price: Entry price
            stop_loss: Proposed stop loss price
            position_side: 'long' or 'short'
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    async def get_risk_summary(self) -> Dict[str, Any]:
        """
        Get current risk summary for monitoring
        
        Returns:
            Dictionary containing:
                - exposure_pct: Current exposure as percentage of capital
                - daily_loss_pct: Today's loss as percentage
                - drawdown_pct: Current drawdown percentage
                - risk_level: Overall risk level (low/medium/high/critical)
                - thresholds: Risk thresholds being monitored
        """
        pass