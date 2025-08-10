"""
Backtest Artifact Writer

Utility for writing standardized backtest output files.
"""
import json
import csv
import math
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from io import StringIO


class BacktestArtifactWriter:
    """Writes backtest results to standardized artifact files"""
    
    def __init__(self, output_dir: str = "artifacts"):
        """
        Initialize artifact writer
        
        Args:
            output_dir: Directory to write artifacts to
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def write_all_artifacts(
        self,
        metrics: Dict[str, float],
        equity_curve: List[Dict[str, Any]],
        trades: List[Dict[str, Any]],
        strategy_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Path]:
        """
        Write all standardized artifacts
        
        Args:
            metrics: Performance metrics dictionary
            equity_curve: List of equity points
            trades: List of trade records
            strategy_name: Name of the strategy
            metadata: Optional metadata for the report
            
        Returns:
            Dictionary mapping artifact names to file paths
        """
        artifacts = {}
        
        # Ensure all metrics are finite
        metrics = self._sanitize_metrics(metrics)
        
        # Write metrics.json
        artifacts['metrics'] = self.write_metrics(metrics)
        
        # Write equity.csv
        artifacts['equity'] = self.write_equity_curve(equity_curve)
        
        # Write trades.csv
        artifacts['trades'] = self.write_trades(trades)
        
        # Write report.html
        artifacts['report'] = self.write_html_report(
            metrics, equity_curve, trades, strategy_name, metadata
        )
        
        return artifacts
    
    def write_metrics(self, metrics: Dict[str, float]) -> Path:
        """
        Write metrics to JSON file
        
        Required metrics:
        - sharpe: Sharpe ratio
        - profit_factor: Profit factor
        - win_rate: Win rate percentage
        - max_dd: Maximum drawdown percentage
        - returns: Total returns percentage
        """
        output_path = self.output_dir / "metrics.json"
        
        # Ensure required metrics exist with defaults
        required_metrics = {
            'sharpe': metrics.get('sharpe', 0.0),
            'profit_factor': metrics.get('profit_factor', 0.0),
            'win_rate': metrics.get('win_rate', 0.0),
            'max_dd': metrics.get('max_dd', 0.0),
            'returns': metrics.get('returns', 0.0)
        }
        
        # Add any additional metrics
        for key, value in metrics.items():
            if key not in required_metrics:
                required_metrics[key] = value
        
        # Sanitize values
        sanitized = self._sanitize_metrics(required_metrics)
        
        with open(output_path, 'w') as f:
            json.dump(sanitized, f, indent=2)
        
        return output_path
    
    def write_equity_curve(self, equity_curve: List[Dict[str, Any]]) -> Path:
        """
        Write equity curve to CSV file
        
        Expected columns:
        - timestamp: Date/time
        - equity: Portfolio value
        - drawdown: Current drawdown percentage
        - returns: Cumulative returns percentage
        """
        output_path = self.output_dir / "equity.csv"
        
        if not equity_curve:
            # Write empty file with headers
            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'equity', 'drawdown', 'returns'])
            return output_path
        
        # Ensure all required columns exist
        headers = ['timestamp', 'equity', 'drawdown', 'returns']
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            
            for point in equity_curve:
                row = {
                    'timestamp': point.get('timestamp', ''),
                    'equity': self._sanitize_float(point.get('equity', 0.0)),
                    'drawdown': self._sanitize_float(point.get('drawdown', 0.0)),
                    'returns': self._sanitize_float(point.get('returns', 0.0))
                }
                writer.writerow(row)
        
        return output_path
    
    def write_trades(self, trades: List[Dict[str, Any]]) -> Path:
        """
        Write trades to CSV file
        
        Expected columns:
        - entry_time: Entry timestamp
        - exit_time: Exit timestamp
        - symbol: Trading symbol
        - side: Trade side (long/short)
        - entry_price: Entry price
        - exit_price: Exit price
        - quantity: Trade quantity
        - pnl: Profit/loss
        - pnl_percent: Profit/loss percentage
        - commission: Commission paid
        """
        output_path = self.output_dir / "trades.csv"
        
        if not trades:
            # Write empty file with headers
            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'entry_time', 'exit_time', 'symbol', 'side',
                    'entry_price', 'exit_price', 'quantity',
                    'pnl', 'pnl_percent', 'commission'
                ])
            return output_path
        
        headers = [
            'entry_time', 'exit_time', 'symbol', 'side',
            'entry_price', 'exit_price', 'quantity',
            'pnl', 'pnl_percent', 'commission'
        ]
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            
            for trade in trades:
                row = {
                    'entry_time': trade.get('entry_time', ''),
                    'exit_time': trade.get('exit_time', ''),
                    'symbol': trade.get('symbol', ''),
                    'side': trade.get('side', ''),
                    'entry_price': self._sanitize_float(trade.get('entry_price', 0.0)),
                    'exit_price': self._sanitize_float(trade.get('exit_price', 0.0)),
                    'quantity': self._sanitize_float(trade.get('quantity', 0.0)),
                    'pnl': self._sanitize_float(trade.get('pnl', 0.0)),
                    'pnl_percent': self._sanitize_float(trade.get('pnl_percent', 0.0)),
                    'commission': self._sanitize_float(trade.get('commission', 0.0))
                }
                writer.writerow(row)
        
        return output_path
    
    def write_html_report(
        self,
        metrics: Dict[str, float],
        equity_curve: List[Dict[str, Any]],
        trades: List[Dict[str, Any]],
        strategy_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Write HTML report with summary
        
        Args:
            metrics: Performance metrics
            equity_curve: Equity curve data
            trades: Trade records
            strategy_name: Name of the strategy
            metadata: Optional metadata
            
        Returns:
            Path to the HTML report
        """
        output_path = self.output_dir / "report.html"
        
        # Sanitize metrics
        metrics = self._sanitize_metrics(metrics)
        
        # Create HTML content
        html_content = self._generate_html_report(
            metrics, equity_curve, trades, strategy_name, metadata
        )
        
        with open(output_path, 'w') as f:
            f.write(html_content)
        
        return output_path
    
    def _generate_html_report(
        self,
        metrics: Dict[str, float],
        equity_curve: List[Dict[str, Any]],
        trades: List[Dict[str, Any]],
        strategy_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate HTML report content"""
        
        # Calculate additional stats
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
        losing_trades = sum(1 for t in trades if t.get('pnl', 0) < 0)
        
        # Format metadata
        metadata_html = ""
        if metadata:
            metadata_items = []
            for key, value in metadata.items():
                metadata_items.append(f"<li><strong>{key}:</strong> {value}</li>")
            metadata_html = f"<ul>{''.join(metadata_items)}</ul>"
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Backtest Report - {strategy_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .metric-card {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            border-left: 4px solid #4CAF50;
        }}
        .metric-label {{
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: #333;
            margin-top: 5px;
        }}
        .positive {{ color: #4CAF50; }}
        .negative {{ color: #f44336; }}
        .summary {{
            background: #e8f5e9;
            padding: 20px;
            border-radius: 4px;
            margin: 20px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #f5f5f5;
            font-weight: 600;
        }}
        .timestamp {{
            color: #777;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Backtest Report: {strategy_name}</h1>
        
        <div class="timestamp">
            Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
        
        <div class="summary">
            <h2>Summary</h2>
            <p><strong>Total Returns:</strong> <span class="{'positive' if metrics.get('returns', 0) >= 0 else 'negative'}">{metrics.get('returns', 0):.2f}%</span></p>
            <p><strong>Sharpe Ratio:</strong> {metrics.get('sharpe', 0):.2f}</p>
            <p><strong>Max Drawdown:</strong> <span class="negative">{metrics.get('max_dd', 0):.2f}%</span></p>
            <p><strong>Total Trades:</strong> {total_trades}</p>
        </div>
        
        <h2>Key Metrics</h2>
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Sharpe Ratio</div>
                <div class="metric-value">{metrics.get('sharpe', 0):.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Profit Factor</div>
                <div class="metric-value">{metrics.get('profit_factor', 0):.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Win Rate</div>
                <div class="metric-value">{metrics.get('win_rate', 0):.1f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Max Drawdown</div>
                <div class="metric-value negative">{metrics.get('max_dd', 0):.1f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total Returns</div>
                <div class="metric-value {'positive' if metrics.get('returns', 0) >= 0 else 'negative'}">{metrics.get('returns', 0):.1f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total Trades</div>
                <div class="metric-value">{total_trades}</div>
            </div>
        </div>
        
        <h2>Trade Statistics</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Total Trades</td>
                <td>{total_trades}</td>
            </tr>
            <tr>
                <td>Winning Trades</td>
                <td class="positive">{winning_trades}</td>
            </tr>
            <tr>
                <td>Losing Trades</td>
                <td class="negative">{losing_trades}</td>
            </tr>
            <tr>
                <td>Win Rate</td>
                <td>{metrics.get('win_rate', 0):.1f}%</td>
            </tr>
            <tr>
                <td>Profit Factor</td>
                <td>{metrics.get('profit_factor', 0):.2f}</td>
            </tr>
        </table>
        
        {f'<h2>Strategy Parameters</h2>{metadata_html}' if metadata_html else ''}
        
        <h2>Performance Chart</h2>
        <p><em>Equity curve visualization would go here. See equity.csv for data.</em></p>
        
        <h2>Recent Trades</h2>
        <p>Showing last 10 trades. See trades.csv for complete history.</p>
        <table>
            <tr>
                <th>Entry Time</th>
                <th>Exit Time</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>PnL</th>
                <th>PnL %</th>
            </tr>
            {''.join([f'''<tr>
                <td>{t.get('entry_time', '')}</td>
                <td>{t.get('exit_time', '')}</td>
                <td>{t.get('symbol', '')}</td>
                <td>{t.get('side', '')}</td>
                <td class="{'positive' if t.get('pnl', 0) >= 0 else 'negative'}">{t.get('pnl', 0):.2f}</td>
                <td class="{'positive' if t.get('pnl_percent', 0) >= 0 else 'negative'}">{t.get('pnl_percent', 0):.2f}%</td>
            </tr>''' for t in trades[-10:]])}
        </table>
    </div>
</body>
</html>"""
        
        return html
    
    def _sanitize_float(self, value: Any) -> float:
        """Ensure a value is a finite float"""
        try:
            f = float(value)
            if math.isnan(f) or math.isinf(f):
                return 0.0
            return f
        except (TypeError, ValueError):
            return 0.0
    
    def _sanitize_metrics(self, metrics: Dict[str, Any]) -> Dict[str, float]:
        """Ensure all metrics are finite floats"""
        sanitized = {}
        for key, value in metrics.items():
            sanitized[key] = self._sanitize_float(value)
        return sanitized