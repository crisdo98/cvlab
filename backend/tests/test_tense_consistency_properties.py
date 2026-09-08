"""
Property-Based Tests for Tense Consistency Verification

Feature: cv-web-app, Property 40: Tense Consistency Verification
Validates: Requirements 13.5

Property 40: Tense Consistency Verification
For any CV with inconsistent tense usage, the service should detect
the inconsistencies and flag them for correction.

This test validates that tense consistency checking correctly identifies
tense errors in CV content, particularly ensuring past tense for previous
positions and present tense for current positions.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any

from app.llm.grammar_checker import GrammarChecker
from app.llm.providers.base import BaseLLMProvider, LLMResponse, LLMConfig
from app.models.llm_models import (
    GrammarIssue,
    GrammarIssueType,
    RecommendationPriority
)


# Mock provider for property testing
class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider that simulates tense consistency checking."""
    
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
        """Generate mock completion with tense checking results."""
        self._call_count += 1
        
        # Check if prompt contains tense errors
        prompt_lower = prompt.lower()
        
        # Determine expected tense from prompt
        expected_tense = None
        if "past tense" in prompt_lower:
            expected_tense = "past"
        elif "present tense" in prompt_lower:
            expected_tense = "present"
        
        # Known tense error patterns
        tense_errors = []
        
        # Present tense verbs that should be past for previous positions
        present_verbs = ["develop", "manage", "lead", "implement", "create", "build"]
        past_verbs = ["developed", "managed", "led", "implemented", "created", "built"]
        
        if expected_tense == "past":
            # Check for present tense verbs in past position
            # Need to check that present tense exists but past tense doesn't
            for i, verb in enumerate(present_verbs):
                # Look for present tense verb with word boundaries
                present_pattern = f" {verb} "
                past_pattern = f" {past_verbs[i]} "
                
                # Check if present tense exists and past tense doesn't
                if present_pattern in f" {prompt_lower} " and past_pattern not in f" {prompt_lower} ":
                    tense_errors.append({
                        "issue": f"I {verb}",
                        "correction": f"I {past_verbs[i]}",
                        "explanation": f"Past tense should be used for previous positions"
                    })
            
            # Check for present continuous
            if "i am developing" in prompt_lower or "i am managing" in prompt_lower:
                tense_errors.append({
                    "issue": "I am developing" if "i am developing" in prompt_lower else "I am managing",
                    "correction": "I developed" if "i am developing" in prompt_lower else "I managed",
                    "explanation": "Past tense should be used for previous positions, not present continuous"
                })
        
        elif expected_tense == "present":
            # Check for past tense verbs in current position
            # Need to check that past tense exists but present tense doesn't
            for i, verb in enumerate(past_verbs):
                # Look for past tense verb with word boundaries
                past_pattern = f" {verb} "
                present_pattern = f" {present_verbs[i]} "
                
                # Check if past tense exists and present tense doesn't
                if past_pattern in f" {prompt_lower} " and present_pattern not in f" {prompt_lower} ":
                    tense_errors.append({
                        "issue": f"I {verb}",
                        "correction": f"I {present_verbs[i]}",
                        "explanation": f"Present tense should be used for current positions"
                    })
        
        # Generate response based on detected errors
        if tense_errors:
            content_parts = []
            for error in tense_errors:
                content_parts.append(f"""ISSUE: {error['issue']}
CORRECTION: {error['correction']}
EXPLANATION: {error['explanation']}
---""")
            content = "\n".join(content_parts)
        else:
            content = "NO_ISSUES_FOUND"
        
        return LLMResponse(
            content=content,
            model=self.config.model,
            provider=self._provider_name,
            tokens_used=80 + self._call_count * 15
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
def tense_error_cv_strategy(draw):
    """Generate CV data with tense consistency issues."""
    # Decide if this CV should have tense errors
    has_tense_errors = draw(st.booleans())
    
    # Generate experience entries
    num_experiences = draw(st.integers(min_value=1, max_value=3))
    experiences = []
    
    for i in range(num_experiences):
        # Randomly decide if this is a current position
        is_current = draw(st.booleans()) if i == 0 else False
        
        # Generate description with appropriate or inappropriate tense
        if has_tense_errors and i == 0:
            # First experience has tense error
            if is_current:
                # Current position with past tense (error)
                description = draw(st.sampled_from([
                    "I developed web applications and managed the team",
                    "I led the engineering team and implemented new features",
                    "I created scalable solutions and built robust systems"
                ]))
                achievements = ["Delivered critical features on time"]
            else:
                # Past position with present tense (error)
                description = draw(st.sampled_from([
                    "I develop software applications and manage projects",
                    "I lead cross-functional teams and implement solutions",
                    "I create innovative products and build infrastructure"
                ]))
                achievements = ["I improve system performance significantly"]
        else:
            # Correct tense usage
            if is_current:
                description = draw(st.sampled_from([
                    "I develop web applications and manage the team",
                    "I lead the engineering team and implement new features",
                    "I create scalable solutions and build robust systems"
                ]))
                achievements = ["Delivering critical features on time"]
            else:
                description = draw(st.sampled_from([
                    "I developed software applications and managed projects",
                    "I led cross-functional teams and implemented solutions",
                    "I created innovative products and built infrastructure"
                ]))
                achievements = ["Delivered critical features on time"]
        
        experience = {
            "id": f"exp-{i}",
            "title": draw(st.sampled_from(["Senior Engineer", "Developer", "Tech Lead", "Software Engineer"])),
            "company": draw(st.sampled_from(["TechCorp", "StartupXYZ", "BigTech Inc", "Innovation Labs"])),
            "start_date": f"202{draw(st.integers(min_value=0, max_value=2))}-01",
            "end_date": None if is_current else f"202{draw(st.integers(min_value=3, max_value=4))}-12",
            "current": is_current,
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
        "summary": "Experienced software engineer with strong technical skills",
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
    }, has_tense_errors


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
    cv_data_and_flag=tense_error_cv_strategy()
)
@pytest.mark.asyncio
async def test_property_tense_consistency_verification(
    config_and_provider,
    cv_data_and_flag
):
    """
    Property 40: Tense Consistency Verification
    
    For any CV with inconsistent tense usage, the service should detect
    the inconsistencies and flag them for correction.
    
    Validates: Requirements 13.5
    """
    config, provider_type = config_and_provider
    cv_data, has_tense_errors = cv_data_and_flag
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create grammar checker
    checker = GrammarChecker(mock_provider)
    
    # Perform tense consistency check
    issues = await checker.check_tense_consistency(cv_data)
    
    # Property assertions
    # 1. Result should not be None
    assert issues is not None, "Tense consistency check result should not be None"
    assert isinstance(issues, list), "Result should be a list of issues"
    
    # 2. If CV has tense errors, should detect them
    if has_tense_errors:
        # Should have at least one tense issue
        assert len(issues) > 0, \
            "CV with tense errors should have detected issues"
        
        # 3. Each issue should be a tense issue
        for issue in issues:
            assert isinstance(issue, GrammarIssue), "Issue should be GrammarIssue instance"
            assert issue.type == GrammarIssueType.TENSE, \
                f"Issue type should be TENSE, got {issue.type}"
        
        # 4. Each issue should have required fields
        for issue in issues:
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
        
        # 5. Tense issues should be high priority
        for issue in issues:
            assert issue.severity == RecommendationPriority.HIGH, \
                f"Tense issues should be high priority, got {issue.severity}"
        
        # 6. Corrections should be different from issue text
        for issue in issues:
            issue_normalized = issue.issue_text.lower().strip()
            correction_normalized = issue.correction.lower().strip()
            
            assert issue_normalized != correction_normalized, \
                f"Correction should differ from issue text: '{issue.issue_text}' vs '{issue.correction}'"
        
        # 7. Location should reference experience section
        for issue in issues:
            location_lower = issue.location.lower()
            assert "experience" in location_lower or "achievement" in location_lower or "position" in location_lower, \
                f"Location should reference experience section, got: {issue.location}"
        
        # 8. Explanation should mention tense
        for issue in issues:
            explanation_lower = issue.explanation.lower()
            tense_indicators = ["tense", "past", "present", "previous", "current"]
            
            has_tense_indicator = any(indicator in explanation_lower for indicator in tense_indicators)
            assert has_tense_indicator, \
                f"Explanation should mention tense, got: {issue.explanation}"
    
    # 9. Issues should not have exact duplicates
    if len(issues) > 1:
        issue_signatures = []
        for issue in issues:
            signature = (issue.location, issue.issue_text.lower().strip())
            issue_signatures.append(signature)
        
        # Check for exact duplicates
        unique_signatures = set(issue_signatures)
        assert len(unique_signatures) == len(issue_signatures), \
            "Should not have exact duplicate issues"
    
    # 10. Verify tense checking logic for each experience
    for exp in cv_data.get("experience", []):
        is_current = exp.get("current", False)
        description = exp.get("description", "")
        
        if description:
            # Check if description has correct tense based on position status
            description_lower = description.lower()
            
            # Present tense indicators
            present_indicators = ["i develop", "i manage", "i lead", "i implement", "i create", "i build"]
            # Past tense indicators
            past_indicators = ["i developed", "i managed", "i led", "i implemented", "i created", "i built"]
            
            has_present = any(indicator in description_lower for indicator in present_indicators)
            has_past = any(indicator in description_lower for indicator in past_indicators)
            
            if is_current and has_past and not has_present:
                # Current position with past tense - should have issue
                if has_tense_errors:
                    exp_issues = [i for i in issues if exp.get("title", "") in i.location or exp.get("company", "") in i.location]
                    assert len(exp_issues) > 0, \
                        f"Should detect past tense in current position: {description}"
            
            elif not is_current and has_present and not has_past:
                # Past position with present tense - should have issue
                if has_tense_errors:
                    exp_issues = [i for i in issues if exp.get("title", "") in i.location or exp.get("company", "") in i.location]
                    assert len(exp_issues) > 0, \
                        f"Should detect present tense in past position: {description}"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_tense_consistency_past_position(
    config_and_provider
):
    """
    Property 40: Tense Consistency - Past Position
    
    For CVs with past positions using present tense, the service should
    detect and flag the tense inconsistency.
    
    Validates: Requirements 13.5
    """
    config, provider_type = config_and_provider
    
    # Test specific tense error patterns for past positions
    error_patterns = [
        ("I develop software applications", "I developed software applications"),
        ("I manage cross-functional teams", "I managed cross-functional teams"),
        ("I implement new features", "I implemented new features"),
        ("I create scalable solutions", "I created scalable solutions"),
        ("I build robust systems", "I built robust systems"),
    ]
    
    for error_text, correct_text in error_patterns:
        # Create CV with past position using present tense (error)
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
                "current": False,  # Past position
                "description": error_text,
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
        
        # Perform tense consistency check
        issues = await checker.check_tense_consistency(cv_data)
        
        # Property assertions
        # 1. Should detect the tense error
        assert len(issues) > 0, \
            f"Should detect present tense in past position: '{error_text}'"
        
        # 2. All issues should be tense issues
        for issue in issues:
            assert issue.type == GrammarIssueType.TENSE, \
                f"Issue should be tense type, got {issue.type}"
        
        # 3. Should reference the error
        found_error = False
        for issue in issues:
            issue_text_lower = issue.issue_text.lower()
            error_words = error_text.lower().split()
            
            # Check if key verb from error is in the issue
            if any(word in issue_text_lower for word in error_words if len(word) > 4):
                found_error = True
                
                # 4. Correction should be provided
                assert issue.correction, "Should provide correction"
                assert len(issue.correction.strip()) > 0, "Correction should not be empty"
                
                # 5. Correction should suggest past tense
                correction_lower = issue.correction.lower()
                # Should contain past tense verb or be different from present tense
                # The correction should be different from the error
                assert correction_lower != error_text.lower(), \
                    f"Correction should differ from error text, got: {issue.correction}"
                
                break
        
        assert found_error, \
            f"Should identify tense error '{error_text}' in issues"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_tense_consistency_current_position(
    config_and_provider
):
    """
    Property 40: Tense Consistency - Current Position
    
    For CVs with current positions using past tense, the service should
    detect and flag the tense inconsistency.
    
    Validates: Requirements 13.5
    """
    config, provider_type = config_and_provider
    
    # Test specific tense error patterns for current positions
    error_patterns = [
        ("I developed software applications", "I develop software applications"),
        ("I managed cross-functional teams", "I manage cross-functional teams"),
        ("I implemented new features", "I implement new features"),
        ("I created scalable solutions", "I create scalable solutions"),
        ("I built robust systems", "I build robust systems"),
    ]
    
    for error_text, correct_text in error_patterns:
        # Create CV with current position using past tense (error)
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
                "start_date": "2023-01",
                "end_date": None,
                "current": True,  # Current position
                "description": error_text,
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
        
        # Perform tense consistency check
        issues = await checker.check_tense_consistency(cv_data)
        
        # Property assertions
        # 1. Should detect the tense error
        assert len(issues) > 0, \
            f"Should detect past tense in current position: '{error_text}'"
        
        # 2. All issues should be tense issues
        for issue in issues:
            assert issue.type == GrammarIssueType.TENSE, \
                f"Issue should be tense type, got {issue.type}"
        
        # 3. Should reference the error
        found_error = False
        for issue in issues:
            issue_text_lower = issue.issue_text.lower()
            error_words = error_text.lower().split()
            
            # Check if key verb from error is in the issue
            if any(word in issue_text_lower for word in error_words if len(word) > 4):
                found_error = True
                
                # 4. Correction should be provided
                assert issue.correction, "Should provide correction"
                assert len(issue.correction.strip()) > 0, "Correction should not be empty"
                
                # 5. Correction should suggest present tense
                correction_lower = issue.correction.lower()
                # Should contain present tense verb or be different from past tense
                # The correction should be different from the error
                assert correction_lower != error_text.lower(), \
                    f"Correction should differ from error text, got: {issue.correction}"
                
                break
        
        assert found_error, \
            f"Should identify tense error '{error_text}' in issues"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_tense_consistency_correct_usage(
    config_and_provider
):
    """
    Property 40: Tense Consistency - Correct Usage
    
    For CVs with correct tense usage, the service should not flag
    false positives.
    
    Validates: Requirements 13.5
    """
    config, provider_type = config_and_provider
    
    # Test correct tense usage patterns
    test_cases = [
        # Past position with past tense (correct)
        {
            "current": False,
            "description": "I developed software applications and managed projects",
            "achievements": ["Delivered features ahead of schedule"]
        },
        # Current position with present tense (correct)
        {
            "current": True,
            "description": "I develop software applications and manage projects",
            "achievements": ["Delivering features ahead of schedule"]
        },
    ]
    
    for test_case in test_cases:
        # Create CV with correct tense usage
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
                "start_date": "2020-01" if not test_case["current"] else "2023-01",
                "end_date": "2023-12" if not test_case["current"] else None,
                "current": test_case["current"],
                "description": test_case["description"],
                "achievements": test_case["achievements"]
            }],
            "education": [],
            "skills": {"categories": []},
            "certifications": []
        }
        
        # Create mock provider
        mock_provider = MockLLMProvider(config, provider_type)
        
        # Create grammar checker
        checker = GrammarChecker(mock_provider)
        
        # Perform tense consistency check
        issues = await checker.check_tense_consistency(cv_data)
        
        # Property assertions
        # 1. Should have no or minimal issues for correct tense
        assert len(issues) == 0, \
            f"Correct tense usage should not trigger errors, got {len(issues)} for: {test_case['description']}"


