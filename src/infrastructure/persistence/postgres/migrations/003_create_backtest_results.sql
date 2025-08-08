-- Migration: Create Backtest Results Tables
-- Description: Tables for storing backtesting results and trade history
-- Date: 2025-08-07

-- Create enum for position direction
CREATE TYPE position_direction AS ENUM ('LONG', 'SHORT', 'NEUTRAL');

-- Create enum for backtest status
CREATE TYPE backtest_status AS ENUM ('pending', 'running', 'completed', 'failed', 'cancelled');

-- Main backtest results table
CREATE TABLE IF NOT EXISTS backtest_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Metadata
    strategy_name VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    interval VARCHAR(10) NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    
    -- Parameters
    initial_capital DECIMAL(20, 2) NOT NULL,
    leverage DECIMAL(10, 2) DEFAULT 1.0,
    market_commission DECIMAL(10, 6) DEFAULT 0.0004,
    limit_commission DECIMAL(10, 6) DEFAULT 0.0002,
    strategy_params JSONB,
    
    -- Performance Metrics
    base_return_pct DECIMAL(20, 4),
    leveraged_return_pct DECIMAL(20, 4),
    sharpe_ratio DECIMAL(10, 4),
    sortino_ratio DECIMAL(10, 4),
    calmar_ratio DECIMAL(10, 4),
    max_drawdown_pct DECIMAL(10, 4),
    win_rate_pct DECIMAL(10, 4),
    profit_factor DECIMAL(10, 4),
    kelly_criterion DECIMAL(10, 6),
    sqn DECIMAL(10, 4),
    
    -- Trade Statistics
    total_trades INTEGER DEFAULT 0,
    long_trades INTEGER DEFAULT 0,
    short_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    
    -- Futures Metrics
    long_win_rate_pct DECIMAL(10, 4),
    short_win_rate_pct DECIMAL(10, 4),
    avg_trade_pct DECIMAL(10, 4),
    best_trade_pct DECIMAL(10, 4),
    worst_trade_pct DECIMAL(10, 4),
    avg_trade_duration INTERVAL,
    max_trade_duration INTERVAL,
    
    -- Financial Metrics
    final_equity DECIMAL(20, 2),
    peak_equity DECIMAL(20, 2),
    total_commission_paid DECIMAL(20, 4),
    
    -- Volatility Metrics
    volatility_annual_pct DECIMAL(10, 4),
    leveraged_volatility_pct DECIMAL(10, 4),
    
    -- Status and Timing
    status backtest_status DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    execution_time_ms INTEGER,
    
    -- Additional Data
    error_message TEXT,
    chart_html TEXT,  -- Store the HTML chart
    full_stats JSONB,  -- Store complete statistics
    
    -- Indexes for common queries
    INDEX idx_backtest_symbol (symbol),
    INDEX idx_backtest_strategy (strategy_name),
    INDEX idx_backtest_created (created_at DESC),
    INDEX idx_backtest_return (leveraged_return_pct DESC),
    INDEX idx_backtest_sharpe (sharpe_ratio DESC)
);

-- Backtest trades table (detailed trade history)
CREATE TABLE IF NOT EXISTS backtest_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    backtest_id UUID NOT NULL REFERENCES backtest_results(id) ON DELETE CASCADE,
    
    -- Trade Details
    trade_num INTEGER NOT NULL,
    direction position_direction NOT NULL,
    
    -- Entry/Exit
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP NOT NULL,
    entry_price DECIMAL(20, 8) NOT NULL,
    exit_price DECIMAL(20, 8) NOT NULL,
    
    -- Size and P&L
    size DECIMAL(20, 8) NOT NULL,
    pnl DECIMAL(20, 4),
    pnl_pct DECIMAL(10, 4),
    leveraged_pnl_pct DECIMAL(10, 4),
    
    -- Commission
    entry_commission DECIMAL(20, 8),
    exit_commission DECIMAL(20, 8),
    
    -- Trade Duration
    duration INTERVAL,
    
    -- Metadata
    entry_reason VARCHAR(100),
    exit_reason VARCHAR(100),
    
    -- Index for queries
    INDEX idx_trade_backtest (backtest_id),
    INDEX idx_trade_time (entry_time, exit_time),
    INDEX idx_trade_pnl (pnl_pct DESC)
);

