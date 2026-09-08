"""
Property-Based Tests for Section Identification Robustness

Feature: cv-web-app, Property 47: Section Identification Robustness
Validates: Requirements 15.3

Tests that for any CV with non-standard or inconsistent formatting, the AI parser
should still correctly identify and categorize CV sections.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from unittest.mock import Mock, AsyncMock
from app.llm.ai_parser import AIParser
from app.llm.providers.base import BaseLLMProvider, LLMConfig, StructuredLLMResponse
from app.models.llm_models import AIParsingRequest


# ============================================================================
# Test Strategies
# ============================================================================

# Standard section headers
STANDARD_HEADERS = {
    'personal_info': ['Contact', 'Personal Information', 'About Me'],
    'summary': ['Summary', 'Professional Summary', 'Profile', 'Objective'],
    'experience': ['Experience', 'Work Experience', 'Employment History', 'Professional Experience'],
    'education': ['Education', 'Academic Background', 'Qualifications'],
    'skills': ['Skills', 'Technical Skills', 'Competencies', 'Expertise'],
    'certifications': ['Certifications', 'Licenses', 'Professional Certifications'],
    'projects': ['Projects', 'Portfolio', 'Key Projects'],
    'publications': ['Publications', 'Research', 'Papers'],
    'awards': ['Awards', 'Honors', 'Achievements', 'Recognition']
}

# Non-standard variations
NON_STANDARD_VARIATIONS = {
    'experience': ['What I\'ve Done', 'My Journey', 'Career Path', 'Where I\'ve Worked'],
    'education': ['Where I Studied', 'Academic Journey', 'Learning'],
    'skills': ['What I Know', 'My Toolkit', 'Technologies', 'Capabilities'],
    'projects': ['Things I Built', 'My Work', 'Portfolio Items'],
    'certifications': ['Credentials', 'Professional Development']
}


@st.composite
def formatting_style_strategy(draw):
    """
    Generate different formatting styles for section headers.
    
    Returns:
        Dictionary with formatting parameters
    """
    styles = [
        {'prefix': '## ', 'suffix': '', 'case': 'title'},  # Markdown style
        {'prefix': '', 'suffix': ':', 'case': 'upper'},     # Colon style uppercase
        {'prefix': '', 'suffix': ':', 'case': 'title'},     # Colon style title case
        {'prefix': '=== ', 'suffix': ' ===', 'case': 'upper'},  # Boxed style
        {'prefix': '--- ', 'suffix': ' ---', 'case': 'title'},  # Dashed style
        {'prefix': '# ', 'suffix': '', 'case': 'lower'},    # Markdown lowercase
        {'prefix': '', 'suffix': '', 'case': 'upper'},      # Plain uppercase
        {'prefix': '* ', 'suffix': ' *', 'case': 'title'},  # Asterisk style
    ]
    
    return draw(st.sampled_from(styles))


@st.composite
def inconsistent_cv_strategy(draw):
    """
    Generate CV content with inconsistent formatting.
    
    Returns:
        String containing CV with mixed formatting styles
    """
    sections = []
    
    # Personal info - always present but with varying format
    name_style = draw(st.sampled_from(['plain', 'bold', 'caps', 'mixed']))
    if name_style == 'plain':
        name = "John Doe"
    elif name_style == 'bold':
        name = "**JOHN DOE**"
    elif name_style == 'caps':
        name = "JOHN DOE"
    else:
        name = "JoHn DoE"
    
    contact_format = draw(st.sampled_from(['inline', 'multiline', 'mixed']))
    if contact_format == 'inline':
        contact = "john@example.com | +1-555-1234 | San Francisco, CA"
    elif contact_format == 'multiline':
        contact = "Email: john@example.com\nPhone: +1-555-1234\nLocation: San Francisco, CA"
    else:
        contact = "john@example.com\n+1-555-1234 | San Francisco, CA"
    
    sections.append(f"{name}\nSoftware Engineer\n{contact}")
    
    # Add 2-4 additional sections with different formatting
    num_sections = draw(st.integers(min_value=2, max_value=4))
    available_sections = ['summary', 'experience', 'education', 'skills']
    selected_sections = draw(st.lists(
        st.sampled_from(available_sections),
        min_size=num_sections,
        max_size=num_sections,
        unique=True
    ))
    
    for section_type in selected_sections:
        # Choose between standard and non-standard header
        use_standard = draw(st.booleans())
        
        if use_standard:
            header = draw(st.sampled_from(STANDARD_HEADERS[section_type]))
        elif section_type in NON_STANDARD_VARIATIONS:
            header = draw(st.sampled_from(NON_STANDARD_VARIATIONS[section_type]))
        else:
            header = draw(st.sampled_from(STANDARD_HEADERS[section_type]))
        
        # Apply formatting style
        style = draw(formatting_style_strategy())
        formatted_header = format_header(header, style)
        
        # Generate section content
        if section_type == 'summary':
            content = "Experienced professional with expertise in software development."
        elif section_type == 'experience':
            content = "Senior Developer\nTechCorp Inc.\n2020 - Present\nLead development team"
        elif section_type == 'education':
            content = "BS Computer Science\nUniversity of Technology\n2016 - 2020"
        elif section_type == 'skills':
            content = "Python, JavaScript, Docker, AWS"
        else:
            content = "Section content here"
        
        # Add spacing variation
        spacing = draw(st.sampled_from(['\n', '\n\n', '\n\n\n']))
        sections.append(f"{spacing}{formatted_header}\n{content}")
    
    return '\n'.join(sections)


def format_header(header: str, style: dict) -> str:
    """
    Apply formatting style to header.
    
    Args:
        header: Header text
        style: Formatting style dictionary
        
    Returns:
        Formatted header string
    """
    # Apply case transformation
    if style['case'] == 'upper':
        header = header.upper()
    elif style['case'] == 'lower':
        header = header.lower()
    elif style['case'] == 'title':
        header = header.title()
    
    # Apply prefix and suffix
    return f"{style['prefix']}{header}{style['suffix']}"


@st.composite
def malformed_cv_strategy(draw):
    """
    Generate CV with malformed or unusual structure.
    
    Returns:
        String containing malformed CV content
    """
    issues = draw(st.lists(
        st.sampled_from([
            'missing_headers',
            'duplicate_sections',
            'mixed_languages',
            'unusual_spacing',
            'no_clear_structure'
        ]),
        min_size=1,
        max_size=3,
        unique=True
    ))
    
    content_parts = []
    
    # Always start with some personal info
    content_parts.append("John Doe\njohn@example.com")
    
    if 'missing_headers' in issues:
        # Add content without clear section headers
        content_parts.append("\nSenior Developer at TechCorp\n2020 - Present")
        content_parts.append("\nBS Computer Science, MIT, 2016-2020")
        content_parts.append("\nPython, JavaScript, Docker")
    
    if 'duplicate_sections' in issues:
        # Add duplicate section headers
        content_parts.append("\n\nExperience:\nJob 1 at Company A")
        content_parts.append("\n\nExperience:\nJob 2 at Company B")
    
    if 'unusual_spacing' in issues:
        # Add irregular spacing
        content_parts.append("\n\n\n\n\nSkills:\n\n\nPython\n\n\nJavaScript")
    
    if 'no_clear_structure' in issues:
        # Mix everything together
        content_parts.append("\nDeveloper with 5 years experience Python JavaScript AWS")
        content_parts.append("Worked at multiple companies BS degree in CS")
    
    return ''.join(content_parts)


@st.composite
def mock_section_identification_response(draw, content: str, num_sections: int):
    """
    Generate mock response for section identification.
    
    Args:
        content: CV content
        num_sections: Number of sections to identify
        
    Returns:
        StructuredLLMResponse with identified sections
    """
    section_types = ['personal_info', 'summary', 'experience', 'education', 'skills']
    
    sections = []
    for i in range(min(num_sections, len(section_types))):
        sections.append({
            'type': section_types[i],
            'title': f'Section {i}',
            'confidence': draw(st.floats(min_value=0.6, max_value=1.0))
        })
    
    return StructuredLLMResponse(
        data={'sections': sections},
        model='gpt-4',
        provider='openai',
        tokens_used=draw(st.integers(min_value=100, max_value=500))
    )


# ============================================================================
# Property Tests
# ============================================================================

class TestSectionIdentificationProperties:
    """
    Property-based tests for section identification robustness.
    
    Feature: cv-web-app, Property 47: Section Identification Robustness
    Validates: Requirements 15.3
    """
    
    @given(inconsistent_cv_strategy())
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
    )
    @pytest.mark.asyncio
    async def test_property_47_identifies_sections_with_inconsistent_formatting(self, cv_content):
        """
        Property 47: Section Identification Robustness
        
        For any CV with non-standard or inconsistent formatting, the AI parser
        should still correctly identify and categorize CV sections.
        
        Validates: Requirements 15.3
        """
        # Arrange: Create mock LLM provider
        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.config = LLMConfig(
            provider="openai",
            model="gpt-4",
            temperature=0.7,
            max_tokens=1000
        )
        
        # Create AI parser
        ai_parser = AIParser(mock_provider)
        
        # Create parsing request
        request = AIParsingRequest(
            file_content=cv_content,
            file_format='txt',
            filename='resume.txt'
        )
        
        # Mock section identification - simulate AI identifying sections despite formatting
        # Count likely sections in content
        likely_sections = []
        if any(keyword in cv_content.lower() for keyword in ['email', '@', 'phone', 'contact']):
            likely_sections.append({
                'type': 'personal_info',
                'title': 'Contact Information',
                'confidence': 0.85
            })
        
        if any(keyword in cv_content.lower() for keyword in ['summary', 'profile', 'objective', 'professional']):
            likely_sections.append({
                'type': 'summary',
                'title': 'Summary',
                'confidence': 0.75
            })
        
        if any(keyword in cv_content.lower() for keyword in ['experience', 'work', 'employment', 'career', 'developer', 'engineer']):
            likely_sections.append({
                'type': 'experience',
                'title': 'Experience',
                'confidence': 0.80
            })
        
        if any(keyword in cv_content.lower() for keyword in ['education', 'degree', 'university', 'college', 'bs', 'ms', 'phd']):
            likely_sections.append({
                'type': 'education',
                'title': 'Education',
                'confidence': 0.78
            })
        
        if any(keyword in cv_content.lower() for keyword in ['skills', 'technologies', 'python', 'javascript', 'aws']):
            likely_sections.append({
                'type': 'skills',
                'title': 'Skills',
                'confidence': 0.82
            })
        
        # Ensure at least personal_info is identified
        if not any(s['type'] == 'personal_info' for s in likely_sections):
            likely_sections.insert(0, {
                'type': 'personal_info',
                'title': 'Contact',
                'confidence': 0.70
            })
        
        section_response = StructuredLLMResponse(
            data={'sections': likely_sections},
            model='gpt-4',
            provider='openai',
            tokens_used=200
        )
        
        # Mock parsing responses for each section
        parsing_responses = []
        for section in likely_sections:
            parsing_responses.append(StructuredLLMResponse(
                data={
                    'data': {'extracted': 'data'},
                    'confidence': section['confidence'],
                    'ambiguities': []
                },
                model='gpt-4',
                provider='openai',
                tokens_used=150
            ))
        
        mock_provider.generate_structured_output = AsyncMock(
            side_effect=[section_response] + parsing_responses
        )
        
        # Act: Parse CV
        result = await ai_parser.parse_cv(request)
        
        # Assert: Verify section identification despite inconsistent formatting
        # Property 1: Sections should be identified
        assert len(result.parsed_sections) > 0, \
            "AI parser should identify sections even with inconsistent formatting"
        
        # Property 2: All identified sections should have valid types
        valid_section_types = ai_parser.SECTION_TYPES + ['unknown']
        for section in result.parsed_sections:
            assert section.section_type in valid_section_types, \
                f"Section type '{section.section_type}' should be valid"
        
        # Property 3: Each section should have content
        for section in result.parsed_sections:
            assert section.content is not None, \
                "Each identified section should have content"
            assert isinstance(section.content, dict), \
                "Section content should be structured as dictionary"
        
        # Property 4: Confidence scores should reflect parsing difficulty
        for section in result.parsed_sections:
            assert 0.0 <= section.confidence <= 1.0, \
                f"Section confidence should be valid: {section.confidence}"
        
        # Property 5: Personal info should be identified (most critical section)
        section_types = [s.section_type for s in result.parsed_sections]
        assert 'personal_info' in section_types, \
            "Personal info should be identified even with inconsistent formatting"
    
    @given(malformed_cv_strategy())
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
    )
    @pytest.mark.asyncio
    async def test_property_47_handles_malformed_structure(self, cv_content):
        """
        Property 47a: Malformed Structure Handling
        
        For any CV with malformed or unusual structure (missing headers,
        duplicate sections, no clear structure), the AI parser should still
        attempt to identify sections and not fail completely.
        
        Validates: Requirements 15.3
        """
        # Arrange
        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.config = LLMConfig(
            provider="openai",
            model="gpt-4",
            temperature=0.7,
            max_tokens=1000
        )
        
        ai_parser = AIParser(mock_provider)
        
        request = AIParsingRequest(
            file_content=cv_content,
            file_format='txt',
            filename='resume.txt'
        )
        
        # Mock response - AI should identify at least some structure
        section_response = StructuredLLMResponse(
            data={
                'sections': [{
                    'type': 'personal_info',
                    'title': 'Contact',
                    'confidence': 0.65  # Lower confidence for malformed content
                }]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=200
        )
        
        parsing_response = StructuredLLMResponse(
            data={
                'data': {'name': 'John Doe', 'email': 'john@example.com'},
                'confidence': 0.60,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=150
        )
        
        mock_provider.generate_structured_output = AsyncMock(
            side_effect=[section_response, parsing_response]
        )
        
        # Act: Parse malformed CV
        result = await ai_parser.parse_cv(request)
        
        # Assert: Should not fail completely
        # Property 1: Result should be returned (not exception)
        assert result is not None, \
            "Parser should return result even for malformed CVs"
        
        # Property 2: At least one section should be identified
        assert len(result.parsed_sections) > 0, \
            "Parser should identify at least one section in malformed CV"
        
        # Property 3: Confidence may be lower but should be valid
        assert 0.0 <= result.overall_confidence <= 1.0, \
            "Overall confidence should be valid even for malformed content"
        
        # Property 4: Errors or ambiguities may be present
        # This is acceptable for malformed content
        assert isinstance(result.errors, list), \
            "Errors list should exist for malformed content"
        assert isinstance(result.ambiguities, list), \
            "Ambiguities list should exist for malformed content"
    
    @given(
        st.sampled_from(list(STANDARD_HEADERS.keys())),
        formatting_style_strategy()
    )
    @settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_property_47_recognizes_various_header_formats(self, section_type, formatting_style):
        """
        Property 47b: Header Format Recognition
        
        For any section type with various header formatting styles (markdown,
        uppercase, with symbols, etc.), the AI parser should correctly identify
        the section type.
        
        Validates: Requirements 15.3
        """
        # Arrange
        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.config = LLMConfig(
            provider="openai",
            model="gpt-4",
            temperature=0.7,
            max_tokens=1000
        )
        
        ai_parser = AIParser(mock_provider)
        
        # Create CV with specific formatted header
        header = STANDARD_HEADERS[section_type][0]
        formatted_header = format_header(header, formatting_style)
        
        cv_content = f"""John Doe
