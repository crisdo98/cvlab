"""
Property-Based Tests for Passive Voice Detection

Feature: cv-web-app, Property 38: Passive Voice Detection
Validates: Requirements 13.3

Property 38: Passive Voice Detection
For any text containing passive voice constructions, the service should
detect them and suggest active voice alternatives.

This test validates that passive voice detection correctly identifies
passive voice constructions and provides appropriate active voice
alternatives across different CV content.
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
    """Mock LLM provider that simulates passive voice detection."""
    
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
        """Generate mock completion with passive voice detection results."""
        self._call_count += 1
        
        # Check if prompt contains passive voice patterns
        prompt_lower = prompt.lower()
        
        # Known passive voice patterns
        passive_voice_patterns = []
        
        # "was/were + past participle" patterns
        if "was developed" in prompt_lower:
            passive_voice_patterns.append({
                "issue": "was developed",
                "correction": "developed",
                "explanation": "Active voice is more direct and shows clear ownership of the action"
            })
        
        if "were implemented" in prompt_lower:
            passive_voice_patterns.append({
                "issue": "were implemented",
                "correction": "implemented",
                "explanation": "Active voice clarifies who performed the action and is more engaging"
            })
        
        if "was created" in prompt_lower:
            passive_voice_patterns.append({
                "issue": "was created",
                "correction": "created",
                "explanation": "Active voice makes the subject of the action clear and more impactful"
            })
        
        if "was managed" in prompt_lower:
            passive_voice_patterns.append({
                "issue": "was managed",
                "correction": "managed",
                "explanation": "Active voice demonstrates direct responsibility and leadership"
            })
        
        if "were designed" in prompt_lower:
            passive_voice_patterns.append({
                "issue": "were designed",
                "correction": "designed",
                "explanation": "Active voice shows initiative and ownership of the design process"
            })
        
        # "is/are + past participle" patterns
        if "is maintained" in prompt_lower:
            passive_voice_patterns.append({
                "issue": "is maintained",
                "correction": "maintain",
                "explanation": "Active voice in present tense shows ongoing responsibility"
            })
        
        if "are used" in prompt_lower:
            passive_voice_patterns.append({
                "issue": "are used",
                "correction": "use",
                "explanation": "Active voice demonstrates active engagement with tools and technologies"
            })
        
        # "has/have been + past participle" patterns
        if "has been completed" in prompt_lower:
            passive_voice_patterns.append({
                "issue": "has been completed",
                "correction": "completed",
                "explanation": "Active voice in present perfect shows accomplishment more directly"
            })
        
        if "have been achieved" in prompt_lower:
            passive_voice_patterns.append({
                "issue": "have been achieved",
                "correction": "achieved",
                "explanation": "Active voice emphasizes personal achievement and impact"
            })
        
        # "by [agent]" patterns (strong passive voice indicators)
        if "by the team" in prompt_lower or "by me" in prompt_lower or "by our group" in prompt_lower:
            # Find the passive construction before "by"
            if "was completed by" in prompt_lower:
                passive_voice_patterns.append({
                    "issue": "was completed by the team",
                    "correction": "the team completed" if "by the team" in prompt_lower else "I completed",
                    "explanation": "Active voice with the agent as subject is more direct and professional"
                })
            elif "were delivered by" in prompt_lower:
                passive_voice_patterns.append({
                    "issue": "were delivered by me",
                    "correction": "I delivered",
                    "explanation": "Active voice demonstrates personal responsibility and achievement"
                })
            elif "was led by" in prompt_lower:
                passive_voice_patterns.append({
                    "issue": "was led by me",
                    "correction": "I led",
                    "explanation": "Active voice shows leadership more powerfully"
                })
        
        # "being + past participle" patterns
        if "being developed" in prompt_lower:
            passive_voice_patterns.append({
                "issue": "being developed",
                "correction": "developing",
                "explanation": "Active voice in progressive form shows ongoing action more clearly"
            })
        
        # "been + past participle" patterns
        if "been improved" in prompt_lower:
            passive_voice_patterns.append({
                "issue": "been improved",
                "correction": "improved",
                "explanation": "Active voice makes the improvement more tangible and attributable"
            })
        
        # Generate response based on detected patterns
        if passive_voice_patterns:
            content_parts = []
            for pattern in passive_voice_patterns:
                content_parts.append(f"""ISSUE: {pattern['issue']}
