# Dashboard Risk/Ops Wiring - Implementation Guide

## Overview
This implementation adds comprehensive dashboard monitoring and risk management features to the existing Next.js trading UI, integrating with backend health and risk endpoints.

## Setup Instructions

### 1. Environment Configuration

Copy the sample environment file and configure your API URL:
```bash
cp .env.local.sample .env.local
```

Edit `.env.local` and set your API base URL:
```
VITE_API_BASE_URL=http://localhost:8000
```

For production deployments, use your actual API domain.

### 2. Install Dependencies

Ensure all dependencies are installed:
```bash
npm install
```

### 3. Run Development Server

Start the development server:
```bash
npm run dev
```

The application will be available at `http://localhost:5173` (or the port shown in terminal).

## Running Tests

Run all tests:
```bash
npm test
```

Run specific test suites:
```bash
npm test dashboard.health-tiles
npm test dashboard.risk-panel  
npm test dashboard.positions
```

Run tests in watch mode:
```bash
npm test -- --watch
```

## Configuration

### Lag/Color Thresholds

Module health color thresholds are defined in:
- `src/components/Dashboard.tsx` - `HEALTH_THRESHOLDS` constant
- `src/components/MonitoringTab.tsx` - `HEALTH_THRESHOLDS` constant

Current thresholds:
- **Green**: status='ok' AND lag ≤ 30 seconds
- **Yellow**: status='degraded' OR lag 31-120 seconds  
- **Red**: status='down' OR lag > 120 seconds

To adjust thresholds, modify the constants:
```typescript
const HEALTH_THRESHOLDS = {
  LAG_WARNING: 30,   // Yellow threshold (seconds)
  LAG_CRITICAL: 120  // Red threshold (seconds)
} as const;
```

### API Timeout

The API client timeout is set to 8 seconds. To modify:
- Edit `src/services/api.ts` - `TIMEOUT_MS` property

### Polling Intervals

- Dashboard health/risk data: 10 seconds
- Live positions: 5 seconds  
- Module monitoring: 10 seconds

To adjust polling intervals, modify the `setInterval` calls in respective components.

## Key Features Implemented

### 1. Dashboard Tab (`src/components/Dashboard.tsx`)
- **Health Tiles**: Visual module status with color coding
- **Risk Panel**: Exposure, daily loss, and drawdown metrics with thresholds
- **Live Positions Table**: Real-time position tracking with P&L
- **CSV Export**: Client-side CSV generation for positions
- **Control Actions**: Pause, Stop, and Close All positions with confirmation dialog

### 2. API Service Extensions (`src/services/api.ts`)
- Added health monitoring endpoints with AbortController support
- 8-second timeout for all requests
- Request deduplication by key
- Environment-based API URL configuration

### 3. Live Trading Tab (`src/components/LiveTradingTab.tsx`)
- Compact positions list with auto-refresh
- Position summary statistics
- CSV export functionality

### 4. Monitoring Tab (`src/components/MonitoringTab.tsx`)
- Detailed module health cards
- System summary statistics
- Last success timestamps and lag display

### 5. Utility Functions
- **CSV Helper** (`src/lib/csv.ts`): CSV generation and download
- **Dialog Component** (`src/components/ui/dialog.tsx`): Confirmation dialogs

## API Endpoints Used

All endpoints are prefixed with `VITE_API_BASE_URL`:

- `GET /api/health/summary` - Module health status
- `GET /api/risk/summary` - Risk metrics and thresholds
- `GET /api/live/positions` - Current live positions
- `GET /api/live/orders` - Current orders (prepared for future use)
- `POST /api/live/pause` - Pause live trading
- `POST /api/live/stop` - Stop live trading
- `POST /api/live/close-all` - Close all positions with confirmation

## Error Handling

- **Soft Failures**: API errors show a warning banner but keep previous data
- **Request Timeouts**: 8-second timeout with automatic abort
- **Empty States**: Graceful "No data" messages for empty responses
- **Toast Notifications**: Success/error feedback for user actions

## Type Safety

All API responses are strongly typed:
- `src/types/health.ts` - Health and monitoring types
- `src/types/index.ts` - Existing trading types

## Browser Compatibility

- Modern browsers with ES6+ support
- Requires fetch API support
- Tested on Chrome, Firefox, Safari, Edge

## Production Considerations

1. **API Authentication**: Add authentication headers if required
2. **CORS**: Ensure backend allows frontend origin
3. **HTTPS**: Use HTTPS in production for API calls
4. **Rate Limiting**: Consider implementing client-side rate limiting
5. **Error Tracking**: Integrate error tracking service (e.g., Sentry)
6. **Performance**: Consider React.memo for heavy components

## Troubleshooting

### API Connection Issues
- Verify `VITE_API_BASE_URL` is correct
- Check backend is running and accessible
- Verify CORS headers on backend
- Check browser console for network errors

### Test Failures
- Ensure all mocks are properly configured
- Clear jest cache: `npm test -- --clearCache`
- Check for async timing issues in tests

### Build Issues
- Clear node_modules and reinstall: `rm -rf node_modules && npm install`
- Check TypeScript errors: `npm run type-check`
- Verify all imports are correct

## Future Enhancements

- WebSocket support for real-time updates
- Chart visualizations for metrics
- Historical data comparison
- Alert configuration UI
- Mobile responsive improvements