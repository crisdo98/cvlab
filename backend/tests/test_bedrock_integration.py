"""
Integration tests for AWS Bedrock provider.

Feature: cv-web-app
Tests AWS Bedrock provider integration with Claude, Llama, and Titan models.
Validates credential handling, region configuration, and error handling.

Requirements: 16.1, 16.2
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
import json

from app.llm.providers.bedrock_provider import BedrockProvider, BedrockConfig
from app.llm.providers.base import LLMResponse, StructuredLLMResponse


# Skip all tests if boto3 is not available
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not BOTO3_AVAILABLE,
    reason="boto3 not installed"
)


@pytest.fixture
def mock_bedrock_client():
    """Create a mock Bedrock client."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_boto3_session(mock_bedrock_client):
    """Mock boto3 session and client creation."""
    with patch('boto3.Session') as mock_session_class:
        mock_session = MagicMock()
        mock_session.client.return_value = mock_bedrock_client
        mock_session_class.return_value = mock_session
        yield mock_session_class, mock_session, mock_bedrock_client



@pytest.mark.integration
class TestBedrockProviderInitialization:
    """Test Bedrock provider initialization and configuration."""
    
    def test_initialization_with_explicit_credentials(self, mock_boto3_session):
        """
        Test provider initialization with explicit AWS credentials.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-opus",
            aws_region="us-west-2",
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key"
        )
        
        provider = BedrockProvider(config)
        
        # Verify session was created with credentials
        mock_session_class.assert_called_once()
        call_kwargs = mock_session_class.call_args[1]
        assert call_kwargs['aws_access_key_id'] == "test-access-key"
        assert call_kwargs['aws_secret_access_key'] == "test-secret-key"
        assert call_kwargs['region_name'] == "us-west-2"
        
        # Verify client was created
        mock_session.client.assert_called_once_with(
            'bedrock-runtime',
            region_name='us-west-2'
        )
        
        # Verify model ID was resolved
        assert provider.model_id == "anthropic.claude-3-opus-20240229-v1:0"
    
    def test_initialization_with_session_token(self, mock_boto3_session):
        """
        Test provider initialization with session token.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-sonnet",
            aws_region="eu-west-1",
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key",
            aws_session_token="test-session-token"
        )
        
        provider = BedrockProvider(config)
        
        # Verify session token was passed
        call_kwargs = mock_session_class.call_args[1]
        assert call_kwargs['aws_session_token'] == "test-session-token"
    
    def test_initialization_without_credentials(self, mock_boto3_session):
        """
        Test provider initialization without explicit credentials.
        
        Should use IAM role or environment variables.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-haiku",
            aws_region="us-east-1"
        )
        
        provider = BedrockProvider(config)
        
        # Verify session was created without explicit credentials
        mock_session_class.assert_called_once()
        call_kwargs = mock_session_class.call_args[1]
        assert 'aws_access_key_id' not in call_kwargs or call_kwargs['aws_access_key_id'] is None
        assert call_kwargs['region_name'] == "us-east-1"
    
    def test_initialization_default_region(self, mock_boto3_session):
        """
        Test provider initialization with default region.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-opus"
        )
        
        provider = BedrockProvider(config)
        
        # Should default to us-east-1
        mock_session.client.assert_called_once_with(
            'bedrock-runtime',
            region_name='us-east-1'
        )



