"""
Property-Based Tests for Keyword Stuffing Detection

Feature: cv-web-app, Property 43: Keyword Stuffing Detection
Validates: Requirements 14.3

Property 43: Keyword Stuffing Detection
For any CV with excessive keyword repetition, the service should detect
the keyword stuffing and recommend natural integration.

This test validates that keyword stuffing detection correctly identifies
CVs with excessive keyword usage and provides appropriate recommendations
for natural keyword integration.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck, assume
from typing import List, Dict, Any

from app.llm.ats_analyzer import ATSAnalyzer
from app.llm.providers.base import BaseLLMProvider, LLMResponse, LLMConfig
from app.models.llm_models import (
    ATSAnalysisRequest,
    ATSAnalysisResult,
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
   Suggestion: Add relevant technical keywords
   Impact: Improves ATS keyword matching and search visibility

2. [Formatting] [Priority: Medium]
   Issue: Could improve section organization
   Suggestion: Group related information together
   Impact: Helps ATS categorize your qualifications"""
        
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
def keyword_stuffed_cv_strategy(draw):
    """Generate CV data with keyword stuffing."""
    # Choose a keyword to stuff
    stuffed_keyword = draw(st.sampled_from([
        "Python", "JavaScript", "AWS", "Docker", "Kubernetes",
        "React", "Node.js", "SQL", "API", "Agile"
    ]))
    
    # Generate high repetition count (above stuffing threshold)
    # Threshold is 3% density, so we need enough repetitions
    # For a CV with ~200 words, 3% = 6 occurrences
    # We'll generate 10-30 repetitions to ensure detection
    repetition_count = draw(st.integers(min_value=10, max_value=30))
    
    # Create stuffed text by repeating keyword
    stuffed_text = f"{stuffed_keyword} " * repetition_count
    
    # Add some filler text to make it more realistic
    filler_words = [
        "experience", "developed", "implemented", "managed", "led",
        "created", "designed", "built", "optimized", "improved",
        "team", "project", "system", "application", "solution"
    ]
    
    filler_count = draw(st.integers(min_value=20, max_value=50))
    filler_text = " ".join([
        draw(st.sampled_from(filler_words))
        for _ in range(filler_count)
    ])
    
    # Combine stuffed and filler text
    description = f"{stuffed_text} {filler_text}"
    
    # Create CV with stuffed content
    cv_data = {
        "id": "stuffed-cv",
        "personal_info": {
            "name": "Test User",
            "title": "Software Engineer",
            "contact": {
                "email": "test@example.com",
                "phone": "+1-555-0100"
            }
        },
        "summary": stuffed_text[:100],  # Stuff in summary too
        "experience": [
            {
                "id": "exp-1",
                "title": "Senior Engineer",
                "company": "TechCorp",
                "start_date": "2020-01",
                "end_date": "2023-12",
                "description": description,
                "achievements": [stuffed_text[:50]]
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
                {
                    "name": "Languages",
                    "skills": [stuffed_keyword] * 5  # Repeat in skills too
                }
            ]
        },
        "certifications": []
    }
    
    return cv_data, stuffed_keyword.lower()


