"""
Metrics Tracking Module

Provides metrics collection and tracking for monitoring application performance
and behavior. Tracks key metrics like success rates, durations, error rates, etc.

This module uses a simple in-memory metrics store. In production, this could be
replaced with a proper metrics backend like Prometheus, StatsD, or CloudWatch.
"""

import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class MetricValue:
    """Single metric value with timestamp."""
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricStats:
    """Aggregated statistics for a metric."""
    count: int = 0
    sum: float = 0.0
    min: float = float('inf')
    max: float = float('-inf')
    avg: float = 0.0
    
    def update(self, value: float):
        """Update statistics with new value."""
        self.count += 1
        self.sum += value
        self.min = min(self.min, value)
        self.max = max(self.max, value)
        self.avg = self.sum / self.count


class MetricsCollector:
    """
    Collects and tracks application metrics.
    
    Provides methods to record various types of metrics:
    - Counters: Incrementing values (e.g., request count)
    - Gauges: Point-in-time values (e.g., queue size)
    - Timers: Duration measurements (e.g., request duration)
    - Rates: Success/failure rates (e.g., import success rate)
    
    Metrics are stored in memory with a configurable retention period.
    """
    
    def __init__(self, retention_hours: int = 24):
        """
        Initialize metrics collector.
        
        Args:
            retention_hours: How long to retain metric data (default: 24 hours)
        """
        self.retention_hours = retention_hours
        self.retention_delta = timedelta(hours=retention_hours)
        
        # Metric storage
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._timers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._rates: Dict[str, Dict[str, int]] = defaultdict(lambda: {"success": 0, "failure": 0})
        
        # Thread safety
        self._lock = Lock()
        
        logger.info(f"Metrics collector initialized with {retention_hours}h retention")
    
    def increment_counter(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        """
        Increment a counter metric.
        
        Args:
            name: Metric name
            value: Amount to increment (default: 1)
            tags: Optional tags for metric categorization
        """
        with self._lock:
            key = self._make_key(name, tags)
            self._counters[key] += value
            logger.debug(f"Counter incremented: {key} += {value} (total: {self._counters[key]})")
    
    def set_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """
        Set a gauge metric to a specific value.
        
        Args:
            name: Metric name
            value: Gauge value
            tags: Optional tags for metric categorization
        """
        with self._lock:
            key = self._make_key(name, tags)
            self._gauges[key] = value
            logger.debug(f"Gauge set: {key} = {value}")
    
    def record_timer(self, name: str, duration: float, tags: Optional[Dict[str, str]] = None):
        """
        Record a timer/duration metric.
        
        Args:
            name: Metric name
            duration: Duration in seconds
            tags: Optional tags for metric categorization
        """
        with self._lock:
            key = self._make_key(name, tags)
            metric = MetricValue(value=duration, tags=tags or {})
            self._timers[key].append(metric)
            logger.debug(f"Timer recorded: {key} = {duration:.3f}s")
    
    def record_success(self, name: str, tags: Optional[Dict[str, str]] = None):
        """
        Record a successful operation for rate calculation.
        
        Args:
            name: Metric name
            tags: Optional tags for metric categorization
        """
        with self._lock:
            key = self._make_key(name, tags)
            self._rates[key]["success"] += 1
            logger.debug(f"Success recorded: {key} (total: {self._rates[key]['success']})")
    
    def record_failure(self, name: str, tags: Optional[Dict[str, str]] = None):
        """
        Record a failed operation for rate calculation.
        
        Args:
            name: Metric name
            tags: Optional tags for metric categorization
        """
        with self._lock:
            key = self._make_key(name, tags)
            self._rates[key]["failure"] += 1
            logger.debug(f"Failure recorded: {key} (total: {self._rates[key]['failure']})")
    
    def get_counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> int:
        """Get current counter value."""
        with self._lock:
            key = self._make_key(name, tags)
            return self._counters.get(key, 0)
    
    def get_gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get current gauge value."""
        with self._lock:
            key = self._make_key(name, tags)
            return self._gauges.get(key)
    
    def get_timer_stats(self, name: str, tags: Optional[Dict[str, str]] = None) -> Optional[MetricStats]:
        """
        Get aggregated statistics for a timer metric.
        
        Args:
            name: Metric name
            tags: Optional tags for metric categorization
            
        Returns:
            MetricStats with aggregated statistics or None if no data
        """
        with self._lock:
            key = self._make_key(name, tags)
            values = self._timers.get(key, [])
            
            if not values:
                return None
            
            # Clean old values
            cutoff = datetime.now() - self.retention_delta
            values = [v for v in values if v.timestamp > cutoff]
            
            if not values:
                return None
            
            stats = MetricStats()
            for metric in values:
                stats.update(metric.value)
            
            return stats
    
    def get_success_rate(self, name: str, tags: Optional[Dict[str, str]] = None) -> Optional[float]:
        """
        Get success rate for a metric (0.0 to 1.0).
        
        Args:
            name: Metric name
            tags: Optional tags for metric categorization
            
        Returns:
            Success rate as float between 0.0 and 1.0, or None if no data
        """
        with self._lock:
            key = self._make_key(name, tags)
            rate_data = self._rates.get(key)
            
            if not rate_data:
                return None
            
            total = rate_data["success"] + rate_data["failure"]
            if total == 0:
                return None
            
            return rate_data["success"] / total
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all current metrics as a dictionary.
        
        Returns:
            Dictionary with all metric types and their current values
        """
        with self._lock:
            metrics = {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "timers": {},
                "rates": {}
            }
            
            # Add timer statistics
            for key, values in self._timers.items():
                if values:
                    stats = MetricStats()
                    for metric in values:
                        stats.update(metric.value)
                    metrics["timers"][key] = {
                        "count": stats.count,
                        "avg": stats.avg,
                        "min": stats.min,
                        "max": stats.max
                    }
            
            # Add success rates
            for key, rate_data in self._rates.items():
                total = rate_data["success"] + rate_data["failure"]
                if total > 0:
                    metrics["rates"][key] = {
                        "success": rate_data["success"],
                        "failure": rate_data["failure"],
                        "total": total,
                        "success_rate": rate_data["success"] / total
                    }
            
            return metrics
    
    def reset(self):
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._timers.clear()
            self._rates.clear()
            logger.info("All metrics reset")
    
    @staticmethod
    def _make_key(name: str, tags: Optional[Dict[str, str]] = None) -> str:
        """
        Create a unique key for a metric with tags.
        
        Args:
            name: Metric name
            tags: Optional tags
            
        Returns:
            Unique key string
        """
        if not tags:
            return name
        
        # Sort tags for consistent key generation
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"


class TimerContext:
    """Context manager for timing operations."""
    
    def __init__(self, collector: MetricsCollector, name: str, tags: Optional[Dict[str, str]] = None):
        """
        Initialize timer context.
        
        Args:
            collector: MetricsCollector instance
            name: Metric name
            tags: Optional tags
        """
        self.collector = collector
        self.name = name
        self.tags = tags
        self.start_time = None
    
    def __enter__(self):
        """Start timing."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop timing and record duration."""
        if self.start_time is not None:
            duration = time.time() - self.start_time
            self.collector.record_timer(self.name, duration, self.tags)


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """
    Get global metrics collector instance.
    
    Returns:
        MetricsCollector singleton instance
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def reset_metrics_collector():
    """Reset global metrics collector (useful for testing)."""
    global _metrics_collector
    if _metrics_collector is not None:
        _metrics_collector.reset()
