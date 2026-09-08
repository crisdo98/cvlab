"""Tests for LLM provider abstraction layer."""

import pytest
from app.llm.providers import (
    LLMConfig,
    ProviderFactory,
    OpenAIProvider,
    AnthropicProvider,
    LocalProvider,
    BedrockProvider,
    BedrockConfig,
)


class TestLLMConfig:
    """Test LLM configuration model."""
    
    def test_config_creation_with_defaults(self):
        """Test creating config with default values."""
        config = LLMConfig(
            provider="openai",
            model="gpt-4",
            api_key="test-key"
        )
        
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.api_key == "test-key"
        assert config.temperature == 0.7
        assert config.max_tokens == 1000
        assert config.enabled is True
        assert config.timeout == 30
        assert config.max_retries == 3
    
    def test_config_creation_with_custom_values(self):
        """Test creating config with custom values."""
        config = LLMConfig(
            provider="anthropic",
            model="claude-3-opus",
            api_key="test-key",
            temperature=0.5,
            max_tokens=2000,
            enabled=False,
            timeout=60,
            max_retries=5
        )
        
        assert config.temperature == 0.5
        assert config.max_tokens == 2000
        assert config.enabled is False
        assert config.timeout == 60
        assert config.max_retries == 5
    
    def test_config_validation_temperature_range(self):
        """Test temperature validation."""
        # Valid temperature
        config = LLMConfig(
            provider="openai",
            model="gpt-4",
            api_key="test-key",
            temperature=1.5
        )
        assert config.temperature == 1.5
        
        # Invalid temperature (too high)
        with pytest.raises(ValueError):
            LLMConfig(
                provider="openai",
                model="gpt-4",
                api_key="test-key",
                temperature=3.0
            )
        
        # Invalid temperature (negative)
        with pytest.raises(ValueError):
            LLMConfig(
                provider="openai",
                model="gpt-4",
                api_key="test-key",
                temperature=-0.5
            )


class TestProviderFactory:
    """Test provider factory."""
    
    def test_create_openai_provider(self):
        """Test creating OpenAI provider."""
        config = LLMConfig(
            provider="openai",
            model="gpt-4",
            api_key="test-key"
        )
        
        provider = ProviderFactory.create_provider(config)
        assert isinstance(provider, OpenAIProvider)
        assert provider.get_provider_name() == "openai"
    
    def test_create_anthropic_provider(self):
        """Test creating Anthropic provider."""
        config = LLMConfig(
            provider="anthropic",
            model="claude-3-opus",
            api_key="test-key"
        )
        
        provider = ProviderFactory.create_provider(config)
        assert isinstance(provider, AnthropicProvider)
        assert provider.get_provider_name() == "anthropic"
    
    def test_create_local_provider(self):
        """Test creating local provider."""
        config = LLMConfig(
            provider="local",
            model="llama2",
            base_url="http://localhost:11434"
        )
        
        provider = ProviderFactory.create_provider(config)
        assert isinstance(provider, LocalProvider)
        assert provider.get_provider_name() == "local"
    
    def test_create_provider_case_insensitive(self):
        """Test provider creation is case insensitive."""
        config = LLMConfig(
            provider="OpenAI",
            model="gpt-4",
            api_key="test-key"
        )
        
        provider = ProviderFactory.create_provider(config)
        assert isinstance(provider, OpenAIProvider)
    
    def test_create_unsupported_provider(self):
        """Test creating unsupported provider raises error."""
        config = LLMConfig(
            provider="unsupported",
            model="test-model",
            api_key="test-key"
        )
        
        with pytest.raises(ValueError, match="Unsupported provider"):
            ProviderFactory.create_provider(config)
    
    def test_get_supported_providers(self):
        """Test getting list of supported providers."""
        providers = ProviderFactory.get_supported_providers()
        
        assert "openai" in providers
        assert "anthropic" in providers
        assert "local" in providers
        assert "bedrock" in providers
        assert len(providers) == 4


