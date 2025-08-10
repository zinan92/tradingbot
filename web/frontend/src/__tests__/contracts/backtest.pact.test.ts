import { Pact, Matchers } from '@pact-foundation/pact';
import path from 'path';

const { like, eachLike, term, iso8601DateTimeWithMillis } = Matchers;

describe('Backtest API Pact Tests', () => {
  const provider = new Pact({
    consumer: 'TradingBotUI',
    provider: 'TradingBotAPI',
    log: path.resolve(process.cwd(), 'logs', 'pact.log'),
    logLevel: 'warn',
    dir: path.resolve(process.cwd(), 'pacts'),
    cors: true,
    port: 1234
  });

  beforeAll(() => provider.setup());
  afterEach(() => provider.verify());
  afterAll(() => provider.finalize());

  describe('POST /api/backtest/run', () => {
    it('should run a backtest successfully', async () => {
      const backtestRequest = {
        strategy_id: 'strat-001',
        symbol: 'BTCUSDT',
        start_date: '2024-01-01',
        end_date: '2024-12-31',
        initial_capital: 10000,
        timeframe: '1h',
        params: {
          fast_period: 12,
          slow_period: 26,
          stop_loss_pct: 0.02,
          take_profit_pct: 0.05
        }
      };

      const expectedResponse = {
        backtest_id: like('backtest-456'),
        status: like('completed'),
        strategy_id: like('strat-001'),
        symbol: like('BTCUSDT'),
        timeframe: like('1h'),
        period: {
          start: like('2024-01-01'),
          end: like('2024-12-31')
        },
        metrics: {
          total_return: like(25.5),
          total_return_pct: like(2.55),
          sharpe_ratio: like(1.85),
          sortino_ratio: like(2.1),
          max_drawdown: like(-8.5),
          max_drawdown_pct: like(-0.85),
          win_rate: like(58.5),
          profit_factor: like(1.75),
          total_trades: like(245),
          winning_trades: like(143),
          losing_trades: like(102),
          avg_win: like(125.50),
          avg_loss: like(-65.25),
          largest_win: like(450.00),
          largest_loss: like(-180.00),
          consecutive_wins: like(8),
          consecutive_losses: like(5),
          recovery_factor: like(3.0),
          calmar_ratio: like(3.0),
          var_95: like(-250.00),
          cvar_95: like(-320.00)
        },
        trades: eachLike({
          id: like('trade-001'),
          timestamp: iso8601DateTimeWithMillis(),
          side: term({
            matcher: 'buy|sell',
            generate: 'buy'
          }),
          quantity: like(0.5),
          price: like(42500.00),
          pnl: like(125.50),
          pnl_pct: like(0.59),
          commission: like(2.50),
          slippage: like(0.05)
        }),
        equity_curve: eachLike({
          timestamp: iso8601DateTimeWithMillis(),
          equity: like(10250.00),
          drawdown: like(-2.5)
        }),
        daily_returns: eachLike({
          date: like('2024-01-01'),
          return_pct: like(0.85),
          equity: like(10085.00)
        }),
        completed_at: iso8601DateTimeWithMillis(),
        execution_time_ms: like(1250)
      };

      await provider.addInteraction({
        state: 'ready to run backtest',
        uponReceiving: 'a request to run a backtest',
        withRequest: {
          method: 'POST',
          path: '/api/backtest/run',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json'
          },
          body: backtestRequest
        },
        willRespondWith: {
          status: 200,
          headers: {
            'Content-Type': 'application/json'
          },
          body: expectedResponse
        }
      });

      const response = await fetch('http://localhost:1234/api/backtest/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json'
        },
        body: JSON.stringify(backtestRequest)
      });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.backtest_id).toBeDefined();
      expect(data.status).toBe('completed');
      expect(data.metrics).toBeDefined();
      expect(data.metrics.total_return).toBeDefined();
      expect(data.metrics.sharpe_ratio).toBeDefined();
      expect(data.trades).toBeDefined();
      expect(Array.isArray(data.trades)).toBe(true);
    });

    it('should handle backtest with invalid parameters', async () => {
      const invalidRequest = {
        strategy_id: 'strat-001',
        symbol: 'INVALID',
        start_date: '2025-01-01', // Future date
        end_date: '2024-01-01', // End before start
        initial_capital: -1000 // Negative capital
      };

      const expectedError = {
        error: like('Validation Error'),
        code: like('INVALID_PARAMS'),
        details: eachLike({
          field: like('start_date'),
          message: like('Start date must be before end date'),
          value: like('2025-01-01')
        })
      };

      await provider.addInteraction({
        state: 'ready to run backtest',
        uponReceiving: 'an invalid backtest request',
        withRequest: {
          method: 'POST',
          path: '/api/backtest/run',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json'
          },
          body: invalidRequest
        },
        willRespondWith: {
          status: 400,
          headers: {
            'Content-Type': 'application/json'
          },
          body: expectedError
        }
      });

      const response = await fetch('http://localhost:1234/api/backtest/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json'
        },
        body: JSON.stringify(invalidRequest)
      });
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBeDefined();
      expect(data.code).toBe('INVALID_PARAMS');
      expect(data.details).toBeDefined();
    });

    it('should handle async backtest initiation', async () => {
      const backtestRequest = {
        strategy_id: 'strat-002',
        symbol: 'ETHUSDT',
        start_date: '2023-01-01',
        end_date: '2023-12-31',
        initial_capital: 50000,
        mode: 'async' // Async mode
      };

      const expectedResponse = {
        backtest_id: like('backtest-789'),
        status: like('running'),
        message: like('Backtest started successfully'),
        estimated_time_seconds: like(30),
        progress_url: like('/api/backtest/backtest-789/status'),
        result_url: like('/api/backtest/backtest-789/result'),
        started_at: iso8601DateTimeWithMillis()
      };

      await provider.addInteraction({
        state: 'ready to run async backtest',
        uponReceiving: 'a request to run async backtest',
        withRequest: {
          method: 'POST',
          path: '/api/backtest/run',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json'
          },
          body: backtestRequest
        },
        willRespondWith: {
          status: 202, // Accepted
          headers: {
            'Content-Type': 'application/json',
            'Location': term({
              matcher: '/api/backtest/[a-z0-9-]+/status',
              generate: '/api/backtest/backtest-789/status'
            })
          },
          body: expectedResponse
        }
      });

      const response = await fetch('http://localhost:1234/api/backtest/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json'
        },
        body: JSON.stringify(backtestRequest)
      });
      const data = await response.json();

      expect(response.status).toBe(202);
      expect(data.backtest_id).toBeDefined();
      expect(data.status).toBe('running');
      expect(data.progress_url).toBeDefined();
      expect(data.result_url).toBeDefined();
    });
  });
});