#!/usr/bin/env python3
"""
Trading Bot Operations CLI

Safety-first command line interface for trading operations.
Always starts with safety ladder reminder and documentation links.
"""

import sys
import os
import asyncio
import click
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
import aiohttp
import websocket
import subprocess
import signal

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.infrastructure.config.feature_flags import FeatureFlagManager, Environment
from src.infrastructure.monitoring.health_monitor import HealthMonitor
from src.infrastructure.exchange.adapter_factory import get_adapter_factory

console = Console()

# API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
WS_BASE_URL = os.getenv("WS_BASE_URL", "ws://localhost:8000")

# Safety configuration
SAFETY_MODES = {
    "testnet": {
        "color": "green",
        "description": "Safe testing environment with fake money",
        "confirm_required": False,
        "warning": None
    },
    "paper": {
        "color": "yellow", 
        "description": "Paper trading with real data, no real money",
        "confirm_required": True,
        "warning": "Switching to paper trading mode. Orders will be simulated."
    },
    "mainnet": {
        "color": "red",
        "description": "LIVE TRADING with REAL MONEY",
        "confirm_required": True,
        "warning": "⚠️  WARNING: You are about to enable LIVE TRADING with REAL MONEY! ⚠️",
        "extra_confirmation": "Type 'ENABLE MAINNET' to confirm"
    }
}


def show_safety_ladder():
    """Display the safety ladder and documentation links."""
    console.print("\n" + "="*60, style="bright_blue")
    console.print("🪜 TRADING SAFETY LADDER", style="bold bright_white", justify="center")
    console.print("="*60, style="bright_blue")
    
    # Safety ladder visualization
    ladder = Table(show_header=False, box=None, padding=(0, 2))
    ladder.add_column("Level", style="bold")
    ladder.add_column("Mode")
    ladder.add_column("Description")
    
    ladder.add_row(
        "1️⃣", 
        "[green]TESTNET[/green]", 
        "Test strategies with fake money on test network"
    )
    ladder.add_row(
        "2️⃣", 
        "[yellow]PAPER[/yellow]", 
        "Validate with real data, simulated execution"
    )
    ladder.add_row(
        "3️⃣", 
        "[red]MAINNET[/red]", 
        "[bold red]LIVE TRADING - REAL MONEY AT RISK[/bold red]"
    )
    
    console.print(ladder)
    
    # Documentation links
    console.print("\n📚 Documentation:", style="bold cyan")
    console.print("  • Getting Started: https://docs.tradingbot.io/quickstart", style="dim")
    console.print("  • Safety Guide: https://docs.tradingbot.io/safety", style="dim")
    console.print("  • API Reference: https://docs.tradingbot.io/api", style="dim")
    console.print("  • Emergency Procedures: https://docs.tradingbot.io/emergency", style="dim")
    
    # Current mode
    current_mode = get_current_mode()
    mode_info = SAFETY_MODES.get(current_mode, SAFETY_MODES["testnet"])
    console.print(f"\n🔒 Current Mode: [{mode_info['color']}]{current_mode.upper()}[/{mode_info['color']}]", style="bold")
    console.print("="*60 + "\n", style="bright_blue")


def get_current_mode() -> str:
    """Get the current trading mode."""
    try:
        config_file = Path("config/cli_config.json")
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
                return config.get("mode", "testnet")
    except Exception:
        pass
    return "testnet"


def save_mode(mode: str):
    """Save the current trading mode."""
    config_file = Path("config/cli_config.json")
    config_file.parent.mkdir(parents=True, exist_ok=True)
    
    config = {}
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)
    
    config["mode"] = mode
    config["updated_at"] = datetime.now().isoformat()
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)


@click.group()
@click.pass_context
def cli(ctx):
    """Trading Bot Operations CLI - Safety First!"""
    # Show safety ladder on every command
    if ctx.invoked_subcommand != 'version':
        show_safety_ladder()


