"""
Basic tests for ATS Analyzer functionality.

These tests verify the core functionality of the ATS analyzer including
keyword identification, keyword stuffing detection, and compatibility scoring.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.llm.ats_analyzer import ATSAnalyzer, ATSAnalyzerFactory
from app.llm.providers.base import BaseLLMProvider, LLMResponse, LLMConfig
from app.models.llm_models import (
    ATSAnalysisRequest,
    ATSAnalysisResult,
    ATSCompatibilityScore,
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
        # Return a mock response with sample ATS recommendations
        mock_response = """1. [Keywords] [Priority: High]
   Issue: Missing industry-standard keywords
   Suggestion: Add relevant technical keywords like Python, AWS, Docker
   Impact: Improves ATS keyword matching and search visibility

2. [Formatting] [Priority: High]
   Issue: Missing contact information
   Suggestion: Include email and phone number in contact section
   Impact: Ensures ATS can properly parse your CV

3. [Structure] [Priority: Medium]
   Issue: Skills section could be better organized
   Suggestion: Group skills into clear categories
   Impact: Helps ATS categorize your qualifications"""
        
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
def analyzer(mock_provider):
    """Create ATS analyzer with mock provider."""
    return ATSAnalyzer(mock_provider)


@pytest.fixture
def sample_cv_data():
    """Sample CV data for testing."""
    return {
        "id": "test-cv-id",
        "personal_info": {
            "name": "John Doe",
            "title": "Software Engineer",
            "contact": {
                "email": "john@example.com",
                "phone": "+1-555-0100"
            }
        },
        "summary": "Experienced software engineer with Python and AWS expertise",
        "experience": [
            {
                "id": "exp-1",
                "title": "Senior Software Engineer",
                "company": "TechCorp",
                "start_date": "2020-01",
                "description": "Developed Python applications using AWS and Docker",
                "achievements": ["Improved system performance by 40%"]
            }
        ],
        "education": [
            {
                "degree": "BS Computer Science",
                "institution": "University"
            }
        ],
        "skills": {
            "categories": [
                {
                    "name": "Languages",
                    "skills": ["Python", "JavaScript", "Java"]
                },
                {
                    "name": "Cloud",
                    "skills": ["AWS", "Docker", "Kubernetes"]
                }
            ]
        },
        "certifications": []
    }


@pytest.mark.asyncio
async def test_analyze_ats_compatibility_basic(analyzer, sample_cv_data):
    """Test basic ATS compatibility analysis."""
    request = ATSAnalysisRequest(
        cv_id="test-cv-id",
        cv_data=sample_cv_data,
        industry="software",
        job_title="Software Engineer"
    )
    
    result = await analyzer.analyze_ats_compatibility(request)
    
    assert isinstance(result, ATSAnalysisResult)
    assert result.cv_id == "test-cv-id"
    assert isinstance(result.compatibility_score, ATSCompatibilityScore)
    assert 0 <= result.compatibility_score.overall_score <= 100
    assert len(result.recommendations) > 0
    assert result.summary
    assert result.model == "mock-model"
    assert result.provider == "mock"


@pytest.mark.asyncio
async def test_identify_industry_keywords(analyzer, sample_cv_data):
    """Test industry keyword identification."""
    # Test with software industry
    keywords = analyzer._identify_industry_keywords(
        sample_cv_data,
        "software",
        "Software Engineer"
    )
    
    assert len(keywords) > 0
    assert any("python" in kw.lower() for kw in keywords)
    
    # Test with data industry
    keywords_data = analyzer._identify_industry_keywords(
        sample_cv_data,
        "data science",
        "Data Scientist"
    )
    
    assert len(keywords_data) > 0


@pytest.mark.asyncio
async def test_find_present_keywords(analyzer, sample_cv_data):
    """Test finding present keywords in CV."""
    industry_keywords = ["python", "aws", "docker", "kubernetes", "react", "vue"]
    
    present = analyzer._find_present_keywords(sample_cv_data, industry_keywords)
    
    # Should find python, aws, docker, kubernetes
    assert "python" in [k.lower() for k in present]
    assert "aws" in [k.lower() for k in present]
    assert "docker" in [k.lower() for k in present]
    
    # Should not find react or vue
    assert "react" not in [k.lower() for k in present]


@pytest.mark.asyncio
async def test_analyze_keyword_density(analyzer, sample_cv_data):
    """Test keyword density analysis."""
    industry_keywords = ["python", "aws", "docker"]
    
    density = analyzer._analyze_keyword_density(sample_cv_data, industry_keywords)
    
    assert isinstance(density, dict)
    # Python should have some density since it appears in the CV
    assert "python" in [k.lower() for k in density.keys()]
    
    # Density should be reasonable (not too high)
    for keyword, dens in density.items():
        assert 0 <= dens <= 10  # Should be less than 10% density


@pytest.mark.asyncio
async def test_detect_keyword_stuffing(analyzer):
    """Test keyword stuffing detection."""
    # Create CV with keyword stuffing - need more repetition to trigger threshold
    stuffed_cv = {
        "personal_info": {"name": "Test"},
        "summary": "Python " * 20,  # Repeat 20 times
        "experience": [
            {
                "description": "Python " * 30  # Repeat 30 times
            }
        ],
        "skills": {"categories": []},
        "education": []
    }
    
    # Calculate density first
    density = analyzer._analyze_keyword_density(stuffed_cv, ["python"])
    
    # Detect stuffing
    recommendations = analyzer._detect_keyword_stuffing(stuffed_cv, density)
    
    # Should detect keyword stuffing
    assert len(recommendations) > 0
    assert any("keyword" in rec.category.lower() for rec in recommendations)


@pytest.mark.asyncio
async def test_check_formatting_issues(analyzer, sample_cv_data):
    """Test formatting issue detection."""
    issues = analyzer._check_formatting_issues(sample_cv_data)
    
    # Sample CV should have minimal issues
    assert isinstance(issues, list)
    
    # Test with incomplete CV
    incomplete_cv = {
        "personal_info": {},
        "experience": [],
        "education": [],
        "skills": {}
    }
    
    issues_incomplete = analyzer._check_formatting_issues(incomplete_cv)
    
    # Should detect multiple issues
    assert len(issues_incomplete) > 0
    assert any("missing" in issue.lower() for issue in issues_incomplete)


def test_is_valid_date_format(analyzer):
    """Test date format validation."""
    # Valid formats
    assert analyzer._is_valid_date_format("2020-01")
    assert analyzer._is_valid_date_format("2020")
    assert analyzer._is_valid_date_format("Jan 2020")
    assert analyzer._is_valid_date_format("January 2020")
    assert analyzer._is_valid_date_format("01/2020")
    
    # Invalid formats
    assert not analyzer._is_valid_date_format("2020/01/15")
    assert not analyzer._is_valid_date_format("invalid")


@pytest.mark.asyncio
async def test_calculate_compatibility_scores(analyzer, sample_cv_data):
    """Test compatibility score calculation."""
    present_keywords = ["python", "aws", "docker"]
    missing_keywords = ["kubernetes", "react"]
    formatting_issues = []
    stuffing_issues = []
    
    score = analyzer._calculate_compatibility_scores(
        sample_cv_data,
        present_keywords,
        missing_keywords,
        formatting_issues,
        stuffing_issues
    )
    
    assert isinstance(score, ATSCompatibilityScore)
    assert 0 <= score.overall_score <= 100
    assert 0 <= score.keyword_score <= 100
    assert 0 <= score.formatting_score <= 100
    assert 0 <= score.structure_score <= 100
    assert 0 <= score.completeness_score <= 100
    
    # With good CV data, scores should be reasonable
    assert score.overall_score > 50


@pytest.mark.asyncio
async def test_calculate_compatibility_scores_with_issues(analyzer, sample_cv_data):
    """Test compatibility score calculation with issues."""
    present_keywords = ["python"]
    missing_keywords = ["aws", "docker", "kubernetes", "react", "vue"]
    formatting_issues = ["Missing email", "Missing phone"]
    stuffing_issues = [
        MagicMock(category="Keyword Stuffing", priority=RecommendationPriority.HIGH)
    ]
    
    score = analyzer._calculate_compatibility_scores(
        sample_cv_data,
        present_keywords,
        missing_keywords,
        formatting_issues,
        stuffing_issues
    )
    
    # Score should be lower with more issues
    assert score.overall_score < 80
    assert score.keyword_score < 50  # Many missing keywords
    assert score.formatting_score < 100  # Formatting issues


def test_extract_cv_text(analyzer, sample_cv_data):
    """Test CV text extraction."""
    text = analyzer._extract_cv_text(sample_cv_data)
    
    assert isinstance(text, str)
    assert len(text) > 0
    assert "john doe" in text.lower()
    assert "python" in text.lower()
    assert "aws" in text.lower()


def test_analyzer_factory():
    """Test analyzer factory."""
    provider = MockLLMProvider()
    analyzer = ATSAnalyzerFactory.create_analyzer(provider)
    
    assert isinstance(analyzer, ATSAnalyzer)
    assert analyzer.llm_provider == provider


def test_get_provider_info(analyzer):
    """Test getting provider information."""
    info = analyzer.get_provider_info()
    
    assert "provider" in info
    assert "enabled" in info
    assert "model" in info
    assert info["provider"] == "mock"
    assert info["model"] == "mock-model"


@pytest.mark.asyncio
async def test_generate_ats_summary(analyzer):
    """Test ATS summary generation."""
    score = ATSCompatibilityScore(
        overall_score=75.0,
        keyword_score=70.0,
        formatting_score=80.0,
        structure_score=75.0,
        completeness_score=75.0
    )
    
    summary = analyzer._generate_ats_summary(score, 10, 5, 2)
    
    assert isinstance(summary, str)
    assert len(summary) > 0
    assert "75" in summary or "good" in summary.lower()


@pytest.mark.asyncio
async def test_industry_keyword_detection_from_cv(analyzer):
    """Test industry detection from CV content."""
    # CV with software keywords
    software_cv = {
        "personal_info": {"name": "Test"},
        "summary": "Python developer with React and Node.js experience",
        "experience": [{"description": "Built APIs with Python and Docker"}],
        "skills": {"categories": [{"skills": ["Python", "JavaScript"]}]},
        "education": []
    }
    
    keywords = analyzer._identify_industry_keywords(software_cv, None, None)
    
    # Should detect software industry
    assert len(keywords) > 0
    assert any("python" in kw.lower() for kw in keywords)


@pytest.mark.asyncio
async def test_get_formatting_suggestion(analyzer):
    """Test formatting suggestion generation."""
    suggestion = analyzer._get_formatting_suggestion("Missing email address")
    
    assert isinstance(suggestion, str)
    assert len(suggestion) > 0
    assert "email" in suggestion.lower()
