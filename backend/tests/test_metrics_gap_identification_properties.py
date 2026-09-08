"""
Property-Based Tests for Metrics Gap Identification

Feature: cv-web-app, Property 29: Metrics Gap Identification
Validates: Requirements 11.3

Property 29: Metrics Gap Identification
For any CV section that could contain quantifiable metrics but doesn't, the service
should flag the absence and suggest where to add them.

This test validates that metrics gap identification correctly identifies missing
quantifiable metrics across different CV content.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any

from app.llm.cv_optimizer import CVOptimizer
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
        
        # Check if prompt contains metrics indicators
        prompt_lower = prompt.lower()
        metrics_patterns = [
            r'\d+%', r'\$\d+', r'\d+\+', r'\d+x',
            'increased by', 'reduced by', 'improved by',
            'team of', 'budget of', 'saved', 'generated'
        ]
        
        import re
        
        # Count how many metrics patterns are found
        metrics_count = sum(1 for pattern in metrics_patterns if re.search(pattern, prompt_lower))
        
        # Check for non-metric descriptions
        non_metric_patterns = [
            'developed web applications', 'managed software', 'worked on',
            'implemented features', 'created system', 'built application'
        ]
        has_non_metric_content = any(pattern in prompt_lower for pattern in non_metric_patterns)
        
        # Generate realistic optimization response based on content
        # If there are some metrics but also non-metric content, provide medium priority
        if metrics_count > 0 and has_non_metric_content:
            content = """1. [Metrics] [Priority: Medium] Issue: Some descriptions lack quantifiable metrics
   Suggestion: Add specific numbers, percentages, or metrics to demonstrate impact (e.g., team size, budget, performance improvements)
   Location: Experience Section
   Reasoning: Quantifiable metrics make your impact concrete and memorable for recruiters

2. [Metrics] [Priority: High] Issue: No achievement statements listed
   Suggestion: Add 2-4 bullet points highlighting specific achievements with quantifiable results
   Location: Experience Section
   Reasoning: Achievement statements are crucial for demonstrating your value and impact to hiring managers"""
        elif metrics_count >= 2:
            # For content with multiple metrics, provide minimal feedback
            content = """1. [Metrics] [Priority: Low] Issue: Could add more specific metrics
   Suggestion: Consider adding additional quantifiable results where possible
   Location: Experience Section
   Reasoning: Additional metrics strengthen impact and provide concrete evidence of your achievements"""
        else:
            # For content without metrics, provide metrics-focused recommendations
            content = """1. [Metrics] [Priority: High] Issue: Description lacks quantifiable metrics
   Suggestion: Add specific numbers, percentages, or metrics to demonstrate impact (e.g., team size, budget, performance improvements)
   Location: Experience Section
   Reasoning: Quantifiable metrics make your impact concrete and memorable

