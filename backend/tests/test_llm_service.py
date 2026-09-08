"""
Tests for LLM Service

Tests for LLM configuration management, secure API key storage,
provider switching, and consent management.
"""

import pytest
import json
import os
from pathlib import Path
import tempfile
import shutil

from app.services.llm_service import LLMService
from app.models.llm_models import LLMProviderType, LLMConfigRequest


class TestLLMService:
    """Test LLM service functionality."""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def llm_service(self, temp_config_dir):
        """Create LLM service instance with temporary config directory."""
        return LLMService(config_dir=temp_config_dir)
    
    def test_service_initialization(self, llm_service):
        """Test that service initializes with default configuration."""
        config = llm_service.get_config()
        
        assert config.provider == LLMProviderType.LOCAL
        assert config.model == "llama2"
        assert config.enabled is False
        assert config.consent_given is False
        assert config.has_api_key is False
    
    def test_update_provider(self, llm_service):
        """Test updating provider type."""
        request = LLMConfigRequest(
            provider=LLMProviderType.OPENAI,
            model="gpt-3.5-turbo",
            api_key="test-key-123"
        )
        
        result = llm_service.update_config(request)
        
        assert result.provider == LLMProviderType.OPENAI
        assert result.model == "gpt-3.5-turbo"
        assert result.has_api_key is True
    
    def test_api_key_encryption(self, llm_service):
        """Test that API keys are encrypted in storage."""
        api_key = "test-secret-key-12345"
        
        request = LLMConfigRequest(
            provider=LLMProviderType.OPENAI,
            model="gpt-3.5-turbo",
            api_key=api_key
        )
        
        llm_service.update_config(request)
        
        # Read config file directly
        config_file = Path(llm_service.config_dir) / "llm_config.json"
        with open(config_file, "r") as f:
            stored_config = json.load(f)
        
        # API key should be encrypted (not plain text)
        assert stored_config["api_key"] != api_key
        assert len(stored_config["api_key"]) > len(api_key)
    
    def test_api_key_decryption(self, llm_service):
        """Test that API keys are correctly decrypted."""
        api_key = "test-secret-key-12345"
        
        request = LLMConfigRequest(
            provider=LLMProviderType.OPENAI,
            model="gpt-3.5-turbo",
            api_key=api_key
        )
        
        llm_service.update_config(request)
        
        # Create new service instance to test loading from file
        new_service = LLMService(config_dir=llm_service.config_dir)
        
        # API key should be decrypted correctly
        assert new_service._config.api_key == api_key
    
    def test_consent_management(self, llm_service):
        """Test consent granting and revoking."""
        # Initially no consent
        assert llm_service.has_consent() is False
        
        # Grant consent
        request = LLMConfigRequest(consent_given=True)
        llm_service.update_config(request)
        
        assert llm_service.has_consent() is True
        
        # Check consent log
        log = llm_service.get_consent_log()
        assert len(log) == 1
        assert log[0]["action"] == "consent_given"
        
        # Revoke consent
        llm_service.revoke_consent()
        
        assert llm_service.has_consent() is False
        
        # Check consent log updated
        log = llm_service.get_consent_log()
        assert len(log) == 2
        assert log[1]["action"] == "consent_revoked"
    
    def test_enable_disable_features(self, llm_service):
        """Test enabling and disabling LLM features."""
        # Initially disabled
        assert llm_service.is_enabled() is False
        
        # Configure with local provider (no consent needed)
        request = LLMConfigRequest(
            provider=LLMProviderType.LOCAL,
            model="llama2",
            base_url="http://localhost:11434"
        )
        llm_service.update_config(request)
        
        # Enable features
        llm_service.enable_llm_features()
        assert llm_service.is_enabled() is True
        
        # Disable features
        llm_service.disable_llm_features()
        assert llm_service.is_enabled() is False
    
    def test_requires_consent_for_external_providers(self, llm_service):
        """Test that external providers require consent."""
        # OpenAI requires consent
        request = LLMConfigRequest(
            provider=LLMProviderType.OPENAI,
            api_key="test-key",
            model="gpt-3.5-turbo"
        )
        llm_service.update_config(request)
        assert llm_service.requires_consent() is True
        
        # Anthropic requires consent
        request = LLMConfigRequest(
            provider=LLMProviderType.ANTHROPIC,
            api_key="test-key",
            model="claude-3-sonnet"
        )
        llm_service.update_config(request)
        assert llm_service.requires_consent() is True
        
        # Local does not require consent
        request = LLMConfigRequest(
            provider=LLMProviderType.LOCAL,
            model="llama2",
            base_url="http://localhost:11434"
        )
        llm_service.update_config(request)
        assert llm_service.requires_consent() is False
    
    def test_cannot_enable_without_consent(self, llm_service):
        """Test that external providers cannot be enabled without consent."""
        request = LLMConfigRequest(
            provider=LLMProviderType.OPENAI,
            model="gpt-3.5-turbo",
            api_key="test-key"
        )
        llm_service.update_config(request)
        
        # Try to enable without consent
        with pytest.raises(ValueError, match="consent"):
            llm_service.enable_llm_features()
    
    def test_can_enable_with_consent(self, llm_service):
        """Test that external providers can be enabled with consent."""
        request = LLMConfigRequest(
            provider=LLMProviderType.OPENAI,
            model="gpt-3.5-turbo",
            api_key="test-key",
            consent_given=True
        )
        llm_service.update_config(request)
        
        # Should be able to enable with consent
        llm_service.enable_llm_features()
        assert llm_service.is_enabled() is True
    
    def test_config_validation_openai(self, llm_service):
        """Test configuration validation for OpenAI provider."""
        # Missing API key
        request = LLMConfigRequest(
            provider=LLMProviderType.OPENAI,
            model="gpt-3.5-turbo"
        )
        
        with pytest.raises(ValueError, match="API key"):
            llm_service.update_config(request)
    
    def test_config_validation_temperature(self, llm_service):
        """Test temperature validation."""
        from pydantic import ValidationError
        
        # Temperature too high - should fail at Pydantic level
        with pytest.raises(ValidationError):
            request = LLMConfigRequest(temperature=3.0)
        
        # Temperature too low - should fail at Pydantic level
        with pytest.raises(ValidationError):
            request = LLMConfigRequest(temperature=-0.5)
    
    def test_config_validation_max_tokens(self, llm_service):
        """Test max_tokens validation."""
        from pydantic import ValidationError
        
        # Max tokens too high - should fail at Pydantic level
        with pytest.raises(ValidationError):
            request = LLMConfigRequest(max_tokens=10000)
        
        # Max tokens too low - should fail at Pydantic level
        with pytest.raises(ValidationError):
            request = LLMConfigRequest(max_tokens=0)
    
    def test_config_persistence(self, llm_service, temp_config_dir):
        """Test that configuration persists across service instances."""
        # Update configuration
        request = LLMConfigRequest(
            provider=LLMProviderType.ANTHROPIC,
            model="claude-3-sonnet",
            api_key="test-key-anthropic",
            temperature=0.5,
            max_tokens=2000,
            consent_given=True
        )
        llm_service.update_config(request)
        
        # Create new service instance
        new_service = LLMService(config_dir=temp_config_dir)
        config = new_service.get_config()
        
        # Configuration should be loaded from file
        assert config.provider == LLMProviderType.ANTHROPIC
        assert config.model == "claude-3-sonnet"
        assert config.temperature == 0.5
        assert config.max_tokens == 2000
        assert config.consent_given is True
        assert config.has_api_key is True
    
    def test_encryption_key_persistence(self, llm_service, temp_config_dir):
        """Test that encryption key persists and is reused."""
        key_file = Path(temp_config_dir) / ".llm_key"
        
        # Key file should be created
        assert key_file.exists()
        
        # Read key
        with open(key_file, "rb") as f:
            original_key = f.read()
        
        # Create new service instance
        new_service = LLMService(config_dir=temp_config_dir)
        
        # Key should be the same
        with open(key_file, "rb") as f:
            reused_key = f.read()
        
        assert original_key == reused_key
    
    def test_get_provider_when_disabled(self, llm_service):
        """Test that getting provider fails when features are disabled."""
        with pytest.raises(ValueError, match="disabled"):
            llm_service.get_provider()
    
    def test_get_provider_without_consent(self, llm_service):
        """Test that getting provider fails without consent for external providers."""
        request = LLMConfigRequest(
            provider=LLMProviderType.OPENAI,
            model="gpt-3.5-turbo",
            api_key="test-key",
            enabled=True
        )
        llm_service.update_config(request)
        
        with pytest.raises(ValueError, match="consent"):
            llm_service.get_provider()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