john@example.com

{formatted_header}
This is the content for the {section_type} section.
Some additional information here.
"""
        
        request = AIParsingRequest(
            file_content=cv_content,
            file_format='txt',
            filename='resume.txt'
        )
        
        # Mock response - AI should identify the section correctly
        section_response = StructuredLLMResponse(
            data={
                'sections': [
                    {
                        'type': 'personal_info',
                        'title': 'Contact',
                        'confidence': 0.90
                    },
                    {
                        'type': section_type,
                        'title': formatted_header,
                        'confidence': 0.85
                    }
                ]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=200
        )
        
        parsing_response1 = StructuredLLMResponse(
            data={
                'data': {'name': 'John Doe'},
                'confidence': 0.90,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=100
        )
        
        parsing_response2 = StructuredLLMResponse(
            data={
                'data': {'content': 'section data'},
                'confidence': 0.85,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=150
        )
        
        mock_provider.generate_structured_output = AsyncMock(
            side_effect=[section_response, parsing_response1, parsing_response2]
        )
        
        # Act
        result = await ai_parser.parse_cv(request)
        
        # Assert: Section should be correctly identified
        section_types = [s.section_type for s in result.parsed_sections]
        
        # Property: The specific section type should be identified
        assert section_type in section_types, \
            f"Section type '{section_type}' should be identified despite formatting style"
    
    @given(st.sampled_from(list(NON_STANDARD_VARIATIONS.keys())))
    @settings(max_examples=30, deadline=None)
    @pytest.mark.asyncio
    async def test_property_47_recognizes_non_standard_headers(self, section_type):
        """
        Property 47c: Non-Standard Header Recognition
        
        For any section with non-standard header names (e.g., "What I've Done"
        instead of "Experience"), the AI parser should still correctly identify
        the section type based on content and context.
        
        Validates: Requirements 15.3
        """
        # Arrange
        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.config = LLMConfig(
            provider="openai",
            model="gpt-4",
            temperature=0.7,
            max_tokens=1000
        )
        
        ai_parser = AIParser(mock_provider)
        
        # Use non-standard header
        non_standard_header = NON_STANDARD_VARIATIONS[section_type][0]
        
        cv_content = f"""John Doe
