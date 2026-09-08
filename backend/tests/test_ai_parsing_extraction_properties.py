"""
Property-Based Tests for AI Parsing Extraction

Feature: cv-web-app, Property 45: AI Parsing Extraction
Validates: Requirements 15.1

Tests that for any CV file in supported formats (PDF, DOCX, TXT), the AI parsing
service extracts structured data with identified sections.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from unittest.mock import Mock, AsyncMock
from app.llm.ai_parser import AIParser, UnsupportedFormatError
from app.llm.providers.base import BaseLLMProvider, LLMConfig, StructuredLLMResponse
from app.models.llm_models import AIParsingRequest, AIParsingResult, ParsedSection


# ============================================================================
# Test Strategies
# ============================================================================

# Supported file formats
SUPPORTED_FORMATS = ['pdf', 'docx', 'txt', 'html', 'md', 'markdown']

# CV section types
SECTION_TYPES = [
    'personal_info',
    'summary',
    'experience',
    'education',
    'skills',
    'certifications',
    'projects',
    'publications',
    'awards'
]


@st.composite
def cv_content_strategy(draw):
    """
    Generate realistic CV content with various sections.
    
    Returns:
        String containing CV content
    """
    sections = []
    
    # Personal info (always present)
    # Use letters and spaces for names
    name = draw(st.text(min_size=5, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters=' ')))
    title = draw(st.text(min_size=5, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters=' ')))
    email = f"{name.replace(' ', '').lower()}@example.com"
    sections.append(f"{name}\n{title}\n{email}")
    
    # Optional summary
    if draw(st.booleans()):
        summary = draw(st.text(min_size=20, max_size=200, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Pd'), whitelist_characters=' ')))
        sections.append(f"\nSummary:\n{summary}")
    
    # Optional experience
    if draw(st.booleans()):
        job_title = draw(st.text(min_size=5, max_size=40, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters=' ')))
        company = draw(st.text(min_size=3, max_size=30, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters=' ')))
        sections.append(f"\nExperience:\n{job_title}\n{company}\n2020 - Present")
    
    # Optional education
    if draw(st.booleans()):
        degree = draw(st.text(min_size=5, max_size=40, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters=' ')))
        school = draw(st.text(min_size=5, max_size=40, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters=' ')))
        sections.append(f"\nEducation:\n{degree}\n{school}")
    
    # Optional skills
    if draw(st.booleans()):
        num_skills = draw(st.integers(min_value=1, max_value=5))
        skills = [draw(st.text(min_size=3, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll')))) for _ in range(num_skills)]
        sections.append(f"\nSkills:\n" + ", ".join(skills))
    
    return "\n".join(sections)


@st.composite
def parsing_request_strategy(draw):
    """
    Generate AIParsingRequest with various formats and content.
    
    Returns:
        AIParsingRequest instance
    """
    file_format = draw(st.sampled_from(SUPPORTED_FORMATS))
    content = draw(cv_content_strategy())
    filename = f"resume.{file_format}"
    
    return AIParsingRequest(
        file_content=content,
        file_format=file_format,
        filename=filename
    )


@st.composite
def mock_section_response_strategy(draw, content: str):
    """
    Generate mock section identification response.
    
    Args:
        content: CV content to base sections on
        
    Returns:
        StructuredLLMResponse with sections
    """
    # Identify which sections are likely present based on content
    sections = []
    
    # Always include personal_info
    sections.append({
        'type': 'personal_info',
        'title': 'Contact Information',
        'confidence': draw(st.floats(min_value=0.7, max_value=1.0))
    })
    
    # Add other sections based on content
    if 'Summary:' in content or 'summary' in content.lower():
        sections.append({
            'type': 'summary',
            'title': 'Summary',
            'confidence': draw(st.floats(min_value=0.6, max_value=1.0))
        })
    
    if 'Experience:' in content or 'experience' in content.lower():
        sections.append({
            'type': 'experience',
            'title': 'Experience',
            'confidence': draw(st.floats(min_value=0.6, max_value=1.0))
        })
    
    if 'Education:' in content or 'education' in content.lower():
        sections.append({
            'type': 'education',
            'title': 'Education',
            'confidence': draw(st.floats(min_value=0.6, max_value=1.0))
        })
    
    if 'Skills:' in content or 'skills' in content.lower():
        sections.append({
            'type': 'skills',
            'title': 'Skills',
            'confidence': draw(st.floats(min_value=0.6, max_value=1.0))
        })
    
    return StructuredLLMResponse(
        data={'sections': sections},
        model='gpt-4',
        provider='openai',
        tokens_used=draw(st.integers(min_value=50, max_value=500))
    )


@st.composite
def mock_parsing_response_strategy(draw, section_type: str):
    """
    Generate mock section parsing response.
    
    Args:
        section_type: Type of section being parsed
        
    Returns:
        StructuredLLMResponse with parsed data
    """
    confidence = draw(st.floats(min_value=0.5, max_value=1.0))
    
    # Generate section-specific data
    if section_type == 'personal_info':
        data = {
            'name': draw(st.text(min_size=5, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters=' '))),
            'title': draw(st.text(min_size=5, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters=' '))),
            'email': 'test@example.com'
        }
    elif section_type == 'experience':
        data = {
            'entries': [{
                'title': draw(st.text(min_size=5, max_size=40, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters=' '))),
                'company': draw(st.text(min_size=3, max_size=30, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters=' '))),
                'start_date': '2020',
                'current': draw(st.booleans())
            }]
        }
    elif section_type == 'education':
        data = {
            'entries': [{
                'degree': draw(st.text(min_size=5, max_size=40, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters=' '))),
                'institution': draw(st.text(min_size=5, max_size=40, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters=' ')))
            }]
        }
    elif section_type == 'skills':
        num_skills = draw(st.integers(min_value=1, max_value=5))
        data = {
            'categories': [{
                'name': 'Technical Skills',
                'skills': [draw(st.text(min_size=3, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll')))) for _ in range(num_skills)]
            }]
        }
    else:
        data = {'raw': 'Section content'}
    
    return StructuredLLMResponse(
        data={
            'data': data,
            'confidence': confidence,
            'ambiguities': []
        },
        model='gpt-4',
        provider='openai',
        tokens_used=draw(st.integers(min_value=50, max_value=500))
    )


# ============================================================================
# Property Tests
# ============================================================================

class TestAIParsingExtractionProperties:
    """
    Property-based tests for AI parsing extraction.
    
    Feature: cv-web-app, Property 45: AI Parsing Extraction
    Validates: Requirements 15.1
    """
    
    @given(parsing_request_strategy())
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
    )
    @pytest.mark.asyncio
    async def test_property_45_ai_parsing_extracts_structured_data(self, request_data):
        """
        Property 45: AI Parsing Extraction
        
        For any CV file in supported formats (PDF, DOCX, TXT), the AI parsing
        service should extract structured data with identified sections.
        
        Validates: Requirements 15.1
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
        
        # Mock section identification response - create simple response
        section_response = StructuredLLMResponse(
            data={
                'sections': [{
                    'type': 'personal_info',
                    'title': 'Contact Information',
                    'confidence': 0.9
                }]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=100
        )
        
        # Mock section parsing response
        parsing_response = StructuredLLMResponse(
            data={
                'data': {
                    'name': 'Test User',
                    'email': 'test@example.com'
                },
                'confidence': 0.85,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=150
        )
        
        # Set up mock to return responses in sequence
        mock_provider.generate_structured_output = AsyncMock(
            side_effect=[section_response, parsing_response]
        )
        
        # Act: Parse CV
        result = await ai_parser.parse_cv(request_data)
        
        # Assert: Verify structured data extraction
        # Property 1: Result should be an AIParsingResult instance
        assert isinstance(result, AIParsingResult), \
            "Parsing should return AIParsingResult instance"
        
        # Property 2: Result should contain parsed sections
        assert isinstance(result.parsed_sections, list), \
            "Result should contain list of parsed sections"
        
        # Property 3: At least one section should be identified
        assert len(result.parsed_sections) > 0, \
            f"At least one section should be identified for format {request_data.file_format}"
        
        # Property 4: Each parsed section should have required fields
        for section in result.parsed_sections:
            assert isinstance(section, ParsedSection), \
                "Each section should be a ParsedSection instance"
            assert hasattr(section, 'section_type'), \
                "Section should have section_type"
            assert hasattr(section, 'content'), \
                "Section should have content"
            assert hasattr(section, 'confidence'), \
                "Section should have confidence score"
            assert hasattr(section, 'raw_text'), \
                "Section should have raw_text"
            
            # Confidence should be between 0 and 1
            assert 0.0 <= section.confidence <= 1.0, \
                f"Section confidence should be between 0 and 1, got {section.confidence}"
            
            # Content should be a dictionary
            assert isinstance(section.content, dict), \
                "Section content should be a dictionary"
        
        # Property 5: Overall confidence should be calculated
        assert hasattr(result, 'overall_confidence'), \
            "Result should have overall_confidence"
        assert 0.0 <= result.overall_confidence <= 1.0, \
            f"Overall confidence should be between 0 and 1, got {result.overall_confidence}"
        
        # Property 6: Result should include model and provider information
        assert hasattr(result, 'model'), \
            "Result should include model information"
        assert hasattr(result, 'provider'), \
            "Result should include provider information"
        assert result.model == 'gpt-4', \
            "Model should match provider configuration"
        assert result.provider == 'openai', \
            "Provider should match provider configuration"
        
        # Property 7: Ambiguities list should exist (even if empty)
        assert hasattr(result, 'ambiguities'), \
            "Result should have ambiguities list"
        assert isinstance(result.ambiguities, list), \
            "Ambiguities should be a list"
        
        # Property 8: Errors list should exist (even if empty)
        assert hasattr(result, 'errors'), \
            "Result should have errors list"
        assert isinstance(result.errors, list), \
            "Errors should be a list"
    
    @given(st.sampled_from(SUPPORTED_FORMATS))
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_property_45_supported_formats_accepted(self, file_format):
        """
        Property 45a: Supported Format Acceptance
        
        For any supported file format, the AI parser should accept the request
        and attempt parsing without raising UnsupportedFormatError.
        
        Validates: Requirements 15.1
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
            file_content="John Doe\nSoftware Engineer\njohn@example.com",
            file_format=file_format,
            filename=f"resume.{file_format}"
        )
        
        # Mock responses
        section_response = StructuredLLMResponse(
            data={
                'sections': [{
                    'type': 'personal_info',
                    'title': 'Contact',
                    'confidence': 0.9
                }]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=100
        )
        
        parsing_response = StructuredLLMResponse(
            data={
                'data': {'name': 'John Doe'},
                'confidence': 0.85,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=150
        )
        
        mock_provider.generate_structured_output = AsyncMock(
            side_effect=[section_response, parsing_response]
        )
        
        # Act & Assert: Should not raise UnsupportedFormatError
        try:
            result = await ai_parser.parse_cv(request)
            assert isinstance(result, AIParsingResult), \
                f"Supported format {file_format} should be parsed successfully"
        except UnsupportedFormatError:
            pytest.fail(f"Format {file_format} should be supported but raised UnsupportedFormatError")
    
    @given(st.text(min_size=1, max_size=20).filter(lambda x: x.lower() not in SUPPORTED_FORMATS))
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_property_45_unsupported_formats_rejected(self, file_format):
        """
        Property 45b: Unsupported Format Rejection
        
        For any unsupported file format, the AI parser should raise
        UnsupportedFormatError without attempting parsing.
        
        Validates: Requirements 15.1
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
            file_content="Some content",
            file_format=file_format,
            filename=f"file.{file_format}"
        )
        
        # Act & Assert: Should raise UnsupportedFormatError
        with pytest.raises(UnsupportedFormatError) as exc_info:
            await ai_parser.parse_cv(request)
        
        assert "not supported" in str(exc_info.value).lower(), \
            "Error message should indicate format is not supported"
    
    @given(cv_content_strategy())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_property_45_personal_info_always_extracted(self, cv_content):
        """
        Property 45c: Personal Info Extraction
        
        For any CV content, the AI parser should always attempt to extract
        personal information as it's the most critical section.
        
        Validates: Requirements 15.1
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
        
        # Mock responses - always include personal_info section
        section_response = StructuredLLMResponse(
            data={
                'sections': [{
                    'type': 'personal_info',
                    'title': 'Contact Information',
                    'confidence': 0.9
                }]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=100
        )
        
        parsing_response = StructuredLLMResponse(
            data={
                'data': {
                    'name': 'Test User',
                    'email': 'test@example.com'
                },
                'confidence': 0.85,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=150
        )
        
        mock_provider.generate_structured_output = AsyncMock(
            side_effect=[section_response, parsing_response]
        )
        
        # Act
        result = await ai_parser.parse_cv(request)
        
        # Assert: Personal info should be present
        section_types = [section.section_type for section in result.parsed_sections]
        assert 'personal_info' in section_types, \
            "Personal info section should always be extracted from CV content"
    
    @given(
        st.integers(min_value=1, max_value=5),
        st.floats(min_value=0.5, max_value=1.0)
    )
    @settings(max_examples=30, deadline=None)
    @pytest.mark.asyncio
    async def test_property_45_confidence_scores_valid(self, num_sections, base_confidence):
        """
        Property 45d: Confidence Score Validity
        
        For any parsing result, all confidence scores (section-level and overall)
        should be valid numbers between 0 and 1.
        
        Validates: Requirements 15.1
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
            file_content="Test CV content",
            file_format='txt',
            filename='resume.txt'
        )
        
        # Create sections with varying confidence
        sections = []
        for i in range(num_sections):
            sections.append({
                'type': SECTION_TYPES[i % len(SECTION_TYPES)],
                'title': f'Section {i}',
                'confidence': min(1.0, base_confidence + (i * 0.05))
            })
        
        section_response = StructuredLLMResponse(
            data={'sections': sections},
            model='gpt-4',
            provider='openai',
            tokens_used=100
        )
        
        # Create parsing responses
        parsing_responses = []
        for section in sections:
            parsing_responses.append(StructuredLLMResponse(
                data={
                    'data': {'test': 'data'},
                    'confidence': section['confidence'],
                    'ambiguities': []
                },
                model='gpt-4',
                provider='openai',
                tokens_used=100
            ))
        
        mock_provider.generate_structured_output = AsyncMock(
            side_effect=[section_response] + parsing_responses
        )
        
        # Act
        result = await ai_parser.parse_cv(request)
        
        # Assert: All confidence scores should be valid
        for section in result.parsed_sections:
            assert 0.0 <= section.confidence <= 1.0, \
                f"Section confidence {section.confidence} should be between 0 and 1"
        
        assert 0.0 <= result.overall_confidence <= 1.0, \
            f"Overall confidence {result.overall_confidence} should be between 0 and 1"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