class TestOpenAIProvider:
    """Test OpenAI provider."""
    
    def test_validate_config_success(self):
        """Test successful config validation."""
        config = LLMConfig(
            provider="openai",
            model="gpt-4",
            api_key="test-key"
        )
        
        provider = OpenAIProvider(config)
        assert provider.validate_config() is True
    
    def test_validate_config_missing_api_key(self):
        """Test validation fails without API key."""
        config = LLMConfig(
            provider="openai",
            model="gpt-4"
        )
        
        with pytest.raises(ValueError, match="API key is required"):
            OpenAIProvider(config)
    
    def test_validate_config_missing_model(self):
        """Test validation fails without model."""
        config = LLMConfig(
            provider="openai",
            model="",
            api_key="test-key"
        )
        
        with pytest.raises(ValueError, match="Model name is required"):
            OpenAIProvider(config)
    
    def test_validate_config_invalid_model(self):
        """Test validation fails with invalid model."""
        config = LLMConfig(
            provider="openai",
            model="invalid-model",
            api_key="test-key"
        )
        
        with pytest.raises(ValueError, match="Invalid OpenAI model"):
            OpenAIProvider(config)
    
    def test_is_enabled(self):
        """Test checking if provider is enabled."""
        config = LLMConfig(
            provider="openai",
            model="gpt-4",
            api_key="test-key",
            enabled=True
        )
        
        provider = OpenAIProvider(config)
        assert provider.is_enabled() is True
        
        config.enabled = False
        provider = OpenAIProvider(config)
        assert provider.is_enabled() is False


class TestAnthropicProvider:
    """Test Anthropic provider."""
    
    def test_validate_config_success(self):
        """Test successful config validation."""
        config = LLMConfig(
            provider="anthropic",
            model="claude-3-opus",
            api_key="test-key"
        )
        
        provider = AnthropicProvider(config)
        assert provider.validate_config() is True
    
    def test_validate_config_missing_api_key(self):
        """Test validation fails without API key."""
        config = LLMConfig(
            provider="anthropic",
            model="claude-3-opus"
        )
        
        with pytest.raises(ValueError, match="API key is required"):
            AnthropicProvider(config)
    
    def test_validate_config_invalid_model(self):
        """Test validation fails with invalid model."""
        config = LLMConfig(
            provider="anthropic",
            model="invalid-model",
            api_key="test-key"
        )
        
        with pytest.raises(ValueError, match="Invalid Anthropic model"):
            AnthropicProvider(config)


class TestLocalProvider:
    """Test local provider."""
    
    def test_validate_config_success(self):
        """Test successful config validation."""
        config = LLMConfig(
            provider="local",
            model="llama2",
            base_url="http://localhost:11434"
        )
        
        provider = LocalProvider(config)
        assert provider.validate_config() is True
    
    def test_validate_config_missing_base_url(self):
        """Test validation fails without base URL."""
        config = LLMConfig(
            provider="local",
            model="llama2"
        )
        
        with pytest.raises(ValueError, match="Base URL is required"):
            LocalProvider(config)
    
    def test_validate_config_invalid_base_url(self):
        """Test validation fails with invalid base URL."""
        config = LLMConfig(
            provider="local",
            model="llama2",
            base_url="invalid-url"
        )
        
        with pytest.raises(ValueError, match="Invalid base URL"):
            LocalProvider(config)
    
    def test_validate_config_missing_model(self):
        """Test validation fails without model."""
        config = LLMConfig(
            provider="local",
            model="",
            base_url="http://localhost:11434"
        )
        
        with pytest.raises(ValueError, match="Model name is required"):
            LocalProvider(config)



class TestBedrockConfig:
    """Test Bedrock configuration model."""
    
    def test_bedrock_config_creation_with_defaults(self):
        """Test creating Bedrock config with default values."""
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-opus",
            aws_region="us-east-1"
        )
        
        assert config.provider == "bedrock"
        assert config.model == "claude-3-opus"
        assert config.aws_region == "us-east-1"
        assert config.aws_access_key_id is None
        assert config.aws_secret_access_key is None
        assert config.aws_session_token is None
    
    def test_bedrock_config_with_credentials(self):
        """Test creating Bedrock config with explicit credentials."""
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-sonnet",
            aws_region="us-west-2",
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key",
            aws_session_token="test-session-token"
        )
        
        assert config.aws_region == "us-west-2"
        assert config.aws_access_key_id == "test-access-key"
        assert config.aws_secret_access_key == "test-secret-key"
        assert config.aws_session_token == "test-session-token"


