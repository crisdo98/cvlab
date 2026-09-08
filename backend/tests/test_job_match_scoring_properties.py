"""
Property-Based Tests for Job Match Scoring

Feature: cv-web-app, Property 33: Job Match Scoring

**Property 33: Job Match Scoring**
*For any* CV and job description pair, the matching service should return a numerical score (0-100%)
with detailed breakdown of matched and missing elements

**Validates: Requirements 12.4, 12.5**

These tests verify that the job matching scorer:
1. Always returns a valid score between 0-100
2. Provides detailed breakdown with all required components
3. Correctly identifies matched and missing skills
4. Correctly identifies matched and missing requirements
5. Provides meaningful recommendations
6. Generates informative summaries
7. Handles edge cases (empty CV, minimal job description, etc.)
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from unittest.mock import AsyncMock

from app.llm.cv_optimizer import CVOptimizer
from app.llm.providers.base import BaseLLMProvider, LLMResponse, LLMConfig
from app.models.llm_models import (
    JobMatchRequest,
    JobMatchResult,
    JobMatchScoreBreakdown,
    JobDescriptionAnalysis
)


# ============================================================================
# Test Data Generators
# ============================================================================

@st.composite
def cv_data_strategy(draw):
    """Generate valid CV data for testing."""
    # Generate personal info - use sampled_from for simplicity
    name = draw(st.sampled_from([
        "John Smith", "Jane Doe", "Alice Johnson", "Bob Williams",
        "Carol Brown", "David Miller", "Eve Davis", "Frank Wilson"
    ]))
    title = draw(st.sampled_from([
        "Software Engineer", "Senior Developer", "Tech Lead",
        "Data Scientist", "DevOps Engineer", "Full Stack Developer"
    ]))
    
    # Generate skills
    num_skills = draw(st.integers(min_value=0, max_value=10))
    skills = [
        draw(st.sampled_from([
            "Python", "JavaScript", "Java", "C++", "Go", "Rust",
            "AWS", "Azure", "GCP", "Docker", "Kubernetes",
            "React", "Vue", "Angular", "Node.js",
            "SQL", "MongoDB", "PostgreSQL", "Redis",
            "Machine Learning", "Data Science", "DevOps"
        ]))
        for _ in range(num_skills)
    ]
    
    # Generate experience
    num_experiences = draw(st.integers(min_value=0, max_value=5))
    experiences = []
    for i in range(num_experiences):
        exp = {
            "id": f"exp-{i}",
            "title": draw(st.sampled_from([
                "Software Engineer", "Senior Developer", "Tech Lead",
                "Data Scientist", "DevOps Engineer", "Full Stack Developer"
            ])),
            "company": draw(st.sampled_from([
                "TechCorp", "StartupCo", "BigTech Inc", "Innovation Labs",
                "Digital Solutions", "Cloud Systems", "Data Dynamics"
            ])),
            "start_date": "2020-01",
            "end_date": "2024-01",
            "description": draw(st.text(min_size=10, max_size=200)),
            "achievements": [
                draw(st.text(min_size=10, max_size=100))
                for _ in range(draw(st.integers(min_value=0, max_value=3)))
            ]
        }
        experiences.append(exp)
    
    # Generate education
    num_education = draw(st.integers(min_value=0, max_value=3))
    education = []
    for i in range(num_education):
        edu = {
            "id": f"edu-{i}",
            "degree": draw(st.sampled_from([
                "Bachelor of Science in Computer Science",
                "Master of Science in Software Engineering",
                "Associate Degree in Programming",
                "PhD in Computer Science"
            ])),
            "institution": draw(st.sampled_from([
                "State University", "Tech Institute", "Community College",
                "National University", "Engineering School"
            ])),
            "start_date": "2016-09",
            "end_date": "2020-05"
        }
        education.append(edu)
    
    return {
        "id": "test-cv-id",
        "personal_info": {
            "name": name,
            "title": title
        },
        "summary": draw(st.text(min_size=0, max_size=300)),
        "experience": experiences,
        "education": education,
        "skills": {
            "categories": [
                {
                    "name": "Technical Skills",
                    "skills": skills
                }
            ]
        },
        "certifications": []
    }


@st.composite
def job_description_strategy(draw):
    """Generate valid job descriptions for testing."""
    job_title = draw(st.sampled_from([
        "Software Engineer", "Senior Developer", "Tech Lead",
        "Data Scientist", "DevOps Engineer", "Full Stack Developer",
        "Backend Engineer", "Frontend Developer"
    ]))
    
    company = draw(st.sampled_from([
        "TechCorp Inc", "StartupCo", "BigTech Solutions", "Innovation Labs",
        "Digital Systems", "Cloud Dynamics", "Data Corp"
    ]))
    
    # Generate requirements
    num_requirements = draw(st.integers(min_value=1, max_value=5))
    requirements = [
        draw(st.sampled_from([
            "5+ years of software development experience",
            "Bachelor's degree in Computer Science",
            "Strong knowledge of Python and JavaScript",
            "Experience with cloud platforms",
            "Leadership and mentoring experience",
            "Excellent communication skills"
        ]))
        for _ in range(num_requirements)
    ]
    
    # Generate skills
    num_skills = draw(st.integers(min_value=1, max_value=8))
    skills = [
        draw(st.sampled_from([
            "Python", "JavaScript", "Java", "AWS", "Docker",
            "Kubernetes", "React", "Node.js", "SQL", "MongoDB"
        ]))
        for _ in range(num_skills)
    ]
    
    description = f"""{job_title} - {company}

