"""Factory for creating LLM provider instances."""

from typing import Dict, Type
from .base import BaseLLMProvider, LLMConfig
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .local_provider import LocalProvider
from .bedrock_provider import BedrockProvider, BedrockConfig
from .claude_code_provider import ClaudeCodeProvider


class ProviderFactory:
    """Factory for creating LLM provider instances."""
    
    _providers: Dict[str, Type[BaseLLMProvider]] = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "local": LocalProvider,
        "bedrock": BedrockProvider,
        "claude_code": ClaudeCodeProvider,
    }
    
    @classmethod
    def create_provider(cls, config: LLMConfig) -> BaseLLMProvider:
        """Create an LLM provider instance based on configuration.
        
        Args:
            config: LLM provider configuration
            
        Returns:
            Initialized LLM provider instance
            
        Raises:
            ValueError: If provider type is not supported
        """
        provider_type = config.provider.lower()
        
        if provider_type not in cls._providers:
            raise ValueError(
                f"Unsupported provider: {provider_type}. "
                f"Supported providers: {', '.join(cls._providers.keys())}"
            )
        
        provider_class = cls._providers[provider_type]
        
        # Use BedrockConfig for bedrock provider
        if provider_type == "bedrock" and not isinstance(config, BedrockConfig):
            # Convert LLMConfig to BedrockConfig
            config_dict = config.model_dump()
            config = BedrockConfig(**config_dict)
        
        return provider_class(config)
    
    @classmethod
    def register_provider(cls, name: str, provider_class: Type[BaseLLMProvider]):
        """Register a custom provider.
        
        Args:
            name: Provider name
            provider_class: Provider class that extends BaseLLMProvider
        """
        cls._providers[name.lower()] = provider_class
    
    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """Get list of supported provider names.
        
        Returns:
            List of provider names
        """
        return list(cls._providers.keys())
