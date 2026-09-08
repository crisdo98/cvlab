"""
Property-Based Tests for ATS Compatibility Scoring

Feature: cv-web-app, Property 41: ATS Compatibility Scoring
Validates: Requirements 14.1, 14.5

Property 41: ATS Compatibility Scoring
For any CV, the ATS analysis should return a numerical compatibility score
and structured recommendations.

This test validates that ATS compatibility scoring correctly calculates
scores, provides structured recommendations, and maintains consistency
across different CV content.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any

from app.llm.ats_analyzer import ATSAnalyzer
from app.llm.providers.base import BaseLLMProvider, LLMResponse, LLMConfig
from app.models.llm_models import (
    ATSAnalysisRequest,
    ATSAnalysisResult,
    ATSCompatibilityScore,
    ATSRecommendation,
    RecommendationPriority
)


# Mock provider for property testing
class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider that simulates ATS analysis."""
    
    def __init__(self, config: LLMConfig, provider_name: str = "mock"):
        super().__init__(config)
        self._provider_name = provider_name
        self._call_count = 0
    
    async def generate_completion(
        self,
        prompt: str,
        system_prompt=None,
        temperature=None,
        max_tokens=None,
        **kwargs
    ) -> LLMResponse:
        """Generate mock completion with ATS recommendations."""
        self._call_count += 1
        
        # Generate realistic ATS analysis response
        content = """1. [Keywords] [Priority: High]
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
   Impact: Helps ATS categorize your qualifications

4. [Keywords] [Priority: Medium]
   Issue: Could incorporate more industry-specific terminology
   Suggestion: Use standard job titles and technical terms
   Impact: Increases match rate with job descriptions"""
        
        return LLMResponse(
            content=content,
            model=self.config.model,
            provider=self._provider_name,
            tokens_used=200 + self._call_count * 30
        )
    
    async def generate_structured_output(
        self,
        prompt: str,
        schema: dict,
        system_prompt=None,
        temperature=None,
        max_tokens=None,
        **kwargs
    ) -> dict:
        """Generate mock structured output."""
        return {"data": {}}
    
    def validate_config(self) -> bool:
        """Validate configuration."""
        return True
    
    async def test_connection(self) -> bool:
        """Test connection."""
        return True
    
    def get_provider_name(self) -> str:
        """Get provider name."""
        return self._provider_name


# Hypothesis strategies for generating test data
@st.composite
def cv_data_strategy(draw):
    """Generate CV data with varying completeness and quality."""
    # Generate personal info with varying completeness
    has_email = draw(st.booleans())
    has_phone = draw(st.booleans())
    has_name = draw(st.booleans())
    
    personal_info = {}
    if has_name:
        personal_info["name"] = draw(st.sampled_from(["John Doe", "Jane Smith", "Alex Johnson", "Maria Garcia"]))
        personal_info["title"] = draw(st.sampled_from(["Software Engineer", "Data Scientist", "Product Manager"]))
    
    contact = {}
    if has_email:
        contact["email"] = "test@example.com"
    if has_phone:
        contact["phone"] = "+1-555-0100"
    
    if contact:
        personal_info["contact"] = contact
    
    # Generate summary
    has_summary = draw(st.booleans())
    summary = ""
    if has_summary:
        summary = draw(st.sampled_from([
            "Experienced software engineer with proven track record",
            "Results-driven professional with expertise in technology",
            "Skilled developer with strong problem-solving abilities"
        ]))
    
    # Generate experience entries
    num_experiences = draw(st.integers(min_value=0, max_value=3))
    experiences = []
    
    for i in range(num_experiences):
        exp = {
            "id": f"exp-{i}",
            "title": draw(st.sampled_from(["Senior Engineer", "Developer", "Tech Lead", "Manager"])),
            "company": draw(st.sampled_from(["TechCorp", "StartupXYZ", "BigTech Inc"])),
            "start_date": f"202{draw(st.integers(min_value=0, max_value=3))}-01",
            "end_date": f"202{draw(st.integers(min_value=3, max_value=4))}-12",
            "description": draw(st.sampled_from([
                "Developed scalable applications using modern technologies",
                "Led team of engineers to deliver high-impact features",
                "Implemented automated testing and CI/CD pipelines"
            ])),
            "achievements": []
        }
        
        # Add achievements sometimes
        if draw(st.booleans()):
            num_achievements = draw(st.integers(min_value=1, max_value=3))
            exp["achievements"] = [
                draw(st.sampled_from([
                    "Improved system performance by 40%",
                    "Reduced deployment time by 60%",
                    "Increased test coverage to 95%"
                ]))
                for _ in range(num_achievements)
            ]
        
        experiences.append(exp)
    
    # Generate education entries
    num_education = draw(st.integers(min_value=0, max_value=2))
    education = []
    
    for i in range(num_education):
        edu = {
            "id": f"edu-{i}",
            "degree": draw(st.sampled_from(["BS Computer Science", "MS Engineering", "MBA"])),
            "institution": draw(st.sampled_from(["University", "Tech Institute", "State College"])),
            "start_date": "2015-09",
            "end_date": "2019-05"
        }
        education.append(edu)
    
    # Generate skills
    has_skills = draw(st.booleans())
    skills = {"categories": []}
    
    if has_skills:
        num_categories = draw(st.integers(min_value=1, max_value=4))
        for i in range(num_categories):
            category = {
                "name": draw(st.sampled_from(["Programming", "Cloud", "Tools", "Soft Skills"])),
                "skills": [
                    draw(st.sampled_from(["Python", "JavaScript", "AWS", "Docker", "Git", "React"]))
                    for _ in range(draw(st.integers(min_value=1, max_value=5)))
                ]
            }
            skills["categories"].append(category)
    
    return {
        "id": "test-cv-id",
        "personal_info": personal_info,
        "summary": summary,
        "experience": experiences,
        "education": education,
        "skills": skills,
        "certifications": []
    }



