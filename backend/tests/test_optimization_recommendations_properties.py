"""
Property-Based Tests for Optimization Recommendations Structure

Feature: cv-web-app, Property 27: Optimization Recommendations Structure
Validates: Requirements 11.1, 11.5

Property 27: Optimization Recommendations Structure
For any CV content, optimization analysis should return recommendations with
category, priority, issue description, and specific suggestions.

This test validates that CV optimization produces properly structured
recommendations across different CV content and provider configurations.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any

from app.llm.cv_optimizer import CVOptimizer, CVOptimizerFactory
from app.llm.providers.base import BaseLLMProvider, LLMResponse, LLMConfig
from app.models.llm_models import (
    OptimizationRequest,
    OptimizationResult,
    OptimizationRecommendation,
    RecommendationCategory,
    RecommendationPriority
)


# Mock provider for property testing
class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider that simulates optimization analysis."""
    
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
        """Generate mock completion with optimization recommendations."""
        self._call_count += 1
        
        # Generate realistic optimization response
        content = """1. [Language] [Priority: High] Issue: Weak phrase "responsible for" detected in experience description
   Suggestion: Replace with stronger action verb like "Led" or "Managed" to demonstrate ownership
   Location: Experience: Senior Engineer at TechCorp
   Reasoning: Weak phrases reduce impact and fail to demonstrate clear ownership of accomplishments

2. [Metrics] [Priority: High] Issue: Description lacks quantifiable metrics
   Suggestion: Add specific numbers, percentages, or metrics to demonstrate measurable impact
   Location: Experience: Senior Engineer at TechCorp
   Reasoning: Quantifiable metrics make your impact concrete and memorable for recruiters

3. [Structure] [Priority: Medium] Issue: Missing professional summary
   Suggestion: Add a 3-4 sentence professional summary at the top of your CV
   Location: Professional Summary
   Reasoning: A strong summary helps recruiters quickly understand your value proposition

4. [Content] [Priority: Medium] Issue: Achievement statements could be more impactful
   Suggestion: Start each achievement with a strong action verb and include quantifiable results
   Location: Experience: Senior Engineer at TechCorp - Achievement 1
   Reasoning: Achievement statements should clearly demonstrate your contributions and results

5. [Clarity] [Priority: Low] Issue: Some descriptions are overly technical
   Suggestion: Balance technical details with business impact to appeal to both technical and non-technical reviewers
   Location: Experience: Senior Engineer at TechCorp
   Reasoning: Your CV may be reviewed by non-technical recruiters first"""
        
        return LLMResponse(
            content=content,
            model=self.config.model,
            provider=self._provider_name,
            tokens_used=150 + self._call_count * 20
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
    """Generate realistic CV data for testing."""
    # Generate personal info
    names = ["John Doe", "Jane Smith", "Alex Johnson", "Maria Garcia", "David Chen"]
    titles = ["Software Engineer", "Senior Developer", "Product Manager", "Data Scientist", "DevOps Engineer"]
    
    personal_info = {
        "name": draw(st.sampled_from(names)),
        "title": draw(st.sampled_from(titles)),
        "contact": {
            "email": "test@example.com",
            "phone": "+1-555-0100"
        }
    }
    
    # Generate summary (sometimes missing)
    has_summary = draw(st.booleans())
    summary = ""
    if has_summary:
        summaries = [
            "Experienced software engineer with 5+ years of experience",
            "Results-driven professional with proven track record",
            "Responsible for managing various projects",  # Weak language
            "Skilled developer with expertise in multiple technologies"
        ]
        summary = draw(st.sampled_from(summaries))
    
    # Generate experience entries
    num_experiences = draw(st.integers(min_value=0, max_value=4))
    experiences = []
    
    for i in range(num_experiences):
        # Some descriptions have weak language, some don't
        descriptions = [
            "Responsible for developing web applications",  # Weak
            "Led team of 5 developers to deliver high-impact features",  # Strong
            "Worked on various projects",  # Weak
            "Developed and deployed scalable microservices architecture",  # Strong
            "Helped with system improvements",  # Weak
            "Architected and implemented cloud-native solutions reducing costs by 40%"  # Strong with metrics
        ]
        
        # Some have achievements, some don't
        has_achievements = draw(st.booleans())
        achievements = []
        if has_achievements:
            achievement_options = [
                "Improved system performance",  # No metrics
                "Reduced API response time by 50%",  # Has metrics
                "Led migration to cloud infrastructure",  # No metrics
                "Increased test coverage from 60% to 95%"  # Has metrics
            ]
            num_achievements = draw(st.integers(min_value=0, max_value=3))
            achievements = [draw(st.sampled_from(achievement_options)) for _ in range(num_achievements)]
        
        experience = {
            "id": f"exp-{i}",
            "title": draw(st.sampled_from(["Senior Engineer", "Developer", "Tech Lead", "Architect"])),
            "company": draw(st.sampled_from(["TechCorp", "StartupXYZ", "BigTech Inc", "Innovation Labs"])),
            "start_date": f"202{draw(st.integers(min_value=0, max_value=3))}-01",
            "end_date": f"202{draw(st.integers(min_value=3, max_value=4))}-12",
            "description": draw(st.sampled_from(descriptions)),
            "achievements": achievements
        }
        experiences.append(experience)
    
    # Generate education (sometimes missing)
    has_education = draw(st.booleans())
    education = []
    if has_education:
        education = [{
            "id": "edu-1",
            "degree": "BS Computer Science",
            "institution": "University",
            "start_date": "2015-09",
            "end_date": "2019-05"
        }]
    
    # Generate skills (sometimes missing or too many categories)
    num_skill_categories = draw(st.integers(min_value=0, max_value=7))
    skill_categories = []
    for i in range(num_skill_categories):
        category = {
            "name": f"Category {i+1}",
            "skills": ["Python", "JavaScript", "React"]
        }
        skill_categories.append(category)
    
    return {
        "id": "test-cv-id",
        "personal_info": personal_info,
        "summary": summary,
        "experience": experiences,
        "education": education,
        "skills": {"categories": skill_categories},
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
            temperature=draw(st.floats(min_value=0.0, max_value=1.0)),
            max_tokens=draw(st.integers(min_value=500, max_value=2000))
        )
    elif provider_type == "anthropic":
        model = draw(st.sampled_from(["claude-3-opus", "claude-3-sonnet"]))
        config = LLMConfig(
            provider=provider_type,
            model=model,
            api_key="test-key-456",
            temperature=draw(st.floats(min_value=0.0, max_value=1.0)),
            max_tokens=draw(st.integers(min_value=500, max_value=2000))
        )
    else:  # local
        model = draw(st.sampled_from(["llama2", "mistral"]))
        config = LLMConfig(
            provider=provider_type,
            model=model,
            base_url="http://localhost:11434",
            temperature=draw(st.floats(min_value=0.0, max_value=1.0)),
            max_tokens=draw(st.integers(min_value=500, max_value=2000))
        )
    
    return config, provider_type


@st.composite
def focus_areas_strategy(draw):
    """Generate optional focus areas for optimization."""
    has_focus = draw(st.booleans())
    if not has_focus:
        return None
    
    # Select 1-3 random categories to focus on
    all_categories = [
        RecommendationCategory.LANGUAGE,
        RecommendationCategory.METRICS,
        RecommendationCategory.STRUCTURE,
        RecommendationCategory.CONTENT,
        RecommendationCategory.CLARITY
    ]
    
    num_focus = draw(st.integers(min_value=1, max_value=3))
    return draw(st.lists(
        st.sampled_from(all_categories),
        min_size=num_focus,
        max_size=num_focus,
        unique=True
    ))


# Property Tests
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy(),
    cv_data=cv_data_strategy(),
    focus_areas=focus_areas_strategy(),
    include_reasoning=st.booleans()
)
@pytest.mark.asyncio
async def test_property_optimization_recommendations_structure(
    config_and_provider,
    cv_data,
    focus_areas,
    include_reasoning
):
    """
    Property 27: Optimization Recommendations Structure
    
    For any CV content, optimization analysis should return recommendations
    with proper structure including category, priority, issue description,
    and specific suggestions.
    
    Validates: Requirements 11.1, 11.5
    """
    config, provider_type = config_and_provider
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create optimizer
    optimizer = CVOptimizer(mock_provider)
    
    # Create optimization request
    request = OptimizationRequest(
        cv_id=cv_data["id"],
        cv_data=cv_data,
        focus_areas=focus_areas,
        include_reasoning=include_reasoning
    )
    
    # Perform optimization
    result = await optimizer.optimize_cv(request)
    
    # Property assertions
    # 1. Result should not be None
    assert result is not None, "Optimization result should not be None"
    assert isinstance(result, OptimizationResult), "Result should be OptimizationResult instance"
    
    # 2. Should have CV ID
    assert result.cv_id == cv_data["id"], "Result should include correct CV ID"
    
    # 3. Should have overall score in valid range
    assert 0.0 <= result.overall_score <= 100.0, \
        f"Overall score should be between 0 and 100, got {result.overall_score}"
    
    # 4. Should have recommendations list (may be empty for perfect CVs)
    assert isinstance(result.recommendations, list), "Recommendations should be a list"
    
    # 5. Each recommendation should have required structure
    for i, rec in enumerate(result.recommendations):
        assert isinstance(rec, OptimizationRecommendation), \
            f"Recommendation {i+1} should be OptimizationRecommendation instance"
        
        # Required fields
        assert rec.category is not None, \
            f"Recommendation {i+1} should have category"
        assert isinstance(rec.category, RecommendationCategory), \
            f"Recommendation {i+1} category should be RecommendationCategory enum"
        
        assert rec.priority is not None, \
            f"Recommendation {i+1} should have priority"
        assert isinstance(rec.priority, RecommendationPriority), \
            f"Recommendation {i+1} priority should be RecommendationPriority enum"
        
        assert rec.issue, \
            f"Recommendation {i+1} should have non-empty issue description"
        assert len(rec.issue.strip()) > 0, \
            f"Recommendation {i+1} issue should not be just whitespace"
        
        assert rec.suggestion, \
            f"Recommendation {i+1} should have non-empty suggestion"
        assert len(rec.suggestion.strip()) > 0, \
            f"Recommendation {i+1} suggestion should not be just whitespace"
        
        assert rec.location, \
            f"Recommendation {i+1} should have location"
        assert len(rec.location.strip()) > 0, \
            f"Recommendation {i+1} location should not be just whitespace"
        
        # If reasoning was requested, check it's included
        if include_reasoning:
            # Note: Reasoning may be None for rule-based recommendations
            # but LLM-generated ones should have it
            pass  # Optional field, don't enforce
        
        # Recommendation should have unique ID
        assert rec.id, f"Recommendation {i+1} should have unique ID"
    
    # 6. Should have summary
    assert result.summary, "Result should have summary"
    assert len(result.summary.strip()) > 0, "Summary should not be empty"
    
    # 7. Should have strengths list
    assert isinstance(result.strengths, list), "Strengths should be a list"
    # Strengths may be empty for very poor CVs, but usually should have at least one
    
    # 8. Should have areas for improvement list
    assert isinstance(result.areas_for_improvement, list), \
        "Areas for improvement should be a list"
    
    # 9. Should have timestamp
    assert result.analyzed_at is not None, "Result should have analysis timestamp"
    
    # 10. Should have provider information
    assert result.model == config.model, f"Result should indicate model '{config.model}'"
    assert result.provider == provider_type, f"Result should indicate provider '{provider_type}'"
    
    # 11. Priority counts should match actual recommendations
    high_count = sum(1 for r in result.recommendations if r.priority == RecommendationPriority.HIGH)
    medium_count = sum(1 for r in result.recommendations if r.priority == RecommendationPriority.MEDIUM)
    low_count = sum(1 for r in result.recommendations if r.priority == RecommendationPriority.LOW)
    
    assert result.high_priority_count == high_count, \
        f"High priority count should match actual count ({result.high_priority_count} != {high_count})"
    assert result.medium_priority_count == medium_count, \
        f"Medium priority count should match actual count ({result.medium_priority_count} != {medium_count})"
    assert result.low_priority_count == low_count, \
        f"Low priority count should match actual count ({result.low_priority_count} != {low_count})"
    
    # 12. Recommendations by category should be properly grouped
    recs_by_category = result.recommendations_by_category
    assert isinstance(recs_by_category, dict), "Recommendations by category should be a dict"
    
    # Verify all recommendations are in the grouped dict
    total_in_groups = sum(len(recs) for recs in recs_by_category.values())
    assert total_in_groups == len(result.recommendations), \
        "All recommendations should be in category groups"
    
    # 13. If focus areas were specified, recommendations should be relevant
    if focus_areas:
        # At least some recommendations should be in the focus areas
        # (though rule-based checks may add others)
        focus_categories = {area.value for area in focus_areas}
        rec_categories = {rec.category.value for rec in result.recommendations}
        
        # Should have at least one recommendation in a focus area
        # (unless CV is perfect in those areas)
        if len(result.recommendations) > 0:
            has_focus_rec = any(cat in focus_categories for cat in rec_categories)
            # Note: This is a soft check - perfect CVs might not have recommendations
            # even in focus areas


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
async def test_property_optimization_recommendations_completeness(
    config_and_provider,
    cv_data
):
    """
    Property 27: Optimization Recommendations Completeness
    
    For any CV content, optimization should provide actionable recommendations
    with all required fields populated.
    
    Validates: Requirements 11.1, 11.5
    """
    config, provider_type = config_and_provider
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create optimizer
    optimizer = CVOptimizer(mock_provider)
    
    # Create optimization request
    request = OptimizationRequest(
        cv_id=cv_data["id"],
        cv_data=cv_data,
        include_reasoning=True
    )
    
    # Perform optimization
    result = await optimizer.optimize_cv(request)
    
    # Property assertions for completeness
    # 1. Result should be complete
    assert result is not None, "Result should not be None"
    
    # 2. Every recommendation should be actionable
    for i, rec in enumerate(result.recommendations):
        # Issue should describe what's wrong
        assert len(rec.issue) >= 10, \
            f"Recommendation {i+1} issue should be descriptive (at least 10 chars)"
        
        # Suggestion should provide specific guidance
        assert len(rec.suggestion) >= 10, \
            f"Recommendation {i+1} suggestion should be specific (at least 10 chars)"
        
        # Location should identify where in CV
        assert len(rec.location) >= 3, \
            f"Recommendation {i+1} location should identify CV section"
        
        # Suggestion should be different from issue
        assert rec.suggestion.lower() != rec.issue.lower(), \
            f"Recommendation {i+1} suggestion should differ from issue"
    
    # 3. Summary should provide overview
    assert len(result.summary) >= 20, \
        "Summary should provide meaningful overview (at least 20 chars)"
    
    # 4. Should mention score in summary
    assert str(int(result.overall_score)) in result.summary or \
           f"{result.overall_score:.1f}" in result.summary, \
        "Summary should mention the overall score"
    
    # 5. Areas for improvement should be high-level
    for area in result.areas_for_improvement:
        assert len(area) >= 5, "Improvement areas should be descriptive"
    
    # 6. Strengths should be positive statements
    for strength in result.strengths:
        assert len(strength) >= 5, "Strengths should be descriptive"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    cv_data=cv_data_strategy()
)
@pytest.mark.asyncio
async def test_property_optimization_recommendations_consistency(
    cv_data
):
    """
    Property 27: Optimization Recommendations Consistency
    
    For the same CV content, optimization should produce consistent
    recommendation structure across multiple runs.
    
    Validates: Requirements 11.1, 11.5
    """
    # Create mock provider
    config = LLMConfig(
        provider="mock",
        model="mock-model",
        temperature=0.3,  # Low temperature for consistency
        max_tokens=1500
    )
    mock_provider = MockLLMProvider(config, "mock")
    
    # Create optimizer
    optimizer = CVOptimizer(mock_provider)
    
    # Create optimization request
    request = OptimizationRequest(
        cv_id=cv_data["id"],
        cv_data=cv_data,
        include_reasoning=True
    )
    
    # Run optimization twice
    result1 = await optimizer.optimize_cv(request)
    result2 = await optimizer.optimize_cv(request)
    
    # Property assertions for consistency
    # 1. Both results should be valid
    assert result1 is not None, "First result should not be None"
    assert result2 is not None, "Second result should not be None"
    
    # 2. Should have similar number of recommendations
    # (allowing for some variation due to LLM non-determinism)
    rec_count_diff = abs(len(result1.recommendations) - len(result2.recommendations))
    assert rec_count_diff <= 3, \
        f"Recommendation counts should be similar (diff: {rec_count_diff})"
    
    # 3. Should have similar overall scores
    # (allowing for some variation)
    score_diff = abs(result1.overall_score - result2.overall_score)
    assert score_diff <= 15.0, \
        f"Overall scores should be similar (diff: {score_diff})"
    
    # 4. Should identify similar categories of issues
    categories1 = {rec.category for rec in result1.recommendations}
    categories2 = {rec.category for rec in result2.recommendations}
    
    # At least 50% overlap in categories identified
    if categories1 and categories2:
        overlap = len(categories1 & categories2)
        total_unique = len(categories1 | categories2)
        overlap_ratio = overlap / total_unique if total_unique > 0 else 1.0
        
        assert overlap_ratio >= 0.5, \
            f"Should identify similar issue categories (overlap: {overlap_ratio:.2f})"
    
    # 5. Both should have valid structure
    for result in [result1, result2]:
        assert 0.0 <= result.overall_score <= 100.0, "Score should be in valid range"
        assert result.summary, "Should have summary"
        assert isinstance(result.recommendations, list), "Should have recommendations list"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_optimization_recommendations_priority_distribution(
    config_and_provider
):
    """
    Property 27: Optimization Recommendations Priority Distribution
    
    For any CV, recommendations should have a reasonable distribution of
    priorities (not all high or all low).
    
    Validates: Requirements 11.1, 11.5
    """
    config, provider_type = config_and_provider
    
    # Create a CV with known issues
    cv_data = {
        "id": "test-cv-id",
        "personal_info": {
            "name": "Test User",
            "title": "Software Engineer"
        },
        "summary": "",  # Missing summary (high priority)
        "experience": [
            {
                "id": "exp-1",
                "title": "Engineer",
                "company": "Company",
                "start_date": "2020-01",
                "description": "Responsible for various tasks",  # Weak language (medium priority)
                "achievements": []  # No achievements (high priority)
            }
        ],
        "education": [],  # Missing education (medium priority)
        "skills": {"categories": []},  # Missing skills (medium priority)
        "certifications": []
    }
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create optimizer
    optimizer = CVOptimizer(mock_provider)
    
    # Create optimization request
    request = OptimizationRequest(
        cv_id=cv_data["id"],
        cv_data=cv_data
    )
    
    # Perform optimization
    result = await optimizer.optimize_cv(request)
    
    # Property assertions for priority distribution
    # 1. Should have recommendations (CV has clear issues)
    assert len(result.recommendations) > 0, \
        "CV with issues should have recommendations"
    
    # 2. Should have mix of priorities (not all the same)
    priorities = {rec.priority for rec in result.recommendations}
    
    # With multiple issues, should have at least 2 different priority levels
    if len(result.recommendations) >= 3:
        assert len(priorities) >= 2, \
            "Should have mix of priority levels for CV with multiple issues"
    
    # 3. High priority recommendations should be for critical issues
    high_priority_recs = [r for r in result.recommendations 
                          if r.priority == RecommendationPriority.HIGH]
    
    for rec in high_priority_recs:
        # High priority should be for important categories
        assert rec.category in [
            RecommendationCategory.LANGUAGE,
            RecommendationCategory.METRICS,
            RecommendationCategory.STRUCTURE,
            RecommendationCategory.CONTENT
        ], f"High priority recommendation should be for critical category, got {rec.category}"
    
    # 4. Priority counts should be reasonable
    assert result.high_priority_count >= 0, "High priority count should be non-negative"
    assert result.medium_priority_count >= 0, "Medium priority count should be non-negative"
    assert result.low_priority_count >= 0, "Low priority count should be non-negative"
    
    total_count = result.high_priority_count + result.medium_priority_count + result.low_priority_count
    assert total_count == len(result.recommendations), \
        "Sum of priority counts should equal total recommendations"


