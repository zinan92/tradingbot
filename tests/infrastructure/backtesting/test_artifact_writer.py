"""
Tests for Backtest Artifact Writer

Verifies that artifacts are generated with correct schema and valid data.
"""
import pytest
import json
import csv
import math
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from src.infrastructure.backtesting.artifact_writer import BacktestArtifactWriter


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test artifacts"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_metrics():
    """Sample metrics data"""
    return {
        'sharpe': 1.5,
        'profit_factor': 2.3,
        'win_rate': 65.0,
        'max_dd': 12.5,
        'returns': 45.2,
        'total_trades': 150,
        'winning_trades': 98,
        'losing_trades': 52
    }


@pytest.fixture
def sample_equity_curve():
    """Sample equity curve data"""
    return [
        {
            'timestamp': '2024-01-01 00:00:00',
            'equity': 10000.0,
            'drawdown': 0.0,
            'returns': 0.0
        },
        {
            'timestamp': '2024-01-02 00:00:00',
            'equity': 10500.0,
            'drawdown': 0.0,
            'returns': 5.0
        },
        {
            'timestamp': '2024-01-03 00:00:00',
            'equity': 10200.0,
            'drawdown': 2.86,
            'returns': 2.0
        }
    ]


@pytest.fixture
def sample_trades():
    """Sample trades data"""
    return [
        {
            'entry_time': '2024-01-01 10:00:00',
            'exit_time': '2024-01-01 14:00:00',
            'symbol': 'BTCUSDT',
            'side': 'long',
            'entry_price': 45000.0,
            'exit_price': 45500.0,
            'quantity': 0.1,
            'pnl': 50.0,
            'pnl_percent': 1.11,
            'commission': 2.0
        },
        {
            'entry_time': '2024-01-02 09:00:00',
            'exit_time': '2024-01-02 11:00:00',
            'symbol': 'ETHUSDT',
            'side': 'short',
            'entry_price': 3000.0,
            'exit_price': 2950.0,
            'quantity': 1.0,
            'pnl': 50.0,
            'pnl_percent': 1.67,
            'commission': 1.5
        }
    ]


def test_artifact_writer_creates_output_directory(temp_dir):
    """Test that output directory is created"""
    output_dir = Path(temp_dir) / "test_artifacts"
    writer = BacktestArtifactWriter(str(output_dir))
    
    assert output_dir.exists()
    assert output_dir.is_dir()


def test_write_metrics_file_exists(temp_dir, sample_metrics):
    """Test that metrics.json is created"""
    writer = BacktestArtifactWriter(temp_dir)
    path = writer.write_metrics(sample_metrics)
    
    assert path.exists()
    assert path.name == "metrics.json"
    
    # Verify JSON is valid
    with open(path) as f:
        data = json.load(f)
    
    # Check required fields
    assert 'sharpe' in data
    assert 'profit_factor' in data
    assert 'win_rate' in data
    assert 'max_dd' in data
    assert 'returns' in data


def test_write_metrics_schema(temp_dir, sample_metrics):
    """Test that metrics.json has correct schema"""
    writer = BacktestArtifactWriter(temp_dir)
    path = writer.write_metrics(sample_metrics)
    
    with open(path) as f:
        data = json.load(f)
    
    # Verify all values are numbers
    for key, value in data.items():
        assert isinstance(value, (int, float)), f"{key} should be numeric"
        assert math.isfinite(value), f"{key} should be finite"
    
    # Verify expected metrics
    assert data['sharpe'] == 1.5
    assert data['profit_factor'] == 2.3
    assert data['win_rate'] == 65.0
    assert data['max_dd'] == 12.5
    assert data['returns'] == 45.2


def test_write_metrics_handles_nan_inf(temp_dir):
    """Test that NaN and Inf values are sanitized"""
    metrics = {
        'sharpe': float('nan'),
        'profit_factor': float('inf'),
        'win_rate': -float('inf'),
        'max_dd': None,
        'returns': "invalid"
    }
    
    writer = BacktestArtifactWriter(temp_dir)
    path = writer.write_metrics(metrics)
    
    with open(path) as f:
        data = json.load(f)
    
    # All invalid values should be converted to 0.0
    for key in ['sharpe', 'profit_factor', 'win_rate', 'max_dd', 'returns']:
        assert data[key] == 0.0
        assert math.isfinite(data[key])


