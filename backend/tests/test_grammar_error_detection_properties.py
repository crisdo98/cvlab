"""
Property-Based Tests for Grammar Error Detection

Feature: cv-web-app, Property 36: Grammar Error Detection
Validates: Requirements 13.1

Property 36: Grammar Error Detection
For any text containing grammatical errors, the LLM service should
detect and provide corrections.

This test validates that grammar error detection correctly identifies
grammar errors, spelling mistakes, punctuation issues, and provides
appropriate corrections across different CV content.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any

from app.llm.grammar_checker import GrammarChecker
from app.llm.providers.base import BaseLLMProvider, LLMResponse, LLMConfig
from app.models.llm_models import (
    GrammarCheckRequest,
    GrammarCheckResult,
    GrammarIssue,
    GrammarIssueType,
    RecommendationPriority
)


# Mock provider for property testing
class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider that simulates grammar checking."""
    
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
        """Generate mock completion with grammar checking results."""
        self._call_count += 1
        
        # Check if prompt contains grammar errors
        prompt_lower = prompt.lower()
        
        # Known grammar error patterns
        grammar_errors = []
        
        # Subject-verb agreement errors
        if "i was a experienced" in prompt_lower or "a experienced" in prompt_lower:
            grammar_errors.append({
                "location": "Summary" if "summary" in prompt_lower else "Experience Section",
                "type": "grammar",
                "issue": "a experienced",
                "correction": "an experienced",
                "explanation": "Use 'an' before words starting with vowel sounds",
                "severity": "high"
            })
        
        if "he have" in prompt_lower or "she have" in prompt_lower:
            grammar_errors.append({
                "location": "Experience Section",
                "type": "grammar",
                "issue": "he have" if "he have" in prompt_lower else "she have",
                "correction": "he has" if "he have" in prompt_lower else "she has",
                "explanation": "Subject-verb agreement: singular subjects require singular verbs",
                "severity": "high"
            })
        
        if "they was" in prompt_lower:
            grammar_errors.append({
                "location": "Experience Section",
                "type": "grammar",
                "issue": "they was",
                "correction": "they were",
                "explanation": "Subject-verb agreement: plural subjects require plural verbs",
                "severity": "high"
            })
        
        # Article errors
        if "a unique" in prompt_lower:
            grammar_errors.append({
                "location": "Summary",
                "type": "grammar",
                "issue": "a unique",
                "correction": "a unique",
                "explanation": "Correct article usage",
                "severity": "low"
            })
        
        # Spelling errors
        if "recieve" in prompt_lower:
            grammar_errors.append({
                "location": "Experience Section",
                "type": "spelling",
                "issue": "recieve",
                "correction": "receive",
                "explanation": "'I before E except after C' - correct spelling is 'receive'",
                "severity": "high"
            })
        
        if "occured" in prompt_lower:
            grammar_errors.append({
                "location": "Experience Section",
                "type": "spelling",
                "issue": "occured",
                "correction": "occurred",
                "explanation": "Double consonant before -ed: correct spelling is 'occurred'",
                "severity": "high"
            })
        
        if "managment" in prompt_lower:
            grammar_errors.append({
                "location": "Experience Section",
                "type": "spelling",
                "issue": "managment",
                "correction": "management",
                "explanation": "Correct spelling is 'management' with 'e' before 'ment'",
                "severity": "high"
            })
        
        # Punctuation errors
        if "however" in prompt_lower and "however," not in prompt_lower and "however;" not in prompt_lower:
            # Check if "however" appears without proper punctuation
            if ". however " in prompt_lower or " however " in prompt_lower:
                grammar_errors.append({
                    "location": "Experience Section",
                    "type": "punctuation",
                    "issue": "however without comma",
                    "correction": "however, with comma",
                    "explanation": "Transitional words like 'however' should be followed by a comma",
                    "severity": "medium"
                })
        
        # Tense errors
        if "i develop" in prompt_lower and ("previous" in prompt_lower or "past" in prompt_lower or "2020" in prompt_lower):
            grammar_errors.append({
                "location": "Experience: Previous Position",
                "type": "tense",
                "issue": "I develop",
                "correction": "I developed",
                "explanation": "Past tense should be used for previous positions",
                "severity": "high"
            })
        
        # Generate response based on detected errors
        if grammar_errors:
            content_parts = []
            for error in grammar_errors:
                content_parts.append(f"""LOCATION: {error['location']}
ISSUE_TYPE: {error['type']}
ISSUE_TEXT: {error['issue']}
CORRECTION: {error['correction']}
EXPLANATION: {error['explanation']}
SEVERITY: {error['severity']}
---""")
            content = "\n".join(content_parts)
        else:
            content = "NO_ISSUES_FOUND"
        
        return LLMResponse(
            content=content,
            model=self.config.model,
            provider=self._provider_name,
            tokens_used=100 + self._call_count * 20
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
def grammar_error_cv_strategy(draw):
    """Generate CV data with known grammar errors."""
    # Grammar error patterns
    grammar_errors = [
        ("a experienced", "article error"),
        ("he have", "subject-verb agreement"),
        ("they was", "subject-verb agreement"),
    ]
    
    # Spelling error patterns
    spelling_errors = [
        ("recieve", "spelling error"),
        ("occured", "spelling error"),
        ("managment", "spelling error"),
    ]
    
    # Correct alternatives
    correct_phrases = [
        "an experienced software engineer",
        "developed scalable applications",
        "implemented robust solutions",
        "managed cross-functional teams"
    ]
    
    # Decide if this CV should have errors
    has_errors = draw(st.booleans())
    
    # Generate summary
    if has_errors and draw(st.booleans()):
        error_type = draw(st.sampled_from(["grammar", "spelling"]))
        if error_type == "grammar":
            error_phrase, _ = draw(st.sampled_from(grammar_errors))
            summary = f"I am {error_phrase} software engineer with 5 years of experience"
        else:
            error_phrase, _ = draw(st.sampled_from(spelling_errors))
            summary = f"I {error_phrase}d recognition for outstanding performance"
    else:
        summary = draw(st.sampled_from(correct_phrases))
    
    # Generate experience entries
    num_experiences = draw(st.integers(min_value=1, max_value=2))
    experiences = []
    
    for i in range(num_experiences):
        if has_errors and i == 0:
            # First experience has errors
            error_type = draw(st.sampled_from(["grammar", "spelling"]))
            if error_type == "grammar":
                error_phrase, _ = draw(st.sampled_from(grammar_errors))
                description = f"I develop applications and {error_phrase} managed the team"
            else:
                error_phrase, _ = draw(st.sampled_from(spelling_errors))
                description = f"This {error_phrase} during the project timeline"
            
            achievements = [
                f"The project {draw(st.sampled_from(['recieve', 'occured']))}d positive feedback"
            ] if draw(st.booleans()) else []
        else:
            description = draw(st.sampled_from(correct_phrases))
            achievements = ["Delivered high-quality solutions on time"]
        
        experience = {
            "id": f"exp-{i}",
            "title": draw(st.sampled_from(["Senior Engineer", "Developer", "Tech Lead"])),
            "company": draw(st.sampled_from(["TechCorp", "StartupXYZ", "BigTech Inc"])),
            "start_date": f"202{draw(st.integers(min_value=0, max_value=2))}-01",
            "end_date": f"202{draw(st.integers(min_value=3, max_value=4))}-12",
            "current": False,
            "description": description,
            "achievements": achievements
        }
        experiences.append(experience)
    
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
    }, has_errors


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
    cv_data_and_flag=grammar_error_cv_strategy()
)
@pytest.mark.asyncio
async def test_property_grammar_error_detection(
    config_and_provider,
    cv_data_and_flag
):
    """
    Property 36: Grammar Error Detection
    
    For any text containing grammatical errors, the LLM service should
    detect and provide corrections.
    
    Validates: Requirements 13.1
    """
    config, provider_type = config_and_provider
    cv_data, has_errors = cv_data_and_flag
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create grammar checker
    checker = GrammarChecker(mock_provider)
    
    # Create grammar check request
    request = GrammarCheckRequest(
        cv_id=cv_data["id"],
        cv_data=cv_data
    )
    
    # Perform grammar check
    result = await checker.check_grammar(request)
    
    # Property assertions
    # 1. Result should not be None
    assert result is not None, "Grammar check result should not be None"
    assert isinstance(result, GrammarCheckResult), "Result should be GrammarCheckResult instance"
    
    # 2. Result should have required fields
    assert result.cv_id == cv_data["id"], "Result should have correct CV ID"
    assert result.model, "Result should have model information"
    assert result.provider, "Result should have provider information"
    assert result.overall_quality, "Result should have overall quality assessment"
    
    # 3. If CV has errors, should detect them
    if has_errors:
        # Should have at least one grammar issue
        assert len(result.issues) > 0, \
            "CV with grammar errors should have detected issues"
        
        # 4. Each issue should have required fields
        for issue in result.issues:
            assert isinstance(issue, GrammarIssue), "Issue should be GrammarIssue instance"
            assert issue.type, "Issue should have type"
            assert isinstance(issue.type, GrammarIssueType), "Issue type should be GrammarIssueType enum"
            assert issue.location, "Issue should have location"
            assert len(issue.location.strip()) > 0, "Location should not be empty"
            assert issue.issue_text, "Issue should have issue text"
            assert len(issue.issue_text.strip()) > 0, "Issue text should not be empty"
            assert issue.correction, "Issue should have correction"
            assert len(issue.correction.strip()) > 0, "Correction should not be empty"
            assert issue.explanation, "Issue should have explanation"
            assert len(issue.explanation.strip()) > 0, "Explanation should not be empty"
            assert issue.severity, "Issue should have severity"
            assert isinstance(issue.severity, RecommendationPriority), \
                "Severity should be RecommendationPriority enum"
        
        # 5. Corrections should be different from issue text
        for issue in result.issues:
            # Normalize for comparison (lowercase, strip whitespace)
            issue_normalized = issue.issue_text.lower().strip()
            correction_normalized = issue.correction.lower().strip()
            
            assert issue_normalized != correction_normalized, \
                f"Correction should differ from issue text: '{issue.issue_text}' vs '{issue.correction}'"
        
        # 6. Location should reference CV section
        for issue in result.issues:
            location_lower = issue.location.lower()
            location_indicators = [
                "summary", "experience", "education", "achievement",
                "description", "section", "position", "skill"
            ]
            
            has_location_indicator = any(indicator in location_lower for indicator in location_indicators)
            assert has_location_indicator, \
                f"Location should reference CV section, got: {issue.location}"
        
        # 7. Explanation should explain the error
        for issue in result.issues:
            explanation_lower = issue.explanation.lower()
            explanation_indicators = [
                "should", "use", "correct", "error", "mistake",
                "grammar", "spelling", "punctuation", "tense",
                "agreement", "article", "verb", "subject"
            ]
            
            has_explanation_indicator = any(
                indicator in explanation_lower for indicator in explanation_indicators
            )
            assert has_explanation_indicator, \
                f"Explanation should explain the error, got: {issue.explanation}"
        
        # 8. Grammar and spelling errors should be high or medium priority
        for issue in result.issues:
            if issue.type in [GrammarIssueType.GRAMMAR, GrammarIssueType.SPELLING]:
                assert issue.severity in [
                    RecommendationPriority.HIGH,
                    RecommendationPriority.MEDIUM
                ], f"Grammar/spelling errors should be high or medium priority, got {issue.severity}"
    
    # 9. Issues should not have exact duplicates
    if len(result.issues) > 1:
        issue_signatures = []
        for issue in result.issues:
            signature = (issue.type, issue.location, issue.issue_text.lower().strip())
            issue_signatures.append(signature)
        
        # Check for exact duplicates
        unique_signatures = set(issue_signatures)
        assert len(unique_signatures) == len(issue_signatures), \
            "Should not have exact duplicate issues"
    
    # 10. Overall quality should reflect number and severity of issues
    if len(result.issues) == 0:
        assert "excellent" in result.overall_quality.lower() or "no" in result.overall_quality.lower(), \
            "Quality should indicate no issues when none found"
    elif len(result.issues) > 5:
        high_count = sum(1 for i in result.issues if i.severity == RecommendationPriority.HIGH)
        if high_count > 3:
            assert "needs improvement" in result.overall_quality.lower() or "issues" in result.overall_quality.lower(), \
                "Quality should indicate problems when many high-priority issues found"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_grammar_error_detection_specific_errors(
    config_and_provider
):
    """
    Property 36: Grammar Error Detection - Specific Error Types
    
    For CVs with known specific grammar errors, the service should
    detect and correct each error type appropriately.
    
    Validates: Requirements 13.1
    """
    config, provider_type = config_and_provider
    
    # Test specific grammar error patterns
    error_patterns = [
        ("a experienced engineer", "an experienced engineer", "article error"),
        ("he have experience", "he has experience", "subject-verb agreement"),
        ("they was responsible", "they were responsible", "subject-verb agreement"),
        ("I recieve feedback", "I receive feedback", "spelling error"),
        ("the project occured", "the project occurred", "spelling error"),
        ("team managment", "team management", "spelling error"),
    ]
    
    for error_text, correct_text, error_type in error_patterns:
        # Create CV with specific error
        cv_data = {
            "id": "test-cv-id",
            "personal_info": {
                "name": "Test User",
                "title": "Software Engineer"
            },
            "summary": f"I am {error_text} with strong skills",
            "experience": [{
                "id": "exp-1",
                "title": "Senior Engineer",
                "company": "TechCorp",
                "start_date": "2020-01",
                "end_date": "2023-12",
                "current": False,
                "description": f"In this role, {error_text} in various projects",
                "achievements": []
            }],
            "education": [],
            "skills": {"categories": []},
            "certifications": []
        }
        
        # Create mock provider
        mock_provider = MockLLMProvider(config, provider_type)
        
        # Create grammar checker
        checker = GrammarChecker(mock_provider)
        
        # Create grammar check request
        request = GrammarCheckRequest(
            cv_id=cv_data["id"],
            cv_data=cv_data
        )
        
        # Perform grammar check
        result = await checker.check_grammar(request)
        
        # Property assertions
        # 1. Should detect the error
        assert len(result.issues) > 0, \
            f"Should detect {error_type}: '{error_text}'"
        
        # 2. At least one issue should reference the error
        found_error = False
        for issue in result.issues:
            issue_text_lower = issue.issue_text.lower()
            # Check if the error phrase or key words from it are in the issue
            error_words = error_text.lower().split()
            if any(word in issue_text_lower for word in error_words if len(word) > 3):
                found_error = True
                
                # 3. Correction should be provided
                assert issue.correction, f"Should provide correction for {error_type}"
                assert len(issue.correction.strip()) > 0, "Correction should not be empty"
                
                # 4. Correction should be different from error
                assert issue.issue_text.lower().strip() != issue.correction.lower().strip(), \
                    f"Correction should differ from error for {error_type}"
                
                break
        
        assert found_error, \
            f"Should identify {error_type} '{error_text}' in issues"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_grammar_error_detection_no_false_positives(
    config_and_provider
):
    """
    Property 36: Grammar Error Detection - No False Positives
    
    For CVs with correct grammar, the service should not incorrectly
    flag them as having errors.
    
    Validates: Requirements 13.1
    """
    config, provider_type = config_and_provider
    
    # Correct text that should NOT trigger grammar errors
    correct_texts = [
        "an experienced software engineer with proven track record",
        "developed scalable applications using modern frameworks",
        "managed cross-functional teams to deliver high-quality solutions",
        "implemented robust testing strategies improving code quality",
        "architected microservices infrastructure reducing costs by 40%"
    ]
    
    for correct_text in correct_texts:
        # Create CV with correct grammar
        cv_data = {
            "id": "test-cv-id",
            "personal_info": {
                "name": "Test User",
                "title": "Software Engineer"
            },
            "summary": f"I am {correct_text}",
            "experience": [{
                "id": "exp-1",
                "title": "Senior Engineer",
                "company": "TechCorp",
                "start_date": "2020-01",
                "end_date": "2023-12",
                "current": False,
                "description": correct_text,
                "achievements": [
                    "Delivered critical features ahead of schedule",
                    "Established best practices adopted across teams"
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
        
        # Create grammar checker
        checker = GrammarChecker(mock_provider)
        
        # Create grammar check request
        request = GrammarCheckRequest(
            cv_id=cv_data["id"],
            cv_data=cv_data
        )
        
        # Perform grammar check
        result = await checker.check_grammar(request)
        
        # Property assertions
        # 1. Should have no or minimal issues for correct grammar
        assert len(result.issues) <= 1, \
            f"Correct grammar should not trigger multiple errors, got {len(result.issues)} for: {correct_text}"
        
        # 2. If there is an issue, it should be low priority or style-related
        for issue in result.issues:
            assert issue.severity in [RecommendationPriority.LOW, RecommendationPriority.MEDIUM], \
                f"Correct grammar should not trigger high priority errors, got {issue.severity} for: {correct_text}"
            
            # Should not be grammar or spelling errors
            assert issue.type not in [GrammarIssueType.GRAMMAR, GrammarIssueType.SPELLING], \
                f"Correct text should not trigger grammar/spelling errors, got {issue.type} for: {correct_text}"
        
        # 3. Overall quality should be positive
        assert "excellent" in result.overall_quality.lower() or \
               "good" in result.overall_quality.lower() or \
               "no" in result.overall_quality.lower(), \
            f"Quality should be positive for correct grammar, got: {result.overall_quality}"


@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_grammar_error_detection_consistency(
    config_and_provider
):
    """
    Property 36: Grammar Error Detection - Consistency
    
    For the same CV with grammar errors, detection should be consistent
    across multiple runs.
    
    Validates: Requirements 13.1
    """
    config, provider_type = config_and_provider
    
    # Create CV with known grammar errors
    cv_data = {
        "id": "test-cv-id",
        "personal_info": {
            "name": "Test User",
            "title": "Software Engineer"
        },
        "summary": "I am a experienced engineer who have strong skills",
        "experience": [{
            "id": "exp-1",
            "title": "Senior Engineer",
            "company": "TechCorp",
            "start_date": "2020-01",
            "end_date": "2023-12",
            "current": False,
            "description": "I recieve feedback and they was happy with results",
            "achievements": [
                "The project occured on schedule",
                "Team managment improved significantly"
            ]
        }],
        "education": [],
        "skills": {"categories": []},
        "certifications": []
    }
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create grammar checker
    checker = GrammarChecker(mock_provider)
    
    # Create grammar check request
    request = GrammarCheckRequest(
        cv_id=cv_data["id"],
        cv_data=cv_data
    )
    
    # Run grammar check twice
    result1 = await checker.check_grammar(request)
    result2 = await checker.check_grammar(request)
    
    # Property assertions
    # 1. Both should detect issues
    assert len(result1.issues) > 0, "First run should detect grammar issues"
    assert len(result2.issues) > 0, "Second run should detect grammar issues"
    
    # 2. Should detect similar number of issues
    count_diff = abs(len(result1.issues) - len(result2.issues))
    assert count_diff <= 2, \
        f"Should detect similar number of issues (diff: {count_diff})"
    
    # 3. Should identify same error types
    types1 = set(issue.type for issue in result1.issues)
    types2 = set(issue.type for issue in result2.issues)
    
    # Should have significant overlap in error types
    if types1 and types2:
        overlap = len(types1 & types2)
        total_unique = len(types1 | types2)
        overlap_ratio = overlap / total_unique if total_unique > 0 else 1.0
        
        assert overlap_ratio >= 0.5, \
            f"Should consistently detect same error types (overlap: {overlap_ratio:.2f})"
    
    # 4. Overall quality assessment should be similar
    quality1_lower = result1.overall_quality.lower()
    quality2_lower = result2.overall_quality.lower()
    
    # Both should indicate issues (not "excellent" or "no issues")
    assert "excellent" not in quality1_lower or "issues" in quality1_lower, \
        "Quality should reflect detected issues"
    assert "excellent" not in quality2_lower or "issues" in quality2_lower, \
        "Quality should reflect detected issues"
