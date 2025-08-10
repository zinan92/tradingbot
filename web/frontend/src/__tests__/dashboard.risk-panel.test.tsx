import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Dashboard from '@/components/Dashboard';
import { api } from '@/services/api';
import { RiskSummary } from '@/types/health';

jest.mock('@/services/api');

describe('Dashboard Risk Panel', () => {
  const mockRiskSummary: RiskSummary = {
    exposure_pct: 65,
    daily_loss_pct: 3.5,
    drawdown_pct: 8,
    risk_level: 'HIGH',
    thresholds: {
      exposure: 80,
      daily_loss: 5,
      drawdown: 10
    }
  };

  beforeEach(() => {
    (api.getHealthSummary as jest.Mock).mockResolvedValue({
      modules: [],
      generated_at: '2024-01-15T12:00:00Z'
    });
    (api.getRiskSummary as jest.Mock).mockResolvedValue(mockRiskSummary);
    (api.getLivePositions as jest.Mock).mockResolvedValue([]);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should display risk metrics correctly', async () => {
    render(
      <Dashboard 
        portfolioMetrics={{ total_balance: 10000 }}
        onRefresh={() => {}}
      />
    );

    await screen.findByText(/risk management/i);

    // Check risk values are displayed
    expect(screen.getByText('65.0%')).toBeInTheDocument(); // Exposure
    expect(screen.getByText('3.50%')).toBeInTheDocument(); // Daily loss
    expect(screen.getByText('8.00%')).toBeInTheDocument(); // Drawdown
  });

  it('should display risk level badge', async () => {
    render(
      <Dashboard 
        portfolioMetrics={{ total_balance: 10000 }}
        onRefresh={() => {}}
      />
    );

    await screen.findByText(/risk management/i);
    expect(screen.getByText('HIGH')).toBeInTheDocument();
  });

  it('should call pause API when Pause button clicked', async () => {
    (api.pauseLiveTrading as jest.Mock).mockResolvedValue({ ok: true });

    render(
      <Dashboard 
        portfolioMetrics={{ total_balance: 10000 }}
        onRefresh={() => {}}
      />
    );

    await screen.findByText(/risk management/i);
    
    const pauseButton = screen.getByRole('button', { name: /pause/i });
    fireEvent.click(pauseButton);

    await waitFor(() => {
      expect(api.pauseLiveTrading).toHaveBeenCalledTimes(1);
    });
  });

  it('should call stop API when Stop button clicked', async () => {
    (api.stopLiveTrading as jest.Mock).mockResolvedValue({ ok: true });

    render(
      <Dashboard 
        portfolioMetrics={{ total_balance: 10000 }}
        onRefresh={() => {}}
      />
    );

    await screen.findByText(/risk management/i);
    
    const stopButton = screen.getByRole('button', { name: /stop/i });
    fireEvent.click(stopButton);

    await waitFor(() => {
      expect(api.stopLiveTrading).toHaveBeenCalledTimes(1);
    });
  });

  it('should open dialog when Close All clicked', async () => {
    render(
      <Dashboard 
        portfolioMetrics={{ total_balance: 10000 }}
        onRefresh={() => {}}
      />
    );

    await screen.findByText(/risk management/i);
    
    const closeAllButton = screen.getByRole('button', { name: /close all/i });
    fireEvent.click(closeAllButton);

    // Check dialog appears
    await screen.findByText(/this will close all/i);
    expect(screen.getByText(/this action cannot be undone/i)).toBeInTheDocument();
  });

  it('should call closeAllPositions API with reason', async () => {
    (api.closeAllPositions as jest.Mock).mockResolvedValue({ ok: true });

    render(
      <Dashboard 
        portfolioMetrics={{ total_balance: 10000 }}
        onRefresh={() => {}}
      />
    );

    await screen.findByText(/risk management/i);
    
    // Open dialog
    const closeAllButton = screen.getByRole('button', { name: /close all/i });
    fireEvent.click(closeAllButton);

    // Enter reason
    const reasonInput = await screen.findByPlaceholderText(/risk limit reached/i);
    fireEvent.change(reasonInput, { target: { value: 'Risk limit exceeded' } });

    // Confirm
    const confirmButton = screen.getByRole('button', { name: /confirm close all/i });
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(api.closeAllPositions).toHaveBeenCalledWith('Risk limit exceeded');
    });
  });

  it('should disable buttons while request in flight', async () => {
    (api.pauseLiveTrading as jest.Mock).mockImplementation(
      () => new Promise(resolve => setTimeout(() => resolve({ ok: true }), 1000))
    );

    render(
      <Dashboard 
        portfolioMetrics={{ total_balance: 10000 }}
        onRefresh={() => {}}
      />
    );

    await screen.findByText(/risk management/i);
    
    const pauseButton = screen.getByRole('button', { name: /pause/i });
    const stopButton = screen.getByRole('button', { name: /stop/i });
    
    fireEvent.click(pauseButton);

    // Buttons should be disabled
    expect(pauseButton).toBeDisabled();
    expect(stopButton).toBeDisabled();
  });
});