@cli.command()
@click.option('--detailed', '-d', is_flag=True, help='Show detailed status')
def status(detailed):
    """Show system status and health metrics."""
    console.print("🔍 Checking system status...\n", style="cyan")
    
    async def get_status():
        status_data = {
            "mode": get_current_mode(),
            "services": {},
            "trading": {},
            "system": {}
        }
        
        # Check API health
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{API_BASE_URL}/health") as resp:
                    if resp.status == 200:
                        health_data = await resp.json()
                        status_data["services"]["api"] = "healthy"
                        status_data["system"] = health_data.get("system", {})
                    else:
                        status_data["services"]["api"] = "unhealthy"
        except Exception as e:
            status_data["services"]["api"] = f"error: {str(e)}"
        
        # Check trading status
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{API_BASE_URL}/api/trading/status") as resp:
                    if resp.status == 200:
                        trading_data = await resp.json()
                        status_data["trading"] = trading_data
        except Exception:
            status_data["trading"]["status"] = "unknown"
        
        # Check adapter status
        try:
            factory = get_adapter_factory()
            adapter = await factory.get_adapter()
            status_data["services"]["adapter"] = adapter.get_adapter_name()
            status_data["services"]["connected"] = await adapter.is_connected()
        except Exception:
            status_data["services"]["adapter"] = "unavailable"
        
        return status_data
    
    # Get status
    status_data = asyncio.run(get_status())
    
    # Display status table
    table = Table(title="System Status", show_header=True)
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="yellow")
    
    # Mode
    mode = status_data["mode"]
    mode_info = SAFETY_MODES[mode]
    table.add_row(
        "Trading Mode",
        f"[{mode_info['color']}]{mode.upper()}[/{mode_info['color']}]",
        mode_info["description"]
    )
    
    # API Status
    api_status = status_data["services"].get("api", "unknown")
    api_style = "green" if api_status == "healthy" else "red"
    table.add_row("API Server", f"[{api_style}]{api_status}[/{api_style}]", API_BASE_URL)
    
    # Adapter Status
    adapter = status_data["services"].get("adapter", "unknown")
    connected = status_data["services"].get("connected", False)
    conn_style = "green" if connected else "red"
    table.add_row(
        "Exchange Adapter",
        f"[{conn_style}]{'connected' if connected else 'disconnected'}[/{conn_style}]",
        adapter
    )
    
    # Trading Status
    trading_status = status_data["trading"].get("status", "unknown")
    active_strategies = status_data["trading"].get("active_strategies", 0)
    open_positions = status_data["trading"].get("open_positions", 0)
    
    table.add_row(
        "Trading Engine",
        trading_status,
        f"{active_strategies} strategies, {open_positions} positions"
    )
    
    console.print(table)
    
    # Detailed view
    if detailed:
        console.print("\n📊 Detailed Metrics:", style="bold cyan")
        
        # System metrics
        if "system" in status_data and status_data["system"]:
            sys_table = Table(title="System Resources", show_header=True)
            sys_table.add_column("Metric", style="cyan")
            sys_table.add_column("Value", style="yellow")
            
            for key, value in status_data["system"].items():
                sys_table.add_row(key, str(value))
            
            console.print(sys_table)
        
        # Trading metrics
        if "trading" in status_data and "metrics" in status_data["trading"]:
            trade_table = Table(title="Trading Metrics", show_header=True)
            trade_table.add_column("Metric", style="cyan")
            trade_table.add_column("Value", style="yellow")
            
            for key, value in status_data["trading"]["metrics"].items():
                trade_table.add_row(key, str(value))
            
            console.print(trade_table)


@cli.command()
@click.option('--lines', '-n', default=20, help='Number of lines to show')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
@click.option('--filter', '-g', help='Filter logs by pattern')
def tail(lines, follow, filter):
    """Tail application logs in real-time."""
    log_file = Path("logs/trading.log")
    
    if not log_file.exists():
        console.print(f"❌ Log file not found: {log_file}", style="red")
        return
    
    console.print(f"📜 Tailing {log_file}...\n", style="cyan")
    
    if follow:
        # Follow mode - use subprocess for real-time tailing
        cmd = ["tail", "-f", str(log_file)]
        if filter:
            cmd = ["tail", "-f", str(log_file), "|", "grep", filter]
            cmd = " ".join(cmd)
            subprocess.run(cmd, shell=True)
        else:
            subprocess.run(cmd)
    else:
        # Static tail
        with open(log_file, 'r') as f:
            all_lines = f.readlines()
            
            # Apply filter if provided
            if filter:
                all_lines = [l for l in all_lines if filter in l]
            
            # Get last n lines
            for line in all_lines[-lines:]:
                # Color code by log level
                if "ERROR" in line:
                    console.print(line.strip(), style="red")
                elif "WARNING" in line:
                    console.print(line.strip(), style="yellow")
                elif "INFO" in line:
                    console.print(line.strip(), style="green")
                else:
                    console.print(line.strip())