def test_write_equity_curve_file_exists(temp_dir, sample_equity_curve):
    """Test that equity.csv is created"""
    writer = BacktestArtifactWriter(temp_dir)
    path = writer.write_equity_curve(sample_equity_curve)
    
    assert path.exists()
    assert path.name == "equity.csv"


def test_write_equity_curve_schema(temp_dir, sample_equity_curve):
    """Test that equity.csv has correct schema"""
    writer = BacktestArtifactWriter(temp_dir)
    path = writer.write_equity_curve(sample_equity_curve)
    
    with open(path) as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        rows = list(reader)
    
    # Check headers
    assert headers == ['timestamp', 'equity', 'drawdown', 'returns']
    
    # Check data
    assert len(rows) == 3
    
    # Verify first row
    assert rows[0]['timestamp'] == '2024-01-01 00:00:00'
    assert float(rows[0]['equity']) == 10000.0
    assert float(rows[0]['drawdown']) == 0.0
    assert float(rows[0]['returns']) == 0.0
    
    # Verify all numeric values are finite
    for row in rows:
        assert math.isfinite(float(row['equity']))
        assert math.isfinite(float(row['drawdown']))
        assert math.isfinite(float(row['returns']))


def test_write_equity_curve_empty(temp_dir):
    """Test that empty equity curve creates file with headers"""
    writer = BacktestArtifactWriter(temp_dir)
    path = writer.write_equity_curve([])
    
    with open(path) as f:
        reader = csv.reader(f)
        headers = next(reader)
        
    assert headers == ['timestamp', 'equity', 'drawdown', 'returns']
    
    # File should have only headers
    with open(path) as f:
        lines = f.readlines()
    assert len(lines) == 1


def test_write_trades_file_exists(temp_dir, sample_trades):
    """Test that trades.csv is created"""
    writer = BacktestArtifactWriter(temp_dir)
    path = writer.write_trades(sample_trades)
    
    assert path.exists()
    assert path.name == "trades.csv"


def test_write_trades_schema(temp_dir, sample_trades):
    """Test that trades.csv has correct schema"""
    writer = BacktestArtifactWriter(temp_dir)
    path = writer.write_trades(sample_trades)
    
    with open(path) as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        rows = list(reader)
    
    # Check headers
    expected_headers = [
        'entry_time', 'exit_time', 'symbol', 'side',
        'entry_price', 'exit_price', 'quantity',
        'pnl', 'pnl_percent', 'commission'
    ]
    assert headers == expected_headers
    
    # Check data
    assert len(rows) == 2
    
    # Verify first trade
    assert rows[0]['entry_time'] == '2024-01-01 10:00:00'
    assert rows[0]['symbol'] == 'BTCUSDT'
    assert rows[0]['side'] == 'long'
    assert float(rows[0]['pnl']) == 50.0
    
    # Verify all numeric values are finite
    numeric_fields = ['entry_price', 'exit_price', 'quantity', 'pnl', 'pnl_percent', 'commission']
    for row in rows:
        for field in numeric_fields:
            assert math.isfinite(float(row[field]))


def test_write_html_report_file_exists(temp_dir, sample_metrics, sample_equity_curve, sample_trades):
    """Test that report.html is created"""
    writer = BacktestArtifactWriter(temp_dir)
    path = writer.write_html_report(
        sample_metrics,
        sample_equity_curve,
        sample_trades,
        "TestStrategy"
    )
    
    assert path.exists()
    assert path.name == "report.html"


