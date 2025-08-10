import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import Dashboard from '@/components/Dashboard';
import { api } from '@/services/api';
import { LivePosition } from '@/types/health';
import * as csvUtils from '@/lib/csv';

jest.mock('@/services/api');
jest.mock('@/lib/csv');

describe('Dashboard Positions Table', () => {
  const mockPositions: LivePosition[] = [
    {
      id: '1',
      symbol: 'BTCUSDT',
      side: 'long',
      quantity: 0.5,
      entry_price: 43000,
      current_price: 44000,
      pnl: 500,
      pnl_percent: 2.33,
      timestamp: '2024-01-15T12:00:00Z'
    },
    {
      id: '2',
      symbol: 'ETHUSDT',
      side: 'short',
      quantity: 2,
      entry_price: 2500,
      current_price: 2450,
      pnl: 100,
      pnl_percent: 2.0,
      timestamp: '2024-01-15T11:30:00Z'
    }
  ];

  beforeEach(() => {
    (api.getHealthSummary as jest.Mock).mockResolvedValue({
      modules: [],
      generated_at: '2024-01-15T12:00:00Z'
    });
    (api.getRiskSummary as jest.Mock).mockResolvedValue({
      exposure_pct: 50,
      daily_loss_pct: 2,
      drawdown_pct: 5,
      risk_level: 'MEDIUM',
      thresholds: { exposure: 80, daily_loss: 5, drawdown: 10 }
    });
    (api.getLivePositions as jest.Mock).mockResolvedValue(mockPositions);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should display positions table with correct data', async () => {
    render(
      <Dashboard 
        portfolioMetrics={{ total_balance: 10000 }}
        onRefresh={() => {}}
      />
    );

    // Wait for positions to load
    await screen.findByText('BTCUSDT');
    
    // Check position data is displayed
    expect(screen.getByText('BTCUSDT')).toBeInTheDocument();
    expect(screen.getByText('ETHUSDT')).toBeInTheDocument();
    expect(screen.getByText('0.5000')).toBeInTheDocument(); // quantity
    expect(screen.getByText('2.0000')).toBeInTheDocument(); // quantity
  });

  it('should show empty state when no positions', async () => {
    (api.getLivePositions as jest.Mock).mockResolvedValue([]);

    render(
      <Dashboard 
        portfolioMetrics={{ total_balance: 10000 }}
        onRefresh={() => {}}
      />
    );

    await screen.findByText(/no positions yet/i);
  });

  it('should call CSV export when Export button clicked', async () => {
    const mockToCSV = jest.spyOn(csvUtils, 'toCSV');
    const mockDownloadCSV = jest.spyOn(csvUtils, 'downloadCSV');

    render(
      <Dashboard 
        portfolioMetrics={{ total_balance: 10000 }}
        onRefresh={() => {}}
      />
    );

    await screen.findByText('BTCUSDT');
    
    const exportButton = screen.getByRole('button', { name: /export csv/i });
    fireEvent.click(exportButton);

    expect(mockToCSV).toHaveBeenCalledWith(
      mockPositions,
      expect.arrayContaining(['symbol', 'side', 'quantity'])
    );
    expect(mockDownloadCSV).toHaveBeenCalled();
  });

  it('should disable Export button when no positions', async () => {
    (api.getLivePositions as jest.Mock).mockResolvedValue([]);

    render(
      <Dashboard 
        portfolioMetrics={{ total_balance: 10000 }}
        onRefresh={() => {}}
      />
    );

    await screen.findByText(/no positions yet/i);
    
    const exportButton = screen.getByRole('button', { name: /export csv/i });
    expect(exportButton).toBeDisabled();
  });

  it('should format PnL with correct colors', async () => {
    const mixedPositions: LivePosition[] = [
      { ...mockPositions[0], pnl: 100, pnl_percent: 1 },
      { ...mockPositions[1], pnl: -50, pnl_percent: -2 }
    ];
    
    (api.getLivePositions as jest.Mock).mockResolvedValue(mixedPositions);

    render(
      <Dashboard 
        portfolioMetrics={{ total_balance: 10000 }}
        onRefresh={() => {}}
      />
    );

    await screen.findByText('BTCUSDT');

    // Check for positive PnL (should have green color class)
    const positivePnL = screen.getByText('$100.00');
    expect(positivePnL).toHaveClass('text-green-500');

    // Check for negative PnL (should have red color class)
    const negativePnL = screen.getByText('-$50.00');
    expect(negativePnL).toHaveClass('text-red-500');
  });

  it('should display side badges correctly', async () => {
    render(
      <Dashboard 
        portfolioMetrics={{ total_balance: 10000 }}
        onRefresh={() => {}}
      />
    );

    await screen.findByText('BTCUSDT');

    // Check for LONG and SHORT badges
    expect(screen.getByText('LONG')).toBeInTheDocument();
    expect(screen.getByText('SHORT')).toBeInTheDocument();
  });
});