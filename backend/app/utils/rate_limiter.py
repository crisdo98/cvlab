"""
Rate Limiter

Token bucket implementation for rate limiting API requests.
Supports per-user tracking and request queuing.

Requirements:
- 5.1: Implement rate limiting to prevent excessive requests
- 5.2: Queue additional requests when approaching limits
- 5.4: Track import attempts per user
"""

import time
import asyncio
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.utils.metrics import get_metrics_collector

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """
    Token bucket for rate limiting.
    
    Tokens are added at a fixed rate. Each request consumes one token.
    If no tokens are available, requests must wait.
    """
    max_tokens: int
    refill_rate: float  # tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)
    
    def __post_init__(self):
        """Initialize bucket with full tokens."""
        self.tokens = float(self.max_tokens)
        self.last_refill = time.time()
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.max_tokens, self.tokens + tokens_to_add)
        self.last_refill = now
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        
        return False
    
    def get_wait_time(self, tokens: int = 1) -> float:
        """
        Get time to wait until tokens are available.
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Seconds to wait (0 if tokens available now)
        """
        self._refill()
        
        if self.tokens >= tokens:
            return 0.0
        
        # Calculate how long until we have enough tokens
        tokens_needed = tokens - self.tokens
        wait_time = tokens_needed / self.refill_rate
        
        return wait_time
    
    def get_available_tokens(self) -> int:
        """
        Get number of available tokens.
        
        Returns:
            Number of tokens currently available
        """
        self._refill()
        return int(self.tokens)