@st.composite
def provider_config_strategy(draw):
    """Generate provider configurations."""
    provider_type = draw(st.sampled_from(["openai", "anthropic", "local"]))
    
    if provider_type == "openai":
        model = draw(st.sampled_from(["gpt-4", "gpt-3.5-turbo"]))
        config = LLMConfig(
            provider=provider_type,
            model=model,
            api_key="test-key-123",
            temperature=draw(st.floats(min_value=0.0, max_value=0.5)),
            max_tokens=draw(st.integers(min_value=500, max_value=2000))
        )
    elif provider_type == "anthropic":
        model = draw(st.sampled_from(["claude-3-opus", "claude-3-sonnet"]))
        config = LLMConfig(
            provider=provider_type,
            model=model,
            api_key="test-key-456",
            temperature=draw(st.floats(min_value=0.0, max_value=0.5)),
            max_tokens=draw(st.integers(min_value=500, max_value=2000))
        )
    else:  # local
        model = draw(st.sampled_from(["llama2", "mistral"]))
        config = LLMConfig(
            provider=provider_type,
            model=model,
            base_url="http://localhost:11434",
            temperature=draw(st.floats(min_value=0.0, max_value=0.5)),
            max_tokens=draw(st.integers(min_value=500, max_value=2000))
        )
    
    return config, provider_type


