"""
Paper trading adapter for testing without real money.

Simulates exchange behavior for development and testing.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from datetime import datetime
import uuid
import random

from src.infrastructure.exchange.execution_adapter import (
    ExecutionAdapter, ExecutionResult, MarketData, AccountInfo,
    SymbolInfo, OrderStatus, Order, Position
)

logger = logging.getLogger(__name__)


class PaperTradingAdapter(ExecutionAdapter):
    """Paper trading implementation for testing."""
    
    def __init__(self, initial_balance: Decimal = Decimal("10000")):
        self.connected = False
        self.initial_balance = initial_balance
        
        # Simulated state
        self.balances: Dict[str, Decimal] = {
            "USDT": initial_balance,
            "BTC": Decimal("0"),
            "ETH": Decimal("0"),
            "BNB": Decimal("10")  # For commission
        }
        
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.positions: List[Position] = []
        self.trades: List[Dict[str, Any]] = []
        
        # Simulated market prices
        self.market_prices = {
            "BTCUSDT": Decimal("50000"),
            "ETHUSDT": Decimal("3000"),
            "BNBUSDT": Decimal("500")
        }
        
        # Execution settings
        self.slippage = Decimal("0.001")  # 0.1% slippage
        self.commission_rate = Decimal("0.001")  # 0.1% commission
        self.fill_probability = 0.95  # 95% fill rate
        
        # Statistics
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = Decimal("0")
    
    async def connect(self) -> bool:
        """Simulate connection."""
        await asyncio.sleep(0.1)  # Simulate network delay
        self.connected = True
        logger.info("Connected to Paper Trading adapter")
        return True
    
    async def disconnect(self) -> bool:
        """Simulate disconnection."""
        self.connected = False
        logger.info("Disconnected from Paper Trading adapter")
        return True
    
    async def is_connected(self) -> bool:
        """Check connection status."""
        return self.connected
    
    async def place_order(self, order: Order) -> ExecutionResult:
        """Simulate order placement."""
        if not self.connected:
            return self._create_failed_result("Not connected")
        
        # Simulate processing delay
        await asyncio.sleep(random.uniform(0.01, 0.1))
        
        # Check if order should fill
        if random.random() > self.fill_probability:
            return self._create_failed_result("Order rejected by exchange")
        
        # Generate order ID
        order_id = str(uuid.uuid4())
        
        # Get execution price with slippage
        base_price = order.price.value if order.price else self.market_prices.get(
            order.symbol.value, 
            Decimal("50000")
        )
        
        slippage_mult = Decimal("1")
        if order.side.value == "BUY":
            slippage_mult += self.slippage
        else:
            slippage_mult -= self.slippage
        
        execution_price = base_price * slippage_mult
        
        # Calculate commission
        commission = order.quantity.value * execution_price * self.commission_rate
        
        # Update balances
        if order.symbol.value == "BTCUSDT":
            if order.side.value == "BUY":
                cost = order.quantity.value * execution_price + commission
                if self.balances["USDT"] >= cost:
                    self.balances["USDT"] -= cost
                    self.balances["BTC"] += order.quantity.value
                else:
                    return self._create_failed_result("Insufficient balance")
            else:
                if self.balances["BTC"] >= order.quantity.value:
                    self.balances["BTC"] -= order.quantity.value
                    self.balances["USDT"] += order.quantity.value * execution_price - commission
                else:
                    return self._create_failed_result("Insufficient balance")
        
        # Record order
        self.orders[order_id] = {
            "order": order,
            "status": OrderStatus.FILLED,
            "filled_quantity": order.quantity.value,
            "execution_price": execution_price,
            "commission": commission,
            "timestamp": datetime.now()
        }
        
        # Record trade
        self.trades.append({
            "order_id": order_id,
            "symbol": order.symbol.value,
            "side": order.side.value,
            "quantity": order.quantity.value,
            "price": execution_price,
            "commission": commission,
            "timestamp": datetime.now()
        })
        
        self.total_trades += 1
        
        logger.info(
            f"Paper trade executed: {order.side.value} {order.quantity.value} "
            f"{order.symbol.value} @ {execution_price}"
        )
        
        return ExecutionResult(
            success=True,
            order_id=order_id,
            status=OrderStatus.FILLED,
            filled_quantity=order.quantity.value,
            average_price=execution_price,
            commission=commission,
            commission_asset="BNB",
            timestamp=datetime.now(),
            raw_response={"paper": True}
        )
    
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Simulate order cancellation."""
        if order_id in self.orders:
            self.orders[order_id]["status"] = OrderStatus.CANCELED
            logger.info(f"Paper order canceled: {order_id}")
            return True
        return False
    
    async def get_order_status(self, order_id: str, symbol: str) -> ExecutionResult:
        """Get simulated order status."""
        if order_id not in self.orders:
            return self._create_failed_result("Order not found")
        
        order_data = self.orders[order_id]
        
        return ExecutionResult(
            success=True,
            order_id=order_id,
            status=order_data["status"],
            filled_quantity=order_data["filled_quantity"],
            average_price=order_data["execution_price"],
            commission=order_data["commission"],
            commission_asset="BNB",
            timestamp=order_data["timestamp"],
            raw_response={"paper": True}
        )
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get simulated open orders."""
        open_orders = []
        
        for order_id, order_data in self.orders.items():
            if order_data["status"] in [OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]:
                if not symbol or order_data["order"].symbol.value == symbol:
                    open_orders.append(order_data["order"])
        
        return open_orders
    
    async def get_account_info(self) -> AccountInfo:
        """Get simulated account information."""
        # Calculate equity
        equity = self.balances["USDT"]
        equity += self.balances["BTC"] * self.market_prices.get("BTCUSDT", Decimal("50000"))
        equity += self.balances["ETH"] * self.market_prices.get("ETHUSDT", Decimal("3000"))
        equity += self.balances["BNB"] * self.market_prices.get("BNBUSDT", Decimal("500"))
        
        # Calculate PnL
        self.total_pnl = equity - self.initial_balance
        
        return AccountInfo(
            balances=self.balances.copy(),
            positions=self.positions.copy(),
            margin_level=None,
            free_margin=None,
            equity=equity,
            timestamp=datetime.now()
        )
    
    async def get_market_data(self, symbol: str) -> MarketData:
        """Get simulated market data."""
        # Simulate price movement
        base_price = self.market_prices.get(symbol, Decimal("50000"))
        
        # Add random walk
        change = Decimal(str(random.uniform(-0.001, 0.001)))
        new_price = base_price * (Decimal("1") + change)
        self.market_prices[symbol] = new_price
        
        # Simulate spread
        spread = new_price * Decimal("0.0001")  # 0.01% spread
        
        return MarketData(
            symbol=symbol,
            bid=new_price - spread,
            ask=new_price + spread,
            last=new_price,
            volume_24h=Decimal(str(random.uniform(1000, 10000))),
            timestamp=datetime.now()
        )
    
    async def get_symbol_info(self, symbol: str) -> SymbolInfo:
        """Get simulated symbol information."""
        return SymbolInfo(
            symbol=symbol,
            base_asset=symbol[:-4] if symbol.endswith("USDT") else symbol[:-3],
            quote_asset="USDT",
            status="TRADING",
            min_quantity=Decimal("0.00001"),
            max_quantity=Decimal("10000"),
            step_size=Decimal("0.00001"),
            min_notional=Decimal("10"),
            price_precision=2,
            quantity_precision=5,
            base_precision=8,
            quote_precision=8,
            filters={}
        )
    
    async def get_precision_map(self) -> Dict[str, Tuple[int, int]]:
        """Get simulated precision map."""
        return {
            "BTCUSDT": (2, 5),
            "ETHUSDT": (2, 4),
            "BNBUSDT": (2, 3)
        }
    
    def get_adapter_name(self) -> str:
        """Get adapter name."""
        return "paper"
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status."""
        win_rate = 0
        if self.total_trades > 0:
            win_rate = (self.winning_trades / self.total_trades) * 100
        
        return {
            "adapter": "paper",
            "connected": self.connected,
            "initial_balance": str(self.initial_balance),
            "current_equity": str(sum(self.balances.values())),
            "total_pnl": str(self.total_pnl),
            "total_trades": self.total_trades,
            "win_rate": f"{win_rate:.2f}%",
            "open_orders": len([o for o in self.orders.values() if o["status"] == OrderStatus.NEW]),
            "timestamp": datetime.now().isoformat()
        }
    
    def _create_failed_result(self, error_message: str) -> ExecutionResult:
        """Create failed execution result."""
        return ExecutionResult(
            success=False,
            order_id="",
            status=OrderStatus.REJECTED,
            filled_quantity=Decimal("0"),
            average_price=Decimal("0"),
            commission=Decimal("0"),
            commission_asset="",
            timestamp=datetime.now(),
            raw_response={"paper": True},
            error_message=error_message
        )
    
    def reset(self):
        """Reset paper trading state."""
        self.balances = {
            "USDT": self.initial_balance,
            "BTC": Decimal("0"),
            "ETH": Decimal("0"),
            "BNB": Decimal("10")
        }
        self.orders.clear()
        self.positions.clear()
        self.trades.clear()
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = Decimal("0")
        logger.info("Paper trading state reset")