@st.composite
def clean_cv_strategy(draw):
    """Generate CV data without keyword stuffing."""
    # Create CV with reasonable keyword usage
    keywords = ["Python", "JavaScript", "AWS", "Docker"]
    
    # Use each keyword only 1-2 times
    description_parts = []
    for keyword in keywords:
        usage_count = draw(st.integers(min_value=1, max_value=2))
        for _ in range(usage_count):
            description_parts.append(keyword)
    
    # Add substantial filler text to keep density low
    # Need at least 100 words to keep density below 3% with 4-8 keyword occurrences
    # 8 keywords / 100 words = 8% density, so we need more filler
    filler_words = [
        "experience with", "developed", "implemented", "using",
        "managed", "led team", "created", "designed", "built",
        "collaborated on", "delivered", "optimized", "enhanced",
        "maintained", "architected", "deployed", "integrated"
    ]
    
    # Add 80-100 filler words to ensure low density
    filler_count = draw(st.integers(min_value=80, max_value=100))
    for _ in range(filler_count):
        description_parts.append(draw(st.sampled_from(filler_words)))
    
    description = " ".join(description_parts)
    
    cv_data = {
        "id": "clean-cv",
        "personal_info": {
            "name": "Test User",
            "title": "Software Engineer",
            "contact": {
                "email": "test@example.com",
                "phone": "+1-555-0100"
            }
        },
        "summary": "Experienced software engineer with diverse technical skills",
        "experience": [
            {
                "id": "exp-1",
                "title": "Senior Engineer",
                "company": "TechCorp",
                "start_date": "2020-01",
                "end_date": "2023-12",
                "description": description,
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
                {
                    "name": "Languages",
                    "skills": keywords
                }
            ]
        },
        "certifications": []
    }
    
    return cv_data


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
            temperature=0.3,
            max_tokens=2000
        )
    elif provider_type == "anthropic":
        model = draw(st.sampled_from(["claude-3-opus", "claude-3-sonnet"]))
        config = LLMConfig(
            provider=provider_type,
            model=model,
            api_key="test-key-456",
            temperature=0.3,
            max_tokens=2000
        )
    else:  # local
        model = draw(st.sampled_from(["llama2", "mistral"]))
        config = LLMConfig(
            provider=provider_type,
            model=model,
            base_url="http://localhost:11434",
            temperature=0.3,
            max_tokens=2000
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
    cv_and_keyword=keyword_stuffed_cv_strategy()
)
@pytest.mark.asyncio
async def test_property_keyword_stuffing_detection_identifies_stuffing(
    config_and_provider,
    cv_and_keyword
):
    """
    Property 43: Keyword Stuffing Detection - Identifies Stuffing
    
    For any CV with excessive keyword repetition (density > 3%),
    the service should detect keyword stuffing.
    
    Validates: Requirements 14.3
    """
    config, provider_type = config_and_provider
    cv_data, stuffed_keyword = cv_and_keyword
    
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
    # 1. Should calculate keyword density
    assert result.keyword_density is not None, \
        "Result should include keyword density analysis"
    assert isinstance(result.keyword_density, dict), \
        "Keyword density should be a dictionary"
    
    # 2. Stuffed keyword should have high density
    # Find the stuffed keyword in density (case-insensitive)
    stuffed_keyword_density = None
    for keyword, density in result.keyword_density.items():
        if keyword.lower() == stuffed_keyword:
            stuffed_keyword_density = density
            break
    
    # If keyword is in industry keywords, it should be in density
    if stuffed_keyword in [k.lower() for k in result.industry_keywords]:
        assert stuffed_keyword_density is not None, \
            f"Stuffed keyword '{stuffed_keyword}' should be in density analysis"
        
        # Density should be above threshold (3%)
        assert stuffed_keyword_density > 3.0, \
            f"Stuffed keyword density should be > 3%, got {stuffed_keyword_density}%"
    
    # 3. Should have keyword stuffing recommendations
    stuffing_recommendations = [
        rec for rec in result.recommendations
        if "keyword" in rec.category.lower() and "stuff" in rec.category.lower()
    ]
    
    # Should detect stuffing if keyword is in industry keywords
    if stuffed_keyword in [k.lower() for k in result.industry_keywords]:
        assert len(stuffing_recommendations) > 0, \
            "Should detect keyword stuffing and provide recommendations"
        
        # 4. Stuffing recommendations should mention the stuffed keyword
        found_keyword_mention = False
        for rec in stuffing_recommendations:
            if stuffed_keyword in rec.issue.lower():
                found_keyword_mention = True
                break
        
        assert found_keyword_mention, \
            f"Keyword stuffing recommendation should mention '{stuffed_keyword}'"


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy(),
    cv_and_keyword=keyword_stuffed_cv_strategy()
)
@pytest.mark.asyncio
async def test_property_keyword_stuffing_detection_provides_natural_integration_suggestions(
    config_and_provider,
    cv_and_keyword
):
    """
    Property 43: Keyword Stuffing Detection - Natural Integration
    
    For any CV with keyword stuffing, the service should recommend
    natural integration of keywords.
    
    Validates: Requirements 14.3
    """
    config, provider_type = config_and_provider
    cv_data, stuffed_keyword = cv_and_keyword
    
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
    # 1. Should have recommendations
    assert len(result.recommendations) > 0, \
        "Result should include recommendations"
    
    # 2. Find keyword stuffing recommendations
    stuffing_recommendations = [
        rec for rec in result.recommendations
        if "keyword" in rec.category.lower() and "stuff" in rec.category.lower()
    ]
    
    # If stuffing detected, check recommendations
    if len(stuffing_recommendations) > 0:
        for rec in stuffing_recommendations:
            # 3. Should have proper structure
            assert rec.issue, "Recommendation should have issue description"
            assert rec.suggestion, "Recommendation should have suggestion"
            assert rec.impact, "Recommendation should have impact description"
            
            # 4. Suggestion should mention natural integration
            suggestion_lower = rec.suggestion.lower()
            natural_indicators = [
                "natural", "reduce", "variation", "synonym",
                "alternative", "rephrase", "integrate", "incorporate"
            ]
            
            has_natural_suggestion = any(
                indicator in suggestion_lower
                for indicator in natural_indicators
            )
            
            assert has_natural_suggestion, \
                f"Suggestion should recommend natural integration, got: {rec.suggestion}"
            
            # 5. Should be high priority
            assert rec.priority == RecommendationPriority.HIGH, \
                "Keyword stuffing should be high priority issue"
            
            # 6. Impact should mention ATS or spam filters
            impact_lower = rec.impact.lower()
            impact_indicators = ["ats", "spam", "filter", "ranking", "score"]
            
            has_impact_mention = any(
                indicator in impact_lower
                for indicator in impact_indicators
            )
            
            assert has_impact_mention, \
                f"Impact should mention ATS implications, got: {rec.impact}"


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy(),
    clean_cv=clean_cv_strategy()
)
@pytest.mark.asyncio
async def test_property_keyword_stuffing_detection_no_false_positives(
    config_and_provider,
    clean_cv
):
    """
    Property 43: Keyword Stuffing Detection - No False Positives
    
    For any CV with reasonable keyword usage (density <= 3%),
    the service should not detect keyword stuffing.
    
    Validates: Requirements 14.3
    """
    config, provider_type = config_and_provider
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create analyzer
    analyzer = ATSAnalyzer(mock_provider)
    
    # Create analysis request
    request = ATSAnalysisRequest(
        cv_id=clean_cv["id"],
        cv_data=clean_cv,
        industry="software",
        job_title="Software Engineer"
    )
    
    # Perform analysis
    result = await analyzer.analyze_ats_compatibility(request)
    
    # Property assertions
    # 1. Should calculate keyword density
    assert result.keyword_density is not None, \
        "Result should include keyword density analysis"
    
    # 2. All keyword densities should be reasonable (< 3%)
    for keyword, density in result.keyword_density.items():
        assert density <= 3.5, \
            f"Clean CV should not have high keyword density, got {density}% for '{keyword}'"
    
    # 3. Should not have keyword stuffing recommendations
    stuffing_recommendations = [
        rec for rec in result.recommendations
        if "keyword" in rec.category.lower() and "stuff" in rec.category.lower()
    ]
    
    assert len(stuffing_recommendations) == 0, \
        f"Clean CV should not trigger keyword stuffing detection, got {len(stuffing_recommendations)} recommendations"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_keyword_stuffing_detection_threshold_accuracy(
    config_and_provider
):
    """
    Property 43: Keyword Stuffing Detection - Threshold Accuracy
    
    The keyword stuffing detection should use a consistent threshold
    (3% density) to identify excessive keyword usage.
    
    Validates: Requirements 14.3
    """
    config, provider_type = config_and_provider
    
    # Create CV with keyword at exactly threshold (3%)
    # For 100 words, 3% = 3 occurrences
    keyword = "Python"
    
    # Create text with exactly 100 words, 3 of which are the keyword
    filler_words = ["experience", "developed", "implemented"] * 32  # 96 words
    text_words = [keyword] * 3 + filler_words[:97]  # 3 + 97 = 100 words
    
    description = " ".join(text_words)
    
    cv_at_threshold = {
        "id": "threshold-cv",
        "personal_info": {
            "name": "Test User",
            "title": "Software Engineer"
        },
        "summary": "",
        "experience": [
            {
                "id": "exp-1",
                "title": "Engineer",
                "company": "TechCorp",
                "start_date": "2020-01",
                "end_date": "2023-12",
                "description": description,
                "achievements": []
            }
        ],
        "education": [],
        "skills": {"categories": []},
        "certifications": []
    }
    
    # Create CV with keyword above threshold (5%)
    # For 100 words, 5% = 5 occurrences
    text_words_above = [keyword] * 5 + filler_words[:95]  # 5 + 95 = 100 words
    description_above = " ".join(text_words_above)
    
    cv_above_threshold = {
        "id": "above-threshold-cv",
        "personal_info": {
            "name": "Test User",
            "title": "Software Engineer"
        },
        "summary": "",
        "experience": [
            {
                "id": "exp-1",
                "title": "Engineer",
                "company": "TechCorp",
                "start_date": "2020-01",
                "end_date": "2023-12",
                "description": description_above,
                "achievements": []
            }
        ],
        "education": [],
        "skills": {"categories": []},
        "certifications": []
    }
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create analyzer
    analyzer = ATSAnalyzer(mock_provider)
    
    # Analyze CV at threshold
    request_at = ATSAnalysisRequest(
        cv_id=cv_at_threshold["id"],
        cv_data=cv_at_threshold,
        industry="software",
        job_title="Software Engineer"
    )
    result_at = await analyzer.analyze_ats_compatibility(request_at)
    
    # Analyze CV above threshold
    request_above = ATSAnalysisRequest(
        cv_id=cv_above_threshold["id"],
        cv_data=cv_above_threshold,
        industry="software",
        job_title="Software Engineer"
    )
    result_above = await analyzer.analyze_ats_compatibility(request_above)
    
    # Property assertions
    # 1. CV above threshold should have keyword stuffing detection
    stuffing_recs_above = [
        rec for rec in result_above.recommendations
        if "keyword" in rec.category.lower() and "stuff" in rec.category.lower()
    ]
    
    # If Python is in industry keywords, should detect stuffing
    if "python" in [k.lower() for k in result_above.industry_keywords]:
        assert len(stuffing_recs_above) > 0, \
            "CV with 5% keyword density should trigger stuffing detection"
    
    # 2. Keyword density should be calculated correctly
    if "python" in [k.lower() for k in result_above.industry_keywords]:
        python_density_above = None
        for kw, density in result_above.keyword_density.items():
            if kw.lower() == "python":
                python_density_above = density
                break
        
        if python_density_above is not None:
            # Should be approximately 5% (allow some tolerance)
            assert 4.0 <= python_density_above <= 6.0, \
                f"Keyword density should be ~5%, got {python_density_above}%"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy(),
    cv_and_keyword=keyword_stuffed_cv_strategy()
)
@pytest.mark.asyncio
async def test_property_keyword_stuffing_detection_affects_compatibility_score(
    config_and_provider,
    cv_and_keyword
):
    """
    Property 43: Keyword Stuffing Detection - Score Impact
    
    For any CV with keyword stuffing, the compatibility score should
    be negatively impacted.
    
    Validates: Requirements 14.3
    """
    config, provider_type = config_and_provider
    cv_data, stuffed_keyword = cv_and_keyword
    
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
    # 1. Should have compatibility score
    assert result.compatibility_score is not None, \
        "Result should have compatibility score"
    
    # 2. Find keyword stuffing recommendations
    stuffing_recommendations = [
        rec for rec in result.recommendations
        if "keyword" in rec.category.lower() and "stuff" in rec.category.lower()
    ]
    
    # 3. If stuffing detected, keyword score should be impacted
    if len(stuffing_recommendations) > 0:
        # Keyword score should be reduced due to stuffing
        # The implementation deducts 10 points per stuffing issue
        expected_max_score = 100 - (len(stuffing_recommendations) * 10)
        
        assert result.compatibility_score.keyword_score <= expected_max_score, \
            f"Keyword score should be reduced by stuffing penalties, " \
            f"expected <= {expected_max_score}, got {result.compatibility_score.keyword_score}"
        
        # 4. Overall score should also be affected
        # Since keyword score is 35% of overall score, overall should be lower
        assert result.compatibility_score.overall_score < 100, \
            "Overall score should be reduced when keyword stuffing is detected"
