# CLI Operations Guide

## Overview

The `ops` CLI provides a safety-first interface for managing your trading bot. Every command emphasizes safe practices and requires explicit confirmations for dangerous operations.

## Installation

```bash
# Make the script executable
chmod +x ops.py

# Create alias for convenience
alias ops='python3 ops.py'

# Or install as command
pip install -e .
```

## Safety Ladder

The system enforces a progression through three trading modes:

```
1️⃣ TESTNET  → Test strategies with fake money
2️⃣ PAPER    → Validate with real data, simulated execution  
3️⃣ MAINNET  → LIVE TRADING - REAL MONEY AT RISK
```

**Always start in testnet and progress gradually!**

## Commands

### System Status

```bash
# Show system status
ops status

# Detailed status with metrics
ops status --detailed
```

Output shows:
- Current trading mode
- API server health
- Exchange connection status
- Active strategies and positions
- System resources (with --detailed)

### Log Management

```bash
# Show last 20 lines of logs
ops tail

# Show last 50 lines
ops tail -n 50

# Follow logs in real-time
ops tail -f

# Filter logs by pattern
ops tail -g ERROR
ops tail -f -g "BTCUSDT"
```

### Trading Control

#### Pause Trading
Temporarily stops opening new positions while keeping existing positions open.

```bash
ops pause
```

#### Resume Trading
Resumes trading after pause.

```bash
ops resume
```

#### Stop Trading
Stops all trading and closes all positions gracefully.

```bash
ops stop
```

#### Emergency Stop
Immediately closes all positions at market prices.

```bash
ops close-all
```

**⚠️ WARNING**: In mainnet mode, requires typing exact confirmation text.

### System Management

#### Unlock System
Clears system locks after emergency stops or errors.

```bash
ops unlock
```

Use this when:
- System is stuck after emergency stop
- Error locks prevent trading
- Need to reset after crashes

### Mode Switching

#### View Current Mode
Mode is shown in the safety ladder display on every command.

#### Switch to Testnet (Safe)
```bash
ops mode testnet
```
No confirmation required - always safe to switch to testnet.

#### Switch to Paper Trading
```bash
ops mode paper
```
Requires confirmation. Orders are simulated with real market data.

#### Switch to Mainnet (DANGEROUS)
```bash
ops mode mainnet
```

**⚠️ EXTREME CAUTION REQUIRED!**

Mainnet activation requires:
1. Confirmation of safety checklist
2. Typing exact text: "ENABLE MAINNET"
3. Understanding you're trading with REAL MONEY

### Monitoring

#### Live Dashboard
```bash
# Monitor default symbol (BTCUSDT)
ops monitor

# Monitor specific symbol
ops monitor -s ETHUSDT

# Custom update interval (seconds)
ops monitor -i 5
```

Shows real-time:
- Market prices and volume
- Open positions with PnL
- Account balance and margin

Press `Ctrl+C` to exit.

#### Health Check
```bash
ops health
```

Comprehensive diagnostic checking:
- API server
- Database connection
- Redis cache
- Exchange connection
- Strategy deployment

### Version Information
```bash
ops version
```

## Safety Features

### Confirmation Prompts

The CLI requires explicit confirmation for:
- Mode switches (paper/mainnet)
- Position closing operations
- System stops

### Mainnet Safeguards

When switching to mainnet:
1. Shows comprehensive checklist
2. Requires exact confirmation text
3. Logs activation time
4. Shows warnings on every command

### Emergency Procedures

If something goes wrong:

1. **Immediate Stop**:
   ```bash
   ops close-all
   ```

2. **Check Status**:
   ```bash
   ops status
   ops tail -n 100
   ```

3. **Unlock if Needed**:
   ```bash
   ops unlock
   ```

4. **Return to Safety**:
   ```bash
   ops mode testnet
   ```

## Configuration

Configuration stored in `config/cli_config.json`:

