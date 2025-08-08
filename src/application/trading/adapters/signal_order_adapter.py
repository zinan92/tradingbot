"""
Signal to Order Adapter

Converts trading signals from strategies into executable orders
with proper position sizing and risk management.
"""
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional, Tuple
from uuid import UUID

from src.config.trading_config import TradingConfig, get_config
from src.domain.strategy.events import SignalGenerated
from src.domain.trading.aggregates.order import Order
from src.domain.trading.aggregates.portfolio import Portfolio
from src.domain.trading.value_objects.price import Price
from src.domain.trading.value_objects.quantity import Quantity
from src.domain.trading.value_objects.leverage import Leverage
from src.domain.trading.value_objects.side import PositionSide

logger = logging.getLogger(__name__)


@dataclass
class OrderParameters:
    """Parameters for order creation"""
    symbol: str
    quantity: int
    order_type: str
    side: str  # BUY/SELL
    position_side: Optional[str] = None  # LONG/SHORT
    leverage: Optional[int] = None
    price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    reduce_only: bool = False
    
    def validate(self) -> bool:
        """Validate order parameters"""
        if self.quantity <= 0:
            return False
        
        if self.order_type not in ["MARKET", "LIMIT", "STOP", "STOP_MARKET"]:
            return False
        
        if self.order_type == "LIMIT" and not self.price:
            return False
        
        if self.leverage and (self.leverage < 1 or self.leverage > 125):
            return False
        
        return True


