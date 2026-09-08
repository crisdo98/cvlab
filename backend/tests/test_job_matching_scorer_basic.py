"""
Basic tests for Job Matching Scorer functionality.

These tests verify the core functionality of the job matching scorer including
match score calculation, skill matching, requirement matching, and detailed breakdown.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.llm.cv_optimizer import CVOptimizer
from app.llm.providers.base import BaseLLMProvider, LLMResponse, LLMConfig
from app.models.llm_models import (
    JobMatchRequest,
    JobMatchResult,
    JobMatchScoreBreakdown,
    JobDescriptionAnalysis
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
        self.call_count = 0
    
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        """Mock completion generation."""
        self.call_count += 1
        
        # First call: job description analysis
        if self.call_count == 1:
            mock_response = """Job Title: Senior Software Engineer
Company: TechCorp Inc
Experience Level: Senior level
Industry: Technology

Requirements:
- 5+ years of software development experience
- Strong knowledge of Python and JavaScript
- Experience with cloud platforms (AWS, Azure, or GCP)
- Leadership and mentoring experience
- Bachelor's degree in Computer Science or related field

Skills:
- Python
- JavaScript
- AWS
- Docker
- Kubernetes
- React
- Node.js
- SQL

Keywords (important terms for ATS):
- Software Development
- Cloud Computing
- Microservices
- CI/CD
- Agile
- Team Leadership
- API Development
- Database Design"""
        
        # Second call: requirement matching
        elif self.call_count == 2:
            mock_response = """MET:
- 5+ years of software development experience
- Strong knowledge of Python and JavaScript
- Experience with cloud platforms (AWS, Azure, or GCP)

NOT MET:
- Leadership and mentoring experience
- Bachelor's degree in Computer Science or related field"""
        
        else:
            mock_response = "Mock response"
        
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
            "name": "Jane Smith",
            "title": "Software Engineer"
        },
        "summary": "Experienced software engineer with 6 years of experience in Python and JavaScript development. Skilled in cloud platforms and microservices architecture.",
        "experience": [
            {
                "id": "exp-1",
                "title": "Software Engineer",
                "company": "Tech Solutions Inc",
                "start_date": "2018-01",
                "end_date": "2024-01",
                "description": "Developed cloud-based applications using Python and AWS. Built microservices architecture and implemented CI/CD pipelines.",
                "achievements": [
                    "Improved system performance by 40%",
                    "Led migration to AWS cloud infrastructure"
                ]
            },
            {
                "id": "exp-2",
                "title": "Junior Developer",
                "company": "StartupCo",
                "start_date": "2016-06",
                "end_date": "2018-01",
                "description": "Worked on web applications using JavaScript and React.",
                "achievements": []
            }
        ],
        "education": [
            {
                "id": "edu-1",
                "degree": "Associate Degree in Computer Programming",
                "institution": "Community College",
                "start_date": "2014-09",
                "end_date": "2016-05"
            }
        ],
        "skills": {
            "categories": [
                {
                    "name": "Programming Languages",
                    "skills": ["Python", "JavaScript", "SQL"]
                },
                {
                    "name": "Cloud & DevOps",
                    "skills": ["AWS", "Docker", "CI/CD"]
                },
                {
                    "name": "Web Technologies",
                    "skills": ["React", "Node.js", "REST APIs"]
                }
            ]
        },
        "certifications": [
            {
                "id": "cert-1",
                "name": "AWS Certified Developer",
                "issuer": "Amazon Web Services"
            }
        ]
    }


@pytest.fixture
def sample_job_description():
    """Sample job description for testing."""
    return """Senior Software Engineer - TechCorp Inc

We are seeking a Senior Software Engineer to join our growing team. The ideal candidate will have:

Requirements:
- 5+ years of software development experience
- Strong knowledge of Python and JavaScript
- Experience with cloud platforms (AWS, Azure, or GCP)
- Leadership and mentoring experience
- Bachelor's degree in Computer Science or related field

Responsibilities:
- Design and develop scalable microservices
- Lead technical projects and mentor junior developers
- Implement CI/CD pipelines and DevOps practices
- Collaborate with cross-functional teams

Skills:
Python, JavaScript, AWS, Docker, Kubernetes, React, Node.js, SQL, Microservices, CI/CD, Agile"""