@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_tense_consistency_multiple_positions(
    config_and_provider
):
    """
    Property 40: Tense Consistency - Multiple Positions
    
    For CVs with multiple positions, the service should correctly
    check tense for each position independently.
    
    Validates: Requirements 13.5
    """
    config, provider_type = config_and_provider
    
    # Create CV with multiple positions, some with errors
    cv_data = {
        "id": "test-cv-id",
        "personal_info": {
            "name": "Test User",
            "title": "Software Engineer"
        },
        "summary": "Experienced software engineer",
        "experience": [
            {
                "id": "exp-1",
                "title": "Senior Engineer",
                "company": "CurrentCorp",
                "start_date": "2023-01",
                "end_date": None,
                "current": True,
                "description": "I developed applications",  # Error: past tense in current position
                "achievements": []
            },
            {
                "id": "exp-2",
                "title": "Engineer",
                "company": "PreviousCorp",
                "start_date": "2020-01",
                "end_date": "2022-12",
                "current": False,
                "description": "I develop software",  # Error: present tense in past position
                "achievements": []
            },
            {
                "id": "exp-3",
                "title": "Junior Engineer",
                "company": "OldCorp",
                "start_date": "2018-01",
                "end_date": "2019-12",
                "current": False,
                "description": "I developed applications",  # Correct: past tense in past position
                "achievements": []
            }
        ],
        "education": [],
        "skills": {"categories": []},
        "certifications": []
    }
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create grammar checker
    checker = GrammarChecker(mock_provider)
    
    # Perform tense consistency check
    issues = await checker.check_tense_consistency(cv_data)
    
    # Property assertions
    # 1. Should detect issues in positions with errors
    assert len(issues) >= 2, \
        f"Should detect tense errors in multiple positions, got {len(issues)}"
    
    # 2. Should check each position independently
    # Check that issues reference different positions
    locations = [issue.location for issue in issues]
    unique_positions = set()
    
    for location in locations:
        if "CurrentCorp" in location or "exp-1" in location:
            unique_positions.add("exp-1")
        elif "PreviousCorp" in location or "exp-2" in location:
            unique_positions.add("exp-2")
        elif "OldCorp" in location or "exp-3" in location:
            unique_positions.add("exp-3")
    
    # Should have issues from at least 2 different positions
    assert len(unique_positions) >= 2, \
        f"Should detect issues in multiple positions, found in: {unique_positions}"
    
    # 3. Should not flag the correct position (exp-3)
    correct_position_issues = [i for i in issues if "OldCorp" in i.location or "Junior Engineer" in i.location]
    assert len(correct_position_issues) == 0, \
        "Should not flag position with correct tense usage"
