# Contract Testing with Pact

This document describes the consumer-driven contract testing implementation using Pact for the Trading Bot system.

## Overview

Contract testing ensures that the frontend (consumer) and backend API (provider) maintain compatible interfaces. Any schema drift or breaking changes are caught early in the CI pipeline.

## Architecture

```
┌──────────────┐         ┌─────────────┐         ┌──────────────┐
│   Frontend   │ ──────> │ Pact Broker │ <────── │   Backend    │
│  (Consumer)  │         │             │         │  (Provider)  │
└──────────────┘         └─────────────┘         └──────────────┘
      │                         ▲                        │
      │                         │                        │
      └── Generates Pacts ─────┘                        │
                                                         │
                          Verifies Pacts ───────────────┘
```

## Contracts Covered

The following API endpoints have consumer contract tests:

### 1. Strategy Management
- `GET /api/strategy` - List all strategies
- `GET /api/strategy/{id}` - Get specific strategy
- `POST /api/strategy/publish` - Publish strategy to production

### 2. Backtesting
- `POST /api/backtest/run` - Run backtest (sync and async modes)
- Includes validation error scenarios

### 3. Live Trading
- `POST /api/live/emergency-stop` - Emergency stop with various scenarios:
  - Full stop with positions
  - Stop with no positions
  - Partial stop
  - Exchange failure handling

### 4. Risk Management
- `GET /api/risk/summary` - Risk metrics with states:
  - Normal risk levels
  - Critical risk with breaches
  - No positions
  - Filtered by account/strategy

## Local Development Setup

### 1. Start Pact Broker

```bash
# Start local Pact Broker with PostgreSQL
docker-compose -f docker-compose.pact.yml up -d

# Verify broker is running
curl -u pact:pact http://localhost:9292
```

### 2. Run Consumer Tests

```bash
cd web/frontend

# Install dependencies
npm install

# Run Pact consumer tests
npm run test:pact

# Tests will generate pact files in web/frontend/pacts/
```

### 3. Publish Pacts to Broker

```bash
# Publish to local broker
npm run pact:publish

# Or with environment variables
PACT_BROKER_URL=http://localhost:9292 \
PACT_BROKER_USERNAME=pact \
PACT_BROKER_PASSWORD=pact \
npm run pact:publish
```

### 4. Run Provider Verification

```bash
# From project root
cd /Users/park/tradingbot_v2

# Run provider tests
python -m pytest tests/contracts/test_pact_provider.py -v

# Or verify from broker
python scripts/verify_broker_pacts.py
```

## CI/CD Pipeline

The GitHub Actions workflow (`contract-tests.yml`) runs automatically on:
- Push to main/develop branches
- Pull requests to main
- Manual workflow dispatch

### Pipeline Stages

1. **Consumer Tests**
   - Runs Jest with Pact tests
   - Generates contract files
   - Uploads artifacts

2. **Provider Verification**
   - Sets up test database
   - Downloads pact artifacts
   - Verifies API compliance

3. **Can I Deploy**
   - Checks if versions are compatible
   - Prevents breaking deployments

4. **Schema Drift Detection** (PRs only)
   - Compares contracts between branches
   - Comments on PR with changes

## Writing New Contract Tests

### Consumer Side (Frontend)

```typescript
// src/__tests__/contracts/example.pact.test.ts
import { Pact, Matchers } from '@pact-foundation/pact';

describe('Example API Pact Tests', () => {
  const provider = new Pact({
    consumer: 'TradingBotUI',
    provider: 'TradingBotAPI',
    // ... configuration
  });

  it('should handle example request', async () => {
    await provider.addInteraction({
      state: 'example state exists',
      uponReceiving: 'a request for example',
      withRequest: {
        method: 'GET',
        path: '/api/example',
      },
      willRespondWith: {
        status: 200,
        body: Matchers.like({
          id: 'example-001',
          value: 42
        })
      }
    });
    
    // Make request and verify
  });
});
```

### Provider Side (Backend)

```python
# tests/contracts/test_pact_provider.py
def _setup_example_state(self):
    """Setup provider state for example."""
    with patch('src.application.use_cases.ExampleUseCase.execute') as mock:
        mock.return_value = {
            "id": "example-001",
            "value": 42
        }
```

## Matchers Reference

Pact provides flexible matchers for contract testing:

- `like(value)` - Type matching
- `eachLike(template)` - Array of similar objects
- `term({matcher, generate})` - Regex matching
- `iso8601DateTimeWithMillis()` - ISO datetime format
- `integer()`, `decimal()` - Number types
- `boolean()` - Boolean values

## Environment Variables

### Consumer (Frontend)
```bash
PACT_BROKER_URL=http://localhost:9292
PACT_BROKER_USERNAME=pact
PACT_BROKER_PASSWORD=pact
GIT_BRANCH=main
```

### Provider (Backend)
```bash
PACT_BROKER_URL=http://localhost:9292
PACT_BROKER_USERNAME=pact
PACT_BROKER_PASSWORD=pact
GIT_COMMIT=$(git rev-parse --short HEAD)
DATABASE_URL=postgresql://user:pass@localhost/db
```

## Troubleshooting

### Common Issues

1. **Pact files not generated**
   - Check test output for errors
   - Ensure `pacts/` directory exists
   - Verify mock server is starting

2. **Broker connection failed**
   - Check broker is running: `docker ps`
   - Verify credentials
   - Check network connectivity

3. **Provider verification fails**
   - Ensure all provider states are implemented
   - Check database fixtures
   - Verify mock responses match contract

4. **Can't deploy check fails**
   - Ensure both consumer and provider versions are published
   - Check version tags match branch
   - Verify all contracts are satisfied

### Debug Commands

```bash
# View broker logs
docker logs pact-broker

# Check PostgreSQL
docker exec -it pact-postgres psql -U pact -d pact

# List all pacts
curl -u pact:pact http://localhost:9292/pacts/latest

# Get specific pact
curl -u pact:pact \
  http://localhost:9292/pacts/provider/TradingBotAPI/consumer/TradingBotUI/latest

# Verify specific interaction
npm run test:pact -- --testNamePattern="should return list of strategies"
```

## Best Practices

1. **Provider States**
   - Keep states simple and focused
   - Use descriptive state names
   - Avoid complex state dependencies

2. **Contract Design**
   - Focus on critical fields only
   - Use flexible matchers
   - Avoid over-specification

3. **Version Management**
   - Use semantic versioning
   - Tag with environment (dev/staging/prod)
   - Track breaking changes

4. **Testing Strategy**
   - Run contracts in CI/CD
   - Verify before deployment
   - Monitor contract compliance

## Breaking Changes Process

When introducing breaking API changes:

1. **Backwards Compatible (Preferred)**
   - Add new fields (optional)
   - Create new endpoints
   - Deprecate old versions gradually

2. **Breaking Change Required**
   - Update consumer tests first
   - Version the API endpoint
   - Coordinate deployment
   - Use feature flags if needed

## Monitoring

Monitor contract testing health:

- Pact Broker dashboard: http://localhost:9292
- CI pipeline status
- Can-i-deploy results
- Verification success rate

## Resources

- [Pact Documentation](https://docs.pact.io/)
- [Pact JS](https://github.com/pact-foundation/pact-js)
- [Pact Python](https://github.com/pact-foundation/pact-python)
- [Contract Testing Best Practices](https://docs.pact.io/best_practices)