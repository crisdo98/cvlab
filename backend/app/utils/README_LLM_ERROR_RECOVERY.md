# LLM Error Handling and Recovery

This document describes the comprehensive error handling and recovery mechanisms implemented for LLM operations.

## Overview

The LLM error handling system provides robust error recovery through:
- **Frontend**: User-friendly error messages, retry logic, and fallback UI
- **Backend**: Provider fallback, request queuing, timeout handling, and graceful degradation

## Frontend Implementation

### 1. Error Handler Utility (`frontend/src/utils/llmErrorHandler.js`)

**Features:**
- **Error Classification**: Identifies 10 different error types (rate limit, timeout, invalid API key, etc.)
- **User-Friendly Messages**: Provides clear titles, messages, and suggestions for each error type
- **Retry Configuration**: Automatic retry logic with exponential backoff based on error type
- **Error Tracking**: Tracks error history to temporarily disable LLM features after repeated failures
- **Recovery Actions**: Suggests specific actions users can take to resolve errors

**Error Types:**
- `RATE_LIMIT`: Too many requests to LLM provider
- `TIMEOUT`: Request took too long
- `INVALID_API_KEY`: Authentication failed
- `PROVIDER_ERROR`: LLM service internal error
- `NETWORK_ERROR`: Connection issues
- `SERVICE_UNAVAILABLE`: Service temporarily down
- `INVALID_REQUEST`: Bad request format
- `QUOTA_EXCEEDED`: API usage limits reached
- `MODEL_NOT_FOUND`: Requested model unavailable
- `UNKNOWN`: Unclassified errors

**Retry Strategy:**
```javascript
// Example: Rate limit errors
{
  shouldRetry: true,
  maxRetries: 3,
  baseDelay: 5000,      // 5 seconds
  maxDelay: 60000,      // 60 seconds
  backoffMultiplier: 2  // Exponential backoff
}
```

### 2. Error Display Component (`frontend/src/components/LLMErrorDisplay.vue`)

**Features:**
- Visual error display with icons (warning for recoverable, error for fatal)
- Retry countdown with progress indicator
- Action buttons for recovery (retry, settings, switch provider, etc.)
- Dismissible errors
- Temporary disable warning when error threshold reached

**Usage:**
```vue
<LLMErrorDisplay
  :error="error"
  :actions="errorActions"
  :retrying="retrying"
  :retry-attempt="retryAttempt"
  :retry-max-attempts="maxAttempts"
  @action="handleAction"
  @dismiss="clearError"
/>
```

### 3. LLM Request Composable (`frontend/src/composables/useLLMRequest.js`)

**Features:**
- Unified interface for making LLM requests
- Automatic retry with exponential backoff
- Loading state management
- Error tracking and fallback states
- Recovery action handling
- Global error tracker for disabling LLM features

**Usage:**
```javascript
import { useLLMRequest } from '@/composables/useLLMRequest';

const { loading, error, execute, handleAction } = useLLMRequest();

// Execute request with automatic error handling
const result = await execute(
  () => llmAPI.generateContent(request),
  {
    providerName: 'OpenAI',
    onSuccess: (result) => console.log('Success:', result),
    onError: (err, errorType) => console.error('Failed:', errorType)
  }
);
```

### 4. API Service Updates (`frontend/src/services/api.js`)

**Features:**
- Separate axios instance for LLM requests with 60-second timeout
- Longer timeout for LLM operations vs regular API calls
- Consistent error handling across all LLM endpoints

## Backend Implementation

### 1. Error Recovery Utility (`backend/app/utils/llm_error_recovery.py`)

**Components:**

#### LLMErrorClassifier
- Classifies exceptions into error types
- Determines if errors are retryable
- Provides retry configuration per error type

#### LLMRequestQueue
- Priority-based request queuing
- Rate limiting (configurable requests per minute)
- Prevents API rate limit violations
- Request deduplication

#### LLMProviderFallback
- Manages multiple LLM providers
- Automatic fallback on provider failure
- Tracks provider error history
- Skips non-retryable errors

#### Retry Functions
- `retry_with_exponential_backoff`: Retry with configurable backoff
- `execute_with_timeout`: Timeout handling with partial results
- Jitter to prevent thundering herd problem

#### GracefulDegradation
- Caches successful results
- Provides fallback responses
- Returns cached/fallback data on failure

**Usage:**
```python
from app.utils.llm_error_recovery import (
    retry_with_exponential_backoff,
    LLMProviderFallback,
    get_request_queue
)

# Retry with automatic backoff
result = await retry_with_exponential_backoff(
    lambda: provider.generate_completion(prompt)
)

# Provider fallback
fallback = LLMProviderFallback([provider1, provider2, provider3])
result = await fallback.execute_with_fallback(
    lambda p: p.generate_completion(prompt)
)

# Request queuing for rate limits
queue = get_request_queue()
result = await queue.enqueue(
    lambda: provider.generate_completion(prompt),
    priority=1
)
```

