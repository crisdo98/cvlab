"""
Property-Based Tests for Rate Limiting

Tests Property 7: Rate Limiting Enforcement

Validates Requirements:
- 5.1: Implement rate limiting to prevent excessive requests
- 5.2: Queue additional requests when approaching limits
- 5.4: Track import attempts per user

These tests verify that rate limits are enforced correctly across all scenarios.
"""

import pytest
import asyncio
import time
from hypothesis import given, strategies as st, settings, assume
from hypothesis import HealthCheck

from app.utils.rate_limiter import RateLimiter, TokenBucket


class TestProperty7RateLimitingEnforcement:
    """
    Property 7: Rate Limiting Enforcement
    
    For any sequence of import requests from a single user, when the rate limit
    threshold is approached, additional requests should be queued rather than rejected,
    and the system should track the number of requests per user to enforce limits.
    
    Validates: Requirements 5.1, 5.2, 5.4
    """
    
    @given(
        max_requests=st.integers(min_value=1, max_value=20),
        time_window=st.integers(min_value=1, max_value=10),
        num_requests=st.integers(min_value=1, max_value=30)
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_rate_limit_enforcement_never_exceeds_limit(
        self,
        max_requests: int,
        time_window: int,
        num_requests: int
    ):
        """
        Property: Rate limiter never allows more than max_requests in time_window.
        
        For any configuration and request sequence, the number of successful
        requests in any time window should never exceed the configured limit.
        """
        # Create rate limiter
        limiter = RateLimiter(
            max_requests=max_requests,
            time_window=time_window
        )
        
        user_id = "test_user"
        
        # Track successful requests with timestamps
        successful_requests = []
        
        # Make requests synchronously (checking without consuming)
        for _ in range(num_requests):
            if limiter.check_limit(user_id):
                # Manually consume token
                bucket = limiter._get_bucket(user_id)
                if bucket.consume():
                    successful_requests.append(time.time())
                    limiter._track_request(user_id)
        
        # Verify: Count requests in any sliding window
        if successful_requests:
            for i, start_time in enumerate(successful_requests):
                # Count requests within time_window from this request
                window_end = start_time + time_window
                requests_in_window = sum(
                    1 for t in successful_requests
                    if start_time <= t < window_end
                )
                
                # Should never exceed max_requests
                assert requests_in_window <= max_requests, (
                    f"Rate limit violated: {requests_in_window} requests in window "
                    f"(max: {max_requests})"
                )
    
    @given(
        max_requests=st.integers(min_value=5, max_value=20),
        time_window=st.integers(min_value=2, max_value=5),
        num_users=st.integers(min_value=2, max_value=5)
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_per_user_tracking_isolation(
        self,
        max_requests: int,
        time_window: int,
        num_users: int
    ):
        """
        Property: Rate limits are tracked independently per user.
        
        For any number of users, each user's rate limit should be tracked
        independently without affecting other users.
        
        Validates: Requirement 5.4 (per-user tracking)
        """
        limiter = RateLimiter(
            max_requests=max_requests,
            time_window=time_window
        )
        
        # Create user IDs
        user_ids = [f"user_{i}" for i in range(num_users)]
        
        # Each user makes requests up to their limit
        for user_id in user_ids:
            bucket = limiter._get_bucket(user_id)
            
            # Consume all tokens for this user
            consumed = 0
            while bucket.consume():
                limiter._track_request(user_id)
                consumed += 1
                if consumed >= max_requests:
                    break
            
            # Verify this user is now limited
            assert not limiter.check_limit(user_id), (
                f"User {user_id} should be rate limited after {consumed} requests"
            )
        
        # Verify each user's status is independent
        statuses = [limiter.get_status(uid) for uid in user_ids]
        
        for status in statuses:
            # Each user should have made requests
            assert status["requests_in_window"] > 0
            # Each user should be rate limited
            assert status["is_rate_limited"]
    
    @pytest.mark.asyncio
    @given(
        max_requests=st.integers(min_value=10, max_value=20),
        time_window=st.integers(min_value=10, max_value=20)
    )
    @settings(
        max_examples=30,
        deadline=5000,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    async def test_request_queuing_when_approaching_limit(
        self,
        max_requests: int,
        time_window: int
    ):
        """
        Property: Requests wait when rate limit is exhausted.
        
        For any rate limiter configuration, when all tokens are consumed,
        subsequent requests should wait for token refill.
        
        Validates: Requirement 5.2 (queue requests when approaching limits)
        """
        # Use a low queue threshold to trigger queuing behavior
        limiter = RateLimiter(
            max_requests=max_requests,
            time_window=time_window,
            queue_threshold=0.3
        )
        
        user_id = "test_user"
        bucket = limiter._get_bucket(user_id)
        
        # Consume ALL tokens
        for _ in range(max_requests + 1):
            if not bucket.consume():
                break
        
        # Verify no tokens available
        available = bucket.get_available_tokens()
        assert available == 0, f"Expected 0 tokens, got {available}"
        
        # Now try to acquire - it should wait/block
        acquire_task = asyncio.create_task(limiter.acquire(user_id))
        
        # Give it a moment
        await asyncio.sleep(0.1)
        
        # Task should still be pending (waiting for tokens)
        is_pending = not acquire_task.done()
        
        # Cancel the task
        acquire_task.cancel()
        try:
            await acquire_task
        except asyncio.CancelledError:
            pass
        
        # Verify the request was blocked/waiting
        assert is_pending, (
            f"Request should be waiting when no tokens available. "
            f"Tokens: {available}, Task done: {not is_pending}"
        )
    
    @given(
        max_requests=st.integers(min_value=5, max_value=15),
        time_window=st.integers(min_value=2, max_value=5)
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_rate_limit_status_accuracy(
        self,
        max_requests: int,
        time_window: int
    ):
        """
        Property: Rate limit status accurately reflects current state.
        
        For any rate limiter state, the status information should accurately
        reflect the number of available tokens, requests in window, and
        rate limit state.
        
        Validates: Requirement 5.4 (track per-user requests)
        """
        limiter = RateLimiter(
            max_requests=max_requests,
            time_window=time_window
        )
        
        user_id = "test_user"
        bucket = limiter._get_bucket(user_id)
        
        # Make some requests
        num_requests = min(max_requests - 1, 5)
        for _ in range(num_requests):
            bucket.consume()
            limiter._track_request(user_id)
        
        # Get status
        status = limiter.get_status(user_id)
        
        # Verify status fields
        assert "user_id" in status
        assert status["user_id"] == user_id
        
        assert "tokens_available" in status
        assert isinstance(status["tokens_available"], int)
        assert 0 <= status["tokens_available"] <= max_requests
        
        assert "max_tokens" in status
        assert status["max_tokens"] == max_requests
        
        assert "requests_in_window" in status
        assert status["requests_in_window"] == num_requests
        
        assert "is_rate_limited" in status
        assert isinstance(status["is_rate_limited"], bool)
        
        # If tokens available, should not be rate limited
        if status["tokens_available"] >= 1:
            assert not status["is_rate_limited"]
    
    def test_token_bucket_refill_rate(self):
        """
        Property: Token bucket refills at correct rate.
        
        For any token bucket configuration, tokens should refill at the
        specified rate over time.
        """
        max_tokens = 10
        refill_rate = 2.0  # 2 tokens per second
        
        bucket = TokenBucket(max_tokens=max_tokens, refill_rate=refill_rate)
        
        # Consume all tokens
        for _ in range(max_tokens):
            assert bucket.consume()
        
        # Should be empty
        assert bucket.get_available_tokens() == 0
        
        # Wait for some tokens to refill
        time.sleep(1.0)  # Should refill ~2 tokens
        
        # Check refilled tokens (allow some tolerance)
        refilled = bucket.get_available_tokens()
        assert 1 <= refilled <= 3, (
            f"Expected ~2 tokens after 1s, got {refilled}"
        )
    
    @given(
        max_tokens=st.integers(min_value=5, max_value=20),
        tokens_to_consume=st.integers(min_value=1, max_value=25)
    )
    @settings(max_examples=100)
    def test_token_bucket_never_goes_negative(
        self,
        max_tokens: int,
        tokens_to_consume: int
    ):
        """
        Property: Token bucket never has negative tokens.
        
        For any sequence of consume operations, the token count should
        never go below zero.
        """
        refill_rate = max_tokens / 10.0  # Arbitrary refill rate
        bucket = TokenBucket(max_tokens=max_tokens, refill_rate=refill_rate)
        
        # Try to consume tokens
        for _ in range(tokens_to_consume):
            bucket.consume()
        
        # Tokens should never be negative
        available = bucket.get_available_tokens()
        assert available >= 0, f"Token count went negative: {available}"
    
    @given(
        max_tokens=st.integers(min_value=5, max_value=20),
        refill_rate=st.floats(min_value=0.1, max_value=5.0)
    )
    @settings(
        max_examples=100,
        deadline=1000  # Increased deadline to accommodate sleep
    )
    def test_token_bucket_never_exceeds_max(
        self,
        max_tokens: int,
        refill_rate: float
    ):
        """
        Property: Token bucket never exceeds maximum capacity.
        
        For any token bucket, even after refilling, the token count should
        never exceed the maximum capacity.
        """
        bucket = TokenBucket(max_tokens=max_tokens, refill_rate=refill_rate)
        
        # Consume some tokens
        bucket.consume(max_tokens // 2)
        
        # Wait for refill (shorter wait to avoid deadline issues)
        time.sleep(0.1)
        
        # Force refill
        bucket._refill()
        
        # Should not exceed max
        available = bucket.get_available_tokens()
        assert available <= max_tokens, (
            f"Token count exceeded max: {available} > {max_tokens}"
        )
    
    @given(
        max_requests=st.integers(min_value=3, max_value=10),
        time_window=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=50)
    def test_cleanup_removes_inactive_users(
        self,
        max_requests: int,
        time_window: int
    ):
        """
        Property: Cleanup removes inactive users without affecting active ones.
        
        For any rate limiter, cleanup should remove inactive users while
        preserving data for active users.
        """
        limiter = RateLimiter(
            max_requests=max_requests,
            time_window=time_window
        )
        
        # Create some users
        active_user = "active_user"
        inactive_user = "inactive_user"
        
        # Make requests for both users
        limiter._get_bucket(active_user).consume()
        limiter._track_request(active_user)
        
        limiter._get_bucket(inactive_user).consume()
        limiter._track_request(inactive_user)
        
        # Manually mark inactive user as old
        limiter._request_counts[inactive_user] = [time.time() - 7200]  # 2 hours ago
        
        # Run cleanup with 1 hour threshold
        cleaned = limiter.cleanup_inactive_users(inactive_threshold=3600)
        
        # Should have cleaned up inactive user
        assert cleaned >= 1
        
        # Active user should still exist
        assert active_user in limiter._buckets
        
        # Inactive user should be removed
        # (might be recreated on next access, but request history should be gone)
        if inactive_user in limiter._request_counts:
            assert len(limiter._request_counts[inactive_user]) == 0


class TestTokenBucketBasicProperties:
    """Basic property tests for TokenBucket implementation."""
    
    @given(
        max_tokens=st.integers(min_value=1, max_value=100),
        refill_rate=st.floats(min_value=0.1, max_value=10.0)
    )
    @settings(max_examples=100)
    def test_token_bucket_initialization(
        self,
        max_tokens: int,
        refill_rate: float
    ):
        """
        Property: Token bucket initializes with full tokens.
        
        For any valid configuration, a new token bucket should start
        with the maximum number of tokens available.
        """
        bucket = TokenBucket(max_tokens=max_tokens, refill_rate=refill_rate)
        
        assert bucket.get_available_tokens() == max_tokens
        assert bucket.max_tokens == max_tokens
        assert bucket.refill_rate == refill_rate
    
    @given(
        max_tokens=st.integers(min_value=2, max_value=20),
        tokens_to_consume=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=100)
    def test_consume_reduces_available_tokens(
        self,
        max_tokens: int,
        tokens_to_consume: int
    ):
        """
        Property: Consuming tokens reduces available count.
        
        For any token bucket, successfully consuming tokens should reduce
        the available token count by the consumed amount.
        """
        assume(tokens_to_consume <= max_tokens)
        
        refill_rate = 1.0
        bucket = TokenBucket(max_tokens=max_tokens, refill_rate=refill_rate)
        
        initial_tokens = bucket.get_available_tokens()
        success = bucket.consume(tokens_to_consume)
        final_tokens = bucket.get_available_tokens()
        
        if success:
            # Should have consumed the tokens
            assert final_tokens == initial_tokens - tokens_to_consume
        else:
            # Should not have changed
            assert final_tokens == initial_tokens
    
    @given(
        max_tokens=st.integers(min_value=5, max_value=20),
        tokens_needed=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=100)
    def test_wait_time_calculation(
        self,
        max_tokens: int,
        tokens_needed: int
    ):
        """
        Property: Wait time is calculated correctly based on refill rate.
        
        For any token bucket state, the wait time should be proportional
        to the number of tokens needed and the refill rate.
        """
        refill_rate = 2.0  # 2 tokens per second
        bucket = TokenBucket(max_tokens=max_tokens, refill_rate=refill_rate)
        
        # Consume all tokens
        bucket.consume(max_tokens)
        
        # Calculate wait time for tokens_needed
        wait_time = bucket.get_wait_time(tokens_needed)
        
        # Wait time should be approximately tokens_needed / refill_rate
        expected_wait = tokens_needed / refill_rate
        
        # Allow some tolerance for timing
        assert abs(wait_time - expected_wait) < 0.1, (
            f"Wait time {wait_time} doesn't match expected {expected_wait}"
        )