class RateLimiter:
    """
    Rate limiter with per-user tracking and request queuing.
    
    Uses token bucket algorithm to enforce rate limits.
    Supports queuing requests when limits are approached.
    
    Requirements:
    - 5.1: Implement rate limiting
    - 5.2: Queue requests when approaching limits
    - 5.4: Track per-user requests
    """
    
    def __init__(
        self,
        max_requests: int,
        time_window: int,
        queue_threshold: float = 0.2
    ):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
            queue_threshold: Queue requests when tokens fall below this fraction
                           (e.g., 0.2 means queue when < 20% tokens remain)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.queue_threshold = queue_threshold
        
        # Calculate refill rate (tokens per second)
        self.refill_rate = max_requests / time_window
        
        # Per-user token buckets
        self._buckets: Dict[str, TokenBucket] = {}
        
        # Per-user request queues
        self._queues: Dict[str, asyncio.Queue] = {}
        
        # Per-user request counts (for tracking)
        self._request_counts: Dict[str, List[float]] = {}
        
        # Metrics collector
        self.metrics = get_metrics_collector()
        
        logger.info(
            f"Rate limiter initialized: {max_requests} requests per {time_window}s "
            f"(refill rate: {self.refill_rate:.2f} tokens/s)"
        )
    
    def _get_bucket(self, user_id: str) -> TokenBucket:
        """
        Get or create token bucket for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            TokenBucket for the user
        """
        if user_id not in self._buckets:
            self._buckets[user_id] = TokenBucket(
                max_tokens=self.max_requests,
                refill_rate=self.refill_rate
            )
        
        return self._buckets[user_id]
    
    def _get_queue(self, user_id: str) -> asyncio.Queue:
        """
        Get or create request queue for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            asyncio.Queue for the user
        """
        if user_id not in self._queues:
            self._queues[user_id] = asyncio.Queue()
        
        return self._queues[user_id]
    
    def _track_request(self, user_id: str) -> None:
        """
        Track a request for statistics.
        
        Args:
            user_id: User identifier
        """
        now = time.time()
        
        if user_id not in self._request_counts:
            self._request_counts[user_id] = []
        
        # Add current request
        self._request_counts[user_id].append(now)
        
        # Clean old requests outside time window
        cutoff = now - self.time_window
        self._request_counts[user_id] = [
            t for t in self._request_counts[user_id]
            if t > cutoff
        ]
    
    async def acquire(self, user_id: str) -> bool:
        """
        Acquire permission to make a request.
        
        If tokens are available, returns immediately.
        If approaching limit (below queue threshold), queues the request.
        
        Args:
            user_id: User identifier
            
        Returns:
            True when request is allowed to proceed
            
        Requirements:
        - 5.1: Enforce rate limits
        - 5.2: Queue requests when approaching limits
        """
        bucket = self._get_bucket(user_id)
        
        # Check if we should queue this request
        available_tokens = bucket.get_available_tokens()
        should_queue = available_tokens < (self.max_requests * self.queue_threshold)
        
        if should_queue:
            # Track queue metrics
            self.metrics.increment_counter("rate_limiter.requests_queued", tags={"user_id": user_id})
            
            logger.info(
                f"Rate limit approaching for user {user_id} "
                f"({available_tokens}/{self.max_requests} tokens). Queuing request."
            )
            
            # Add to queue
            queue = self._get_queue(user_id)
            await queue.put(time.time())
            
            # Track queue size
            self.metrics.set_gauge(
                "rate_limiter.queue_size",
                queue.qsize(),
                tags={"user_id": user_id}
            )
            
            # Wait for our turn
            await self._process_queue(user_id)
        
        # Try to consume token
        while not bucket.consume():
            wait_time = bucket.get_wait_time()
            
            # Track rate limit hit
            self.metrics.increment_counter("rate_limiter.rate_limit_hit", tags={"user_id": user_id})
            
            logger.info(
                f"Rate limit reached for user {user_id}. "
                f"Waiting {wait_time:.2f}s for token refill."
            )
            await asyncio.sleep(wait_time)
        
        # Track the request
        self._track_request(user_id)
        
        # Track successful acquisition
        self.metrics.increment_counter("rate_limiter.requests_allowed", tags={"user_id": user_id})
        self.metrics.set_gauge(
            "rate_limiter.tokens_available",
            bucket.get_available_tokens(),
            tags={"user_id": user_id}
        )
        
        logger.debug(
            f"Request allowed for user {user_id}. "
            f"Tokens remaining: {bucket.get_available_tokens()}"
        )
        
        return True
    
    async def _process_queue(self, user_id: str) -> None:
        """
        Process queued requests for a user.
        
        Waits until it's this request's turn based on queue position
        and token availability.
        
        Args:
            user_id: User identifier
        """
        queue = self._get_queue(user_id)
        bucket = self._get_bucket(user_id)
        
        # Wait until we're at the front of the queue
        while queue.qsize() > 1:
            await asyncio.sleep(0.1)
        
        # Wait until tokens are available
        while bucket.get_available_tokens() < 1:
            wait_time = bucket.get_wait_time()
            await asyncio.sleep(min(wait_time, 1.0))
        
        # Remove from queue
        await queue.get()
    
    def check_limit(self, user_id: str) -> bool:
        """
        Check if user has tokens available without consuming.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if tokens available, False otherwise
        """
        bucket = self._get_bucket(user_id)
        return bucket.get_available_tokens() >= 1
    
    def get_status(self, user_id: str) -> Dict[str, any]:
        """
        Get rate limit status for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with rate limit status information
            
        Requirements:
        - 5.4: Track per-user requests
        """
        bucket = self._get_bucket(user_id)
        queue = self._get_queue(user_id)
        
        # Get request count in current window
        request_count = len(self._request_counts.get(user_id, []))
        
        return {
            "user_id": user_id,
            "tokens_available": bucket.get_available_tokens(),
            "max_tokens": self.max_requests,
            "requests_in_window": request_count,
            "queued_requests": queue.qsize(),
            "wait_time_seconds": bucket.get_wait_time(),
            "is_rate_limited": bucket.get_available_tokens() < 1
        }
    
    def get_all_users_status(self) -> List[Dict[str, any]]:
        """
        Get rate limit status for all tracked users.
        
        Returns:
            List of status dictionaries for all users
        """
        return [
            self.get_status(user_id)
            for user_id in self._buckets.keys()
        ]
    
    def reset_user(self, user_id: str) -> None:
        """
        Reset rate limit for a user.
        
        Args:
            user_id: User identifier
        """
        if user_id in self._buckets:
            del self._buckets[user_id]
        
        if user_id in self._queues:
            del self._queues[user_id]
        
        if user_id in self._request_counts:
            del self._request_counts[user_id]
        
        logger.info(f"Rate limit reset for user {user_id}")
    
    def cleanup_inactive_users(self, inactive_threshold: int = 3600) -> int:
        """
        Clean up tracking data for inactive users.
        
        Args:
            inactive_threshold: Seconds of inactivity before cleanup
            
        Returns:
            Number of users cleaned up
        """
        now = time.time()
        cutoff = now - inactive_threshold
        
        inactive_users = []
        
        for user_id, requests in self._request_counts.items():
            if not requests or max(requests) < cutoff:
                inactive_users.append(user_id)
        
        for user_id in inactive_users:
            self.reset_user(user_id)
        
        if inactive_users:
            logger.info(f"Cleaned up {len(inactive_users)} inactive users")
        
        return len(inactive_users)
