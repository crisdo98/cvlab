"""
Basic tests for CV Optimizer functionality.

These tests verify the core functionality of the CV optimizer including
weak language detection, metrics gap identification, and structural analysis.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.llm.cv_optimizer import CVOptimizer, CVOptimizerFactory
from app.llm.providers.base import BaseLLMProvider, LLMResponse, LLMConfig
from app.models.llm_models import (
    OptimizationRequest,
    OptimizationResult,
    RecommendationCategory,
    RecommendationPriority
)


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider for testing."""
    
    def __init__(self):
        config = LLMConfig(
            provider="mock",
            model="mock-model",
            api_key="mock-key",
            base_url=None,
            temperature=0.7,
            max_tokens=1000
        )
        super().__init__(config)
    
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        """Mock completion generation."""
        # Return a mock response with sample recommendations
        mock_response = """1. [Language] [Priority: High] Issue: Weak phrase "responsible for" detected
   Suggestion: Replace with stronger action verb like "Led" or "Managed"
   Location: Experience: Senior Engineer at TechCorp
   Reasoning: Weak phrases reduce impact

2. [Metrics] [Priority: High] Issue: Description lacks quantifiable metrics
   Suggestion: Add specific numbers or percentages
   Location: Experience: Senior Engineer at TechCorp
   Reasoning: Metrics make impact concrete

3. [Structure] [Priority: Medium] Issue: Missing professional summary
   Suggestion: Add a 3-4 sentence summary at the top
   Location: Professional Summary
   Reasoning: Helps recruiters understand value quickly"""
        
        return LLMResponse(
            content=mock_response,
            model="mock-model",
            provider="mock",
            usage={"prompt_tokens": 100, "completion_tokens": 200}
        )
    
    async def generate_structured_output(
        self,
        prompt: str,
        schema: dict,
        system_prompt: str = None,
        temperature: float = 0.7
    ) -> dict:
        """Mock structured output generation."""
        return {}
    
    def get_provider_name(self) -> str:
        return "mock"
    
    def is_enabled(self) -> bool:
        return True
    
    async def test_connection(self) -> bool:
        return True
    
    def validate_config(self) -> bool:
        """Validate configuration."""
        return True


@pytest.fixture
def mock_provider():
    """Create mock LLM provider."""
    return MockLLMProvider()


@pytest.fixture
def optimizer(mock_provider):
    """Create CV optimizer with mock provider."""
    return CVOptimizer(mock_provider)


@pytest.fixture
def sample_cv_data():
    """Sample CV data for testing."""
    return {
        "id": "test-cv-id",
        "personal_info": {
            "name": "John Doe",
            "title": "Software Engineer"
        },
        "summary": "",
        "experience": [
            {
                "id": "exp-1",
                "title": "Senior Engineer",
                "company": "TechCorp",
                "start_date": "2020-01",
                "description": "Responsible for developing applications",
                "achievements": []
            }
        ],
        "education": [],
        "skills": {"categories": []},
        "certifications": []
    }


@pytest.mark.asyncio
async def test_optimize_cv_basic(optimizer, sample_cv_data):
    """Test basic CV optimization."""
    request = OptimizationRequest(
        cv_id="test-cv-id",
        cv_data=sample_cv_data
    )
    
    result = await optimizer.optimize_cv(request)
    
    assert isinstance(result, OptimizationResult)
    assert result.cv_id == "test-cv-id"
    assert 0 <= result.overall_score <= 100
    assert len(result.recommendations) > 0
    assert result.summary
    assert result.model == "mock-model"
    assert result.provider == "mock"


@pytest.mark.asyncio
async def test_detect_weak_language(optimizer, sample_cv_data):
    """Test weak language detection."""
    recommendations = optimizer._detect_weak_language(sample_cv_data)
    
    # Should detect "responsible for" as weak language
    assert len(recommendations) > 0
    weak_language_recs = [
        r for r in recommendations
        if r.category == RecommendationCategory.LANGUAGE
    ]
    assert len(weak_language_recs) > 0