CORRECTION: {pattern['correction']}
EXPLANATION: {pattern['explanation']}
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
def passive_voice_text_strategy(draw):
    """Generate text with passive voice constructions."""
    # Passive voice patterns
    passive_patterns = [
        "The application was developed by the team",
        "New features were implemented in the system",
        "The database was created to store user data",
        "The project was managed effectively",
        "Solutions were designed to meet requirements",
        "The codebase is maintained regularly",
        "Best practices are used throughout",
        "The milestone has been completed successfully",
        "Goals have been achieved ahead of schedule",
        "The project was completed by me ahead of schedule",
        "Results were delivered by our group on time",
        "The initiative was led by me to improve processes",
        "The feature is being developed currently",
        "Performance has been improved significantly"
    ]
    
    # Active voice alternatives (should NOT trigger passive voice detection)
    active_patterns = [
        "I developed the application",
        "The team implemented new features",
        "I created the database to store user data",
        "I managed the project effectively",
        "I designed solutions to meet requirements",
        "I maintain the codebase regularly",
        "I use best practices throughout",
        "I completed the milestone successfully",
        "I achieved goals ahead of schedule",
        "I delivered results on time",
        "I led the initiative to improve processes",
        "I am developing the feature currently",
        "I improved performance significantly"
    ]
    
    # Decide if this text should have passive voice
    has_passive = draw(st.booleans())
    
    if has_passive:
        # Select 1-3 passive voice patterns
        num_patterns = draw(st.integers(min_value=1, max_value=3))
        selected_patterns = draw(st.lists(
            st.sampled_from(passive_patterns),
            min_size=num_patterns,
            max_size=num_patterns,
            unique=True
        ))
        text = ". ".join(selected_patterns) + "."
    else:
        # Select 1-3 active voice patterns
        num_patterns = draw(st.integers(min_value=1, max_value=3))
        selected_patterns = draw(st.lists(
            st.sampled_from(active_patterns),
            min_size=num_patterns,
            max_size=num_patterns,
            unique=True
        ))
        text = ". ".join(selected_patterns) + "."
    
    return text, has_passive


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
    text_and_flag=passive_voice_text_strategy()
)
@pytest.mark.asyncio
async def test_property_passive_voice_detection(
    config_and_provider,
    text_and_flag
):
    """
    Property 38: Passive Voice Detection
    
    For any text containing passive voice constructions, the service should
    detect them and suggest active voice alternatives.
    
    Validates: Requirements 13.3
    """
    config, provider_type = config_and_provider
    text, has_passive = text_and_flag
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create grammar checker
    checker = GrammarChecker(mock_provider)
    
    # Check for passive voice
    issues = await checker.check_passive_voice(text, "Test Section")
    
    # Property assertions
    # 1. Result should not be None
    assert issues is not None, "Passive voice check result should not be None"
    assert isinstance(issues, list), "Result should be a list"
    
    # 2. If text has passive voice, should detect it
    if has_passive:
        assert len(issues) > 0, \
            f"Text with passive voice should have detected issues: {text}"
        
        # 3. Each issue should be marked as passive voice type
        for issue in issues:
            assert isinstance(issue, GrammarIssue), "Issue should be GrammarIssue instance"
            assert issue.type == GrammarIssueType.PASSIVE_VOICE, \
                f"Issue type should be PASSIVE_VOICE, got {issue.type}"
        
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
        
        # 5. Corrections should be different from issue text
        for issue in issues:
            issue_normalized = issue.issue_text.lower().strip()
            correction_normalized = issue.correction.lower().strip()
            
            assert issue_normalized != correction_normalized, \
                f"Correction should differ from issue text: '{issue.issue_text}' vs '{issue.correction}'"
        
        # 6. Corrections should suggest active voice
        for issue in issues:
            correction_lower = issue.correction.lower()
            
            # Active voice typically removes "was", "were", "been", "being"
            passive_indicators = ["was ", "were ", "been ", "being ", "is ", "are "]
            has_passive_indicator = any(indicator in issue.issue_text.lower() for indicator in passive_indicators)
            
            if has_passive_indicator:
                # Correction should have fewer or no passive indicators
                correction_passive_count = sum(1 for indicator in passive_indicators if indicator in correction_lower)
                issue_passive_count = sum(1 for indicator in passive_indicators if indicator in issue.issue_text.lower())
                
                assert correction_passive_count <= issue_passive_count, \
                    f"Active voice correction should reduce passive indicators: '{issue.issue_text}' -> '{issue.correction}'"
        
        # 7. Explanation should mention active voice or related concepts
        for issue in issues:
            explanation_lower = issue.explanation.lower()
            active_voice_indicators = [
                "active", "direct", "clear", "ownership", "responsibility",
                "subject", "action", "agent", "shows", "demonstrates"
            ]
            
            has_active_indicator = any(
                indicator in explanation_lower for indicator in active_voice_indicators
            )
            assert has_active_indicator, \
                f"Explanation should mention active voice benefits, got: {issue.explanation}"
        
        # 8. Severity should be medium or low (passive voice is style, not grammar error)
        for issue in issues:
            assert issue.severity in [
                RecommendationPriority.MEDIUM,
                RecommendationPriority.LOW
            ], f"Passive voice should be medium or low priority, got {issue.severity}"
    
    # 9. If text is active voice, should not detect passive voice issues
    else:
        # Should have no issues or very few
        assert len(issues) <= 1, \
            f"Active voice text should not trigger many passive voice detections, got {len(issues)} for: {text}"
    
    # 10. Issues should not have exact duplicates
    if len(issues) > 1:
        issue_signatures = []
        for issue in issues:
            signature = (issue.issue_text.lower().strip(), issue.correction.lower().strip())
            issue_signatures.append(signature)
        
        # Check for exact duplicates
        unique_signatures = set(issue_signatures)
        assert len(unique_signatures) == len(issue_signatures), \
            "Should not have exact duplicate passive voice issues"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_passive_voice_detection_specific_patterns(
    config_and_provider
):
    """
    Property 38: Passive Voice Detection - Specific Patterns
    
    For text with known specific passive voice patterns, the service should
    detect and provide active voice alternatives for each pattern.
    
    Validates: Requirements 13.3
    """
    config, provider_type = config_and_provider
    
    # Test specific passive voice patterns
    passive_patterns = [
        ("The application was developed by the team", "active voice"),
        ("New features were implemented", "active voice"),
        ("The database was created", "active voice"),
        ("The project was managed", "active voice"),
        ("Solutions were designed", "active voice"),
        ("The codebase is maintained", "active voice"),
        ("The milestone has been completed", "active voice"),
        ("The project was completed by me", "active voice with agent"),
        ("Results were delivered by our group", "active voice with agent"),
    ]
    
    for passive_text, pattern_type in passive_patterns:
        # Create mock provider
        mock_provider = MockLLMProvider(config, provider_type)
        
        # Create grammar checker
        checker = GrammarChecker(mock_provider)
        
        # Check for passive voice
        issues = await checker.check_passive_voice(passive_text, "Test Section")
        
        # Property assertions
        # 1. Should detect the passive voice
        assert len(issues) > 0, \
            f"Should detect {pattern_type}: '{passive_text}'"
        
        # 2. At least one issue should reference the passive construction
        found_passive = False
        for issue in issues:
            issue_text_lower = issue.issue_text.lower()
            passive_text_lower = passive_text.lower()
            
            # Check if key words from passive text are in the issue
            passive_words = [w for w in passive_text_lower.split() if len(w) > 3]
            if any(word in issue_text_lower for word in passive_words[:3]):  # Check first 3 significant words
                found_passive = True
                
                # 3. Should be marked as passive voice
                assert issue.type == GrammarIssueType.PASSIVE_VOICE, \
                    f"Should be marked as PASSIVE_VOICE for {pattern_type}"
                
                # 4. Correction should be provided
                assert issue.correction, f"Should provide correction for {pattern_type}"
                assert len(issue.correction.strip()) > 0, "Correction should not be empty"
                
                # 5. Correction should be different from passive text
                assert issue.issue_text.lower().strip() != issue.correction.lower().strip(), \
                    f"Correction should differ from passive text for {pattern_type}"
                
                # 6. Explanation should mention active voice
                explanation_lower = issue.explanation.lower()
                assert "active" in explanation_lower or "direct" in explanation_lower, \
                    f"Explanation should mention active voice for {pattern_type}"
                
                break
        
        assert found_passive, \
            f"Should identify {pattern_type} '{passive_text}' in issues"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_passive_voice_detection_no_false_positives(
    config_and_provider
):
    """
    Property 38: Passive Voice Detection - No False Positives
    
    For text with active voice, the service should not incorrectly
    flag it as passive voice.
    
    Validates: Requirements 13.3
    """
    config, provider_type = config_and_provider
    
    # Active voice text that should NOT trigger passive voice detection
    active_texts = [
        "I developed the application using modern frameworks",
        "The team implemented new features for the platform",
        "I created the database to store user data",
        "I managed the project effectively and delivered on time",
        "I designed solutions to meet customer requirements",
        "I maintain the codebase regularly with updates",
        "I use best practices throughout the development process",
        "I completed the milestone successfully ahead of schedule",
        "I achieved goals and exceeded expectations",
        "I delivered results on time and within budget",
        "I led the initiative to improve team processes",
        "I am developing the feature currently",
        "I improved performance significantly through optimization"
    ]
    
    for active_text in active_texts:
        # Create mock provider
        mock_provider = MockLLMProvider(config, provider_type)
        
        # Create grammar checker
        checker = GrammarChecker(mock_provider)
        
        # Check for passive voice
        issues = await checker.check_passive_voice(active_text, "Test Section")
        
        # Property assertions
        # 1. Should have no or minimal issues for active voice
        assert len(issues) == 0, \
            f"Active voice should not trigger passive voice detection, got {len(issues)} for: {active_text}"


