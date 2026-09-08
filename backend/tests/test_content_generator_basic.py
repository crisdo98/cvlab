"""
Basic tests for ContentGenerator to verify implementation.

These are simple unit tests to ensure the content generator works correctly
with the LLM provider abstraction.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.llm.content_generator import (
    ContentGenerator,
    SummaryGenerationRequest,
    NoteExpansionRequest,
    AchievementGenerationRequest,
    ContentGeneratorFactory
)
from app.llm.providers.base import LLMResponse, BaseLLMProvider, LLMConfig


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider for testing."""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.generate_completion = AsyncMock()
        self.generate_structured_output = AsyncMock()
        self.test_connection = AsyncMock(return_value=True)
    
    async def generate_completion(self, prompt: str, system_prompt=None, temperature=None, max_tokens=None, **kwargs):
        """Mock completion generation."""
        return LLMResponse(
            content="1. First variation\n2. Second variation\n3. Third variation",
            model=self.config.model,
            provider=self.config.provider,
            tokens_used=100
        )
    
    async def generate_structured_output(self, prompt: str, schema: dict, system_prompt=None, temperature=None, max_tokens=None, **kwargs):
        """Mock structured output generation."""
        return {"data": {}}
    
    def validate_config(self) -> bool:
        """Validate configuration."""
        return True
    
    async def test_connection(self) -> bool:
        """Test connection."""
        return True


@pytest.fixture
def mock_provider():
    """Create a mock LLM provider."""
    config = LLMConfig(
        provider="mock",
        model="mock-model",
        temperature=0.7,
        max_tokens=1000
    )
    return MockLLMProvider(config)


@pytest.fixture
def content_generator(mock_provider):
    """Create a content generator with mock provider."""
    return ContentGenerator(mock_provider)


@pytest.mark.asyncio
async def test_generate_summary(content_generator, mock_provider):
    """Test summary generation."""
    # Setup mock response
    mock_provider.generate_completion = AsyncMock(return_value=LLMResponse(
        content="1. Experienced software engineer with 5 years in web development.\n2. Senior developer specializing in Python and JavaScript.\n3. Full-stack engineer with proven track record.",
        model="mock-model",
        provider="mock",
        tokens_used=100
    ))
    
    # Create request
    request = SummaryGenerationRequest(
        job_title="Software Engineer",
        years_experience=5,
        skills=["Python", "JavaScript", "React"],
        num_variations=3
    )
    
    # Generate summary
    result = await content_generator.generate_summary(request)
    
    # Verify result
    assert result.section_type == "summary"
    assert len(result.variations) > 0
    assert result.model == "mock-model"
    assert result.provider == "mock"
    
    # Verify provider was called
    mock_provider.generate_completion.assert_called_once()


@pytest.mark.asyncio
async def test_expand_notes(content_generator, mock_provider):
    """Test note expansion."""
    # Setup mock response
    mock_provider.generate_completion = AsyncMock(return_value=LLMResponse(
        content="1. Led development of microservices architecture using Python and FastAPI.\n2. Architected and implemented scalable backend services.\n3. Designed and built RESTful APIs for enterprise applications.",
        model="mock-model",
        provider="mock",
        tokens_used=100
    ))
    
    # Create request
    request = NoteExpansionRequest(
        notes="Built APIs with Python",
        job_title="Backend Engineer",
        company="Tech Corp",
        num_variations=3
    )
    
    # Expand notes
    result = await content_generator.expand_notes(request)
    
    # Verify result
    assert result.section_type == "note_expansion"
    assert len(result.variations) > 0
    assert result.model == "mock-model"
    
    # Verify provider was called
    mock_provider.generate_completion.assert_called_once()


@pytest.mark.asyncio
async def test_generate_achievements(content_generator, mock_provider):
    """Test achievement generation."""
    # Setup mock response
    mock_provider.generate_completion = AsyncMock(return_value=LLMResponse(
        content="1. Reduced API response time by 40% through query optimization\n2. Improved system performance by 50% via caching implementation\n3. Decreased server costs by 30% through infrastructure optimization",
        model="mock-model",
        provider="mock",
        tokens_used=100
    ))
    
    # Create request
    request = AchievementGenerationRequest(
        notes="Optimized API performance",
        job_title="Software Engineer",
        company="Tech Corp",
        num_variations=3
    )
    
    # Generate achievements
    result = await content_generator.generate_achievements(request)
    
    # Verify result
    assert result.section_type == "achievement"
    assert len(result.variations) > 0
    assert result.model == "mock-model"
    
    # Verify provider was called
    mock_provider.generate_completion.assert_called_once()


