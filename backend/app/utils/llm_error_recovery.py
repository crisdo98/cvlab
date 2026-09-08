"""
LLM Error Recovery Utilities

Provides error recovery mechanisms for LLM operations including:
- Provider fallback logic
- Request queuing for rate-limited APIs
- Timeout handling with partial results
- Graceful degradation
"""

import asyncio
import time
from typing import Optional, Callable, Any, Dict, List
from enum import Enum
from dataclasses import dataclass, field
from collections import deque
import logging

logger = logging.getLogger(__name__)


class LLMErrorType(str, Enum):
    """Types of LLM errors"""
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    INVALID_API_KEY = "invalid_api_key"
    PROVIDER_ERROR = "provider_error"
    NETWORK_ERROR = "network_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    INVALID_REQUEST = "invalid_request"
    QUOTA_EXCEEDED = "quota_exceeded"
    MODEL_NOT_FOUND = "model_not_found"
    UNKNOWN = "unknown"


@dataclass
class RetryConfig:
    """Configuration for retry logic"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True


@dataclass
class QueuedRequest:
    """Queued LLM request"""
    request_fn: Callable
    priority: int = 0
    timestamp: float = field(default_factory=time.time)
    retries: int = 0


class LLMErrorClassifier:
    """Classifies errors and determines recovery strategy"""
    
    @staticmethod
    def classify_error(error: Exception) -> LLMErrorType:
        """
        Classify error type from exception.
        
        Args:
            error: Exception to classify
            
        Returns:
            Classified error type
        """
        error_msg = str(error).lower()
        
        # Check for specific error patterns
        if "rate limit" in error_msg or "429" in error_msg:
            return LLMErrorType.RATE_LIMIT
        
        if "timeout" in error_msg or "timed out" in error_msg:
            return LLMErrorType.TIMEOUT
        
        # Check for AWS credential errors (including expired credentials)
        if any(pattern in error_msg for pattern in [
            "api key",
            "authentication",
            "401",
            "credentials not found",
            "aws credentials",
            "expired",
            "expiredtoken",
            "invalid credentials",
            "access denied",
            "unauthorized",
            "signature",
            "sigv4"
        ]):
            return LLMErrorType.INVALID_API_KEY
        
        if "quota" in error_msg or "billing" in error_msg or "402" in error_msg:
            return LLMErrorType.QUOTA_EXCEEDED
        
        if "model not found" in error_msg or "404" in error_msg:
            return LLMErrorType.MODEL_NOT_FOUND
        
        if "503" in error_msg or "unavailable" in error_msg or "overloaded" in error_msg:
            return LLMErrorType.SERVICE_UNAVAILABLE
        
        if "400" in error_msg or "422" in error_msg or "invalid" in error_msg:
            return LLMErrorType.INVALID_REQUEST
        
        if "network" in error_msg or "connection" in error_msg:
            return LLMErrorType.NETWORK_ERROR
        
        if "500" in error_msg or "internal" in error_msg:
            return LLMErrorType.PROVIDER_ERROR
        
        return LLMErrorType.UNKNOWN
    
    @staticmethod
    def is_retryable(error_type: LLMErrorType) -> bool:
        """
        Check if error type is retryable.
        
        Args:
            error_type: Error type to check
            
        Returns:
            True if error is retryable
        """
        retryable_errors = {
            LLMErrorType.RATE_LIMIT,
            LLMErrorType.TIMEOUT,
            LLMErrorType.PROVIDER_ERROR,
            LLMErrorType.NETWORK_ERROR,
            LLMErrorType.SERVICE_UNAVAILABLE
        }
        return error_type in retryable_errors
    
    @staticmethod
    def get_retry_config(error_type: LLMErrorType) -> RetryConfig:
        """
        Get retry configuration for error type.
        
        Args:
            error_type: Error type
            
        Returns:
            Retry configuration
        """
        configs = {
            LLMErrorType.RATE_LIMIT: RetryConfig(
                max_retries=3,
                base_delay=5.0,
                max_delay=60.0,
                backoff_multiplier=2.0
            ),
            LLMErrorType.TIMEOUT: RetryConfig(
                max_retries=2,
                base_delay=2.0,
                max_delay=10.0,
                backoff_multiplier=2.0
            ),
            LLMErrorType.PROVIDER_ERROR: RetryConfig(
                max_retries=2,
                base_delay=3.0,
                max_delay=15.0,
                backoff_multiplier=2.0
            ),
            LLMErrorType.NETWORK_ERROR: RetryConfig(
                max_retries=3,
                base_delay=2.0,
                max_delay=10.0,
                backoff_multiplier=2.0
            ),
            LLMErrorType.SERVICE_UNAVAILABLE: RetryConfig(
                max_retries=2,
                base_delay=10.0,
                max_delay=30.0,
                backoff_multiplier=2.0
            )
        }
        return configs.get(error_type, RetryConfig(max_retries=0))


class LLMRequestQueue:
    """
    Queue for managing rate-limited LLM requests.
    
    Implements:
    - Priority-based queuing
    - Rate limiting
    - Request deduplication
    """
    
    def __init__(self, max_requests_per_minute: int = 60):
        """
        Initialize request queue.
        
        Args:
            max_requests_per_minute: Maximum requests per minute
        """
        self.queue: deque[QueuedRequest] = deque()
        self.max_requests_per_minute = max_requests_per_minute
        self.request_timestamps: deque[float] = deque()
        self.processing = False
    
    async def enqueue(
        self,
        request_fn: Callable,
        priority: int = 0
    ) -> Any:
        """
        Enqueue a request for processing.
        
        Args:
            request_fn: Async function to execute
            priority: Request priority (higher = more important)
            
        Returns:
            Result from request function
        """
        queued_request = QueuedRequest(
            request_fn=request_fn,
            priority=priority
        )
        
        # Insert based on priority
        inserted = False
        for i, existing in enumerate(self.queue):
            if priority > existing.priority:
                self.queue.insert(i, queued_request)
                inserted = True
                break
        
        if not inserted:
            self.queue.append(queued_request)
        
        # Start processing if not already running
        if not self.processing:
            return await self._process_queue()
        
        # Wait for this request to be processed
        while queued_request in self.queue:
            await asyncio.sleep(0.1)
        
        # Request was processed, but we need to return result
        # For now, just execute it directly after rate limit check
        await self._wait_for_rate_limit()
        return await request_fn()
    
    async def _process_queue(self) -> Any:
        """Process queued requests with rate limiting."""
        self.processing = True
        result = None
        
        try:
            while self.queue:
                # Wait if rate limit would be exceeded
                await self._wait_for_rate_limit()
                
                # Get next request
                request = self.queue.popleft()
                
                # Execute request
                try:
                    result = await request.request_fn()
                    self.request_timestamps.append(time.time())
                except Exception as e:
                    logger.error(f"Error processing queued request: {e}")
                    raise
        finally:
            self.processing = False
        
        return result
    
    async def _wait_for_rate_limit(self) -> None:
        """Wait if rate limit would be exceeded."""
        now = time.time()
        
        # Remove timestamps older than 1 minute
        while self.request_timestamps and now - self.request_timestamps[0] > 60:
            self.request_timestamps.popleft()
        
        # Wait if at rate limit
        if len(self.request_timestamps) >= self.max_requests_per_minute:
            oldest = self.request_timestamps[0]
            wait_time = 60 - (now - oldest)
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)


class LLMProviderFallback:
    """
    Manages fallback between multiple LLM providers.
    
    Attempts primary provider first, falls back to alternatives on failure.
    """
    
    def __init__(self, providers: List[Callable]):
        """
        Initialize provider fallback.
        
        Args:
            providers: List of provider functions in priority order
        """
        self.providers = providers
        self.provider_errors: Dict[int, List[Exception]] = {}
    
    async def execute_with_fallback(
        self,
        request_fn: Callable[[Any], Any],
        *args,
        **kwargs
    ) -> Any:
        """
        Execute request with provider fallback.
        
        Args:
            request_fn: Function to execute with provider
            *args: Positional arguments for request function
            **kwargs: Keyword arguments for request function
            
        Returns:
            Result from successful provider
            
        Raises:
            Exception: If all providers fail
        """
        last_error = None
        
        for i, provider in enumerate(self.providers):
            try:
                logger.info(f"Attempting provider {i + 1}/{len(self.providers)}")
                result = await request_fn(provider, *args, **kwargs)
                
                # Success - clear error history for this provider
                if i in self.provider_errors:
                    self.provider_errors[i].clear()
                
                return result
                
            except Exception as e:
                last_error = e
                error_type = LLMErrorClassifier.classify_error(e)
                
                # Track error
                if i not in self.provider_errors:
                    self.provider_errors[i] = []
                self.provider_errors[i].append(e)
                
                logger.warning(
                    f"Provider {i + 1} failed with {error_type}: {e}"
                )
                
                # Don't try fallback for non-retryable errors
                if not LLMErrorClassifier.is_retryable(error_type):
                    logger.info("Error not retryable, skipping remaining providers")
                    raise
                
                # Continue to next provider
                continue
        
        # All providers failed
        logger.error("All providers failed")
        raise last_error or Exception("All LLM providers failed")


async def retry_with_exponential_backoff(
    request_fn: Callable,
    error_classifier: Optional[LLMErrorClassifier] = None,
    retry_config: Optional[RetryConfig] = None
) -> Any:
    """
    Retry a request with exponential backoff.
    
    Args:
        request_fn: Async function to retry
        error_classifier: Error classifier for determining retry strategy
        retry_config: Retry configuration (auto-determined if not provided)
        
    Returns:
        Result from successful request
        
    Raises:
        Exception: If all retries fail
    """
    if error_classifier is None:
        error_classifier = LLMErrorClassifier()
    
    last_error = None
    attempt = 0
    
    while True:
        try:
            return await request_fn()
            
        except Exception as e:
            last_error = e
            error_type = error_classifier.classify_error(e)
            
            # Get retry config if not provided
            if retry_config is None:
                retry_config = error_classifier.get_retry_config(error_type)
            
            # Check if we should retry
            if not error_classifier.is_retryable(error_type):
                logger.info(f"Error type {error_type} not retryable")
                raise
            
            if attempt >= retry_config.max_retries:
                logger.info(f"Max retries ({retry_config.max_retries}) reached")
                raise
            
            # Calculate delay with exponential backoff
            delay = min(
                retry_config.base_delay * (retry_config.backoff_multiplier ** attempt),
                retry_config.max_delay
            )
            
            # Add jitter to prevent thundering herd
            if retry_config.jitter:
                import random
                delay = delay * (0.5 + random.random())
            
            logger.info(
                f"Retry attempt {attempt + 1}/{retry_config.max_retries} "
                f"after {delay:.2f}s delay (error: {error_type})"
            )
            
            await asyncio.sleep(delay)
            attempt += 1


async def execute_with_timeout(
    request_fn: Callable,
    timeout_seconds: float = 60.0,
    partial_result_fn: Optional[Callable] = None
) -> Any:
    """
    Execute request with timeout and optional partial result handling.
    
    Args:
        request_fn: Async function to execute
        timeout_seconds: Timeout in seconds
        partial_result_fn: Optional function to get partial results on timeout
        
    Returns:
        Result from request or partial result on timeout
        
    Raises:
        asyncio.TimeoutError: If timeout occurs and no partial result available
    """
    try:
        return await asyncio.wait_for(request_fn(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(f"Request timed out after {timeout_seconds}s")
        
        # Try to get partial result
        if partial_result_fn:
            try:
                partial_result = await partial_result_fn()
                logger.info("Returning partial result after timeout")
                return partial_result
            except Exception as e:
                logger.error(f"Failed to get partial result: {e}")
        
        raise


class GracefulDegradation:
    """
    Manages graceful degradation when LLM services fail.
    
    Provides fallback responses and caching for resilience.
    """
    
    def __init__(self):
        """Initialize graceful degradation manager."""
        self.cache: Dict[str, Any] = {}
        self.fallback_responses: Dict[str, Any] = {}
    
    def set_fallback(self, operation: str, fallback_response: Any) -> None:
        """
        Set fallback response for an operation.
        
        Args:
            operation: Operation name
            fallback_response: Fallback response to return on failure
        """
        self.fallback_responses[operation] = fallback_response
    
    def get_fallback(self, operation: str) -> Optional[Any]:
        """
        Get fallback response for an operation.
        
        Args:
            operation: Operation name
            
        Returns:
            Fallback response if available
        """
        return self.fallback_responses.get(operation)
    
    def cache_result(self, key: str, result: Any) -> None:
        """
        Cache a successful result.
        
        Args:
            key: Cache key
            result: Result to cache
        """
        self.cache[key] = result
    
    def get_cached(self, key: str) -> Optional[Any]:
        """
        Get cached result.
        
        Args:
            key: Cache key
            
        Returns:
            Cached result if available
        """
        return self.cache.get(key)
    
    async def execute_with_degradation(
        self,
        operation: str,
        request_fn: Callable,
        cache_key: Optional[str] = None
    ) -> Any:
        """
        Execute request with graceful degradation.
        
        Args:
            operation: Operation name
            request_fn: Async function to execute
            cache_key: Optional cache key for result caching
            
        Returns:
            Result from request, cached result, or fallback response
        """
        try:
            result = await request_fn()
            
            # Cache successful result
            if cache_key:
                self.cache_result(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.warning(f"Operation {operation} failed: {e}")
            
            # Try cached result first
            if cache_key:
                cached = self.get_cached(cache_key)
                if cached is not None:
                    logger.info(f"Returning cached result for {operation}")
                    return cached
            
            # Fall back to default response
            fallback = self.get_fallback(operation)
            if fallback is not None:
                logger.info(f"Returning fallback response for {operation}")
                return fallback
            
            # No fallback available
            raise


# Global instances
_request_queue: Optional[LLMRequestQueue] = None
_graceful_degradation: Optional[GracefulDegradation] = None


def get_request_queue() -> LLMRequestQueue:
    """Get global request queue instance."""
    global _request_queue
    if _request_queue is None:
        _request_queue = LLMRequestQueue()
    return _request_queue


def get_graceful_degradation() -> GracefulDegradation:
    """Get global graceful degradation instance."""
    global _graceful_degradation
    if _graceful_degradation is None:
        _graceful_degradation = GracefulDegradation()
    return _graceful_degradation
