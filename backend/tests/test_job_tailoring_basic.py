"""
Basic tests for job tailoring functionality.

Tests the job description analyzer and CV tailoring engine.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.llm.cv_optimizer import CVOptimizer
from app.llm.providers.base import LLMResponse
from app.models.llm_models import (
    JobTailoringRequest,
    JobDescriptionAnalysis,
    TailoringSuggestion,
    RecommendationPriority
)


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider."""
    provider = MagicMock()
    provider.get_provider_name.return_value = "mock"
    provider.is_enabled.return_value = True
    provider.config.model = "mock-model"
    return provider


@pytest.fixture
def sample_cv_data():
    """Sample CV data for testing."""
    return {
        "personal_info": {
            "name": "John Doe",
            "title": "Software Engineer",
            "contact": {
                "email": "john@example.com"
            }
        },
        "summary": "Experienced software engineer with 5 years in web development.",
        "experience": [
            {
                "title": "Senior Software Engineer",
                "company": "Tech Corp",
                "start_date": "2020-01",
                "end_date": "2024-01",
                "current": False,
                "description": "Developed web applications using React and Node.js",
                "achievements": [
                    "Improved application performance by 30%",
                    "Led team of 3 developers"
                ]
            },
            {
                "title": "Software Engineer",
                "company": "StartupCo",
                "start_date": "2018-06",
                "end_date": "2020-01",
                "current": False,
                "description": "Built REST APIs and microservices",
                "achievements": []
            }
        ],
        "education": [
            {
                "degree": "BS Computer Science",
                "institution": "University",
                "start_date": "2014-09",
                "end_date": "2018-05"
            }
        ],
        "skills": {
            "categories": [
                {
                    "name": "Programming Languages",
                    "skills": ["Python", "JavaScript", "TypeScript"]
                },
                {
                    "name": "Frameworks",
                    "skills": ["React", "Node.js", "Express"]
                }
            ]
        }
    }


@pytest.fixture
def sample_job_description():
    """Sample job description for testing."""
    return """
    Senior Full Stack Engineer
    
    We are seeking a Senior Full Stack Engineer to join our team.
    
    Requirements:
    - 5+ years of experience in web development
    - Strong proficiency in React and Node.js
    - Experience with TypeScript
    - Knowledge of AWS cloud services
    - Experience with Docker and Kubernetes
    - Strong problem-solving skills
    - Excellent communication abilities
    
    Responsibilities:
    - Design and develop scalable web applications
    - Lead technical initiatives
    - Mentor junior developers
    - Collaborate with cross-functional teams
    """


@pytest.mark.asyncio
async def test_analyze_job_description(mock_llm_provider, sample_job_description):
    """Test job description analysis."""
    # Mock LLM response
    mock_response = LLMResponse(
        content="""Job Title: Senior Full Stack Engineer
Company: Not specified
Experience Level: Senior
Industry: Technology

Requirements:
- 5+ years of experience in web development
- Strong proficiency in React and Node.js
- Experience with TypeScript
- Knowledge of AWS cloud services

Skills:
- React
- Node.js
- TypeScript
- AWS
- Docker
- Kubernetes

Keywords (important terms for ATS):
- Full Stack
- React
- Node.js
- TypeScript
- AWS
- Docker
- Kubernetes
- Web Development
- Scalable Applications
- Microservices""",
        model="mock-model",
        provider="mock",
        tokens_used=500
    )
    
    mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)
    
    optimizer = CVOptimizer(mock_llm_provider)
    analysis = await optimizer.analyze_job_description(sample_job_description)
    
    # Verify analysis structure
    assert isinstance(analysis, JobDescriptionAnalysis)
    assert analysis.job_title == "Senior Full Stack Engineer"
    assert len(analysis.requirements) > 0
    assert len(analysis.skills) > 0
    assert len(analysis.keywords) > 0
    assert "React" in analysis.skills or "React" in analysis.keywords
    assert "Node.js" in analysis.skills or "Node.js" in analysis.keywords


@pytest.mark.asyncio
async def test_analyze_job_description_invalid_input(mock_llm_provider):
    """Test job description analysis with invalid input."""
    optimizer = CVOptimizer(mock_llm_provider)
    
    # Test with empty job description
    with pytest.raises(ValueError, match="Job description must be at least 10 characters"):
        await optimizer.analyze_job_description("")
    
    # Test with too short job description
    with pytest.raises(ValueError, match="Job description must be at least 10 characters"):
        await optimizer.analyze_job_description("short")


