"""
Property-Based Tests for Note Expansion Preservation

Feature: cv-web-app, Property 23: Note Expansion Preservation
Validates: Requirements 10.2

Property 23: Note Expansion Preservation
For any brief notes provided, the expanded description should be longer, more detailed,
and preserve the core meaning of the original notes.

This test validates that note expansion:
1. Produces longer text than the original notes
2. Preserves key terms and concepts from the original notes
3. Generates professional, detailed descriptions
4. Works consistently across different providers
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from unittest.mock import AsyncMock
import re

from app.llm.content_generator import (
    ContentGenerator,
    NoteExpansionRequest,
    ContentVariation
)
from app.llm.providers.base import BaseLLMProvider, LLMResponse, LLMConfig


class MockLLMProviderForNoteExpansion(BaseLLMProvider):
    """Mock LLM provider that simulates realistic note expansion."""
    
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
        """Generate mock completion that expands notes realistically."""
        self._call_count += 1
        
        # The notes are in the prompt in the format "Notes: {notes}"
        # Extract them to ensure we preserve key terms
        original_notes = ""
        
        # Look for "Notes:" followed by the actual notes
        import re
        # Try multiple patterns to extract notes
        patterns = [
            r'Notes:\s*([^\n]+)',  # Notes: followed by text until newline
            r'notes:\s*([^\n]+)',  # lowercase version
            r'brief notes:\s*([^\n]+)',  # "brief notes:"
            r'Expand these brief notes[^\n]*:\s*([^\n]+)',  # Full sentence pattern
        ]
        
        for pattern in patterns:
            match = re.search(pattern, prompt)
            if match:
                original_notes = match.group(1).strip()
                break
        
        # If no notes found, try to extract from the first line after "Notes:"
        if not original_notes:
            lines = prompt.split('\n')
            for i, line in enumerate(lines):
                if 'notes' in line.lower() and ':' in line:
                    # Get the content after the colon
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        original_notes = parts[1].strip()
                        break
        
        # If still no notes found, use a default
        if not original_notes:
            original_notes = "work on project"
        
        # Generate expanded versions that preserve key terms
        content = self._generate_expanded_notes(original_notes, self._provider_name)
        
        return LLMResponse(
            content=content,
            model=self.config.model,
            provider=self._provider_name,
            tokens_used=100 + self._call_count * 10
        )
    
    def _generate_expanded_notes(self, notes: str, provider_name: str) -> str:
        """Generate expanded notes that preserve key terms from original."""
        # Extract key terms from notes (nouns, verbs, technical terms)
        key_terms = self._extract_key_terms(notes)
        
        # If no key terms extracted, use the notes directly
        if not key_terms:
            key_terms = notes.lower().split()[:3]  # Use first 3 words
        
        # Generate variations that include key terms
        if provider_name == "openai":
            return self._generate_openai_expansion(notes, key_terms)
        elif provider_name == "anthropic":
            return self._generate_anthropic_expansion(notes, key_terms)
        elif provider_name == "local":
            return self._generate_local_expansion(notes, key_terms)
        else:
            return self._generate_generic_expansion(notes, key_terms)
    
    def _extract_key_terms(self, notes: str) -> list:
        """Extract key terms from notes."""
        # Simple extraction of important words (nouns, verbs, technical terms)
        words = notes.lower().split()
        # Filter out common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        key_terms = [w for w in words if w not in stop_words and len(w) > 2]
        return key_terms
    
    def _generate_openai_expansion(self, notes: str, key_terms: list) -> str:
        """Generate OpenAI-style expansion."""
        # Ensure we have key terms to work with
        if not key_terms:
            key_terms = notes.lower().split()[:3]
        
        # Create variations that incorporate key terms
        variations = []
        
        # Variation 1: Detailed professional description
        terms_str = ' and '.join(key_terms[:2]) if len(key_terms) >= 2 else key_terms[0] if key_terms else 'development'
        var1 = f"1. Led comprehensive development efforts focusing on {terms_str} "
        var1 += f"to deliver high-quality solutions that exceeded project requirements and stakeholder expectations."
        variations.append(var1)
        
        # Variation 2: Achievement-focused
        terms_str = ' '.join(key_terms[:2]) if len(key_terms) >= 2 else key_terms[0] if key_terms else 'development'
        var2 = f"2. Successfully implemented {terms_str} initiatives, "
        var2 += f"resulting in improved system performance and enhanced user experience across the platform."
        variations.append(var2)
        
        # Variation 3: Technical detail
        terms_str = ' and '.join(key_terms[:2]) if len(key_terms) >= 2 else key_terms[0] if key_terms else 'development'
        var3 = f"3. Architected and deployed robust solutions utilizing {terms_str}, "
        var3 += f"demonstrating technical expertise and commitment to best practices in software development."
        variations.append(var3)
        
        return '\n'.join(variations)
    
    def _generate_anthropic_expansion(self, notes: str, key_terms: list) -> str:
        """Generate Anthropic-style expansion."""
        # Ensure we have key terms to work with
        if not key_terms:
            key_terms = notes.lower().split()[:3]
        
        terms_str1 = ' and '.join(key_terms[:2]) if len(key_terms) >= 2 else key_terms[0] if key_terms else 'development'
        var1 = f"Spearheaded critical initiatives involving {terms_str1}, "
        var1 += f"collaborating with cross-functional teams to deliver innovative solutions that addressed complex business challenges."
        
        terms_str2 = ' '.join(key_terms[:2]) if len(key_terms) >= 2 else key_terms[0] if key_terms else 'development'
        var2 = f"\n\nDrove strategic implementation of {terms_str2} capabilities, "
        var2 += f"leveraging technical expertise to optimize workflows and enhance overall system reliability."
        
        terms_str3 = ' and '.join(key_terms[:2]) if len(key_terms) >= 2 else key_terms[0] if key_terms else 'development'
        var3 = f"\n\nChampioned development efforts centered on {terms_str3}, "
        var3 += f"establishing best practices and mentoring team members to ensure consistent delivery of high-quality results."
        
        return var1 + var2 + var3
    
    def _generate_local_expansion(self, notes: str, key_terms: list) -> str:
        """Generate local model style expansion."""
        # Ensure we have key terms to work with
        if not key_terms:
            key_terms = notes.lower().split()[:3]
        
        terms_str1 = ' and '.join(key_terms[:2]) if len(key_terms) >= 2 else key_terms[0] if key_terms else 'development'
        var1 = f"1. Worked on {terms_str1} to improve system functionality and meet project goals."
        
        terms_str2 = ' '.join(key_terms[:2]) if len(key_terms) >= 2 else key_terms[0] if key_terms else 'development'
        var2 = f"2. Developed solutions using {terms_str2} with focus on quality and performance."
        
        terms_str3 = ' and '.join(key_terms[:2]) if len(key_terms) >= 2 else key_terms[0] if key_terms else 'development'
        var3 = f"3. Implemented features related to {terms_str3} following industry standards."
        
        return f"{var1}\n{var2}\n{var3}"
    
    def _generate_generic_expansion(self, notes: str, key_terms: list) -> str:
        """Generate generic expansion."""
        # Ensure we have key terms to work with
        if not key_terms:
            key_terms = notes.lower().split()[:3]
        
        terms_str1 = ' and '.join(key_terms[:2]) if len(key_terms) >= 2 else key_terms[0] if key_terms else 'development'
        var1 = f"Contributed to projects involving {terms_str1}, "
        var1 += f"applying technical skills to deliver effective solutions."
        
        terms_str2 = ' '.join(key_terms[:2]) if len(key_terms) >= 2 else key_terms[0] if key_terms else 'development'
        var2 = f"\n\nParticipated in development activities focused on {terms_str2}, "
        var2 += f"ensuring alignment with project objectives and quality standards."
        
        terms_str3 = ' and '.join(key_terms[:2]) if len(key_terms) >= 2 else key_terms[0] if key_terms else 'development'
        var3 = f"\n\nSupported implementation of {terms_str3} features, "
        var3 += f"demonstrating commitment to continuous improvement and technical excellence."
        
        return var1 + var2 + var3
    
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


# Hypothesis strategies
@st.composite
def brief_notes_strategy(draw):
    """Generate realistic brief notes that users might enter."""
    note_templates = [
        "Built {tech} {artifact}",
        "Led {activity} for {project}",
        "Improved {metric} by {method}",
        "Implemented {feature} using {tech}",
        "Managed {resource} for {project}",
        "Designed {artifact} with {tech}",
        "Optimized {component} performance",
        "Developed {feature} functionality",
        "Created {artifact} system",
        "Maintained {component} infrastructure"
    ]
    
    technologies = ["Python", "JavaScript", "React", "API", "database", "cloud", "microservices"]
    artifacts = ["APIs", "services", "applications", "systems", "tools", "features"]
    activities = ["development", "implementation", "deployment", "testing", "migration"]
    projects = ["web platform", "mobile app", "backend system", "data pipeline"]
    metrics = ["performance", "reliability", "efficiency", "scalability"]
    methods = ["optimization", "refactoring", "caching", "automation"]
    features = ["authentication", "payment", "search", "notification", "reporting"]
    components = ["API", "database", "frontend", "backend", "infrastructure"]
    resources = ["team", "project", "infrastructure", "deployment"]
    
    template = draw(st.sampled_from(note_templates))
    
    # Fill in template
    notes = template.format(
        tech=draw(st.sampled_from(technologies)),
        artifact=draw(st.sampled_from(artifacts)),
        activity=draw(st.sampled_from(activities)),
        project=draw(st.sampled_from(projects)),
        metric=draw(st.sampled_from(metrics)),
        method=draw(st.sampled_from(methods)),
        feature=draw(st.sampled_from(features)),
        component=draw(st.sampled_from(components)),
        resource=draw(st.sampled_from(resources))
    )
    
    return notes


@st.composite
def job_context_strategy(draw):
    """Generate job context for note expansion."""
    job_titles = [
        "Software Engineer", "Senior Developer", "Backend Engineer",
        "Full Stack Developer", "DevOps Engineer", "Data Engineer",
        "Frontend Developer", "Solutions Architect", "Technical Lead"
    ]
    
    companies = [
        "Tech Corp", "Innovation Labs", "Digital Solutions",
        "Cloud Systems", "Data Dynamics", "Web Services Inc"
    ]
    
    return {
        "job_title": draw(st.sampled_from(job_titles)),
        "company": draw(st.sampled_from(companies))
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
            temperature=draw(st.floats(min_value=0.5, max_value=0.9)),
            max_tokens=draw(st.integers(min_value=200, max_value=500))
        )
    elif provider_type == "anthropic":
        model = draw(st.sampled_from(["claude-3-opus", "claude-3-sonnet"]))
        config = LLMConfig(
            provider=provider_type,
            model=model,
            api_key="test-key-456",
            temperature=draw(st.floats(min_value=0.5, max_value=0.9)),
            max_tokens=draw(st.integers(min_value=200, max_value=500))
        )
    else:  # local
        model = draw(st.sampled_from(["llama2", "mistral"]))
        config = LLMConfig(
            provider=provider_type,
            model=model,
            base_url="http://localhost:11434",
            temperature=draw(st.floats(min_value=0.5, max_value=0.9)),
            max_tokens=draw(st.integers(min_value=200, max_value=500))
        )
    
    return config, provider_type


# Property Tests
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    notes=brief_notes_strategy(),
    context=job_context_strategy(),
    config_and_provider=provider_config_strategy(),
    num_variations=st.integers(min_value=1, max_value=5)
)
@pytest.mark.asyncio
async def test_property_note_expansion_preservation_length(
    notes,
    context,
    config_and_provider,
    num_variations
):
    """
    Property 23: Note Expansion Preservation - Length Increase
    
    For any brief notes provided, the expanded description should be longer
    and more detailed than the original notes.
    
    Validates: Requirements 10.2
    """
    config, provider_type = config_and_provider
    
    # Create mock provider
    mock_provider = MockLLMProviderForNoteExpansion(config, provider_type)
    
    # Create content generator
    generator = ContentGenerator(mock_provider)
    
    # Create expansion request
    request = NoteExpansionRequest(
        notes=notes,
        job_title=context["job_title"],
        company=context["company"],
        num_variations=num_variations
    )
    
    # Expand notes
    result = await generator.expand_notes(request)
    
    # Property assertions
    # 1. Result should not be None
    assert result is not None, "Note expansion result should not be None"
    
    # 2. Should have variations
    assert len(result.variations) > 0, "Should generate at least one variation"
    
    # 3. Each expanded variation should be longer than original notes
    original_length = len(notes)
    for i, variation in enumerate(result.variations):
        expanded_length = len(variation.text)
        assert expanded_length > original_length, \
            f"Variation {i+1}: Expanded text ({expanded_length} chars) should be longer than original notes ({original_length} chars)"
        
        # Should be significantly longer (at least 2x)
        assert expanded_length >= original_length * 1.5, \
            f"Variation {i+1}: Expanded text should be at least 1.5x longer than original notes"
    
    # 4. Section type should be correct
    assert result.section_type == "note_expansion", "Section type should be 'note_expansion'"


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    notes=brief_notes_strategy(),
    context=job_context_strategy(),
    config_and_provider=provider_config_strategy(),
    num_variations=st.integers(min_value=1, max_value=5)
)
@pytest.mark.asyncio
async def test_property_note_expansion_preservation_key_terms(
    notes,
    context,
    config_and_provider,
    num_variations
):
    """
    Property 23: Note Expansion Preservation - Key Term Preservation
    
    For any brief notes provided, the expanded description should preserve
    key terms and concepts from the original notes.
    
    Validates: Requirements 10.2
    """
    config, provider_type = config_and_provider
    
    # Create mock provider
    mock_provider = MockLLMProviderForNoteExpansion(config, provider_type)
    
    # Create content generator
    generator = ContentGenerator(mock_provider)
    
    # Create expansion request
    request = NoteExpansionRequest(
        notes=notes,
        job_title=context["job_title"],
        company=context["company"],
        num_variations=num_variations
    )
    
    # Expand notes
    result = await generator.expand_notes(request)
    
    # Extract key terms from original notes
    # Remove common words and keep significant terms
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'using', 'from'}
    original_words = notes.lower().split()
    key_terms = [w.strip('.,!?;:') for w in original_words if w.lower() not in stop_words and len(w) > 2]
    
    # Property assertions
    # 1. At least some key terms should be preserved in expanded text
    if key_terms:  # Only check if there are key terms
        for i, variation in enumerate(result.variations):
            expanded_text_lower = variation.text.lower()
            
            # Count how many key terms are preserved
            preserved_terms = [term for term in key_terms if term in expanded_text_lower]
            preservation_ratio = len(preserved_terms) / len(key_terms)
            
            # At least 50% of key terms should be preserved
            assert preservation_ratio >= 0.5, \
                f"Variation {i+1}: At least 50% of key terms should be preserved. " \
                f"Original terms: {key_terms}, Preserved: {preserved_terms}"
    
    # 2. Expanded text should not be just the original notes repeated
    for i, variation in enumerate(result.variations):
        assert variation.text.lower() != notes.lower(), \
            f"Variation {i+1}: Expanded text should not be identical to original notes"
        
        # Should not just be notes with minor additions
        assert not variation.text.lower().startswith(notes.lower() + " "), \
            f"Variation {i+1}: Expanded text should be a proper expansion, not just appending to original"


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    notes=brief_notes_strategy(),
    context=job_context_strategy(),
    config_and_provider=provider_config_strategy(),
    num_variations=st.integers(min_value=2, max_value=5)
)
@pytest.mark.asyncio
async def test_property_note_expansion_preservation_professional_quality(
    notes,
    context,
    config_and_provider,
    num_variations
):
    """
    Property 23: Note Expansion Preservation - Professional Quality
    
    For any brief notes provided, the expanded description should be
    professional, well-structured, and detailed.
    
    Validates: Requirements 10.2
    """
    config, provider_type = config_and_provider
    
    # Create mock provider
    mock_provider = MockLLMProviderForNoteExpansion(config, provider_type)
    
    # Create content generator
    generator = ContentGenerator(mock_provider)
    
    # Create expansion request
    request = NoteExpansionRequest(
        notes=notes,
        job_title=context["job_title"],
        company=context["company"],
        num_variations=num_variations
    )
    
    # Expand notes
    result = await generator.expand_notes(request)
    
    # Property assertions
    # 1. Each variation should have professional structure
    for i, variation in enumerate(result.variations):
        text = variation.text
        
        # Should not be empty or just whitespace
        assert text.strip(), f"Variation {i+1}: Should not be empty"
        
        # Should have reasonable length for professional description
        assert len(text) >= 30, \
            f"Variation {i+1}: Should have at least 30 characters for professional description"
        
        # Should contain complete sentences (ends with punctuation)
        assert text.strip()[-1] in '.!?', \
            f"Variation {i+1}: Should end with proper punctuation"
        
        # Should not have excessive repetition (same word 5+ times in a row)
        words = text.lower().split()
        for j in range(len(words) - 4):
            word_sequence = words[j:j+5]
            assert len(set(word_sequence)) > 1, \
                f"Variation {i+1}: Should not have excessive word repetition"
    
    # 2. Multiple variations should be distinct
    if len(result.variations) >= 2:
        for i in range(len(result.variations) - 1):
            text1 = result.variations[i].text.lower()
            text2 = result.variations[i+1].text.lower()
            
            # Variations should not be identical
            assert text1 != text2, \
                f"Variations {i+1} and {i+2} should be distinct"
            
            # Calculate similarity (simple word overlap)
            words1 = set(text1.split())
            words2 = set(text2.split())
            overlap = len(words1 & words2) / max(len(words1), len(words2))
            
            # Variations should not be too similar (less than 90% word overlap)
            assert overlap < 0.9, \
                f"Variations {i+1} and {i+2} should be sufficiently different (overlap: {overlap:.2%})"


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    notes=brief_notes_strategy(),
    context=job_context_strategy(),
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_note_expansion_preservation_context_integration(
    notes,
    context,
    config_and_provider
):
    """
    Property 23: Note Expansion Preservation - Context Integration
    
    For any brief notes provided with job context, the expanded description
    should integrate the context appropriately while preserving the core meaning.
    
    Validates: Requirements 10.2
    """
    config, provider_type = config_and_provider
    
    # Create mock provider
    mock_provider = MockLLMProviderForNoteExpansion(config, provider_type)
    
    # Create content generator
    generator = ContentGenerator(mock_provider)
    
    # Create expansion request
    request = NoteExpansionRequest(
        notes=notes,
        job_title=context["job_title"],
        company=context["company"],
        num_variations=3
    )
    
    # Expand notes
    result = await generator.expand_notes(request)
    
    # Property assertions
    # 1. Context should be preserved in result metadata
    assert result.context_used is not None, "Context should be preserved"
    assert "notes" in result.context_used, "Original notes should be in context"
    assert "job_title" in result.context_used, "Job title should be in context"
    assert "company" in result.context_used, "Company should be in context"
    
    # 2. Original notes should match what was provided
    assert result.context_used["notes"] == notes, "Original notes should be preserved exactly"
    
    # 3. Job context should match what was provided
    assert result.context_used["job_title"] == context["job_title"], \
        "Job title should be preserved exactly"
    assert result.context_used["company"] == context["company"], \
        "Company should be preserved exactly"
    
    # 4. Expanded text should be contextually appropriate
    for i, variation in enumerate(result.variations):
        # Should be longer and more detailed
        assert len(variation.text) > len(notes), \
            f"Variation {i+1}: Should be expanded from original notes"
        
        # Should maintain professional tone
        assert variation.text[0].isupper() or variation.text[0].isdigit(), \
            f"Variation {i+1}: Should start with capital letter or number"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    notes=brief_notes_strategy(),
    context=job_context_strategy()
)
@pytest.mark.asyncio
async def test_property_note_expansion_preservation_cross_provider_consistency(
    notes,
    context
):
    """
    Property 23: Note Expansion Preservation - Cross-Provider Consistency
    
    For any brief notes, all providers should produce expansions that preserve
    the core meaning and meet quality standards, regardless of provider type.
    
    Validates: Requirements 10.2
    """
    providers = [
        ("openai", "gpt-4", {"api_key": "test-key"}),
        ("anthropic", "claude-3-opus", {"api_key": "test-key"}),
        ("local", "llama2", {"base_url": "http://localhost:11434"})
    ]
    
    results = []
    
    for provider_type, model, extra_config in providers:
        # Create config
        config = LLMConfig(
            provider=provider_type,
            model=model,
            temperature=0.7,
            max_tokens=400,
            **extra_config
        )
        
        # Create mock provider
        mock_provider = MockLLMProviderForNoteExpansion(config, provider_type)
        
        # Create content generator
        generator = ContentGenerator(mock_provider)
        
        # Create expansion request
        request = NoteExpansionRequest(
            notes=notes,
            job_title=context["job_title"],
            company=context["company"],
            num_variations=3
        )
        
        # Expand notes
        result = await generator.expand_notes(request)
        results.append((provider_type, result))
    
    # Property assertions across all providers
    # 1. All providers should produce valid results
    for provider_type, result in results:
        assert result is not None, f"Provider '{provider_type}' should produce result"
        assert len(result.variations) > 0, \
            f"Provider '{provider_type}' should produce variations"
    
    # 2. All providers should expand notes (make them longer)
    original_length = len(notes)
    for provider_type, result in results:
        for i, variation in enumerate(result.variations):
            assert len(variation.text) > original_length, \
                f"Provider '{provider_type}' variation {i+1} should expand notes"
    
    # 3. All providers should preserve key terms
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    original_words = notes.lower().split()
    key_terms = [w.strip('.,!?;:') for w in original_words if w.lower() not in stop_words and len(w) > 2]
    
    if key_terms:
        for provider_type, result in results:
            for i, variation in enumerate(result.variations):
                expanded_text_lower = variation.text.lower()
                preserved_terms = [term for term in key_terms if term in expanded_text_lower]
                preservation_ratio = len(preserved_terms) / len(key_terms)
                
                assert preservation_ratio >= 0.4, \
                    f"Provider '{provider_type}' variation {i+1} should preserve at least 40% of key terms"
    
    # 4. All providers should produce professional quality
    for provider_type, result in results:
        for i, variation in enumerate(result.variations):
            assert len(variation.text) >= 30, \
                f"Provider '{provider_type}' variation {i+1} should have professional length"
            assert variation.text.strip()[-1] in '.!?', \
                f"Provider '{provider_type}' variation {i+1} should end with punctuation"
