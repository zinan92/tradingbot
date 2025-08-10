import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Download } from 'lucide-react';
import { api } from '@/services/api';
import { toCSV, downloadCSV } from '@/lib/csv';
import { LivePosition } from '@/types/health';

export default function LiveTradingTab() {
  const [positions, setPositions] = useState<LivePosition[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPositions = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getLivePositions();
      setPositions(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch positions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleExportCSV = () => {
    if (positions.length === 0) return;
    
    const csv = toCSV(positions, [
      'symbol', 'side', 'quantity', 'entry_price', 
      'current_price', 'pnl', 'pnl_percent', 'timestamp'
    ]);
    
    downloadCSV(`live_positions_${new Date().toISOString().split('T')[0]}.csv`, csv);
  };

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
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Live Trading Positions</CardTitle>
              <CardDescription>
                Real-time positions from live trading strategies
              </CardDescription>
            </div>
            <Button 
              variant="outline" 
              size="sm"
              onClick={handleExportCSV}
              disabled={positions.length === 0}
            >
              <Download className="h-4 w-4 mr-2" />
              Export CSV
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="text-red-500 text-sm mb-4">
              Error: {error}
            </div>
          )}
          
          {loading && positions.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              Loading positions...
            </div>
          ) : positions.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No live positions
            </div>
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

      <Card>
        <CardHeader>
          <CardTitle>Position Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">Total Positions</p>
              <p className="text-2xl font-bold">{positions.length}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Long</p>
              <p className="text-2xl font-bold">
                {positions.filter(p => p.side === 'long').length}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Short</p>
              <p className="text-2xl font-bold">
                {positions.filter(p => p.side === 'short').length}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Total P&L</p>
              <p className={`text-2xl font-bold ${
                positions.reduce((sum, p) => sum + p.pnl, 0) >= 0 
                  ? 'text-green-500' 
                  : 'text-red-500'
              }`}>
                {formatCurrency(positions.reduce((sum, p) => sum + p.pnl, 0))}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}