Software Engineer
john@example.com

{non_standard_header}
Relevant content for this section.
"""
        
        request = AIParsingRequest(
            file_content=cv_content,
            file_format='txt',
            filename='resume.txt'
        )
        
        # Mock response - AI should map non-standard header to correct type
        section_response = StructuredLLMResponse(
            data={
                'sections': [
                    {
                        'type': 'personal_info',
                        'title': 'Contact',
                        'confidence': 0.90
                    },
                    {
                        'type': section_type,
                        'title': non_standard_header,
                        'confidence': 0.75  # Slightly lower confidence for non-standard
                    }
                ]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=200
        )
        
        parsing_response1 = StructuredLLMResponse(
            data={
                'data': {'name': 'John Doe'},
                'confidence': 0.90,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=100
        )
        
        parsing_response2 = StructuredLLMResponse(
            data={
                'data': {'content': 'data'},
                'confidence': 0.75,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=150
        )
        
        mock_provider.generate_structured_output = AsyncMock(
            side_effect=[section_response, parsing_response1, parsing_response2]
        )
        
        # Act
        result = await ai_parser.parse_cv(request)
        
        # Assert: Non-standard header should be mapped to correct section type
        section_types = [s.section_type for s in result.parsed_sections]
        
        # Property: AI should identify the correct section type despite non-standard naming
        assert section_type in section_types, \
            f"Non-standard header '{non_standard_header}' should be mapped to '{section_type}'"
    
    @given(st.integers(min_value=0, max_value=10))
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_property_47_handles_varying_section_counts(self, num_extra_newlines):
        """
        Property 47d: Variable Spacing Handling
        
        For any CV with varying amounts of whitespace between sections,
        the AI parser should still correctly identify all sections.
        
        Validates: Requirements 15.3
        """
        # Arrange
        mock_provider = Mock(spec=BaseLLMProvider)
        mock_provider.config = LLMConfig(
            provider="openai",
            model="gpt-4",
            temperature=0.7,
            max_tokens=1000
        )
        
        ai_parser = AIParser(mock_provider)
        
        # Create CV with variable spacing
        spacing = '\n' * num_extra_newlines
        cv_content = f"""John Doe
