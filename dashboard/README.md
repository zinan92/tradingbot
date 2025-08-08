# 📊 Trading Bot Dashboard

A real-time web dashboard for monitoring and controlling your trading bot, built with Streamlit.

## 🚀 Features

### 📈 Live Monitoring
- **Real-time P&L tracking** - See your profit/loss updated every 5 seconds
- **Active positions display** - Monitor all open positions with entry/current prices
- **Recent trades log** - View your last 50 trades with details
- **Performance charts** - Visualize cumulative P&L and win rate trends

### 🎯 Strategy Deployment
- **Easy strategy configuration** - Select and configure strategies through UI
- **Multiple strategy types** - Grid, Momentum, EMA Cross, Mean Reversion
- **Symbol selection** - Trade any supported cryptocurrency pair
- **Risk parameters** - Set position sizes, stop losses, and take profits
- **One-click deployment** - Deploy strategies with safety confirmations

### ⚠️ Risk Management
- **Risk level indicator** - Visual gauge showing current risk level
- **Risk metrics dashboard** - Monitor exposure, drawdown, and positions
- **Configurable risk limits** - Adjust max positions, daily loss, drawdown
- **Emergency controls** - Pause, stop, or emergency close all positions

### 📊 Performance History
- **Historical analysis** - View performance over 7, 30, 90, or 365 days
- **Detailed metrics** - Sharpe ratio, Sortino ratio, profit factor
- **Monthly heatmap** - Visualize daily P&L in calendar format
- **Export capabilities** - Download data as CSV for further analysis

## 🛠️ Installation

### Prerequisites
- Python 3.8 or higher
- PostgreSQL database (for trade data)
- Trading bot system running

### Install Dependencies
```bash
cd /Users/park/tradingbot_v2
pip install -r dashboard/requirements.txt
```

## 🏃 Running the Dashboard

### Start the Dashboard
```bash
cd /Users/park/tradingbot_v2
streamlit run dashboard/app.py
```

The dashboard will open in your browser at `http://localhost:8501`

### Alternative Launch Options
```bash
# Specify port
streamlit run dashboard/app.py --server.port 8080

# Run without opening browser
streamlit run dashboard/app.py --server.headless true

# Enable hot reload for development
streamlit run dashboard/app.py --server.runOnSave true
```

## 📋 Configuration

The dashboard reads configuration from:
- **Config file**: `config/live_trading_config.yaml`
- **Database**: PostgreSQL connection settings
- **API**: FastAPI backend (if running)

### Database Connection
The dashboard connects to your PostgreSQL database to fetch:
- Current positions
- Trade history
- Performance metrics

Make sure your database is running and accessible.

### API Connection (Optional)
If you have the FastAPI backend running:
```bash
# Start API server (in separate terminal)
cd /Users/park/tradingbot_v2
uvicorn src.adapters.api.app:app --reload
```

## 📱 Dashboard Pages

### 1. Live Monitoring
Main monitoring page showing:
- P&L summary cards
- Active positions table
- Performance charts
- Recent trades

**Auto-refresh**: Toggle to update every 5 seconds

### 2. Deploy Strategy
Configure and deploy strategies:
1. Select strategy type (Grid, Momentum, etc.)
2. Choose symbol and timeframe
3. Set strategy parameters
4. Configure risk limits
5. Deploy with confirmation

### 3. Risk Management
Monitor and control risk:
- Risk level gauge (LOW/MEDIUM/HIGH/CRITICAL)
- Risk metrics display
- Adjustable risk limits
- Emergency controls

### 4. Performance History
Analyze historical performance:
- Time period selection (7 days to 1 year)
- Cumulative P&L charts
- Win rate trends
- Risk metrics calculation
- Monthly performance heatmap

## 🎨 Customization

### Modify Appearance
Edit `dashboard/app.py` to change:
- Color schemes
- Page layout
- Sidebar content
- Custom CSS styling

### Add New Pages
1. Create new file in `dashboard/pages/`
2. Implement `render()` function
3. Add to navigation in `app.py`

### Extend Data Service
Edit `dashboard/services/data_service.py` to:
- Add new data sources
- Implement additional calculations
- Connect to external APIs

## 🔧 Troubleshooting

### Dashboard Won't Start
```bash
# Check Streamlit installation
streamlit --version

# Reinstall dependencies
pip install -r dashboard/requirements.txt --upgrade
```

### Database Connection Failed
- Check PostgreSQL is running: `pg_isready`
- Verify database credentials in config
- Ensure database exists: `psql -d tradingbot -c "\dt"`

### No Data Showing
- Verify trading bot is running
- Check database has data
- Look at browser console for errors
- Check `data_service.py` logs

### Performance Issues
- Reduce auto-refresh frequency
- Limit data query periods
- Use caching in data service
- Close unused browser tabs

## 🔐 Security Notes

⚠️ **Important Security Considerations**:
- Dashboard is for local/personal use
- Do not expose to public internet without authentication
- Keep API keys in config files, not code
- Use read-only database user if possible
- Enable HTTPS for production use

## 📝 Usage Tips

### Best Practices
1. **Start with testnet** - Always test strategies on testnet first
2. **Monitor regularly** - Check dashboard at least daily
3. **Set risk limits** - Configure conservative limits initially
4. **Use emergency stop** - Know how to stop everything quickly
5. **Export data** - Regularly export performance data for records

### Keyboard Shortcuts
- `R` - Refresh data (when not in input field)
- `Esc` - Close modals/popups
- `Tab` - Navigate between elements

### Performance Optimization
- Close other Streamlit tabs
- Use Chrome/Firefox for best performance
- Clear browser cache if sluggish
- Restart dashboard daily for stability

## 🚧 Known Limitations

- Single user interface (not multi-user)
- 5-second minimum refresh interval
- Limited to 1000 rows in tables
- Charts may lag with >10,000 data points
- Mobile view not optimized

## 🔮 Future Enhancements

Planned features:
- [ ] WebSocket real-time updates
- [ ] Mobile-responsive design
- [ ] User authentication
- [ ] Email/SMS alerts
- [ ] Advanced charting tools
- [ ] Strategy backtesting UI
- [ ] Multi-account support
- [ ] Dark/light theme toggle

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review logs in `logs/` directory
3. Verify configuration files
4. Restart all services

## 📄 License

This dashboard is part of the Trading Bot system and follows the same license.

---

**Remember**: Always start with small amounts and test thoroughly before trading with significant capital. The dashboard is a monitoring tool - always verify critical actions independently.