@pytest.mark.integration
class TestBedrockClaudeModels:
    """Test Bedrock provider with Claude models."""
    
    @pytest.mark.asyncio
    async def test_claude_completion_generation(self, mock_boto3_session):
        """
        Test completion generation with Claude model.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        # Mock successful API response
        mock_response = {
            'body': MagicMock(),
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'This is a test response from Claude.'}],
            'usage': {'input_tokens': 10, 'output_tokens': 20},
            'stop_reason': 'end_turn'
        }).encode('utf-8')
        
        mock_client.invoke_model.return_value = mock_response
        
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-opus",
            aws_region="us-east-1"
        )
        
        provider = BedrockProvider(config)
        
        # Generate completion
        result = await provider.generate_completion(
            prompt="What is the capital of France?",
            system_prompt="You are a helpful assistant.",
            temperature=0.7,
            max_tokens=100
        )
        
        # Verify result
        assert isinstance(result, LLMResponse)
        assert result.content == "This is a test response from Claude."
        assert result.model == "anthropic.claude-3-opus-20240229-v1:0"
        assert result.provider == "bedrock"
        assert result.tokens_used == 30  # 10 + 20
        assert result.finish_reason == "end_turn"
        
        # Verify API was called correctly
        mock_client.invoke_model.assert_called_once()
        call_kwargs = mock_client.invoke_model.call_args[1]
        assert call_kwargs['modelId'] == "anthropic.claude-3-opus-20240229-v1:0"
        assert call_kwargs['contentType'] == 'application/json'
        assert call_kwargs['accept'] == 'application/json'
        
        # Verify request body
        body = json.loads(call_kwargs['body'])
        assert body['anthropic_version'] == "bedrock-2023-05-31"
        assert body['messages'][0]['role'] == 'user'
        assert body['messages'][0]['content'] == "What is the capital of France?"
        assert body['system'] == "You are a helpful assistant."
        assert body['temperature'] == 0.7
        assert body['max_tokens'] == 100
    
    @pytest.mark.asyncio
    async def test_claude_structured_output(self, mock_boto3_session):
        """
        Test structured output generation with Claude model.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        # Mock successful API response with JSON
        mock_response = {
            'body': MagicMock(),
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': '{"name": "John Doe", "age": 30, "skills": ["Python", "AWS"]}'}],
            'usage': {'input_tokens': 15, 'output_tokens': 25}
        }).encode('utf-8')
        
        mock_client.invoke_model.return_value = mock_response
        
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-sonnet",
            aws_region="us-east-1"
        )
        
        provider = BedrockProvider(config)
        
        # Generate structured output
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "number"},
                "skills": {"type": "array", "items": {"type": "string"}}
            }
        }
        
        result = await provider.generate_structured_output(
            prompt="Extract person information",
            schema=schema
        )
        
        # Verify result
        assert isinstance(result, StructuredLLMResponse)
        assert result.data == {"name": "John Doe", "age": 30, "skills": ["Python", "AWS"]}
        assert result.model == "anthropic.claude-3-sonnet-20240229-v1:0"
        assert result.provider == "bedrock"
        assert result.tokens_used == 40
    
    @pytest.mark.asyncio
    async def test_claude_different_models(self, mock_boto3_session):
        """
        Test different Claude model variants.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        # Mock response
        mock_response = {
            'body': MagicMock(),
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'Test response'}]
        }).encode('utf-8')
        
        mock_client.invoke_model.return_value = mock_response
        
        # Test different Claude models
        models = [
            ("claude-3-opus", "anthropic.claude-3-opus-20240229-v1:0"),
            ("claude-3-sonnet", "anthropic.claude-3-sonnet-20240229-v1:0"),
            ("claude-3-haiku", "anthropic.claude-3-haiku-20240307-v1:0"),
            ("claude-2.1", "anthropic.claude-v2:1"),
            ("claude-2", "anthropic.claude-v2")
        ]
        
        for short_name, expected_id in models:
            config = BedrockConfig(
                provider="bedrock",
                model=short_name,
                aws_region="us-east-1"
            )
            
            provider = BedrockProvider(config)
            assert provider.model_id == expected_id
            
            result = await provider.generate_completion(prompt="Test")
            assert result.model == expected_id



@pytest.mark.integration
class TestBedrockLlamaModels:
    """Test Bedrock provider with Llama models."""
    
    @pytest.mark.asyncio
    async def test_llama_completion_generation(self, mock_boto3_session):
        """
        Test completion generation with Llama model.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        # Mock successful API response
        mock_response = {
            'body': MagicMock(),
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        mock_response['body'].read.return_value = json.dumps({
            'generation': 'This is a response from Llama.',
            'prompt_token_count': 12,
            'generation_token_count': 18,
            'stop_reason': 'stop'
        }).encode('utf-8')
        
        mock_client.invoke_model.return_value = mock_response
        
        config = BedrockConfig(
            provider="bedrock",
            model="llama2-70b",
            aws_region="us-east-1"
        )
        
        provider = BedrockProvider(config)
        
        # Generate completion
        result = await provider.generate_completion(
            prompt="What is machine learning?",
            system_prompt="You are an AI expert.",
            temperature=0.5,
            max_tokens=200
        )
        
        # Verify result
        assert isinstance(result, LLMResponse)
        assert result.content == "This is a response from Llama."
        assert result.model == "meta.llama2-70b-chat-v1"
        assert result.provider == "bedrock"
        
        # Verify API was called correctly
        mock_client.invoke_model.assert_called_once()
        call_kwargs = mock_client.invoke_model.call_args[1]
        assert call_kwargs['modelId'] == "meta.llama2-70b-chat-v1"
        
        # Verify request body format for Llama
        body = json.loads(call_kwargs['body'])
        assert 'prompt' in body
        assert '<s>[INST]' in body['prompt']
        assert '<<SYS>>' in body['prompt']
        assert 'You are an AI expert.' in body['prompt']
        assert 'What is machine learning?' in body['prompt']
        assert body['temperature'] == 0.5
        assert body['max_gen_len'] == 200
    
    @pytest.mark.asyncio
    async def test_llama_different_models(self, mock_boto3_session):
        """
        Test different Llama model variants.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        # Mock response
        mock_response = {
            'body': MagicMock(),
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        mock_response['body'].read.return_value = json.dumps({
            'generation': 'Test response'
        }).encode('utf-8')
        
        mock_client.invoke_model.return_value = mock_response
        
        # Test different Llama models
        models = [
            ("llama2-13b", "meta.llama2-13b-chat-v1"),
            ("llama2-70b", "meta.llama2-70b-chat-v1"),
            ("llama3-8b", "meta.llama3-8b-instruct-v1:0"),
            ("llama3-70b", "meta.llama3-70b-instruct-v1:0")
        ]
        
        for short_name, expected_id in models:
            config = BedrockConfig(
                provider="bedrock",
                model=short_name,
                aws_region="us-east-1"
            )
            
            provider = BedrockProvider(config)
            assert provider.model_id == expected_id
            
            result = await provider.generate_completion(prompt="Test")
            assert result.model == expected_id



@pytest.mark.integration
class TestBedrockTitanModels:
    """Test Bedrock provider with Titan models."""
    
    @pytest.mark.asyncio
    async def test_titan_completion_generation(self, mock_boto3_session):
        """
        Test completion generation with Titan model.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        # Mock successful API response
        mock_response = {
            'body': MagicMock(),
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        mock_response['body'].read.return_value = json.dumps({
            'results': [
                {
                    'outputText': 'This is a response from Titan.',
                    'tokenCount': 25,
                    'completionReason': 'FINISH'
                }
            ],
            'inputTextTokenCount': 8
        }).encode('utf-8')
        
        mock_client.invoke_model.return_value = mock_response
        
        config = BedrockConfig(
            provider="bedrock",
            model="titan-text-express",
            aws_region="us-east-1"
        )
        
        provider = BedrockProvider(config)
        
        # Generate completion
        result = await provider.generate_completion(
            prompt="Explain cloud computing",
            temperature=0.6,
            max_tokens=150
        )
        
        # Verify result
        assert isinstance(result, LLMResponse)
        assert result.content == "This is a response from Titan."
        assert result.model == "amazon.titan-text-express-v1"
        assert result.provider == "bedrock"
        
        # Verify API was called correctly
        mock_client.invoke_model.assert_called_once()
        call_kwargs = mock_client.invoke_model.call_args[1]
        assert call_kwargs['modelId'] == "amazon.titan-text-express-v1"
        
        # Verify request body format for Titan
        body = json.loads(call_kwargs['body'])
        assert body['inputText'] == "Explain cloud computing"
        assert body['textGenerationConfig']['temperature'] == 0.6
        assert body['textGenerationConfig']['maxTokenCount'] == 150
    
    @pytest.mark.asyncio
    async def test_titan_different_models(self, mock_boto3_session):
        """
        Test different Titan model variants.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        # Mock response
        mock_response = {
            'body': MagicMock(),
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        mock_response['body'].read.return_value = json.dumps({
            'results': [{'outputText': 'Test response'}]
        }).encode('utf-8')
        
        mock_client.invoke_model.return_value = mock_response
        
        # Test different Titan models
        models = [
            ("titan-text-express", "amazon.titan-text-express-v1"),
            ("titan-text-lite", "amazon.titan-text-lite-v1"),
            ("titan-text-premier", "amazon.titan-text-premier-v1:0")
        ]
        
        for short_name, expected_id in models:
            config = BedrockConfig(
                provider="bedrock",
                model=short_name,
                aws_region="us-east-1"
            )
            
            provider = BedrockProvider(config)
            assert provider.model_id == expected_id
            
            result = await provider.generate_completion(prompt="Test")
            assert result.model == expected_id



@pytest.mark.integration
class TestBedrockErrorHandling:
    """Test Bedrock provider error handling and retry logic."""
    
    @pytest.mark.asyncio
    async def test_no_credentials_error(self, mock_boto3_session):
        """
        Test handling of missing AWS credentials.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        # Mock NoCredentialsError
        mock_client.invoke_model.side_effect = NoCredentialsError()
        
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-opus",
            aws_region="us-east-1"
        )
        
        provider = BedrockProvider(config)
        
        # Should raise RuntimeError with helpful message
        with pytest.raises(RuntimeError) as exc_info:
            await provider.generate_completion(prompt="Test")
        
        assert "credentials not found" in str(exc_info.value).lower()
        assert "environment variables" in str(exc_info.value).lower() or "IAM role" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_client_error_handling(self, mock_boto3_session):
        """
        Test handling of AWS client errors.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        # Mock ClientError
        error_response = {
            'Error': {
                'Code': 'ValidationException',
                'Message': 'Invalid model ID'
            }
        }
        mock_client.invoke_model.side_effect = ClientError(error_response, 'InvokeModel')
        
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-opus",
            aws_region="us-east-1"
        )
        
        provider = BedrockProvider(config)
        
        # Should raise RuntimeError with error details
        with pytest.raises(RuntimeError) as exc_info:
            await provider.generate_completion(prompt="Test")
        
        assert "ValidationException" in str(exc_info.value)
        assert "Invalid model ID" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_throttling_with_retry(self, mock_boto3_session):
        """
        Test retry logic for throttling errors.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        # Mock throttling error on first call, success on second
        error_response = {
            'Error': {
                'Code': 'ThrottlingException',
                'Message': 'Rate exceeded'
            }
        }
        
        success_response = {
            'body': MagicMock(),
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        success_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'Success after retry'}]
        }).encode('utf-8')
        
        mock_client.invoke_model.side_effect = [
            ClientError(error_response, 'InvokeModel'),
            success_response
        ]
        
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-opus",
            aws_region="us-east-1",
            max_retries=3
        )
        
        provider = BedrockProvider(config)
        
        # Should succeed after retry
        result = await provider.generate_completion(prompt="Test")
        assert result.content == "Success after retry"
        
        # Should have called twice (initial + 1 retry)
        assert mock_client.invoke_model.call_count == 2
    
    @pytest.mark.asyncio
    async def test_invalid_json_response(self, mock_boto3_session):
        """
        Test handling of invalid JSON in structured output.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        # Mock response with invalid JSON
        mock_response = {
            'body': MagicMock(),
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'This is not valid JSON {'}]
        }).encode('utf-8')
        
        mock_client.invoke_model.return_value = mock_response
        
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-opus",
            aws_region="us-east-1"
        )
        
        provider = BedrockProvider(config)
        
        # Should raise RuntimeError for invalid JSON
        with pytest.raises(RuntimeError) as exc_info:
            await provider.generate_structured_output(
                prompt="Extract data",
                schema={"type": "object"}
            )
        
        assert "parse json" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_empty_prompt_validation(self, mock_boto3_session):
        """
        Test validation of empty prompts.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-opus",
            aws_region="us-east-1"
        )
        
        provider = BedrockProvider(config)
        
        # Should raise ValueError for empty prompt
        with pytest.raises(ValueError) as exc_info:
            await provider.generate_completion(prompt="")
        
        assert "empty" in str(exc_info.value).lower()
        
        # Should also fail for whitespace-only prompt
        with pytest.raises(ValueError):
            await provider.generate_completion(prompt="   ")