@cli.command()
def pause():
    """Pause trading (keeps positions open)."""
    if not Confirm.ask("⏸️  Pause trading? (positions remain open)", default=False):
        console.print("Cancelled", style="yellow")
        return
    
    async def pause_trading():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{API_BASE_URL}/api/trading/pause") as resp:
                    if resp.status == 200:
                        console.print("✅ Trading paused successfully", style="green")
                        console.print("ℹ️  Positions remain open. Use 'ops resume' to continue.", style="cyan")
                    else:
                        error = await resp.text()
                        console.print(f"❌ Failed to pause: {error}", style="red")
        except Exception as e:
            console.print(f"❌ Error: {e}", style="red")
    
    asyncio.run(pause_trading())


@cli.command()
def stop():
    """Stop trading (closes all positions)."""
    mode = get_current_mode()
    
    # Extra confirmation for mainnet
    if mode == "mainnet":
        console.print("⚠️  WARNING: This will CLOSE ALL POSITIONS in MAINNET!", style="bold red")
        if not Confirm.ask("Are you absolutely sure?", default=False):
            console.print("Cancelled", style="yellow")
            return
    else:
        if not Confirm.ask("🛑 Stop trading and close all positions?", default=False):
            console.print("Cancelled", style="yellow")
            return
    
    async def stop_trading():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{API_BASE_URL}/api/trading/stop") as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        console.print("✅ Trading stopped", style="green")
                        console.print(f"📊 Closed {result.get('positions_closed', 0)} positions", style="cyan")
                        console.print(f"💰 Final PnL: {result.get('total_pnl', 0)}", style="yellow")
                    else:
                        error = await resp.text()
                        console.print(f"❌ Failed to stop: {error}", style="red")
        except Exception as e:
            console.print(f"❌ Error: {e}", style="red")
    
    asyncio.run(stop_trading())


@cli.command(name="close-all")
def close_all():
    """Emergency close all positions."""
    console.print("🚨 EMERGENCY POSITION CLOSE 🚨", style="bold red on yellow")
    console.print("This will immediately close ALL open positions at market prices!", style="bold red")
    
    mode = get_current_mode()
    if mode == "mainnet":
        console.print("\n⚠️  YOU ARE IN MAINNET - THIS WILL CLOSE REAL POSITIONS! ⚠️", style="bold red")
        confirmation = Prompt.ask(
            "Type 'CLOSE ALL POSITIONS' to confirm",
            default=""
        )
        if confirmation != "CLOSE ALL POSITIONS":
            console.print("Cancelled - confirmation text did not match", style="yellow")
            return
    else:
        if not Confirm.ask("Close all positions immediately?", default=False):
            console.print("Cancelled", style="yellow")
            return
    
    async def emergency_close():
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Closing positions...", total=None)
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{API_BASE_URL}/api/live/emergency-stop") as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            progress.stop()
                            
                            console.print("\n✅ Emergency close completed", style="green")
                            
                            # Show results
                            table = Table(title="Positions Closed", show_header=True)
                            table.add_column("Symbol", style="cyan")
                            table.add_column("Side", style="yellow")
                            table.add_column("Quantity", style="white")
                            table.add_column("PnL", style="green")
                            
                            for position in result.get("closed_positions", []):
                                pnl_style = "green" if position["pnl"] >= 0 else "red"
                                table.add_row(
                                    position["symbol"],
                                    position["side"],
                                    str(position["quantity"]),
                                    f"[{pnl_style}]{position['pnl']:.2f}[/{pnl_style}]"
                                )
                            
                            console.print(table)
                            console.print(f"\n💰 Total PnL: {result.get('total_pnl', 0):.2f}", style="bold")
                        else:
                            error = await resp.text()
                            console.print(f"❌ Failed: {error}", style="red")
        except Exception as e:
            console.print(f"❌ Error: {e}", style="red")
    
    asyncio.run(emergency_close())


