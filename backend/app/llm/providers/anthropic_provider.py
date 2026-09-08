"""Anthropic Claude LLM provider implementation."""

import json
from typing import Dict, Any, Optional
from anthropic import AsyncAnthropic, APIError, RateLimitError, APITimeoutError, AnthropicError
from .base import BaseLLMProvider, LLMConfig, LLMResponse, StructuredLLMResponse


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API provider implementation.
    
    Supports Claude 3 models (Opus, Sonnet, Haiku).
    """
    
    # Model alias to API name mapping
    MODEL_ALIAS_MAP = {
        # Claude 4.5 models
        "claude-sonnet-4.5": "claude-sonnet-4-5-20250929",
        "claude-haiku-4.5": "claude-haiku-4-5-20251001",
        "claude-opus-4.5": "claude-opus-4-5-20251101",
        
        # Claude 4 models
        "claude-opus-4.1": "claude-opus-4-1-20250827",
        "claude-sonnet-4": "claude-sonnet-4-20250514",
        "claude-opus-4": "claude-opus-4-20250514",
        
        # Claude 3.5 models
        "claude-3.5-sonnet": "claude-3-5-sonnet-20241022",
        "claude-3.5-haiku": "claude-3-5-haiku-20241022",
        
        # Claude 3 models
        "claude-3-opus": "claude-3-opus-20240229",
        "claude-3-sonnet": "claude-3-sonnet-20240229",
        "claude-3-haiku": "claude-3-haiku-20240307",
    }
    
    def __init__(self, config: LLMConfig):
        """Initialize Anthropic provider.
        
        Args:
            config: LLM provider configuration with Anthropic API key
        """
        super().__init__(config)
        
        # Map alias to actual API model name
        self.api_model = self.MODEL_ALIAS_MAP.get(config.model, config.model)
        
        self.client = AsyncAnthropic(
            api_key=config.api_key,
            timeout=config.timeout
        )
    
    def validate_config(self) -> bool:
        """Validate Anthropic provider configuration.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        if not self.config.api_key:
            raise ValueError("Anthropic API key is required")
        
        if not self.config.model:
            raise ValueError("Model name is required")
        
        # Validate model name format - accept aliases
        valid_patterns = [
            "claude-sonnet-4.5", "claude-haiku-4.5", "claude-opus-4.5",  # Claude 4.5 family
            "claude-opus-4.1", "claude-sonnet-4", "claude-opus-4",  # Claude 4 family
            "claude-3.5-sonnet", "claude-3.5-haiku",  # Claude 3.5 family
            "claude-3-opus", "claude-3-sonnet", "claude-3-haiku",  # Claude 3 family
            "claude-2.1", "claude-2",  # Claude 2 family
            "claude-sonnet-4-5", "claude-haiku-4-5", "claude-opus-4-5",  # API names for 4.5
            "claude-opus-4-1", "claude-sonnet-4-", "claude-opus-4-",  # API names for 4
            "claude-3-5-sonnet", "claude-3-5-haiku",  # API names for 3.5
        ]
        if not any(self.config.model.startswith(pattern) for pattern in valid_patterns):
            raise ValueError(
                f"Invalid Anthropic model: {self.config.model}. "
                f"Must be a valid Claude model (e.g., claude-sonnet-4.5, claude-3.5-sonnet)"
            )
        
        return True
    
    async def test_connection(self) -> bool:
        """Test connection to Anthropic API.
        
        Returns:
            True if connection is successful
            
        Raises:
            RuntimeError: If connection test fails
        """
        try:
            # Make a minimal API call to test connection
            from anthropic import Anthropic
            sync_client = Anthropic(api_key=self.config.api_key)
            response = sync_client.messages.create(
                model=self.api_model,
                max_tokens=5,
                messages=[{"role": "user", "content": "test"}]
            )
            return True
        except AnthropicError as e:
            raise RuntimeError(f"Anthropic connection test failed: {str(e)}")
    
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate text completion using Anthropic API.
        
        Args:
            prompt: The user prompt to generate completion for
            system_prompt: Optional system prompt to set context
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            **kwargs: Additional Anthropic-specific parameters
            
        Returns:
            LLMResponse containing generated text and metadata
            
        Raises:
            ValueError: If prompt is empty or invalid
            RuntimeError: If generation fails after retries
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        
        # Build messages
        messages = [{"role": "user", "content": prompt}]
        
        # Use config defaults if not overridden
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens
        
        # Build request parameters
        request_params = {
            "model": self.api_model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": tokens,
            **kwargs
        }
        
        # Add system prompt if provided
        if system_prompt:
            request_params["system"] = system_prompt
        
        async def _generate():
            try:
                # AsyncAnthropic client's messages.create is accessed directly
                response = await self.client.messages.create(**request_params)
                
                # Extract text content from response
                content = ""
                for block in response.content:
                    if hasattr(block, 'text'):
                        content += block.text
                
                return LLMResponse(
                    content=content,
                    model=response.model,
                    provider="anthropic",
                    tokens_used=response.usage.input_tokens + response.usage.output_tokens if response.usage else None,
                    finish_reason=response.stop_reason
                )
            except RateLimitError as e:
                raise RuntimeError(f"Anthropic rate limit exceeded: {str(e)}")
            except APITimeoutError as e:
                raise RuntimeError(f"Anthropic API timeout: {str(e)}")
            except APIError as e:
                raise RuntimeError(f"Anthropic API error: {str(e)}")
            except AnthropicError as e:
                raise RuntimeError(f"Anthropic error: {str(e)}")
            except AttributeError as e:
                raise RuntimeError(f"Anthropic client error - check anthropic library version: {str(e)}")
        
        return await self.generate_with_retry(_generate)
    
    async def generate_structured_output(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> StructuredLLMResponse:
        """Generate structured JSON output using Anthropic API.
        
        Args:
            prompt: The user prompt to generate completion for
            schema: JSON schema that the output should conform to
            system_prompt: Optional system prompt to set context
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            **kwargs: Additional Anthropic-specific parameters
            
        Returns:
            StructuredLLMResponse containing structured data and metadata
            
        Raises:
            ValueError: If prompt or schema is invalid
            RuntimeError: If generation fails after retries
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        
        if not schema:
            raise ValueError("Schema cannot be empty")
        
        # Add schema instruction to prompt
        schema_instruction = (
            f"\n\nYou must respond with valid JSON that conforms to this schema:\n"
            f"{json.dumps(schema, indent=2)}\n"
            f"Respond only with the JSON object, no additional text."
        )
        
        # Build messages
        messages = [{"role": "user", "content": prompt + schema_instruction}]
        
        # Use config defaults if not overridden
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens
        
        # Build request parameters
        request_params = {
            "model": self.api_model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": tokens,
            **kwargs
        }
        
        # Add system prompt if provided
        if system_prompt:
            request_params["system"] = system_prompt
        
        async def _generate():
            try:
                response = await self.client.messages.create(**request_params)
                
                # Extract text content from response
                content = ""
                for block in response.content:
                    if hasattr(block, 'text'):
                        content += block.text
                
                # Parse JSON response
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as e:
                    raise RuntimeError(f"Failed to parse JSON response: {str(e)}")
                
                return StructuredLLMResponse(
                    data=data,
                    model=response.model,
                    provider="anthropic",
                    tokens_used=response.usage.input_tokens + response.usage.output_tokens if response.usage else None
                )
            except RateLimitError as e:
                raise RuntimeError(f"Anthropic rate limit exceeded: {str(e)}")
            except APITimeoutError as e:
                raise RuntimeError(f"Anthropic API timeout: {str(e)}")
            except APIError as e:
                raise RuntimeError(f"Anthropic API error: {str(e)}")
            except AnthropicError as e:
                raise RuntimeError(f"Anthropic error: {str(e)}")
        
        return await self.generate_with_retry(_generate)