@pytest.mark.integration
class TestBedrockRegionConfiguration:
    """Test AWS region configuration for Bedrock provider."""
    
    def test_different_regions(self, mock_boto3_session):
        """
        Test provider initialization with different AWS regions.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        regions = [
            "us-east-1",
            "us-west-2",
            "eu-west-1",
            "eu-central-1",
            "ap-southeast-1",
            "ap-northeast-1"
        ]
        
        for region in regions:
            config = BedrockConfig(
                provider="bedrock",
                model="claude-3-opus",
                aws_region=region
            )
            
            provider = BedrockProvider(config)
            
            # Verify client was created with correct region
            # Get the last call (since we're creating multiple providers)
            call_kwargs = mock_session.client.call_args[1]
            assert call_kwargs['region_name'] == region
    
    @pytest.mark.asyncio
    async def test_region_specific_model_availability(self, mock_boto3_session):
        """
        Test that provider works with region-specific model availability.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        # Mock successful response
        mock_response = {
            'body': MagicMock(),
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'Response from specific region'}]
        }).encode('utf-8')
        
        mock_client.invoke_model.return_value = mock_response
        
        # Test with different region
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-opus",
            aws_region="eu-west-1"
        )
        
        provider = BedrockProvider(config)
        result = await provider.generate_completion(prompt="Test")
        
        assert result.content == "Response from specific region"
        
        # Verify correct region was used
        call_kwargs = mock_session.client.call_args[1]
        assert call_kwargs['region_name'] == "eu-west-1"


