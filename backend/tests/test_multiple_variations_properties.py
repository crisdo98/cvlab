"""
Property-Based Tests for Multiple Variations Provision

Feature: cv-web-app, Property 26: Multiple Variations Provision
Validates: Requirements 10.5

Property 26: Multiple Variations Provision
For any content generation request, the LLM service should return multiple
distinct variations for user selection.

This test validates that:
1. The requested number of variations is generated (up to the limit)
2. Each variation is distinct from the others
3. All variations are valid and non-empty
4. Variation numbering is sequential and correct
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any

from app.llm.content_generator import (
    ContentGenerator,
    SummaryGenerationRequest,
    NoteExpansionRequest,
    AchievementGenerationRequest,
    ContentVariation
)
from app.llm.providers.base import BaseLLMProvider, LLMResponse, LLMConfig


# Mock provider for property testing
class MockVariationProvider(BaseLLMProvider):
    """Mock LLM provider that generates distinct variations."""
    
    def __init__(self, config: LLMConfig, variation_style: str = "numbered"):
        super().__init__(config)
        self._variation_style = variation_style
        self._call_count = 0
    
    async def generate_completion(
        self,
        prompt: str,
        system_prompt=None,
        temperature=None,
        max_tokens=None,
        **kwargs
    ) -> LLMResponse:
        """Generate mock completion with multiple variations."""
        self._call_count += 1
        
        # Extract requested number of variations from prompt
        num_variations = self._extract_num_variations(prompt)
        
        # Generate variations based on style
        if self._variation_style == "numbered":
            content = self._generate_numbered_variations(num_variations)
        elif self._variation_style == "paragraphs":
            content = self._generate_paragraph_variations(num_variations)
        elif self._variation_style == "mixed":
            content = self._generate_mixed_variations(num_variations)
        else:
            content = self._generate_numbered_variations(num_variations)
        
        return LLMResponse(
            content=content,
            model=self.config.model,
            provider=self.config.provider,
            tokens_used=100 + self._call_count * 50
        )
    
    def _extract_num_variations(self, prompt: str) -> int:
        """Extract number of variations from prompt."""
        # Look for common patterns in prompts
        import re
        patterns = [
            r'generate\s+(\d+)\s+distinct',  # "Generate 4 distinct variations"
            r'create\s+(\d+)\s+distinct',    # "Create 4 distinct achievement statements"
            r'(\d+)\s+distinct\s+variations?',  # "4 distinct variations"
            r'(\d+)\s+variations?',          # "4 variations"
            r'provide\s+(\d+)',              # "provide 4"
            r'generate\s+(\d+)',             # "generate 4"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, prompt.lower())
            if match:
                return int(match.group(1))
        
        # Default to 3 if not found
        return 3
    
    def _generate_numbered_variations(self, num: int) -> str:
        """Generate numbered list variations."""
        variations = []
        templates = [
            "Professional summary variation {i} with unique content demonstrating expertise and achievements in the field. This variation emphasizes different aspects of the candidate's profile.",
            "Professional summary variation {i} with unique content demonstrating expertise and achievements.",
            "Professional summary variation {i} with unique content demonstrating expertise and achievements in the field. This variation emphasizes different aspects of the candidate's profile and provides additional context about their experience.",
            "Professional summary variation {i} showcasing key accomplishments and technical skills.",
            "Professional summary variation {i} highlighting leadership abilities and strategic thinking with proven results."
        ]
        for i in range(1, num + 1):
            # Use different templates to ensure uniqueness
            template_idx = (i - 1) % len(templates)
            variations.append(f"{i}. {templates[template_idx].format(i=i)}")
        return "\n\n".join(variations)
    
    def _generate_paragraph_variations(self, num: int) -> str:
        """Generate paragraph-separated variations."""
        variations = []
        templates = [
            "Accomplished professional with extensive experience in delivering innovative solutions. This version highlights specific strengths and unique value proposition number {i}.",
            "Accomplished professional with extensive experience in delivering innovative solutions and driving results.",
            "Accomplished professional with extensive experience in delivering innovative solutions. This version highlights specific strengths and unique value proposition number {i}. Additional details about leadership and technical expertise.",
            "Accomplished professional with proven track record in delivering high-impact projects and solutions.",
            "Accomplished professional combining technical excellence with strategic business acumen and leadership skills."
        ]
        for i in range(1, num + 1):
            # Use different templates to ensure uniqueness
            template_idx = (i - 1) % len(templates)
            variations.append(f"Variation {i}: {templates[template_idx].format(i=i)}")
        return "\n\n".join(variations)
    
    def _generate_mixed_variations(self, num: int) -> str:
        """Generate mixed format variations."""
        variations = []
        numbered_templates = [
            "Professional description variation {i} with distinct focus and emphasis on key qualifications.",
            "Professional description variation {i} with distinct focus and emphasis on key qualifications and achievements.",
            "Professional description variation {i} showcasing technical expertise and leadership capabilities."
        ]
        labeled_templates = [
            "Experienced professional with proven track record in the industry.",
            "Experienced professional with proven track record in the industry and strong leadership skills.",
            "Experienced professional combining technical depth with strategic vision and execution."
        ]
        
        for i in range(1, num + 1):
            if i % 2 == 1:
                # Numbered format
                template_idx = ((i - 1) // 2) % len(numbered_templates)
                variations.append(f"{i}. {numbered_templates[template_idx].format(i=i)}")
            else:
                # Paragraph format
                template_idx = ((i - 2) // 2) % len(labeled_templates)
                variations.append(f"Alternative version {i}: {labeled_templates[template_idx]}")
        return "\n\n".join(variations)
    
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
        return self.config.provider


# Hypothesis strategies
@st.composite
def num_variations_strategy(draw):
    """Generate valid number of variations (1-5)."""
    return draw(st.integers(min_value=1, max_value=5))


@st.composite
def variation_style_strategy(draw):
    """Generate variation formatting styles."""
    return draw(st.sampled_from(["numbered", "paragraphs", "mixed"]))


@st.composite
def job_title_strategy(draw):
    """Generate realistic job titles."""
    return draw(st.sampled_from([
        "Software Engineer",
        "Senior Developer",
        "Product Manager",
        "Data Scientist",
        "DevOps Engineer",
        "UX Designer",
        "Marketing Manager",
        "Business Analyst"
    ]))


@st.composite
def skills_list_strategy(draw):
    """Generate realistic skills lists."""
    all_skills = [
        "Python", "JavaScript", "TypeScript", "React", "Vue.js",
        "Node.js", "FastAPI", "Django", "PostgreSQL", "MongoDB",
        "AWS", "Docker", "Kubernetes", "CI/CD", "Git"
    ]
    num_skills = draw(st.integers(min_value=3, max_value=10))
    return draw(st.lists(
        st.sampled_from(all_skills),
        min_size=num_skills,
        max_size=num_skills,
        unique=True
    ))


@st.composite
def summary_request_with_variations_strategy(draw):
    """Generate summary requests with varying num_variations."""
    return SummaryGenerationRequest(
        job_title=draw(job_title_strategy()),
        years_experience=draw(st.integers(min_value=0, max_value=30)),
        skills=draw(skills_list_strategy()),
        industry=draw(st.sampled_from([None, "Technology", "Finance", "Healthcare"])),
        num_variations=draw(num_variations_strategy())
    )


@st.composite
def note_expansion_request_with_variations_strategy(draw):
    """Generate note expansion requests with varying num_variations."""
    notes_options = [
        "Built APIs with Python",
        "Led team of developers",
        "Improved system performance",
        "Implemented new features"
    ]
    
    return NoteExpansionRequest(
        notes=draw(st.sampled_from(notes_options)),
        job_title=draw(job_title_strategy()),
        company=draw(st.text(min_size=3, max_size=30, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs')))),
        num_variations=draw(num_variations_strategy())
    )


@st.composite
def achievement_request_with_variations_strategy(draw):
    """Generate achievement requests with varying num_variations."""
    notes_options = [
        "Optimized API performance",
        "Reduced server costs",
        "Improved user experience",
        "Increased team productivity"
    ]
    
    return AchievementGenerationRequest(
        notes=draw(st.sampled_from(notes_options)),
        job_title=draw(job_title_strategy()),
        company=draw(st.text(min_size=3, max_size=30, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs')))),
        num_variations=draw(num_variations_strategy())
    )


# Property Tests
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    request_data=summary_request_with_variations_strategy(),
    variation_style=variation_style_strategy()
)
@pytest.mark.asyncio
async def test_property_multiple_variations_summary(request_data, variation_style):
    """
    Property 26: Multiple Variations Provision - Summary Generation
    
    For any summary generation request with num_variations specified,
    the content generator should return exactly that number of distinct
    variations (up to the maximum of 5).
    
    Validates: Requirements 10.5
    """
    # Create mock provider with specified variation style
    config = LLMConfig(
        provider="mock",
        model="mock-model",
        temperature=0.7,
        max_tokens=1000
    )
    mock_provider = MockVariationProvider(config, variation_style)
    
    # Create content generator
    generator = ContentGenerator(mock_provider)
    
    # Generate summary
    result = await generator.generate_summary(request_data)
    
    # Property assertions
    # 1. Should return the requested number of variations
    assert len(result.variations) == request_data.num_variations, \
        f"Should generate exactly {request_data.num_variations} variations, got {len(result.variations)}"
    
    # 2. Each variation should be non-empty
    for i, variation in enumerate(result.variations):
        assert variation.text, f"Variation {i+1} should have non-empty text"
        assert len(variation.text.strip()) > 0, f"Variation {i+1} should not be just whitespace"
        assert len(variation.text) >= 20, f"Variation {i+1} should have meaningful content"
    
    # 3. Variation numbers should be sequential (1, 2, 3, ...)
    for i, variation in enumerate(result.variations):
        expected_num = i + 1
        assert variation.variation_number == expected_num, \
            f"Variation {i+1} should have variation_number={expected_num}, got {variation.variation_number}"
    
    # 4. Variations should be distinct (not identical)
    if len(result.variations) > 1:
        texts = [v.text for v in result.variations]
        unique_texts = set(texts)
        assert len(unique_texts) == len(texts), \
            "All variations should be distinct (no duplicates)"
    
    # 5. All variations should have reasonable length
    for variation in result.variations:
        assert len(variation.text) < 1000, \
            "Variations should not be excessively long"


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    request_data=note_expansion_request_with_variations_strategy(),
    variation_style=variation_style_strategy()
)
@pytest.mark.asyncio
async def test_property_multiple_variations_note_expansion(request_data, variation_style):
    """
    Property 26: Multiple Variations Provision - Note Expansion
    
    For any note expansion request with num_variations specified,
    the content generator should return exactly that number of distinct
    expanded descriptions.
    
    Validates: Requirements 10.5
    """
    # Create mock provider
    config = LLMConfig(
        provider="mock",
        model="mock-model",
        temperature=0.7,
        max_tokens=1000
    )
    mock_provider = MockVariationProvider(config, variation_style)
    
    # Create content generator
    generator = ContentGenerator(mock_provider)
    
    # Expand notes
    result = await generator.expand_notes(request_data)
    
    # Property assertions
    # 1. Should return the requested number of variations
    assert len(result.variations) == request_data.num_variations, \
        f"Should generate exactly {request_data.num_variations} variations, got {len(result.variations)}"
    
    # 2. Each variation should be non-empty and longer than original notes
    for i, variation in enumerate(result.variations):
        assert variation.text, f"Variation {i+1} should have non-empty text"
        assert len(variation.text) >= len(request_data.notes), \
            f"Variation {i+1} should be at least as long as original notes"
    
    # 3. Variation numbers should be sequential
    for i, variation in enumerate(result.variations):
        expected_num = i + 1
        assert variation.variation_number == expected_num, \
            f"Variation {i+1} should have variation_number={expected_num}"
    
    # 4. Variations should be distinct
    if len(result.variations) > 1:
        texts = [v.text for v in result.variations]
        unique_texts = set(texts)
        assert len(unique_texts) == len(texts), \
            "All variations should be distinct"


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    request_data=achievement_request_with_variations_strategy(),
    variation_style=variation_style_strategy()
)
@pytest.mark.asyncio
async def test_property_multiple_variations_achievements(request_data, variation_style):
    """
    Property 26: Multiple Variations Provision - Achievement Generation
    
    For any achievement generation request with num_variations specified,
    the content generator should return exactly that number of distinct
    achievement statements.
    
    Validates: Requirements 10.5
    """
    # Create mock provider
    config = LLMConfig(
        provider="mock",
        model="mock-model",
        temperature=0.7,
        max_tokens=1000
    )
    mock_provider = MockVariationProvider(config, variation_style)
    
    # Create content generator
    generator = ContentGenerator(mock_provider)
    
    # Generate achievements
    result = await generator.generate_achievements(request_data)
    
    # Property assertions
    # 1. Should return the requested number of variations
    assert len(result.variations) == request_data.num_variations, \
        f"Should generate exactly {request_data.num_variations} variations, got {len(result.variations)}"
    
    # 2. Each variation should be non-empty
    for i, variation in enumerate(result.variations):
        assert variation.text, f"Variation {i+1} should have non-empty text"
        assert len(variation.text.strip()) > 0, f"Variation {i+1} should not be just whitespace"
    
    # 3. Variation numbers should be sequential
    for i, variation in enumerate(result.variations):
        expected_num = i + 1
        assert variation.variation_number == expected_num, \
            f"Variation {i+1} should have variation_number={expected_num}"
    
    # 4. Variations should be distinct
    if len(result.variations) > 1:
        texts = [v.text for v in result.variations]
        unique_texts = set(texts)
        assert len(unique_texts) == len(texts), \
            "All variations should be distinct"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    num_variations=num_variations_strategy(),
    variation_style=variation_style_strategy()
)
@pytest.mark.asyncio
async def test_property_multiple_variations_boundary_cases(num_variations, variation_style):
    """
    Property 26: Multiple Variations Provision - Boundary Cases
    
    For any valid num_variations value (1-5), the system should correctly
    handle edge cases including:
    - Single variation (num_variations=1)
    - Maximum variations (num_variations=5)
    - All values in between
    
    Validates: Requirements 10.5
    """
    # Create mock provider
    config = LLMConfig(
        provider="mock",
        model="mock-model",
        temperature=0.7,
        max_tokens=1000
    )
    mock_provider = MockVariationProvider(config, variation_style)
    
    # Create content generator
    generator = ContentGenerator(mock_provider)
    
    # Create request with specific num_variations
    request = SummaryGenerationRequest(
        job_title="Software Engineer",
        years_experience=5,
        skills=["Python", "JavaScript", "React"],
        num_variations=num_variations
    )
    
    # Generate content
    result = await generator.generate_summary(request)
    
    # Property assertions
    # 1. Should return exactly the requested number
    assert len(result.variations) == num_variations, \
        f"Should generate exactly {num_variations} variations"
    
    # 2. For single variation, should still work correctly
    if num_variations == 1:
        assert len(result.variations) == 1, "Should handle single variation correctly"
        assert result.variations[0].variation_number == 1, \
            "Single variation should have variation_number=1"
    
    # 3. For maximum variations, should not exceed limit
    if num_variations == 5:
        assert len(result.variations) <= 5, "Should not exceed maximum of 5 variations"
    
    # 4. All variations should be valid
    for variation in result.variations:
        assert variation.text, "Each variation should have text"
        assert variation.variation_number > 0, "Variation number should be positive"
        assert variation.variation_number <= num_variations, \
            "Variation number should not exceed requested count"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    num_variations=num_variations_strategy()
)
@pytest.mark.asyncio
async def test_property_multiple_variations_consistency_across_methods(num_variations):
    """
    Property 26: Multiple Variations Provision - Consistency Across Methods
    
    For any num_variations value, all content generation methods should
    consistently return the requested number of variations with proper
    structure and numbering.
    
    Validates: Requirements 10.5
    """
    # Create mock provider
    config = LLMConfig(
        provider="mock",
        model="mock-model",
        temperature=0.7,
        max_tokens=1000
    )
    mock_provider = MockVariationProvider(config, "numbered")
    
    # Create content generator
    generator = ContentGenerator(mock_provider)
    
    # Test summary generation
    summary_request = SummaryGenerationRequest(
        job_title="Software Engineer",
        years_experience=5,
        skills=["Python", "JavaScript"],
        num_variations=num_variations
    )
    summary_result = await generator.generate_summary(summary_request)
    
    # Test note expansion
    note_request = NoteExpansionRequest(
        notes="Built APIs",
        job_title="Software Engineer",
        company="Tech Corp",
        num_variations=num_variations
    )
    note_result = await generator.expand_notes(note_request)
    
    # Test achievement generation
    achievement_request = AchievementGenerationRequest(
        notes="Improved performance",
        job_title="Software Engineer",
        company="Tech Corp",
        num_variations=num_variations
    )
    achievement_result = await generator.generate_achievements(achievement_request)
    
    # Property assertions - all methods should behave consistently
    results = [summary_result, note_result, achievement_result]
    
    for result in results:
        # 1. Should return requested number of variations
        assert len(result.variations) == num_variations, \
            f"All methods should generate {num_variations} variations"
        
        # 2. Variation numbers should be sequential
        for i, variation in enumerate(result.variations):
            assert variation.variation_number == i + 1, \
                "All methods should use sequential variation numbering"
        
        # 3. All variations should be non-empty
        for variation in result.variations:
            assert variation.text, "All methods should generate non-empty variations"
            assert len(variation.text.strip()) > 0, \
                "All methods should generate non-whitespace content"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    num_variations=num_variations_strategy()
)
@pytest.mark.asyncio
async def test_property_multiple_variations_distinctness(num_variations):
    """
    Property 26: Multiple Variations Provision - Variation Distinctness
    
    For any num_variations > 1, the generated variations should be
    meaningfully distinct from each other, not just minor rephrasing.
    
    Validates: Requirements 10.5
    """
    # Create mock provider
    config = LLMConfig(
        provider="mock",
        model="mock-model",
        temperature=0.7,
        max_tokens=1000
    )
    mock_provider = MockVariationProvider(config, "numbered")
    
    # Create content generator
    generator = ContentGenerator(mock_provider)
    
    # Create request
    request = SummaryGenerationRequest(
        job_title="Software Engineer",
        years_experience=5,
        skills=["Python", "JavaScript", "React"],
        num_variations=num_variations
    )
    
    # Generate content
    result = await generator.generate_summary(request)
    
    # Property assertions for distinctness
    if num_variations > 1:
        # 1. No two variations should be identical
        texts = [v.text for v in result.variations]
        assert len(set(texts)) == len(texts), \
            "No two variations should be identical"
        
        # 2. Each variation should be independently valid
        for i, variation in enumerate(result.variations):
            assert variation.text, f"Variation {i+1} should be independently valid"
            assert len(variation.text) >= 20, f"Variation {i+1} should have meaningful content"
