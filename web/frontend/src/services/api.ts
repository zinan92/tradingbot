import { 
  Position, 
  Strategy, 
  Trade, 
  PortfolioMetrics, 
  PerformanceData,
  BacktestResult,
  RiskMetrics 
} from '@/types';
import { 
  HealthSummary, 
  RiskSummary, 
  LivePosition, 
  ApiActionResponse 
} from '@/types/health';

// Use environment variable or fallback to localhost
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 
  (typeof window !== 'undefined' && window.location.hostname === 'localhost' 
    ? 'http://localhost:8000' 
    : '');

class ApiService {
  private abortControllers = new Map<string, AbortController>();
  private readonly TIMEOUT_MS = 8000; // 8 second timeout

  private async fetchJson<T>(
    url: string, 
    options: RequestInit = {},
    key?: string
  ): Promise<T> {
    // Cancel any existing request with the same key
    if (key && this.abortControllers.has(key)) {
      this.abortControllers.get(key)?.abort();
    }

    const controller = new AbortController();
    if (key) {
      this.abortControllers.set(key, controller);
    }

    // Set up timeout
    const timeoutId = setTimeout(() => controller.abort(), this.TIMEOUT_MS);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error: any) {
      clearTimeout(timeoutId);
      
      if (error.name === 'AbortError') {
        throw new Error('Request timeout');
      }
      console.error(`Error fetching ${url}:`, error);
      throw error;
    } finally {
      if (key) {
        this.abortControllers.delete(key);
      }
    }
  }

  async getPositions(): Promise<Position[]> {
    return this.fetchJson<Position[]>(`${API_BASE_URL}/positions`);
  }

  async getTrades(limit: number = 50): Promise<Trade[]> {
    return this.fetchJson<Trade[]>(`${API_BASE_URL}/trades?limit=${limit}`);
  }

  async getStrategies(): Promise<Strategy[]> {
    return this.fetchJson<Strategy[]>(`${API_BASE_URL}/strategies`);
  }

  async getPortfolioMetrics(): Promise<PortfolioMetrics> {
    return this.fetchJson<PortfolioMetrics>(`${API_BASE_URL}/portfolio`);
  }

  async getPerformanceHistory(days: number = 30): Promise<PerformanceData[]> {
    return this.fetchJson<PerformanceData[]>(`${API_BASE_URL}/performance?days=${days}`);
  }

  async getBacktestResults(limit: number = 10): Promise<BacktestResult[]> {
    return this.fetchJson<BacktestResult[]>(`${API_BASE_URL}/backtest?limit=${limit}`);
  }

  async getRiskMetrics(): Promise<RiskMetrics> {
    return this.fetchJson<RiskMetrics>(`${API_BASE_URL}/risk-metrics`);
  }

  async toggleStrategy(strategyId: string): Promise<{ message: string; status: string }> {
    const response = await fetch(`${API_BASE_URL}/strategies/${strategyId}/toggle`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
  }

  // Health monitoring endpoints
  async getHealthSummary(): Promise<HealthSummary> {
    // DDD API health summary endpoint
    return this.fetchJson<HealthSummary>(
      `${API_BASE_URL}/health/summary`,
      {},
      'health'
    );
  }

  async getRiskSummary(): Promise<RiskSummary> {
    // DDD API risk summary
    return this.fetchJson<RiskSummary>(
      `${API_BASE_URL}/api/risk/summary`,
      {},
      'risk'
    );
  }

  async getLivePositions(): Promise<LivePosition[]> {
    // DDD API live-trading positions
    return this.fetchJson<LivePosition[]>(
      `${API_BASE_URL}/api/v1/live-trading/positions`,
      {},
      'positions'
    );
  }

  async getLiveOrders(): Promise<any[]> {
    return this.fetchJson<any[]>(
      `${API_BASE_URL}/api/live/orders`,
      {},
      'orders'
    );
  }

  // Live trading control actions
  async pauseLiveTrading(): Promise<ApiActionResponse> {
    // DDD API bridge endpoint
    return this.fetchJson<ApiActionResponse>(
      `${API_BASE_URL}/api/v1/live-trading/pause`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' } }
    );
  }

  async stopLiveTrading(): Promise<ApiActionResponse> {
    // DDD API bridge endpoint
    return this.fetchJson<ApiActionResponse>(
      `${API_BASE_URL}/api/v1/live-trading/stop`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' } }
    );
  }

  async closeAllPositions(reason?: string): Promise<ApiActionResponse> {
    // DDD API bridge endpoint
    return this.fetchJson<ApiActionResponse>(
      `${API_BASE_URL}/api/v1/live-trading/close-all`,
      { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm: true, reason })
      }
    );
  }
}

export const api = new ApiService();