-- Backtest optimization results table
CREATE TABLE IF NOT EXISTS backtest_optimizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Optimization Details
    strategy_name VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    interval VARCHAR(10) NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    
    -- Optimization Parameters
    param_ranges JSONB NOT NULL,
    optimization_metric VARCHAR(50) NOT NULL,  -- e.g., 'Sharpe Ratio', 'Return [%]'
    
    -- Best Parameters Found
    best_params JSONB,
    best_metric_value DECIMAL(20, 4),
    
    -- Results
    all_results JSONB,  -- Store all parameter combinations tested
    total_combinations INTEGER,
    
    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    execution_time_ms INTEGER,
    
    -- Index
    INDEX idx_optimization_symbol (symbol),
    INDEX idx_optimization_strategy (strategy_name),
    INDEX idx_optimization_created (created_at DESC)
);

-- Function to calculate backtest statistics
CREATE OR REPLACE FUNCTION calculate_backtest_stats(backtest_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE backtest_results br
    SET 
        total_trades = (SELECT COUNT(*) FROM backtest_trades WHERE backtest_id = br.id),
        long_trades = (SELECT COUNT(*) FROM backtest_trades WHERE backtest_id = br.id AND direction = 'LONG'),
        short_trades = (SELECT COUNT(*) FROM backtest_trades WHERE backtest_id = br.id AND direction = 'SHORT'),
        winning_trades = (SELECT COUNT(*) FROM backtest_trades WHERE backtest_id = br.id AND pnl > 0),
        losing_trades = (SELECT COUNT(*) FROM backtest_trades WHERE backtest_id = br.id AND pnl <= 0),
        avg_trade_pct = (SELECT AVG(pnl_pct) FROM backtest_trades WHERE backtest_id = br.id),
        best_trade_pct = (SELECT MAX(pnl_pct) FROM backtest_trades WHERE backtest_id = br.id),
        worst_trade_pct = (SELECT MIN(pnl_pct) FROM backtest_trades WHERE backtest_id = br.id)
    WHERE br.id = backtest_id;
END;
$$ LANGUAGE plpgsql;

-- View for recent backtest performance
CREATE OR REPLACE VIEW v_recent_backtests AS
SELECT 
    br.id,
    br.strategy_name,
    br.symbol,
    br.interval,
    br.start_date,
    br.end_date,
    br.leveraged_return_pct,
    br.sharpe_ratio,
    br.max_drawdown_pct,
    br.win_rate_pct,
    br.total_trades,
    br.status,
    br.created_at,
    br.execution_time_ms
FROM backtest_results br
WHERE br.created_at > CURRENT_DATE - INTERVAL '30 days'
ORDER BY br.created_at DESC;

-- View for strategy performance comparison
CREATE OR REPLACE VIEW v_strategy_performance AS
SELECT 
    strategy_name,
    symbol,
    COUNT(*) as backtest_count,
    AVG(leveraged_return_pct) as avg_return,
    MAX(leveraged_return_pct) as max_return,
    MIN(leveraged_return_pct) as min_return,
    AVG(sharpe_ratio) as avg_sharpe,
    AVG(win_rate_pct) as avg_win_rate,
    AVG(total_trades) as avg_trades
FROM backtest_results
WHERE status = 'completed'
GROUP BY strategy_name, symbol
ORDER BY avg_return DESC;

-- Comments
COMMENT ON TABLE backtest_results IS 'Stores comprehensive backtesting results including futures metrics';
COMMENT ON TABLE backtest_trades IS 'Detailed trade-by-trade history for each backtest';
COMMENT ON TABLE backtest_optimizations IS 'Results from parameter optimization runs';
COMMENT ON COLUMN backtest_results.leveraged_return_pct IS 'Return percentage with leverage applied';
COMMENT ON COLUMN backtest_results.sqn IS 'System Quality Number - measure of trading system quality';
COMMENT ON COLUMN backtest_trades.direction IS 'LONG for buy positions, SHORT for sell positions';