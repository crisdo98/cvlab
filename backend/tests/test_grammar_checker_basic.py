"""
Basic tests for Grammar Checker

Tests the core functionality of the grammar checker service including
grammar error detection, passive voice detection, tense consistency,
sentence complexity analysis, and style consistency checking.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.llm.grammar_checker import GrammarChecker, GrammarCheckerFactory
from app.llm.providers.base import BaseLLMProvider, LLMResponse, LLMConfig
from app.models.llm_models import (
    GrammarCheckRequest,
    GrammarCheckResult,
    GrammarIssue,
    GrammarIssueType,
    RecommendationPriority
)


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider for testing."""
    provider = MagicMock(spec=BaseLLMProvider)
    provider.config = LLMConfig(
        provider="openai",
        model="gpt-4",
        temperature=0.7,
        max_tokens=1000,
        enabled=True
    )
    provider.get_provider_name.return_value = "openai"
    provider.is_enabled.return_value = True
    return provider


@pytest.fixture
def sample_cv_data():
    """Sample CV data for testing."""
    return {
        "id": "test-cv-123",
        "personal_info": {
            "name": "John Doe",
            "title": "Software Engineer"
        },
        "summary": "I am a experienced software engineer with 5 years of experience.",
        "experience": [
            {
                "title": "Senior Engineer",
                "company": "TechCorp",
                "current": False,
                "description": "I develop software applications and leads team meetings.",
                "achievements": [
                    "The project was completed ahead of schedule by me",
                    "Performance improvements was implemented"
                ]
            },
            {
                "title": "Software Developer",
                "company": "StartupCo",
                "current": True,
                "description": "I developed web applications using React and Node.js.",
                "achievements": [
                    "Built new features for the platform"
                ]
            }
        ],
        "education": [
            {
                "degree": "BS Computer Science",
                "institution": "University",
                "description": "Studied computer science and learned programming."
            }
        ],
        "skills": {
            "categories": [
                {
                    "name": "Programming",
                    "skills": ["Python", "JavaScript", "Java"]
                }
            ]
        }
    }


@pytest.mark.asyncio
async def test_grammar_checker_initialization(mock_llm_provider):
    """Test grammar checker initialization."""
    checker = GrammarChecker(mock_llm_provider)
    
    assert checker.llm_provider == mock_llm_provider
    assert checker.GRAMMAR_CHECK_SYSTEM_PROMPT is not None


@pytest.mark.asyncio
async def test_check_grammar_with_issues(mock_llm_provider, sample_cv_data):
    """Test grammar checking that finds issues."""
    # Mock LLM response with grammar issues
    mock_response = LLMResponse(
        content="""LOCATION: Summary
ISSUE_TYPE: grammar
ISSUE_TEXT: I am a experienced software engineer
CORRECTION: I am an experienced software engineer
EXPLANATION: Use 'an' before words starting with vowel sounds
SEVERITY: high
---
LOCATION: Experience: Senior Engineer at TechCorp
ISSUE_TYPE: tense
ISSUE_TEXT: I develop software applications and leads team meetings
CORRECTION: I developed software applications and led team meetings
EXPLANATION: Past tense should be used for previous positions
SEVERITY: high
---
LOCATION: Experience: Senior Engineer at TechCorp - Achievement 1
ISSUE_TYPE: passive_voice
ISSUE_TEXT: The project was completed ahead of schedule by me
CORRECTION: I completed the project ahead of schedule
EXPLANATION: Active voice is more direct and professional
SEVERITY: medium""",
        model="gpt-4",
        provider="openai",
        usage={"prompt_tokens": 100, "completion_tokens": 200}
    )
    
    mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)
    
    checker = GrammarChecker(mock_llm_provider)
    request = GrammarCheckRequest(
        cv_id="test-cv-123",
        cv_data=sample_cv_data
    )
    
    result = await checker.check_grammar(request)
    
    assert isinstance(result, GrammarCheckResult)
    assert result.cv_id == "test-cv-123"
    assert len(result.issues) == 3
    assert result.model == "gpt-4"
    assert result.provider == "openai"
    
    # Check first issue
    assert result.issues[0].type == GrammarIssueType.GRAMMAR
    assert "experienced" in result.issues[0].issue_text
    assert result.issues[0].severity == RecommendationPriority.HIGH
    
    # Check second issue
    assert result.issues[1].type == GrammarIssueType.TENSE
    assert "develop" in result.issues[1].issue_text
    
    # Check third issue
    assert result.issues[2].type == GrammarIssueType.PASSIVE_VOICE
    assert "completed" in result.issues[2].issue_text


