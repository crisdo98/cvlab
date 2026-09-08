"""
Tests for AI Parser Integration

Tests the integration of AI parser with the import service.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.import_service import ImportService
from app.llm.ai_parser import AIParser
from app.llm.providers.base import BaseLLMProvider, LLMConfig
from app.models.llm_models import AIParsingResult, ParsedSection, AIParsingRequest
from app.models.cv_models import CVModel


class TestAIParserIntegration:
    """Test AI parser integration with import service."""
    
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
        
        # Create import service with mock provider
        self.import_service = ImportService(llm_provider=self.mock_provider)
    
    def test_import_service_with_llm_provider(self):
        """Test that ImportService can be initialized with LLM provider."""
        assert self.import_service.llm_provider is not None
        assert self.import_service.ai_parser is not None
        assert isinstance(self.import_service.ai_parser, AIParser)
    
    def test_import_service_without_llm_provider(self):
        """Test that ImportService can be initialized without LLM provider."""
        service = ImportService()
        assert service.llm_provider is None
        assert service.ai_parser is None
    
    @pytest.mark.asyncio
    async def test_import_from_file_async_markdown(self):
        """Test async import from markdown file."""
        markdown_content = """---
title: Test CV
---

# John Doe

Software Engineer

- john@example.com
- +1-555-1234

## Summary

Experienced software engineer.

## Experience

### Senior Engineer
**TechCorp** | San Francisco, CA
*January 2020 - Present*

Lead development of web applications.

## Skills

- Programming: Python; JavaScript
"""
        
        # Mock AI parsing result
        mock_result = AIParsingResult(
            parsed_sections=[
                ParsedSection(
                    section_type='personal_info',
                    content={
                        'name': 'John Doe',
                        'title': 'Software Engineer',
                        'email': 'john@example.com',
                        'phone': '+1-555-1234'
                    },
                    confidence=0.9,
                    raw_text='# John Doe\nSoftware Engineer'
                )
            ],
            ambiguities=[],
            overall_confidence=0.85,
            cv_data={
                'personal_info': {
                    'name': 'John Doe',
                    'title': 'Software Engineer',
                    'contact': {
                        'email': 'john@example.com',
                        'phone': '+1-555-1234'
                    }
                },
                'summary': 'Experienced software engineer.',
                'experience': [],
                'education': [],
                'skills': {'categories': []},
                'certifications': []
            },
            errors=[],
            model='gpt-4',
            provider='openai'
        )
        
        # Mock the AI parser's parse_cv method
        with patch.object(self.import_service.ai_parser, 'parse_cv', new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = mock_result
            
            # Test import with AI parsing
            cv_model, parsing_result = await self.import_service.import_from_file_async(
                file_content=markdown_content,
                file_format='markdown',
                cv_title='Test CV',
                use_ai_parsing=True
            )
            
            # Verify results
            assert isinstance(cv_model, CVModel)
            assert cv_model.personal_info.name == 'John Doe'
            assert parsing_result is not None
            assert parsing_result.overall_confidence == 0.85
            assert len(parsing_result.ambiguities) == 0
    
    @pytest.mark.asyncio
    async def test_import_from_file_async_pdf_requires_ai(self):
        """Test that PDF import requires AI parsing."""
        service = ImportService()  # No LLM provider
        
        with pytest.raises(Exception) as exc_info:
            await service.import_from_file_async(
                file_content="PDF content",
                file_format='pdf',
                use_ai_parsing=True
            )
        
        assert "AI parsing not available" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_import_from_file_async_low_confidence(self):
        """Test handling of low confidence AI parsing."""
        # Mock AI parsing result with low confidence
        mock_result = AIParsingResult(
            parsed_sections=[],
            ambiguities=[],
            overall_confidence=0.3,  # Low confidence
            cv_data=None,
            errors=['Could not identify sections'],
            model='gpt-4',
            provider='openai'
        )
        
        with patch.object(self.import_service.ai_parser, 'parse_cv', new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = mock_result
            
            with pytest.raises(Exception) as exc_info:
                await self.import_service.import_from_file_async(
                    file_content="Some content",
                    file_format='txt',
                    use_ai_parsing=True
                )
            
            assert "confidence too low" in str(exc_info.value).lower()
    
    def test_convert_ai_parsed_data_to_cv_model(self):
        """Test conversion of AI-parsed data to CV model."""
        ai_data = {
            'metadata': {
                'title': 'Test CV'
            },
            'personal_info': {
                'name': 'Jane Smith',
                'title': 'Data Scientist',
                'contact': {
                    'email': 'jane@example.com',
                    'phone': '+1-555-5678',
                    'linkedin': 'https://linkedin.com/in/janesmith'
                }
            },
            'summary': 'Experienced data scientist with ML expertise.',
            'experience': [
                {
                    'title': 'Senior Data Scientist',
                    'company': 'DataCorp',
                    'location': 'New York, NY',
                    'start_date': 'January 2020',
                    'end_date': None,
                    'current': True,
                    'description': 'Lead ML projects',
                    'achievements': ['Improved model accuracy by 20%']
                }
            ],
            'education': [
                {
                    'degree': 'PhD in Computer Science',
                    'institution': 'MIT',
                    'location': 'Cambridge, MA',
                    'start_date': '2015',
                    'end_date': '2019'
                }
            ],
            'skills': {
                'categories': [
                    {
                        'name': 'Programming',
                        'skills': ['Python', 'R', 'SQL']
                    }
                ]
            },
            'certifications': [
                {
                    'name': 'AWS ML Specialty',
                    'issuer': 'Amazon',
                    'date': 'June 2021'
                }
            ]
        }
        
        cv_model = self.import_service._convert_ai_parsed_data_to_cv_model(ai_data, 'Test CV')
        
        # Verify conversion
        assert isinstance(cv_model, CVModel)
        assert cv_model.metadata.title == 'Test CV'
        assert cv_model.personal_info.name == 'Jane Smith'
        assert cv_model.personal_info.title == 'Data Scientist'
        assert cv_model.personal_info.contact.email == 'jane@example.com'
        assert cv_model.summary == 'Experienced data scientist with ML expertise.'
        assert len(cv_model.experience) == 1
        assert cv_model.experience[0].title == 'Senior Data Scientist'
        assert cv_model.experience[0].current is True
        assert len(cv_model.education) == 1
        assert cv_model.education[0].degree == 'PhD in Computer Science'
        assert len(cv_model.skills.categories) == 1
        assert len(cv_model.certifications) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
