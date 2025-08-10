// Health and monitoring types
export interface ModuleHealth {
  name: string;
  status: 'ok' | 'degraded' | 'down';
  last_success_ts: string;
  lag_seconds: number;
}

export interface HealthSummary {
  modules: ModuleHealth[];
  generated_at: string;
}

export interface RiskSummary {
  exposure_pct: number;
  daily_loss_pct: number;
  drawdown_pct: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  thresholds: {
    exposure: number;
    daily_loss: number;
    drawdown: number;
  };
}

export interface LivePosition {
  id: string;
  symbol: string;
  side: 'long' | 'short';
  quantity: number;
  entry_price: number;
  current_price: number;
  pnl: number;
  pnl_percent: number;
  timestamp: string;
}

export interface ApiActionResponse {
  ok: boolean;
  message?: string;
}