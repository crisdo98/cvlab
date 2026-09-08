# LLM Provider Abstraction Layer

This module provides a flexible abstraction layer for integrating multiple LLM providers into the CV Web Application.

## Overview

The LLM provider abstraction layer enables seamless switching between different LLM services (OpenAI, Anthropic, local models) while maintaining a consistent interface throughout the application.

## Architecture

### Base Provider Interface

All LLM providers implement the `BaseLLMProvider` abstract class, which defines:

- `generate_completion()`: Generate text completions from prompts
- `generate_structured_output()`: Generate structured JSON output matching a schema
- `validate_config()`: Validate provider configuration
- `test_connection()`: Test connectivity to the LLM service
- `generate_with_retry()`: Built-in retry logic with exponential backoff

### Supported Providers

1. **OpenAI Provider** (`openai_provider.py`)
   - Supports GPT-4, GPT-3.5-turbo models
   - Uses official OpenAI Python SDK
   - Includes rate limiting and error handling

2. **Anthropic Provider** (`anthropic_provider.py`)
   - Supports Claude 3 models (Opus, Sonnet, Haiku)
   - Uses official Anthropic Python SDK
   - Includes rate limiting and error handling

3. **AWS Bedrock Provider** (`bedrock_provider.py`)
   - Supports Claude, Llama, and Titan models on AWS Bedrock
   - Uses boto3 AWS SDK
   - Includes AWS credential management and region configuration
   - See `providers/AWS_BEDROCK_SETUP.md` for detailed setup instructions

4. **Local Provider** (`local_provider.py`)
   - Supports Ollama and llama.cpp
   - Uses OpenAI-compatible API endpoints
   - Enables fully offline operation for privacy

### Provider Factory

The `ProviderFactory` class simplifies provider instantiation:

```python
from backend.app.llm.providers import ProviderFactory, LLMConfig

# Create configuration
config = LLMConfig(
    provider="openai",
    model="gpt-4",
    api_key="your-api-key",
    temperature=0.7,
    max_tokens=1000
)

# Create provider instance
provider = ProviderFactory.create_provider(config)

# Generate completion
response = await provider.generate_completion(
    prompt="Write a professional summary for a software engineer",
    system_prompt="You are a professional CV writer"
)

print(response.content)
```

## Configuration

### LLMConfig Model

```python
class LLMConfig(BaseModel):
    provider: str              # "openai", "anthropic", "bedrock", or "local"
    api_key: Optional[str]     # API key for external providers
    model: str                 # Model identifier
    base_url: Optional[str]    # Base URL for local models
    temperature: float = 0.7   # Sampling temperature (0.0-2.0)
    max_tokens: int = 1000     # Maximum tokens to generate
    enabled: bool = True       # Whether provider is enabled
    timeout: int = 30          # Request timeout in seconds
    max_retries: int = 3       # Maximum retry attempts

class BedrockConfig(LLMConfig):
    aws_region: Optional[str] = "us-east-1"           # AWS region
    aws_access_key_id: Optional[str] = None           # AWS access key
    aws_secret_access_key: Optional[str] = None       # AWS secret key
    aws_session_token: Optional[str] = None           # AWS session token
```

## Usage Examples

### OpenAI Provider

```python
config = LLMConfig(
    provider="openai",
    model="gpt-4",
    api_key="sk-..."
)

provider = ProviderFactory.create_provider(config)

# Text completion
response = await provider.generate_completion(
    prompt="Expand these bullet points into a professional description",
    temperature=0.7
)

# Structured output
schema = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_skills": {"type": "array", "items": {"type": "string"}}
    }
}

structured_response = await provider.generate_structured_output(
    prompt="Extract key information from this CV section",
    schema=schema
)
```

### Anthropic Provider

```python
config = LLMConfig(
    provider="anthropic",
    model="claude-3-opus-20240229",
    api_key="sk-ant-..."
)

provider = ProviderFactory.create_provider(config)

response = await provider.generate_completion(
    prompt="Optimize this CV section for ATS systems",
    system_prompt="You are an expert in ATS optimization"
)
```

### Local Provider (Ollama)

```python
config = LLMConfig(
    provider="local",
    model="llama2",
    base_url="http://localhost:11434"
)

provider = ProviderFactory.create_provider(config)

# Check available models
models = await provider.list_available_models()
print(f"Available models: {models}")

# Generate completion
response = await provider.generate_completion(
    prompt="Improve this CV summary"
)
```

### AWS Bedrock Provider

```python
from backend.app.llm.providers import BedrockConfig

# Using environment variables or IAM role for credentials
config = BedrockConfig(
    provider="bedrock",
    model="claude-3-opus",  # Short name
    aws_region="us-east-1"
)

# Or with explicit credentials
config = BedrockConfig(
    provider="bedrock",
    model="anthropic.claude-3-sonnet-20240229-v1:0",  # Full model ID
    aws_region="us-west-2",
    aws_access_key_id="AKIA...",
    aws_secret_access_key="..."
)

provider = ProviderFactory.create_provider(config)

# Test connection
is_connected = await provider.test_connection()

# Generate completion
response = await provider.generate_completion(
    prompt="Write a professional summary",
    system_prompt="You are a CV expert"
)

# Supported models:
# Claude: claude-3-opus, claude-3-sonnet, claude-3-haiku, claude-2.1, claude-2
# Llama: llama2-13b, llama2-70b, llama3-8b, llama3-70b
# Titan: titan-text-express, titan-text-lite, titan-text-premier
```

For detailed Bedrock setup instructions, see `backend/app/llm/providers/AWS_BEDROCK_SETUP.md`.

## Error Handling

All providers include comprehensive error handling:

- **Rate Limiting**: Automatic retry with exponential backoff
- **Timeouts**: Configurable timeout with graceful failure
- **API Errors**: Detailed error messages with context
- **Validation**: Input validation before API calls

```python
try:
    response = await provider.generate_completion(prompt="...")
except ValueError as e:
    # Invalid input (empty prompt, invalid config, etc.)
    print(f"Validation error: {e}")
except RuntimeError as e:
    # API error, timeout, or retry exhaustion
    print(f"Generation failed: {e}")
```

## Testing

The module includes comprehensive unit tests in `backend/tests/test_llm_providers.py`:

- Configuration validation
- Provider factory functionality
- Provider-specific validation rules
- Error handling

Run tests:
```bash
source .venv/bin/activate
python -m pytest backend/tests/test_llm_providers.py -v
```

## Dependencies

Required packages (added to `backend/requirements.txt`):
- `openai==1.6.1` - OpenAI API client
- `anthropic==0.8.1` - Anthropic API client
- `boto3==1.34.34` - AWS SDK for Bedrock provider
- `botocore==1.34.34` - AWS SDK core library
- `httpx` - HTTP client for local providers (already included)

## Future Extensions

The abstraction layer is designed for easy extension:

1. **Custom Providers**: Register custom providers using `ProviderFactory.register_provider()`
2. **Additional Models**: Add support for new models by updating validation rules
3. **Caching**: Add response caching layer for repeated queries
4. **Streaming**: Extend interface to support streaming responses

## Privacy and Security

- **API Key Storage**: API keys should be encrypted at rest
- **Local Models**: Use local provider for complete privacy
- **Data Minimization**: Only send necessary context to external services
- **Consent Management**: Always obtain user consent before external API calls