2. [Metrics] [Priority: High] Issue: Achievement lacks quantifiable results
   Suggestion: Add specific metrics: percentages, dollar amounts, time saved, or other measurable outcomes
   Location: Experience Section - Achievement 1
   Reasoning: Achievements without metrics are less credible and impactful"""
        
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
def metrics_gap_cv_strategy(draw):
    """Generate CV data with known metrics gaps."""
    # Decide if this CV should have metrics gaps
    has_metrics_gaps = draw(st.booleans())
    
    # Generate experience entries
    num_experiences = draw(st.integers(min_value=1, max_value=3))
    experiences = []
    
    for i in range(num_experiences):
        if has_metrics_gaps and i == 0:
            # First experience lacks metrics
            description_options = [
                "Developed web applications for clients",
                "Managed software development projects",
                "Led team in implementing new features",
                "Worked on system architecture improvements"
            ]
            description = draw(st.sampled_from(description_options))
            
            # Achievements without metrics
            achievements = [
                "Improved system performance",
                "Enhanced user experience",
                "Implemented new features",
                "Reduced technical debt"
            ]
        else:
            # Other experiences have metrics
            metrics_descriptions = [
                "Led team of 8 developers to deliver features ahead of schedule",
                "Managed projects with $2M budget and 15+ stakeholders",
                "Reduced API response time by 50% through optimization",
                "Increased test coverage from 60% to 95%"
            ]
            description = draw(st.sampled_from(metrics_descriptions))
            
            # Achievements with metrics
            achievements = [
                "Reduced deployment time by 40% through automation",
                "Increased user engagement by 25% with new features",
                "Saved $100K annually by optimizing infrastructure",
                "Improved performance by 3x through code refactoring"
            ]
        
        experience = {
            "id": f"exp-{i}",
            "title": draw(st.sampled_from(["Senior Engineer", "Developer", "Tech Lead"])),
            "company": draw(st.sampled_from(["TechCorp", "StartupXYZ", "BigTech Inc"])),
            "start_date": f"202{draw(st.integers(min_value=0, max_value=3))}-01",
            "end_date": f"202{draw(st.integers(min_value=3, max_value=4))}-12",
            "description": description,
            "achievements": achievements[:draw(st.integers(min_value=0, max_value=3))]
        }
        experiences.append(experience)
    
    return {
        "id": "test-cv-id",
        "personal_info": {
            "name": "Test User",
            "title": "Software Engineer",
            "contact": {"email": "test@example.com"}
        },
        "summary": "Experienced software engineer with track record of delivering solutions",
        "experience": experiences,
        "education": [{
            "id": "edu-1",
            "degree": "BS Computer Science",
            "institution": "University",
            "start_date": "2015-09",
            "end_date": "2019-05"
        }],
        "skills": {"categories": [{"name": "Programming", "skills": ["Python", "JavaScript"]}]},
        "certifications": []
    }, has_metrics_gaps


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
            max_tokens=draw(st.integers(min_value=500, max_value=1500))
        )
    elif provider_type == "anthropic":
        model = draw(st.sampled_from(["claude-3-opus", "claude-3-sonnet"]))
        config = LLMConfig(
            provider=provider_type,
            model=model,
            api_key="test-key-456",
            temperature=draw(st.floats(min_value=0.0, max_value=0.5)),
            max_tokens=draw(st.integers(min_value=500, max_value=1500))
        )
    else:  # local
        model = draw(st.sampled_from(["llama2", "mistral"]))
        config = LLMConfig(
            provider=provider_type,
            model=model,
            base_url="http://localhost:11434",
            temperature=draw(st.floats(min_value=0.0, max_value=0.5)),
            max_tokens=draw(st.integers(min_value=500, max_value=1500))
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
    cv_data_and_flag=metrics_gap_cv_strategy()
)
@pytest.mark.asyncio
async def test_property_metrics_gap_identification(
    config_and_provider,
    cv_data_and_flag
):
    """
    Property 29: Metrics Gap Identification
    
    For any CV section that could contain quantifiable metrics but doesn't,
    the service should flag the absence and suggest where to add them.
    
    Validates: Requirements 11.3
    """
    config, provider_type = config_and_provider
    cv_data, has_metrics_gaps = cv_data_and_flag
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create optimizer
    optimizer = CVOptimizer(mock_provider)
    
    # Create optimization request
    request = OptimizationRequest(
        cv_id=cv_data["id"],
        cv_data=cv_data,
        focus_areas=[RecommendationCategory.METRICS],
        include_reasoning=True
    )
    
    # Perform optimization
    result = await optimizer.optimize_cv(request)
    
    # Property assertions
    # 1. Result should not be None
    assert result is not None, "Optimization result should not be None"
    assert isinstance(result, OptimizationResult), "Result should be OptimizationResult instance"
    
    # 2. If CV has metrics gaps, should detect them
    metrics_recommendations = [
        rec for rec in result.recommendations
        if rec.category == RecommendationCategory.METRICS
    ]
    
    if has_metrics_gaps:
        # Should have at least one metrics recommendation
        assert len(metrics_recommendations) > 0, \
            "CV with metrics gaps should have metrics recommendations"
        
        # 3. Each metrics recommendation should identify the gap
        for rec in metrics_recommendations:
            assert rec.issue, "Metrics recommendation should have issue description"
            assert len(rec.issue.strip()) > 0, "Issue should not be empty"
            
            # Issue should mention missing metrics or quantifiable results
            issue_lower = rec.issue.lower()
            metrics_indicators = [
                "metric", "quantif", "number", "percentage", "measur",
                "lacks", "missing", "without", "no achievement",
                "specific", "concrete", "result"
            ]
            
            has_metrics_indicator = any(indicator in issue_lower for indicator in metrics_indicators)
            assert has_metrics_indicator, \
                f"Metrics issue should mention missing quantifiable metrics, got: {rec.issue}"
        
        # 4. Each metrics recommendation should suggest specific types of metrics
        for rec in metrics_recommendations:
            assert rec.suggestion, "Metrics recommendation should have suggestion"
            assert len(rec.suggestion.strip()) > 0, "Suggestion should not be empty"
            
            # Suggestion should mention types of metrics to add
            suggestion_lower = rec.suggestion.lower()
            metric_type_indicators = [
                "percentage", "percent", "%", "number", "dollar", "$",
                "team size", "budget", "time", "performance", "improvement",
                "increase", "decrease", "reduce", "save", "generate",
                "metric", "quantif", "measur", "specific", "concrete"
            ]
            
            has_metric_type = any(indicator in suggestion_lower for indicator in metric_type_indicators)
            assert has_metric_type, \
                f"Metrics suggestion should mention specific types of metrics to add, got: {rec.suggestion}"
        
        # 5. Recommendations should identify specific location in CV
        for rec in metrics_recommendations:
            assert rec.location, "Metrics recommendation should have location"
            assert len(rec.location.strip()) > 0, "Location should not be empty"
            
            # Location should reference CV section
            location_lower = rec.location.lower()
            location_indicators = [
                "experience", "achievement", "description",
                "work experience", "professional experience",
                "summary", "position"
            ]
            
            has_location_indicator = any(indicator in location_lower for indicator in location_indicators)
            assert has_location_indicator, \
                f"Location should reference specific CV section, got: {rec.location}"
        
        # 6. Recommendations should have appropriate priority
        # Note: Priority can be LOW if some metrics exist but more could be added
        # HIGH/MEDIUM priority for clear gaps, LOW for enhancement suggestions
        for rec in metrics_recommendations:
            assert rec.priority in [
                RecommendationPriority.HIGH,
                RecommendationPriority.MEDIUM,
                RecommendationPriority.LOW
            ], "Metrics recommendations should have valid priority"
            
            # If issue mentions "lacks" or "missing", should be HIGH or MEDIUM
            if any(word in rec.issue.lower() for word in ["lacks", "missing", "without", "no achievement"]):
                assert rec.priority in [
                    RecommendationPriority.HIGH,
                    RecommendationPriority.MEDIUM
                ], f"Clear metrics gaps should be high or medium priority, got {rec.priority} for: {rec.issue}"
        
        # 7. If reasoning requested, should explain why metrics are important
        for rec in metrics_recommendations:
            if rec.reasoning:
                reasoning_lower = rec.reasoning.lower()
                reasoning_indicators = [
                    "impact", "concrete", "credible", "memorable",
                    "demonstrate", "prove", "show", "evidence",
                    "recruiter", "hiring", "quantif", "measur",
                    "specific", "tangible", "results"
                ]
                
                has_reasoning_indicator = any(
                    indicator in reasoning_lower for indicator in reasoning_indicators
                )
                assert has_reasoning_indicator, \
                    f"Reasoning should explain importance of metrics, got: {rec.reasoning}"
    
    # 8. Recommendations should not have exact duplicate issues for same location
    if len(metrics_recommendations) > 1:
        # Group by location to check for duplicates within same location
        from collections import defaultdict
        issues_by_location = defaultdict(list)
        for rec in metrics_recommendations:
            issues_by_location[rec.location].append(rec.issue)
        
        # Check that within each location, issues are unique or reasonably different
        for location, issues in issues_by_location.items():
            if len(issues) > 1:
                # Check for exact duplicates only
                exact_duplicates = len(issues) - len(set(issues))
                # Allow some duplicates if they're for different achievements/items
                assert exact_duplicates <= len(issues) // 2, \
                    f"Too many exact duplicate issues in {location}: {issues}"
    
    # 9. Each recommendation should have unique ID
    if len(metrics_recommendations) > 0:
        rec_ids = [rec.id for rec in metrics_recommendations]
        assert len(rec_ids) == len(set(rec_ids)), \
            "Each recommendation should have unique ID"


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_metrics_gap_identification_specific_sections(
    config_and_provider
):
    """
    Property 29: Metrics Gap Identification - Specific Sections
    
    For CVs with known sections lacking metrics, the service should
    detect and flag each specific section.
    
    Validates: Requirements 11.3
    """
    config, provider_type = config_and_provider
    
    # Test specific sections without metrics
    test_cases = [
        {
            "section": "description",
            "content": "Developed web applications for various clients",
            "location_pattern": "experience"
        },
        {
            "section": "achievement",
            "content": "Improved system performance",
            "location_pattern": "achievement"
        },
        {
            "section": "description",
            "content": "Managed software development projects",
            "location_pattern": "experience"
        },
        {
            "section": "achievement",
            "content": "Enhanced user experience",
            "location_pattern": "achievement"
        }
    ]
    
    for test_case in test_cases:
        # Create CV with specific section lacking metrics
        if test_case["section"] == "description":
            cv_data = {
                "id": "test-cv-id",
                "personal_info": {
                    "name": "Test User",
                    "title": "Software Engineer"
                },
                "summary": "",
                "experience": [{
                    "id": "exp-1",
                    "title": "Senior Engineer",
                    "company": "TechCorp",
                    "start_date": "2020-01",
                    "end_date": "2023-12",
                    "description": test_case["content"],
                    "achievements": []
                }],
                "education": [],
                "skills": {"categories": []},
                "certifications": []
            }
        else:  # achievement
            cv_data = {
                "id": "test-cv-id",
                "personal_info": {
                    "name": "Test User",
                    "title": "Software Engineer"
                },
                "summary": "",
                "experience": [{
                    "id": "exp-1",
                    "title": "Senior Engineer",
                    "company": "TechCorp",
                    "start_date": "2020-01",
                    "end_date": "2023-12",
                    "description": "Led software development initiatives",
                    "achievements": [test_case["content"]]
                }],
                "education": [],
                "skills": {"categories": []},
                "certifications": []
            }
        
        # Create mock provider
        mock_provider = MockLLMProvider(config, provider_type)
        
        # Create optimizer
        optimizer = CVOptimizer(mock_provider)
        
        # Create optimization request
        request = OptimizationRequest(
            cv_id=cv_data["id"],
            cv_data=cv_data,
            focus_areas=[RecommendationCategory.METRICS]
        )
        
        # Perform optimization
        result = await optimizer.optimize_cv(request)
        
        # Property assertions
        # 1. Should detect the metrics gap
        metrics_recommendations = [
            rec for rec in result.recommendations
            if rec.category == RecommendationCategory.METRICS
        ]
        
        assert len(metrics_recommendations) > 0, \
            f"Should detect metrics gap in {test_case['section']}: {test_case['content']}"
        
        # 2. At least one recommendation should reference the section
        found_section = False
        for rec in metrics_recommendations:
            if test_case["location_pattern"].lower() in rec.location.lower():
                found_section = True
                break
        
        assert found_section, \
            f"Should identify metrics gap in {test_case['section']}"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_metrics_gap_identification_with_metrics_no_false_positives(
    config_and_provider
):
    """
    Property 29: Metrics Gap Identification - No False Positives
    
    For CVs with quantifiable metrics, the service should not incorrectly
    flag them as having metrics gaps.
    
    Validates: Requirements 11.3
    """
    config, provider_type = config_and_provider
    
    # Descriptions with metrics that should NOT trigger gaps
    descriptions_with_metrics = [
        "Led team of 8 developers to deliver features ahead of schedule",
        "Managed projects with $2M budget and 15+ stakeholders",
        "Reduced API response time by 50% through optimization",
        "Increased test coverage from 60% to 95%",
        "Saved $100K annually by optimizing infrastructure"
    ]
    
    for description in descriptions_with_metrics:
        # Create CV with metrics
        cv_data = {
            "id": "test-cv-id",
            "personal_info": {
                "name": "Test User",
                "title": "Software Engineer"
            },
            "summary": "Results-driven engineer with proven track record",
            "experience": [{
                "id": "exp-1",
                "title": "Senior Engineer",
                "company": "TechCorp",
                "start_date": "2020-01",
                "end_date": "2023-12",
                "description": description,
                "achievements": [
                    "Delivered features resulting in 25% revenue increase",
                    "Improved performance by 3x through code refactoring"
                ]
            }],
            "education": [{
                "id": "edu-1",
                "degree": "BS Computer Science",
                "institution": "University",
                "start_date": "2015-09",
                "end_date": "2019-05"
            }],
            "skills": {"categories": [{"name": "Programming", "skills": ["Python", "JavaScript"]}]},
            "certifications": []
        }
        
        # Create mock provider
        mock_provider = MockLLMProvider(config, provider_type)
        
        # Create optimizer
        optimizer = CVOptimizer(mock_provider)
        
        # Create optimization request
        request = OptimizationRequest(
            cv_id=cv_data["id"],
            cv_data=cv_data,
            focus_areas=[RecommendationCategory.METRICS]
        )
        
        # Perform optimization
        result = await optimizer.optimize_cv(request)
        
        # Property assertions
        # 1. Should have minimal or no metrics recommendations for content with metrics
        metrics_recommendations = [
            rec for rec in result.recommendations
            if rec.category == RecommendationCategory.METRICS
        ]
        
        # Content with metrics should result in few or no metrics gap flags
        # Allow up to 1 minor suggestion for additional metrics, but not multiple gaps
        assert len(metrics_recommendations) <= 1, \
            f"Content with metrics should not trigger multiple metrics gap flags, got {len(metrics_recommendations)} for: {description}"
        
        # 2. If there is a metrics recommendation, it should be low priority
        for rec in metrics_recommendations:
            assert rec.priority in [RecommendationPriority.LOW, RecommendationPriority.MEDIUM], \
                f"Content with metrics should not trigger high priority metrics gaps, got {rec.priority} for: {description}"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_metrics_gap_identification_no_achievements(
    config_and_provider
):
    """
    Property 29: Metrics Gap Identification - No Achievements
    
    For experience entries with no achievement statements, the service
    should flag this as a metrics gap.
    
    Validates: Requirements 11.3
    """
    config, provider_type = config_and_provider
    
    # Create CV with experience but no achievements
    cv_data = {
        "id": "test-cv-id",
        "personal_info": {
            "name": "Test User",
            "title": "Software Engineer"
        },
        "summary": "Experienced software engineer",
        "experience": [{
            "id": "exp-1",
            "title": "Senior Engineer",
            "company": "TechCorp",
            "start_date": "2020-01",
            "end_date": "2023-12",
            "description": "Developed web applications and managed projects",
            "achievements": []  # No achievements
        }],
        "education": [],
        "skills": {"categories": []},
        "certifications": []
    }
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create optimizer
    optimizer = CVOptimizer(mock_provider)
    
    # Create optimization request
    request = OptimizationRequest(
        cv_id=cv_data["id"],
        cv_data=cv_data,
        focus_areas=[RecommendationCategory.METRICS]
    )
    
    # Perform optimization
    result = await optimizer.optimize_cv(request)
    
    # Property assertions
    # 1. Should detect missing achievements
    metrics_recommendations = [
        rec for rec in result.recommendations
        if rec.category == RecommendationCategory.METRICS
    ]
    
    assert len(metrics_recommendations) > 0, \
        "Should detect missing achievements as metrics gap"
    
    # 2. At least one recommendation should mention achievements
    found_achievement_mention = False
    for rec in metrics_recommendations:
        combined_text = f"{rec.issue} {rec.suggestion}".lower()
        if "achievement" in combined_text or "bullet" in combined_text:
            found_achievement_mention = True
            break
    
    assert found_achievement_mention, \
        "Should mention missing achievements in recommendations"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_metrics_gap_identification_consistency(
    config_and_provider
):
    """
    Property 29: Metrics Gap Identification - Consistency
    
    For the same CV with metrics gaps, detection should be consistent
    across multiple runs.
    
    Validates: Requirements 11.3
    """
    config, provider_type = config_and_provider
    
    # Create CV with known metrics gaps
    cv_data = {
        "id": "test-cv-id",
        "personal_info": {
            "name": "Test User",
            "title": "Software Engineer"
        },
        "summary": "Experienced software engineer",
        "experience": [{
            "id": "exp-1",
            "title": "Senior Engineer",
            "company": "TechCorp",
            "start_date": "2020-01",
            "end_date": "2023-12",
            "description": "Developed web applications and managed projects",
            "achievements": [
                "Improved system performance",
                "Enhanced user experience"
            ]
        }],
        "education": [],
        "skills": {"categories": []},
        "certifications": []
    }
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create optimizer
    optimizer = CVOptimizer(mock_provider)
    
    # Create optimization request
    request = OptimizationRequest(
        cv_id=cv_data["id"],
        cv_data=cv_data,
        focus_areas=[RecommendationCategory.METRICS]
    )
    
    # Run optimization twice
    result1 = await optimizer.optimize_cv(request)
    result2 = await optimizer.optimize_cv(request)
    
    # Property assertions
    # 1. Both should detect metrics gaps
    metrics_recs1 = [
        rec for rec in result1.recommendations
        if rec.category == RecommendationCategory.METRICS
    ]
    metrics_recs2 = [
        rec for rec in result2.recommendations
        if rec.category == RecommendationCategory.METRICS
    ]
    
    assert len(metrics_recs1) > 0, "First run should detect metrics gaps"
    assert len(metrics_recs2) > 0, "Second run should detect metrics gaps"
    
    # 2. Should detect similar number of gaps
    count_diff = abs(len(metrics_recs1) - len(metrics_recs2))
    assert count_diff <= 2, \
        f"Should detect similar number of metrics gaps (diff: {count_diff})"
    
    # 3. Should identify same sections with gaps
    def extract_sections(recs):
        sections = set()
        for rec in recs:
            location_lower = rec.location.lower()
            if "description" in location_lower or "experience" in location_lower:
                sections.add("description")
            if "achievement" in location_lower:
                sections.add("achievement")
        return sections
    
    sections1 = extract_sections(metrics_recs1)
    sections2 = extract_sections(metrics_recs2)
    
    # Should have significant overlap in detected sections
    if sections1 and sections2:
        overlap = len(sections1 & sections2)
        total_unique = len(sections1 | sections2)
        overlap_ratio = overlap / total_unique if total_unique > 0 else 1.0
        
        assert overlap_ratio >= 0.5, \
            f"Should consistently detect same sections with gaps (overlap: {overlap_ratio:.2f})"
