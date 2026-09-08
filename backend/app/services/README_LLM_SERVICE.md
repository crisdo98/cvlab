# LLM Service Documentation

## Overview

The LLM Service provides centralized management of LLM configuration, secure API key storage, provider switching, consent management, and feature toggles for all LLM-powered functionality in the CV Web Application.

## Features

### 1. Secure API Key Storage

- **Encryption**: API keys are encrypted using Fernet (symmetric encryption) before storage
- **Key Management**: Encryption keys are generated once and stored securely with restrictive file permissions (0o600)
- **Automatic Decryption**: Keys are automatically decrypted when loading configuration
- **No Plain Text**: API keys are never stored in plain text on disk

### 2. Provider Management

Supports multiple LLM providers:
- **OpenAI**: GPT-3.5, GPT-4 models via OpenAI API
- **Anthropic**: Claude models via Anthropic API
- **Local**: Ollama, llama.cpp for privacy-focused deployments

Provider switching is seamless - just update the configuration and the service handles provider initialization.

### 3. Configuration Validation

Comprehensive validation ensures:
- Required fields are present for each provider type
- Temperature is within valid range (0.0 - 2.0)
- Max tokens is within valid range (1 - 8000)
- Provider-specific requirements are met (e.g., API keys for external providers)

### 4. Consent Management

For external LLM providers (OpenAI, Anthropic):
- **Consent Required**: User must explicitly grant consent before data is sent to external services
- **Audit Logging**: All consent grants and revocations are logged with timestamps
- **Consent Checks**: Automatic consent verification before external API calls
- **Easy Revocation**: Users can revoke consent at any time

### 5. Feature Toggles

- **Global Enable/Disable**: Turn all LLM features on or off with a single toggle
- **Graceful Degradation**: Core CV functionality remains available when LLM features are disabled
- **Validation on Enable**: Configuration is validated before enabling features

## Usage

### Basic Configuration

```python
from app.services.llm_service import get_llm_service
from app.models.llm_models import LLMConfigRequest, LLMProviderType

# Get service instance
llm_service = get_llm_service()

# Configure OpenAI provider
config_request = LLMConfigRequest(
    provider=LLMProviderType.OPENAI,
    api_key="your-api-key-here",
    model="gpt-3.5-turbo",
    temperature=0.7,
    max_tokens=1000,
    consent_given=True
)

llm_service.update_config(config_request)
```

### Getting a Provider

```python
# Enable LLM features
llm_service.enable_llm_features()

# Get provider instance
provider = llm_service.get_provider()

# Use provider for LLM operations
result = await provider.generate_completion("Your prompt here")
```

### Consent Management

```python
# Check if consent is required
if llm_service.requires_consent():
    # Grant consent
    llm_service.update_config(LLMConfigRequest(consent_given=True))

# Check consent status
has_consent = llm_service.has_consent()

# Revoke consent
llm_service.revoke_consent()

# Get consent audit log
log = llm_service.get_consent_log()
```

### Feature Toggles

```python
# Check if LLM features are enabled
is_enabled = llm_service.is_enabled()

# Enable LLM features
llm_service.enable_llm_features()

# Disable LLM features
llm_service.disable_llm_features()
```

## API Endpoints

The LLM router provides REST API endpoints for configuration and consent management:

### Configuration

- `GET /api/llm/config` - Get current configuration (without sensitive data)
- `PUT /api/llm/config` - Update configuration
- `GET /api/llm/status` - Get LLM service status

### Consent Management

- `POST /api/llm/consent/grant` - Grant consent for external services
- `POST /api/llm/consent/revoke` - Revoke consent
- `GET /api/llm/consent/log` - Get consent audit log

### Feature Toggles

- `POST /api/llm/enable` - Enable LLM features
- `POST /api/llm/disable` - Disable LLM features

### Testing

- `POST /api/llm/test-connection` - Test LLM provider connection

## File Structure

Configuration files are stored in `data/config/`:

```
data/config/
├── llm_config.json          # LLM configuration (with encrypted API keys)
├── llm_consent_log.json     # Consent audit log
└── .llm_key                 # Encryption key (restrictive permissions)
```

## Security Considerations

1. **Encryption Keys**: Stored with 0o600 permissions (owner read/write only)
2. **Configuration Files**: Stored with 0o600 permissions
3. **API Keys**: Never logged or exposed in API responses
4. **Consent Tracking**: All external data transmission requires explicit consent
5. **Audit Trail**: Complete log of consent grants and revocations

## Privacy Features

- **Local-First**: Supports local LLM models for complete privacy
- **Explicit Consent**: Clear indication when data leaves the system
- **Consent Revocation**: Easy to revoke consent and disable external services
- **Audit Logging**: Complete transparency of consent history
- **Feature Disable**: Can completely disable LLM features while maintaining core functionality

## Error Handling

The service provides clear error messages for:
- Missing required configuration
- Invalid configuration values
- Missing consent for external providers
- Disabled features
- Provider initialization failures

## Testing

Comprehensive test suite covers:
- Configuration management
- API key encryption/decryption
- Consent management
- Feature toggles
- Provider switching
- Configuration validation
- Configuration persistence

Run tests:
```bash
python -m pytest backend/tests/test_llm_service.py -v
```

## Dependencies

- `cryptography`: For secure API key encryption
- `pydantic`: For configuration validation
- `fastapi`: For REST API endpoints

## Future Enhancements

Potential future improvements:
- Per-feature granular controls (enable/disable specific LLM features)
- Multiple API key support (for different providers)
- Usage tracking and rate limiting
- Cost estimation and budgeting
- Provider fallback chains
- Configuration profiles (development, production, etc.)
