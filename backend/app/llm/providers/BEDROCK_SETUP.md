# AWS Bedrock Provider Setup Guide

## Overview

The AWS Bedrock provider enables the CV Web Application to use AWS Bedrock's foundation models including Claude, Llama, and Titan models. This provider integrates seamlessly with the existing LLM abstraction layer.

## Supported Models

### Claude Models (Anthropic)
- `claude-3-opus` → `anthropic.claude-3-opus-20240229-v1:0`
- `claude-3-sonnet` → `anthropic.claude-3-sonnet-20240229-v1:0`
- `claude-3-haiku` → `anthropic.claude-3-haiku-20240307-v1:0`
- `claude-2.1` → `anthropic.claude-v2:1`
- `claude-2` → `anthropic.claude-v2`

### Llama Models (Meta)
- `llama2-13b` → `meta.llama2-13b-chat-v1`
- `llama2-70b` → `meta.llama2-70b-chat-v1`
- `llama3-8b` → `meta.llama3-8b-instruct-v1:0`
- `llama3-70b` → `meta.llama3-70b-instruct-v1:0`

### Titan Models (Amazon)
- `titan-text-express` → `amazon.titan-text-express-v1`
- `titan-text-lite` → `amazon.titan-text-lite-v1`
- `titan-text-premier` → `amazon.titan-text-premier-v1:0`

## Prerequisites

1. **AWS Account**: You need an active AWS account with access to AWS Bedrock
2. **Model Access**: Request access to the models you want to use in the AWS Bedrock console
3. **AWS Credentials**: Configure AWS credentials (see below)
4. **boto3 Package**: Install boto3 (included in requirements.txt)

```bash
pip install boto3==1.34.34
```

## AWS Credentials Configuration

The Bedrock provider supports multiple methods for AWS credential configuration:

### Option 1: Environment Variables (Recommended for Development)

```bash
export AWS_ACCESS_KEY_ID="your-access-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-access-key"
export AWS_DEFAULT_REGION="us-east-1"
```

### Option 2: AWS Credentials File

Create or edit `~/.aws/credentials`:

```ini
[default]
aws_access_key_id = your-access-key-id
aws_secret_access_key = your-secret-access-key
```

Create or edit `~/.aws/config`:

```ini
[default]
region = us-east-1
```

### Option 3: IAM Role (Recommended for Production)

When running in AWS (EC2, ECS, Lambda), use IAM roles for automatic credential management.

### Option 4: Explicit Configuration

Pass credentials directly in the configuration:

```python
from app.llm.providers import BedrockConfig, BedrockProvider

config = BedrockConfig(
    provider="bedrock",
    model="claude-3-opus",
    aws_region="us-east-1",
    aws_access_key_id="your-access-key-id",
    aws_secret_access_key="your-secret-access-key"
)

provider = BedrockProvider(config)
```

## Usage Examples

### Basic Usage with Factory

```python
from app.llm.providers import ProviderFactory, LLMConfig

# Using short model name
config = LLMConfig(
    provider="bedrock",
    model="claude-3-opus",
    temperature=0.7,
    max_tokens=1000
)

provider = ProviderFactory.create_provider(config)

# Generate completion
response = await provider.generate_completion(
    prompt="Write a professional summary for a software engineer",
    system_prompt="You are a professional CV writer"
)

print(response.content)
```

### Using Full Model ID

```python
config = LLMConfig(
    provider="bedrock",
    model="anthropic.claude-3-sonnet-20240229-v1:0",
    temperature=0.5,
    max_tokens=2000
)

provider = ProviderFactory.create_provider(config)
```

### Structured Output Generation

```python
schema = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "skills": {"type": "array", "items": {"type": "string"}},
        "experience_years": {"type": "number"}
    },
    "required": ["summary", "skills"]
}

response = await provider.generate_structured_output(
    prompt="Extract CV information from this text: ...",
    schema=schema
)

print(response.data)
```

### Using Different Model Families

#### Claude Models
```python
config = BedrockConfig(
    provider="bedrock",
    model="claude-3-haiku",  # Fast and cost-effective
    aws_region="us-east-1"
)
```

#### Llama Models
```python
config = BedrockConfig(
    provider="bedrock",
    model="llama3-70b",  # Open-source alternative
    aws_region="us-west-2"
)
```

#### Titan Models
```python
config = BedrockConfig(
    provider="bedrock",
    model="titan-text-express",  # AWS native model
    aws_region="us-east-1"
)
```

## Configuration in LLM Service

Update your LLM service configuration to use Bedrock:

```json
{
  "provider": "bedrock",
  "model": "claude-3-opus",
  "aws_region": "us-east-1",
  "temperature": 0.7,
  "max_tokens": 1000,
  "enabled": true,
  "timeout": 30,
  "max_retries": 3
}
```

## Error Handling

The Bedrock provider includes comprehensive error handling:

### No Credentials Error
```
RuntimeError: AWS credentials not found. Please configure AWS credentials 
via environment variables, IAM role, or explicit configuration.
```

**Solution**: Configure AWS credentials using one of the methods above.

### Model Access Error
```
RuntimeError: AWS Bedrock API error (AccessDeniedException): 
You don't have access to the model with the specified model ID.
```

**Solution**: Request model access in the AWS Bedrock console.

### Region Error
```
RuntimeError: AWS Bedrock error: Could not connect to the endpoint URL
```

**Solution**: Ensure the model is available in your selected region.

## Testing Connection

Test your Bedrock configuration:

```python
from app.llm.providers import BedrockConfig, BedrockProvider

config = BedrockConfig(
    provider="bedrock",
    model="claude-3-opus",
    aws_region="us-east-1"
)

try:
    provider = BedrockProvider(config)
    result = await provider.test_connection()
    print("✓ Connection successful!")
except Exception as e:
    print(f"✗ Connection failed: {e}")
```

## Cost Considerations

AWS Bedrock charges based on:
- **Input tokens**: Text sent to the model
- **Output tokens**: Text generated by the model

Different models have different pricing:
- **Claude 3 Opus**: Most capable, highest cost
- **Claude 3 Sonnet**: Balanced performance and cost
- **Claude 3 Haiku**: Fast and cost-effective
- **Llama models**: Generally lower cost
- **Titan models**: AWS native, competitive pricing

Check [AWS Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/) for current rates.

## Best Practices

1. **Use IAM Roles in Production**: Avoid hardcoding credentials
2. **Request Only Needed Models**: Reduce access scope
3. **Set Appropriate Timeouts**: Bedrock can be slower than direct APIs
4. **Monitor Token Usage**: Track costs with CloudWatch
5. **Use Appropriate Model**: Choose based on task complexity and budget
6. **Enable Retry Logic**: Network issues are common with AWS services
7. **Test in Development**: Verify model access before production deployment

## Troubleshooting

### Issue: "Model not found"
- Verify the model ID is correct
- Check if the model is available in your region
- Ensure you have requested access to the model

### Issue: "Timeout errors"
- Increase the timeout value in configuration
- Check your network connectivity to AWS
- Consider using a different AWS region

### Issue: "Rate limiting"
- Implement exponential backoff (included in provider)
- Request quota increases in AWS Service Quotas
- Consider using multiple models for load distribution

## Additional Resources

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [AWS Bedrock Model IDs](https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html)
- [AWS Credentials Configuration](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
- [boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