@pytest.mark.asyncio
async def test_identify_metrics_gaps(optimizer, sample_cv_data):
    """Test metrics gap identification."""
    recommendations = optimizer._identify_metrics_gaps(sample_cv_data)
    
    # Should identify missing metrics
    assert len(recommendations) > 0
    metrics_recs = [
        r for r in recommendations
        if r.category == RecommendationCategory.METRICS
    ]
    assert len(metrics_recs) > 0


@pytest.mark.asyncio
async def test_analyze_structure(optimizer, sample_cv_data):
    """Test structural analysis."""
    recommendations = optimizer._analyze_structure(sample_cv_data)
    
    # Should identify missing summary and other structural issues
    assert len(recommendations) > 0
    structure_recs = [
        r for r in recommendations
        if r.category == RecommendationCategory.STRUCTURE
    ]
    assert len(structure_recs) > 0


def test_contains_weak_language(optimizer):
    """Test weak language detection helper."""
    assert optimizer._contains_weak_language("I was responsible for managing the team")
    assert optimizer._contains_weak_language("Worked on various projects")
    assert not optimizer._contains_weak_language("Led team of 5 developers")


def test_contains_passive_voice(optimizer):
    """Test passive voice detection."""
    assert optimizer._contains_passive_voice("The project was completed by me")
    assert optimizer._contains_passive_voice("Tasks were assigned to team members")
    assert not optimizer._contains_passive_voice("I completed the project")


def test_contains_metrics(optimizer):
    """Test metrics detection."""
    assert optimizer._contains_metrics("Improved performance by 40%")
    assert optimizer._contains_metrics("Led team of 5 developers")
    assert optimizer._contains_metrics("Saved $50,000 annually")
    assert not optimizer._contains_metrics("Improved system performance")


def test_calculate_overall_score(optimizer, sample_cv_data):
    """Test overall score calculation."""
    from app.models.llm_models import OptimizationRecommendation
    
    # Test with no recommendations
    score = optimizer._calculate_overall_score([], sample_cv_data)
    assert 0 <= score <= 100
    
    # Test with high priority recommendations
    high_priority_recs = [
        OptimizationRecommendation(
            category=RecommendationCategory.LANGUAGE,
            priority=RecommendationPriority.HIGH,
            issue="Test issue",
            suggestion="Test suggestion",
            location="Test location"
        )
        for _ in range(3)
    ]
    
    score_with_issues = optimizer._calculate_overall_score(high_priority_recs, sample_cv_data)
    assert score_with_issues < score  # Score should be lower with issues


def test_identify_strengths(optimizer):
    """Test strength identification."""
    cv_with_strengths = {
        "summary": "Experienced software engineer",
        "experience": [
            {
                "achievements": ["Improved performance by 40%"]
            },
            {},
            {}
        ],
        "skills": {
            "categories": [
                {"name": "Languages", "skills": ["Python"]},
                {"name": "Frameworks", "skills": ["Django"]}
            ]
        },
        "education": [{"degree": "BS Computer Science"}],
        "certifications": [{"name": "AWS Certified"}]
    }
    
    strengths = optimizer._identify_strengths(cv_with_strengths)
    assert len(strengths) > 0
    assert any("summary" in s.lower() for s in strengths)


def test_optimizer_factory():
    """Test optimizer factory."""
    provider = MockLLMProvider()
    optimizer = CVOptimizerFactory.create_optimizer(provider)
    
    assert isinstance(optimizer, CVOptimizer)
    assert optimizer.llm_provider == provider


def test_get_provider_info(optimizer):
    """Test getting provider information."""
    info = optimizer.get_provider_info()
    
    assert "provider" in info
    assert "enabled" in info
    assert "model" in info
    assert info["provider"] == "mock"
    assert info["model"] == "mock-model"
