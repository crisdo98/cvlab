"""AWS Bedrock LLM provider implementation."""

import json
from typing import Dict, Any, Optional
from .base import BaseLLMProvider, LLMConfig, LLMResponse, StructuredLLMResponse

try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class BedrockConfig(LLMConfig):
    """Extended configuration for AWS Bedrock provider."""
    aws_region: Optional[str] = "us-east-1"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None


class BedrockProvider(BaseLLMProvider):
    """AWS Bedrock API provider implementation.
    
    Supports Claude, Llama, and Titan models on AWS Bedrock.
    """
    
    # Model ID mappings for common model names
    # NOTE: Some AWS accounts/regions require inference profiles for ALL models.
    # Cross-region inference profiles are region-specific (us. for US, eu. for EU)
    MODEL_ID_MAP = {
        # EU Cross-region inference profiles (for eu-west-1, eu-central-1, etc.)
        "claude-3-opus": "eu.anthropic.claude-3-opus-20240229-v1:0",
        "claude-3-sonnet": "eu.anthropic.claude-3-sonnet-20240229-v1:0",
        "claude-3-haiku": "eu.anthropic.claude-3-haiku-20240307-v1:0",
        "claude-3.5-sonnet": "eu.anthropic.claude-3-5-sonnet-20241022-v2:0",
        "claude-3.5-haiku": "eu.anthropic.claude-3-5-haiku-20241022-v1:0",
        
        # US Cross-region inference profiles (for us-east-1, us-west-2, etc.)
        "claude-3-opus-us": "us.anthropic.claude-3-opus-20240229-v1:0",
        "claude-3-sonnet-us": "us.anthropic.claude-3-sonnet-20240229-v1:0",
        "claude-3-haiku-us": "us.anthropic.claude-3-haiku-20240307-v1:0",
        
        # Direct model IDs (fallback - may not work in accounts requiring inference profiles)
        "claude-3-opus-direct": "anthropic.claude-3-opus-20240229-v1:0",
        "claude-3-sonnet-direct": "anthropic.claude-3-sonnet-20240229-v1:0",
        "claude-3-haiku-direct": "anthropic.claude-3-haiku-20240307-v1:0",
        
        # Llama models (usually don't require inference profiles)
        "llama2-13b": "meta.llama2-13b-chat-v1",
        "llama2-70b": "meta.llama2-70b-chat-v1",
        "llama3-8b": "meta.llama3-8b-instruct-v1:0",
        "llama3-70b": "meta.llama3-70b-instruct-v1:0",
        
        # Titan models (usually don't require inference profiles)
        "titan-text-express": "amazon.titan-text-express-v1",
        "titan-text-lite": "amazon.titan-text-lite-v1",
        "titan-text-premier": "amazon.titan-text-premier-v1:0",
    }
    
    # Default model to use if none specified
    DEFAULT_MODEL = "claude-3-sonnet"
    
    def __init__(self, config: BedrockConfig):
        """Initialize AWS Bedrock provider.
        
        Args:
            config: LLM provider configuration with AWS credentials
            
        Raises:
            ImportError: If boto3 is not installed
        """
        if not BOTO3_AVAILABLE:
            raise ImportError(
                "boto3 is required for AWS Bedrock provider. "
                "Install it with: pip install boto3"
            )
        
        super().__init__(config)
        
        # Build boto3 session with credentials
        session_kwargs = {}
        if config.aws_access_key_id:
            session_kwargs['aws_access_key_id'] = config.aws_access_key_id
        if config.aws_secret_access_key:
            session_kwargs['aws_secret_access_key'] = config.aws_secret_access_key
        if config.aws_session_token:
            session_kwargs['aws_session_token'] = config.aws_session_token
        if config.aws_region:
            session_kwargs['region_name'] = config.aws_region
        
        # Create boto3 session and client
        self.session = boto3.Session(**session_kwargs)
        self.client = self.session.client(
            'bedrock-runtime',
            region_name=config.aws_region or 'us-east-1'
        )
        
        # Resolve model ID
        self.model_id = self._resolve_model_id(config.model)
    
    def _resolve_model_id(self, model_name: str) -> str:
        """Resolve model name to full Bedrock model ID.
        
        Args:
            model_name: Short model name or full model ID
            
        Returns:
            Full Bedrock model ID
        """
        # If it's already a full model ID, return as-is
        if '.' in model_name and any(
            model_name.startswith(prefix) 
            for prefix in ['anthropic.', 'meta.', 'amazon.', 'ai21.', 'cohere.']
        ):
            return model_name
        
        # Try to map from short name
        if model_name in self.MODEL_ID_MAP:
            return self.MODEL_ID_MAP[model_name]
        
        # Return as-is and let AWS validate
        return model_name
    
    def validate_config(self) -> bool:
        """Validate AWS Bedrock provider configuration.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        if not self.config.model:
            raise ValueError("Model name is required")
        
        # AWS region is optional (defaults to us-east-1)
        # Credentials are optional (can use IAM role or environment variables)
        
        return True
    
    async def test_connection(self) -> bool:
        """Test connection to AWS Bedrock API.
        
        Returns:
            True if connection is successful
            
        Raises:
            RuntimeError: If connection test fails
        """
        try:
            # Make a minimal API call to test connection
            response = await self._invoke_model_async(
                prompt="test",
                max_tokens=5
            )
            return True
        except Exception as e:
            raise RuntimeError(f"AWS Bedrock connection test failed: {str(e)}")
    
    def _get_model_family(self) -> str:
        """Determine the model family from model ID.
        
        Returns:
            Model family: 'claude', 'llama', 'titan', or 'unknown'
        """
        if 'anthropic.claude' in self.model_id:
            return 'claude'
        elif 'meta.llama' in self.model_id:
            return 'llama'
        elif 'amazon.titan' in self.model_id:
            return 'titan'
        else:
            return 'unknown'
    
    def _build_request_body(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Build request body based on model family.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            
        Returns:
            Request body dictionary for the specific model
        """
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens
        
        model_family = self._get_model_family()
        
        if model_family == 'claude':
            # Claude models use messages API format
            messages = [{"role": "user", "content": prompt}]
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": messages,
                "temperature": temp,
                "max_tokens": tokens
            }
            if system_prompt:
                body["system"] = system_prompt
            return body
        
        elif model_family == 'llama':
            # Llama models use prompt format
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"<s>[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n{prompt} [/INST]"
            else:
                full_prompt = f"<s>[INST] {prompt} [/INST]"
            
            return {
                "prompt": full_prompt,
                "temperature": temp,
                "max_gen_len": tokens,
                "top_p": 0.9
            }
        
        elif model_family == 'titan':
            # Titan models use textGenerationConfig
            return {
                "inputText": prompt,
                "textGenerationConfig": {
                    "temperature": temp,
                    "maxTokenCount": tokens,
                    "topP": 0.9
                }
            }
        
        else:
            # Generic format
            return {
                "prompt": prompt,
                "temperature": temp,
                "max_tokens": tokens
            }
    
    def _extract_response_text(self, response_body: Dict[str, Any]) -> str:
        """Extract text from response based on model family.
        
        Args:
            response_body: Response body from Bedrock
            
        Returns:
            Extracted text content
            
        Raises:
            RuntimeError: If response format is unexpected
        """
        model_family = self._get_model_family()
        
        if model_family == 'claude':
            # Claude response format
            if 'content' in response_body:
                content = response_body['content']
                if isinstance(content, list) and len(content) > 0:
                    return content[0].get('text', '')
            raise RuntimeError("Unexpected Claude response format")
        
        elif model_family == 'llama':
            # Llama response format
            if 'generation' in response_body:
                return response_body['generation']
            raise RuntimeError("Unexpected Llama response format")
        
        elif model_family == 'titan':
            # Titan response format
            if 'results' in response_body and len(response_body['results']) > 0:
                return response_body['results'][0].get('outputText', '')
            raise RuntimeError("Unexpected Titan response format")
        
        else:
            # Try common fields
            for field in ['text', 'completion', 'output', 'generation']:
                if field in response_body:
                    return response_body[field]
            
            raise RuntimeError(f"Could not extract text from response: {response_body}")
    
    async def _invoke_model_async(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Invoke Bedrock model asynchronously.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            
        Returns:
            Response body dictionary
            
        Raises:
            RuntimeError: If invocation fails
        """
        try:
            # Build request body
            body = self._build_request_body(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Invoke model
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
                contentType='application/json',
                accept='application/json'
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            return response_body
            
        except NoCredentialsError as e:
            raise RuntimeError(
                "AWS credentials not found. Please configure AWS credentials "
                "via environment variables, IAM role, or explicit configuration."
            )
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            # Provide helpful guidance for common errors
            if error_code == 'ValidationException' and 'inference profile' in error_message.lower():
                raise RuntimeError(
                    f"Model {self.model_id} requires an inference profile. "
                    f"Your AWS account requires cross-region inference profiles for Claude models. "
                    f"Please use one of these inference profile IDs based on your region:\n\n"
                    f"For EU regions (eu-west-1, eu-central-1, etc.):\n"
                    f"  • eu.anthropic.claude-3-sonnet-20240229-v1:0 (recommended)\n"
                    f"  • eu.anthropic.claude-3-haiku-20240307-v1:0 (fastest)\n"
                    f"  • eu.anthropic.claude-3-opus-20240229-v1:0 (highest quality)\n\n"
                    f"For US regions (us-east-1, us-west-2, etc.):\n"
                    f"  • us.anthropic.claude-3-sonnet-20240229-v1:0 (recommended)\n"
                    f"  • us.anthropic.claude-3-haiku-20240307-v1:0 (fastest)\n"
                    f"  • us.anthropic.claude-3-opus-20240229-v1:0 (highest quality)\n\n"
                    f"Or use short names: claude-3-sonnet, claude-3-haiku, claude-3-opus\n"
                    f"(These now default to EU profiles)\n\n"
                    f"Original error: {error_message}"
                )
            
            raise RuntimeError(f"AWS Bedrock API error ({error_code}): {error_message}")
        except BotoCoreError as e:
            raise RuntimeError(f"AWS Bedrock error: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error invoking Bedrock model: {str(e)}")
    
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate text completion using AWS Bedrock API.
        
        Args:
            prompt: The user prompt to generate completion for
            system_prompt: Optional system prompt to set context
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            **kwargs: Additional Bedrock-specific parameters
            
        Returns:
            LLMResponse containing generated text and metadata
            
        Raises:
            ValueError: If prompt is empty or invalid
            RuntimeError: If generation fails after retries
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        
        async def _generate():
            response_body = await self._invoke_model_async(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Extract text from response
            content = self._extract_response_text(response_body)
            
            # Extract token usage if available
            tokens_used = None
            if 'usage' in response_body:
                usage = response_body['usage']
                if isinstance(usage, dict):
                    tokens_used = usage.get('total_tokens') or (
                        usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
                    )
            
            return LLMResponse(
                content=content,
                model=self.model_id,
                provider="bedrock",
                tokens_used=tokens_used,
                finish_reason=response_body.get('stop_reason') or response_body.get('stopReason')
            )
        
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
        """Generate structured JSON output using AWS Bedrock API.
        
        Args:
            prompt: The user prompt to generate completion for
            schema: JSON schema that the output should conform to
            system_prompt: Optional system prompt to set context
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            **kwargs: Additional Bedrock-specific parameters
            
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
        
        async def _generate():
            response_body = await self._invoke_model_async(
                prompt=prompt + schema_instruction,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Extract text from response
            content = self._extract_response_text(response_body)
            
            # Parse JSON response
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Failed to parse JSON response: {str(e)}")
            
            # Extract token usage if available
            tokens_used = None
            if 'usage' in response_body:
                usage = response_body['usage']
                if isinstance(usage, dict):
                    tokens_used = usage.get('total_tokens') or (
                        usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
                    )
            
            return StructuredLLMResponse(
                data=data,
                model=self.model_id,
                provider="bedrock",
                tokens_used=tokens_used
            )
        
        return await self.generate_with_retry(_generate)
