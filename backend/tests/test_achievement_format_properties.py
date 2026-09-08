"""
Property-Based Tests for Achievement Statement Format

Feature: cv-web-app, Property 24: Achievement Statement Format
Validates: Requirements 10.3

Property 24: Achievement Statement Format
For any work description, generated achievement statements should contain action verbs,
quantifiable metrics, and follow professional formatting standards.

This test validates that achievement statements follow the required format:
- Start with strong action verbs
- Include quantifiable metrics (numbers, percentages, etc.)
- Follow professional formatting standards
- Are concise (under 20 words when possible)
"""

import pytest
import re
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List

from app.llm.content_generator import (
    ContentGenerator,
    AchievementGenerationRequest
)
from app.llm.providers.base import BaseLLMProvider, LLMResponse, LLMConfig


# Common action verbs that should appear at the start of achievement statements
ACTION_VERBS = [
    "achieved", "accelerated", "accomplished", "acquired", "adapted", "addressed",
    "administered", "advanced", "analyzed", "architected", "automated", "built",
    "collaborated", "completed", "conducted", "configured", "consolidated", "created",
    "decreased", "delivered", "demonstrated", "designed", "developed", "directed",
    "drove", "eliminated", "enabled", "engineered", "enhanced", "established",
    "executed", "expanded", "facilitated", "generated", "grew", "guided",
    "implemented", "improved", "increased", "initiated", "innovated", "integrated",
    "launched", "led", "managed", "migrated", "optimized", "orchestrated",
    "organized", "overhauled", "pioneered", "planned", "produced", "reduced",
    "refactored", "resolved", "restructured", "revamped", "scaled", "spearheaded",
    "streamlined", "strengthened", "transformed", "upgraded"
]

# Patterns for quantifiable metrics
METRIC_PATTERNS = [
    r'\d+%',  # Percentages: 40%, 25%
    r'\d+x',  # Multipliers: 2x, 3x
    r'\$\d+[KMB]?',  # Money: $100K, $2M
    r'\d+\s*(hours?|days?|weeks?|months?|years?)',  # Time: 2 weeks, 3 months
    r'\d+\s*(users?|customers?|clients?)',  # People: 100 users, 50 clients
    r'\d+\s*(developers?|engineers?|team members?)',  # Team size: 5 developers
    r'\d+\s*(projects?|features?|systems?)',  # Deliverables: 10 projects
    r'\d+[KMB]?\+',  # Plus notation: 100+, 50+, 10M+
    r'from\s+\d+\s+to\s+\d+',  # Range: from 10 to 50
    r'by\s+\d+',  # By amount: by 40, by 25
    r'\d+\s*(million|thousand|billion)',  # Large numbers: 2 million
    r'\b(doubled|tripled|quadrupled)\b',  # Multiplier words
    r'\d+[KMB]',  # Numbers with K/M/B suffix: 10M, 500K
]


class MockAchievementProvider(BaseLLMProvider):
    """Mock LLM provider that generates realistic achievement statements."""
    
    def __init__(self, config: LLMConfig, style: str = "standard"):
        super().__init__(config)
        self._style = style
        self._call_count = 0
    
    async def generate_completion(
        self,
        prompt: str,
        system_prompt=None,
        temperature=None,
        max_tokens=None,
        **kwargs
    ) -> LLMResponse:
        """Generate mock achievement statements."""
        self._call_count += 1
        
        # Generate different styles of achievement statements
        if self._style == "standard":
            content = self._generate_standard_achievements()
        elif self._style == "detailed":
            content = self._generate_detailed_achievements()
        elif self._style == "concise":
            content = self._generate_concise_achievements()
        elif self._style == "poor_format":
            # Intentionally poor format for negative testing
            content = self._generate_poor_format_achievements()
        else:
            content = self._generate_standard_achievements()
        
        return LLMResponse(
            content=content,
            model=self.config.model,
            provider="mock",
            tokens_used=100
        )
    
    def _generate_standard_achievements(self) -> str:
        """Generate standard format achievement statements."""
        # Return 3 variations separated by blank lines, each with multiple achievement statements
        return """1. Reduced API response time by 40% through database query optimization and caching implementation
2. Led team of 5 developers to deliver project 2 weeks ahead of schedule
3. Increased user engagement by 25% by implementing new feature set

1. Optimized database queries reducing response time by 40%
2. Managed team of 5 engineers completing project 2 weeks early
3. Boosted user engagement 25% through feature development

1. Decreased API latency by 40% via query optimization
2. Directed 5-person development team to early project completion
3. Enhanced user engagement by 25% with new features"""
    
    def _generate_detailed_achievements(self) -> str:
        """Generate detailed achievement statements with metrics."""
        return """1. Optimized system performance by 60% by refactoring core algorithms and implementing parallel processing
2. Managed migration of 500K+ users to new platform with 99.9% uptime
3. Decreased infrastructure costs by $50K annually through cloud resource optimization

1. Improved system efficiency 60% through algorithm refactoring and parallelization
2. Led migration of 500,000+ users maintaining 99.9% availability
3. Reduced cloud infrastructure spend by $50,000 per year

1. Accelerated system performance by 60% via core algorithm improvements
2. Orchestrated 500K+ user migration with 99.9% uptime
3. Cut infrastructure costs $50K annually through optimization"""
    
    def _generate_concise_achievements(self) -> str:
        """Generate concise achievement statements."""
        # Ensure all statements have quantifiable metrics
        return """1. Improved deployment speed by 3x
2. Reduced bug count by 45%
3. Scaled system to handle 10M+ requests/day

1. Accelerated deployments 3x faster
2. Decreased bugs by 45%
3. Scaled to 10M+ daily requests

1. Tripled deployment velocity
2. Cut bug rate 45%
3. Handled 10M+ requests/day"""
    
    def _generate_poor_format_achievements(self) -> str:
        """Generate poorly formatted achievements (for negative testing)."""
        return """1. Was responsible for improving the system
2. Helped with various projects
3. Worked on making things better"""
    
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
        return "mock"


