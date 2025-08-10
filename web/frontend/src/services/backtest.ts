import { API_BASE_URL } from './api';

export interface BacktestConfig {
  strategy: string;
  symbol: string;
  start_date: string;
  end_date: string;
  initial_capital?: number;
  leverage?: number;
  commission?: number;
  interval?: string;
  strategy_params?: Record<string, any>;
}

export interface BacktestJob {
  job_id: string;
  status: string;
  strategy: string;
  symbol: string;
  start_date: string;
  end_date: string;
  created_at: string;
  completed_at?: string;
  error?: string;
}

export interface BacktestResult {
  job_id: string;
  status: string;
  stats?: Record<string, any>;
  trades?: Array<{
    entry_time: string;
    exit_time: string;
    entry_price: number;
    exit_price: number;
    size: number;
    pnl: number;
    pnl_pct: number;
    duration: string;
  }>;
  equity_curve?: Array<{
    date: string;
    equity: number;
    drawdown: number;
  }>;
}

export interface Strategy {
  name: string;
  description: string;
  parameters: Record<string, {
    type: string;
    default: number;
    min?: number;
    max?: number;
  }>;
}

export interface Symbol {
  symbol: string;
  name: string;
}

export class BacktestService {
  async runBacktest(config: BacktestConfig): Promise<BacktestJob> {
    const response = await fetch(`${API_BASE_URL}/api/backtest/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to start backtest');
    }

    return response.json();
  }

  async getJob(jobId: string): Promise<BacktestResult> {
    const response = await fetch(`${API_BASE_URL}/api/backtest/job/${jobId}`);
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get job status');
    }

    return response.json();
  }

  async listJobs(status?: string): Promise<BacktestJob[]> {
    const url = status 
      ? `${API_BASE_URL}/api/backtest/jobs?status=${status}`
      : `${API_BASE_URL}/api/backtest/jobs`;
    
    const response = await fetch(url);
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to list jobs');
    }

    return response.json();
  }

  async cancelJob(jobId: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/backtest/job/${jobId}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to cancel job');
    }
  }

  async getStrategies(): Promise<Strategy[]> {
    const response = await fetch(`${API_BASE_URL}/api/backtest/strategies`);
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get strategies');
    }

    return response.json();
  }

  async getSymbols(): Promise<Symbol[]> {
    const response = await fetch(`${API_BASE_URL}/api/backtest/symbols`);
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get symbols');
    }

    return response.json();
  }

  // Helper to poll job status until completion
  async waitForCompletion(jobId: string, pollInterval = 2000): Promise<BacktestResult> {
    return new Promise((resolve, reject) => {
      const checkStatus = async () => {
        try {
          const result = await this.getJob(jobId);
          
          if (result.status === 'completed') {
            resolve(result);
          } else if (result.status === 'failed') {
            reject(new Error('Backtest failed'));
          } else {
            setTimeout(checkStatus, pollInterval);
          }
        } catch (error) {
          reject(error);
        }
      };

      checkStatus();
    });
  }
}

export const backtestService = new BacktestService();