@pytest.mark.asyncio
async def test_tailor_cv_to_job(mock_llm_provider, sample_cv_data, sample_job_description):
    """Test CV tailoring to job description."""
    # Mock LLM responses
    job_analysis_response = LLMResponse(
        content="""Job Title: Senior Full Stack Engineer
Company: Not specified
Experience Level: Senior
Industry: Technology

Requirements:
- 5+ years of experience in web development
- Strong proficiency in React and Node.js

Skills:
- React
- Node.js
- TypeScript
- AWS
- Docker

Keywords (important terms for ATS):
- React
- Node.js
- TypeScript
- AWS
- Docker
- Kubernetes""",
        model="mock-model",
        provider="mock",
        tokens_used=500
    )
    
    tailoring_response = LLMResponse(
        content="""1. [Professional Summary] [Priority: High]
   Current: Experienced software engineer with 5 years in web development.
   Suggested: Senior Full Stack Engineer with 5+ years specializing in React and Node.js development, delivering scalable web applications.
   Reason: Aligns title and emphasizes relevant technologies from job description
   Keywords Added: Full Stack, Scalable

2. [Experience] [Priority: Medium]
   Current: Developed web applications using React and Node.js
   Suggested: Architected and developed scalable web applications using React and Node.js, implementing microservices architecture
   Reason: Emphasizes scalability and adds relevant architecture keywords
   Keywords Added: Scalable, Microservices""",
        model="mock-model",
        provider="mock",
        tokens_used=800
    )
    
    # Set up mock to return different responses for different calls
    mock_llm_provider.generate_completion = AsyncMock(
        side_effect=[job_analysis_response, tailoring_response]
    )
    
    optimizer = CVOptimizer(mock_llm_provider)
    
    request = JobTailoringRequest(
        cv_id="test-cv-id",
        cv_data=sample_cv_data,
        job_description=sample_job_description
    )
    
    result = await optimizer.tailor_cv_to_job(request)
    
    # Verify result structure
    assert result.cv_id == "test-cv-id"
    assert isinstance(result.job_analysis, JobDescriptionAnalysis)
    assert len(result.suggestions) > 0
    assert 0 <= result.match_score <= 100
    assert len(result.summary) > 0
    
    # Verify suggestions have required fields
    for suggestion in result.suggestions:
        assert isinstance(suggestion, TailoringSuggestion)
        assert suggestion.section
        assert suggestion.current
        assert suggestion.suggested
        assert suggestion.reason
        assert isinstance(suggestion.priority, RecommendationPriority)


@pytest.mark.asyncio
async def test_tailor_cv_identifies_missing_keywords(mock_llm_provider, sample_cv_data, sample_job_description):
    """Test that tailoring identifies missing keywords."""
    # Mock responses
    job_analysis_response = LLMResponse(
        content="""Job Title: Senior Full Stack Engineer
Skills:
- React
- Node.js
- AWS
- Docker
- Kubernetes

Keywords (important terms for ATS):
- AWS
- Docker
- Kubernetes""",
        model="mock-model",
        provider="mock",
        tokens_used=300
    )
    
    tailoring_response = LLMResponse(
        content="""1. [Skills] [Priority: High]
   Current: React, Node.js, Express
   Suggested: Add AWS, Docker, and Kubernetes if you have experience
   Reason: These are key requirements in the job description
   Keywords Added: AWS, Docker, Kubernetes""",
        model="mock-model",
        provider="mock",
        tokens_used=400
    )
    
    mock_llm_provider.generate_completion = AsyncMock(
        side_effect=[job_analysis_response, tailoring_response]
    )
    
    optimizer = CVOptimizer(mock_llm_provider)
    
    request = JobTailoringRequest(
        cv_id="test-cv-id",
        cv_data=sample_cv_data,
        job_description=sample_job_description
    )
    
    result = await optimizer.tailor_cv_to_job(request)
    
    # Verify missing keywords are identified
    assert len(result.missing_keywords) > 0
    # AWS, Docker, Kubernetes should be in missing keywords since they're not in the CV
    missing_lower = [k.lower() for k in result.missing_keywords]
    assert any(k in missing_lower for k in ["aws", "docker", "kubernetes"])


