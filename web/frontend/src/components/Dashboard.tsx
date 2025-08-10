import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Progress } from '@/components/ui/progress';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { 
  Dialog, 
  DialogContent, 
  DialogDescription, 
  DialogFooter, 
  DialogHeader, 
  DialogTitle 
} from '@/components/ui/dialog';
import { 
  TrendingUp, 
  TrendingDown, 
  DollarSign, 
  Activity, 
  AlertTriangle,
  Download,
  Pause,
  Square,
  XCircle,
  RefreshCw
} from 'lucide-react';
import { api } from '@/services/api';
import { toCSV, downloadCSV } from '@/lib/csv';
import { 
  HealthSummary, 
  ModuleHealth, 
  RiskSummary, 
  LivePosition 
} from '@/types/health';

// Thresholds for module health coloring
const HEALTH_THRESHOLDS = {
  LAG_WARNING: 30,  // seconds - yellow
  LAG_CRITICAL: 120 // seconds - red
} as const;

interface DashboardProps {
  portfolioMetrics: any;
  onRefresh: () => void;
  loading?: boolean;
}

export default function Dashboard({ portfolioMetrics, onRefresh, loading = false }: DashboardProps) {
  const [healthSummary, setHealthSummary] = useState<HealthSummary | null>(null);
  const [riskSummary, setRiskSummary] = useState<RiskSummary | null>(null);
  const [livePositions, setLivePositions] = useState<LivePosition[]>([]);
  const [lastHealthError, setLastHealthError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showCloseDialog, setShowCloseDialog] = useState(false);
  const [closeReason, setCloseReason] = useState('');
  const [toastMessage, setToastMessage] = useState<{ type: 'success' | 'error', message: string } | null>(null);

  // Polling for health data
  const fetchHealthData = useCallback(async () => {
    try {
      const [health, risk, positions] = await Promise.all([
        api.getHealthSummary(),
        api.getRiskSummary(),
        api.getLivePositions()
      ]);
      
      setHealthSummary(health);
      setRiskSummary(risk);
      setLivePositions(positions);
      setLastUpdate(new Date());
      setLastHealthError(null);
    } catch (error: any) {
      console.error('Error fetching health data:', error);
      setLastHealthError(error.message || 'Failed to fetch health data');
      // Keep previous data on error
    }
  }, []);

  // Set up polling
  useEffect(() => {
    fetchHealthData();
    const interval = setInterval(fetchHealthData, 10000); // Poll every 10 seconds
    return () => clearInterval(interval);
  }, [fetchHealthData]);

  // Get module health color
  const getModuleHealthColor = (module: ModuleHealth): string => {
    if (module.status === 'down') return 'bg-red-500';
    if (module.status === 'degraded') return 'bg-yellow-500';
    if (module.lag_seconds > HEALTH_THRESHOLDS.LAG_CRITICAL) return 'bg-red-500';
    if (module.lag_seconds > HEALTH_THRESHOLDS.LAG_WARNING) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  // Get risk level badge variant
  const getRiskLevelVariant = (level: string): "default" | "secondary" | "destructive" | "outline" => {
    switch (level) {
      case 'LOW': return 'default';
      case 'MEDIUM': return 'secondary';
      case 'HIGH': return 'destructive';
      case 'CRITICAL': return 'destructive';
      default: return 'outline';
    }
  };

  // Handle CSV export
  const handleExportCSV = () => {
    if (livePositions.length === 0) {
      setToastMessage({ type: 'error', message: 'No positions to export' });
      return;
    }

    const csv = toCSV(livePositions, [
      'symbol',
      'side',
      'quantity',
      'entry_price',
      'current_price',
      'pnl',
      'pnl_percent',
      'timestamp'
    ]);
    
    const filename = `positions_${new Date().toISOString().split('T')[0]}.csv`;
    downloadCSV(filename, csv);
    setToastMessage({ type: 'success', message: `Exported ${livePositions.length} positions` });
  };

  // Handle live trading actions
  const handlePause = async () => {
    setActionLoading('pause');
    try {
      const response = await api.pauseLiveTrading();
      setToastMessage({ 
        type: 'success', 
        message: response.message || 'Live trading paused' 
      });
      onRefresh();
    } catch (error: any) {
      setToastMessage({ 
        type: 'error', 
        message: error.message || 'Failed to pause trading' 
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleStop = async () => {
    setActionLoading('stop');
    try {
      const response = await api.stopLiveTrading();
      setToastMessage({ 
        type: 'success', 
        message: response.message || 'Live trading stopped' 
      });
      onRefresh();
    } catch (error: any) {
      setToastMessage({ 
        type: 'error', 
        message: error.message || 'Failed to stop trading' 
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleCloseAll = async () => {
    setActionLoading('close');
    try {
      const response = await api.closeAllPositions(closeReason);
      setToastMessage({ 
        type: 'success', 
        message: response.message || 'All positions closed' 
      });
      setShowCloseDialog(false);
      setCloseReason('');
      onRefresh();
      fetchHealthData();
    } catch (error: any) {
      setToastMessage({ 
        type: 'error', 
        message: error.message || 'Failed to close positions' 
      });
    } finally {
      setActionLoading(null);
    }
  };

  // Clear toast after 3 seconds
  useEffect(() => {
    if (toastMessage) {
      const timer = setTimeout(() => setToastMessage(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toastMessage]);

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2
    }).format(value);
  };

  const formatPercent = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  return (
    <div className="space-y-6">
      {/* Error Banner */}
      {lastHealthError && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-center">
            <AlertTriangle className="h-5 w-5 text-yellow-600 mr-2" />
            <span className="text-sm text-yellow-800">
              Using last known values - {lastHealthError}
            </span>
          </div>
        </div>
      )}

      {/* Module Health Status */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">System Health</h3>
          <span className="text-xs text-muted-foreground">
            Last updated: {lastUpdate.toLocaleTimeString()}
          </span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          {healthSummary?.modules.map((module) => (
            <Card key={module.name} className="relative">
              <div className={`absolute top-2 right-2 w-2 h-2 rounded-full ${getModuleHealthColor(module)}`} />
              <CardHeader className="pb-2">
                <CardTitle className="text-xs font-medium capitalize">
                  {module.name.replace('_', ' ')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  Lag: {module.lag_seconds}s
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Risk Panel */}
      {riskSummary && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Risk Management</CardTitle>
              <Badge variant={getRiskLevelVariant(riskSummary.risk_level)}>
                {riskSummary.risk_level}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <Label>Exposure</Label>
                  <span className={riskSummary.exposure_pct > riskSummary.thresholds.exposure ? 'text-red-500' : ''}>
                    {riskSummary.exposure_pct.toFixed(1)}%
                  </span>
                </div>
                <Progress 
                  value={riskSummary.exposure_pct} 
                  className={riskSummary.exposure_pct > riskSummary.thresholds.exposure ? 'bg-red-100' : ''}
                />
              </div>
              
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <Label>Daily Loss</Label>
                  <span className={riskSummary.daily_loss_pct > riskSummary.thresholds.daily_loss ? 'text-red-500' : ''}>
                    {riskSummary.daily_loss_pct.toFixed(2)}%
                  </span>
                </div>
                <Progress 
                  value={Math.abs(riskSummary.daily_loss_pct)} 
                  className="bg-red-100"
                />
              </div>
              
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <Label>Drawdown</Label>
                  <span className={riskSummary.drawdown_pct > riskSummary.thresholds.drawdown ? 'text-red-500' : ''}>
                    {riskSummary.drawdown_pct.toFixed(2)}%
                  </span>
                </div>
                <Progress 
                  value={Math.abs(riskSummary.drawdown_pct)} 
                  className="bg-red-100"
                />
              </div>
            </div>
            
            <div className="flex gap-2 pt-2">
              <Button 
                variant="outline" 
                size="sm"
                onClick={handlePause}
                disabled={actionLoading !== null}
              >
                <Pause className="h-4 w-4 mr-2" />
                Pause
              </Button>
              <Button 
                variant="outline" 
                size="sm"
                onClick={handleStop}
                disabled={actionLoading !== null}
              >
                <Square className="h-4 w-4 mr-2" />
                Stop
              </Button>
              <Button 
                variant="destructive" 
                size="sm"
                onClick={() => setShowCloseDialog(true)}
                disabled={actionLoading !== null}
              >
                <XCircle className="h-4 w-4 mr-2" />
                Close All
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Live Positions Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Live Positions</CardTitle>
              <CardDescription>Real-time positions from live trading</CardDescription>
            </div>
            <Button 
              variant="outline" 
              size="sm"
              onClick={handleExportCSV}
              disabled={livePositions.length === 0}
            >
              <Download className="h-4 w-4 mr-2" />
              Export CSV
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {livePositions.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No positions yet
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Symbol</TableHead>
                  <TableHead>Side</TableHead>
                  <TableHead>Quantity</TableHead>
                  <TableHead>Entry</TableHead>
                  <TableHead>Current</TableHead>
                  <TableHead>P&L</TableHead>
                  <TableHead>P&L %</TableHead>
                  <TableHead>Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {livePositions.map((position) => (
                  <TableRow key={position.id}>
                    <TableCell className="font-medium">{position.symbol}</TableCell>
                    <TableCell>
                      <Badge variant={position.side === 'long' ? 'default' : 'secondary'}>
                        {position.side.toUpperCase()}
                      </Badge>
                    </TableCell>
                    <TableCell>{position.quantity.toFixed(4)}</TableCell>
                    <TableCell>{formatCurrency(position.entry_price)}</TableCell>
                    <TableCell>{formatCurrency(position.current_price)}</TableCell>
                    <TableCell className={position.pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                      {formatCurrency(position.pnl)}
                    </TableCell>
                    <TableCell className={position.pnl_percent >= 0 ? 'text-green-500' : 'text-red-500'}>
                      {formatPercent(position.pnl_percent)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(position.timestamp).toLocaleTimeString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Close All Dialog */}
      <Dialog open={showCloseDialog} onOpenChange={setShowCloseDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Close All Positions</DialogTitle>
            <DialogDescription>
              This will close all {livePositions.length} open positions immediately. 
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="reason">Reason (optional)</Label>
              <Input
                id="reason"
                value={closeReason}
                onChange={(e) => setCloseReason(e.target.value)}
                placeholder="e.g., Risk limit reached, Market conditions"
              />
            </div>
          </div>
          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={() => setShowCloseDialog(false)}
              disabled={actionLoading === 'close'}
            >
              Cancel
            </Button>
            <Button 
              variant="destructive" 
              onClick={handleCloseAll}
              disabled={actionLoading === 'close'}
            >
              {actionLoading === 'close' ? 'Closing...' : 'Confirm Close All'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Toast Notification */}
      {toastMessage && (
        <div 
          className={`fixed bottom-4 right-4 p-4 rounded-lg shadow-lg z-50 ${
            toastMessage.type === 'success' ? 'bg-green-500' : 'bg-red-500'
          } text-white`}
        >
          {toastMessage.message}
        </div>
      )}
    </div>
  );
}