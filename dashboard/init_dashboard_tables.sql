-- Initialize tables for dashboard if they don't exist
-- Run with: psql -d tradingbot -f dashboard/init_dashboard_tables.sql

-- Create positions table (for tracking open positions)
CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    entry_price DECIMAL(20, 8) NOT NULL,
    current_price DECIMAL(20, 8),
    unrealized_pnl DECIMAL(20, 8) DEFAULT 0,
    realized_pnl DECIMAL(20, 8) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'OPEN',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create orders table (for tracking trades)
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL DEFAULT 'MARKET',
    quantity DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8),
    status VARCHAR(20) DEFAULT 'NEW',
    filled_quantity DECIMAL(20, 8) DEFAULT 0,
    filled_price DECIMAL(20, 8),
    fee DECIMAL(20, 8) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    filled_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create performance_history table (for tracking daily performance)
CREATE TABLE IF NOT EXISTS performance_history (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    daily_pnl DECIMAL(20, 8) DEFAULT 0,
    cumulative_pnl DECIMAL(20, 8) DEFAULT 0,
    win_rate DECIMAL(5, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add some sample data for demonstration
-- Sample positions (you can remove this section if you want real data only)
INSERT INTO positions (symbol, side, quantity, entry_price, current_price, unrealized_pnl, status)
VALUES 
    ('BTCUSDT', 'LONG', 0.001, 95000, 96500, 1.50, 'OPEN'),
    ('ETHUSDT', 'LONG', 0.1, 3200, 3250, 5.00, 'OPEN'),
    ('BNBUSDT', 'SHORT', 1.0, 650, 645, 5.00, 'OPEN')
ON CONFLICT DO NOTHING;

-- Sample recent orders
INSERT INTO orders (symbol, side, quantity, price, filled_quantity, filled_price, status, filled_at)
VALUES
    ('BTCUSDT', 'BUY', 0.001, 95000, 0.001, 95000, 'FILLED', NOW() - INTERVAL '1 hour'),
    ('ETHUSDT', 'BUY', 0.1, 3200, 0.1, 3200, 'FILLED', NOW() - INTERVAL '2 hours'),
    ('BNBUSDT', 'SELL', 1.0, 650, 1.0, 650, 'FILLED', NOW() - INTERVAL '3 hours'),
    ('BTCUSDT', 'SELL', 0.0005, 96000, 0.0005, 96000, 'FILLED', NOW() - INTERVAL '4 hours'),
    ('LINKUSDT', 'BUY', 10, 25, 10, 25, 'FILLED', NOW() - INTERVAL '5 hours')
ON CONFLICT DO NOTHING;

-- Sample performance history
INSERT INTO performance_history (date, total_trades, winning_trades, daily_pnl, cumulative_pnl, win_rate)
SELECT 
    CURRENT_DATE - i,
    5 + (random() * 10)::int,
    3 + (random() * 5)::int,
    -50 + (random() * 200),
    0,
    40 + (random() * 30)
FROM generate_series(0, 29) AS i
ON CONFLICT (date) DO NOTHING;

-- Update cumulative P&L
WITH cumulative AS (
    SELECT 
        id,
        date,
        SUM(daily_pnl) OVER (ORDER BY date) as cum_pnl
    FROM performance_history
)
UPDATE performance_history p
SET cumulative_pnl = c.cum_pnl
FROM cumulative c
WHERE p.id = c.id;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_performance_date ON performance_history(date);

-- Grant permissions (adjust user as needed)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO CURRENT_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO CURRENT_USER;

-- Show summary
SELECT 'Dashboard tables initialized successfully!' as message;
SELECT 'Positions:' as table_name, COUNT(*) as count FROM positions
UNION ALL
SELECT 'Orders:', COUNT(*) FROM orders
UNION ALL
SELECT 'Performance History:', COUNT(*) FROM performance_history;