class TestBedrockProvider:
    """Test AWS Bedrock provider."""
    
    def test_validate_config_success(self):
        """Test successful config validation."""
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-opus",
            aws_region="us-east-1"
        )
        
        # Skip if boto3 not available
        try:
            provider = BedrockProvider(config)
            assert provider.validate_config() is True
        except ImportError:
            pytest.skip("boto3 not installed")
    
    def test_validate_config_missing_model(self):
        """Test validation fails without model."""
        config = BedrockConfig(
            provider="bedrock",
            model="",
            aws_region="us-east-1"
        )
        
        try:
            with pytest.raises(ValueError, match="Model name is required"):
                BedrockProvider(config)
        except ImportError:
            pytest.skip("boto3 not installed")
    
    def test_model_id_resolution_short_names(self):
        """Test model ID resolution from short names."""
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-opus",
            aws_region="us-east-1"
        )
        
        try:
            provider = BedrockProvider(config)
            assert provider.model_id == "anthropic.claude-3-opus-20240229-v1:0"
        except ImportError:
            pytest.skip("boto3 not installed")
    
    def test_model_id_resolution_full_id(self):
        """Test model ID resolution with full ID."""
        config = BedrockConfig(
            provider="bedrock",
            model="anthropic.claude-3-sonnet-20240229-v1:0",
            aws_region="us-east-1"
        )
        
        try:
            provider = BedrockProvider(config)
            assert provider.model_id == "anthropic.claude-3-sonnet-20240229-v1:0"
        except ImportError:
            pytest.skip("boto3 not installed")
    
    def test_model_family_detection_claude(self):
        """Test model family detection for Claude models."""
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-opus",
            aws_region="us-east-1"
        )
        
        try:
            provider = BedrockProvider(config)
            assert provider._get_model_family() == "claude"
        except ImportError:
            pytest.skip("boto3 not installed")
    
    def test_model_family_detection_llama(self):
        """Test model family detection for Llama models."""
        config = BedrockConfig(
            provider="bedrock",
            model="llama2-70b",
            aws_region="us-east-1"
        )
        
        try:
            provider = BedrockProvider(config)
            assert provider._get_model_family() == "llama"
        except ImportError:
            pytest.skip("boto3 not installed")
    
    def test_model_family_detection_titan(self):
        """Test model family detection for Titan models."""
        config = BedrockConfig(
            provider="bedrock",
            model="titan-text-express",
            aws_region="us-east-1"
        )
        
        try:
            provider = BedrockProvider(config)
            assert provider._get_model_family() == "titan"
        except ImportError:
            pytest.skip("boto3 not installed")
    
    def test_build_request_body_claude(self):
        """Test request body building for Claude models."""
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-opus",
            aws_region="us-east-1"
        )
        
        try:
            provider = BedrockProvider(config)
            body = provider._build_request_body(
                prompt="Test prompt",
                system_prompt="Test system",
                temperature=0.5,
                max_tokens=100
            )
            
            assert body["anthropic_version"] == "bedrock-2023-05-31"
            assert body["messages"][0]["role"] == "user"
            assert body["messages"][0]["content"] == "Test prompt"
            assert body["system"] == "Test system"
            assert body["temperature"] == 0.5
            assert body["max_tokens"] == 100
        except ImportError:
            pytest.skip("boto3 not installed")
    
    def test_build_request_body_llama(self):
        """Test request body building for Llama models."""
        config = BedrockConfig(
            provider="bedrock",
            model="llama2-70b",
            aws_region="us-east-1"
        )
        
        try:
            provider = BedrockProvider(config)
            body = provider._build_request_body(
                prompt="Test prompt",
                system_prompt="Test system",
                temperature=0.5,
                max_tokens=100
            )
            
            assert "prompt" in body
            assert "<s>[INST]" in body["prompt"]
            assert "<<SYS>>" in body["prompt"]
            assert "Test system" in body["prompt"]
            assert "Test prompt" in body["prompt"]
            assert body["temperature"] == 0.5
            assert body["max_gen_len"] == 100
        except ImportError:
            pytest.skip("boto3 not installed")
    
    def test_build_request_body_titan(self):
        """Test request body building for Titan models."""
        config = BedrockConfig(
            provider="bedrock",
            model="titan-text-express",
            aws_region="us-east-1"
        )
        
        try:
            provider = BedrockProvider(config)
            body = provider._build_request_body(
                prompt="Test prompt",
                temperature=0.5,
                max_tokens=100
            )
            
            assert body["inputText"] == "Test prompt"
            assert body["textGenerationConfig"]["temperature"] == 0.5
            assert body["textGenerationConfig"]["maxTokenCount"] == 100
        except ImportError:
            pytest.skip("boto3 not installed")
    
    def test_factory_creates_bedrock_provider(self):
        """Test factory creates Bedrock provider."""
        config = LLMConfig(
            provider="bedrock",
            model="claude-3-opus"
        )
        
        try:
            provider = ProviderFactory.create_provider(config)
            assert isinstance(provider, BedrockProvider)
            assert provider.get_provider_name() == "bedrock"
        except ImportError:
            pytest.skip("boto3 not installed")
    
    def test_factory_converts_to_bedrock_config(self):
        """Test factory converts LLMConfig to BedrockConfig."""
        config = LLMConfig(
            provider="bedrock",
            model="claude-3-opus",
            temperature=0.8,
            max_tokens=2000
        )
        
        try:
            provider = ProviderFactory.create_provider(config)
            assert isinstance(provider, BedrockProvider)
            assert provider.config.temperature == 0.8
            assert provider.config.max_tokens == 2000
        except ImportError:
            pytest.skip("boto3 not installed")