@pytest.mark.asyncio
async def test_check_grammar_no_issues(mock_llm_provider, sample_cv_data):
    """Test grammar checking when no issues are found."""
    mock_response = LLMResponse(
        content="NO_ISSUES_FOUND",
        model="gpt-4",
        provider="openai",
        usage={"prompt_tokens": 100, "completion_tokens": 10}
    )
    
    mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)
    
    checker = GrammarChecker(mock_llm_provider)
    request = GrammarCheckRequest(
        cv_id="test-cv-123",
        cv_data=sample_cv_data
    )
    
    result = await checker.check_grammar(request)
    
    assert isinstance(result, GrammarCheckResult)
    assert len(result.issues) == 0
    assert "Excellent" in result.overall_quality


@pytest.mark.asyncio
async def test_check_passive_voice(mock_llm_provider):
    """Test passive voice detection."""
    mock_response = LLMResponse(
        content="""ISSUE: The application was developed by the team
CORRECTION: The team developed the application
EXPLANATION: Active voice is more direct and shows clear ownership
---
ISSUE: Improvements were made to the system
CORRECTION: I made improvements to the system
EXPLANATION: Active voice clarifies who performed the action""",
        model="gpt-4",
        provider="openai",
        usage={"prompt_tokens": 50, "completion_tokens": 100}
    )
    
    mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)
    
    checker = GrammarChecker(mock_llm_provider)
    text = "The application was developed by the team. Improvements were made to the system."
    
    issues = await checker.check_passive_voice(text, "Experience section")
    
    assert len(issues) == 2
    assert all(issue.type == GrammarIssueType.PASSIVE_VOICE for issue in issues)
    assert issues[0].location == "Experience section"
    assert "developed" in issues[0].issue_text


@pytest.mark.asyncio
async def test_check_passive_voice_none_found(mock_llm_provider):
    """Test passive voice detection when none found."""
    mock_response = LLMResponse(
        content="NO_ISSUES_FOUND",
        model="gpt-4",
        provider="openai",
        usage={"prompt_tokens": 50, "completion_tokens": 10}
    )
    
    mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)
    
    checker = GrammarChecker(mock_llm_provider)
    text = "I developed the application. The team implemented new features."
    
    issues = await checker.check_passive_voice(text, "Experience section")
    
    assert len(issues) == 0


@pytest.mark.asyncio
async def test_check_tense_consistency(mock_llm_provider, sample_cv_data):
    """Test tense consistency checking."""
    # Mock response for past tense check (previous position)
    past_tense_response = LLMResponse(
        content="""ISSUE: I develop software applications
CORRECTION: I developed software applications
EXPLANATION: Past tense should be used for previous positions
---
ISSUE: leads team meetings
CORRECTION: led team meetings
EXPLANATION: Past tense should be used for previous positions""",
        model="gpt-4",
        provider="openai",
        usage={"prompt_tokens": 50, "completion_tokens": 80}
    )
    
    # Mock response for present tense check (current position)
    present_tense_response = LLMResponse(
        content="NO_ISSUES_FOUND",
        model="gpt-4",
        provider="openai",
        usage={"prompt_tokens": 50, "completion_tokens": 10}
    )
    
    # Set up mock to return different responses
    # Need enough responses for: description + 2 achievements for past position, description + 1 achievement for current position
    mock_llm_provider.generate_completion = AsyncMock(
        side_effect=[
            past_tense_response,  # Past position description
            past_tense_response,  # Past position achievement 1
            past_tense_response,  # Past position achievement 2
            present_tense_response,  # Current position description
            present_tense_response   # Current position achievement 1
        ]
    )
    
    checker = GrammarChecker(mock_llm_provider)
    issues = await checker.check_tense_consistency(sample_cv_data)
    
    # Should find tense issues in the past position
    assert len(issues) >= 2
    assert all(issue.type == GrammarIssueType.TENSE for issue in issues)
    assert all(issue.severity == RecommendationPriority.HIGH for issue in issues)


@pytest.mark.asyncio
async def test_check_sentence_complexity(mock_llm_provider):
    """Test sentence complexity analysis."""
    mock_response = LLMResponse(
        content="""ISSUE: I was responsible for developing, testing, and deploying complex software applications using multiple programming languages and frameworks while also mentoring junior developers and participating in code reviews.
CORRECTION: I developed, tested, and deployed complex software applications using multiple programming languages. I also mentored junior developers and participated in code reviews.
EXPLANATION: Breaking the long sentence into two shorter sentences improves clarity and readability""",
        model="gpt-4",
        provider="openai",
        usage={"prompt_tokens": 100, "completion_tokens": 150}
    )
    
    mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)
    
    checker = GrammarChecker(mock_llm_provider)
    text = "I was responsible for developing, testing, and deploying complex software applications using multiple programming languages and frameworks while also mentoring junior developers and participating in code reviews."
    
    issues = await checker.check_sentence_complexity(text, "Experience section")
    
    assert len(issues) == 1
    assert issues[0].type == GrammarIssueType.CLARITY
    assert issues[0].severity == RecommendationPriority.MEDIUM
    assert "shorter sentences" in issues[0].explanation.lower() or "clarity" in issues[0].explanation.lower()