@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_passive_voice_detection_consistency(
    config_and_provider
):
    """
    Property 38: Passive Voice Detection - Consistency
    
    For the same text with passive voice, detection should be consistent
    across multiple runs.
    
    Validates: Requirements 13.3
    """
    config, provider_type = config_and_provider
    
    # Text with multiple passive voice constructions
    text = """The application was developed by the team over six months.
    New features were implemented to improve user experience.
    The database was created to store customer information.
    Results were delivered by our group ahead of schedule."""
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create grammar checker
    checker = GrammarChecker(mock_provider)
    
    # Run passive voice check twice
    issues1 = await checker.check_passive_voice(text, "Test Section")
    issues2 = await checker.check_passive_voice(text, "Test Section")
    
    # Property assertions
    # 1. Both should detect passive voice
    assert len(issues1) > 0, "First run should detect passive voice"
    assert len(issues2) > 0, "Second run should detect passive voice"
    
    # 2. Should detect same number of issues
    assert len(issues1) == len(issues2), \
        f"Should detect same number of issues (run1: {len(issues1)}, run2: {len(issues2)})"
    
    # 3. All issues should be passive voice type
    for issue in issues1 + issues2:
        assert issue.type == GrammarIssueType.PASSIVE_VOICE, \
            "All issues should be PASSIVE_VOICE type"
    
    # 4. Should identify same passive constructions
    issues1_texts = set(issue.issue_text.lower().strip() for issue in issues1)
    issues2_texts = set(issue.issue_text.lower().strip() for issue in issues2)
    
    assert issues1_texts == issues2_texts, \
        "Should consistently detect same passive voice constructions"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_passive_voice_detection_correction_quality(
    config_and_provider
):
    """
    Property 38: Passive Voice Detection - Correction Quality
    
    For passive voice constructions, the suggested active voice alternatives
    should be grammatically correct and more direct.
    
    Validates: Requirements 13.3
    """
    config, provider_type = config_and_provider
    
    # Passive voice texts with expected characteristics in corrections
    test_cases = [
        {
            "text": "The application was developed by the team",
            "passive_phrase": "was developed",
            "should_contain_in_correction": ["develop"],
            "should_not_contain": ["was"]
        },
        {
            "text": "New features were implemented in the system",
            "passive_phrase": "were implemented",
            "should_contain_in_correction": ["implement"],
            "should_not_contain": ["were"]
        },
        {
            "text": "The project was completed by me ahead of schedule",
            "passive_phrase": "was completed by me",
            "should_contain_in_correction": ["complet"],
            "should_not_contain": ["was", "by me"]
        }
    ]
    
    for test_case in test_cases:
        # Create mock provider
        mock_provider = MockLLMProvider(config, provider_type)
        
        # Create grammar checker
        checker = GrammarChecker(mock_provider)
        
        # Check for passive voice
        issues = await checker.check_passive_voice(test_case["text"], "Test Section")
        
        # Property assertions
        # 1. Should detect passive voice
        assert len(issues) > 0, \
            f"Should detect passive voice in: {test_case['text']}"
        
        # 2. Find the relevant issue
        relevant_issue = None
        for issue in issues:
            if test_case["passive_phrase"] in issue.issue_text.lower():
                relevant_issue = issue
                break
        
        if relevant_issue:
            correction_lower = relevant_issue.correction.lower()
            
            # 3. Correction should contain expected words
            for expected_word in test_case["should_contain_in_correction"]:
                assert expected_word in correction_lower, \
                    f"Correction should contain '{expected_word}': {relevant_issue.correction}"
            
            # 4. Correction should not contain passive indicators
            for unwanted_word in test_case["should_not_contain"]:
                # Allow these words if they're part of a larger word
                if f" {unwanted_word} " in f" {correction_lower} ":
                    assert False, \
                        f"Correction should not contain '{unwanted_word}': {relevant_issue.correction}"
            
            # 5. Correction should be shorter or same length (active voice is typically more concise)
            correction_word_count = len(relevant_issue.correction.split())
            issue_word_count = len(relevant_issue.issue_text.split())
            
            assert correction_word_count <= issue_word_count + 2, \
                f"Active voice correction should not be significantly longer: {relevant_issue.issue_text} -> {relevant_issue.correction}"


