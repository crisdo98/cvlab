"""OpenAI LLM provider implementation."""

import json
from typing import Dict, Any, Optional
from openai import AsyncOpenAI, OpenAIError, APIError, RateLimitError, APITimeoutError
from .base import BaseLLMProvider, LLMConfig, LLMResponse, StructuredLLMResponse


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider implementation.
    
    Supports GPT-4, GPT-3.5-turbo, and other OpenAI models.
    """
    
    def __init__(self, config: LLMConfig):
        """Initialize OpenAI provider.
        
        Args:
            config: LLM provider configuration with OpenAI API key
        """
        super().__init__(config)
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            timeout=config.timeout
        )
    
    def validate_config(self) -> bool:
        """Validate OpenAI provider configuration.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        if not self.config.api_key:
            raise ValueError("OpenAI API key is required")
        
        if not self.config.model:
            raise ValueError("Model name is required")
        
        # Validate model name format
        valid_prefixes = ["gpt-4", "gpt-3.5"]
        if not any(self.config.model.startswith(prefix) for prefix in valid_prefixes):
            raise ValueError(
                f"Invalid OpenAI model: {self.config.model}. "
                f"Must start with one of: {', '.join(valid_prefixes)}"
            )
        
        return True
    
    async def test_connection(self) -> bool:
        """Test connection to OpenAI API.
        
        Returns:
            True if connection is successful
            
        Raises:
            RuntimeError: If connection test fails
        """
        try:
            # Make a minimal API call to test connection
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            return True
        except OpenAIError as e:
            raise RuntimeError(f"OpenAI connection test failed: {str(e)}")
    
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate text completion using OpenAI API.
        
        Args:
            prompt: The user prompt to generate completion for
            system_prompt: Optional system prompt to set context
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            **kwargs: Additional OpenAI-specific parameters
            
        Returns:
            LLMResponse containing generated text and metadata
            
        Raises:
            ValueError: If prompt is empty or invalid
            RuntimeError: If generation fails after retries
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        
        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # Use config defaults if not overridden
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens
        
        async def _generate():
            try:
                response = await self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=tokens,
                    **kwargs
                )
                
                return LLMResponse(
                    content=response.choices[0].message.content,
                    model=response.model,
                    provider="openai",
                    tokens_used=response.usage.total_tokens if response.usage else None,
                    finish_reason=response.choices[0].finish_reason
                )
            except RateLimitError as e:
                raise RuntimeError(f"OpenAI rate limit exceeded: {str(e)}")
            except APITimeoutError as e:
                raise RuntimeError(f"OpenAI API timeout: {str(e)}")
            except APIError as e:
                raise RuntimeError(f"OpenAI API error: {str(e)}")
            except OpenAIError as e:
                raise RuntimeError(f"OpenAI error: {str(e)}")
        
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
        """Generate structured JSON output using OpenAI API.
        
        Args:
            prompt: The user prompt to generate completion for
            schema: JSON schema that the output should conform to
            system_prompt: Optional system prompt to set context
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            **kwargs: Additional OpenAI-specific parameters
            
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
        
        # Build messages with schema instruction
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add schema instruction to prompt
        schema_instruction = (
            f"\n\nYou must respond with valid JSON that conforms to this schema:\n"
            f"{json.dumps(schema, indent=2)}\n"
            f"Respond only with the JSON object, no additional text."
        )
        messages.append({"role": "user", "content": prompt + schema_instruction})
        
        # Use config defaults if not overridden
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens
        
        async def _generate():
            try:
                response = await self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=tokens,
                    response_format={"type": "json_object"},
                    **kwargs
                )
                
                content = response.choices[0].message.content
                
                # Parse JSON response
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as e:
                    raise RuntimeError(f"Failed to parse JSON response: {str(e)}")
                
                return StructuredLLMResponse(
                    data=data,
                    model=response.model,
                    provider="openai",
                    tokens_used=response.usage.total_tokens if response.usage else None
                )
            except RateLimitError as e:
                raise RuntimeError(f"OpenAI rate limit exceeded: {str(e)}")
            except APITimeoutError as e:
                raise RuntimeError(f"OpenAI API timeout: {str(e)}")
            except APIError as e:
                raise RuntimeError(f"OpenAI API error: {str(e)}")
            except OpenAIError as e:
                raise RuntimeError(f"OpenAI error: {str(e)}")
        
        return await self.generate_with_retry(_generate)