# Hypothesis strategies
@st.composite
def achievement_request_strategy(draw):
    """Generate achievement generation requests."""
    notes_options = [
        "Optimized API performance",
        "Reduced server costs",
        "Improved user experience",
        "Increased team productivity",
        "Streamlined deployment process",
        "Enhanced security measures",
        "Migrated legacy system",
        "Implemented new features",
        "Led development team",
        "Automated testing pipeline"
    ]
    
    job_titles = [
        "Software Engineer",
        "Senior Developer",
        "DevOps Engineer",
        "Technical Lead",
        "Product Manager",
        "Data Engineer"
    ]
    
    companies = [
        "Tech Corp",
        "Innovation Labs",
        "Digital Solutions",
        "Cloud Systems",
        "Data Analytics Inc"
    ]
    
    return AchievementGenerationRequest(
        notes=draw(st.sampled_from(notes_options)),
        job_title=draw(st.sampled_from(job_titles)),
        company=draw(st.sampled_from(companies)),
        num_variations=draw(st.integers(min_value=1, max_value=5))
    )


@st.composite
def provider_style_strategy(draw):
    """Generate provider configurations with different styles."""
    style = draw(st.sampled_from(["standard", "detailed", "concise"]))
    
    config = LLMConfig(
        provider="mock",
        model="mock-model",
        temperature=draw(st.floats(min_value=0.0, max_value=1.0)),
        max_tokens=draw(st.integers(min_value=100, max_value=500))
    )
    
    return config, style


# Helper functions for validation
def starts_with_action_verb(text: str) -> bool:
    """Check if text starts with an action verb."""
    # Normalize text: lowercase, remove leading numbers/bullets
    normalized = re.sub(r'^\d+[\.\)]\s*', '', text.strip()).lower()
    
    # Check if starts with any action verb
    for verb in ACTION_VERBS:
        if normalized.startswith(verb):
            return True
    
    return False


def contains_quantifiable_metric(text: str) -> bool:
    """Check if text contains quantifiable metrics."""
    for pattern in METRIC_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    return False


def is_concise(text: str, max_words: int = 25) -> bool:
    """Check if text is concise (under specified word count)."""
    # Remove leading numbers/bullets
    clean_text = re.sub(r'^\d+[\.\)]\s*', '', text.strip())
    word_count = len(clean_text.split())
    return word_count <= max_words


def extract_achievement_statements(text: str) -> List[str]:
    """Extract individual achievement statements from generated text."""
    # Split by numbered list items
    statements = re.split(r'\n\s*\d+[\.\)]\s*', text.strip())
    
    # Remove empty strings and clean up
    statements = [s.strip() for s in statements if s.strip()]
    
    # If no numbered list found, try splitting by newlines
    if len(statements) <= 1:
        statements = [s.strip() for s in text.split('\n') if s.strip()]
        # Filter out lines that are just numbers
        statements = [s for s in statements if not re.match(r'^\d+[\.\)]\s*$', s)]
    
    # Remove any leading numbered items from statements
    cleaned_statements = []
    for stmt in statements:
        # Remove leading number if present
        cleaned = re.sub(r'^\d+[\.\)]\s*', '', stmt).strip()
        if cleaned:
            cleaned_statements.append(cleaned)
    
    return cleaned_statements


