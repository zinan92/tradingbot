import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { backtestService, BacktestConfig, BacktestJob, BacktestResult, Strategy, Symbol } from '@/services/backtest';

const BacktestTab: React.FC = () => {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [symbols, setSymbols] = useState<Symbol[]>([]);
  const [jobs, setJobs] = useState<BacktestJob[]>([]);
  const [selectedJob, setSelectedJob] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [polling, setPolling] = useState(false);
  
  // Form state
  const [config, setConfig] = useState<BacktestConfig>({
    strategy: 'SmaCross',
    symbol: 'BTCUSDT',
    start_date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    end_date: new Date().toISOString().split('T')[0],
    initial_capital: 10000,
    leverage: 1,
    commission: 0.002,
    interval: '1h',
    strategy_params: {}
  });

  const [strategyParams, setStrategyParams] = useState<Record<string, any>>({});

  // Load available strategies and symbols on mount
  useEffect(() => {
    const loadOptions = async () => {
      try {
        const [strategiesData, symbolsData] = await Promise.all([
          backtestService.getStrategies(),
          backtestService.getSymbols()
        ]);
        setStrategies(strategiesData);
        setSymbols(symbolsData);
        
        // Set default strategy params
        if (strategiesData.length > 0) {
          const defaultStrategy = strategiesData.find(s => s.name === config.strategy);
          if (defaultStrategy) {
            const defaultParams: Record<string, any> = {};
            Object.entries(defaultStrategy.parameters).forEach(([key, param]) => {
              defaultParams[key] = param.default;
            });
            setStrategyParams(defaultParams);
          }
        }
      } catch (error) {
        console.error('Failed to load options:', error);
      }
    };
    
    loadOptions();
    loadJobs();
  }, []);

  // Load jobs
  const loadJobs = async () => {
    try {
      const jobsData = await backtestService.listJobs();
      setJobs(jobsData);
    } catch (error) {
      console.error('Failed to load jobs:', error);
    }
  };

  // Poll for job updates
  useEffect(() => {
    if (polling) {
      const interval = setInterval(loadJobs, 2000);
      return () => clearInterval(interval);
    }
  }, [polling]);

  // Handle strategy change
  const handleStrategyChange = (strategyName: string) => {
    setConfig({ ...config, strategy: strategyName });
    
    const strategy = strategies.find(s => s.name === strategyName);
    if (strategy) {
      const defaultParams: Record<string, any> = {};
      Object.entries(strategy.parameters).forEach(([key, param]) => {
        defaultParams[key] = param.default;
      });
      setStrategyParams(defaultParams);
    }
  };

  // Handle parameter change
  const handleParamChange = (paramName: string, value: string) => {
    const strategy = strategies.find(s => s.name === config.strategy);
    if (strategy && strategy.parameters[paramName]) {
      const param = strategy.parameters[paramName];
      const parsedValue = param.type === 'float' ? parseFloat(value) : parseInt(value);
      setStrategyParams({ ...strategyParams, [paramName]: parsedValue });
    }
  };

  // Run backtest
  const runBacktest = async () => {
    setLoading(true);
    setPolling(true);
    
    try {
      const backtestConfig: BacktestConfig = {
        ...config,
        strategy_params: strategyParams
      };
      
      const job = await backtestService.runBacktest(backtestConfig);
      setJobs([job, ...jobs]);
      
      // Wait for completion
      const result = await backtestService.waitForCompletion(job.job_id);
      setSelectedJob(result);
      
      // Reload jobs
      await loadJobs();
    } catch (error) {
      console.error('Backtest failed:', error);
    } finally {
      setLoading(false);
      setPolling(false);
    }
  };

  // View job results
  const viewJobResults = async (jobId: string) => {
    try {
      const result = await backtestService.getJob(jobId);
      setSelectedJob(result);
    } catch (error) {
      console.error('Failed to load job results:', error);
    }
  };

  // Format functions
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

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  // Get current strategy
  const currentStrategy = strategies.find(s => s.name === config.strategy);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-1 space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Backtest Configuration</CardTitle>
            <CardDescription>Configure and run strategy backtests</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Strategy</Label>
              <Select value={config.strategy} onValueChange={handleStrategyChange}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {strategies.map((strategy) => (
                    <SelectItem key={strategy.name} value={strategy.name}>
                      {strategy.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {currentStrategy && (
                <p className="text-xs text-muted-foreground">{currentStrategy.description}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label>Symbol</Label>
              <Select 
                value={config.symbol} 
                onValueChange={(value) => setConfig({ ...config, symbol: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {symbols.map((symbol) => (
                    <SelectItem key={symbol.symbol} value={symbol.symbol}>
                      {symbol.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Start Date</Label>
                <Input 
                  type="date" 
                  value={config.start_date}
                  onChange={(e) => setConfig({ ...config, start_date: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>End Date</Label>
                <Input 
                  type="date" 
                  value={config.end_date}
                  onChange={(e) => setConfig({ ...config, end_date: e.target.value })}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Initial Capital</Label>
              <Input 
                type="number" 
                value={config.initial_capital}
                onChange={(e) => setConfig({ ...config, initial_capital: parseFloat(e.target.value) })}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Leverage</Label>
                <Input 
                  type="number" 
                  value={config.leverage}
                  step="0.5"
                  min="1"
                  max="10"
                  onChange={(e) => setConfig({ ...config, leverage: parseFloat(e.target.value) })}
                />
              </div>
              <div className="space-y-2">
                <Label>Commission</Label>
                <Input 
                  type="number" 
                  value={config.commission}
                  step="0.0001"
                  onChange={(e) => setConfig({ ...config, commission: parseFloat(e.target.value) })}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Interval</Label>
              <Select 
                value={config.interval} 
                onValueChange={(value) => setConfig({ ...config, interval: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1m">1 Minute</SelectItem>
                  <SelectItem value="5m">5 Minutes</SelectItem>
                  <SelectItem value="15m">15 Minutes</SelectItem>
                  <SelectItem value="1h">1 Hour</SelectItem>
                  <SelectItem value="4h">4 Hours</SelectItem>
                  <SelectItem value="1d">1 Day</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {currentStrategy && Object.keys(currentStrategy.parameters).length > 0 && (
              <>
                <Separator />
                <div className="space-y-4">
                  <Label>Strategy Parameters</Label>
                  {Object.entries(currentStrategy.parameters).map(([paramName, param]) => (
                    <div key={paramName} className="space-y-2">
                      <Label className="text-xs capitalize">
                        {paramName.replace(/_/g, ' ')}
                      </Label>
                      <Input 
                        type="number"
                        value={strategyParams[paramName] || param.default}
                        min={param.min}
                        max={param.max}
                        step={param.type === 'float' ? 0.1 : 1}
                        onChange={(e) => handleParamChange(paramName, e.target.value)}
                      />
                    </div>
                  ))}
                </div>
              </>
            )}

            <Button 
              className="w-full" 
              onClick={runBacktest}
              disabled={loading}
            >
              {loading ? 'Running Backtest...' : 'Run Backtest'}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent Jobs</CardTitle>
            <CardDescription>Previously run backtests</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {jobs.slice(0, 5).map((job) => (
                <div 
                  key={job.job_id}
                  className="flex items-center justify-between p-2 rounded hover:bg-muted cursor-pointer"
                  onClick={() => viewJobResults(job.job_id)}
                >
                  <div>
                    <p className="text-sm font-medium">{job.strategy}</p>
                    <p className="text-xs text-muted-foreground">{job.symbol}</p>
                  </div>
                  <Badge 
                    variant={
                      job.status === 'completed' ? 'default' : 
                      job.status === 'running' ? 'secondary' : 
                      job.status === 'failed' ? 'destructive' : 'outline'
                    }
                  >
                    {job.status}
                  </Badge>
                </div>
              ))}
              {jobs.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No backtests run yet
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="lg:col-span-2 space-y-6">
        {selectedJob && selectedJob.stats ? (
          <>
            <Card>
              <CardHeader>
                <CardTitle>Backtest Results</CardTitle>
                <CardDescription>
                  Performance metrics and statistics
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <div>
                    <Label className="text-xs text-muted-foreground">Total Return</Label>
                    <p className={`text-lg font-semibold ${
                      (selectedJob.stats['Return [%]'] || 0) >= 0 ? 'text-green-500' : 'text-red-500'
                    }`}>
                      {formatPercent(selectedJob.stats['Return [%]'] || 0)}
                    </p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Sharpe Ratio</Label>
                    <p className="text-lg font-semibold">
                      {(selectedJob.stats['Sharpe Ratio'] || 0).toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Max Drawdown</Label>
                    <p className="text-lg font-semibold text-red-500">
                      {formatPercent(selectedJob.stats['Max. Drawdown [%]'] || 0)}
                    </p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Win Rate</Label>
                    <p className="text-lg font-semibold">
                      {(selectedJob.stats['Win Rate [%]'] || 0).toFixed(1)}%
                    </p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Total Trades</Label>
                    <p className="text-lg font-semibold">
                      {selectedJob.stats['# Trades'] || 0}
                    </p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Profit Factor</Label>
                    <p className="text-lg font-semibold">
                      {(selectedJob.stats['Profit Factor'] || 0).toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Avg Trade</Label>
                    <p className={`text-lg font-semibold ${
                      (selectedJob.stats['Avg. Trade [%]'] || 0) >= 0 ? 'text-green-500' : 'text-red-500'
                    }`}>
                      {formatPercent(selectedJob.stats['Avg. Trade [%]'] || 0)}
                    </p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Best Trade</Label>
                    <p className="text-lg font-semibold text-green-500">
                      {formatPercent(selectedJob.stats['Best Trade [%]'] || 0)}
                    </p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Worst Trade</Label>
                    <p className="text-lg font-semibold text-red-500">
                      {formatPercent(selectedJob.stats['Worst Trade [%]'] || 0)}
                    </p>
                  </div>
                </div>

                <Separator className="my-4" />

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-xs text-muted-foreground">Buy & Hold Return</Label>
                    <p className="text-lg font-semibold">
                      {formatPercent(selectedJob.stats['Buy & Hold Return [%]'] || 0)}
                    </p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Calmar Ratio</Label>
                    <p className="text-lg font-semibold">
                      {(selectedJob.stats['Calmar Ratio'] || 0).toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Sortino Ratio</Label>
                    <p className="text-lg font-semibold">
                      {(selectedJob.stats['Sortino Ratio'] || 0).toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">SQN</Label>
                    <p className="text-lg font-semibold">
                      {((selectedJob.stats && selectedJob.stats['SQN']) || 0).toFixed(2)}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {selectedJob.trades && selectedJob.trades.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Trade History</CardTitle>
                  <CardDescription>
                    Individual trades from the backtest
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Entry Time</TableHead>
                        <TableHead>Exit Time</TableHead>
                        <TableHead>Entry Price</TableHead>
                        <TableHead>Exit Price</TableHead>
                        <TableHead>Size</TableHead>
                        <TableHead>P&L</TableHead>
                        <TableHead>P&L %</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {selectedJob.trades.slice(0, 10).map((trade, index) => (
                        <TableRow key={index}>
                          <TableCell className="text-xs">
                            {formatDate(trade.entry_time)}
                          </TableCell>
                          <TableCell className="text-xs">
                            {formatDate(trade.exit_time)}
                          </TableCell>
                          <TableCell>{formatCurrency(trade.entry_price)}</TableCell>
                          <TableCell>{formatCurrency(trade.exit_price)}</TableCell>
                          <TableCell>{trade.size.toFixed(4)}</TableCell>
                          <TableCell className={trade.pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                            {formatCurrency(trade.pnl)}
                          </TableCell>
                          <TableCell className={trade.pnl_pct >= 0 ? 'text-green-500' : 'text-red-500'}>
                            {formatPercent(trade.pnl_pct)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  {selectedJob.trades.length > 10 && (
                    <p className="text-sm text-muted-foreground text-center mt-4">
                      Showing first 10 of {selectedJob.trades.length} trades
                    </p>
                  )}
                </CardContent>
              </Card>
            )}
          </>
        ) : (
          <Card>
            <CardContent className="py-16">
              <p className="text-muted-foreground text-center">
                {loading ? 'Running backtest...' : 'Select a backtest configuration and click "Run Backtest" to see results'}
              </p>
              {loading && (
                <Progress value={33} className="w-1/2 mx-auto mt-4" />
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default BacktestTab;