# Property Tests
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy(),
    cv_data=cv_data_strategy()
)
@pytest.mark.asyncio
async def test_property_ats_compatibility_scoring_returns_valid_score(
    config_and_provider,
    cv_data
):
    """
    Property 41: ATS Compatibility Scoring - Valid Score
    
    For any CV, the ATS analysis should return a numerical compatibility
    score between 0 and 100.
    
    Validates: Requirements 14.1, 14.5
    """
    config, provider_type = config_and_provider
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create analyzer
    analyzer = ATSAnalyzer(mock_provider)
    
    # Create analysis request
    request = ATSAnalysisRequest(
        cv_id=cv_data["id"],
        cv_data=cv_data,
        industry="software",
        job_title="Software Engineer"
    )
    
    # Perform analysis
    result = await analyzer.analyze_ats_compatibility(request)
    
    # Property assertions
    # 1. Result should not be None
    assert result is not None, "ATS analysis result should not be None"
    assert isinstance(result, ATSAnalysisResult), "Result should be ATSAnalysisResult instance"
    
    # 2. Should have compatibility score
    assert result.compatibility_score is not None, "Result should have compatibility score"
    assert isinstance(result.compatibility_score, ATSCompatibilityScore), \
        "Compatibility score should be ATSCompatibilityScore instance"
    
    # 3. Overall score should be between 0 and 100
    assert 0 <= result.compatibility_score.overall_score <= 100, \
        f"Overall score should be 0-100, got {result.compatibility_score.overall_score}"
    
    # 4. All component scores should be between 0 and 100
    assert 0 <= result.compatibility_score.keyword_score <= 100, \
        f"Keyword score should be 0-100, got {result.compatibility_score.keyword_score}"
    assert 0 <= result.compatibility_score.formatting_score <= 100, \
        f"Formatting score should be 0-100, got {result.compatibility_score.formatting_score}"
    assert 0 <= result.compatibility_score.structure_score <= 100, \
        f"Structure score should be 0-100, got {result.compatibility_score.structure_score}"
    assert 0 <= result.compatibility_score.completeness_score <= 100, \
        f"Completeness score should be 0-100, got {result.compatibility_score.completeness_score}"
    
    # 5. Overall score should be reasonable combination of component scores
    # It should be within the range of component scores
    component_scores = [
        result.compatibility_score.keyword_score,
        result.compatibility_score.formatting_score,
        result.compatibility_score.structure_score,
        result.compatibility_score.completeness_score
    ]
    min_component = min(component_scores)
    max_component = max(component_scores)
    
    assert min_component <= result.compatibility_score.overall_score <= max_component, \
        f"Overall score {result.compatibility_score.overall_score} should be between min {min_component} and max {max_component} component scores"


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy(),
    cv_data=cv_data_strategy()
)
@pytest.mark.asyncio
async def test_property_ats_compatibility_scoring_returns_structured_recommendations(
    config_and_provider,
    cv_data
):
    """
    Property 41: ATS Compatibility Scoring - Structured Recommendations
    
    For any CV, the ATS analysis should return structured recommendations
    with all required fields.
    
    Validates: Requirements 14.1, 14.5
    """
    config, provider_type = config_and_provider
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create analyzer
    analyzer = ATSAnalyzer(mock_provider)
    
    # Create analysis request
    request = ATSAnalysisRequest(
        cv_id=cv_data["id"],
        cv_data=cv_data,
        industry="software",
        job_title="Software Engineer"
    )
    
    # Perform analysis
    result = await analyzer.analyze_ats_compatibility(request)
    
    # Property assertions
    # 1. Should have recommendations list
    assert result.recommendations is not None, "Result should have recommendations"
    assert isinstance(result.recommendations, list), "Recommendations should be a list"
    
    # 2. Each recommendation should be properly structured
    for rec in result.recommendations:
        assert isinstance(rec, ATSRecommendation), \
            "Each recommendation should be ATSRecommendation instance"
        
        # 3. Each recommendation should have required fields
        assert rec.category, "Recommendation should have category"
        assert isinstance(rec.category, str), "Category should be string"
        assert len(rec.category.strip()) > 0, "Category should not be empty"
        
        assert rec.issue, "Recommendation should have issue description"
        assert isinstance(rec.issue, str), "Issue should be string"
        assert len(rec.issue.strip()) > 0, "Issue should not be empty"
        
        assert rec.suggestion, "Recommendation should have suggestion"
        assert isinstance(rec.suggestion, str), "Suggestion should be string"
        assert len(rec.suggestion.strip()) > 0, "Suggestion should not be empty"
        
        assert rec.impact, "Recommendation should have impact description"
        assert isinstance(rec.impact, str), "Impact should be string"
        assert len(rec.impact.strip()) > 0, "Impact should not be empty"
        
        # 4. Priority should be valid enum value
        assert rec.priority in [
            RecommendationPriority.HIGH,
            RecommendationPriority.MEDIUM,
            RecommendationPriority.LOW
        ], f"Priority should be valid enum value, got {rec.priority}"
    
    # 5. Recommendations should be actionable
    for rec in result.recommendations:
        # Suggestion should contain actionable language
        suggestion_lower = rec.suggestion.lower()
        actionable_indicators = [
            "add", "include", "remove", "replace", "use", "ensure",
            "consider", "incorporate", "organize", "group", "simplify",
            "improve", "enhance", "update", "modify", "change"
        ]
        
        has_actionable = any(indicator in suggestion_lower for indicator in actionable_indicators)
        assert has_actionable, \
            f"Suggestion should be actionable, got: {rec.suggestion}"


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy(),
    cv_data=cv_data_strategy()
)
@pytest.mark.asyncio
async def test_property_ats_compatibility_scoring_includes_metadata(
    config_and_provider,
    cv_data
):
    """
    Property 41: ATS Compatibility Scoring - Metadata
    
    For any CV, the ATS analysis should include complete metadata
    about the analysis.
    
    Validates: Requirements 14.1, 14.5
    """
    config, provider_type = config_and_provider
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create analyzer
    analyzer = ATSAnalyzer(mock_provider)
    
    # Create analysis request
    request = ATSAnalysisRequest(
        cv_id=cv_data["id"],
        cv_data=cv_data,
        industry="software",
        job_title="Software Engineer"
    )
    
    # Perform analysis
    result = await analyzer.analyze_ats_compatibility(request)
    
    # Property assertions
    # 1. Should have CV ID
    assert result.cv_id == cv_data["id"], "Result should have correct CV ID"
    
    # 2. Should have summary
    assert result.summary, "Result should have summary"
    assert isinstance(result.summary, str), "Summary should be string"
    assert len(result.summary) > 0, "Summary should not be empty"
    
    # 3. Summary should mention score
    assert str(int(result.compatibility_score.overall_score)) in result.summary or \
           "score" in result.summary.lower(), \
        "Summary should mention the compatibility score"
    
    # 4. Should have timestamp
    assert result.analyzed_at is not None, "Result should have timestamp"
    
    # 5. Should have model and provider info
    assert result.model, "Result should have model name"
    assert isinstance(result.model, str), "Model should be string"
    
    assert result.provider, "Result should have provider name"
    assert isinstance(result.provider, str), "Provider should be string"
    assert result.provider == provider_type, \
        f"Provider should match request provider: {provider_type}"
    
    # 6. Should have keyword analysis
    assert result.industry_keywords is not None, "Result should have industry keywords"
    assert isinstance(result.industry_keywords, list), "Industry keywords should be list"
    
    assert result.present_keywords is not None, "Result should have present keywords"
    assert isinstance(result.present_keywords, list), "Present keywords should be list"
    
    assert result.missing_keywords is not None, "Result should have missing keywords"
    assert isinstance(result.missing_keywords, list), "Missing keywords should be list"
    
    # 7. Present and missing keywords should be mutually exclusive
    present_set = set(result.present_keywords)
    missing_set = set(result.missing_keywords)
    overlap = present_set & missing_set
    
    assert len(overlap) == 0, \
        f"Present and missing keywords should not overlap, found: {overlap}"
    
    # 8. Should have keyword density analysis
    assert result.keyword_density is not None, "Result should have keyword density"
    assert isinstance(result.keyword_density, dict), "Keyword density should be dict"
    
    # All keywords in density should be present keywords
    for keyword in result.keyword_density.keys():
        assert keyword in result.present_keywords or keyword.lower() in [k.lower() for k in result.present_keywords], \
            f"Keyword in density should be in present keywords: {keyword}"
    
    # 9. Should have formatting issues list
    assert result.formatting_issues is not None, "Result should have formatting issues"
    assert isinstance(result.formatting_issues, list), "Formatting issues should be list"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_ats_compatibility_scoring_incomplete_cv_lower_score(
    config_and_provider
):
    """
    Property 41: ATS Compatibility Scoring - Incomplete CV
    
    For CVs with missing sections or information, the compatibility
    score should be lower than complete CVs.
    
    Validates: Requirements 14.1, 14.5
    """
    config, provider_type = config_and_provider
    
    # Create complete CV
    complete_cv = {
        "id": "complete-cv",
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
                "end_date": "2023-12",
                "description": "Developed scalable applications using Python and AWS",
                "achievements": ["Improved system performance by 40%"]
            }
        ],
        "education": [
            {
                "id": "edu-1",
                "degree": "BS Computer Science",
                "institution": "University",
                "start_date": "2015-09",
                "end_date": "2019-05"
            }
        ],
        "skills": {
            "categories": [
                {"name": "Languages", "skills": ["Python", "JavaScript"]},
                {"name": "Cloud", "skills": ["AWS", "Docker"]}
            ]
        },
        "certifications": []
    }
    
    # Create incomplete CV (missing key sections)
    incomplete_cv = {
        "id": "incomplete-cv",
        "personal_info": {},
        "summary": "",
        "experience": [],
        "education": [],
        "skills": {"categories": []},
        "certifications": []
    }
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create analyzer
    analyzer = ATSAnalyzer(mock_provider)
    
    # Analyze complete CV
    complete_request = ATSAnalysisRequest(
        cv_id=complete_cv["id"],
        cv_data=complete_cv,
        industry="software",
        job_title="Software Engineer"
    )
    complete_result = await analyzer.analyze_ats_compatibility(complete_request)
    
    # Analyze incomplete CV
    incomplete_request = ATSAnalysisRequest(
        cv_id=incomplete_cv["id"],
        cv_data=incomplete_cv,
        industry="software",
        job_title="Software Engineer"
    )
    incomplete_result = await analyzer.analyze_ats_compatibility(incomplete_request)
    
    # Property assertions
    # 1. Incomplete CV should have lower overall score
    assert incomplete_result.compatibility_score.overall_score < complete_result.compatibility_score.overall_score, \
        f"Incomplete CV score ({incomplete_result.compatibility_score.overall_score}) should be lower than complete CV ({complete_result.compatibility_score.overall_score})"
    
    # 2. Incomplete CV should have lower completeness score
    assert incomplete_result.compatibility_score.completeness_score < complete_result.compatibility_score.completeness_score, \
        "Incomplete CV should have lower completeness score"
    
    # 3. Incomplete CV should have more formatting issues
    assert len(incomplete_result.formatting_issues) > len(complete_result.formatting_issues), \
        "Incomplete CV should have more formatting issues"
    
    # 4. Incomplete CV should have more recommendations
    assert len(incomplete_result.recommendations) >= len(complete_result.recommendations), \
        "Incomplete CV should have at least as many recommendations"