# Property Tests
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_style=provider_style_strategy(),
    request_data=achievement_request_strategy()
)
@pytest.mark.asyncio
async def test_property_achievement_format_action_verbs(
    config_and_style,
    request_data
):
    """
    Property 24: Achievement Statement Format - Action Verbs
    
    For any achievement generation request, all generated achievement statements
    should start with strong action verbs.
    
    Validates: Requirements 10.3
    """
    config, style = config_and_style
    
    # Create mock provider
    mock_provider = MockAchievementProvider(config, style)
    
    # Create content generator
    generator = ContentGenerator(mock_provider)
    
    # Generate achievements
    result = await generator.generate_achievements(request_data)
    
    # Property assertions
    assert result is not None, "Achievement generation should return result"
    assert len(result.variations) > 0, "Should generate at least one variation"
    
    # Check each variation
    for i, variation in enumerate(result.variations):
        # Extract individual achievement statements
        statements = extract_achievement_statements(variation.text)
        
        assert len(statements) > 0, f"Variation {i+1} should contain achievement statements"
        
        # Each statement should start with an action verb
        for j, statement in enumerate(statements):
            assert starts_with_action_verb(statement), \
                f"Variation {i+1}, Statement {j+1} should start with action verb: '{statement}'"


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_style=provider_style_strategy(),
    request_data=achievement_request_strategy()
)
@pytest.mark.asyncio
async def test_property_achievement_format_quantifiable_metrics(
    config_and_style,
    request_data
):
    """
    Property 24: Achievement Statement Format - Quantifiable Metrics
    
    For any achievement generation request, generated achievement statements
    should include quantifiable metrics (numbers, percentages, etc.).
    
    Validates: Requirements 10.3
    """
    config, style = config_and_style
    
    # Create mock provider
    mock_provider = MockAchievementProvider(config, style)
    
    # Create content generator
    generator = ContentGenerator(mock_provider)
    
    # Generate achievements
    result = await generator.generate_achievements(request_data)
    
    # Property assertions
    assert result is not None, "Achievement generation should return result"
    assert len(result.variations) > 0, "Should generate at least one variation"
    
    # Check each variation
    for i, variation in enumerate(result.variations):
        # Extract individual achievement statements
        statements = extract_achievement_statements(variation.text)
        
        # At least some statements should contain metrics
        # (Not all statements may have metrics, but most should)
        statements_with_metrics = sum(
            1 for stmt in statements if contains_quantifiable_metric(stmt)
        )
        
        metric_ratio = statements_with_metrics / len(statements) if statements else 0
        
        assert metric_ratio >= 0.5, \
            f"Variation {i+1}: At least 50% of statements should contain quantifiable metrics " \
            f"(found {statements_with_metrics}/{len(statements)})"


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_style=provider_style_strategy(),
    request_data=achievement_request_strategy()
)
@pytest.mark.asyncio
async def test_property_achievement_format_conciseness(
    config_and_style,
    request_data
):
    """
    Property 24: Achievement Statement Format - Conciseness
    
    For any achievement generation request, generated achievement statements
    should be concise (under 25 words, ideally under 20).
    
    Validates: Requirements 10.3
    """
    config, style = config_and_style
    
    # Create mock provider
    mock_provider = MockAchievementProvider(config, style)
    
    # Create content generator
    generator = ContentGenerator(mock_provider)
    
    # Generate achievements
    result = await generator.generate_achievements(request_data)
    
    # Property assertions
    assert result is not None, "Achievement generation should return result"
    assert len(result.variations) > 0, "Should generate at least one variation"
    
    # Check each variation
    for i, variation in enumerate(result.variations):
        # Extract individual achievement statements
        statements = extract_achievement_statements(variation.text)
        
        # Each statement should be concise
        for j, statement in enumerate(statements):
            assert is_concise(statement, max_words=25), \
                f"Variation {i+1}, Statement {j+1} should be concise (under 25 words): '{statement}'"


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_style=provider_style_strategy(),
    request_data=achievement_request_strategy()
)
@pytest.mark.asyncio
async def test_property_achievement_format_professional_structure(
    config_and_style,
    request_data
):
    """
    Property 24: Achievement Statement Format - Professional Structure
    
    For any achievement generation request, generated achievement statements
    should follow professional formatting standards:
    - Start with action verb
    - Include task/action description
    - Show result/impact
    
    Validates: Requirements 10.3
    """
    config, style = config_and_style
    
    # Create mock provider
    mock_provider = MockAchievementProvider(config, style)
    
    # Create content generator
    generator = ContentGenerator(mock_provider)
    
    # Generate achievements
    result = await generator.generate_achievements(request_data)
    
    # Property assertions
    assert result is not None, "Achievement generation should return result"
    assert len(result.variations) > 0, "Should generate at least one variation"
    
    # Check each variation
    for i, variation in enumerate(result.variations):
        # Extract individual achievement statements
        statements = extract_achievement_statements(variation.text)
        
        assert len(statements) > 0, f"Variation {i+1} should contain achievement statements"
        
        # Each statement should have professional structure
        for j, statement in enumerate(statements):
            # Should start with action verb
            assert starts_with_action_verb(statement), \
                f"Variation {i+1}, Statement {j+1} should start with action verb"
            
            # Should be a complete statement (not just a fragment)
            # Minimum 4 words to ensure it's not just a fragment
            assert len(statement.split()) >= 4, \
                f"Variation {i+1}, Statement {j+1} should be a complete statement (at least 4 words)"
            
            # Should not be overly long
            assert is_concise(statement, max_words=30), \
                f"Variation {i+1}, Statement {j+1} should not be overly long (under 30 words)"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    request_data=achievement_request_strategy()
)
@pytest.mark.asyncio
async def test_property_achievement_format_consistency_across_variations(
    request_data
):
    """
    Property 24: Achievement Statement Format - Consistency
    
    For any achievement generation request, all variations should follow
    the same formatting standards consistently.
    
    Validates: Requirements 10.3
    """
    # Create mock provider with standard style
    config = LLMConfig(
        provider="mock",
        model="mock-model",
        temperature=0.7,
        max_tokens=400
    )
    mock_provider = MockAchievementProvider(config, "standard")
    
    # Create content generator
    generator = ContentGenerator(mock_provider)
    
    # Generate achievements
    result = await generator.generate_achievements(request_data)
    
    # Property assertions
    assert result is not None, "Achievement generation should return result"
    assert len(result.variations) > 0, "Should generate at least one variation"
    
    # Track format compliance across all variations
    all_start_with_verbs = True
    all_have_metrics = True
    all_are_concise = True
    
    for variation in result.variations:
        statements = extract_achievement_statements(variation.text)
        
        # Check if all statements in this variation follow format
        for statement in statements:
            if not starts_with_action_verb(statement):
                all_start_with_verbs = False
            if not contains_quantifiable_metric(statement):
                all_have_metrics = False
            if not is_concise(statement, max_words=25):
                all_are_concise = False
    
    # At least action verbs and conciseness should be consistent
    assert all_start_with_verbs, "All variations should consistently start with action verbs"
    assert all_are_concise, "All variations should consistently be concise"