### 2. Router Integration (`backend/app/routers/llm_router.py`)

**Features:**
- `execute_llm_request_with_recovery`: Wrapper for all LLM requests
- Automatic retry with exponential backoff
- Timeout handling (60 seconds default)
- Graceful degradation with fallbacks
- Error classification and HTTP status mapping

**Error to HTTP Status Mapping:**
- `RATE_LIMIT` → 429 Too Many Requests
- `TIMEOUT` → 504 Gateway Timeout
- `INVALID_API_KEY` → 401 Unauthorized
- `QUOTA_EXCEEDED` → 402 Payment Required
- `MODEL_NOT_FOUND` → 404 Not Found
- `SERVICE_UNAVAILABLE` → 503 Service Unavailable
- `INVALID_REQUEST` → 400 Bad Request
- `PROVIDER_ERROR` → 502 Bad Gateway
- `NETWORK_ERROR` → 503 Service Unavailable
- `UNKNOWN` → 500 Internal Server Error

**Usage in Endpoints:**
```python
@router.post("/generate-content")
async def generate_content(
    request: ContentGenerationRequest,
    provider: BaseLLMProvider = Depends(get_llm_provider)
):
    generator = ContentGenerator(provider)
    
    result = await execute_llm_request_with_recovery(
        lambda: generator.generate_content(request),
        operation_name="content_generation",
        timeout_seconds=60.0,
        enable_retry=True
    )
    
    return result
```

## Error Recovery Flow

### Frontend Flow
1. User initiates LLM request
2. `useLLMRequest.execute()` wraps the API call
3. On error:
   - Error is classified by type
   - Retry logic determines if retryable
   - Exponential backoff applied for retries
   - Error tracked in global tracker
   - User-friendly error displayed with actions
4. If too many errors: LLM features temporarily disabled

### Backend Flow
1. Request received at LLM endpoint
2. `execute_llm_request_with_recovery()` wraps execution
3. Request wrapped with timeout handler
4. Retry logic applied if enabled
5. On error:
   - Error classified by type
   - Fallback response checked
   - Appropriate HTTP status returned
6. Provider fallback can be used for multi-provider setups

## Configuration

### Frontend Configuration
```javascript
// Error tracker settings
const tracker = new LLMErrorTracker();
tracker.maxErrors = 5;           // Max errors before disable
tracker.timeWindow = 5 * 60 * 1000; // 5 minutes

// Retry configuration
const retryConfig = {
  maxRetries: 3,
  baseDelay: 1000,
  maxDelay: 60000,
  backoffMultiplier: 2
};
```

### Backend Configuration
```python
# Request queue settings
queue = LLMRequestQueue(max_requests_per_minute=60)

# Retry configuration
retry_config = RetryConfig(
    max_retries=3,
    base_delay=1.0,
    max_delay=60.0,
    backoff_multiplier=2.0,
    jitter=True
)

# Timeout settings
timeout_seconds = 60.0
```

## Best Practices

### Frontend
1. Always use `useLLMRequest` composable for LLM operations
2. Provide clear recovery actions in error handlers
3. Show retry progress to users
4. Cache successful results when possible
5. Respect the global error tracker disable state

### Backend
1. Use `execute_llm_request_with_recovery` for all LLM endpoints
2. Set appropriate timeouts based on operation complexity
3. Configure fallback responses for critical operations
4. Use request queuing for rate-limited APIs
5. Implement provider fallback for high availability

## Testing

### Frontend Testing
- Test error classification for all error types
- Verify retry logic with exponential backoff
- Test error tracker disable/enable behavior
- Verify recovery action handling

### Backend Testing
- Test retry logic with various error types
- Verify timeout handling
- Test provider fallback mechanism
- Verify request queuing under load
- Test graceful degradation with fallbacks

## Monitoring

### Metrics to Track
- Error rates by type
- Retry success rates
- Provider fallback frequency
- Request queue depth
- Timeout occurrences
- Cache hit rates

### Logging
- All errors logged with classification
- Retry attempts logged with delay
- Provider fallback events logged
- Timeout events logged
- Fallback usage logged

## Future Enhancements

1. **Circuit Breaker**: Automatically disable failing providers
2. **Adaptive Retry**: Adjust retry strategy based on error patterns
3. **Request Prioritization**: Priority queue for important requests
4. **Partial Results**: Return partial results on timeout
5. **Error Analytics**: Dashboard for error trends and patterns
6. **Provider Health Checks**: Proactive provider availability checks
7. **Smart Caching**: ML-based cache invalidation
8. **Rate Limit Prediction**: Predict and prevent rate limit errors