@pytest.mark.asyncio
async def test_match_cv_to_job_basic(optimizer, sample_cv_data, sample_job_description):
    """Test basic job matching functionality."""
    request = JobMatchRequest(
        cv_id="test-cv-id",
        cv_data=sample_cv_data,
        job_description=sample_job_description
    )
    
    result = await optimizer.match_cv_to_job(request)
    
    # Verify result structure
    assert isinstance(result, JobMatchResult)
    assert result.cv_id == "test-cv-id"
    assert isinstance(result.job_analysis, JobDescriptionAnalysis)
    assert isinstance(result.score_breakdown, JobMatchScoreBreakdown)
    
    # Verify score breakdown
    assert 0 <= result.score_breakdown.overall_score <= 100
    assert 0 <= result.score_breakdown.keyword_alignment_score <= 100
    assert 0 <= result.score_breakdown.experience_relevance_score <= 100
    assert 0 <= result.score_breakdown.skills_match_score <= 100
    assert 0 <= result.score_breakdown.requirements_match_score <= 100
    
    # Verify lists are populated
    assert isinstance(result.matched_skills, list)
    assert isinstance(result.missing_skills, list)
    assert isinstance(result.matched_requirements, list)
    assert isinstance(result.missing_requirements, list)
    assert isinstance(result.matched_keywords, list)
    assert isinstance(result.missing_keywords, list)
    assert isinstance(result.qualification_gaps, list)
    assert isinstance(result.strengths, list)
    assert isinstance(result.recommendations, list)
    
    # Verify summary
    assert result.summary
    assert len(result.summary) > 0
    
    # Verify metadata
    assert result.model == "mock-model"
    assert result.provider == "mock"


@pytest.mark.asyncio
async def test_match_cv_to_job_skill_matching(optimizer, sample_cv_data, sample_job_description):
    """Test skill matching in job matching."""
    request = JobMatchRequest(
        cv_id="test-cv-id",
        cv_data=sample_cv_data,
        job_description=sample_job_description
    )
    
    result = await optimizer.match_cv_to_job(request)
    
    # Should match Python, JavaScript, AWS, Docker, React, Node.js, SQL
    assert len(result.matched_skills) > 0
    assert "Python" in result.matched_skills or any("python" in s.lower() for s in result.matched_skills)
    
    # Should identify missing skills like Kubernetes
    assert len(result.missing_skills) > 0


@pytest.mark.asyncio
async def test_match_cv_to_job_requirements(optimizer, sample_cv_data, sample_job_description):
    """Test requirement matching in job matching."""
    request = JobMatchRequest(
        cv_id="test-cv-id",
        cv_data=sample_cv_data,
        job_description=sample_job_description
    )
    
    result = await optimizer.match_cv_to_job(request)
    
    # Should have both matched and missing requirements
    assert len(result.matched_requirements) > 0
    assert len(result.missing_requirements) > 0
    
    # Total requirements should match job analysis
    total_reqs = len(result.matched_requirements) + len(result.missing_requirements)
    assert total_reqs > 0


@pytest.mark.asyncio
async def test_match_cv_to_job_qualification_gaps(optimizer, sample_cv_data, sample_job_description):
    """Test qualification gap identification."""
    request = JobMatchRequest(
        cv_id="test-cv-id",
        cv_data=sample_cv_data,
        job_description=sample_job_description
    )
    
    result = await optimizer.match_cv_to_job(request)
    
    # Should identify some qualification gaps
    assert isinstance(result.qualification_gaps, list)
    # Gaps might include missing Bachelor's degree, leadership experience, etc.


@pytest.mark.asyncio
async def test_match_cv_to_job_strengths(optimizer, sample_cv_data, sample_job_description):
    """Test strength identification."""
    request = JobMatchRequest(
        cv_id="test-cv-id",
        cv_data=sample_cv_data,
        job_description=sample_job_description
    )
    
    result = await optimizer.match_cv_to_job(request)
    
    # Should identify strengths
    assert len(result.strengths) > 0
    # Should mention skill alignment or experience


@pytest.mark.asyncio
async def test_match_cv_to_job_recommendations(optimizer, sample_cv_data, sample_job_description):
    """Test recommendation generation."""
    request = JobMatchRequest(
        cv_id="test-cv-id",
        cv_data=sample_cv_data,
        job_description=sample_job_description
    )
    
    result = await optimizer.match_cv_to_job(request)
    
    # Should provide recommendations
    assert len(result.recommendations) > 0
    # Recommendations should be actionable strings


def test_calculate_keyword_alignment_score(optimizer):
    """Test keyword alignment score calculation."""
    # Perfect match
    score = optimizer._calculate_keyword_alignment_score(
        matched_keywords=["Python", "AWS", "Docker"],
        missing_keywords=[]
    )
    assert score == 100.0
    
    # 50% match
    score = optimizer._calculate_keyword_alignment_score(
        matched_keywords=["Python", "AWS"],
        missing_keywords=["Docker", "Kubernetes"]
    )
    assert score == 50.0
    
    # No keywords
    score = optimizer._calculate_keyword_alignment_score(
        matched_keywords=[],
        missing_keywords=[]
    )
    assert score == 50.0  # Neutral score


def test_calculate_skills_match_score(optimizer):
    """Test skills match score calculation."""
    # Perfect match
    score = optimizer._calculate_skills_match_score(
        matched_skills=["Python", "JavaScript", "AWS"],
        missing_skills=[]
    )
    assert score == 100.0
    
    # 60% match
    score = optimizer._calculate_skills_match_score(
        matched_skills=["Python", "JavaScript", "AWS"],
        missing_skills=["Kubernetes", "Go"]
    )
    assert score == 60.0


