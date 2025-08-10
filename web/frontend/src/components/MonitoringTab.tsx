import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { api } from '@/services/api';
import { HealthSummary, ModuleHealth } from '@/types/health';

const HEALTH_THRESHOLDS = {
  LAG_WARNING: 30,
  LAG_CRITICAL: 120
} as const;

export default function MonitoringTab() {
  const [healthSummary, setHealthSummary] = useState<HealthSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const fetchHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getHealthSummary();
      setHealthSummary(data);
      setLastUpdate(new Date());
    } catch (err: any) {
      setError(err.message || 'Failed to fetch health data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  const getModuleStatus = (module: ModuleHealth): { 
    color: string; 
    text: string; 
    badge: "default" | "secondary" | "destructive" | "outline" 
  } => {
    if (module.status === 'down') {
      return { color: 'text-red-500', text: 'Down', badge: 'destructive' };
    }
    if (module.status === 'degraded') {
      return { color: 'text-yellow-500', text: 'Degraded', badge: 'secondary' };
    }
    if (module.lag_seconds > HEALTH_THRESHOLDS.LAG_CRITICAL) {
      return { color: 'text-red-500', text: 'Critical Lag', badge: 'destructive' };
    }
    if (module.lag_seconds > HEALTH_THRESHOLDS.LAG_WARNING) {
      return { color: 'text-yellow-500', text: 'High Lag', badge: 'secondary' };
    }
    return { color: 'text-green-500', text: 'Healthy', badge: 'default' };
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const formatLag = (seconds: number): string => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>System Monitoring</CardTitle>
              <CardDescription>
                Module health status and performance metrics
              </CardDescription>
            </div>
            <div className="text-sm text-muted-foreground">
              Last updated: {lastUpdate.toLocaleTimeString()}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="text-red-500 text-sm mb-4">
              Error: {error}
            </div>
          )}
          
          {loading && !healthSummary ? (
            <div className="text-center py-8 text-muted-foreground">
              Loading health data...
            </div>
          ) : healthSummary ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {healthSummary.modules.map((module) => {
                const status = getModuleStatus(module);
                return (
                  <Card key={module.name}>
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-sm font-medium capitalize">
                          {module.name.replace(/_/g, ' ')}
                        </CardTitle>
                        <Badge variant={status.badge}>
                          {status.text}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Status:</span>
                        <span className={status.color}>
                          {module.status.toUpperCase()}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Lag:</span>
                        <span className={
                          module.lag_seconds > HEALTH_THRESHOLDS.LAG_WARNING 
                            ? 'text-yellow-500' 
                            : ''
                        }>
                          {formatLag(module.lag_seconds)}
                        </span>
                      </div>
                      <div className="text-xs text-muted-foreground mt-2">
                        Last success: {formatTimestamp(module.last_success_ts)}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              No health data available
            </div>
          )}
        </CardContent>
      </Card>

      {/* System Summary */}
      {healthSummary && (
        <Card>
          <CardHeader>
            <CardTitle>System Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Total Modules</p>
                <p className="text-2xl font-bold">{healthSummary.modules.length}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Healthy</p>
                <p className="text-2xl font-bold text-green-500">
                  {healthSummary.modules.filter(m => 
                    m.status === 'ok' && m.lag_seconds <= HEALTH_THRESHOLDS.LAG_WARNING
                  ).length}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Warning</p>
                <p className="text-2xl font-bold text-yellow-500">
                  {healthSummary.modules.filter(m => 
                    m.status === 'degraded' || 
                    (m.lag_seconds > HEALTH_THRESHOLDS.LAG_WARNING && 
                     m.lag_seconds <= HEALTH_THRESHOLDS.LAG_CRITICAL)
                  ).length}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Critical</p>
                <p className="text-2xl font-bold text-red-500">
                  {healthSummary.modules.filter(m => 
                    m.status === 'down' || m.lag_seconds > HEALTH_THRESHOLDS.LAG_CRITICAL
                  ).length}
                </p>
              </div>
            </div>
            
            <div className="mt-4 pt-4 border-t">
              <p className="text-xs text-muted-foreground">
                Report generated: {formatTimestamp(healthSummary.generated_at)}
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}