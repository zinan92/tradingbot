# 🚀 Trading Bot Web UI

A modern, real-time web dashboard for monitoring your algorithmic trading bot.

![Dashboard Preview](dashboard-preview.png)

## ✨ Features

- **Real-time Monitoring**: Live updates of positions, P&L, and trades
- **Portfolio Overview**: Total balance, daily P&L, win rate, and trade count
- **Active Positions**: Track all open positions with entry/current prices and P&L
- **Strategy Management**: Monitor and control multiple trading strategies
- **Trade History**: View recent executed trades across all strategies
- **Risk Analytics**: Performance metrics, risk indicators, and portfolio exposure
- **Auto-refresh**: Data updates every 5 seconds automatically
- **Responsive Design**: Works on desktop and mobile devices

## 🛠️ Tech Stack

- **Frontend**: React 18 + TypeScript + Vite
- **UI Components**: Custom shadcn/ui-inspired components
- **Styling**: Tailwind CSS
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL
- **Icons**: Lucide React

## 📋 Prerequisites

- Node.js 18+ and npm
- Python 3.8+
- PostgreSQL (existing tradingbot database)
- Your trading bot backend running

## 🚀 Quick Start

### Option 1: Automatic Setup (Recommended)

```bash
cd web
./start.sh
```

This will:
1. Install all dependencies
2. Start the backend API server (port 8000)
3. Start the frontend dev server (port 5174)
4. Open your browser to http://localhost:5174

### Option 2: Manual Setup

#### Backend Setup

```bash
cd web/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start API server
python api_server.py
```

The API will be available at http://localhost:8000
API documentation at http://localhost:8000/docs

#### Frontend Setup

```bash
cd web/frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The dashboard will be available at http://localhost:5174

## 📁 Project Structure

```
web/
├── backend/
│   ├── api_server.py       # FastAPI server
│   └── requirements.txt    # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/     # React components
│   │   │   └── ui/        # Reusable UI components
│   │   ├── services/       # API integration
│   │   ├── types/          # TypeScript types
│   │   └── App.tsx         # Main application
│   ├── package.json        # Node dependencies
│   └── vite.config.ts      # Vite configuration
├── start.sh                # Startup script
└── README.md               # This file
```

## 🔧 Configuration

### Backend Configuration

Edit `backend/api_server.py` to configure:
- Database connection settings
- CORS origins
- API endpoints

### Frontend Configuration

Edit `frontend/vite.config.ts` to configure:
- Development server port
- API proxy settings

## 📊 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/positions` | GET | Get all open positions |
| `/api/trades` | GET | Get recent trades |
| `/api/strategies` | GET | Get strategy status |
| `/api/portfolio` | GET | Get portfolio metrics |
| `/api/performance` | GET | Get performance history |
| `/api/backtest` | GET | Get backtest results |
| `/api/risk-metrics` | GET | Get risk metrics |
| `/api/strategies/{id}/toggle` | POST | Toggle strategy on/off |

## 🎨 Customization

### Adding New Metrics

1. Add endpoint in `backend/api_server.py`
2. Add type definition in `frontend/src/types/index.ts`
3. Add API call in `frontend/src/services/api.ts`
4. Display in `frontend/src/App.tsx`

### Changing Refresh Rate

Edit `frontend/src/App.tsx`:
```typescript
const interval = setInterval(fetchData, 5000); // Change 5000 to desired milliseconds
```

### Styling

- Colors: Edit `frontend/src/index.css`
- Layout: Modify components in `frontend/src/App.tsx`
- Components: Edit files in `frontend/src/components/ui/`

## 🐛 Troubleshooting

### Backend Issues

**Database connection error:**
- Check PostgreSQL is running
- Verify database name is `tradingbot`
- Check `.env` file for credentials

**Port 8000 already in use:**
```bash
lsof -i:8000  # Find process
kill -9 <PID>  # Kill process
```

### Frontend Issues

**Dependencies not installing:**
```bash
rm -rf node_modules package-lock.json
npm install
```

**Port 5174 already in use:**
```bash
lsof -i:5174  # Find process
kill -9 <PID>  # Kill process
```

### No Data Showing

1. Check backend is running: http://localhost:8000/health
2. Check browser console for errors
3. Verify database has data:
```sql
psql -d tradingbot -c "SELECT * FROM positions LIMIT 5;"
```

## 🚦 Development

### Running in Production

```bash
# Build frontend
cd frontend
npm run build

# Serve with a production server
npm install -g serve
serve -s dist -p 3000
```

### Adding Mock Data

For testing without real trading data, the backend returns mock data when database queries fail.

### Database Schema

The dashboard expects these tables:
- `positions` - Open trading positions
- `orders` - Trade history
- `performance_history` - Daily performance metrics
- `backtest_results` - Backtest data (optional)

## 📝 Notes

- The dashboard is read-only by default (no trading actions)
- Data refreshes every 5 seconds automatically
- All times are displayed in local timezone
- P&L calculations assume USDT as base currency

## 🤝 Contributing

Feel free to customize and extend this dashboard for your needs!

## 📄 License

MIT

---

**Built with ❤️ for algorithmic traders**