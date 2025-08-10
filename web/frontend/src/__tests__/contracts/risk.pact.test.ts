import { Pact, Matchers } from '@pact-foundation/pact';
import path from 'path';

const { like, eachLike, term, iso8601DateTimeWithMillis } = Matchers;

describe('Risk API Pact Tests', () => {
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

  describe('GET /api/risk/summary', () => {
    it('should return risk summary with normal levels', async () => {
      const expectedResponse = {
        exposure_pct: like(45.5),
        daily_loss_pct: like(1.2),
        drawdown_pct: like(3.5),
        risk_level: term({
          matcher: 'LOW|MEDIUM|HIGH|CRITICAL',
          generate: 'MEDIUM'
        }),
        thresholds: {
          exposure: like(80),
          daily_loss: like(5),
          drawdown: like(10)
        },
        metrics: {
          var_95: like(-2500.00),
          cvar_95: like(-3200.00),
          sharpe_ratio: like(1.85),
          sortino_ratio: like(2.1),
          beta: like(0.85),
          correlation_btc: like(0.92),
          max_position_size: like(0.25),
          leverage: like(1.0)
        },
        positions: {
          total: like(5),
          long: like(3),
          short: like(2),
          largest_position_pct: like(15.5),
          concentration_risk: term({
            matcher: 'low|medium|high',
            generate: 'low'
          })
        },
        alerts: eachLike({
          id: like('alert-001'),
          severity: term({
            matcher: 'info|warning|critical',
            generate: 'warning'
          }),
          type: like('exposure_threshold'),
          message: like('Exposure approaching threshold (75% of limit)'),
          timestamp: iso8601DateTimeWithMillis(),
          acknowledged: like(false)
        }),
        historical: {
          max_drawdown_30d: like(-8.5),
          max_daily_loss_30d: like(-3.2),
          avg_exposure_30d: like(42.3),
          breaches_30d: like(2)
        },
        recommendations: eachLike({
          action: like('reduce_position_size'),
          reason: like('High correlation between positions'),
          priority: term({
            matcher: 'low|medium|high',
            generate: 'medium'
          })
        }),
        last_updated: iso8601DateTimeWithMillis()
      };

      await provider.addInteraction({
        state: 'trading is active with normal risk',
        uponReceiving: 'a request for risk summary',
        withRequest: {
          method: 'GET',
          path: '/api/risk/summary',
          headers: {
            Accept: 'application/json'
          }
        },
        willRespondWith: {
          status: 200,
          headers: {
            'Content-Type': 'application/json'
          },
          body: expectedResponse
        }
      });

      const response = await fetch('http://localhost:1234/api/risk/summary', {
        headers: { Accept: 'application/json' }
      });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.exposure_pct).toBeDefined();
      expect(data.risk_level).toBeDefined();
      expect(data.thresholds).toBeDefined();
      expect(data.metrics).toBeDefined();
    });

    it('should return critical risk summary', async () => {
      const expectedResponse = {
        exposure_pct: like(95.0),
        daily_loss_pct: like(6.5),
        drawdown_pct: like(12.0),
        risk_level: like('CRITICAL'),
        thresholds: {
          exposure: like(80),
          daily_loss: like(5),
          drawdown: like(10)
        },
        breaches: eachLike({
          metric: like('exposure'),
          current_value: like(95.0),
          threshold: like(80),
          exceeded_by_pct: like(18.75),
          duration_minutes: like(15),
          action_required: like('immediate_reduction')
        }),
        auto_actions: {
          enabled: like(true),
          triggered: eachLike({
            action: like('position_reduction'),
            timestamp: iso8601DateTimeWithMillis(),
            details: like('Reduced BTCUSDT position by 50%')
          }),
          pending: eachLike({
            action: like('trading_pause'),
            trigger_at: iso8601DateTimeWithMillis(),
            condition: like('If exposure > 100%')
          })
        },
        alerts: eachLike({
          id: like('alert-critical-001'),
          severity: like('critical'),
          type: like('multiple_threshold_breach'),
          message: like('CRITICAL: Multiple risk thresholds breached'),
          timestamp: iso8601DateTimeWithMillis(),
          acknowledged: like(false),
          escalated: like(true),
          escalation_level: like(2)
        }),
        emergency_controls: {
          pause_trading: like(true),
          close_all_positions: like(true),
          cancel_all_orders: like(true),
          estimated_loss_if_closed: like(-5250.00)
        },
        last_updated: iso8601DateTimeWithMillis()
      };

      await provider.addInteraction({
        state: 'critical risk thresholds breached',
        uponReceiving: 'a request for risk summary in critical state',
        withRequest: {
          method: 'GET',
          path: '/api/risk/summary',
          headers: {
            Accept: 'application/json'
          }
        },
        willRespondWith: {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
            'X-Risk-Alert': 'CRITICAL'
          },
          body: expectedResponse
        }
      });

      const response = await fetch('http://localhost:1234/api/risk/summary', {
        headers: { Accept: 'application/json' }
      });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.risk_level).toBe('CRITICAL');
      expect(data.breaches).toBeDefined();
      expect(data.auto_actions).toBeDefined();
      expect(data.emergency_controls).toBeDefined();
      expect(response.headers.get('X-Risk-Alert')).toBe('CRITICAL');
    });

    it('should return risk summary with no positions', async () => {
      const expectedResponse = {
        exposure_pct: like(0),
        daily_loss_pct: like(0),
        drawdown_pct: like(0),
        risk_level: like('LOW'),
        thresholds: {
          exposure: like(80),
          daily_loss: like(5),
          drawdown: like(10)
        },
        metrics: {
          var_95: like(0),
          cvar_95: like(0),
          sharpe_ratio: like(0),
          sortino_ratio: like(0),
          beta: like(0),
          correlation_btc: like(0),
          max_position_size: like(0.25),
          leverage: like(1.0)
        },
        positions: {
          total: like(0),
          long: like(0),
          short: like(0),
          largest_position_pct: like(0),
          concentration_risk: like('none')
        },
        message: like('No active positions'),
        last_updated: iso8601DateTimeWithMillis()
      };

      await provider.addInteraction({
        state: 'no active positions',
        uponReceiving: 'a request for risk summary with no positions',
        withRequest: {
          method: 'GET',
          path: '/api/risk/summary',
          headers: {
            Accept: 'application/json'
          }
        },
        willRespondWith: {
          status: 200,
          headers: {
            'Content-Type': 'application/json'
          },
          body: expectedResponse
        }
      });

      const response = await fetch('http://localhost:1234/api/risk/summary', {
        headers: { Accept: 'application/json' }
      });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.exposure_pct).toBe(0);
      expect(data.risk_level).toBe('LOW');
      expect(data.positions.total).toBe(0);
      expect(data.message).toBeDefined();
    });

    it('should include filtering parameters', async () => {
      const expectedResponse = {
        exposure_pct: like(35.5),
        daily_loss_pct: like(0.8),
        drawdown_pct: like(2.1),
        risk_level: like('LOW'),
        thresholds: {
          exposure: like(80),
          daily_loss: like(5),
          drawdown: like(10)
        },
        filter_applied: {
          account: like('main'),
          strategy: like('strat-001')
        },
        metrics: {
          var_95: like(-1200.00),
          cvar_95: like(-1500.00),
          sharpe_ratio: like(2.1),
          sortino_ratio: like(2.5)
        },
        last_updated: iso8601DateTimeWithMillis()
      };

      await provider.addInteraction({
        state: 'trading is active',
        uponReceiving: 'a filtered risk summary request',
        withRequest: {
          method: 'GET',
          path: '/api/risk/summary',
          query: {
            account: 'main',
            strategy: 'strat-001'
          },
          headers: {
            Accept: 'application/json'
          }
        },
        willRespondWith: {
          status: 200,
          headers: {
            'Content-Type': 'application/json'
          },
          body: expectedResponse
        }
      });

      const response = await fetch('http://localhost:1234/api/risk/summary?account=main&strategy=strat-001', {
        headers: { Accept: 'application/json' }
      });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.filter_applied).toBeDefined();
      expect(data.filter_applied.account).toBe('main');
      expect(data.filter_applied.strategy).toBe('strat-001');
    });
  });
});