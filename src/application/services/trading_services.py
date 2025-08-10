"""
Trading services for position management, risk control, and margin calculations.

These services are tested by property-based tests to ensure invariants hold.
"""

from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
from threading import Lock

from src.domain.entities import Order, Position, OrderType, OrderSide, OrderStatus
from src.domain.value_objects import Symbol, Price, Quantity, Money


class RiskLevel(Enum):
    """Risk level classifications."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RiskLimits:
    """Risk limit configuration."""
    max_exposure: Decimal = Decimal("0.8")
    max_daily_loss: Decimal = Decimal("0.05")
    max_drawdown: Decimal = Decimal("0.10")
    max_position_size: Decimal = Decimal("0.25")
    max_leverage: Decimal = Decimal("100")


class PositionManager:
    """Manages trading positions."""
    
    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self._position_counter = 0
        self._lock = Lock()
    
    def open_position(self, order: Order) -> Optional[Position]:
        """Open a new position from an order."""
        with self._lock:
            self._position_counter += 1
            
            position = Position(
                id=f"pos-{self._position_counter}",
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                entry_price=order.price or Price(Decimal("50000")),  # Default for market orders
                status="OPEN",
                created_at=order.created_at
            )
            
            self.positions[position.id] = position
            return position
    
    def close_position(self, position_id: str, exit_price: Decimal) -> Optional[Decimal]:
        """Close a position and return PnL."""
        with self._lock:
            if position_id not in self.positions:
                return None
            
            position = self.positions[position_id]
            
            # Calculate PnL
            if position.side == OrderSide.BUY:
                pnl = (exit_price - position.entry_price.value) * position.quantity.value
            else:
                pnl = (position.entry_price.value - exit_price) * position.quantity.value
            
            # Remove position
            del self.positions[position_id]
            
            return pnl
    
    def get_all_positions(self) -> List[Position]:
        """Get all open positions."""
        with self._lock:
            return list(self.positions.values())
    
    def calculate_total_exposure(self, current_price: Decimal, symbol: str = None) -> Decimal:
        """Calculate total exposure for all positions or specific symbol."""
        with self._lock:
            total = Decimal("0")
            
            for position in self.positions.values():
                if symbol and position.symbol.value != symbol:
                    continue
                
                # Use current price for the symbol
                price = current_price if not symbol or position.symbol.value == symbol else position.entry_price.value
                exposure = position.quantity.value * price
                total += exposure
            
            return total
    
    def calculate_net_position(self) -> Decimal:
        """Calculate net position across all assets."""
        with self._lock:
            net = Decimal("0")
            
            for position in self.positions.values():
                if position.side == OrderSide.BUY:
                    net += position.quantity.value
                else:
                    net -= position.quantity.value
            
            return net
    
    def calculate_unrealized_pnl(self, current_prices: Dict[str, Decimal]) -> Decimal:
        """Calculate total unrealized PnL."""
        with self._lock:
            total_pnl = Decimal("0")
            
            for position in self.positions.values():
                current_price = current_prices.get(
                    position.symbol.value,
                    position.entry_price.value
                )
                
                if position.side == OrderSide.BUY:
                    pnl = (current_price - position.entry_price.value) * position.quantity.value
                else:
                    pnl = (position.entry_price.value - current_price) * position.quantity.value
                
                total_pnl += pnl
            
            return total_pnl


class RiskManager:
    """Manages trading risk and enforces limits."""
    
    def __init__(self, max_exposure: Decimal = Decimal("0.8"),
                 max_daily_loss: Decimal = Decimal("0.05"),
                 max_drawdown: Decimal = Decimal("0.10")):
        self.max_exposure = max_exposure
        self.max_daily_loss = max_daily_loss
        self.max_drawdown = max_drawdown
        self.daily_loss = Decimal("0")
        self.peak_equity = Decimal("0")
        self.current_drawdown = Decimal("0")
        self._blocked = False
    
    def should_block_order(self, order: Order, current_exposure: Decimal) -> bool:
        """Check if an order should be blocked due to risk limits."""
        if self._blocked:
            return True
        
        # Check exposure limit
        order_value = order.quantity.value * (order.price.value if order.price else Decimal("50000"))
        potential_exposure = current_exposure + order_value
        
        if potential_exposure > self.max_exposure * Decimal("100000"):  # Assuming max account size
            self._blocked = True
            return True
        
        # Check daily loss limit
        if self.daily_loss > self.max_daily_loss * Decimal("100000"):
            self._blocked = True
            return True
        
        # Check drawdown limit
        if self.current_drawdown > self.max_drawdown:
            self._blocked = True
            return True
        
        return False
    
    def update_daily_loss(self, loss: Decimal):
        """Update daily loss tracking."""
        self.daily_loss += abs(loss)
    
    def update_equity(self, equity: Decimal):
        """Update equity for drawdown tracking."""
        if equity > self.peak_equity:
            self.peak_equity = equity
            self.current_drawdown = Decimal("0")
        else:
            self.current_drawdown = (self.peak_equity - equity) / self.peak_equity
    
    def reset_daily_limits(self):
        """Reset daily limits (called at day rollover)."""
        self.daily_loss = Decimal("0")
        self._blocked = False
    
    def get_risk_level(self) -> RiskLevel:
        """Get current risk level."""
        if self._blocked or self.current_drawdown > self.max_drawdown * Decimal("0.9"):
            return RiskLevel.CRITICAL
        elif self.current_drawdown > self.max_drawdown * Decimal("0.7"):
            return RiskLevel.HIGH
        elif self.current_drawdown > self.max_drawdown * Decimal("0.5"):
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW


class MarginCalculator:
    """Calculates margin requirements."""
    
    def __init__(self, leverage: Decimal = Decimal("10")):
        self.leverage = leverage
        self.maintenance_margin_ratio = Decimal("0.05")
        self.initial_margin_ratio = Decimal("0.10")
    
    def calculate_required_margin(self, quantity: Decimal, price: Decimal, 
                                 leverage: Decimal = None) -> Decimal:
        """Calculate required margin for a position."""
        effective_leverage = leverage or self.leverage
        position_value = quantity * price
        required_margin = position_value / effective_leverage
        
        return required_margin
    
    def calculate_maintenance_margin(self, position_value: Decimal) -> Decimal:
        """Calculate maintenance margin for a position."""
        return position_value * self.maintenance_margin_ratio
    
    def calculate_margin_level(self, equity: Decimal, used_margin: Decimal) -> Decimal:
        """Calculate margin level as percentage."""
        if used_margin == Decimal("0"):
            return Decimal("999999")  # Infinite
        
        return (equity / used_margin) * Decimal("100")
    
    def is_margin_call(self, equity: Decimal, used_margin: Decimal) -> bool:
        """Check if account is in margin call."""
        margin_level = self.calculate_margin_level(equity, used_margin)
        return margin_level < Decimal("100")  # Below 100% is margin call


class MarginMonitor:
    """Monitors margin levels and triggers alerts."""
    
    def __init__(self, maintenance_margin_ratio: Decimal = Decimal("0.05"),
                 initial_margin_ratio: Decimal = Decimal("0.10")):
        self.maintenance_margin_ratio = maintenance_margin_ratio
        self.initial_margin_ratio = initial_margin_ratio
        self.margin_calls: List[Dict] = []
    
    def check_margin_requirements(self, positions: List[Position], 
                                 current_prices: Dict[str, Decimal],
                                 account_equity: Decimal) -> List[Dict]:
        """Check margin requirements for all positions."""
        alerts = []
        total_margin_required = Decimal("0")
        
        for position in positions:
            current_price = current_prices.get(
                position.symbol.value,
                position.entry_price.value
            )
            
            position_value = position.quantity.value * current_price
            maintenance_margin = position_value * self.maintenance_margin_ratio
            
            # Calculate position PnL
            if position.side == OrderSide.BUY:
                pnl = (current_price - position.entry_price.value) * position.quantity.value
            else:
                pnl = (position.entry_price.value - current_price) * position.quantity.value
            
            position_equity = position_value + pnl
            
            if position_equity < maintenance_margin:
                alerts.append({
                    'position_id': position.id,
                    'symbol': position.symbol.value,
                    'margin_level': position_equity / maintenance_margin if maintenance_margin > 0 else 0,
                    'action': 'MARGIN_CALL'
                })
            
            total_margin_required += maintenance_margin
        
        # Check overall margin
        if account_equity < total_margin_required:
            alerts.append({
                'type': 'ACCOUNT_MARGIN_CALL',
                'equity': account_equity,
                'required': total_margin_required
            })
        
        return alerts


class LiquidationEngine:
    """Handles position liquidations."""
    
    def __init__(self):
        self.liquidation_queue: List[Dict] = []
        self._lock = Lock()
    
    def queue_liquidation(self, position: Position, reason: str):
        """Queue a position for liquidation."""
        with self._lock:
            self.liquidation_queue.append({
                'position': position,
                'reason': reason,
                'queued_at': datetime.now()
            })
    
    def process_liquidations(self, position_manager: PositionManager,
                           current_prices: Dict[str, Decimal]) -> List[Dict]:
        """Process pending liquidations."""
        results = []
        
        with self._lock:
            while self.liquidation_queue:
                item = self.liquidation_queue.pop(0)
                position = item['position']
                
                current_price = current_prices.get(
                    position.symbol.value,
                    position.entry_price.value
                )
                
                pnl = position_manager.close_position(position.id, current_price)
                
                results.append({
                    'position_id': position.id,
                    'symbol': position.symbol.value,
                    'pnl': pnl,
                    'reason': item['reason']
                })
        
        return results
    
    def get_liquidation_queue(self) -> List[Dict]:
        """Get current liquidation queue."""
        with self._lock:
            return self.liquidation_queue.copy()


class OrderExecutor:
    """Executes orders with concurrency control."""
    
    def __init__(self):
        self.executed_orders: List[Dict] = []
        self._order_counter = 0
        self._lock = asyncio.Lock()
    
    async def execute_order(self, symbol: str, side: str, quantity: Decimal) -> Dict:
        """Execute an order asynchronously."""
        async with self._lock:
            self._order_counter += 1
            
            order = {
                'id': f"order-{self._order_counter}",
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'margin_used': quantity * Decimal("5000"),  # Simplified
                'executed_at': datetime.now()
            }
            
            self.executed_orders.append(order)
            
            # Simulate execution delay
            await asyncio.sleep(0.001)
            
            return order


class ConcurrencyManager:
    """Manages concurrent access to trading resources."""
    
    def __init__(self):
        self.locks: Dict[str, asyncio.Lock] = {}
    
    def acquire_lock(self, resource: str) -> asyncio.Lock:
        """Get or create a lock for a resource."""
        if resource not in self.locks:
            self.locks[resource] = asyncio.Lock()
        return self.locks[resource]


class PnLCalculator:
    """Calculates profit and loss."""
    
    def __init__(self, commission_rate: Decimal = Decimal("0.001")):
        self.commission_rate = commission_rate
    
    def calculate_realized_pnl(self, quantity: Decimal, entry_price: Decimal,
                              exit_price: Decimal) -> Decimal:
        """Calculate realized PnL including commissions."""
        gross_pnl = (exit_price - entry_price) * quantity
        
        # Commission on entry and exit
        entry_commission = quantity * entry_price * self.commission_rate
        exit_commission = quantity * exit_price * self.commission_rate
        total_commission = entry_commission + exit_commission
        
        net_pnl = gross_pnl - total_commission
        
        return net_pnl
    
    def calculate_unrealized_pnl(self, quantity: Decimal, entry_price: Decimal,
                                current_price: Decimal) -> Decimal:
        """Calculate unrealized PnL."""
        return (current_price - entry_price) * quantity