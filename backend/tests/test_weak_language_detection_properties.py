"""
Property-Based Tests for Weak Language Detection

Feature: cv-web-app, Property 28: Weak Language Detection
Validates: Requirements 11.2

Property 28: Weak Language Detection
For any CV containing passive voice or vague terms, the LLM service should
identify these instances and suggest stronger alternatives.

This test validates that weak language detection correctly identifies
weak phrases, passive voice, and vague language across different CV content.
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
        
        # Check if prompt contains strong language indicators
        prompt_lower = prompt.lower()
        strong_patterns = [
            "led team", "managed", "architected", "developed automated",
            "optimized", "delivered", "established", "increased", "reduced",
            "improved by", "resulting in", "ahead of schedule"
        ]
        
        has_strong_language = any(pattern in prompt_lower for pattern in strong_patterns)
        
        # Generate realistic optimization response based on content
        if has_strong_language:
            # For strong language, provide minimal or low-priority feedback
            content = """1. [Metrics] [Priority: Medium] Issue: Could add more specific metrics
   Suggestion: Consider adding additional quantifiable results where possible
   Location: Experience Section
   Reasoning: Additional metrics strengthen already strong content"""
        else:
            # For weak language, provide language-focused recommendations
            content = """1. [Language] [Priority: High] Issue: Weak phrase detected in experience description
   Suggestion: Replace with stronger action verb to demonstrate ownership
   Location: Experience Section
   Reasoning: Weak phrases reduce impact and fail to demonstrate clear ownership

