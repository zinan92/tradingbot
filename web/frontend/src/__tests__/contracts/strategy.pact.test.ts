import { Pact, Matchers } from '@pact-foundation/pact';
import path from 'path';
import { api } from '@/services/api';

const { like, eachLike, term, iso8601DateTimeWithMillis } = Matchers;

describe('Strategy API Pact Tests', () => {
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

  describe('GET /api/strategy', () => {
    it('should return list of strategies', async () => {
      const expectedBody = eachLike({
        id: like('strat-001'),
        name: like('EMA Cross Strategy'),
        type: term({
          matcher: 'EMA_CROSS|RSI|MACD|SMA_CROSS',
          generate: 'EMA_CROSS'
        }),
        status: term({
          matcher: 'active|inactive|testing',
          generate: 'active'
        }),
        params: like({
          fast_period: like(12),
          slow_period: like(26),
          stop_loss_pct: like(0.02),
          take_profit_pct: like(0.05)
        }),
        performance: {
          total_return: like(15.5),
          sharpe_ratio: like(1.8),
          max_drawdown: like(-5.2),
          win_rate: like(62.5)
        },
        created_at: iso8601DateTimeWithMillis(),
        updated_at: iso8601DateTimeWithMillis()
      });

      await provider.addInteraction({
        state: 'strategies exist',
        uponReceiving: 'a request for all strategies',
        withRequest: {
          method: 'GET',
          path: '/api/strategy',
          headers: {
            Accept: 'application/json'
          }
        },
        willRespondWith: {
          status: 200,
          headers: {
            'Content-Type': 'application/json'
          },
          body: expectedBody
        }
      });

      // Use test endpoint
      const testApi = Object.create(api);
      testApi.baseUrl = 'http://localhost:1234';
      
      const response = await fetch(`${testApi.baseUrl}/api/strategy`, {
        headers: { Accept: 'application/json' }
      });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(Array.isArray(data)).toBe(true);
      expect(data[0]).toHaveProperty('id');
      expect(data[0]).toHaveProperty('name');
      expect(data[0]).toHaveProperty('status');
    });

    it('should get single strategy by ID', async () => {
      const strategyId = 'strat-001';
      const expectedBody = {
        id: like(strategyId),
        name: like('EMA Cross Strategy'),
        type: term({
          matcher: 'EMA_CROSS|RSI|MACD|SMA_CROSS',
          generate: 'EMA_CROSS'
        }),
        status: term({
          matcher: 'active|inactive|testing',
          generate: 'active'
        }),
        params: like({
          fast_period: like(12),
          slow_period: like(26),
          stop_loss_pct: like(0.02),
          take_profit_pct: like(0.05),
          position_size: like(0.95),
          use_volume_filter: like(false),
          trailing_stop_pct: like(0.03)
        }),
        performance: {
          total_return: like(15.5),
          sharpe_ratio: like(1.8),
          max_drawdown: like(-5.2),
          win_rate: like(62.5),
          profit_factor: like(1.6),
          total_trades: like(125),
          winning_trades: like(78),
          losing_trades: like(47)
        },
        risk_metrics: {
          var_95: like(-2.5),
          cvar_95: like(-3.2),
          beta: like(0.85),
          alpha: like(0.12)
        },
        created_at: iso8601DateTimeWithMillis(),
        updated_at: iso8601DateTimeWithMillis(),
        last_execution: iso8601DateTimeWithMillis()
      };

      await provider.addInteraction({
        state: 'strategy exists',
        uponReceiving: 'a request for a specific strategy',
        withRequest: {
          method: 'GET',
          path: `/api/strategy/${strategyId}`,
          headers: {
            Accept: 'application/json'
          }
        },
        willRespondWith: {
          status: 200,
          headers: {
            'Content-Type': 'application/json'
          },
          body: expectedBody
        }
      });

      const testApi = Object.create(api);
      testApi.baseUrl = 'http://localhost:1234';
      
      const response = await fetch(`${testApi.baseUrl}/api/strategy/${strategyId}`, {
        headers: { Accept: 'application/json' }
      });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.id).toBeDefined();
      expect(data.params).toBeDefined();
      expect(data.performance).toBeDefined();
    });
  });

  describe('POST /api/strategy/publish', () => {
    it('should publish a strategy', async () => {
      const publishRequest = {
        strategy_id: 'strat-001',
        environment: 'production',
        version: '1.2.0',
        notes: 'Improved risk parameters'
      };

      const expectedResponse = {
        success: like(true),
        message: like('Strategy published successfully'),
        published_at: iso8601DateTimeWithMillis(),
        deployment: {
          id: like('deploy-123'),
          strategy_id: like('strat-001'),
          environment: term({
            matcher: 'production|staging|testing',
            generate: 'production'
          }),
          version: like('1.2.0'),
          status: like('deployed'),
          deployed_at: iso8601DateTimeWithMillis()
        }
      };

      await provider.addInteraction({
        state: 'ready to publish strategy',
        uponReceiving: 'a request to publish a strategy',
        withRequest: {
          method: 'POST',
          path: '/api/strategy/publish',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json'
          },
          body: publishRequest
        },
        willRespondWith: {
          status: 200,
          headers: {
            'Content-Type': 'application/json'
          },
          body: expectedResponse
        }
      });

      const testApi = Object.create(api);
      testApi.baseUrl = 'http://localhost:1234';
      
      const response = await fetch(`${testApi.baseUrl}/api/strategy/publish`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json'
        },
        body: JSON.stringify(publishRequest)
      });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.deployment).toBeDefined();
      expect(data.deployment.status).toBe('deployed');
    });

    it('should handle validation errors', async () => {
      const invalidRequest = {
        strategy_id: '', // Invalid: empty ID
        environment: 'invalid_env'
      };

      const expectedError = {
        error: like('Validation Error'),
        details: eachLike({
          field: like('strategy_id'),
          message: like('Strategy ID is required')
        })
      };

      await provider.addInteraction({
        state: 'ready to publish strategy',
        uponReceiving: 'an invalid publish request',
        withRequest: {
          method: 'POST',
          path: '/api/strategy/publish',
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

      const testApi = Object.create(api);
      testApi.baseUrl = 'http://localhost:1234';
      
      const response = await fetch(`${testApi.baseUrl}/api/strategy/publish`, {
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
      expect(data.details).toBeDefined();
    });
  });
});