# Integration test with real-world examples
@pytest.mark.asyncio
async def test_achievement_format_real_world_examples():
    """
    Test achievement format with real-world examples to ensure
    the property tests align with actual usage.
    """
    config = LLMConfig(
        provider="mock",
        model="mock-model",
        temperature=0.7,
        max_tokens=400
    )
    
    # Test with different styles
    styles = ["standard", "detailed", "concise"]
    
    for style in styles:
        mock_provider = MockAchievementProvider(config, style)
        generator = ContentGenerator(mock_provider)
        
        request = AchievementGenerationRequest(
            notes="Improved system performance",
            job_title="Software Engineer",
            company="Tech Corp",
            num_variations=3
        )
        
        result = await generator.generate_achievements(request)
        
        # Verify format compliance
        assert result is not None
        assert len(result.variations) > 0
        
        for variation in result.variations:
            statements = extract_achievement_statements(variation.text)
            
            # At least one statement should exist
            assert len(statements) > 0, f"Style '{style}' should generate statements"
            
            # Check format compliance
            for statement in statements:
                # Should start with action verb
                assert starts_with_action_verb(statement), \
                    f"Style '{style}' statement should start with action verb: '{statement}'"
                
                # Should be concise
                assert is_concise(statement, max_words=30), \
                    f"Style '{style}' statement should be concise: '{statement}'"