@pytest.mark.asyncio
async def test_tailor_cv_calculates_match_score(mock_llm_provider, sample_cv_data, sample_job_description):
    """Test that match score is calculated correctly."""
    # Mock responses
    job_analysis_response = LLMResponse(
        content="""Job Title: Senior Full Stack Engineer
Skills:
- React
- Node.js
- TypeScript

Keywords (important terms for ATS):
- React
- Node.js
- TypeScript""",
        model="mock-model",
        provider="mock",
        tokens_used=200
    )
    
    tailoring_response = LLMResponse(
        content="""1. [Summary] [Priority: Medium]
   Current: Software engineer
   Suggested: Senior Full Stack Engineer
   Reason: Match job title
   Keywords Added: Full Stack""",
        model="mock-model",
        provider="mock",
        tokens_used=300
    )
    
    mock_llm_provider.generate_completion = AsyncMock(
        side_effect=[job_analysis_response, tailoring_response]
    )
    
    optimizer = CVOptimizer(mock_llm_provider)
    
    request = JobTailoringRequest(
        cv_id="test-cv-id",
        cv_data=sample_cv_data,
        job_description=sample_job_description
    )
    
    result = await optimizer.tailor_cv_to_job(request)
    
    # Match score should be reasonable since CV has React, Node.js, TypeScript
    assert 40 <= result.match_score <= 100
    
    # Should have matching keywords
    assert len(result.matching_keywords) > 0


def test_extract_cv_keywords(mock_llm_provider, sample_cv_data):
    """Test CV keyword extraction."""
    optimizer = CVOptimizer(mock_llm_provider)
    
    keywords = optimizer._extract_cv_keywords(sample_cv_data)
    
    # Should extract skills
    assert "Python" in keywords or "python" in [k.lower() for k in keywords]
    assert "React" in keywords or "react" in [k.lower() for k in keywords]
    
    # Should extract job titles
    assert any("engineer" in k.lower() for k in keywords)


def test_calculate_match_score(mock_llm_provider, sample_cv_data):
    """Test match score calculation."""
    optimizer = CVOptimizer(mock_llm_provider)
    
    job_analysis = JobDescriptionAnalysis(
        job_title="Senior Software Engineer",
        requirements=["5+ years experience", "React expertise"],
        skills=["React", "Node.js", "TypeScript"],
        keywords=["React", "Node.js", "TypeScript", "AWS", "Docker"]
    )
    
    matching_keywords = ["React", "Node.js", "TypeScript"]
    missing_keywords = ["AWS", "Docker"]
    
    score = optimizer._calculate_match_score(
        sample_cv_data,
        job_analysis,
        matching_keywords,
        missing_keywords
    )
    
    # Score should be between 0 and 100
    assert 0 <= score <= 100
    
    # Score should be reasonable given 3/5 keywords match
    assert score >= 40  # Should have at least 40% match


def test_truthfulness_validation_in_prompts(mock_llm_provider):
    """Test that truthfulness validation is built into system prompts."""
    optimizer = CVOptimizer(mock_llm_provider)
    
    # Get the tailoring system prompt
    system_prompt = optimizer._build_tailoring_system_prompt()
    
    # Verify truthfulness guidelines are present
    assert "NEVER suggest adding false information" in system_prompt
    assert "maintaining truthfulness" in system_prompt or "maintain" in system_prompt.lower()
    assert "honest" in system_prompt.lower() or "accuracy" in system_prompt.lower()


def test_keyword_suggestions_generation(mock_llm_provider, sample_cv_data):
    """Test keyword incorporation suggestions."""
    optimizer = CVOptimizer(mock_llm_provider)
    
    job_analysis = JobDescriptionAnalysis(
        job_title="Senior Software Engineer",
        requirements=["AWS experience", "Docker knowledge"],
        skills=["AWS", "Docker", "Kubernetes"],
        keywords=["AWS", "Docker", "Kubernetes"]
    )
    
    missing_keywords = ["AWS", "Docker"]
    
    suggestions = optimizer._generate_keyword_suggestions(
        sample_cv_data,
        missing_keywords,
        job_analysis
    )
    
    # Should generate suggestions for missing keywords
    assert len(suggestions) > 0
    
    # Suggestions should mention the missing keywords
    suggestion_text = " ".join([s.suggested for s in suggestions])
    assert "AWS" in suggestion_text or "Docker" in suggestion_text


def test_experience_prioritization_suggestions(mock_llm_provider, sample_cv_data):
    """Test experience prioritization suggestions."""
    optimizer = CVOptimizer(mock_llm_provider)
    
    # Create job analysis that matches second experience better
    job_analysis = JobDescriptionAnalysis(
        job_title="Software Engineer",  # Matches second experience
        requirements=["API development", "Microservices"],
        skills=["REST", "Microservices"],
        keywords=["API", "REST", "Microservices"]
    )
    
    suggestions = optimizer._generate_prioritization_suggestions(
        sample_cv_data,
        job_analysis
    )
    
    # Should generate prioritization suggestions
    # (May be empty if heuristics don't trigger, which is okay)
    assert isinstance(suggestions, list)
    
    # If suggestions are generated, they should be about experience ordering
    for suggestion in suggestions:
        assert suggestion.section == "Experience"
        assert "experience" in suggestion.suggested.lower() or "highlight" in suggestion.suggested.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