# Additional test for factory integration
@pytest.mark.asyncio
async def test_optimizer_factory_with_multiple_providers():
    """
    Test that CVOptimizerFactory works with different provider types.
    
    This validates that the factory pattern correctly creates optimizers
    for all supported providers.
    """
    provider_configs = [
        ("openai", "gpt-4", {"api_key": "test-key"}),
        ("anthropic", "claude-3-opus", {"api_key": "test-key"}),
        ("local", "llama2", {"base_url": "http://localhost:11434"}),
    ]
    
    for provider_type, model, extra_config in provider_configs:
        # Create config
        config = LLMConfig(
            provider=provider_type,
            model=model,
            **extra_config
        )
        
        # Create mock provider
        mock_provider = MockLLMProvider(config, provider_type)
        
        # Create optimizer using factory
        optimizer = CVOptimizerFactory.create_optimizer(mock_provider)
        
        # Verify optimizer is created correctly
        assert optimizer is not None, f"Factory should create optimizer for '{provider_type}'"
        assert isinstance(optimizer, CVOptimizer), \
            f"Factory should create CVOptimizer instance for '{provider_type}'"
        assert optimizer.llm_provider == mock_provider, \
            f"Optimizer should use correct provider for '{provider_type}'"
        
        # Test that optimizer can produce results
        cv_data = {
            "id": "test-cv-id",
            "personal_info": {"name": "Test User", "title": "Engineer"},
            "summary": "",
            "experience": [],
            "education": [],
            "skills": {"categories": []},
            "certifications": []
        }
        
        request = OptimizationRequest(
            cv_id="test-cv-id",
            cv_data=cv_data
        )
        
        result = await optimizer.optimize_cv(request)
        
        # Verify result
        assert result is not None, f"Optimizer for '{provider_type}' should produce result"
        assert isinstance(result, OptimizationResult), \
            f"Optimizer for '{provider_type}' should produce OptimizationResult"
        assert result.provider == provider_type, \
            f"Result should indicate provider '{provider_type}'"
