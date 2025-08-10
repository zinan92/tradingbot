import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { TrendingUp, TrendingDown, DollarSign, Activity, BarChart3, Settings, Play, Pause, RefreshCw } from 'lucide-react';
import { api } from '@/services/api';
import { Position, Strategy, Trade, PortfolioMetrics, RiskMetrics } from '@/types';
import BacktestTab from '@/components/BacktestTab';
import Dashboard from '@/components/Dashboard';

const App: React.FC = () => {
  const [selectedTimeframe, setSelectedTimeframe] = useState('1D');
  const [portfolioMetrics, setPortfolioMetrics] = useState<PortfolioMetrics>({
    total_balance: 10000,
    daily_pnl: 0,
    total_trades: 0,
    win_rate: 0,
    open_positions: 0,
    total_pnl: 0
  });
  
  const [positions, setPositions] = useState<Position[]>([]);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [recentTrades, setRecentTrades] = useState<Trade[]>([]);
  const [riskMetrics, setRiskMetrics] = useState<RiskMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());

  // Fetch all data
  const fetchData = async () => {
    try {
      setLoading(true);
      const [portfolioData, positionsData, strategiesData, tradesData, riskData] = await Promise.all([
        api.getPortfolioMetrics(),
        api.getPositions(),
        api.getStrategies(),
        api.getTrades(20),
        api.getRiskMetrics()
      ]);
      
      setPortfolioMetrics(portfolioData);
      setPositions(positionsData);
      setStrategies(strategiesData);
      setRecentTrades(tradesData);
      setRiskMetrics(riskData);
      setLastUpdate(new Date());
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  // Initial load and auto-refresh
  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, []);

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

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'bg-green-500';
      case 'paused':
        return 'bg-yellow-500';
      case 'stopped':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return <Play className="h-3 w-3" />;
      case 'paused':
        return <Pause className="h-3 w-3" />;
      case 'stopped':
        return <RefreshCw className="h-3 w-3" />;
      default:
        return <Settings className="h-3 w-3" />;
    }
  };

  const handleStrategyToggle = async (strategyId: string) => {
    try {
      await api.toggleStrategy(strategyId);
      await fetchData(); // Refresh data after toggle
    } catch (error) {
      console.error('Error toggling strategy:', error);
    }
  };

  return (
    <div className="min-h-screen bg-background p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Trading Bot Dashboard</h1>
          <p className="text-muted-foreground">Monitor your algorithmic trading strategies</p>
        </div>
        <div className="flex items-center space-x-4">
          <Select value={selectedTimeframe} onValueChange={setSelectedTimeframe}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1H">1 Hour</SelectItem>
              <SelectItem value="4H">4 Hours</SelectItem>
              <SelectItem value="1D">1 Day</SelectItem>
              <SelectItem value="1W">1 Week</SelectItem>
              <SelectItem value="1M">1 Month</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm" onClick={fetchData}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <span className="text-xs text-muted-foreground">
            Last update: {lastUpdate.toLocaleTimeString()}
          </span>
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Balance</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatCurrency(portfolioMetrics.total_balance)}</div>
            <p className="text-xs text-muted-foreground">
              {portfolioMetrics.open_positions} open positions
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Daily P&L</CardTitle>
            {portfolioMetrics.daily_pnl >= 0 ? (
              <TrendingUp className="h-4 w-4 text-green-500" />
            ) : (
              <TrendingDown className="h-4 w-4 text-red-500" />
            )}
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${portfolioMetrics.daily_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              {formatCurrency(portfolioMetrics.daily_pnl)}
            </div>
            <p className="text-xs text-muted-foreground">
              {formatPercent(portfolioMetrics.daily_pnl / portfolioMetrics.total_balance * 100)} today
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Trades</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{portfolioMetrics.total_trades}</div>
            <p className="text-xs text-muted-foreground">
              {recentTrades.length} recent trades
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Win Rate</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{portfolioMetrics.win_rate.toFixed(1)}%</div>
            <Progress value={portfolioMetrics.win_rate} className="mt-2" />
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="dashboard" className="space-y-6">
        <TabsList className="grid w-full grid-cols-6">
          <TabsTrigger value="dashboard">Dashboard</TabsTrigger>
          <TabsTrigger value="positions">Active Positions</TabsTrigger>
          <TabsTrigger value="strategies">Strategies</TabsTrigger>
          <TabsTrigger value="trades">Recent Trades</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
          <TabsTrigger value="backtesting">Backtesting</TabsTrigger>
        </TabsList>

        <TabsContent value="dashboard" className="space-y-6">
          <Dashboard 
            portfolioMetrics={portfolioMetrics}
            onRefresh={fetchData}
            loading={loading}
          />
        </TabsContent>

        <TabsContent value="positions" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Active Positions</CardTitle>
              <CardDescription>
                Current open positions across all strategies
              </CardDescription>
            </CardHeader>
            <CardContent>
              {positions.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">No open positions</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Symbol</TableHead>
                      <TableHead>Side</TableHead>
                      <TableHead>Quantity</TableHead>
                      <TableHead>Entry Price</TableHead>
                      <TableHead>Current Price</TableHead>
                      <TableHead>P&L</TableHead>
                      <TableHead>P&L %</TableHead>
                      <TableHead>Time</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {positions.map((position) => (
                      <TableRow key={position.id}>
                        <TableCell className="font-medium">{position.symbol}</TableCell>
                        <TableCell>
                          <Badge variant={position.side.toLowerCase() === 'long' ? 'default' : 'secondary'}>
                            {position.side.toUpperCase()}
                          </Badge>
                        </TableCell>
                        <TableCell>{position.quantity.toFixed(4)}</TableCell>
                        <TableCell>{formatCurrency(position.entry_price)}</TableCell>
                        <TableCell>{formatCurrency(position.current_price || position.entry_price)}</TableCell>
                        <TableCell className={position.pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                          {formatCurrency(position.pnl || position.unrealized_pnl || 0)}
                        </TableCell>
                        <TableCell className={position.pnl_percent >= 0 ? 'text-green-500' : 'text-red-500'}>
                          {formatPercent(position.pnl_percent || 0)}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {new Date(position.created_at).toLocaleTimeString()}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="strategies" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {strategies.map((strategy) => (
              <Card key={strategy.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{strategy.name}</CardTitle>
                    <div className="flex items-center space-x-2">
                      <div className={`w-2 h-2 rounded-full ${getStatusColor(strategy.status)}`} />
                      {getStatusIcon(strategy.status)}
                    </div>
                  </div>
                  <CardDescription>
                    <Badge variant="outline" className="capitalize">
                      {strategy.status}
                    </Badge>
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label className="text-xs text-muted-foreground">Total P&L</Label>
                      <p className={`text-lg font-semibold ${strategy.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                        {formatCurrency(strategy.total_pnl)}
                      </p>
                    </div>
                    <div>
                      <Label className="text-xs text-muted-foreground">Win Rate</Label>
                      <p className="text-lg font-semibold">{strategy.win_rate.toFixed(1)}%</p>
                    </div>
                    <div>
                      <Label className="text-xs text-muted-foreground">Trades</Label>
                      <p className="text-lg font-semibold">{strategy.trades}</p>
                    </div>
                    <div>
                      <Label className="text-xs text-muted-foreground">Sharpe Ratio</Label>
                      <p className="text-lg font-semibold">{strategy.sharpe_ratio.toFixed(2)}</p>
                    </div>
                  </div>
                  <Separator />
                  <div className="flex space-x-2">
                    <Button 
                      size="sm" 
                      variant="outline" 
                      className="flex-1"
                      onClick={() => handleStrategyToggle(strategy.id)}
                    >
                      {strategy.status === 'running' ? 'Pause' : 'Start'}
                    </Button>
                    <Button size="sm" variant="outline">
                      <Settings className="h-4 w-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="trades" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Recent Trades</CardTitle>
              <CardDescription>
                Latest executed trades across all strategies
              </CardDescription>
            </CardHeader>
            <CardContent>
              {recentTrades.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">No recent trades</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Symbol</TableHead>
                      <TableHead>Side</TableHead>
                      <TableHead>Quantity</TableHead>
                      <TableHead>Price</TableHead>
                      <TableHead>P&L</TableHead>
                      <TableHead>Strategy</TableHead>
                      <TableHead>Time</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {recentTrades.map((trade) => (
                      <TableRow key={trade.id}>
                        <TableCell className="font-medium">{trade.symbol}</TableCell>
                        <TableCell>
                          <Badge variant={trade.side.toLowerCase() === 'buy' ? 'default' : 'destructive'}>
                            {trade.side.toUpperCase()}
                          </Badge>
                        </TableCell>
                        <TableCell>{trade.quantity.toFixed(4)}</TableCell>
                        <TableCell>{formatCurrency(trade.price)}</TableCell>
                        <TableCell className={trade.pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                          {formatCurrency(trade.pnl)}
                        </TableCell>
                        <TableCell className="text-muted-foreground">{trade.strategy}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {new Date(trade.timestamp).toLocaleTimeString()}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="analytics" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Performance Metrics</CardTitle>
                <CardDescription>Key performance indicators</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <Label>Total Return</Label>
                    <span className={`font-semibold ${portfolioMetrics.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      {formatPercent((portfolioMetrics.total_pnl / portfolioMetrics.total_balance) * 100)}
                    </span>
                  </div>
                  <Progress value={Math.abs((portfolioMetrics.total_pnl / portfolioMetrics.total_balance) * 100)} />
                </div>
                {riskMetrics && (
                  <>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <Label>Max Drawdown</Label>
                        <span className="text-red-500 font-semibold">
                          {formatPercent(riskMetrics.max_drawdown)}
                        </span>
                      </div>
                      <Progress value={Math.abs(riskMetrics.max_drawdown)} className="bg-red-100" />
                    </div>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <Label>Volatility</Label>
                        <span className="font-semibold">{riskMetrics.volatility.toFixed(2)}%</span>
                      </div>
                      <Progress value={riskMetrics.volatility} />
                    </div>
                  </>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Risk Metrics</CardTitle>
                <CardDescription>Risk management indicators</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {riskMetrics && (
                  <>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label className="text-xs text-muted-foreground">VaR (95%)</Label>
                        <p className="text-lg font-semibold text-red-500">
                          {formatCurrency(-Math.abs(riskMetrics.var_95))}
                        </p>
                      </div>
                      <div>
                        <Label className="text-xs text-muted-foreground">Beta</Label>
                        <p className="text-lg font-semibold">{riskMetrics.beta.toFixed(2)}</p>
                      </div>
                      <div>
                        <Label className="text-xs text-muted-foreground">Alpha</Label>
                        <p className="text-lg font-semibold text-green-500">
                          +{(riskMetrics.alpha * 100).toFixed(1)}%
                        </p>
                      </div>
                      <div>
                        <Label className="text-xs text-muted-foreground">Correlation</Label>
                        <p className="text-lg font-semibold">{riskMetrics.correlation.toFixed(2)}</p>
                      </div>
                    </div>
                    <Separator />
                    <div className="space-y-2">
                      <Label>Portfolio Exposure</Label>
                      <div className="space-y-1">
                        <div className="flex justify-between text-sm">
                          <span>Long Positions</span>
                          <span>{riskMetrics.long_exposure_pct.toFixed(1)}%</span>
                        </div>
                        <Progress value={riskMetrics.long_exposure_pct} />
                        <div className="flex justify-between text-sm">
                          <span>Short Positions</span>
                          <span>{riskMetrics.short_exposure_pct.toFixed(1)}%</span>
                        </div>
                        <Progress value={riskMetrics.short_exposure_pct} />
                      </div>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="backtesting" className="space-y-6">
          <BacktestTab />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default App;