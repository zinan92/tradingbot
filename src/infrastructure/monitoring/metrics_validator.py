"""
Metrics validator for ensuring deterministic test results.

Validates that metrics are identical across multiple test runs.
"""

import json
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class MetricsValidator:
    """
    Validates metrics consistency across test runs.
    
    Ensures deterministic behavior by comparing metrics hashes and values.
    """
    
    def __init__(self, tolerance: float = 0.0):
        """
        Initialize metrics validator.
        
        Args:
            tolerance: Allowed tolerance for floating point comparisons (0 = exact match)
        """
        self.tolerance = tolerance
        self.validation_history: List[Dict[str, Any]] = []
    
    def validate_metrics(
        self,
        metrics1: Dict[str, Any],
        metrics2: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate two sets of metrics are identical.
        
        Args:
            metrics1: First metrics set
            metrics2: Second metrics set
            
        Returns:
            Tuple of (is_valid, list_of_differences)
        """
        differences = []
        
        # Check keys match
        keys1 = set(metrics1.keys())
        keys2 = set(metrics2.keys())
        
        missing_in_2 = keys1 - keys2
        missing_in_1 = keys2 - keys1
        
        if missing_in_2:
            differences.append(f"Keys missing in second set: {missing_in_2}")
        if missing_in_1:
            differences.append(f"Keys missing in first set: {missing_in_1}")
        
        # Compare common keys
        common_keys = keys1 & keys2
        
        for key in common_keys:
            val1 = metrics1[key]
            val2 = metrics2[key]
            
            if not self._values_equal(val1, val2):
                differences.append(
                    f"{key}: {val1} != {val2} (diff: {self._calculate_diff(val1, val2)})"
                )
        
        # Record validation
        validation_result = {
            "timestamp": datetime.now().isoformat(),
            "valid": len(differences) == 0,
            "differences": differences,
            "hash1": self.calculate_hash(metrics1),
            "hash2": self.calculate_hash(metrics2)
        }
        
        self.validation_history.append(validation_result)
        
        return len(differences) == 0, differences
    
    def _values_equal(self, val1: Any, val2: Any) -> bool:
        """Check if two values are equal within tolerance."""
        # Handle None
        if val1 is None and val2 is None:
            return True
        if val1 is None or val2 is None:
            return False
        
        # Handle different types
        if type(val1) != type(val2):
            return False
        
        # Handle numbers
        if isinstance(val1, (int, float, Decimal)):
            if self.tolerance > 0:
                return abs(float(val1) - float(val2)) <= self.tolerance
            else:
                return val1 == val2
        
        # Handle other types
        return val1 == val2
    
    def _calculate_diff(self, val1: Any, val2: Any) -> str:
        """Calculate difference between values."""
        try:
            if isinstance(val1, (int, float, Decimal)) and isinstance(val2, (int, float, Decimal)):
                diff = float(val1) - float(val2)
                if val2 != 0:
                    percent = (diff / float(val2)) * 100
                    return f"{diff:.6f} ({percent:.2f}%)"
                else:
                    return f"{diff:.6f}"
        except:
            pass
        
        return "N/A"
    
    def calculate_hash(self, metrics: Dict[str, Any]) -> str:
        """
        Calculate deterministic hash of metrics.
        
        Args:
            metrics: Metrics dictionary
            
        Returns:
            SHA256 hash (truncated to 16 chars)
        """
        # Convert to JSON with sorted keys
        normalized = self._normalize_metrics(metrics)
        json_str = json.dumps(normalized, sort_keys=True, separators=(',', ':'))
        
        # Calculate hash
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]
    
    def _normalize_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize metrics for consistent hashing."""
        normalized = {}
        
        for key, value in metrics.items():
            if isinstance(value, (float, Decimal)):
                # Round floats to consistent precision
                normalized[key] = round(float(value), 10)
            elif isinstance(value, dict):
                # Recursively normalize nested dicts
                normalized[key] = self._normalize_metrics(value)
            elif isinstance(value, list):
                # Normalize lists
                normalized[key] = [
                    self._normalize_value(item) for item in value
                ]
            else:
                normalized[key] = value
        
        return normalized
    
    def _normalize_value(self, value: Any) -> Any:
        """Normalize a single value."""
        if isinstance(value, (float, Decimal)):
            return round(float(value), 10)
        elif isinstance(value, dict):
            return self._normalize_metrics(value)
        return value
    
    def validate_metrics_file(
        self,
        file1: Path,
        file2: Path
    ) -> Tuple[bool, List[str]]:
        """
        Validate metrics from two files.
        
        Args:
            file1: Path to first metrics file
            file2: Path to second metrics file
            
        Returns:
            Tuple of (is_valid, list_of_differences)
        """
        # Load metrics
        with open(file1, 'r') as f:
            metrics1 = json.load(f)
        
        with open(file2, 'r') as f:
            metrics2 = json.load(f)
        
        return self.validate_metrics(metrics1, metrics2)
    
    def validate_multiple_runs(
        self,
        metrics_list: List[Dict[str, Any]]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate metrics across multiple runs.
        
        Args:
            metrics_list: List of metrics from multiple runs
            
        Returns:
            Tuple of (all_identical, validation_summary)
        """
        if len(metrics_list) < 2:
            return True, {"message": "Need at least 2 runs to compare"}
        
        # Calculate hashes
        hashes = [self.calculate_hash(m) for m in metrics_list]
        unique_hashes = set(hashes)
        
        # Check if all identical
        all_identical = len(unique_hashes) == 1
        
        # Find differences
        all_differences = []
        for i in range(len(metrics_list) - 1):
            valid, diffs = self.validate_metrics(
                metrics_list[i],
                metrics_list[i + 1]
            )
            if not valid:
                all_differences.append({
                    "run1": i,
                    "run2": i + 1,
                    "differences": diffs
                })
        
        # Create summary
        summary = {
            "total_runs": len(metrics_list),
            "unique_results": len(unique_hashes),
            "all_identical": all_identical,
            "hashes": hashes,
            "differences": all_differences
        }
        
        return all_identical, summary
    
    def generate_report(self, output_path: Optional[Path] = None) -> str:
        """
        Generate validation report.
        
        Args:
            output_path: Optional path to save report
            
        Returns:
            Report as string
        """
        report_lines = [
            "=" * 60,
            "METRICS VALIDATION REPORT",
            "=" * 60,
            f"Generated: {datetime.now().isoformat()}",
            f"Total Validations: {len(self.validation_history)}",
            ""
        ]
        
        # Summary
        valid_count = sum(1 for v in self.validation_history if v["valid"])
        invalid_count = len(self.validation_history) - valid_count
        
        report_lines.extend([
            "SUMMARY:",
            f"  Valid: {valid_count}",
            f"  Invalid: {invalid_count}",
            f"  Success Rate: {(valid_count / len(self.validation_history) * 100):.1f}%"
            if self.validation_history else "N/A",
            ""
        ])
        
        # Detailed results
        if invalid_count > 0:
            report_lines.extend([
                "FAILED VALIDATIONS:",
                "-" * 40
            ])
            
            for i, validation in enumerate(self.validation_history):
                if not validation["valid"]:
                    report_lines.extend([
                        f"\nValidation #{i + 1}:",
                        f"  Time: {validation['timestamp']}",
                        f"  Hash1: {validation['hash1']}",
                        f"  Hash2: {validation['hash2']}",
                        "  Differences:"
                    ])
                    
                    for diff in validation["differences"][:10]:  # Limit to 10
                        report_lines.append(f"    - {diff}")
                    
                    if len(validation["differences"]) > 10:
                        report_lines.append(
                            f"    ... and {len(validation['differences']) - 10} more"
                        )
        
        report = "\n".join(report_lines)
        
        # Save if path provided
        if output_path:
            with open(output_path, 'w') as f:
                f.write(report)
            logger.info(f"Report saved to {output_path}")
        
        return report


class MetricsComparator:
    """
    Advanced metrics comparison with statistical analysis.
    """
    
    def __init__(self):
        self.validator = MetricsValidator()
    
    def compare_strategies(
        self,
        strategy_results: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Compare metrics across different strategies.
        
        Args:
            strategy_results: Dict mapping strategy names to lists of run results
            
        Returns:
            Comparison summary
        """
        comparison = {
            "strategies": list(strategy_results.keys()),
            "determinism": {},
            "performance": {},
            "consistency": {}
        }
        
        # Check determinism for each strategy
        for strategy, runs in strategy_results.items():
            if len(runs) > 1:
                is_deterministic, summary = self.validator.validate_multiple_runs(
                    [run["metrics"] for run in runs]
                )
                comparison["determinism"][strategy] = {
                    "is_deterministic": is_deterministic,
                    "unique_results": summary["unique_results"],
                    "total_runs": summary["total_runs"]
                }
            
            # Calculate average performance
            if runs:
                avg_metrics = self._calculate_average_metrics(
                    [run["metrics"] for run in runs]
                )
                comparison["performance"][strategy] = avg_metrics
        
        return comparison
    
    def _calculate_average_metrics(
        self,
        metrics_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate average metrics across runs."""
        if not metrics_list:
            return {}
        
        # Aggregate numerical metrics
        aggregated = {}
        
        for metrics in metrics_list:
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    if key not in aggregated:
                        aggregated[key] = []
                    aggregated[key].append(value)
        
        # Calculate averages
        averages = {}
        for key, values in aggregated.items():
            averages[key] = {
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "std": self._calculate_std(values)
            }
        
        return averages
    
    def _calculate_std(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance ** 0.5