@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_passive_voice_detection_explanation_quality(
    config_and_provider
):
    """
    Property 38: Passive Voice Detection - Explanation Quality
    
    For passive voice detections, explanations should clearly explain
    why active voice is better.
    
    Validates: Requirements 13.3
    """
    config, provider_type = config_and_provider
    
    # Text with passive voice
    text = "The application was developed by the team and features were implemented successfully"
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create grammar checker
    checker = GrammarChecker(mock_provider)
    
    # Check for passive voice
    issues = await checker.check_passive_voice(text, "Test Section")
    
    # Property assertions
    # 1. Should detect passive voice
    assert len(issues) > 0, "Should detect passive voice"
    
    # 2. Each explanation should be meaningful
    for issue in issues:
        explanation = issue.explanation
        explanation_lower = explanation.lower()
        
        # 3. Explanation should not be empty or too short
        assert len(explanation.strip()) >= 20, \
            f"Explanation should be meaningful, got: {explanation}"
        
        # 4. Explanation should mention benefits of active voice
        active_voice_benefits = [
            "active", "direct", "clear", "ownership", "responsibility",
            "shows", "demonstrates", "clarifies", "emphasizes", "powerful",
            "professional", "engaging", "impact", "subject", "action"
        ]
        
        has_benefit_mention = any(benefit in explanation_lower for benefit in active_voice_benefits)
        assert has_benefit_mention, \
            f"Explanation should mention active voice benefits, got: {explanation}"
        
        # 5. Explanation should be professional and constructive
        negative_words = ["bad", "wrong", "terrible", "awful", "stupid"]
        has_negative = any(word in explanation_lower for word in negative_words)
        assert not has_negative, \
            f"Explanation should be constructive, not negative, got: {explanation}"
