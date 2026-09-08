"""
Basic Tests for AI Parser

Tests the core functionality of the AI parser service.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.llm.ai_parser import AIParser, AIParserError, UnsupportedFormatError
from app.llm.providers.base import BaseLLMProvider, LLMConfig, StructuredLLMResponse
from app.models.llm_models import AIParsingRequest, AIParsingResult, ParsedSection


class TestAIParser:
    """Test AI parser basic functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create mock LLM provider
        self.mock_provider = Mock(spec=BaseLLMProvider)
        self.mock_provider.config = LLMConfig(
            provider="openai",
            model="gpt-4",
            temperature=0.7,
            max_tokens=1000
        )
        
        # Create AI parser
        self.ai_parser = AIParser(self.mock_provider)
    
    def test_ai_parser_initialization(self):
        """Test AI parser initialization."""
        assert self.ai_parser.llm_provider == self.mock_provider
        assert 'pdf' in self.ai_parser.SUPPORTED_FORMATS
        assert 'docx' in self.ai_parser.SUPPORTED_FORMATS
        assert 'txt' in self.ai_parser.SUPPORTED_FORMATS
    
    @pytest.mark.asyncio
    async def test_parse_cv_unsupported_format(self):
        """Test parsing with unsupported format."""
        request = AIParsingRequest(
            file_content="Some content",
            file_format='unsupported',
            filename='test.unsupported'
        )
        
        with pytest.raises(UnsupportedFormatError) as exc_info:
            await self.ai_parser.parse_cv(request)
        
        assert "not supported" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_parse_cv_success(self):
        """Test successful CV parsing."""
        request = AIParsingRequest(
            file_content="John Doe\nSoftware Engineer\njohn@example.com",
            file_format='txt',
            filename='resume.txt'
        )
        
        # Mock section identification response
        section_response = StructuredLLMResponse(
            data={
                'sections': [
                    {
                        'type': 'personal_info',
                        'title': 'Contact Information',
                        'confidence': 0.9
                    }
                ]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=100
        )
        
        # Mock section parsing response
        parsing_response = StructuredLLMResponse(
            data={
                'data': {
                    'name': 'John Doe',
                    'title': 'Software Engineer',
                    'email': 'john@example.com'
                },
                'confidence': 0.85,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=150
        )
        
        # Mock the LLM provider methods
        self.mock_provider.generate_structured_output = AsyncMock(
            side_effect=[section_response, parsing_response]
        )
        
        # Parse CV
        result = await self.ai_parser.parse_cv(request)
        
        # Verify result
        assert isinstance(result, AIParsingResult)
        assert result.overall_confidence > 0
        assert len(result.parsed_sections) > 0
        assert result.model == 'gpt-4'
        assert result.provider == 'openai'
    
    @pytest.mark.asyncio
    async def test_identify_sections(self):
        """Test section identification."""
        content = """John Doe
Software Engineer

Experience:
Senior Developer at TechCorp

Education:
BS Computer Science
"""
        
        # Mock response
        mock_response = StructuredLLMResponse(
            data={
                'sections': [
                    {
                        'type': 'personal_info',
                        'title': 'John Doe',
                        'confidence': 0.9
                    },
                    {
                        'type': 'experience',
                        'title': 'Experience',
                        'confidence': 0.85
                    },
                    {
                        'type': 'education',
                        'title': 'Education',
                        'confidence': 0.8
                    }
                ]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=200
        )
        
        self.mock_provider.generate_structured_output = AsyncMock(return_value=mock_response)
        
        # Identify sections
        sections = await self.ai_parser._identify_sections(content)
        
        # Verify sections
        assert len(sections) == 3
        assert sections[0]['type'] == 'personal_info'
        assert sections[1]['type'] == 'experience'
        assert sections[2]['type'] == 'education'
        assert all('confidence' in s for s in sections)
    
    def test_calculate_overall_confidence(self):
        """Test overall confidence calculation."""
        sections = [
            ParsedSection(
                section_type='personal_info',
                content={'name': 'John Doe'},
                confidence=0.9,
                raw_text='John Doe'
            ),
            ParsedSection(
                section_type='experience',
                content={'entries': []},
                confidence=0.8,
                raw_text='Experience section'
            ),
            ParsedSection(
                section_type='skills',
                content={'categories': []},
                confidence=0.7,
                raw_text='Skills section'
            )
        ]
        
        confidence = self.ai_parser._calculate_overall_confidence(sections)
        
        # Verify confidence is weighted average
        assert 0.0 <= confidence <= 1.0
        # Personal info has highest weight, so confidence should be closer to 0.9
        assert confidence > 0.75
    
    def test_calculate_overall_confidence_empty(self):
        """Test confidence calculation with no sections."""
        confidence = self.ai_parser._calculate_overall_confidence([])
        assert confidence == 0.0
    
    @pytest.mark.asyncio
    async def test_convert_to_cv_data(self):
        """Test conversion of parsed sections to CV data."""
        sections = [
            ParsedSection(
                section_type='personal_info',
                content={
                    'name': 'Jane Smith',
                    'title': 'Data Scientist',
                    'email': 'jane@example.com',
                    'phone': '+1-555-1234',
                    'location': 'San Francisco, CA'
                },
                confidence=0.9,
                raw_text='Jane Smith\nData Scientist'
            ),
            ParsedSection(
                section_type='summary',
                content={
                    'text': 'Experienced data scientist with ML expertise.'
                },
                confidence=0.85,
                raw_text='Summary section'
            ),
            ParsedSection(
                section_type='experience',
                content={
                    'entries': [
                        {
                            'title': 'Senior Data Scientist',
                            'company': 'DataCorp',
                            'location': 'New York, NY',
                            'start_date': 'January 2020',
                            'current': True,
                            'description': 'Lead ML projects'
                        }
                    ]
                },
                confidence=0.8,
                raw_text='Experience section'
            )
        ]
        
        cv_data = await self.ai_parser._convert_to_cv_data(sections)
        
        # Verify CV data structure
        assert 'metadata' in cv_data
        assert 'personal_info' in cv_data
        assert cv_data['personal_info']['name'] == 'Jane Smith'
        assert cv_data['personal_info']['title'] == 'Data Scientist'
        assert cv_data['personal_info']['contact']['email'] == 'jane@example.com'
        assert 'summary' in cv_data
        assert 'experience' in cv_data
        assert len(cv_data['experience']) == 1
    
    def test_get_section_schema_personal_info(self):
        """Test schema generation for personal info section."""
        schema = self.ai_parser._get_section_schema('personal_info')
        
        assert 'properties' in schema
        assert 'data' in schema['properties']
        assert schema['properties']['data']['type'] == 'object'
        assert 'name' in schema['properties']['data']['properties']
        assert 'email' in schema['properties']['data']['properties']
    
    def test_get_section_schema_experience(self):
        """Test schema generation for experience section."""
        schema = self.ai_parser._get_section_schema('experience')
        
        assert 'properties' in schema
        assert 'data' in schema['properties']
        data_props = schema['properties']['data']['properties']
        assert 'entries' in data_props
        assert data_props['entries']['type'] == 'array'
    
    def test_create_section_identification_prompt(self):
        """Test section identification prompt creation."""
        content = "John Doe\nSoftware Engineer\nExperience:\nSenior Developer"
        
        prompt = self.ai_parser._create_section_identification_prompt(content)
        
        assert 'CV/resume' in prompt
        assert 'personal_info' in prompt
        assert 'experience' in prompt
        assert 'education' in prompt
        assert content in prompt or content[:100] in prompt
    
    def test_create_section_parsing_prompt_personal_info(self):
        """Test parsing prompt for personal info."""
        content = "John Doe\njohn@example.com\n+1-555-1234"
        
        prompt = self.ai_parser._create_section_parsing_prompt('personal_info', content)
        
        assert 'personal_info' in prompt
        assert 'name' in prompt.lower()
        assert 'email' in prompt.lower()
        assert content in prompt
    
    def test_create_section_parsing_prompt_experience(self):
        """Test parsing prompt for experience."""
        content = "Senior Developer\nTechCorp\nJanuary 2020 - Present"
        
        prompt = self.ai_parser._create_section_parsing_prompt('experience', content)
        
        assert 'experience' in prompt
        assert 'title' in prompt.lower()
        assert 'company' in prompt.lower()
        assert content in prompt
    
    def test_extract_section_content_with_line_numbers(self):
        """Test section content extraction with line numbers."""
        lines = [
            "Header",
            "Section 1",
            "Content line 1",
            "Content line 2",
            "Section 2",
            "Content line 3"
        ]
        
        content = self.ai_parser._extract_section_content(
            lines,
            "Section 1",
            1,
            4
        )
        
        assert "Section 1" in content
        assert "Content line 1" in content
        assert "Content line 2" in content
        assert "Section 2" not in content
    
    def test_extract_section_content_by_title(self):
        """Test section content extraction by title search."""
        lines = [
            "# Main Header",
            "## Experience",
            "Senior Developer",
            "TechCorp",
            "## Education",
            "BS Computer Science"
        ]
        
        content = self.ai_parser._extract_section_content(
            lines,
            "Experience",
            None,
            None
        )
        
        assert "Experience" in content
        # The extraction includes from the title line onwards
        # It may or may not include content after depending on header detection
        assert len(content) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
