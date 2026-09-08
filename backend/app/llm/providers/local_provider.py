"""Local LLM provider implementation for Ollama and llama.cpp."""

import json
from typing import Dict, Any, Optional, List
import httpx
from .base import BaseLLMProvider, LLMConfig, LLMResponse, StructuredLLMResponse


class LocalProvider(BaseLLMProvider):
    """Local LLM provider for Ollama and llama.cpp.
    
    Supports local models running on Ollama or llama.cpp servers
    with OpenAI-compatible APIs.
    """
    
    def __init__(self, config: LLMConfig):
        """Initialize local provider.
        
        Args:
            config: LLM provider configuration with base_url for local server
        """
        super().__init__(config)
        self.client = httpx.AsyncClient(timeout=config.timeout)
    
    def validate_config(self) -> bool:
        """Validate local provider configuration.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        if not self.config.base_url:
            raise ValueError("Base URL is required for local provider")
        
        if not self.config.model:
            raise ValueError("Model name is required")
        
        # Validate base_url format
        if not self.config.base_url.startswith(("http://", "https://")):
            raise ValueError(
                f"Invalid base URL: {self.config.base_url}. "
                "Must start with http:// or https://"
            )
        
        return True
    
    async def test_connection(self) -> bool:
        """Test connection to local LLM server.
        
        Returns:
            True if connection is successful
            
        Raises:
            RuntimeError: If connection test fails
        """
        try:
            # Try to list available models
            response = await self.client.get(f"{self.config.base_url}/api/tags")
            
            if response.status_code == 200:
                return True
            else:
                raise RuntimeError(
                    f"Local server returned status {response.status_code}"
                )
        except httpx.RequestError as e:
            raise RuntimeError(f"Failed to connect to local server: {str(e)}")
    
    async def list_available_models(self) -> List[str]:
        """List available models on the local server.
        
        Returns:
            List of model names
            
        Raises:
            RuntimeError: If request fails
        """
        try:
            response = await self.client.get(f"{self.config.base_url}/api/tags")
            response.raise_for_status()
            
            data = response.json()
            models = []
            
            if "models" in data:
                models = [model.get("name", "") for model in data["models"]]
            
            return models
        except httpx.RequestError as e:
            raise RuntimeError(f"Failed to list models: {str(e)}")
    
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate text completion using local LLM server.
        
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
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        
        # Use config defaults if not overridden
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens
        
        # Build request payload for Ollama API
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "temperature": temp,
            "stream": False,
            "options": {
                "num_predict": tokens
            }
        }
        
        # Add system prompt if provided
        if system_prompt:
            payload["system"] = system_prompt
        
        # Add any additional options
        if kwargs:
            payload["options"].update(kwargs)
        
        async def _generate():
            try:
                response = await self.client.post(
                    f"{self.config.base_url}/api/generate",
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                
                return LLMResponse(
                    content=data.get("response", ""),
                    model=self.config.model,
                    provider="local",
                    tokens_used=data.get("eval_count"),
                    finish_reason=data.get("done_reason")
                )
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"Local server HTTP error: {str(e)}")
            except httpx.RequestError as e:
                raise RuntimeError(f"Local server request error: {str(e)}")
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Failed to parse server response: {str(e)}")
        
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
        """Generate structured JSON output using local LLM server.
        
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
        
        enhanced_prompt = prompt + schema_instruction
        
        # Use config defaults if not overridden
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens
        
        # Build request payload
        payload = {
            "model": self.config.model,
            "prompt": enhanced_prompt,
            "temperature": temp,
            "stream": False,
            "format": "json",  # Request JSON format from Ollama
            "options": {
                "num_predict": tokens
            }
        }
        
        # Add system prompt if provided
        if system_prompt:
            payload["system"] = system_prompt
        
        # Add any additional options
        if kwargs:
            payload["options"].update(kwargs)
        
        async def _generate():
            try:
                response = await self.client.post(
                    f"{self.config.base_url}/api/generate",
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                content = data.get("response", "")
                
                # Parse JSON response
                try:
                    parsed_data = json.loads(content)
                except json.JSONDecodeError as e:
                    raise RuntimeError(f"Failed to parse JSON response: {str(e)}")
                
                return StructuredLLMResponse(
                    data=parsed_data,
                    model=self.config.model,
                    provider="local",
                    tokens_used=data.get("eval_count")
                )
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"Local server HTTP error: {str(e)}")
            except httpx.RequestError as e:
                raise RuntimeError(f"Local server request error: {str(e)}")
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Failed to parse server response: {str(e)}")
        
        return await self.generate_with_retry(_generate)
    
    async def close(self):
        """Close the HTTP client connection."""
        await self.client.aclose()
