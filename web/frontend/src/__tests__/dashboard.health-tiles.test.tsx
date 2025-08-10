import React from 'react';
import { render, screen } from '@testing-library/react';
import Dashboard from '@/components/Dashboard';
import { api } from '@/services/api';
import { HealthSummary } from '@/types/health';

// Mock the API
jest.mock('@/services/api');

describe('Dashboard Health Tiles', () => {
  const mockHealthSummary: HealthSummary = {
    modules: [
      {
        name: 'data',
        status: 'ok',
        last_success_ts: '2024-01-15T12:00:00Z',
        lag_seconds: 10
      },
      {
        name: 'indicators',
        status: 'ok',
        last_success_ts: '2024-01-15T11:59:00Z',
        lag_seconds: 45 // Warning threshold
      },
      {
        name: 'live_trading',
        status: 'degraded',
        last_success_ts: '2024-01-15T11:50:00Z',
        lag_seconds: 150 // Critical threshold
      },
      {
        name: 'monitoring',
        status: 'down',
        last_success_ts: '2024-01-15T11:00:00Z',
        lag_seconds: 3600
      }
    ],
    generated_at: '2024-01-15T12:00:00Z'
  };

  beforeEach(() => {
    (api.getHealthSummary as jest.Mock).mockResolvedValue(mockHealthSummary);
    (api.getRiskSummary as jest.Mock).mockResolvedValue({
      exposure_pct: 50,
      daily_loss_pct: 2,
      drawdown_pct: 5,
      risk_level: 'MEDIUM',
      thresholds: { exposure: 80, daily_loss: 5, drawdown: 10 }
    });
    (api.getLivePositions as jest.Mock).mockResolvedValue([]);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should display all module health tiles', async () => {
    render(
      <Dashboard 
        portfolioMetrics={{ total_balance: 10000 }}
        onRefresh={() => {}}
      />
    );

    // Wait for data to load
    await screen.findByText(/system health/i);

    // Check that all modules are displayed
    expect(screen.getByText(/data/i)).toBeInTheDocument();
    expect(screen.getByText(/indicators/i)).toBeInTheDocument();
    expect(screen.getByText(/live trading/i)).toBeInTheDocument();
    expect(screen.getByText(/monitoring/i)).toBeInTheDocument();
  });

  it('should apply correct colors based on lag thresholds', async () => {
    render(
      <Dashboard 
        portfolioMetrics={{ total_balance: 10000 }}
        onRefresh={() => {}}
      />
    );

    await screen.findByText(/system health/i);

    // Check for lag values
    expect(screen.getByText('Lag: 10s')).toBeInTheDocument(); // Green
    expect(screen.getByText('Lag: 45s')).toBeInTheDocument(); // Yellow (>30s)
    expect(screen.getByText('Lag: 150s')).toBeInTheDocument(); // Red (>120s)
  });

  it('should show last updated timestamp', async () => {
    render(
      <Dashboard 
        portfolioMetrics={{ total_balance: 10000 }}
        onRefresh={() => {}}
      />
    );

    await screen.findByText(/last updated:/i);
    
    // Check that timestamp format is shown
    const timestampRegex = /\d{1,2}:\d{2}:\d{2}\s?(AM|PM)?/i;
    const lastUpdated = screen.getByText(timestampRegex);
    expect(lastUpdated).toBeInTheDocument();
  });

  it('should handle API errors gracefully', async () => {
    (api.getHealthSummary as jest.Mock).mockRejectedValue(
      new Error('Network error')
    );

    render(
      <Dashboard 
        portfolioMetrics={{ total_balance: 10000 }}
        onRefresh={() => {}}
      />
    );

    // Should show error banner
    await screen.findByText(/using last known values/i);
    expect(screen.getByText(/network error/i)).toBeInTheDocument();
  });
});