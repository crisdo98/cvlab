"""Base LLM provider interface for abstraction across different LLM services."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """Configuration for LLM provider."""
    provider: str = Field(..., description="Provider name (openai, anthropic, local)")
    api_key: Optional[str] = Field(None, description="API key for external providers")
    model: str = Field(..., description="Model identifier")
    base_url: Optional[str] = Field(None, description="Base URL for local models")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=1000, gt=0, description="Maximum tokens to generate")
    enabled: bool = Field(default=True, description="Whether the provider is enabled")
    timeout: int = Field(default=30, gt=0, description="Request timeout in seconds")
    max_retries: int = Field(default=3, ge=0, description="Maximum number of retry attempts")


class LLMResponse(BaseModel):
    """Response from LLM provider."""
    content: str = Field(..., description="Generated text content")
    model: str = Field(..., description="Model used for generation")
    provider: str = Field(..., description="Provider that generated the response")
    tokens_used: Optional[int] = Field(None, description="Number of tokens used")
    finish_reason: Optional[str] = Field(None, description="Reason for completion")


class StructuredLLMResponse(BaseModel):
    """Structured response from LLM provider."""
    data: Dict[str, Any] = Field(..., description="Structured data extracted from response")
    model: str = Field(..., description="Model used for generation")
    provider: str = Field(..., description="Provider that generated the response")
    tokens_used: Optional[int] = Field(None, description="Number of tokens used")


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers.
    
    This class defines the interface that all LLM providers must implement,
    enabling seamless switching between different LLM services (OpenAI, Anthropic, local models).
    """
    
    def __init__(self, config: LLMConfig):
        """Initialize the provider with configuration.
        
        Args:
            config: LLM provider configuration
        """
        self.config = config
        self._validate_config()
    
    @abstractmethod
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate text completion from prompt.
        
        Args:
            prompt: The user prompt to generate completion for
            system_prompt: Optional system prompt to set context
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse containing generated text and metadata
            
        Raises:
            ValueError: If prompt is empty or invalid
            RuntimeError: If generation fails after retries
        """
        pass
    
    @abstractmethod
    async def generate_structured_output(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> StructuredLLMResponse:
        """Generate structured JSON output matching the provided schema.
        
        Args:
            prompt: The user prompt to generate completion for
            schema: JSON schema that the output should conform to
            system_prompt: Optional system prompt to set context
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            **kwargs: Additional provider-specific parameters
            
        Returns:
            StructuredLLMResponse containing structured data and metadata
            
        Raises:
            ValueError: If prompt or schema is invalid
            RuntimeError: If generation fails after retries
        """
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Validate provider configuration.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid with specific error message
        """
        pass
    
    def _validate_config(self) -> None:
        """Internal validation called during initialization.
        
        Raises:
            ValueError: If configuration is invalid
        """
        if not self.validate_config():
            raise ValueError(f"Invalid configuration for {self.config.provider} provider")
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test connection to the LLM service.
        
        Returns:
            True if connection is successful
            
        Raises:
            RuntimeError: If connection test fails
        """
        pass
    
    def get_provider_name(self) -> str:
        """Get the provider name.
        
        Returns:
            Provider name string
        """
        return self.config.provider
    
    def is_enabled(self) -> bool:
        """Check if the provider is enabled.
        
        Returns:
            True if provider is enabled
        """
        return self.config.enabled
    
    async def generate_with_retry(
        self,
        generate_func,
        *args,
        **kwargs
    ) -> Any:
        """Execute generation with retry logic.
        
        Args:
            generate_func: The generation function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result from the generation function
            
        Raises:
            RuntimeError: If all retry attempts fail
        """
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                return await generate_func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    # Exponential backoff
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
                continue
        
        raise RuntimeError(
            f"Failed after {self.config.max_retries} attempts. Last error: {str(last_error)}"
        )
