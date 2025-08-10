You are given a task to integrate an existing React component in the codebase

The codebase should support:
- React with TypeScript
- Tailwind CSS
- Modern build tools (Vite/Next.js)

If your project doesn't support these, provide instructions on how to set them up.

Copy-paste this component to your project:
App.tsx
```tsx
import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { TrendingUp, TrendingDown, DollarSign, Activity, BarChart3, Settings, Play, Pause, RefreshCw } from 'lucide-react';

interface Position {
  id: string;
  symbol: string;
  side: 'long' | 'short';
  quantity: number;
  entryPrice: number;
  currentPrice: number;
  pnl: number;
  pnlPercent: number;
  timestamp: string;
}

interface Strategy {
  id: string;
  name: string;
  status: 'running' | 'paused' | 'stopped';
  totalPnl: number;
  winRate: number;
  trades: number;
  sharpeRatio: number;
}

interface Trade {
  id: string;
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  price: number;
  pnl: number;
  timestamp: string;
  strategy: string;
}

const QuantTradingTracker: React.FC = () => {
  const [selectedTimeframe, setSelectedTimeframe] = useState('1D');
  const [totalBalance, setTotalBalance] = useState(125430.50);
  const [dailyPnl, setDailyPnl] = useState(2340.75);
  const [totalTrades, setTotalTrades] = useState(47);
  const [winRate, setWinRate] = useState(68.5);

  const [positions] = useState<Position[]>([
    {
      id: '1',
      symbol: 'BTCUSDT',
      side: 'long',
      quantity: 0.5,
      entryPrice: 43250.00,
      currentPrice: 43890.50,
      pnl: 320.25,
      pnlPercent: 1.48,
      timestamp: '2024-01-15 14:30:00'
    },
    {
      id: '2',
      symbol: 'ETHUSDT',
      side: 'short',
      quantity: 2.3,
      entryPrice: 2650.00,
      currentPrice: 2598.75,
      pnl: 117.88,
      pnlPercent: 1.93,
      timestamp: '2024-01-15 13:45:00'
    },
    {
      id: '3',
      symbol: 'SOLUSDT',
      side: 'long',
      quantity: 15.0,
      entryPrice: 98.50,
      currentPrice: 96.20,
      pnl: -34.50,
      pnlPercent: -2.34,
      timestamp: '2024-01-15 12:15:00'
    }
  ]);

  const [strategies] = useState<Strategy[]>([
    {
      id: '1',
      name: 'Mean Reversion BTC',
      status: 'running',
      totalPnl: 15420.30,
      winRate: 72.5,
      trades: 156,
      sharpeRatio: 2.34
    },
    {
      id: '2',
      name: 'Momentum ETH',
      status: 'running',
      totalPnl: 8930.75,
      winRate: 65.2,
      trades: 89,
      sharpeRatio: 1.87
    },
    {
      id: '3',
      name: 'Arbitrage Multi',
      status: 'paused',
      totalPnl: 3240.15,
      winRate: 85.7,
      trades: 234,
      sharpeRatio: 3.12
    }
  ]);

  const [recentTrades] = useState<Trade[]>([
    {
      id: '1',
      symbol: 'BTCUSDT',
      side: 'buy',
      quantity: 0.25,
      price: 43890.50,
      pnl: 125.30,
      timestamp: '2024-01-15 15:22:00',
      strategy: 'Mean Reversion BTC'
    },
    {
      id: '2',
      symbol: 'ETHUSDT',
      side: 'sell',
      quantity: 1.5,
      price: 2598.75,
      pnl: 89.45,
      timestamp: '2024-01-15 15:18:00',
      strategy: 'Momentum ETH'
    },
    {
      id: '3',
      symbol: 'SOLUSDT',
      side: 'buy',
      quantity: 10.0,
      price: 96.20,
      pnl: -23.80,
      timestamp: '2024-01-15 15:10:00',
      strategy: 'Mean Reversion BTC'
    }
  ]);

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

  return (
    <div className="min-h-screen bg-background p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Quant Trading Dashboard</h1>
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
          <Button variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
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
            <div className="text-2xl font-bold">{formatCurrency(totalBalance)}</div>
            <p className="text-xs text-muted-foreground">
              +2.5% from last month
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Daily P&L</CardTitle>
            {dailyPnl >= 0 ? (
              <TrendingUp className="h-4 w-4 text-green-500" />
            ) : (
              <TrendingDown className="h-4 w-4 text-red-500" />
            )}
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${dailyPnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              {formatCurrency(dailyPnl)}
            </div>
            <p className="text-xs text-muted-foreground">
              {formatPercent(dailyPnl / totalBalance * 100)} today
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Trades</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalTrades}</div>
            <p className="text-xs text-muted-foreground">
              +12 from yesterday
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Win Rate</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{winRate}%</div>
            <Progress value={winRate} className="mt-2" />
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="positions" className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="positions">Active Positions</TabsTrigger>
          <TabsTrigger value="strategies">Strategies</TabsTrigger>
          <TabsTrigger value="trades">Recent Trades</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
        </TabsList>

        <TabsContent value="positions" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Active Positions</CardTitle>
              <CardDescription>
                Current open positions across all strategies
              </CardDescription>
            </CardHeader>
            <CardContent>
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
                        <Badge variant={position.side === 'long' ? 'default' : 'secondary'}>
                          {position.side.toUpperCase()}
                        </Badge>
                      </TableCell>
                      <TableCell>{position.quantity}</TableCell>
                      <TableCell>{formatCurrency(position.entryPrice)}</TableCell>
                      <TableCell>{formatCurrency(position.currentPrice)}</TableCell>
                      <TableCell className={position.pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                        {formatCurrency(position.pnl)}
                      </TableCell>
                      <TableCell className={position.pnlPercent >= 0 ? 'text-green-500' : 'text-red-500'}>
                        {formatPercent(position.pnlPercent)}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(position.timestamp).toLocaleTimeString()}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
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
                      <p className={`text-lg font-semibold ${strategy.totalPnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                        {formatCurrency(strategy.totalPnl)}
                      </p>
                    </div>
                    <div>
                      <Label className="text-xs text-muted-foreground">Win Rate</Label>
                      <p className="text-lg font-semibold">{strategy.winRate}%</p>
                    </div>
                    <div>
                      <Label className="text-xs text-muted-foreground">Trades</Label>
                      <p className="text-lg font-semibold">{strategy.trades}</p>
                    </div>
                    <div>
                      <Label className="text-xs text-muted-foreground">Sharpe Ratio</Label>
                      <p className="text-lg font-semibold">{strategy.sharpeRatio}</p>
                    </div>
                  </div>
                  <Separator />
                  <div className="flex space-x-2">
                    <Button size="sm" variant="outline" className="flex-1">
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
                        <Badge variant={trade.side === 'buy' ? 'default' : 'destructive'}>
                          {trade.side.toUpperCase()}
                        </Badge>
                      </TableCell>
                      <TableCell>{trade.quantity}</TableCell>
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
                    <span className="text-green-500 font-semibold">+24.5%</span>
                  </div>
                  <Progress value={24.5} />
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <Label>Max Drawdown</Label>
                    <span className="text-red-500 font-semibold">-8.2%</span>
                  </div>
                  <Progress value={8.2} className="bg-red-100" />
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <Label>Volatility</Label>
                    <span className="font-semibold">12.3%</span>
                  </div>
                  <Progress value={12.3} />
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <Label>Calmar Ratio</Label>
                    <span className="font-semibold">2.99</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Risk Metrics</CardTitle>
                <CardDescription>Risk management indicators</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-xs text-muted-foreground">VaR (95%)</Label>
                    <p className="text-lg font-semibold text-red-500">-$2,340</p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Beta</Label>
                    <p className="text-lg font-semibold">0.85</p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Alpha</Label>
                    <p className="text-lg font-semibold text-green-500">+5.2%</p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Correlation</Label>
                    <p className="text-lg font-semibold">0.72</p>
                  </div>
                </div>
                <Separator />
                <div className="space-y-2">
                  <Label>Portfolio Exposure</Label>
                  <div className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span>Long Positions</span>
                      <span>65%</span>
                    </div>
                    <Progress value={65} />
                    <div className="flex justify-between text-sm">
                      <span>Short Positions</span>
                      <span>35%</span>
                    </div>
                    <Progress value={35} />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default QuantTradingTracker;

```


Additional setup:
1. Make sure you have Tailwind CSS configured in your project
2. Update your main App component or create a new component file
3. Import and use the component in your application

The component is designed to work standalone and includes all necessary styling and functionality.