class SignalOrderAdapter:
    """
    Adapts trading signals into executable orders.
    
    Handles:
    - Signal interpretation
    - Position sizing
    - Order type determination
    - Risk parameter calculation
    """
    
    def __init__(self, config: Optional[TradingConfig] = None):
        """
        Initialize adapter.
        
        Args:
            config: Trading configuration
        """
        self.config = config or get_config()
        logger.info("SignalOrderAdapter initialized")
    
    async def adapt_signal(
        self,
        signal: SignalGenerated,
        portfolio: Portfolio,
        current_price: Decimal
    ) -> Optional[OrderParameters]:
        """
        Convert signal to order parameters.
        
        Args:
            signal: Trading signal from strategy
            portfolio: Current portfolio state
            current_price: Current market price
            
        Returns:
            OrderParameters or None if signal should not be executed
        """
        logger.debug(f"Adapting signal: {signal.symbol} {signal.signal_type}")
        
        # Check if signal should be executed
        if not self._should_execute_signal(signal):
            return None
        
        # Get signal mapping
        mapping = self._get_signal_mapping(signal.signal_type)
        if not mapping:
            logger.warning(f"No mapping for signal type: {signal.signal_type}")
            return None
        
        # Check for hold signal
        if mapping.get("action") == "none":
            logger.debug(f"Signal {signal.signal_type} mapped to no action")
            return None
        
        # Determine order side and position side
        order_side, position_side = self._determine_sides(signal.signal_type, mapping)
        
        # Calculate position size
        quantity = await self._calculate_position_size(
            portfolio=portfolio,
            signal=signal,
            current_price=current_price,
            size_multiplier=mapping.get("size_multiplier", 1.0)
        )
        
        if quantity <= 0:
            logger.info("Calculated position size is 0")
            return None
        
        # Check risk limits
        if not self._check_risk_limits(portfolio, signal.symbol, quantity, current_price):
            logger.warning("Risk limits exceeded")
            return None
        
        # Determine order type and price
        order_type, order_price = self._determine_order_type_and_price(
            signal=signal,
            mapping=mapping,
            current_price=current_price,
            order_side=order_side
        )
        
        # Calculate stop loss and take profit
        stop_loss, take_profit = self._calculate_risk_levels(
            entry_price=order_price or current_price,
            position_side=position_side
        )
        
        # Create order parameters
        params = OrderParameters(
            symbol=signal.symbol,
            quantity=quantity,
            order_type=order_type,
            side=order_side,
            position_side=position_side,
            leverage=self.config.risk.max_leverage,
            price=order_price if order_type == "LIMIT" else None,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reduce_only=mapping.get("reduce_only", False)
        )
        
        if not params.validate():
            logger.error("Invalid order parameters generated")
            return None
        
        logger.info(f"Adapted signal to order: {params.symbol} {params.side} {params.quantity} @ {params.order_type}")
        
        return params
    
    def _should_execute_signal(self, signal: SignalGenerated) -> bool:
        """
        Check if signal meets execution criteria.
        
        Args:
            signal: Trading signal
            
        Returns:
            True if signal should be executed
        """
        # Check auto-execute enabled
        if not self.config.signal.auto_execute:
            logger.debug("Auto-execute disabled")
            return False
        
        # Check confidence threshold
        if signal.confidence < self.config.signal.confidence_threshold:
            logger.info(f"Signal confidence {signal.confidence} below threshold")
            return False
        
        # Check strength threshold
        if signal.strength < self.config.signal.strength_threshold:
            logger.info(f"Signal strength {signal.strength} below threshold")
            return False
        
        return True
    
    def _get_signal_mapping(self, signal_type: str) -> Optional[Dict]:
        """
        Get configuration mapping for signal type.
        
        Args:
            signal_type: Type of signal
            
        Returns:
            Mapping configuration or None
        """
        return self.config.signal.signal_mappings.get(signal_type)
    
    def _determine_sides(self, signal_type: str, mapping: Dict) -> Tuple[str, str]:
        """
        Determine order side and position side from signal.
        
        Args:
            signal_type: Type of signal
            mapping: Signal mapping configuration
            
        Returns:
            Tuple of (order_side, position_side)
        """
        # Check if explicitly specified in mapping
        if "position_side" in mapping:
            position_side = mapping["position_side"]
            
            if mapping.get("reduce_only"):
                # Closing position - reverse side
                order_side = "SELL" if position_side == "LONG" else "BUY"
            else:
                # Opening position
                order_side = "BUY" if position_side == "LONG" else "SELL"
        else:
            # Infer from signal type
            if "BUY" in signal_type or "LONG" in signal_type:
                order_side = "BUY"
                position_side = "LONG"
            elif "SELL" in signal_type or "SHORT" in signal_type:
                order_side = "SELL"
                position_side = "SHORT"
            else:
                # Default to long
                order_side = "BUY"
                position_side = "LONG"
        
        return order_side, position_side
    
    async def _calculate_position_size(
        self,
        portfolio: Portfolio,
        signal: SignalGenerated,
        current_price: Decimal,
        size_multiplier: float
    ) -> int:
        """
        Calculate position size based on portfolio and signal.
        
        Args:
            portfolio: Current portfolio state
            signal: Trading signal
            current_price: Current market price
            size_multiplier: Size adjustment factor
            
        Returns:
            Position size in units
        """
        # Base position value calculation
        if self.config.position_sizing.use_kelly_criterion:
            position_value = self._kelly_position_size(
                portfolio=portfolio,
                signal=signal
            )
        else:
            position_value = self._fixed_position_size(portfolio)
        
        # Apply multipliers
        position_value *= Decimal(str(size_multiplier))
        position_value *= signal.strength  # Scale by signal strength
        
        # Apply limits
        position_value = min(position_value, self.config.risk.max_position_size_usdt)
        
        # Account for leverage
        leveraged_value = position_value * Decimal(str(self.config.risk.max_leverage))
        
        # Calculate quantity
        quantity = int(leveraged_value / current_price)
        
        logger.debug(f"Calculated position size: {quantity} units (value: {position_value} USDT)")
        
        return quantity
    
    def _kelly_position_size(
        self,
        portfolio: Portfolio,
        signal: SignalGenerated
    ) -> Decimal:
        """
        Calculate position size using Kelly criterion.
        
        Args:
            portfolio: Current portfolio
            signal: Trading signal
            
        Returns:
            Position value in USDT
        """
        # Extract win probability from signal confidence
        win_prob = float(signal.confidence)
        
        # Extract expected win/loss ratio from signal parameters
        # Default to 2:1 reward/risk if not specified
        win_loss_ratio = float(signal.parameters.get("expected_rr", 2.0))
        
        # Kelly formula: f = (p * b - q) / b
        # where f = fraction, p = win prob, q = loss prob, b = win/loss ratio
        loss_prob = 1 - win_prob
        kelly_fraction = (win_prob * win_loss_ratio - loss_prob) / win_loss_ratio
        
        # Apply Kelly fraction limit (conservative)
        kelly_fraction = max(0, min(kelly_fraction, float(self.config.position_sizing.kelly_fraction)))
        
        # Calculate position value
        position_value = portfolio.available_cash * Decimal(str(kelly_fraction))
        
        logger.debug(f"Kelly fraction: {kelly_fraction:.4f}, Position value: {position_value}")
        
        return position_value
    
    def _fixed_position_size(self, portfolio: Portfolio) -> Decimal:
        """
        Calculate fixed percentage position size.
        
        Args:
            portfolio: Current portfolio
            
        Returns:
            Position value in USDT
        """
        percentage = self.config.position_sizing.default_position_size_percent / 100
        return portfolio.available_cash * percentage
    
    def _check_risk_limits(
        self,
        portfolio: Portfolio,
        symbol: str,
        quantity: int,
        price: Decimal
    ) -> bool:
        """
        Check if order passes risk limits.
        
        Args:
            portfolio: Current portfolio
            symbol: Trading symbol
            quantity: Order quantity
            price: Current price
            
        Returns:
            True if within risk limits
        """
        # Calculate position value
        position_value = Decimal(str(quantity)) * price
        
        # Check max position size
        if position_value > self.config.risk.max_position_size_usdt:
            logger.warning(f"Position value {position_value} exceeds max {self.config.risk.max_position_size_usdt}")
            return False
        
        # Check max positions
        open_positions = len(portfolio.futures_positions)
        if open_positions >= self.config.risk.max_positions:
            logger.warning(f"Already have {open_positions} positions (max: {self.config.risk.max_positions})")
            return False
        
        # Check if we have sufficient margin
        required_margin = position_value / Decimal(str(self.config.risk.max_leverage))
        if required_margin > portfolio.available_cash:
            logger.warning(f"Insufficient margin: need {required_margin}, have {portfolio.available_cash}")
            return False
        
        return True
    
    def _determine_order_type_and_price(
        self,
        signal: SignalGenerated,
        mapping: Dict,
        current_price: Decimal,
        order_side: str
    ) -> Tuple[str, Optional[Decimal]]:
        """
        Determine order type and price.
        
        Args:
            signal: Trading signal
            mapping: Signal mapping
            current_price: Current market price
            order_side: BUY or SELL
            
        Returns:
            Tuple of (order_type, price)
        """
        order_type = mapping.get("order_type", self.config.order.default_order_type.value)
        
        if order_type == "MARKET":
            return "MARKET", None
        
        elif order_type == "LIMIT":
            # Calculate limit price with offset
            offset_percent = self.config.order.limit_order_offset_percent / 100
            
            if order_side == "BUY":
                # Place buy limit below current price
                limit_price = current_price * (1 - offset_percent)
            else:
                # Place sell limit above current price
                limit_price = current_price * (1 + offset_percent)
            
            return "LIMIT", limit_price
        
        else:
            # Default to market
            return "MARKET", None
    
    def _calculate_risk_levels(
        self,
        entry_price: Decimal,
        position_side: str
    ) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """
        Calculate stop loss and take profit levels.
        
        Args:
            entry_price: Entry price for position
            position_side: LONG or SHORT
            
        Returns:
            Tuple of (stop_loss, take_profit)
        """
        sl_percent = self.config.order.stop_loss_percent / 100
        tp_percent = self.config.order.take_profit_percent / 100
        
        if position_side == "LONG":
            stop_loss = entry_price * (1 - sl_percent)
            take_profit = entry_price * (1 + tp_percent)
        else:  # SHORT
            stop_loss = entry_price * (1 + sl_percent)
            take_profit = entry_price * (1 - tp_percent)
        
        return stop_loss, take_profit
    
    def create_order_from_parameters(
        self,
        params: OrderParameters,
        portfolio_id: UUID
    ) -> Order:
        """
        Create Order object from parameters.
        
        Args:
            params: Order parameters
            portfolio_id: Portfolio ID
            
        Returns:
            Order object
        """
        return Order.create(
            symbol=params.symbol,
            quantity=params.quantity,
            order_type=params.order_type,
            side=params.side,
            price=float(params.price) if params.price else None,
            portfolio_id=portfolio_id,
            leverage=params.leverage,
            position_side=params.position_side,
            reduce_only=params.reduce_only
        )