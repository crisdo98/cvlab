# AWS Bedrock Setup Guide

## Overview

AWS Bedrock provides access to multiple foundation models through a unified API, including Claude, Llama, and Titan models. This guide covers setup, configuration, and troubleshooting for AWS Bedrock integration.

## Prerequisites

### 1. AWS Account
- Active AWS account with billing enabled
- Access to AWS Bedrock service in your region

### 2. Model Access
Before using Bedrock models, you must request access:

1. Navigate to [AWS Bedrock Console](https://console.aws.amazon.com/bedrock/)
2. Go to "Model access" in the left sidebar
3. Click "Manage model access"
4. Select the models you want to use:
   - **Anthropic Claude 3 Opus** (recommended for quality)
   - **Anthropic Claude 3 Sonnet** (recommended for balance)
   - **Anthropic Claude 3 Haiku** (recommended for speed)
   - **Meta Llama 3 70B** (open source alternative)
   - **Amazon Titan Text Express** (AWS native, cost-effective)
5. Click "Request model access"
6. Wait for approval (usually instant for most models)

### 3. IAM Permissions

Create an IAM user or role with Bedrock permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:ListFoundationModels",
        "bedrock:GetFoundationModel"
      ],
      "Resource": "*"
    }
  ]
}
```

**For production**, restrict to specific models:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-opus-20240229-v1:0",
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
      ]
    }
  ]
}
```

## Configuration Methods

### Method 1: IAM Role (Recommended for EC2/ECS/EKS)

**Best for**: Production deployments on AWS infrastructure

1. **Create IAM Role**:
   - Navigate to IAM Console
   - Create role for EC2/ECS/EKS
   - Attach Bedrock permissions policy
   - Attach role to your instance/service

2. **Configure Application**:
   ```bash
   # In .env or docker-compose.yml
   LLM_PROVIDER=bedrock
   AWS_REGION=us-east-1
   BEDROCK_MODEL=claude-3-sonnet
   ```

3. **No credentials needed** - IAM role provides automatic authentication

### Method 2: Access Keys (For Development/Local)

**Best for**: Local development, testing, non-AWS deployments

1. **Create Access Keys**:
   - Navigate to IAM Console
   - Select your user
   - Go to "Security credentials"
   - Click "Create access key"
   - Choose "Application running outside AWS"
   - Copy Access Key ID and Secret Access Key

2. **Configure Application**:
   ```bash
   # Add to .env file
   LLM_PROVIDER=bedrock
   AWS_REGION=us-east-1
   AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
   AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
   BEDROCK_MODEL=claude-3-sonnet
   ```

3. **Security Best Practices**:
   - Never commit credentials to version control
   - Use `.env` file (add to `.gitignore`)
   - Rotate keys every 90 days
   - Use least-privilege permissions
   - Monitor usage in CloudTrail

### Method 3: AWS CLI Profile

**Best for**: Multiple AWS accounts, shared development environments

1. **Configure AWS CLI**:
   ```bash
   aws configure --profile bedrock-cv-app
   # Enter Access Key ID
   # Enter Secret Access Key
   # Enter region (e.g., us-east-1)
   # Enter output format (json)
   ```

2. **Configure Application**:
   ```bash
   # In .env or docker-compose.yml
   LLM_PROVIDER=bedrock
   AWS_PROFILE=bedrock-cv-app
   AWS_REGION=us-east-1
   BEDROCK_MODEL=claude-3-sonnet
   ```

## Available Models

### Claude Models (Anthropic)

| Model | Model ID | Best For | Cost (per 1K tokens) |
|-------|----------|----------|---------------------|
| Claude 3 Opus | `claude-3-opus` | Highest quality, complex tasks | Input: $0.015, Output: $0.075 |
| Claude 3 Sonnet | `claude-3-sonnet` | Balance of quality and speed | Input: $0.003, Output: $0.015 |
| Claude 3 Haiku | `claude-3-haiku` | Fast responses, simple tasks | Input: $0.00025, Output: $0.00125 |
| Claude 2.1 | `claude-2.1` | Legacy, good quality | Input: $0.008, Output: $0.024 |

**Recommendation**: Start with `claude-3-sonnet` for best balance.

### Llama Models (Meta)