john@example.com{spacing}
Experience:{spacing}
Senior Developer{spacing}
Education:{spacing}
BS Computer Science
"""
        
        request = AIParsingRequest(
            file_content=cv_content,
            file_format='txt',
            filename='resume.txt'
        )
        
        # Mock response
        section_response = StructuredLLMResponse(
            data={
                'sections': [
                    {'type': 'personal_info', 'title': 'Contact', 'confidence': 0.90},
                    {'type': 'experience', 'title': 'Experience', 'confidence': 0.85},
                    {'type': 'education', 'title': 'Education', 'confidence': 0.85}
                ]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=200
        )
        
        parsing_responses = [
            StructuredLLMResponse(
                data={'data': {'name': 'John Doe'}, 'confidence': 0.90, 'ambiguities': []},
                model='gpt-4', provider='openai', tokens_used=100
            ),
            StructuredLLMResponse(
                data={'data': {'title': 'Senior Developer'}, 'confidence': 0.85, 'ambiguities': []},
                model='gpt-4', provider='openai', tokens_used=100
            ),
            StructuredLLMResponse(
                data={'data': {'degree': 'BS Computer Science'}, 'confidence': 0.85, 'ambiguities': []},
                model='gpt-4', provider='openai', tokens_used=100
            )
        ]
        
        mock_provider.generate_structured_output = AsyncMock(
            side_effect=[section_response] + parsing_responses
        )
        
        # Act
        result = await ai_parser.parse_cv(request)
        
        # Assert: All sections should be identified regardless of spacing
        section_types = [s.section_type for s in result.parsed_sections]
        
        # Property: Spacing should not prevent section identification
        assert 'personal_info' in section_types, \
            "Personal info should be identified regardless of spacing"
        assert 'experience' in section_types, \
            "Experience should be identified regardless of spacing"
        assert 'education' in section_types, \
            "Education should be identified regardless of spacing"
        
        # Property: Number of sections should be consistent
        assert len(result.parsed_sections) >= 3, \
            f"Should identify at least 3 sections, found {len(result.parsed_sections)}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