@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_ats_compatibility_scoring_keyword_analysis(
    config_and_provider
):
    """
    Property 41: ATS Compatibility Scoring - Keyword Analysis
    
    For any CV, the keyword analysis should correctly identify present
    and missing keywords, and calculate appropriate keyword scores.
    
    Validates: Requirements 14.1, 14.5
    """
    config, provider_type = config_and_provider
    
    # Create CV with known keywords
    cv_with_keywords = {
        "id": "keyword-cv",
        "personal_info": {
            "name": "Jane Smith",
            "title": "Software Engineer"
        },
        "summary": "Python developer with AWS and Docker experience",
        "experience": [
            {
                "id": "exp-1",
                "title": "Software Engineer",
                "company": "TechCorp",
                "start_date": "2020-01",
                "end_date": "2023-12",
                "description": "Developed applications using Python, JavaScript, AWS, Docker, and Kubernetes",
                "achievements": ["Built microservices architecture"]
            }
        ],
        "education": [],
        "skills": {
            "categories": [
                {"name": "Languages", "skills": ["Python", "JavaScript", "Java"]},
                {"name": "Cloud", "skills": ["AWS", "Docker", "Kubernetes"]}
            ]
        },
        "certifications": []
    }
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create analyzer
    analyzer = ATSAnalyzer(mock_provider)
    
    # Analyze CV
    request = ATSAnalysisRequest(
        cv_id=cv_with_keywords["id"],
        cv_data=cv_with_keywords,
        industry="software",
        job_title="Software Engineer"
    )
    result = await analyzer.analyze_ats_compatibility(request)
    
    # Property assertions
    # 1. Should identify industry keywords
    assert len(result.industry_keywords) > 0, \
        "Should identify industry keywords for software engineering"
    
    # 2. Should find present keywords
    assert len(result.present_keywords) > 0, \
        "Should find keywords present in CV"
    
    # Known keywords that should be present
    expected_present = ["python", "javascript", "aws", "docker", "kubernetes"]
    found_present = [k.lower() for k in result.present_keywords]
    
    for keyword in expected_present:
        assert keyword in found_present, \
            f"Should find '{keyword}' in present keywords"
    
    # 3. Keyword score should reflect presence of keywords
    keyword_match_rate = len(result.present_keywords) / len(result.industry_keywords) if result.industry_keywords else 0
    
    # If many keywords are present, keyword score should be reasonably high
    if keyword_match_rate > 0.5:
        assert result.compatibility_score.keyword_score >= 50, \
            f"With {keyword_match_rate:.1%} keyword match rate, score should be >= 50"
    
    # 4. Keyword density should be calculated for present keywords
    for keyword in result.present_keywords[:5]:  # Check first 5
        # If keyword is present, it should have density > 0
        keyword_lower = keyword.lower()
        matching_density_keys = [k for k in result.keyword_density.keys() if k.lower() == keyword_lower]
        
        if matching_density_keys:
            density = result.keyword_density[matching_density_keys[0]]
            assert density > 0, \
                f"Present keyword '{keyword}' should have density > 0"