| Model | Model ID | Best For | Cost (per 1K tokens) |
|-------|----------|----------|---------------------|
| Llama 3 70B | `llama3-70b` | High quality, open source | Input: $0.00265, Output: $0.0035 |
| Llama 3 8B | `llama3-8b` | Fast, cost-effective | Input: $0.0003, Output: $0.0006 |
| Llama 2 70B | `llama2-70b` | Legacy, good quality | Input: $0.00195, Output: $0.00256 |
| Llama 2 13B | `llama2-13b` | Smaller, faster | Input: $0.00075, Output: $0.001 |

**Recommendation**: Use `llama3-70b` for open-source alternative to Claude.

### Titan Models (Amazon)

| Model | Model ID | Best For | Cost (per 1K tokens) |
|-------|----------|----------|---------------------|
| Titan Text Premier | `titan-text-premier` | Highest quality Titan | Input: $0.0005, Output: $0.0015 |
| Titan Text Express | `titan-text-express` | Fast, cost-effective | Input: $0.0002, Output: $0.0006 |
| Titan Text Lite | `titan-text-lite` | Simple tasks, lowest cost | Input: $0.00015, Output: $0.0002 |

**Recommendation**: Use `titan-text-express` for cost-sensitive applications.

## Regional Availability

Bedrock is available in multiple regions. Check [AWS Regional Services](https://aws.amazon.com/about-aws/global-infrastructure/regional-product-services/) for current availability.

**Recommended Regions**:
- `us-east-1` (N. Virginia) - Most models available
- `us-west-2` (Oregon) - Good availability
- `eu-west-1` (Ireland) - European deployments
- `ap-southeast-1` (Singapore) - Asia-Pacific deployments

**Note**: Model availability varies by region. Claude 3 models are widely available, but check your specific region.

## Docker Configuration

### Environment Variables

Add to `docker-compose.yml`:

```yaml
services:
  cv-web-app:
    environment:
      # Enable LLM features
      - LLM_ENABLED=true
      - LLM_PROVIDER=bedrock
      
      # AWS Configuration
      - AWS_REGION=us-east-1
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}  # From .env
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}  # From .env
      # Optional: For temporary credentials
      # - AWS_SESSION_TOKEN=${AWS_SESSION_TOKEN}
      
      # Model Selection
      - BEDROCK_MODEL=claude-3-sonnet
      
      # Optional: Advanced settings
      - LLM_TEMPERATURE=0.7
      - LLM_MAX_TOKENS=2000
```

### Using .env File

Create `.env` file in project root:

```bash
# AWS Bedrock Configuration
LLM_PROVIDER=bedrock
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
BEDROCK_MODEL=claude-3-sonnet

# Optional settings
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000
```

Then reference in `docker-compose.yml`:

```yaml
services:
  cv-web-app:
    env_file:
      - .env
```

## Testing Connection

### Method 1: Web Interface

1. Start the application:
   ```bash
   docker-compose up -d
   ```

2. Open http://localhost:8002

3. Navigate to **Settings → LLM Configuration**

4. Verify:
   - Provider shows "AWS Bedrock"
   - Model shows your selected model
   - Connection status shows "Connected"

5. Click "Test Connection" button

### Method 2: Python Script

Create `test_bedrock.py`:

```python
import boto3
import json

# Configure client
client = boto3.client(
    'bedrock-runtime',
    region_name='us-east-1',
    aws_access_key_id='your-access-key-id',
    aws_secret_access_key='your-secret-access-key'
)

# Test with Claude 3 Sonnet
model_id = 'anthropic.claude-3-sonnet-20240229-v1:0'

# Prepare request
body = json.dumps({
    "anthropic_version": "bedrock-2023-05-31",
    "messages": [
        {
            "role": "user",
            "content": "Hello! Please respond with 'Connection successful.'"
        }
    ],
    "max_tokens": 100,
    "temperature": 0.7
})

# Invoke model
try:
    response = client.invoke_model(
        modelId=model_id,
        body=body,
        contentType='application/json',
        accept='application/json'
    )
    
    # Parse response
    response_body = json.loads(response['body'].read())
    print("Success!")
    print("Response:", response_body['content'][0]['text'])
    
except Exception as e:
    print(f"Error: {e}")
```

Run:
```bash
python test_bedrock.py
```

### Method 3: AWS CLI

```bash
# List available models
aws bedrock list-foundation-models --region us-east-1

# Test specific model
aws bedrock-runtime invoke-model \
    --model-id anthropic.claude-3-sonnet-20240229-v1:0 \
    --body '{"anthropic_version":"bedrock-2023-05-31","messages":[{"role":"user","content":"Hello"}],"max_tokens":100}' \
    --region us-east-1 \
    output.json

# View response
cat output.json
```

## Troubleshooting

### Error: "Unknown service: 'bedrock'"

**Cause**: boto3/botocore version too old

**Solution**:
```bash
# Update dependencies
pip install --upgrade boto3 botocore

# Or in Docker, rebuild:
docker-compose build --no-cache
```

### Error: "NoCredentialsError"

**Cause**: AWS credentials not configured

**Solutions**:
1. Check environment variables are set
2. Verify IAM role is attached (for EC2/ECS)
3. Check AWS CLI configuration: `aws configure list`
4. Verify credentials in `.env` file

### Error: "AccessDeniedException"

**Cause**: IAM permissions insufficient

**Solutions**:
1. Verify IAM policy includes `bedrock:InvokeModel`
2. Check model access is enabled in Bedrock console
3. Verify resource ARN in policy matches your region
4. Check CloudTrail logs for detailed error

### Error: "ValidationException: Model not found"

**Cause**: Model ID incorrect or not available in region

**Solutions**:
1. Verify model ID is correct (see Available Models section)
2. Check model is available in your region
3. Ensure model access is enabled in Bedrock console
4. Try full model ID instead of short name

### Error: "ThrottlingException"

**Cause**: Rate limit exceeded

**Solutions**:
1. Implement exponential backoff (already in provider)
2. Request quota increase in AWS Service Quotas
3. Reduce request frequency
4. Use smaller model for high-volume tasks

### Error: "ModelTimeoutException"

**Cause**: Request took too long

**Solutions**:
1. Reduce `max_tokens` parameter
2. Simplify prompt
3. Increase timeout in configuration
4. Try faster model (e.g., Claude 3 Haiku)

## Cost Optimization

### 1. Choose Right Model

- **High quality needed**: Claude 3 Opus
- **Balanced**: Claude 3 Sonnet (recommended)
- **High volume**: Claude 3 Haiku or Titan Text Express
- **Cost-sensitive**: Titan Text Lite

### 2. Optimize Token Usage

```python
# Bad: Verbose prompt
prompt = """
Please analyze this CV and provide detailed recommendations 
for improvement including grammar, style, structure, keywords, 
and any other suggestions you might have.
"""

# Good: Concise prompt
prompt = "Analyze CV and suggest improvements for grammar, style, structure, and keywords."
```

### 3. Cache Common Requests

The application includes caching for repeated requests. Enable in configuration:

```bash
LLM_CACHE_ENABLED=true
LLM_CACHE_TTL=3600  # 1 hour
```

### 4. Monitor Usage

1. **AWS Cost Explorer**:
   - Navigate to AWS Cost Explorer
   - Filter by service: "Amazon Bedrock"
   - View daily/monthly costs

2. **CloudWatch Metrics**:
   - Monitor invocation count
   - Track token usage
   - Set up billing alarms

3. **Application Logs**:
   ```bash
   docker-compose logs cv-web-app | grep "tokens_used"
   ```

### 5. Set Budget Alerts

1. Navigate to AWS Billing Console
2. Create budget for Bedrock
3. Set threshold (e.g., $50/month)
4. Configure email alerts

## Security Best Practices

### 1. Credential Management

- ✅ Use IAM roles when possible
- ✅ Store credentials in `.env` file
- ✅ Add `.env` to `.gitignore`
- ✅ Rotate access keys every 90 days
- ❌ Never commit credentials to git
- ❌ Never hardcode credentials in code

### 2. Least Privilege

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": [
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
      ],
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    }
  ]
}
```

### 3. Network Security

- Use VPC endpoints for Bedrock (enterprise)
- Enable CloudTrail logging
- Monitor with GuardDuty
- Use AWS PrivateLink for private connectivity

### 4. Data Privacy

- Review AWS Bedrock data handling policies
- Understand data residency requirements
- Enable encryption at rest (automatic)
- Use VPC for sensitive workloads

## Advanced Configuration

### Custom Retry Logic

```python
# In backend/app/llm/providers/bedrock_provider.py
class BedrockProvider(BaseLLMProvider):
    def __init__(self, config: BedrockConfig):
        super().__init__(config)
        
        # Custom retry configuration
        from botocore.config import Config
        
        retry_config = Config(
            retries={
                'max_attempts': 5,
                'mode': 'adaptive'
            },
            connect_timeout=10,
            read_timeout=60
        )
        
        self.client = self.session.client(
            'bedrock-runtime',
            region_name=config.aws_region,
            config=retry_config
        )