@pytest.mark.asyncio
async def test_check_style_consistency(mock_llm_provider, sample_cv_data):
    """Test style consistency checking."""
    mock_response = LLMResponse(
        content="""ISSUE: Inconsistent use of first person
EXAMPLES: "I am a experienced software engineer" vs "The project was completed"
CORRECTION: Use consistent first person throughout: "I am an experienced software engineer" and "I completed the project"
EXPLANATION: Consistency in perspective makes the CV more professional and easier to read
---
ISSUE: Mixing of tenses in similar sections
EXAMPLES: "I develop" (present) and "I developed" (past) for past positions
CORRECTION: Use past tense consistently for all previous positions
EXPLANATION: Tense consistency is crucial for professional CVs""",
        model="gpt-4",
        provider="openai",
        usage={"prompt_tokens": 200, "completion_tokens": 200}
    )
    
    mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)
    
    checker = GrammarChecker(mock_llm_provider)
    issues = await checker.check_style_consistency(sample_cv_data)
    
    assert len(issues) == 2
    assert all(issue.type == GrammarIssueType.STYLE for issue in issues)
    assert "Inconsistent" in issues[0].issue_text


@pytest.mark.asyncio
async def test_extract_cv_text(mock_llm_provider, sample_cv_data):
    """Test CV text extraction."""
    checker = GrammarChecker(mock_llm_provider)
    text = checker._extract_cv_text(sample_cv_data)
    
    assert "John Doe" in text
    assert "Software Engineer" in text
    assert "experienced software engineer" in text
    assert "TechCorp" in text
    assert "Python" in text


@pytest.mark.asyncio
async def test_assess_overall_quality_excellent(mock_llm_provider):
    """Test overall quality assessment with no issues."""
    checker = GrammarChecker(mock_llm_provider)
    quality = checker._assess_overall_quality([])
    
    assert "Excellent" in quality
    assert "No grammar" in quality


@pytest.mark.asyncio
async def test_assess_overall_quality_needs_improvement(mock_llm_provider):
    """Test overall quality assessment with many high priority issues."""
    checker = GrammarChecker(mock_llm_provider)
    
    issues = [
        GrammarIssue(
            type=GrammarIssueType.GRAMMAR,
            location="Test",
            issue_text="test",
            correction="test",
            explanation="test",
            severity=RecommendationPriority.HIGH
        )
        for _ in range(6)
    ]
    
    quality = checker._assess_overall_quality(issues)
    
    assert "Needs Improvement" in quality
    assert "6 critical" in quality


@pytest.mark.asyncio
async def test_grammar_checker_factory(mock_llm_provider):
    """Test grammar checker factory."""
    checker = GrammarCheckerFactory.create_checker(mock_llm_provider)
    
    assert isinstance(checker, GrammarChecker)
    assert checker.llm_provider == mock_llm_provider


@pytest.mark.asyncio
async def test_grammar_checker_factory_with_test(mock_llm_provider):
    """Test grammar checker factory with connection test."""
    mock_llm_provider.test_connection = AsyncMock()
    
    checker = await GrammarCheckerFactory.create_and_test_checker(mock_llm_provider)
    
    assert isinstance(checker, GrammarChecker)
    mock_llm_provider.test_connection.assert_called_once()


@pytest.mark.asyncio
async def test_get_provider_info(mock_llm_provider):
    """Test getting provider information."""
    checker = GrammarChecker(mock_llm_provider)
    info = checker.get_provider_info()
    
    assert info["provider"] == "openai"
    assert info["enabled"] == "True"
    assert info["model"] == "gpt-4"


@pytest.mark.asyncio
async def test_map_issue_type(mock_llm_provider):
    """Test issue type mapping."""
    checker = GrammarChecker(mock_llm_provider)
    
    assert checker._map_issue_type("grammar") == GrammarIssueType.GRAMMAR
    assert checker._map_issue_type("passive_voice") == GrammarIssueType.PASSIVE_VOICE
    assert checker._map_issue_type("passive voice") == GrammarIssueType.PASSIVE_VOICE
    assert checker._map_issue_type("tense") == GrammarIssueType.TENSE
    assert checker._map_issue_type("unknown") == GrammarIssueType.GRAMMAR  # Default


@pytest.mark.asyncio
async def test_map_severity(mock_llm_provider):
    """Test severity mapping."""
    checker = GrammarChecker(mock_llm_provider)
    
    assert checker._map_severity("high") == RecommendationPriority.HIGH
    assert checker._map_severity("medium") == RecommendationPriority.MEDIUM
    assert checker._map_severity("low") == RecommendationPriority.LOW
    assert checker._map_severity("unknown") == RecommendationPriority.MEDIUM  # Default
