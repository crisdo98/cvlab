"""
LLM Service

Service for managing LLM configuration, provider switching, and secure API key storage.
Handles consent management and feature toggles for LLM functionality.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
import base64
import hashlib

logger = logging.getLogger(__name__)

from ..models.llm_models import (
    LLMConfig,
    LLMConfigRequest,
    LLMConfigResponse,
    LLMProviderType
)
from ..llm.providers.base import BaseLLMProvider
from ..llm.providers.openai_provider import OpenAIProvider
from ..llm.providers.anthropic_provider import AnthropicProvider
from ..llm.providers.bedrock_provider import BedrockProvider, BedrockConfig
from ..llm.providers.local_provider import LocalProvider


class LLMService:
    """
    Service for managing LLM configuration and providers.
    
    Handles:
    - Secure API key storage with encryption
    - Provider switching and initialization
    - Configuration validation
    - Consent management
    - Feature toggles
    """
    
    def __init__(self, config_dir: str = "data/config"):
        """
        Initialize LLM service.
        
        Args:
            config_dir: Directory for storing configuration files
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_file = self.config_dir / "llm_config.json"
        self.consent_log_file = self.config_dir / "llm_consent_log.json"
        
        # Initialize encryption key
        self._encryption_key = self._get_or_create_encryption_key()
        self._cipher = Fernet(self._encryption_key)
        
        # Load or create default configuration
        self._config: Optional[LLMConfig] = None
        self._provider: Optional[BaseLLMProvider] = None
        self._load_config()
    
    def _get_or_create_encryption_key(self) -> bytes:
        """
        Get or create encryption key for API key storage.
        
        Returns:
            Encryption key bytes
        """
        key_file = self.config_dir / ".llm_key"
        
        if key_file.exists():
            with open(key_file, "rb") as f:
                return f.read()
        
        # Generate new key
        key = Fernet.generate_key()
        
        # Store key securely
        with open(key_file, "wb") as f:
            f.write(key)
        
        # Set restrictive permissions (owner read/write only)
        os.chmod(key_file, 0o600)
        
        return key
    
    def _encrypt_api_key(self, api_key: str) -> str:
        """
        Encrypt API key for secure storage.
        
        Args:
            api_key: Plain text API key
            
        Returns:
            Encrypted API key (base64 encoded)
        """
        if not api_key:
            return ""
        
        encrypted = self._cipher.encrypt(api_key.encode())
        return base64.b64encode(encrypted).decode()
    
    def _decrypt_api_key(self, encrypted_key: str) -> str:
        """
        Decrypt API key from storage.
        
        Args:
            encrypted_key: Encrypted API key (base64 encoded)
            
        Returns:
            Plain text API key
        """
        if not encrypted_key:
            return ""
        
        try:
            encrypted_bytes = base64.b64decode(encrypted_key.encode())
            decrypted = self._cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception:
            return ""
    
    def _load_config(self) -> None:
        """Load configuration from file or create default."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    config_data = json.load(f)
                
                # Decrypt API key if present
                if config_data.get("api_key"):
                    config_data["api_key_encrypted"] = config_data["api_key"]
                    config_data["api_key"] = self._decrypt_api_key(config_data["api_key"])
                
                self._config = LLMConfig(**config_data)
            except Exception as e:
                print(f"Error loading LLM config: {e}")
                self._config = self._create_default_config()
        else:
            self._config = self._create_default_config()
            self._save_config()
    
    def _create_default_config(self) -> LLMConfig:
        """
        Create default LLM configuration.
        
        Returns:
            Default LLM configuration
        """
        return LLMConfig(
            provider=LLMProviderType.LOCAL,
            model="llama2",
            enabled=False,  # Disabled by default until user configures
            consent_given=False
        )
    
    def _save_config(self) -> None:
        """Save configuration to file."""
        if not self._config:
            return
        
        config_dict = self._config.model_dump()
        
        # Encrypt API key before saving
        if config_dict.get("api_key"):
            config_dict["api_key"] = self._encrypt_api_key(config_dict["api_key"])
        
        with open(self.config_file, "w") as f:
            json.dump(config_dict, f, indent=2)
        
        # Set restrictive permissions
        os.chmod(self.config_file, 0o600)
    
    def get_config(self) -> LLMConfigResponse:
        """
        Get current LLM configuration (without sensitive data).
        
        Returns:
            LLM configuration response
        """
        if not self._config:
            self._config = self._create_default_config()
        
        return LLMConfigResponse(
            provider=self._config.provider,
            model=self._config.model,
            base_url=self._config.base_url,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
            enabled=self._config.enabled,
            consent_given=self._config.consent_given,
            has_api_key=bool(self._config.api_key)
        )
    
    def update_config(self, request: LLMConfigRequest) -> LLMConfigResponse:
        """
        Update LLM configuration.
        
        Args:
            request: Configuration update request
            
        Returns:
            Updated configuration response
            
        Raises:
            ValueError: If configuration is invalid
        """
        if not self._config:
            self._config = self._create_default_config()
        
        # Update fields that are provided
        if request.provider is not None:
            self._config.provider = request.provider
            # Reset provider instance when provider type changes
            self._provider = None
        
        if request.api_key is not None:
            self._config.api_key = request.api_key
            # Reset provider instance when API key changes
            self._provider = None
        
        if request.model is not None:
            self._config.model = request.model
        
        if request.base_url is not None:
            self._config.base_url = request.base_url
        
        if request.temperature is not None:
            self._config.temperature = request.temperature
        
        if request.max_tokens is not None:
            self._config.max_tokens = request.max_tokens
        
        if request.enabled is not None:
            self._config.enabled = request.enabled
        
        if request.consent_given is not None:
            self._config.consent_given = request.consent_given
            # Log consent change
            if request.consent_given:
                self._log_consent_given()
        
        # Validate configuration
        self._validate_config()
        
        # Save updated configuration
        self._save_config()
        
        return self.get_config()
    
    def _validate_config(self) -> None:
        """
        Validate current configuration.
        
        Raises:
            ValueError: If configuration is invalid
        """
        if not self._config:
            raise ValueError("No configuration loaded")
        
        # Validate provider-specific requirements
        if self._config.provider == LLMProviderType.OPENAI:
            if not self._config.api_key:
                raise ValueError("OpenAI provider requires API key")
            if not self._config.model:
                raise ValueError("OpenAI provider requires model name")
        
        elif self._config.provider == LLMProviderType.ANTHROPIC:
            if not self._config.api_key:
                raise ValueError("Anthropic provider requires API key")
            if not self._config.model:
                raise ValueError("Anthropic provider requires model name")
        
        elif self._config.provider == LLMProviderType.BEDROCK:
            if not self._config.model:
                raise ValueError("Bedrock provider requires model name")
            # AWS credentials are optional - can use IAM role
            # Region defaults to us-east-1 if not specified
        
        elif self._config.provider == LLMProviderType.LOCAL:
            if not self._config.model:
                raise ValueError("Local provider requires model name")

        elif self._config.provider == LLMProviderType.CLAUDE_CODE:
            if not self._config.model:
                raise ValueError("Claude Code provider requires model name")
            # No API key: credentials come from Claude Code itself.
        
        # Validate temperature range
        if not (0.0 <= self._config.temperature <= 2.0):
            raise ValueError("Temperature must be between 0.0 and 2.0")
        
        # Validate max_tokens
        if not (1 <= self._config.max_tokens <= 8000):
            raise ValueError("Max tokens must be between 1 and 8000")
    
    def get_provider(self) -> BaseLLMProvider:
        """
        Get initialized LLM provider instance.
        
        Returns:
            Initialized LLM provider
            
        Raises:
            ValueError: If LLM features are disabled or configuration is invalid
        """
        if not self._config or not self._config.enabled:
            raise ValueError("LLM features are disabled")
        
        # Check consent for external providers
        if self._config.provider in [
            LLMProviderType.OPENAI,
            LLMProviderType.ANTHROPIC,
            LLMProviderType.BEDROCK,
            LLMProviderType.CLAUDE_CODE,
        ]:
            if not self._config.consent_given:
                raise ValueError(
                    f"User consent required for external LLM provider: {self._config.provider.value}"
                )
        
        # Return cached provider if available
        if self._provider:
            return self._provider
        
        # Initialize provider based on configuration
        if self._config.provider == LLMProviderType.OPENAI:
            from ..llm.providers.base import LLMConfig as ProviderConfig
            provider_config = ProviderConfig(
                provider="openai",
                api_key=self._config.api_key,
                model=self._config.model,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens
            )
            self._provider = OpenAIProvider(provider_config)
        
        elif self._config.provider == LLMProviderType.ANTHROPIC:
            from ..llm.providers.base import LLMConfig as ProviderConfig
            provider_config = ProviderConfig(
                provider="anthropic",
                api_key=self._config.api_key,
                model=self._config.model,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens
            )
            self._provider = AnthropicProvider(provider_config)
        
        elif self._config.provider == LLMProviderType.BEDROCK:
            # Get AWS credentials from environment or config
            aws_region = os.getenv('AWS_REGION', 'us-east-1')
            aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            aws_session_token = os.getenv('AWS_SESSION_TOKEN')
            
            bedrock_config = BedrockConfig(
                provider="bedrock",
                model=self._config.model,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                aws_region=aws_region,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                aws_session_token=aws_session_token
            )
            self._provider = BedrockProvider(bedrock_config)
        
        elif self._config.provider == LLMProviderType.LOCAL:
            from ..llm.providers.base import LLMConfig as ProviderConfig
            provider_config = ProviderConfig(
                provider="local",
                model=self._config.model,
                base_url=self._config.base_url,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens
            )
            self._provider = LocalProvider(provider_config)

        elif self._config.provider == LLMProviderType.CLAUDE_CODE:
            from ..llm.providers.base import LLMConfig as ProviderConfig
            from ..llm.providers.claude_code_provider import ClaudeCodeProvider
            provider_config = ProviderConfig(
                # The stored credential is a Claude Code OAuth token rather than
                # an API key, but it travels in the same encrypted field. Empty
                # is fine: the provider then falls back to CLAUDE_CODE_OAUTH_TOKEN
                # in the server's environment.
                provider="claude_code",
                api_key=self._config.api_key,
                model=self._config.model,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens
            )
            self._provider = ClaudeCodeProvider(provider_config)

        else:
            raise ValueError(f"Unsupported provider: {self._config.provider}")
        
        # Validate provider configuration
        if not self._provider.validate_config():
            raise ValueError(f"Invalid configuration for provider: {self._config.provider.value}")
        
        return self._provider
    
    def is_enabled(self) -> bool:
        """
        Check if LLM features are enabled.
        
        Returns:
            True if LLM features are enabled
        """
        return bool(self._config and self._config.enabled)
    
    def requires_consent(self) -> bool:
        """
        Check if current provider requires user consent.
        
        Returns:
            True if consent is required
        """
        if not self._config:
            return False
        
        # Claude Code sends CV content to Anthropic just as the API providers
        # do — the credential differs, the data leaving the machine does not.
        return self._config.provider in [
            LLMProviderType.OPENAI,
            LLMProviderType.ANTHROPIC,
            LLMProviderType.BEDROCK,
            LLMProviderType.CLAUDE_CODE,
        ]
    
    def has_consent(self, service_type: Optional[str] = None) -> bool:
        """
        Check if user has given consent for external services.
        
        Args:
            service_type: Optional service type to check consent for.
                         If None, checks general LLM consent.
                         Supported types: "llm"
        
        Returns:
            True if consent has been given for the specified service
        """
        return bool(self._config and self._config.consent_given)
    
    def _log_consent_given(self) -> None:
        """Log consent given event for audit trail."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "provider": self._config.provider.value if self._config else "unknown",
            "action": "consent_given"
        }
        
        # Load existing log
        consent_log = []
        if self.consent_log_file.exists():
            try:
                with open(self.consent_log_file, "r") as f:
                    consent_log = json.load(f)
            except Exception:
                consent_log = []
        
        # Append new entry
        consent_log.append(log_entry)
        
        # Save log
        with open(self.consent_log_file, "w") as f:
            json.dump(consent_log, f, indent=2)
        
        # Set restrictive permissions
        os.chmod(self.consent_log_file, 0o600)
    
    def get_consent_log(self) -> list[Dict[str, Any]]:
        """
        Get consent audit log.
        
        Returns:
            List of consent log entries
        """
        if not self.consent_log_file.exists():
            return []
        
        try:
            with open(self.consent_log_file, "r") as f:
                return json.load(f)
        except Exception:
            return []
    
    def revoke_consent(self, service_type: Optional[str] = None) -> None:
        """
        Revoke consent for external services.
        
        Args:
            service_type: Optional service type to revoke consent for.
                         If None, revokes general LLM consent.
                         Supported types: "llm"
        """
        if self._config:
            self._config.consent_given = False
            self._save_config()
            
            # Log consent revocation
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "provider": self._config.provider.value,
                "action": "consent_revoked"
            }
            
            consent_log = self.get_consent_log()
            consent_log.append(log_entry)
            
            with open(self.consent_log_file, "w") as f:
                json.dump(consent_log, f, indent=2)
    
    def disable_llm_features(self) -> None:
        """Disable all LLM features."""
        if self._config:
            self._config.enabled = False
            self._save_config()
            self._provider = None
    
    def enable_llm_features(self) -> None:
        """
        Enable LLM features.
        
        Raises:
            ValueError: If configuration is invalid or consent is required but not given
        """
        if not self._config:
            raise ValueError("No configuration loaded")
        
        # Validate configuration before enabling
        self._validate_config()
        
        # Check consent for external providers
        if self.requires_consent() and not self.has_consent():
            raise ValueError("User consent required for external LLM provider")
        
        self._config.enabled = True
        self._save_config()


# Global LLM service instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """
    Get global LLM service instance.
    
    Returns:
        LLM service instance
    """
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