```

### Multi-Region Failover

```python
# Configure multiple regions
AWS_REGIONS=us-east-1,us-west-2,eu-west-1

# Application will try regions in order
```

### Model-Specific Parameters

```python
# For Claude models
BEDROCK_CLAUDE_TOP_P=0.9
BEDROCK_CLAUDE_TOP_K=250

# For Llama models
BEDROCK_LLAMA_TOP_P=0.9

# For Titan models
BEDROCK_TITAN_TOP_P=0.9
```

## Support Resources

### AWS Documentation
- [Bedrock User Guide](https://docs.aws.amazon.com/bedrock/)
- [Bedrock API Reference](https://docs.aws.amazon.com/bedrock/latest/APIReference/)
- [Boto3 Bedrock Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-runtime.html)

### Model Documentation
- [Claude Models](https://docs.anthropic.com/claude/docs)
- [Llama Models](https://ai.meta.com/llama/)
- [Titan Models](https://aws.amazon.com/bedrock/titan/)

### AWS Support
- [AWS Support Center](https://console.aws.amazon.com/support/)
- [Bedrock Forum](https://repost.aws/tags/TA4IvCeWI1TE-6rXbfDkEb6g/amazon-bedrock)
- [AWS Service Health Dashboard](https://status.aws.amazon.com/)

### Pricing
- [Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)
- [Cost Calculator](https://calculator.aws/)

## Example Configurations

### Development (Local)

```bash
# .env
LLM_PROVIDER=bedrock
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
BEDROCK_MODEL=claude-3-haiku  # Cheaper for testing
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=1000
```

### Production (EC2 with IAM Role)

```bash
# .env
LLM_PROVIDER=bedrock
AWS_REGION=us-east-1
BEDROCK_MODEL=claude-3-sonnet
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000
LLM_CACHE_ENABLED=true
```

### High-Volume (Cost-Optimized)

```bash
# .env
LLM_PROVIDER=bedrock
AWS_REGION=us-east-1
BEDROCK_MODEL=titan-text-express
LLM_TEMPERATURE=0.5
LLM_MAX_TOKENS=1500
LLM_CACHE_ENABLED=true
LLM_CACHE_TTL=7200
```

### Enterprise (Multi-Region)

```bash
# .env
LLM_PROVIDER=bedrock
AWS_REGIONS=us-east-1,us-west-2,eu-west-1
BEDROCK_MODEL=claude-3-opus
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000
LLM_RETRY_ATTEMPTS=5
LLM_TIMEOUT=120
```

## Migration from Other Providers

### From OpenAI

1. Update environment variables:
   ```bash
   # Change from
   LLM_PROVIDER=openai
   OPENAI_API_KEY=sk-...
   
   # To
   LLM_PROVIDER=bedrock
   AWS_REGION=us-east-1
   BEDROCK_MODEL=claude-3-sonnet
   ```

2. Restart application:
   ```bash
   docker-compose restart cv-web-app
   ```

3. Test functionality in web interface

### From Anthropic

1. Update environment variables:
   ```bash
   # Change from
   LLM_PROVIDER=anthropic
   ANTHROPIC_API_KEY=sk-ant-...
   
   # To
   LLM_PROVIDER=bedrock
   AWS_REGION=us-east-1
   BEDROCK_MODEL=claude-3-sonnet
   ```

2. Restart and test

**Note**: Claude models on Bedrock use the same underlying models as Anthropic API, so quality should be similar.

## Conclusion

AWS Bedrock provides a powerful, flexible platform for LLM integration with enterprise features, multiple model options, and AWS ecosystem integration. Follow this guide for successful setup and operation.

For additional help, consult the main [LLM-SETUP.md](../../../LLM-SETUP.md) guide or open an issue on GitHub.