def test_write_html_report_contains_summary(temp_dir, sample_metrics, sample_equity_curve, sample_trades):
    """Test that HTML report contains summary information"""
    writer = BacktestArtifactWriter(temp_dir)
    path = writer.write_html_report(
        sample_metrics,
        sample_equity_curve,
        sample_trades,
        "TestStrategy",
        metadata={'param1': 'value1', 'param2': 42}
    )
    
    with open(path) as f:
        content = f.read()
    
    # Check for key elements
    assert "TestStrategy" in content
    assert "Summary" in content
    assert "45.2%" in content  # returns
    assert "1.5" in content  # sharpe ratio (formatted as 1.50)
    assert "12.5%" in content  # max drawdown
    assert "Key Metrics" in content
    assert "Trade Statistics" in content
    
    # Check for metadata
    assert "Strategy Parameters" in content
    assert "param1" in content
    assert "value1" in content
    
    # Check for trade data
    assert "BTCUSDT" in content
    assert "ETHUSDT" in content


def test_write_all_artifacts(temp_dir, sample_metrics, sample_equity_curve, sample_trades):
    """Test that all artifacts are written correctly"""
    writer = BacktestArtifactWriter(temp_dir)
    
    artifacts = writer.write_all_artifacts(
        sample_metrics,
        sample_equity_curve,
        sample_trades,
        "TestStrategy",
        {'timeframe': '1h', 'initial_capital': 10000}
    )
    
    # Check all files exist
    assert artifacts['metrics'].exists()
    assert artifacts['equity'].exists()
    assert artifacts['trades'].exists()
    assert artifacts['report'].exists()
    
    # Verify file names
    assert artifacts['metrics'].name == "metrics.json"
    assert artifacts['equity'].name == "equity.csv"
    assert artifacts['trades'].name == "trades.csv"
    assert artifacts['report'].name == "report.html"
    
    # Verify metrics content
    with open(artifacts['metrics']) as f:
        metrics_data = json.load(f)
    assert metrics_data['sharpe'] == 1.5
    assert math.isfinite(metrics_data['sharpe'])
    
    # Verify equity CSV has data
    with open(artifacts['equity']) as f:
        lines = f.readlines()
    assert len(lines) == 4  # header + 3 data rows
    
    # Verify trades CSV has data
    with open(artifacts['trades']) as f:
        lines = f.readlines()
    assert len(lines) == 3  # header + 2 trades
    
    # Verify HTML contains summary
    with open(artifacts['report']) as f:
        html = f.read()
    assert "Summary" in html
    assert "TestStrategy" in html


def test_sanitize_metrics_all_finite():
    """Test that sanitize_metrics ensures all values are finite"""
    writer = BacktestArtifactWriter()
    
    dirty_metrics = {
        'good': 1.5,
        'nan': float('nan'),
        'inf': float('inf'),
        'neg_inf': -float('inf'),
        'none': None,
        'string': "not a number"
    }
    
    clean = writer._sanitize_metrics(dirty_metrics)
    
    # All values should be finite floats
    for key, value in clean.items():
        assert isinstance(value, float)
        assert math.isfinite(value)
    
    # Good value should be preserved
    assert clean['good'] == 1.5
    
    # Bad values should be 0.0
    assert clean['nan'] == 0.0
    assert clean['inf'] == 0.0
    assert clean['neg_inf'] == 0.0
    assert clean['none'] == 0.0
    assert clean['string'] == 0.0


def test_edge_cases_with_missing_data(temp_dir):
    """Test handling of missing or incomplete data"""
    writer = BacktestArtifactWriter(temp_dir)
    
    # Missing required metrics
    incomplete_metrics = {'sharpe': 1.0}  # Missing other required fields
    path = writer.write_metrics(incomplete_metrics)
    
    with open(path) as f:
        data = json.load(f)
    
    # Should have defaults for missing fields
    assert data['profit_factor'] == 0.0
    assert data['win_rate'] == 0.0
    assert data['max_dd'] == 0.0
    assert data['returns'] == 0.0
    
    # Equity curve with missing fields
    incomplete_equity = [{'timestamp': '2024-01-01'}]  # Missing other fields
    path = writer.write_equity_curve(incomplete_equity)
    
    with open(path) as f:
        reader = csv.DictReader(f)
        row = next(reader)
    
    assert float(row['equity']) == 0.0
    assert float(row['drawdown']) == 0.0
    assert float(row['returns']) == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])