def test_calculate_requirements_match_score(optimizer):
    """Test requirements match score calculation."""
    # 75% match
    score = optimizer._calculate_requirements_match_score(
        matched_requirements=["5+ years experience", "Python knowledge", "Cloud experience"],
        missing_requirements=["Bachelor's degree"]
    )
    assert score == 75.0


def test_calculate_experience_relevance_score(optimizer):
    """Test experience relevance score calculation."""
    experiences = [
        {
            "title": "Software Engineer",
            "company": "TechCorp",
            "description": "Developed software applications"
        },
        {
            "title": "Developer",
            "company": "StartupCo",
            "description": "Built web applications"
        }
    ]
    
    job_analysis = JobDescriptionAnalysis(
        job_title="Software Engineer",
        company="TechCorp Inc",
        requirements=[],
        skills=[],
        keywords=[],
        experience_level="Mid level",
        industry="Technology"
    )
    
    score = optimizer._calculate_experience_relevance_score(experiences, job_analysis)
    
    # Should get points for title match
    assert score > 0
    assert score <= 100


def test_extract_cv_skills(optimizer, sample_cv_data):
    """Test CV skills extraction."""
    skills = optimizer._extract_cv_skills(sample_cv_data)
    
    assert len(skills) > 0
    assert "Python" in skills
    assert "JavaScript" in skills
    assert "AWS" in skills


def test_identify_qualification_gaps(optimizer):
    """Test qualification gap identification."""
    missing_skills = ["Kubernetes", "Go", "GraphQL"]
    missing_requirements = ["Bachelor's degree", "Leadership experience"]
    
    job_analysis = JobDescriptionAnalysis(
        job_title="Senior Software Engineer",
        company="TechCorp",
        requirements=missing_requirements,
        skills=missing_skills,
        keywords=[],
        experience_level="Senior level",
        industry="Technology"
    )
    
    gaps = optimizer._identify_qualification_gaps(
        missing_skills,
        missing_requirements,
        job_analysis
    )
    
    assert len(gaps) > 0
    # Should mention missing skills and requirements


def test_identify_match_strengths(optimizer, sample_cv_data):
    """Test match strength identification."""
    matched_skills = ["Python", "JavaScript", "AWS", "Docker", "React"]
    matched_requirements = ["5+ years experience", "Python knowledge", "Cloud experience"]
    
    job_analysis = JobDescriptionAnalysis(
        job_title="Software Engineer",
        company="TechCorp",
        requirements=matched_requirements,
        skills=matched_skills,
        keywords=[],
        experience_level="Mid level",
        industry="Technology"
    )
    
    strengths = optimizer._identify_match_strengths(
        matched_skills,
        matched_requirements,
        sample_cv_data,
        job_analysis
    )
    
    assert len(strengths) > 0
    # Should mention skill alignment or requirements met


def test_generate_match_recommendations(optimizer):
    """Test match recommendation generation."""
    missing_skills = ["Kubernetes", "Go"]
    missing_requirements = ["Bachelor's degree"]
    missing_keywords = ["Microservices", "GraphQL", "Redis"]
    qualification_gaps = ["Missing Bachelor's degree", "Limited leadership experience"]
    
    recommendations = optimizer._generate_match_recommendations(
        missing_skills,
        missing_requirements,
        missing_keywords,
        qualification_gaps,
        overall_score=65.0
    )
    
    assert len(recommendations) > 0
    # Should provide actionable recommendations


@pytest.mark.asyncio
async def test_match_cv_to_job_with_empty_cv(optimizer, sample_job_description):
    """Test job matching with minimal CV data."""
    minimal_cv = {
        "id": "test-cv-id",
        "personal_info": {"name": "Test User", "title": "Developer"},
        "summary": "",
        "experience": [],
        "education": [],
        "skills": {"categories": []},
        "certifications": []
    }
    
    request = JobMatchRequest(
        cv_id="test-cv-id",
        cv_data=minimal_cv,
        job_description=sample_job_description
    )
    
    result = await optimizer.match_cv_to_job(request)
    
    # Should still return valid result with low scores
    assert isinstance(result, JobMatchResult)
    assert result.score_breakdown.overall_score < 50  # Low score expected
    assert len(result.missing_skills) > 0
    assert len(result.qualification_gaps) > 0


@pytest.mark.asyncio
async def test_match_cv_to_job_summary_quality(optimizer, sample_cv_data, sample_job_description):
    """Test that match summary is informative."""
    request = JobMatchRequest(
        cv_id="test-cv-id",
        cv_data=sample_cv_data,
        job_description=sample_job_description
    )
    
    result = await optimizer.match_cv_to_job(request)
    
    # Summary should mention key information
    summary_lower = result.summary.lower()
    assert "match" in summary_lower or "score" in summary_lower
    assert any(word in summary_lower for word in ["excellent", "good", "moderate", "low"])
    # Should mention the job title
    assert "engineer" in summary_lower or "software" in summary_lower