```json
{
  "mode": "testnet",
  "api_base_url": "http://localhost:8000",
  "ws_base_url": "ws://localhost:8000",
  "default_symbol": "BTCUSDT",
  "max_position_size": 0.1,
  "confirm_mainnet": true,
  "show_safety_ladder": true
}
```

### Environment Variables

```bash
# API endpoints
export API_BASE_URL="http://localhost:8000"
export WS_BASE_URL="ws://localhost:8000"

# Skip safety ladder (not recommended)
export SKIP_SAFETY_LADDER=false
```

## Best Practices

### Safe Progression

1. **Start in Testnet**
   - Test all strategies thoroughly
   - Verify system behavior
   - No risk involved

2. **Move to Paper**
   - Validate with real market conditions
   - Check slippage and execution
   - Monitor for at least 24 hours

3. **Carefully Enable Mainnet**
   - Start with minimal position sizes
   - Monitor continuously
   - Have emergency procedures ready

### Daily Operations

```bash
# Morning startup sequence
ops health          # Check system health
ops status -d       # Detailed status check
ops mode paper      # Start in safe mode
ops monitor         # Watch markets

# During trading
ops tail -f         # Monitor logs
ops status          # Regular health checks

# Emergency
ops close-all       # Emergency stop
ops mode testnet    # Return to safety
```

### Position Management

```bash
# Check before closing
ops status          # See open positions

# Gradual shutdown
ops pause           # Stop new positions
ops status          # Verify state
ops stop            # Close positions

# Emergency only
ops close-all       # Immediate market close
```

## Troubleshooting

### System Won't Start
```bash
ops health          # Diagnose issues
ops unlock          # Clear any locks
ops tail -n 100     # Check recent errors
```

### Can't Switch Modes
- Ensure no open positions in current mode
- Check system health first
- Verify configuration file isn't corrupted

### Connection Issues
```bash
# Test API connection
curl http://localhost:8000/health

# Check exchange connection
ops status --detailed

# Review credentials
cat config/feature_flags.json
```

### Logs Not Showing
```bash
# Check log file exists
ls -la logs/trading.log

# Check permissions
chmod 644 logs/trading.log

# Try absolute path
tail -f $(pwd)/logs/trading.log
```

## Examples

### Complete Testing Workflow

```bash
# 1. Start in testnet
ops mode testnet
ops status

# 2. Deploy and test strategy
# ... (deploy via API or UI)

# 3. Monitor performance
ops monitor -s BTCUSDT

# 4. Check logs for issues
ops tail -f -g ERROR

# 5. Move to paper when ready
ops mode paper
ops health

# 6. Run paper trading
ops monitor
# ... wait 24+ hours ...

# 7. Carefully move to mainnet
ops mode mainnet  # Requires confirmations
ops status -d
ops monitor
```

### Emergency Response

```bash
# 1. Stop everything immediately
ops close-all

# 2. Understand what happened
ops status
ops tail -n 200 -g ERROR

# 3. Reset to safe state
ops unlock
ops mode testnet

# 4. Investigate
ops health
ops tail -f
```

## Quick Reference

| Command | Description | Danger Level |
|---------|-------------|--------------|
| `ops status` | Show system status | Safe |
| `ops tail` | View logs | Safe |
| `ops health` | Run diagnostics | Safe |
| `ops monitor` | Live dashboard | Safe |
| `ops pause` | Pause new trades | Safe |
| `ops resume` | Resume trading | Safe |
| `ops unlock` | Clear locks | Safe |
| `ops mode testnet` | Switch to testnet | Safe |
| `ops mode paper` | Switch to paper | Caution |
| `ops stop` | Stop and close positions | Caution |
| `ops mode mainnet` | Enable live trading | **DANGER** |
| `ops close-all` | Emergency position close | **DANGER** |

## Support

- Documentation: https://docs.tradingbot.io
- Emergency: https://docs.tradingbot.io/emergency
- Issues: https://github.com/tradingbot/issues

**Remember: Safety First! When in doubt, use testnet.**