@cli.command()
def unlock():
    """Unlock system after emergency stop or errors."""
    console.print("🔓 Checking for system locks...\n", style="cyan")
    
    async def unlock_system():
        locks_cleared = []
        
        # Check and clear emergency stop lock
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{API_BASE_URL}/api/system/unlock") as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        locks_cleared = result.get("locks_cleared", [])
                    else:
                        console.print("❌ No locks found or unable to unlock", style="yellow")
                        return
        except Exception as e:
            console.print(f"❌ Error checking locks: {e}", style="red")
            return
        
        if locks_cleared:
            console.print("✅ Cleared the following locks:", style="green")
            for lock in locks_cleared:
                console.print(f"  • {lock}", style="cyan")
            console.print("\nℹ️  System is now unlocked and ready for trading", style="green")
        else:
            console.print("ℹ️  No locks found - system is already unlocked", style="green")
    
    asyncio.run(unlock_system())


@cli.command()
@click.argument('mode', type=click.Choice(['testnet', 'paper', 'mainnet']))
def mode(mode):
    """Switch trading mode (testnet/paper/mainnet)."""
    current = get_current_mode()
    
    if current == mode:
        console.print(f"ℹ️  Already in {mode} mode", style="yellow")
        return
    
    # Show mode transition
    console.print(f"\n🔄 Mode Change: [{SAFETY_MODES[current]['color']}]{current}[/{SAFETY_MODES[current]['color']}] → [{SAFETY_MODES[mode]['color']}]{mode}[/{SAFETY_MODES[mode]['color']}]\n", style="bold")
    
    mode_info = SAFETY_MODES[mode]
    
    # Display warning
    if mode_info.get("warning"):
        console.print(Panel(
            mode_info["warning"],
            title="⚠️  Warning",
            border_style="red" if mode == "mainnet" else "yellow"
        ))
    
    # Confirmation
    if mode_info["confirm_required"]:
        # Extra confirmation for mainnet
        if mode == "mainnet":
            console.print("\n" + "="*60, style="red")
            console.print("🚨 MAINNET ACTIVATION CHECKLIST 🚨", style="bold red", justify="center")
            console.print("="*60, style="red")
            
            checklist = [
                "✓ I have tested my strategy in testnet",
                "✓ I have validated performance in paper trading",
                "✓ I understand I will be trading with REAL MONEY",
                "✓ I have set appropriate risk limits",
                "✓ I have emergency stop procedures ready",
                "✓ I accept full responsibility for any losses"
            ]
            
            for item in checklist:
                console.print(f"  {item}", style="yellow")
            
            console.print("="*60 + "\n", style="red")
            
            # Require exact confirmation text
            confirmation = Prompt.ask(
                f"Type '{mode_info['extra_confirmation']}' to proceed",
                default=""
            )
            
            if confirmation != mode_info['extra_confirmation']:
                console.print("❌ Confirmation text did not match. Cancelled.", style="red")
                return
        else:
            if not Confirm.ask(f"Switch to {mode} mode?", default=False):
                console.print("Cancelled", style="yellow")
                return
    
    # Perform mode switch
    async def switch_mode():
        try:
            # Update feature flags
            feature_flags = FeatureFlagManager(environment=mode)
            
            # Update adapter configuration
            if mode == "testnet":
                feature_flags.set("EXECUTION_IMPL", "binance_v2")
                os.environ["USE_TESTNET"] = "true"
            elif mode == "paper":
                feature_flags.set("EXECUTION_IMPL", "paper")
                os.environ["USE_TESTNET"] = "false"
            else:  # mainnet
                feature_flags.set("EXECUTION_IMPL", "binance_v2")
                os.environ["USE_TESTNET"] = "false"
            
            feature_flags.save_config()
            
            # Save mode
            save_mode(mode)
            
            # Restart services if running
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{API_BASE_URL}/api/system/restart") as resp:
                    if resp.status == 200:
                        console.print("✅ Services restarted with new mode", style="green")
        except Exception as e:
            console.print(f"⚠️  Mode saved but services may need manual restart: {e}", style="yellow")
    
    asyncio.run(switch_mode())
    
    # Success message
    console.print(f"\n✅ Switched to [{mode_info['color']}]{mode.upper()}[/{mode_info['color']}] mode", style="bold green")
    console.print(f"📝 {mode_info['description']}", style="cyan")
    
    # Post-switch recommendations
    if mode == "mainnet":
        console.print("\n⚡ MAINNET ACTIVE - Recommended actions:", style="bold yellow")
        console.print("  1. Run 'ops status' to verify all systems", style="yellow")
        console.print("  2. Start with small position sizes", style="yellow")
        console.print("  3. Monitor closely with 'ops tail -f'", style="yellow")
        console.print("  4. Keep 'ops close-all' ready for emergencies", style="yellow")


