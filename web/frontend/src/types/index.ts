export interface Position {
  id: string;
  symbol: string;
  side: 'LONG' | 'SHORT' | 'long' | 'short';
  quantity: number;
  entry_price: number;
  current_price: number;
  pnl: number;
  pnl_percent: number;
  unrealized_pnl?: number;
  status: string;
  created_at: string;
}

export interface Strategy {
  id: string;
  name: string;
  status: 'running' | 'paused' | 'stopped';
  total_pnl: number;
  win_rate: number;
  trades: number;
  sharpe_ratio: number;
}

export interface Trade {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL' | 'buy' | 'sell';
  quantity: number;
  price: number;
  pnl: number;
  timestamp: string;
  strategy: string;
  status: string;
}

export interface PortfolioMetrics {
  total_balance: number;
  daily_pnl: number;
  total_trades: number;
  win_rate: number;
  open_positions: number;
  total_pnl: number;
}

export interface PerformanceData {
  date: string;
  pnl: number;
  cumulative_pnl: number;
  trades: number;
  win_rate: number;
}

export interface BacktestResult {
  id: number;
  strategy: string;
  symbol: string;
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  profit_factor: number;
  created_at: string;
}

export interface RiskMetrics {
  var_95: number;
  beta: number;
  alpha: number;
  correlation: number;
  long_exposure_pct: number;
  short_exposure_pct: number;
  max_drawdown: number;
  volatility: number;
}