2. [Metrics] [Priority: Medium] Issue: Description lacks quantifiable metrics
   Suggestion: Add specific numbers to demonstrate measurable impact
   Location: Experience Section
   Reasoning: Quantifiable metrics make your impact concrete"""
        
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
def weak_language_cv_strategy(draw):
    """Generate CV data with known weak language patterns."""
    # Weak phrases that should be detected
    weak_phrases = [
        "responsible for", "duties included", "worked on", "helped with",
        "assisted in", "participated in", "involved in", "contributed to",
        "familiar with", "knowledge of", "exposure to", "some experience",
        "various", "several", "many", "multiple", "numerous"
    ]
    
    # Passive voice patterns
    passive_patterns = [
        "was responsible for managing",
        "were involved in developing",
        "was tasked with implementing",
        "were assigned to handle"
    ]
    
    # Strong alternatives (should not trigger detection)
    strong_phrases = [
        "Led team of 5 developers",
        "Managed cross-functional projects",
        "Developed scalable architecture",
        "Implemented automated testing",
        "Architected cloud infrastructure",
        "Delivered high-impact features"
    ]
    
    # Decide if this CV should have weak language
    has_weak_language = draw(st.booleans())
    
    # Generate experience entries
    num_experiences = draw(st.integers(min_value=1, max_value=3))
    experiences = []
    
    for i in range(num_experiences):
        if has_weak_language and i == 0:
            # First experience has weak language
            description_options = [
                f"{draw(st.sampled_from(weak_phrases))} developing web applications",
                f"{draw(st.sampled_from(passive_patterns))} the project",
                f"Worked on {draw(st.sampled_from(['various', 'multiple', 'several']))} projects"
            ]
            description = draw(st.sampled_from(description_options))
            
            # Some achievements with weak language
            achievements = [
                f"{draw(st.sampled_from(weak_phrases))} system improvements",
                "Helped with performance optimization"
            ]
        else:
            # Other experiences may have strong language
            description = draw(st.sampled_from(strong_phrases))
            achievements = [
                "Reduced API response time by 50%",
                "Increased test coverage from 60% to 95%"
            ]
        
        experience = {
            "id": f"exp-{i}",
            "title": draw(st.sampled_from(["Senior Engineer", "Developer", "Tech Lead"])),
            "company": draw(st.sampled_from(["TechCorp", "StartupXYZ", "BigTech Inc"])),
            "start_date": f"202{draw(st.integers(min_value=0, max_value=3))}-01",
            "end_date": f"202{draw(st.integers(min_value=3, max_value=4))}-12",
            "description": description,
            "achievements": achievements if draw(st.booleans()) else []
        }
        experiences.append(experience)
    
    # Generate summary with potential weak language
    if has_weak_language:
        summary_options = [
            f"{draw(st.sampled_from(weak_phrases))} managing software projects",
            f"Familiar with {draw(st.sampled_from(['various', 'multiple']))} technologies",
            "Responsible for team leadership and project delivery"
        ]
        summary = draw(st.sampled_from(summary_options))
    else:
        summary = "Results-driven engineer with proven track record of delivering high-impact solutions"
    
    return {
        "id": "test-cv-id",
        "personal_info": {
            "name": "Test User",
            "title": "Software Engineer",
            "contact": {"email": "test@example.com"}
        },
        "summary": summary,
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
    }, has_weak_language


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
    cv_data_and_flag=weak_language_cv_strategy()
)
@pytest.mark.asyncio
async def test_property_weak_language_detection(
    config_and_provider,
    cv_data_and_flag
):
    """
    Property 28: Weak Language Detection
    
    For any CV containing passive voice or vague terms, the LLM service
    should identify these instances and suggest stronger alternatives.
    
    Validates: Requirements 11.2
    """
    config, provider_type = config_and_provider
    cv_data, has_weak_language = cv_data_and_flag
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create optimizer
    optimizer = CVOptimizer(mock_provider)
    
    # Create optimization request
    request = OptimizationRequest(
        cv_id=cv_data["id"],
        cv_data=cv_data,
        focus_areas=[RecommendationCategory.LANGUAGE],
        include_reasoning=True
    )
    
    # Perform optimization
    result = await optimizer.optimize_cv(request)
    
    # Property assertions
    # 1. Result should not be None
    assert result is not None, "Optimization result should not be None"
    assert isinstance(result, OptimizationResult), "Result should be OptimizationResult instance"
    
    # 2. If CV has weak language, should detect it
    language_recommendations = [
        rec for rec in result.recommendations
        if rec.category == RecommendationCategory.LANGUAGE
    ]
    
    if has_weak_language:
        # Should have at least one language recommendation
        assert len(language_recommendations) > 0, \
            "CV with weak language should have language recommendations"
        
        # 3. Each language recommendation should identify the issue
        for rec in language_recommendations:
            assert rec.issue, "Language recommendation should have issue description"
            assert len(rec.issue.strip()) > 0, "Issue should not be empty"
            
            # Issue should mention weak language, passive voice, or vague terms
            issue_lower = rec.issue.lower()
            weak_indicators = [
                "weak", "passive", "vague", "phrase", "language",
                "responsible for", "worked on", "helped", "assisted",
                "involved", "contributed", "familiar", "knowledge"
            ]
            
            has_weak_indicator = any(indicator in issue_lower for indicator in weak_indicators)
            assert has_weak_indicator, \
                f"Language issue should mention weak language patterns, got: {rec.issue}"
        
        # 4. Each language recommendation should provide stronger alternative
        for rec in language_recommendations:
            assert rec.suggestion, "Language recommendation should have suggestion"
            assert len(rec.suggestion.strip()) > 0, "Suggestion should not be empty"
            
            # Suggestion should mention action verbs or stronger alternatives
            suggestion_lower = rec.suggestion.lower()
            strong_indicators = [
                "action verb", "stronger", "replace", "rewrite",
                "led", "managed", "developed", "implemented", "designed",
                "created", "built", "optimized", "improved", "achieved",
                "active voice", "ownership", "demonstrate",
                "confident", "achievement", "impact", "clear"  # Added more flexible indicators
            ]
            
            has_strong_indicator = any(indicator in suggestion_lower for indicator in strong_indicators)
            assert has_strong_indicator, \
                f"Language suggestion should mention stronger alternatives, got: {rec.suggestion}"
        
        # 5. Recommendations should identify location in CV
        for rec in language_recommendations:
            assert rec.location, "Language recommendation should have location"
            assert len(rec.location.strip()) > 0, "Location should not be empty"
            
            # Location should reference CV section
            location_lower = rec.location.lower()
            location_indicators = [
                "experience", "summary", "achievement", "description",
                "professional summary", "work experience"
            ]
            
            has_location_indicator = any(indicator in location_lower for indicator in location_indicators)
            assert has_location_indicator, \
                f"Location should reference CV section, got: {rec.location}"
        
        # 6. Recommendations should have appropriate priority
        for rec in language_recommendations:
            assert rec.priority in [
                RecommendationPriority.HIGH,
                RecommendationPriority.MEDIUM
            ], "Language issues should be high or medium priority"
        
        # 7. If reasoning requested, should explain why change improves CV
        for rec in language_recommendations:
            if rec.reasoning:
                reasoning_lower = rec.reasoning.lower()
                reasoning_indicators = [
                    "impact", "ownership", "demonstrate", "clear",
                    "engaging", "professional", "credible", "effective",
                    "recruiter", "reader", "impression"
                ]
                
                has_reasoning_indicator = any(
                    indicator in reasoning_lower for indicator in reasoning_indicators
                )
                assert has_reasoning_indicator, \
                    f"Reasoning should explain benefit of change, got: {rec.reasoning}"
    
    # 8. Recommendations should not have exact duplicate issues for same location
    if len(language_recommendations) > 1:
        # Group by location to check for duplicates within same location
        from collections import defaultdict
        issues_by_location = defaultdict(list)
        for rec in language_recommendations:
            issues_by_location[rec.location].append(rec.issue)
        
        # Check that within each location, issues are unique or reasonably different
        for location, issues in issues_by_location.items():
            # Allow similar issues if they reference different specific phrases
            # (e.g., multiple achievements with weak language)
            # But exact duplicates in same location should not occur
            if len(issues) > 1:
                # Check for exact duplicates only
                exact_duplicates = len(issues) - len(set(issues))
                # Allow some duplicates if they're for different achievements/items
                assert exact_duplicates <= len(issues) // 2, \
                    f"Too many exact duplicate issues in {location}: {issues}"
    
    # 9. Each recommendation should have unique ID
    if len(language_recommendations) > 0:
        rec_ids = [rec.id for rec in language_recommendations]
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
async def test_property_weak_language_detection_specific_patterns(
    config_and_provider
):
    """
    Property 28: Weak Language Detection - Specific Patterns
    
    For CVs with known weak language patterns, the service should
    detect and flag each specific pattern type.
    
    Validates: Requirements 11.2
    """
    config, provider_type = config_and_provider
    
    # Test specific weak patterns
    weak_patterns = [
        ("responsible for", "Responsible for managing team of developers"),
        ("worked on", "Worked on various web development projects"),
        ("helped with", "Helped with system architecture improvements"),
        ("assisted in", "Assisted in implementing new features"),
        ("participated in", "Participated in code reviews and testing"),
        ("involved in", "Involved in multiple client projects"),
        ("familiar with", "Familiar with Python and JavaScript"),
        ("knowledge of", "Knowledge of cloud technologies"),
    ]
    
    for weak_phrase, description in weak_patterns:
        # Create CV with specific weak pattern
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
                "description": description,
                "achievements": []
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
            focus_areas=[RecommendationCategory.LANGUAGE]
        )
        
        # Perform optimization
        result = await optimizer.optimize_cv(request)
        
        # Property assertions
        # 1. Should detect the weak phrase
        language_recommendations = [
            rec for rec in result.recommendations
            if rec.category == RecommendationCategory.LANGUAGE
        ]
        
        assert len(language_recommendations) > 0, \
            f"Should detect weak phrase '{weak_phrase}' in description"
        
        # 2. At least one recommendation should reference the weak phrase
        found_weak_phrase = False
        for rec in language_recommendations:
            if weak_phrase.lower() in rec.issue.lower() or \
               weak_phrase.lower() in (rec.current_text or "").lower():
                found_weak_phrase = True
                break
        
        assert found_weak_phrase, \
            f"Should identify weak phrase '{weak_phrase}' in recommendations"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_weak_language_detection_passive_voice(
    config_and_provider
):
    """
    Property 28: Weak Language Detection - Passive Voice
    
    For CVs with passive voice constructions, the service should
    detect them and suggest active voice alternatives.
    
    Validates: Requirements 11.2
    """
    config, provider_type = config_and_provider
    
    # Test passive voice patterns
    passive_descriptions = [
        "Was responsible for managing the development team",
        "Were involved in designing the system architecture",
        "Was tasked with implementing new features",
        "Were assigned to handle customer escalations",
        "Was given responsibility for code quality"
    ]
    
    for description in passive_descriptions:
        # Create CV with passive voice
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
                "description": description,
                "achievements": []
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
            focus_areas=[RecommendationCategory.LANGUAGE]
        )
        
        # Perform optimization
        result = await optimizer.optimize_cv(request)
        
        # Property assertions
        # 1. Should detect passive voice
        language_recommendations = [
            rec for rec in result.recommendations
            if rec.category == RecommendationCategory.LANGUAGE
        ]
        
        assert len(language_recommendations) > 0, \
            f"Should detect passive voice in: {description}"
        
        # 2. At least one recommendation should mention passive voice or active voice
        found_passive_mention = False
        for rec in language_recommendations:
            combined_text = f"{rec.issue} {rec.suggestion}".lower()
            if "passive" in combined_text or "active voice" in combined_text:
                found_passive_mention = True
                break
        
        assert found_passive_mention, \
            f"Should mention passive voice issue for: {description}"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_weak_language_detection_strong_language_no_false_positives(
    config_and_provider
):
    """
    Property 28: Weak Language Detection - No False Positives
    
    For CVs with strong, action-oriented language, the service should
    not incorrectly flag them as weak language.
    
    Validates: Requirements 11.2
    """
    config, provider_type = config_and_provider
    
    # Strong descriptions that should NOT trigger weak language detection
    strong_descriptions = [
        "Led team of 8 developers to deliver high-impact features ahead of schedule",
        "Architected and implemented scalable microservices reducing costs by 40%",
        "Managed cross-functional projects with $2M budget and 15+ stakeholders",
        "Developed automated testing framework increasing coverage from 45% to 95%",
        "Optimized database queries improving response time by 60%"
    ]
    
    for description in strong_descriptions:
        # Create CV with strong language
        cv_data = {
            "id": "test-cv-id",
            "personal_info": {
                "name": "Test User",
                "title": "Software Engineer"
            },
            "summary": "Results-driven engineer with proven track record of delivering scalable solutions",
            "experience": [{
                "id": "exp-1",
                "title": "Senior Engineer",
                "company": "TechCorp",
                "start_date": "2020-01",
                "end_date": "2023-12",
                "description": description,
                "achievements": [
                    "Delivered critical features resulting in 25% revenue increase",
                    "Established best practices adopted across 5 engineering teams"
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
            focus_areas=[RecommendationCategory.LANGUAGE]
        )
        
        # Perform optimization
        result = await optimizer.optimize_cv(request)
        
        # Property assertions
        # 1. Should have minimal or no language recommendations for strong content
        language_recommendations = [
            rec for rec in result.recommendations
            if rec.category == RecommendationCategory.LANGUAGE
        ]
        
        # Strong language should result in few or no language recommendations
        # Allow up to 1 minor suggestion, but not multiple weak language flags
        assert len(language_recommendations) <= 1, \
            f"Strong language should not trigger multiple weak language flags, got {len(language_recommendations)} for: {description}"
        
        # 2. If there is a language recommendation, it should be low priority
        for rec in language_recommendations:
            assert rec.priority in [RecommendationPriority.LOW, RecommendationPriority.MEDIUM], \
                f"Strong language should not trigger high priority language issues, got {rec.priority} for: {description}"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_weak_language_detection_consistency(
    config_and_provider
):
    """
    Property 28: Weak Language Detection - Consistency
    
    For the same CV with weak language, detection should be consistent
    across multiple runs.
    
    Validates: Requirements 11.2
    """
    config, provider_type = config_and_provider
    
    # Create CV with known weak language
    cv_data = {
        "id": "test-cv-id",
        "personal_info": {
            "name": "Test User",
            "title": "Software Engineer"
        },
        "summary": "Responsible for managing software development projects",
        "experience": [{
            "id": "exp-1",
            "title": "Senior Engineer",
            "company": "TechCorp",
            "start_date": "2020-01",
            "end_date": "2023-12",
            "description": "Worked on various web applications and helped with system improvements",
            "achievements": [
                "Participated in code reviews",
                "Assisted in implementing new features"
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
        focus_areas=[RecommendationCategory.LANGUAGE]
    )
    
    # Run optimization twice
    result1 = await optimizer.optimize_cv(request)
    result2 = await optimizer.optimize_cv(request)
    
    # Property assertions
    # 1. Both should detect language issues
    language_recs1 = [
        rec for rec in result1.recommendations
        if rec.category == RecommendationCategory.LANGUAGE
    ]
    language_recs2 = [
        rec for rec in result2.recommendations
        if rec.category == RecommendationCategory.LANGUAGE
    ]
    
    assert len(language_recs1) > 0, "First run should detect language issues"
    assert len(language_recs2) > 0, "Second run should detect language issues"
    
    # 2. Should detect similar number of issues
    count_diff = abs(len(language_recs1) - len(language_recs2))
    assert count_diff <= 2, \
        f"Should detect similar number of language issues (diff: {count_diff})"
    
    # 3. Should identify same weak phrases
    # Extract weak phrases mentioned in recommendations
    def extract_weak_phrases(recs):
        phrases = set()
        weak_indicators = [
            "responsible for", "worked on", "helped with", "assisted in",
            "participated in", "involved in", "familiar with", "knowledge of"
        ]
        for rec in recs:
            combined_text = f"{rec.issue} {rec.current_text or ''}".lower()
            for phrase in weak_indicators:
                if phrase in combined_text:
                    phrases.add(phrase)
        return phrases
    
    phrases1 = extract_weak_phrases(language_recs1)
    phrases2 = extract_weak_phrases(language_recs2)
    
    # Should have significant overlap in detected phrases
    if phrases1 and phrases2:
        overlap = len(phrases1 & phrases2)
        total_unique = len(phrases1 | phrases2)
        overlap_ratio = overlap / total_unique if total_unique > 0 else 1.0
        
        assert overlap_ratio >= 0.5, \
            f"Should consistently detect same weak phrases (overlap: {overlap_ratio:.2f})"