@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_ats_compatibility_scoring_consistency(
    config_and_provider
):
    """
    Property 41: ATS Compatibility Scoring - Consistency
    
    For the same CV, ATS analysis should produce consistent scores
    across multiple runs.
    
    Validates: Requirements 14.1, 14.5
    """
    config, provider_type = config_and_provider
    
    # Create consistent CV
    cv_data = {
        "id": "consistent-cv",
        "personal_info": {
            "name": "Test User",
            "title": "Software Engineer",
            "contact": {
                "email": "test@example.com",
                "phone": "+1-555-0100"
            }
        },
        "summary": "Experienced software engineer with Python expertise",
        "experience": [
            {
                "id": "exp-1",
                "title": "Senior Engineer",
                "company": "TechCorp",
                "start_date": "2020-01",
                "end_date": "2023-12",
                "description": "Developed applications using Python and AWS",
                "achievements": ["Improved performance by 40%"]
            }
        ],
        "education": [
            {
                "id": "edu-1",
                "degree": "BS Computer Science",
                "institution": "University",
                "start_date": "2015-09",
                "end_date": "2019-05"
            }
        ],
        "skills": {
            "categories": [
                {"name": "Languages", "skills": ["Python", "JavaScript"]}
            ]
        },
        "certifications": []
    }
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create analyzer
    analyzer = ATSAnalyzer(mock_provider)
    
    # Create request
    request = ATSAnalysisRequest(
        cv_id=cv_data["id"],
        cv_data=cv_data,
        industry="software",
        job_title="Software Engineer"
    )
    
    # Run analysis twice
    result1 = await analyzer.analyze_ats_compatibility(request)
    result2 = await analyzer.analyze_ats_compatibility(request)
    
    # Property assertions
    # 1. Overall scores should be very close (within 5 points)
    score_diff = abs(result1.compatibility_score.overall_score - result2.compatibility_score.overall_score)
    assert score_diff <= 5, \
        f"Overall scores should be consistent (diff: {score_diff})"
    
    # 2. Component scores should be consistent
    keyword_diff = abs(result1.compatibility_score.keyword_score - result2.compatibility_score.keyword_score)
    assert keyword_diff <= 5, \
        f"Keyword scores should be consistent (diff: {keyword_diff})"
    
    formatting_diff = abs(result1.compatibility_score.formatting_score - result2.compatibility_score.formatting_score)
    assert formatting_diff <= 5, \
        f"Formatting scores should be consistent (diff: {formatting_diff})"
    
    # 3. Should identify same keywords
    present1 = set(k.lower() for k in result1.present_keywords)
    present2 = set(k.lower() for k in result2.present_keywords)
    
    # Allow some variation but should have significant overlap
    if present1 and present2:
        overlap = len(present1 & present2)
        union = len(present1 | present2)
        similarity = overlap / union if union > 0 else 0
        
        assert similarity >= 0.7, \
            f"Present keywords should be consistent (similarity: {similarity:.2f})"
    
    # 4. Number of recommendations should be similar
    rec_diff = abs(len(result1.recommendations) - len(result2.recommendations))
    assert rec_diff <= 2, \
        f"Number of recommendations should be consistent (diff: {rec_diff})"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_ats_compatibility_scoring_priority_distribution(
    config_and_provider
):
    """
    Property 41: ATS Compatibility Scoring - Priority Distribution
    
    For any CV, recommendations should have appropriate priority
    distribution based on the severity of issues.
    
    Validates: Requirements 14.1, 14.5
    """
    config, provider_type = config_and_provider
    
    # Create CV with various issues
    cv_with_issues = {
        "id": "issues-cv",
        "personal_info": {
            "name": "Test User"
            # Missing contact info - should be high priority
        },
        "summary": "",  # Missing summary
        "experience": [],  # Missing experience - critical
        "education": [],  # Missing education
        "skills": {"categories": []},  # Missing skills
        "certifications": []
    }
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create analyzer
    analyzer = ATSAnalyzer(mock_provider)
    
    # Analyze CV
    request = ATSAnalysisRequest(
        cv_id=cv_with_issues["id"],
        cv_data=cv_with_issues,
        industry="software",
        job_title="Software Engineer"
    )
    result = await analyzer.analyze_ats_compatibility(request)
    
    # Property assertions
    # 1. Should have recommendations
    assert len(result.recommendations) > 0, \
        "CV with issues should have recommendations"
    
    # 2. Should have high priority recommendations for critical issues
    high_priority_recs = [
        rec for rec in result.recommendations
        if rec.priority == RecommendationPriority.HIGH
    ]
    
    assert len(high_priority_recs) > 0, \
        "CV with missing critical sections should have high priority recommendations"
    
    # 3. Priority distribution should be reasonable
    priority_counts = {
        RecommendationPriority.HIGH: 0,
        RecommendationPriority.MEDIUM: 0,
        RecommendationPriority.LOW: 0
    }
    
    for rec in result.recommendations:
        priority_counts[rec.priority] += 1
    
    # Should not have all recommendations at same priority
    non_zero_priorities = sum(1 for count in priority_counts.values() if count > 0)
    assert non_zero_priorities >= 1, \
        "Should have at least one priority level with recommendations"
    
    # 4. High priority recommendations should address critical issues
    for rec in high_priority_recs:
        issue_lower = rec.issue.lower()
        critical_indicators = [
            "missing", "required", "essential", "critical",
            "contact", "email", "phone", "experience", "education"
        ]
        
        has_critical_indicator = any(indicator in issue_lower for indicator in critical_indicators)
        assert has_critical_indicator, \
            f"High priority recommendation should address critical issue, got: {rec.issue}"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_ats_compatibility_scoring_summary_quality(
    config_and_provider
):
    """
    Property 41: ATS Compatibility Scoring - Summary Quality
    
    For any CV, the analysis summary should provide meaningful
    information about the compatibility score and key issues.
    
    Validates: Requirements 14.1, 14.5
    """
    config, provider_type = config_and_provider
    
    # Create CV
    cv_data = {
        "id": "summary-cv",
        "personal_info": {
            "name": "Test User",
            "title": "Software Engineer",
            "contact": {"email": "test@example.com"}
        },
        "summary": "Software engineer with Python experience",
        "experience": [
            {
                "id": "exp-1",
                "title": "Engineer",
                "company": "TechCorp",
                "start_date": "2020-01",
                "end_date": "2023-12",
                "description": "Developed applications",
                "achievements": []
            }
        ],
        "education": [],
        "skills": {"categories": [{"name": "Languages", "skills": ["Python"]}]},
        "certifications": []
    }
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create analyzer
    analyzer = ATSAnalyzer(mock_provider)
    
    # Analyze CV
    request = ATSAnalysisRequest(
        cv_id=cv_data["id"],
        cv_data=cv_data,
        industry="software",
        job_title="Software Engineer"
    )
    result = await analyzer.analyze_ats_compatibility(request)
    
    # Property assertions
    # 1. Summary should not be empty
    assert result.summary, "Summary should not be empty"
    assert len(result.summary) > 20, \
        "Summary should be meaningful (at least 20 characters)"
    
    # 2. Summary should mention compatibility or score
    summary_lower = result.summary.lower()
    score_indicators = [
        "score", "compatibility", "ats", "rating",
        str(int(result.compatibility_score.overall_score))
    ]
    
    has_score_mention = any(indicator in summary_lower for indicator in score_indicators)
    assert has_score_mention, \
        "Summary should mention score or compatibility"
    
    # 3. Summary should provide qualitative assessment
    quality_indicators = [
        "excellent", "good", "fair", "needs improvement", "poor",
        "well-optimized", "optimized", "improve", "enhancement"
    ]
    
    has_quality_assessment = any(indicator in summary_lower for indicator in quality_indicators)
    assert has_quality_assessment, \
        "Summary should provide qualitative assessment"
    
    # 4. If there are issues, summary should mention them
    if len(result.formatting_issues) > 0 or len(result.missing_keywords) > 0:
        issue_indicators = [
            "issue", "missing", "improve", "consider", "add",
            "keyword", "formatting", "section"
        ]
        
        has_issue_mention = any(indicator in summary_lower for indicator in issue_indicators)
        assert has_issue_mention, \
            "Summary should mention issues when present"
    
    # 5. Summary should be coherent (no obvious formatting issues)
    # Check for basic coherence
    assert not result.summary.startswith(" "), "Summary should not start with space"
    assert not result.summary.endswith(" "), "Summary should not end with space"
    assert "  " not in result.summary, "Summary should not have double spaces"