@cli.command()
def resume():
    """Resume trading after pause."""
    if not Confirm.ask("▶️  Resume trading?", default=True):
        console.print("Cancelled", style="yellow")
        return
    
    async def resume_trading():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{API_BASE_URL}/api/trading/resume") as resp:
                    if resp.status == 200:
                        console.print("✅ Trading resumed", style="green")
                    else:
                        error = await resp.text()
                        console.print(f"❌ Failed to resume: {error}", style="red")
        except Exception as e:
            console.print(f"❌ Error: {e}", style="red")
    
    asyncio.run(resume_trading())


@cli.command()
def health():
    """Run comprehensive health check."""
    console.print("🏥 Running health diagnostics...\n", style="cyan")
    
    async def run_health_check():
        health_status = {
            "api": False,
            "database": False,
            "redis": False,
            "exchange": False,
            "strategies": False
        }
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            # Check API
            task = progress.add_task("Checking API...", total=None)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{API_BASE_URL}/health", timeout=5) as resp:
                        health_status["api"] = resp.status == 200
            except:
                pass
            progress.remove_task(task)
            
            # Check Database
            task = progress.add_task("Checking database...", total=None)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{API_BASE_URL}/api/health/database", timeout=5) as resp:
                        health_status["database"] = resp.status == 200
            except:
                pass
            progress.remove_task(task)
            
            # Check Redis
            task = progress.add_task("Checking Redis...", total=None)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{API_BASE_URL}/api/health/redis", timeout=5) as resp:
                        health_status["redis"] = resp.status == 200
            except:
                pass
            progress.remove_task(task)
            
            # Check Exchange
            task = progress.add_task("Checking exchange connection...", total=None)
            try:
                factory = get_adapter_factory()
                adapter = await factory.get_adapter()
                health_status["exchange"] = await adapter.is_connected()
            except:
                pass
            progress.remove_task(task)
            
            # Check Strategies
            task = progress.add_task("Checking strategies...", total=None)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{API_BASE_URL}/api/strategy", timeout=5) as resp:
                        if resp.status == 200:
                            strategies = await resp.json()
                            health_status["strategies"] = len(strategies) > 0
            except:
                pass
            progress.remove_task(task)
        
        # Display results
        table = Table(title="Health Check Results", show_header=True)
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Action", style="yellow")
        
        for component, healthy in health_status.items():
            status = "✅ Healthy" if healthy else "❌ Unhealthy"
            style = "green" if healthy else "red"
            
            action = ""
            if not healthy:
                if component == "api":
                    action = "Check if API server is running"
                elif component == "database":
                    action = "Check database connection"
                elif component == "redis":
                    action = "Check Redis server"
                elif component == "exchange":
                    action = "Check exchange credentials"
                elif component == "strategies":
                    action = "Deploy at least one strategy"
            
            table.add_row(
                component.capitalize(),
                f"[{style}]{status}[/{style}]",
                action
            )
        
        console.print(table)
        
        # Overall status
        all_healthy = all(health_status.values())
        if all_healthy:
            console.print("\n✅ All systems operational!", style="bold green")
        else:
            console.print("\n⚠️  Some systems need attention", style="bold yellow")
            console.print("Run 'ops tail -n 50' to check recent logs", style="cyan")
    
    asyncio.run(run_health_check())


@cli.command()
def version():
    """Show version information."""
    version_info = {
        "CLI Version": "2.0.0",
        "API Version": "2.0.0",
        "Python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "Mode": get_current_mode()
    }
    
    table = Table(title="Version Information", show_header=False)
    table.add_column("Component", style="cyan")
    table.add_column("Version", style="yellow")
    
    for component, version in version_info.items():
        table.add_row(component, str(version))
    
    console.print(table)


