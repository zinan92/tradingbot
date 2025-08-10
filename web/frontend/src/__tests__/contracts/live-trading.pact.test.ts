import { Pact, Matchers } from '@pact-foundation/pact';
import path from 'path';

const { like, eachLike, term, iso8601DateTimeWithMillis } = Matchers;

describe('Live Trading API Pact Tests', () => {
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

  describe('POST /api/live/emergency-stop', () => {
    it('should execute emergency stop successfully', async () => {
      const emergencyStopRequest = {
        reason: 'Market volatility exceeds risk threshold',
        close_positions: true,
        cancel_orders: true,
        disable_trading: true
      };

      const expectedResponse = {
        success: like(true),
        status: like('emergency_stop_executed'),
        timestamp: iso8601DateTimeWithMillis(),
        actions_taken: {
          positions_closed: like(5),
          orders_cancelled: like(3),
          trading_disabled: like(true),
          notifications_sent: like(true)
        },
        positions_summary: eachLike({
          id: like('pos-001'),
          symbol: like('BTCUSDT'),
          side: term({
            matcher: 'long|short',
            generate: 'long'
          }),
          quantity: like(0.5),
          entry_price: like(42000),
          exit_price: like(41800),
          pnl: like(-100),
          close_reason: like('emergency_stop')
        }),
        orders_cancelled: eachLike({
          id: like('order-001'),
          symbol: like('BTCUSDT'),
          type: term({
            matcher: 'limit|market|stop_loss|take_profit',
            generate: 'limit'
          }),
          side: term({
            matcher: 'buy|sell',
            generate: 'buy'
          }),
          quantity: like(0.25),
          price: like(40000)
        }),
        system_state: {
          trading_enabled: like(false),
          risk_monitoring: like(true),
          auto_trading: like(false),
          manual_override: like(true)
        },
        audit_log: {
          id: like('audit-123'),
          action: like('EMERGENCY_STOP'),
          user: like('system'),
          reason: like('Market volatility exceeds risk threshold'),
          ip_address: like('192.168.1.1'),
          timestamp: iso8601DateTimeWithMillis()
        }
      };

      await provider.addInteraction({
        state: 'live trading is active',
        uponReceiving: 'an emergency stop request',
        withRequest: {
          method: 'POST',
          path: '/api/live/emergency-stop',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json'
          },
          body: emergencyStopRequest
        },
        willRespondWith: {
          status: 200,
          headers: {
            'Content-Type': 'application/json'
          },
          body: expectedResponse
        }
      });

      const response = await fetch('http://localhost:1234/api/live/emergency-stop', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json'
        },
        body: JSON.stringify(emergencyStopRequest)
      });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.status).toBe('emergency_stop_executed');
      expect(data.actions_taken).toBeDefined();
      expect(data.system_state.trading_enabled).toBe(false);
    });

    it('should handle emergency stop with no positions', async () => {
      const emergencyStopRequest = {
        reason: 'Precautionary stop',
        close_positions: true,
        cancel_orders: true,
        disable_trading: true
      };

      const expectedResponse = {
        success: like(true),
        status: like('emergency_stop_executed'),
        timestamp: iso8601DateTimeWithMillis(),
        actions_taken: {
          positions_closed: like(0),
          orders_cancelled: like(0),
          trading_disabled: like(true),
          notifications_sent: like(true)
        },
        message: like('No active positions or orders to close'),
        system_state: {
          trading_enabled: like(false),
          risk_monitoring: like(true),
          auto_trading: like(false),
          manual_override: like(true)
        }
      };

      await provider.addInteraction({
        state: 'no active positions',
        uponReceiving: 'an emergency stop request with no positions',
        withRequest: {
          method: 'POST',
          path: '/api/live/emergency-stop',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json'
          },
          body: emergencyStopRequest
        },
        willRespondWith: {
          status: 200,
          headers: {
            'Content-Type': 'application/json'
          },
          body: expectedResponse
        }
      });

      const response = await fetch('http://localhost:1234/api/live/emergency-stop', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json'
        },
        body: JSON.stringify(emergencyStopRequest)
      });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.actions_taken.positions_closed).toBe(0);
      expect(data.actions_taken.orders_cancelled).toBe(0);
    });

    it('should handle partial emergency stop', async () => {
      const partialStopRequest = {
        reason: 'Reduce exposure',
        close_positions: false,
        cancel_orders: true,
        disable_trading: false
      };

      const expectedResponse = {
        success: like(true),
        status: like('partial_stop_executed'),
        timestamp: iso8601DateTimeWithMillis(),
        actions_taken: {
          positions_closed: like(0),
          orders_cancelled: like(2),
          trading_disabled: like(false),
          notifications_sent: like(true)
        },
        orders_cancelled: eachLike({
          id: like('order-002'),
          symbol: like('ETHUSDT'),
          type: like('limit'),
          side: like('buy'),
          quantity: like(1.5),
          price: like(2200)
        }),
        system_state: {
          trading_enabled: like(true),
          risk_monitoring: like(true),
          auto_trading: like(true),
          manual_override: like(false)
        },
        warning: like('Partial stop executed. Active positions remain open.')
      };

      await provider.addInteraction({
        state: 'live trading is active',
        uponReceiving: 'a partial emergency stop request',
        withRequest: {
          method: 'POST',
          path: '/api/live/emergency-stop',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json'
          },
          body: partialStopRequest
        },
        willRespondWith: {
          status: 200,
          headers: {
            'Content-Type': 'application/json'
          },
          body: expectedResponse
        }
      });

      const response = await fetch('http://localhost:1234/api/live/emergency-stop', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json'
        },
        body: JSON.stringify(partialStopRequest)
      });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.status).toBe('partial_stop_executed');
      expect(data.system_state.trading_enabled).toBe(true);
      expect(data.warning).toBeDefined();
    });

    it('should handle emergency stop failure', async () => {
      const emergencyStopRequest = {
        reason: 'System failure',
        close_positions: true,
        cancel_orders: true,
        disable_trading: true
      };

      const expectedError = {
        success: like(false),
        error: like('Emergency stop failed'),
        code: like('EXCHANGE_CONNECTION_ERROR'),
        details: {
          message: like('Unable to connect to exchange API'),
          attempted_actions: {
            positions_to_close: like(3),
            orders_to_cancel: like(2),
            positions_closed: like(0),
            orders_cancelled: like(0)
          },
          fallback_action: like('Manual intervention required'),
          support_ticket: like('TICKET-12345')
        },
        timestamp: iso8601DateTimeWithMillis()
      };

      await provider.addInteraction({
        state: 'exchange connection lost',
        uponReceiving: 'an emergency stop request when exchange is down',
        withRequest: {
          method: 'POST',
          path: '/api/live/emergency-stop',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json'
          },
          body: emergencyStopRequest
        },
        willRespondWith: {
          status: 503,
          headers: {
            'Content-Type': 'application/json'
          },
          body: expectedError
        }
      });

      const response = await fetch('http://localhost:1234/api/live/emergency-stop', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json'
        },
        body: JSON.stringify(emergencyStopRequest)
      });
      const data = await response.json();

      expect(response.status).toBe(503);
      expect(data.success).toBe(false);
      expect(data.error).toBeDefined();
      expect(data.code).toBe('EXCHANGE_CONNECTION_ERROR');
      expect(data.details.fallback_action).toBeDefined();
    });
  });
});