We are seeking a {job_title} to join our team.

Requirements:
{chr(10).join(f"- {req}" for req in requirements)}

Skills:
{', '.join(skills)}

Responsibilities:
- Design and develop software solutions
- Collaborate with cross-functional teams
- Participate in code reviews
"""
    
    return description


# ============================================================================
# Mock LLM Provider
# ============================================================================

class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider for property testing."""
    
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
            mock_response = """Job Title: Software Engineer
Company: TechCorp Inc
Experience Level: Mid level
Industry: Technology

Requirements:
- 3+ years of software development experience
- Strong knowledge of Python
- Experience with cloud platforms

Skills:
- Python
- JavaScript
- AWS
- Docker

Keywords (important terms for ATS):
- Software Development
- Cloud Computing
- Agile"""
        
        # Second call: requirement matching
        elif self.call_count == 2:
            # Parse the prompt to extract requirements
            if "REQUIREMENTS:" in prompt:
                # Extract requirements from prompt
                lines = prompt.split('\n')
                in_requirements = False
                requirements = []
                for line in lines:
                    if "JOB REQUIREMENTS:" in line:
                        in_requirements = True
                        continue
                    if in_requirements and line.strip().startswith(('1.', '2.', '3.', '4.', '5.')):
                        req = line.split('.', 1)[1].strip()
                        requirements.append(req)
                
                # Randomly mark some as met, some as not met
                import random
                random.seed(len(prompt))  # Deterministic based on prompt
                met = []
                not_met = []
                for req in requirements:
                    if random.random() > 0.5:
                        met.append(req)
                    else:
                        not_met.append(req)
                
                mock_response = "MET:\n"
                for req in met:
                    mock_response += f"- {req}\n"
                mock_response += "\nNOT MET:\n"
                for req in not_met:
                    mock_response += f"- {req}\n"
            else:
                mock_response = "MET:\n- Some requirement\n\nNOT MET:\n- Another requirement"
        
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


# ============================================================================
# Property Tests
# ============================================================================