@pytest.mark.integration
class TestBedrockConnectionTesting:
    """Test connection testing functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_connection_test(self, mock_boto3_session):
        """
        Test successful connection test.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        # Mock successful response
        mock_response = {
            'body': MagicMock(),
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'test'}]
        }).encode('utf-8')
        
        mock_client.invoke_model.return_value = mock_response
        
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-opus",
            aws_region="us-east-1"
        )
        
        provider = BedrockProvider(config)
        
        # Test connection
        result = await provider.test_connection()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_failed_connection_test(self, mock_boto3_session):
        """
        Test failed connection test.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        # Mock connection error
        mock_client.invoke_model.side_effect = NoCredentialsError()
        
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-opus",
            aws_region="us-east-1"
        )
        
        provider = BedrockProvider(config)
        
        # Test connection should raise error
        with pytest.raises(RuntimeError) as exc_info:
            await provider.test_connection()
        
        assert "connection test failed" in str(exc_info.value).lower()


@pytest.mark.integration
class TestBedrockEndToEnd:
    """End-to-end integration tests for Bedrock provider."""
    
    @pytest.mark.asyncio
    async def test_complete_workflow_claude(self, mock_boto3_session):
        """
        Test complete workflow with Claude model.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        # Mock responses for multiple calls
        responses = [
            # First call: simple completion
            {
                'body': MagicMock(),
                'ResponseMetadata': {'HTTPStatusCode': 200}
            },
            # Second call: structured output
            {
                'body': MagicMock(),
                'ResponseMetadata': {'HTTPStatusCode': 200}
            }
        ]
        
        responses[0]['body'].read.return_value = json.dumps({
            'content': [{'text': 'Simple completion response'}],
            'usage': {'input_tokens': 5, 'output_tokens': 10}
        }).encode('utf-8')
        
        responses[1]['body'].read.return_value = json.dumps({
            'content': [{'text': '{"result": "structured data"}'}],
            'usage': {'input_tokens': 8, 'output_tokens': 12}
        }).encode('utf-8')
        
        mock_client.invoke_model.side_effect = responses
        
        config = BedrockConfig(
            provider="bedrock",
            model="claude-3-opus",
            aws_region="us-east-1",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret"
        )
        
        provider = BedrockProvider(config)
        
        # Test 1: Simple completion
        result1 = await provider.generate_completion(
            prompt="Hello, how are you?",
            temperature=0.7
        )
        assert result1.content == "Simple completion response"
        assert result1.tokens_used == 15
        
        # Test 2: Structured output
        result2 = await provider.generate_structured_output(
            prompt="Extract data",
            schema={"type": "object"}
        )
        assert result2.data == {"result": "structured data"}
        assert result2.tokens_used == 20
        
        # Verify both calls were made
        assert mock_client.invoke_model.call_count == 2
    
    @pytest.mark.asyncio
    async def test_complete_workflow_llama(self, mock_boto3_session):
        """
        Test complete workflow with Llama model.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        # Mock response
        mock_response = {
            'body': MagicMock(),
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        mock_response['body'].read.return_value = json.dumps({
            'generation': 'Llama model response'
        }).encode('utf-8')
        
        mock_client.invoke_model.return_value = mock_response
        
        config = BedrockConfig(
            provider="bedrock",
            model="llama2-70b",
            aws_region="us-west-2"
        )
        
        provider = BedrockProvider(config)
        
        result = await provider.generate_completion(
            prompt="Explain AI",
            system_prompt="You are an expert"
        )
        
        assert result.content == "Llama model response"
        assert result.model == "meta.llama2-70b-chat-v1"
    
    @pytest.mark.asyncio
    async def test_complete_workflow_titan(self, mock_boto3_session):
        """
        Test complete workflow with Titan model.
        
        Validates: Requirements 16.1, 16.2
        """
        mock_session_class, mock_session, mock_client = mock_boto3_session
        
        # Mock response
        mock_response = {
            'body': MagicMock(),
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        mock_response['body'].read.return_value = json.dumps({
            'results': [{'outputText': 'Titan model response'}]
        }).encode('utf-8')
        
        mock_client.invoke_model.return_value = mock_response
        
        config = BedrockConfig(
            provider="bedrock",
            model="titan-text-express",
            aws_region="us-east-1"
        )
        
        provider = BedrockProvider(config)
        
        result = await provider.generate_completion(prompt="Test prompt")
        
        assert result.content == "Titan model response"
        assert result.model == "amazon.titan-text-express-v1"