@cli.command()
@click.option('--symbol', '-s', default="BTCUSDT", help='Symbol to monitor')
@click.option('--interval', '-i', default=1, help='Update interval in seconds')
def monitor(symbol, interval):
    """Live monitoring dashboard."""
    console.print(f"📊 Starting live monitor for {symbol}...\n", style="cyan")
    console.print("Press Ctrl+C to exit", style="dim")
    
    async def monitor_loop():
        try:
            while True:
                # Get current data
                async with aiohttp.ClientSession() as session:
                    # Get market data
                    market_data = {}
                    try:
                        async with session.get(f"{API_BASE_URL}/api/market/{symbol}") as resp:
                            if resp.status == 200:
                                market_data = await resp.json()
                    except:
                        pass
                    
                    # Get positions
                    positions = []
                    try:
                        async with session.get(f"{API_BASE_URL}/api/positions") as resp:
                            if resp.status == 200:
                                positions = await resp.json()
                    except:
                        pass
                    
                    # Get account
                    account = {}
                    try:
                        async with session.get(f"{API_BASE_URL}/api/account") as resp:
                            if resp.status == 200:
                                account = await resp.json()
                    except:
                        pass
                
                # Clear screen
                console.clear()
                
                # Header
                console.print(f"📊 Live Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="bold cyan")
                console.print("="*60)
                
                # Market data
                if market_data:
                    market_table = Table(title=f"{symbol} Market Data", show_header=True)
                    market_table.add_column("Metric", style="cyan")
                    market_table.add_column("Value", style="yellow")
                    
                    market_table.add_row("Price", f"${market_data.get('last', 0):.2f}")
                    market_table.add_row("24h Change", f"{market_data.get('change_24h', 0):.2%}")
                    market_table.add_row("Volume", f"{market_data.get('volume', 0):.2f}")
                    market_table.add_row("Bid", f"${market_data.get('bid', 0):.2f}")
                    market_table.add_row("Ask", f"${market_data.get('ask', 0):.2f}")
                    
                    console.print(market_table)
                
                # Positions
                if positions:
                    pos_table = Table(title="Open Positions", show_header=True)
                    pos_table.add_column("Symbol", style="cyan")
                    pos_table.add_column("Side", style="yellow")
                    pos_table.add_column("Quantity", style="white")
                    pos_table.add_column("Entry", style="white")
                    pos_table.add_column("PnL", style="green")
                    
                    for pos in positions[:5]:  # Show top 5
                        pnl = pos.get('unrealized_pnl', 0)
                        pnl_style = "green" if pnl >= 0 else "red"
                        pos_table.add_row(
                            pos['symbol'],
                            pos['side'],
                            str(pos['quantity']),
                            f"${pos['entry_price']:.2f}",
                            f"[{pnl_style}]${pnl:.2f}[/{pnl_style}]"
                        )
                    
                    console.print(pos_table)
                
                # Account
                if account:
                    acc_table = Table(title="Account Summary", show_header=True)
                    acc_table.add_column("Metric", style="cyan")
                    acc_table.add_column("Value", style="yellow")
                    
                    acc_table.add_row("Balance", f"${account.get('balance', 0):.2f}")
                    acc_table.add_row("Equity", f"${account.get('equity', 0):.2f}")
                    acc_table.add_row("Margin Used", f"${account.get('margin_used', 0):.2f}")
                    acc_table.add_row("Free Margin", f"${account.get('free_margin', 0):.2f}")
                    
                    console.print(acc_table)
                
                console.print("\nPress Ctrl+C to exit", style="dim")
                
                await asyncio.sleep(interval)
                
        except KeyboardInterrupt:
            console.print("\n👋 Monitor stopped", style="yellow")
    
    try:
        asyncio.run(monitor_loop())
    except KeyboardInterrupt:
        pass


def main():
    """Main entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n👋 Goodbye!", style="yellow")
        sys.exit(0)
    except Exception as e:
        console.print(f"❌ Unexpected error: {e}", style="red")
        console.print("Please check logs with 'ops tail'", style="yellow")
        sys.exit(1)


if __name__ == "__main__":
    main()