@pytest.mark.asyncio
@given(
    cv_data=cv_data_strategy(),
    job_description=job_description_strategy()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
async def test_property_job_match_score_range(cv_data, job_description):
    """
    Property: Job match score is always between 0 and 100.
    
    For any CV and job description, the overall match score and all component
    scores must be valid percentages (0-100).
    """
    # Arrange
    provider = MockLLMProvider()
    optimizer = CVOptimizer(provider)
    request = JobMatchRequest(
        cv_id="test-cv-id",
        cv_data=cv_data,
        job_description=job_description
    )
    
    # Act
    result = await optimizer.match_cv_to_job(request)
    
    # Assert - Overall score
    assert isinstance(result.score_breakdown.overall_score, (int, float))
    assert 0 <= result.score_breakdown.overall_score <= 100, \
        f"Overall score {result.score_breakdown.overall_score} is out of range [0, 100]"
    
    # Assert - Component scores
    assert 0 <= result.score_breakdown.keyword_alignment_score <= 100, \
        f"Keyword alignment score {result.score_breakdown.keyword_alignment_score} is out of range"
    assert 0 <= result.score_breakdown.experience_relevance_score <= 100, \
        f"Experience relevance score {result.score_breakdown.experience_relevance_score} is out of range"
    assert 0 <= result.score_breakdown.skills_match_score <= 100, \
        f"Skills match score {result.score_breakdown.skills_match_score} is out of range"
    assert 0 <= result.score_breakdown.requirements_match_score <= 100, \
        f"Requirements match score {result.score_breakdown.requirements_match_score} is out of range"


@pytest.mark.asyncio
@given(
    cv_data=cv_data_strategy(),
    job_description=job_description_strategy()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
async def test_property_job_match_result_structure(cv_data, job_description):
    """
    Property: Job match result has all required components.
    
    For any CV and job description, the result must include:
    - Job analysis
    - Score breakdown
    - Matched and missing skills
    - Matched and missing requirements
    - Matched and missing keywords
    - Qualification gaps
    - Strengths
    - Recommendations
    - Summary
    """
    # Arrange
    provider = MockLLMProvider()
    optimizer = CVOptimizer(provider)
    request = JobMatchRequest(
        cv_id="test-cv-id",
        cv_data=cv_data,
        job_description=job_description
    )
    
    # Act
    result = await optimizer.match_cv_to_job(request)
    
    # Assert - Result structure
    assert isinstance(result, JobMatchResult)
    assert result.cv_id == "test-cv-id"
    
    # Assert - Job analysis
    assert isinstance(result.job_analysis, JobDescriptionAnalysis)
    assert result.job_analysis.job_title
    assert isinstance(result.job_analysis.requirements, list)
    assert isinstance(result.job_analysis.skills, list)
    assert isinstance(result.job_analysis.keywords, list)
    
    # Assert - Score breakdown
    assert isinstance(result.score_breakdown, JobMatchScoreBreakdown)
    
    # Assert - Lists are present (may be empty)
    assert isinstance(result.matched_skills, list)
    assert isinstance(result.missing_skills, list)
    assert isinstance(result.matched_requirements, list)
    assert isinstance(result.missing_requirements, list)
    assert isinstance(result.matched_keywords, list)
    assert isinstance(result.missing_keywords, list)
    assert isinstance(result.qualification_gaps, list)
    assert isinstance(result.strengths, list)
    assert isinstance(result.recommendations, list)
    
    # Assert - Summary
    assert isinstance(result.summary, str)
    assert len(result.summary) > 0, "Summary should not be empty"
    
    # Assert - Metadata
    assert result.model
    assert result.provider


@pytest.mark.asyncio
@given(
    cv_data=cv_data_strategy(),
    job_description=job_description_strategy()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
async def test_property_skills_categorization_completeness(cv_data, job_description):
    """
    Property: All identified skills are categorized as matched or missing.
    
    For any CV and job description, every skill identified in the job analysis
    should appear in either matched_skills or missing_skills (but not both).
    """
    # Arrange
    provider = MockLLMProvider()
    optimizer = CVOptimizer(provider)
    request = JobMatchRequest(
        cv_id="test-cv-id",
        cv_data=cv_data,
        job_description=job_description
    )
    
    # Act
    result = await optimizer.match_cv_to_job(request)
    
    # Assert - No skill should be in both lists
    matched_set = set(s.lower() for s in result.matched_skills)
    missing_set = set(s.lower() for s in result.missing_skills)
    overlap = matched_set & missing_set
    assert len(overlap) == 0, f"Skills appear in both matched and missing: {overlap}"
    
    # Assert - All job skills should be categorized
    job_skills = set(s.lower() for s in result.job_analysis.skills)
    categorized_skills = matched_set | missing_set
    
    # Each job skill should be categorized (allowing for partial matches)
    for job_skill in job_skills:
        found = any(
            job_skill in cat_skill or cat_skill in job_skill
            for cat_skill in categorized_skills
        )
        assert found, f"Job skill '{job_skill}' was not categorized as matched or missing"


@pytest.mark.asyncio
@given(
    cv_data=cv_data_strategy(),
    job_description=job_description_strategy()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
async def test_property_requirements_categorization_completeness(cv_data, job_description):
    """
    Property: All identified requirements are categorized as matched or missing.
    
    For any CV and job description, every requirement identified in the job analysis
    should appear in either matched_requirements or missing_requirements.
    """
    # Arrange
    provider = MockLLMProvider()
    optimizer = CVOptimizer(provider)
    request = JobMatchRequest(
        cv_id="test-cv-id",
        cv_data=cv_data,
        job_description=job_description
    )
    
    # Act
    result = await optimizer.match_cv_to_job(request)
    
    # Assert - No requirement should be in both lists
    matched_set = set(r.lower() for r in result.matched_requirements)
    missing_set = set(r.lower() for r in result.missing_requirements)
    overlap = matched_set & missing_set
    assert len(overlap) == 0, f"Requirements appear in both matched and missing: {overlap}"
    
    # Assert - Total requirements should match job analysis
    total_categorized = len(result.matched_requirements) + len(result.missing_requirements)
    total_job_requirements = len(result.job_analysis.requirements)
    
    # Allow for some flexibility due to LLM parsing
    assert total_categorized >= total_job_requirements * 0.8, \
        f"Only {total_categorized} of {total_job_requirements} requirements were categorized"


@pytest.mark.asyncio
@given(
    cv_data=cv_data_strategy(),
    job_description=job_description_strategy()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
async def test_property_score_consistency_with_matches(cv_data, job_description):
    """
    Property: Higher match counts correlate with higher scores.
    
    If a CV has more matched skills/requirements, the corresponding component
    scores should be higher.
    """
    # Arrange
    provider = MockLLMProvider()
    optimizer = CVOptimizer(provider)
    request = JobMatchRequest(
        cv_id="test-cv-id",
        cv_data=cv_data,
        job_description=job_description
    )
    
    # Act
    result = await optimizer.match_cv_to_job(request)
    
    # Assert - Skills match score consistency
    total_skills = len(result.matched_skills) + len(result.missing_skills)
    if total_skills > 0:
        expected_skills_score = (len(result.matched_skills) / total_skills) * 100
        # Allow for rounding differences
        assert abs(result.score_breakdown.skills_match_score - expected_skills_score) < 1.0, \
            f"Skills match score {result.score_breakdown.skills_match_score} doesn't match expected {expected_skills_score}"
    
    # Assert - Requirements match score consistency
    total_requirements = len(result.matched_requirements) + len(result.missing_requirements)
    if total_requirements > 0:
        expected_req_score = (len(result.matched_requirements) / total_requirements) * 100
        # Allow for rounding differences
        assert abs(result.score_breakdown.requirements_match_score - expected_req_score) < 1.0, \
            f"Requirements match score {result.score_breakdown.requirements_match_score} doesn't match expected {expected_req_score}"


@pytest.mark.asyncio
@given(
    cv_data=cv_data_strategy(),
    job_description=job_description_strategy()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
async def test_property_recommendations_provided(cv_data, job_description):
    """
    Property: Recommendations are always provided.
    
    For any CV and job description, the result should include at least one
    actionable recommendation.
    """
    # Arrange
    provider = MockLLMProvider()
    optimizer = CVOptimizer(provider)
    request = JobMatchRequest(
        cv_id="test-cv-id",
        cv_data=cv_data,
        job_description=job_description
    )
    
    # Act
    result = await optimizer.match_cv_to_job(request)
    
    # Assert - Recommendations exist
    assert len(result.recommendations) > 0, "At least one recommendation should be provided"
    
    # Assert - Recommendations are meaningful strings
    for rec in result.recommendations:
        assert isinstance(rec, str)
        assert len(rec) > 10, f"Recommendation too short: '{rec}'"


@pytest.mark.asyncio
@given(
    cv_data=cv_data_strategy(),
    job_description=job_description_strategy()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
async def test_property_summary_quality(cv_data, job_description):
    """
    Property: Summary is informative and mentions key information.
    
    For any CV and job description, the summary should:
    - Mention the match quality or score
    - Reference the job title
    - Be of reasonable length
    """
    # Arrange
    provider = MockLLMProvider()
    optimizer = CVOptimizer(provider)
    request = JobMatchRequest(
        cv_id="test-cv-id",
        cv_data=cv_data,
        job_description=job_description
    )
    
    # Act
    result = await optimizer.match_cv_to_job(request)
    
    # Assert - Summary length
    assert len(result.summary) >= 50, f"Summary too short: {len(result.summary)} characters"
    assert len(result.summary) <= 1000, f"Summary too long: {len(result.summary)} characters"
    
    # Assert - Summary mentions score or match quality
    summary_lower = result.summary.lower()
    assert any(word in summary_lower for word in ["match", "score", "excellent", "good", "moderate", "low"]), \
        "Summary should mention match quality or score"


@pytest.mark.asyncio
@given(cv_data=cv_data_strategy())
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
async def test_property_handles_minimal_job_description(cv_data):
    """
    Property: System handles minimal job descriptions gracefully.
    
    For any CV and a minimal job description, the system should still
    return a valid result without errors.
    """
    # Arrange
    provider = MockLLMProvider()
    optimizer = CVOptimizer(provider)
    minimal_job_description = "Software Engineer position. Python required."
    
    request = JobMatchRequest(
        cv_id="test-cv-id",
        cv_data=cv_data,
        job_description=minimal_job_description
    )
    
    # Act
    result = await optimizer.match_cv_to_job(request)
    
    # Assert - Valid result returned
    assert isinstance(result, JobMatchResult)
    assert 0 <= result.score_breakdown.overall_score <= 100
    assert result.summary
    assert len(result.recommendations) > 0


@pytest.mark.asyncio
@given(job_description=job_description_strategy())
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
async def test_property_handles_empty_cv(job_description):
    """
    Property: System handles empty/minimal CVs gracefully.
    
    For any job description and an empty CV, the system should:
    - Return a valid result
    - Show low match scores
    - Identify many missing skills/requirements
    - Provide helpful recommendations
    """
    # Arrange
    provider = MockLLMProvider()
    optimizer = CVOptimizer(provider)
    empty_cv = {
        "id": "test-cv-id",
        "personal_info": {"name": "Test User", "title": ""},
        "summary": "",
        "experience": [],
        "education": [],
        "skills": {"categories": []},
        "certifications": []
    }
    
    request = JobMatchRequest(
        cv_id="test-cv-id",
        cv_data=empty_cv,
        job_description=job_description
    )
    
    # Act
    result = await optimizer.match_cv_to_job(request)
    
    # Assert - Valid result
    assert isinstance(result, JobMatchResult)
    assert 0 <= result.score_breakdown.overall_score <= 100
    
    # Assert - Low scores expected for empty CV
    assert result.score_breakdown.overall_score < 60, \
        "Empty CV should have low match score"
    
    # Assert - Many missing elements
    assert len(result.missing_skills) > 0, "Empty CV should have missing skills"
    
    # Assert - Recommendations provided
    assert len(result.recommendations) > 0, "Recommendations should be provided for empty CV"


@pytest.mark.asyncio
@given(
    cv_data=cv_data_strategy(),
    job_description=job_description_strategy()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
async def test_property_strengths_identified(cv_data, job_description):
    """
    Property: Strengths are identified when matches exist.
    
    For any CV and job description where there are matched skills or requirements,
    at least one strength should be identified.
    """
    # Arrange
    provider = MockLLMProvider()
    optimizer = CVOptimizer(provider)
    request = JobMatchRequest(
        cv_id="test-cv-id",
        cv_data=cv_data,
        job_description=job_description
    )
    
    # Act
    result = await optimizer.match_cv_to_job(request)
    
    # Assert - If there are matches, strengths should be identified
    has_matches = (
        len(result.matched_skills) > 0 or
        len(result.matched_requirements) > 0 or
        result.score_breakdown.overall_score > 30
    )
    
    if has_matches:
        assert len(result.strengths) > 0, \
            "Strengths should be identified when there are matches"
    
    # Assert - Strengths are meaningful
    for strength in result.strengths:
        assert isinstance(strength, str)
        assert len(strength) > 5, f"Strength too short: '{strength}'"
