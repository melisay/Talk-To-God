from asyncio import iscoroutinefunction
from time import time
from json import dumps
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Callable, TypeVar
from datetime import datetime, timezone
from pathlib import Path
import logging
from .utils import logger

@dataclass
class OperationMetrics:
    operation: str
    start_time: float
    end_time: float
    duration: float
    success: bool
    error: Optional[str] = None
    metadata: Optional[Dict] = None

class PerformanceMonitor:
    def __init__(self):
        self.metrics: List[OperationMetrics] = []
        self.current_operation: Optional[OperationMetrics] = None
        self.log_file = Path("logs/performance.log")
        self.log_file.parent.mkdir(exist_ok=True)
        
    def start_operation(self, operation: str, metadata: Optional[Dict] = None) -> None:
        """Start timing an operation."""
        self.current_operation = OperationMetrics(
            operation=operation,
            start_time=time(),
            end_time=0.0,
            duration=0.0,
            success=False,
            metadata=metadata
        )
        
    def end_operation(self, success: bool = True, error: Optional[str] = None) -> None:
        """End timing an operation and record metrics."""
        if not self.current_operation:
            return
            
        self.current_operation.end_time = time()
        self.current_operation.duration = self.current_operation.end_time - self.current_operation.start_time
        self.current_operation.success = success
        self.current_operation.error = error
        
        # Log the metrics
        self._log_metrics(self.current_operation)
        self.metrics.append(self.current_operation)
        self.current_operation = None
        
    def _log_metrics(self, metrics: OperationMetrics) -> None:
        """Log metrics to file and console."""
        timestamp = datetime.fromtimestamp(metrics.start_time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
        log_entry = {
            "timestamp": timestamp,
            "operation": metrics.operation,
            "duration": f"{metrics.duration:.3f}s",
            "success": metrics.success,
            "error": metrics.error,
            "metadata": metrics.metadata
        }
        
        # Log to file with proper indentation
        with open(self.log_file, "a") as f:
            f.write(dumps(log_entry, indent=2) + "\n")
        
        # Log to console with color
        status_color = "\033[92m" if metrics.success else "\033[91m"  # Green for success, Red for failure
        reset_color = "\033[0m"
        
        console_msg = (
            f"{status_color}[{timestamp}] {metrics.operation}: {metrics.duration:.3f}s"
            f"{f' (Error: {metrics.error})' if metrics.error else ''}{reset_color}"
        )
        if metrics.metadata:
            console_msg += f"\nMetadata: {dumps(metrics.metadata, indent=2)}"
        
        print(console_msg)
        
    def get_operation_stats(self, operation: str) -> Dict:
        """Get statistics for a specific operation type."""
        relevant_metrics = [m for m in self.metrics if m.operation == operation]
        if not relevant_metrics:
            return {}
            
        durations = [m.duration for m in relevant_metrics]
        return {
            "count": len(relevant_metrics),
            "avg_duration": sum(durations) / len(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "success_rate": sum(1 for m in relevant_metrics if m.success) / len(relevant_metrics)
        }
        
    def print_summary(self) -> None:
        """Print a summary of all operations."""
        print("\n=== Performance Summary ===")
        operations = set(m.operation for m in self.metrics)
        for op in sorted(operations):
            stats = self.get_operation_stats(op)
            if stats:
                print(f"\n{op}:")
                print(f"  Count: {stats['count']}")
                print(f"  Avg Duration: {stats['avg_duration']:.3f}s")
                print(f"  Min Duration: {stats['min_duration']:.3f}s")
                print(f"  Max Duration: {stats['max_duration']:.3f}s")
                print(f"  Success Rate: {stats['success_rate']*100:.1f}%")

# Create global instance
performance_monitor = PerformanceMonitor()

def monitor_operation(operation: str, metadata: Optional[Dict] = None):
    """Decorator to monitor operation performance."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            performance_monitor.start_operation(operation, metadata)
            try:
                result = await func(*args, **kwargs)
                performance_monitor.end_operation(success=True)
                return result
            except Exception as e:
                performance_monitor.end_operation(success=False, error=str(e))
                raise
                
        def sync_wrapper(*args, **kwargs):
            performance_monitor.start_operation(operation, metadata)
            try:
                result = func(*args, **kwargs)
                performance_monitor.end_operation(success=True)
                return result
            except Exception as e:
                performance_monitor.end_operation(success=False, error=str(e))
                raise
                
        return async_wrapper if iscoroutinefunction(func) else sync_wrapper
    return decorator