@pytest.mark.asyncio
async def test_generate_experience_description(content_generator, mock_provider):
    """Test experience description generation."""
    # Setup mock response
    mock_provider.generate_completion = AsyncMock(return_value=LLMResponse(
        content="1. Led backend development team in building scalable microservices.\n2. Managed development of RESTful APIs and database architecture.\n3. Directed engineering efforts for cloud-based applications.",
        model="mock-model",
        provider="mock",
        tokens_used=100
    ))
    
    # Generate experience description
    result = await content_generator.generate_experience_description(
        job_title="Senior Software Engineer",
        company="Tech Corp",
        duration="2 years",
        responsibilities="Backend development and team leadership",
        skills=["Python", "FastAPI", "PostgreSQL"],
        num_variations=3
    )
    
    # Verify result
    assert result.section_type == "experience"
    assert len(result.variations) > 0
    assert result.model == "mock-model"
    
    # Verify provider was called
    mock_provider.generate_completion.assert_called_once()


@pytest.mark.asyncio
async def test_parse_variations_numbered_list(content_generator):
    """Test parsing numbered list variations."""
    content = """1. First variation text here
2. Second variation text here
3. Third variation text here"""
    
    variations = content_generator._parse_variations(content, 3)
    
    assert len(variations) == 3
    assert variations[0].variation_number == 1
    assert "First variation" in variations[0].text
    assert variations[1].variation_number == 2
    assert "Second variation" in variations[1].text


@pytest.mark.asyncio
async def test_parse_variations_paragraphs(content_generator):
    """Test parsing paragraph-separated variations."""
    content = "First variation text here.\n\nSecond variation text here.\n\nThird variation text here."
    
    variations = content_generator._parse_variations(content, 3)
    
    assert len(variations) == 3
    assert variations[0].variation_number == 1
    assert variations[1].variation_number == 2


@pytest.mark.asyncio
async def test_parse_variations_single(content_generator):
    """Test parsing single variation."""
    content = "Single variation text here."
    
    variations = content_generator._parse_variations(content, 1)
    
    assert len(variations) == 1
    assert variations[0].variation_number == 1
    assert variations[0].text == content


def test_get_provider_info(content_generator):
    """Test getting provider information."""
    info = content_generator.get_provider_info()
    
    assert "provider" in info
    assert "enabled" in info
    assert "model" in info
    assert info["provider"] == "mock"
    assert info["model"] == "mock-model"


def test_content_generator_factory(mock_provider):
    """Test ContentGeneratorFactory."""
    generator = ContentGeneratorFactory.create_generator(mock_provider)
    
    assert isinstance(generator, ContentGenerator)
    assert generator.llm_provider == mock_provider


@pytest.mark.asyncio
async def test_content_generator_factory_with_test(mock_provider):
    """Test ContentGeneratorFactory with connection test."""
    generator = await ContentGeneratorFactory.create_and_test_generator(mock_provider)
    
    assert isinstance(generator, ContentGenerator)
    assert generator.llm_provider == mock_provider
    
    # Verify test_connection was called
    mock_provider.test_connection.assert_called_once()


@pytest.mark.asyncio
async def test_achievement_generation_requires_description_or_notes(content_generator):
    """Test that achievement generation requires either description or notes."""
    request = AchievementGenerationRequest(
        description=None,
        notes=None,
        num_variations=3
    )
    
    with pytest.raises(ValueError, match="Either description or notes must be provided"):
        await content_generator.generate_achievements(request)


@pytest.mark.asyncio
async def test_generate_content_from_cv_summary(content_generator, mock_provider):
    """Test generating content from CV data."""
    # Setup mock response
    mock_provider.generate_completion = AsyncMock(return_value=LLMResponse(
        content="1. Professional summary variation one\n2. Professional summary variation two\n3. Professional summary variation three",
        model="mock-model",
        provider="mock",
        tokens_used=100
    ))
    
    # Create CV data
    cv_data = {
        "personal_info": {
            "name": "John Doe",
            "title": "Software Engineer"
        },
        "experience": [
            {
                "title": "Senior Engineer",
                "company": "Tech Corp",
                "start_date": "2020-01",
                "current": True
            }
        ],
        "skills": {
            "categories": [
                {
                    "name": "Programming",
                    "skills": ["Python", "JavaScript", "TypeScript"]
                }
            ]
        }
    }
    
    # Generate content
    result = await content_generator.generate_content_from_cv(cv_data, "summary", 3)
    
    # Verify result
    assert result.section_type == "summary"
    assert len(result.variations) > 0
    
    # Verify provider was called
    mock_provider.generate_completion.assert_called_once()


@pytest.mark.asyncio
async def test_generate_content_from_cv_unsupported_section(content_generator):
    """Test generating content from CV with unsupported section type."""
    cv_data = {
        "personal_info": {"name": "John Doe"},
        "experience": [],
        "skills": {"categories": []}
    }
    
    with pytest.raises(ValueError, match="Unsupported section type"):
        await content_generator.generate_content_from_cv(cv_data, "unsupported", 3)
