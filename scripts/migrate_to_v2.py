#!/usr/bin/env python3
"""
Migration script for transitioning from binance_v1 to binance_v2 adapter.

Implements a gradual rollout strategy with health monitoring and rollback capability.
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.config.feature_flags import (
    FeatureFlagManager, ExecutionImplementation, Environment
)
from src.infrastructure.exchange.adapter_factory import (
    get_adapter_factory, AdapterHealthMonitor
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AdapterMigration:
    """
    Manages the migration from v1 to v2 adapter.
    
    Phases:
    1. Testnet deployment (100% v2)
    2. Production canary (10% v2)
    3. Production gradual rollout (10% -> 50% -> 100%)
    4. Cleanup and v1 removal
    """
    
    def __init__(self, environment: Environment):
        self.environment = environment
        self.feature_flags = FeatureFlagManager(environment=environment.value)
        self.factory = get_adapter_factory()
        self.health_monitor = AdapterHealthMonitor()
        self.migration_state = self._load_migration_state()
    
    def _load_migration_state(self) -> Dict[str, Any]:
        """Load migration state from file."""
        state_file = Path("migration_state.json")
        if state_file.exists():
            with open(state_file, 'r') as f:
                return json.load(f)
        
        return {
            "phase": "not_started",
            "started_at": None,
            "testnet_deployed_at": None,
            "production_canary_at": None,
            "production_complete_at": None,
            "rollback_count": 0,
            "health_checks": []
        }
    
    def _save_migration_state(self):
        """Save migration state to file."""
        with open("migration_state.json", 'w') as f:
            json.dump(self.migration_state, f, indent=2)
    
    async def start_migration(self):
        """Start the migration process."""
        logger.info(f"Starting migration in {self.environment.value} environment")
        
        self.migration_state["phase"] = "started"
        self.migration_state["started_at"] = datetime.now().isoformat()
        self._save_migration_state()
        
        if self.environment == Environment.TESTNET:
            await self._deploy_to_testnet()
        elif self.environment == Environment.PRODUCTION:
            await self._deploy_to_production()
        else:
            logger.warning(f"Migration not supported for {self.environment.value}")
    
    async def _deploy_to_testnet(self):
        """Deploy v2 to testnet (100% traffic)."""
        logger.info("Deploying binance_v2 to testnet")
        
        # Set feature flag to v2
        self.feature_flags.set("EXECUTION_IMPL", ExecutionImplementation.BINANCE_V2.value)
        self.feature_flags.enable("EXECUTION_IMPL", rollout_percentage=100.0)
        
        # Save configuration
        self.feature_flags.save_config()
        
        # Test connection
        adapter = await self.factory.get_adapter()
        if adapter.get_adapter_name() != "binance_v2":
            raise Exception("Failed to switch to v2 adapter")
        
        self.migration_state["phase"] = "testnet_deployed"
        self.migration_state["testnet_deployed_at"] = datetime.now().isoformat()
        self._save_migration_state()
        
        logger.info("Successfully deployed v2 to testnet")
        
        # Start monitoring
        await self._monitor_health(duration_hours=48)
    
    async def _deploy_to_production(self):
        """Deploy v2 to production with gradual rollout."""
        logger.info("Starting production deployment")
        
        # Check if testnet was successful
        if self.migration_state["phase"] != "testnet_validated":
            logger.error("Testnet validation required before production deployment")
            return
        
        # Phase 1: Canary deployment (10%)
        await self._deploy_canary()
        
        # Phase 2: Gradual rollout
        await self._gradual_rollout()
        
        # Phase 3: Complete migration
        await self._complete_migration()
    
    async def _deploy_canary(self):
        """Deploy canary release (10% of traffic)."""
        logger.info("Deploying canary release (10% traffic)")
        
        self.feature_flags.set("EXECUTION_IMPL", ExecutionImplementation.BINANCE_V2.value)
        self.feature_flags.enable("EXECUTION_IMPL", rollout_percentage=10.0)
        self.feature_flags.save_config()
        
        self.migration_state["phase"] = "production_canary"
        self.migration_state["production_canary_at"] = datetime.now().isoformat()
        self._save_migration_state()
        
        # Monitor for 6 hours
        healthy = await self._monitor_health(duration_hours=6)
        
        if not healthy:
            logger.error("Canary deployment unhealthy, rolling back")
            await self.rollback()
    
    async def _gradual_rollout(self):
        """Gradually increase traffic to v2."""
        rollout_percentages = [25, 50, 75, 100]
        
        for percentage in rollout_percentages:
            logger.info(f"Increasing v2 traffic to {percentage}%")
            
            self.feature_flags.enable("EXECUTION_IMPL", rollout_percentage=float(percentage))
            self.feature_flags.save_config()
            
            # Monitor for 2 hours at each level
            healthy = await self._monitor_health(duration_hours=2)
            
            if not healthy:
                logger.error(f"Unhealthy at {percentage}%, rolling back")
                await self.rollback()
                return
            
            logger.info(f"Successfully running at {percentage}%")
    
    async def _complete_migration(self):
        """Complete the migration."""
        logger.info("Completing migration to v2")
        
        self.migration_state["phase"] = "completed"
        self.migration_state["production_complete_at"] = datetime.now().isoformat()
        self._save_migration_state()
        
        logger.info("Migration completed successfully!")
        
        # Schedule v1 cleanup for later
        logger.info("V1 adapter can be removed after 7 days if stable")
    
    async def _monitor_health(self, duration_hours: int) -> bool:
        """
        Monitor adapter health for specified duration.
        
        Returns True if healthy throughout period.
        """
        logger.info(f"Monitoring health for {duration_hours} hours")
        
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=duration_hours)
        check_interval = 60  # Check every minute
        
        unhealthy_count = 0
        max_unhealthy = 5  # Allow up to 5 unhealthy checks
        
        while datetime.now() < end_time:
            # Get current adapter
            adapter = await self.factory.get_adapter()
            self.health_monitor.register_adapter(adapter)
            
            # Check health
            health_results = await self.health_monitor.check_health()
            adapter_name = adapter.get_adapter_name()
            
            if adapter_name in health_results:
                health = health_results[adapter_name]
                
                # Log health check
                self.migration_state["health_checks"].append({
                    "timestamp": datetime.now().isoformat(),
                    "adapter": adapter_name,
                    "status": health["status"],
                    "details": health.get("details", {})
                })
                
                # Keep only last 1000 health checks
                if len(self.migration_state["health_checks"]) > 1000:
                    self.migration_state["health_checks"] = self.migration_state["health_checks"][-1000:]
                
                self._save_migration_state()
                
                if health["status"] != "healthy":
                    unhealthy_count += 1
                    logger.warning(f"Unhealthy status detected: {health}")
                    
                    if unhealthy_count > max_unhealthy:
                        logger.error("Too many unhealthy checks, failing health monitoring")
                        return False
                else:
                    # Reset counter on healthy check
                    unhealthy_count = 0
                
                # Log progress
                elapsed = datetime.now() - start_time
                remaining = end_time - datetime.now()
                logger.info(
                    f"Health check: {health['status']} "
                    f"(elapsed: {elapsed}, remaining: {remaining})"
                )
            
            await asyncio.sleep(check_interval)
        
        logger.info("Health monitoring completed successfully")
        return True
    
    async def rollback(self):
        """Rollback to v1 adapter."""
        logger.warning("Rolling back to binance_v1")
        
        self.feature_flags.set("EXECUTION_IMPL", ExecutionImplementation.BINANCE_V1.value)
        self.feature_flags.enable("EXECUTION_IMPL", rollout_percentage=100.0)
        self.feature_flags.save_config()
        
        self.migration_state["rollback_count"] += 1
        self.migration_state["phase"] = "rolled_back"
        self._save_migration_state()
        
        logger.info("Rollback completed")
    
    async def validate_testnet(self):
        """Validate testnet deployment before production."""
        if self.migration_state["phase"] != "testnet_deployed":
            logger.error("Testnet not deployed yet")
            return False
        
        # Check health history
        recent_checks = [
            check for check in self.migration_state["health_checks"]
            if check["adapter"] == "binance_v2"
        ][-100:]  # Last 100 checks
        
        if not recent_checks:
            logger.error("No health checks found for v2")
            return False
        
        # Calculate success rate
        healthy_count = sum(1 for check in recent_checks if check["status"] == "healthy")
        success_rate = (healthy_count / len(recent_checks)) * 100
        
        logger.info(f"Testnet validation: {success_rate:.2f}% healthy")
        
        if success_rate >= 95:  # 95% success rate required
            self.migration_state["phase"] = "testnet_validated"
            self._save_migration_state()
            logger.info("Testnet validated successfully")
            return True
        else:
            logger.error(f"Testnet validation failed: {success_rate:.2f}% < 95%")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current migration status."""
        return {
            "environment": self.environment.value,
            "phase": self.migration_state["phase"],
            "current_implementation": self.feature_flags.get("EXECUTION_IMPL"),
            "rollout_percentage": self.feature_flags.flags.get(
                "EXECUTION_IMPL", {}
            ).rollout_percentage if "EXECUTION_IMPL" in self.feature_flags.flags else 0,
            "rollback_count": self.migration_state["rollback_count"],
            "started_at": self.migration_state["started_at"],
            "health_check_count": len(self.migration_state["health_checks"])
        }


async def main():
    """Main migration entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate to binance_v2 adapter")
    parser.add_argument(
        "--environment",
        choices=["testnet", "staging", "production"],
        required=True,
        help="Target environment"
    )
    parser.add_argument(
        "--action",
        choices=["start", "validate", "rollback", "status"],
        required=True,
        help="Migration action"
    )
    
    args = parser.parse_args()
    
    # Map environment string to enum
    env_map = {
        "testnet": Environment.TESTNET,
        "staging": Environment.STAGING,
        "production": Environment.PRODUCTION
    }
    environment = env_map[args.environment]
    
    # Create migration manager
    migration = AdapterMigration(environment)
    
    # Execute action
    if args.action == "start":
        await migration.start_migration()
    elif args.action == "validate":
        result = await migration.validate_testnet()
        print(f"Validation {'passed' if result else 'failed'}")
    elif args.action == "rollback":
        await migration.rollback()
    elif args.action == "status":
        status = migration.get_status()
        print(json.dumps(status, indent=2))
    
    # Cleanup
    await migration.factory.cleanup()


if __name__ == "__main__":
    asyncio.run(main())