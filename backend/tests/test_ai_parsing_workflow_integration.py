"""
Integration Tests for AI Parsing Workflow

Tests the complete AI parsing workflow including user confirmation for ambiguities.
Validates Requirements 15.1-15.5.

Feature: cv-web-app
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from app.services.import_service import ImportService
from app.llm.ai_parser import AIParser
from app.llm.providers.base import BaseLLMProvider, LLMConfig, StructuredLLMResponse
from app.models.llm_models import (
    AIParsingRequest,
    AIParsingResult,
    ParsedSection,
    ParsingAmbiguity
)
from app.models.cv_models import CVModel


class TestAIParsingWorkflowIntegration:
    """Test complete AI parsing workflow with user confirmation."""
    
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
        self.ai_parser = self.import_service.ai_parser
    
    @pytest.mark.asyncio
    async def test_complete_parsing_workflow_txt_format(self):
        """
        Test complete parsing workflow for TXT format.
        Validates: Requirements 15.1, 15.2, 15.3, 15.4
        """
        # Sample TXT CV content
        txt_content = """John Doe
Software Engineer
john.doe@example.com | +1-555-1234 | San Francisco, CA

SUMMARY
Experienced software engineer with 8 years in web development.

EXPERIENCE
Senior Software Engineer
TechCorp Inc. | San Francisco, CA
January 2020 - Present
- Lead development of microservices architecture
- Improved system performance by 40%

Software Engineer
StartupXYZ | New York, NY
June 2016 - December 2019
- Developed RESTful APIs
- Mentored junior developers

EDUCATION
Bachelor of Science in Computer Science
MIT | Cambridge, MA
2012 - 2016

SKILLS
Programming: Python, JavaScript, Go
Frameworks: Django, React, Node.js
"""
        
        # Mock section identification response
        section_response = StructuredLLMResponse(
            data={
                'sections': [
                    {'type': 'personal_info', 'title': 'Contact', 'confidence': 0.95},
                    {'type': 'summary', 'title': 'Summary', 'confidence': 0.90},
                    {'type': 'experience', 'title': 'Experience', 'confidence': 0.92},
                    {'type': 'education', 'title': 'Education', 'confidence': 0.88},
                    {'type': 'skills', 'title': 'Skills', 'confidence': 0.85}
                ]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=200
        )
        
        # Mock parsing responses for each section
        personal_info_response = StructuredLLMResponse(
            data={
                'data': {
                    'name': 'John Doe',
                    'title': 'Software Engineer',
                    'email': 'john.doe@example.com',
                    'phone': '+1-555-1234',
                    'location': 'San Francisco, CA'
                },
                'confidence': 0.95,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=150
        )
        
        summary_response = StructuredLLMResponse(
            data={
                'data': {
                    'text': 'Experienced software engineer with 8 years in web development.'
                },
                'confidence': 0.90,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=100
        )
        
        experience_response = StructuredLLMResponse(
            data={
                'data': {
                    'entries': [
                        {
                            'title': 'Senior Software Engineer',
                            'company': 'TechCorp Inc.',
                            'location': 'San Francisco, CA',
                            'start_date': 'January 2020',
                            'end_date': None,
                            'current': True,
                            'description': 'Lead development of microservices architecture',
                            'achievements': ['Improved system performance by 40%']
                        },
                        {
                            'title': 'Software Engineer',
                            'company': 'StartupXYZ',
                            'location': 'New York, NY',
                            'start_date': 'June 2016',
                            'end_date': 'December 2019',
                            'current': False,
                            'description': 'Developed RESTful APIs',
                            'achievements': ['Mentored junior developers']
                        }
                    ]
                },
                'confidence': 0.92,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=250
        )
        
        education_response = StructuredLLMResponse(
            data={
                'data': {
                    'entries': [
                        {
                            'degree': 'Bachelor of Science in Computer Science',
                            'institution': 'MIT',
                            'location': 'Cambridge, MA',
                            'start_date': '2012',
                            'end_date': '2016'
                        }
                    ]
                },
                'confidence': 0.88,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=120
        )
        
        skills_response = StructuredLLMResponse(
            data={
                'data': {
                    'categories': [
                        {
                            'name': 'Programming',
                            'skills': ['Python', 'JavaScript', 'Go']
                        },
                        {
                            'name': 'Frameworks',
                            'skills': ['Django', 'React', 'Node.js']
                        }
                    ]
                },
                'confidence': 0.85,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=130
        )
        
        # Mock the LLM provider methods
        self.mock_provider.generate_structured_output = AsyncMock(
            side_effect=[
                section_response,
                personal_info_response,
                summary_response,
                experience_response,
                education_response,
                skills_response
            ]
        )
        
        # Execute complete parsing workflow
        cv_model, parsing_result = await self.import_service.import_from_file_async(
            file_content=txt_content,
            file_format='txt',
            cv_title='John Doe CV',
            use_ai_parsing=True
        )
        
        # Verify CV model was created correctly
        assert isinstance(cv_model, CVModel)
        assert cv_model.personal_info.name == 'John Doe'
        assert cv_model.personal_info.title == 'Software Engineer'
        assert cv_model.personal_info.contact.email == 'john.doe@example.com'
        assert cv_model.personal_info.contact.phone == '+1-555-1234'
        
        # Verify summary
        assert 'Experienced software engineer' in cv_model.summary
        
        # Verify experience entries
        assert len(cv_model.experience) == 2
        assert cv_model.experience[0].title == 'Senior Software Engineer'
        assert cv_model.experience[0].company == 'TechCorp Inc.'
        assert cv_model.experience[0].current is True
        assert cv_model.experience[1].title == 'Software Engineer'
        assert cv_model.experience[1].current is False
        
        # Verify education
        assert len(cv_model.education) == 1
        assert cv_model.education[0].degree == 'Bachelor of Science in Computer Science'
        assert cv_model.education[0].institution == 'MIT'
        
        # Verify skills
        assert len(cv_model.skills.categories) == 2
        
        # Verify parsing result
        assert isinstance(parsing_result, AIParsingResult)
        assert parsing_result.overall_confidence > 0.85
        assert len(parsing_result.ambiguities) == 0
        assert parsing_result.model == 'gpt-4'
        assert parsing_result.provider == 'openai'
    
    @pytest.mark.asyncio
    async def test_parsing_workflow_with_ambiguities(self):
        """
        Test parsing workflow with ambiguities requiring user confirmation.
        Validates: Requirement 15.5
        """
        # Sample content with ambiguous dates
        ambiguous_content = """Jane Smith
Data Scientist

EXPERIENCE
Senior Data Scientist
DataCorp
2020 - Present (or was it 2019?)
Lead ML projects

Data Analyst
AnalyticsCo
2018 - 2020 (approximately)
Performed data analysis
"""
        
        # Mock section identification
        section_response = StructuredLLMResponse(
            data={
                'sections': [
                    {'type': 'personal_info', 'title': 'Contact', 'confidence': 0.90},
                    {'type': 'experience', 'title': 'Experience', 'confidence': 0.85}
                ]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=150
        )
        
        # Mock personal info parsing
        personal_info_response = StructuredLLMResponse(
            data={
                'data': {
                    'name': 'Jane Smith',
                    'title': 'Data Scientist'
                },
                'confidence': 0.90,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=100
        )
        
        # Mock experience parsing with ambiguities
        experience_response = StructuredLLMResponse(
            data={
                'data': {
                    'entries': [
                        {
                            'title': 'Senior Data Scientist',
                            'company': 'DataCorp',
                            'start_date': '2020',  # Ambiguous
                            'current': True,
                            'description': 'Lead ML projects'
                        },
                        {
                            'title': 'Data Analyst',
                            'company': 'AnalyticsCo',
                            'start_date': '2018',
                            'end_date': '2020',
                            'current': False,
                            'description': 'Performed data analysis'
                        }
                    ]
                },
                'confidence': 0.75,
                'ambiguities': [
                    {
                        'field': 'experience[0].start_date',
                        'options': ['2019', '2020'],
                        'context': 'Text mentions "2020 - Present (or was it 2019?)"',
                        'recommendation': '2020'
                    },
                    {
                        'field': 'experience[1].end_date',
                        'options': ['2019', '2020'],
                        'context': 'Text mentions "approximately" for end date',
                        'recommendation': '2020'
                    }
                ]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=200
        )
        
        # Mock the LLM provider methods
        self.mock_provider.generate_structured_output = AsyncMock(
            side_effect=[
                section_response,
                personal_info_response,
                experience_response
            ]
        )
        
        # Execute parsing workflow
        cv_model, parsing_result = await self.import_service.import_from_file_async(
            file_content=ambiguous_content,
            file_format='txt',
            cv_title='Jane Smith CV',
            use_ai_parsing=True
        )
        
        # Verify CV model was created
        assert isinstance(cv_model, CVModel)
        assert cv_model.personal_info.name == 'Jane Smith'
        
        # Verify ambiguities were captured
        assert isinstance(parsing_result, AIParsingResult)
        assert len(parsing_result.ambiguities) == 2
        
        # Verify first ambiguity
        ambiguity1 = parsing_result.ambiguities[0]
        assert ambiguity1.field == 'experience[0].start_date'
        assert '2019' in ambiguity1.options
        assert '2020' in ambiguity1.options
        assert ambiguity1.recommendation == '2020'
        assert 'or was it 2019' in ambiguity1.context
        
        # Verify second ambiguity
        ambiguity2 = parsing_result.ambiguities[1]
        assert ambiguity2.field == 'experience[1].end_date'
        assert 'approximately' in ambiguity2.context
        
        # Verify confidence is lower due to ambiguities
        assert parsing_result.overall_confidence < 0.90
    
    @pytest.mark.asyncio
    async def test_parsing_workflow_docx_format(self):
        """
        Test parsing workflow for DOCX format.
        Validates: Requirement 15.1
        """
        # Simulate DOCX content (would be extracted text)
        docx_content = """CURRICULUM VITAE

Robert Johnson
Senior Product Manager
robert.johnson@email.com

PROFESSIONAL SUMMARY
Product manager with 10+ years experience in tech industry.

WORK HISTORY
Product Manager | TechGiant Corp | 2018-Present
Led product strategy for enterprise solutions

Associate Product Manager | StartupInc | 2014-2018
Managed product roadmap and feature prioritization
"""
        
        # Mock responses
        section_response = StructuredLLMResponse(
            data={
                'sections': [
                    {'type': 'personal_info', 'title': 'Header', 'confidence': 0.92},
                    {'type': 'summary', 'title': 'Professional Summary', 'confidence': 0.88},
                    {'type': 'experience', 'title': 'Work History', 'confidence': 0.90}
                ]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=180
        )
        
        personal_response = StructuredLLMResponse(
            data={
                'data': {
                    'name': 'Robert Johnson',
                    'title': 'Senior Product Manager',
                    'email': 'robert.johnson@email.com'
                },
                'confidence': 0.92,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=120
        )
        
        summary_response = StructuredLLMResponse(
            data={
                'data': {
                    'text': 'Product manager with 10+ years experience in tech industry.'
                },
                'confidence': 0.88,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=90
        )
        
        experience_response = StructuredLLMResponse(
            data={
                'data': {
                    'entries': [
                        {
                            'title': 'Product Manager',
                            'company': 'TechGiant Corp',
                            'start_date': '2018',
                            'current': True,
                            'description': 'Led product strategy for enterprise solutions'
                        },
                        {
                            'title': 'Associate Product Manager',
                            'company': 'StartupInc',
                            'start_date': '2014',
                            'end_date': '2018',
                            'current': False,
                            'description': 'Managed product roadmap and feature prioritization'
                        }
                    ]
                },
                'confidence': 0.90,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=180
        )
        
        self.mock_provider.generate_structured_output = AsyncMock(
            side_effect=[
                section_response,
                personal_response,
                summary_response,
                experience_response
            ]
        )
        
        # Execute parsing for DOCX
        cv_model, parsing_result = await self.import_service.import_from_file_async(
            file_content=docx_content,
            file_format='docx',
            cv_title='Robert Johnson CV',
            use_ai_parsing=True
        )
        
        # Verify successful parsing
        assert isinstance(cv_model, CVModel)
        assert cv_model.personal_info.name == 'Robert Johnson'
        assert cv_model.personal_info.title == 'Senior Product Manager'
        assert len(cv_model.experience) == 2
        assert parsing_result.overall_confidence > 0.85
    
    @pytest.mark.asyncio
    async def test_parsing_workflow_with_inconsistent_formatting(self):
        """
        Test parsing with inconsistent formatting.
        Validates: Requirement 15.3
        """
        # Content with inconsistent formatting
        inconsistent_content = """Maria Garcia
email: maria.garcia@company.com

---EXPERIENCE---
Software Developer @ DevShop (2019-now)
Building web apps

Junior Developer, CodeFactory, 2017 to 2019
Learned programming

EDUCATION
Computer Science degree from State University (graduated 2017)
"""
        
        # Mock responses for inconsistent formatting
        section_response = StructuredLLMResponse(
            data={
                'sections': [
                    {'type': 'personal_info', 'title': 'Header', 'confidence': 0.85},
                    {'type': 'experience', 'title': 'Experience', 'confidence': 0.80},
                    {'type': 'education', 'title': 'Education', 'confidence': 0.82}
                ]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=160
        )
        
        personal_response = StructuredLLMResponse(
            data={
                'data': {
                    'name': 'Maria Garcia',
                    'email': 'maria.garcia@company.com'
                },
                'confidence': 0.85,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=100
        )
        
        experience_response = StructuredLLMResponse(
            data={
                'data': {
                    'entries': [
                        {
                            'title': 'Software Developer',
                            'company': 'DevShop',
                            'start_date': '2019',
                            'current': True,
                            'description': 'Building web apps'
                        },
                        {
                            'title': 'Junior Developer',
                            'company': 'CodeFactory',
                            'start_date': '2017',
                            'end_date': '2019',
                            'current': False,
                            'description': 'Learned programming'
                        }
                    ]
                },
                'confidence': 0.80,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=170
        )
        
        education_response = StructuredLLMResponse(
            data={
                'data': {
                    'entries': [
                        {
                            'degree': 'Computer Science degree',
                            'institution': 'State University',
                            'end_date': '2017'
                        }
                    ]
                },
                'confidence': 0.82,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=110
        )
        
        self.mock_provider.generate_structured_output = AsyncMock(
            side_effect=[
                section_response,
                personal_response,
                experience_response,
                education_response
            ]
        )
        
        # Execute parsing with inconsistent formatting
        cv_model, parsing_result = await self.import_service.import_from_file_async(
            file_content=inconsistent_content,
            file_format='txt',
            cv_title='Maria Garcia CV',
            use_ai_parsing=True
        )
        
        # Verify AI successfully parsed despite inconsistent formatting
        assert isinstance(cv_model, CVModel)
        assert cv_model.personal_info.name == 'Maria Garcia'
        assert len(cv_model.experience) == 2
        assert cv_model.experience[0].company == 'DevShop'
        assert cv_model.experience[1].company == 'CodeFactory'
        assert len(cv_model.education) == 1
        
        # Confidence may be lower but parsing should succeed
        assert parsing_result.overall_confidence > 0.70
    
    @pytest.mark.asyncio
    async def test_parsing_workflow_error_handling(self):
        """
        Test error handling in parsing workflow.
        Validates: Requirement 15.2
        """
        # Content that's difficult to parse
        difficult_content = """Some random text
Not really a CV
Just some words"""
        
        # Mock low confidence response
        section_response = StructuredLLMResponse(
            data={
                'sections': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=80
        )
        
        self.mock_provider.generate_structured_output = AsyncMock(
            return_value=section_response
        )
        
        # Attempt parsing - should handle gracefully
        with pytest.raises(Exception) as exc_info:
            await self.import_service.import_from_file_async(
                file_content=difficult_content,
                file_format='txt',
                cv_title='Invalid CV',
                use_ai_parsing=True
            )
        
        # Verify appropriate error message
        error_msg = str(exc_info.value)
        assert ("Could not identify" in error_msg or 
                "No sections" in error_msg or 
                "confidence too low" in error_msg)
    
    @pytest.mark.asyncio
    async def test_parsing_workflow_entity_extraction_accuracy(self):
        """
        Test accurate entity extraction (dates, titles, companies).
        Validates: Requirement 15.4
        """
        # Content with various date formats and entities
        entity_content = """Dr. Sarah Chen, PhD
Chief Technology Officer
sarah.chen@techcorp.com | (555) 123-4567

EXPERIENCE
Chief Technology Officer
TechCorp International, Inc.
San Francisco, CA
Jan 2021 - Present
Leading technology strategy and innovation

VP of Engineering
StartupXYZ Ltd.
New York, NY
March 2018 - December 2020
Managed engineering team of 50+

EDUCATION
Ph.D. in Computer Science
Stanford University, Palo Alto, CA
September 2014 - June 2018
Dissertation: Machine Learning Applications

M.S. Computer Science
UC Berkeley, Berkeley, CA
2012-2014
"""
        
        # Mock responses with accurate entity extraction
        section_response = StructuredLLMResponse(
            data={
                'sections': [
                    {'type': 'personal_info', 'title': 'Header', 'confidence': 0.95},
                    {'type': 'experience', 'title': 'Experience', 'confidence': 0.93},
                    {'type': 'education', 'title': 'Education', 'confidence': 0.91}
                ]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=200
        )
        
        personal_response = StructuredLLMResponse(
            data={
                'data': {
                    'name': 'Dr. Sarah Chen',
                    'title': 'Chief Technology Officer',
                    'email': 'sarah.chen@techcorp.com',
                    'phone': '(555) 123-4567'
                },
                'confidence': 0.95,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=130
        )
        
        experience_response = StructuredLLMResponse(
            data={
                'data': {
                    'entries': [
                        {
                            'title': 'Chief Technology Officer',
                            'company': 'TechCorp International, Inc.',
                            'location': 'San Francisco, CA',
                            'start_date': 'January 2021',
                            'end_date': None,
                            'current': True,
                            'description': 'Leading technology strategy and innovation'
                        },
                        {
                            'title': 'VP of Engineering',
                            'company': 'StartupXYZ Ltd.',
                            'location': 'New York, NY',
                            'start_date': 'March 2018',
                            'end_date': 'December 2020',
                            'current': False,
                            'description': 'Managed engineering team of 50+'
                        }
                    ]
                },
                'confidence': 0.93,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=220
        )
        
        education_response = StructuredLLMResponse(
            data={
                'data': {
                    'entries': [
                        {
                            'degree': 'Ph.D. in Computer Science',
                            'institution': 'Stanford University',
                            'location': 'Palo Alto, CA',
                            'start_date': 'September 2014',
                            'end_date': 'June 2018',
                            'description': 'Dissertation: Machine Learning Applications'
                        },
                        {
                            'degree': 'M.S. Computer Science',
                            'institution': 'UC Berkeley',
                            'location': 'Berkeley, CA',
                            'start_date': '2012',
                            'end_date': '2014'
                        }
                    ]
                },
                'confidence': 0.91,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=190
        )
        
        self.mock_provider.generate_structured_output = AsyncMock(
            side_effect=[
                section_response,
                personal_response,
                experience_response,
                education_response
            ]
        )
        
        # Execute parsing
        cv_model, parsing_result = await self.import_service.import_from_file_async(
            file_content=entity_content,
            file_format='txt',
            cv_title='Dr. Sarah Chen CV',
            use_ai_parsing=True
        )
        
        # Verify accurate entity extraction
        assert cv_model.personal_info.name == 'Dr. Sarah Chen'
        assert cv_model.personal_info.title == 'Chief Technology Officer'
        assert cv_model.personal_info.contact.email == 'sarah.chen@techcorp.com'
        assert cv_model.personal_info.contact.phone == '(555) 123-4567'
        
        # Verify experience entities
        assert len(cv_model.experience) == 2
        exp1 = cv_model.experience[0]
        assert exp1.title == 'Chief Technology Officer'
        assert exp1.company == 'TechCorp International, Inc.'
        assert exp1.location == 'San Francisco, CA'
        assert 'January 2021' in exp1.start_date
        assert exp1.current is True
        
        exp2 = cv_model.experience[1]
        assert exp2.title == 'VP of Engineering'
        assert 'March 2018' in exp2.start_date
        assert 'December 2020' in exp2.end_date
        
        # Verify education entities
        assert len(cv_model.education) == 2
        edu1 = cv_model.education[0]
        assert 'Ph.D.' in edu1.degree
        assert edu1.institution == 'Stanford University'
        assert 'September 2014' in edu1.start_date
        assert 'June 2018' in edu1.end_date
        
        # High confidence due to clear formatting
        assert parsing_result.overall_confidence > 0.90
    
    @pytest.mark.asyncio
    async def test_parsing_workflow_without_llm_provider(self):
        """
        Test that parsing workflow requires LLM provider.
        Validates: Requirement 15.1
        """
        # Create import service without LLM provider
        service_no_llm = ImportService()
        
        # Attempt AI parsing without provider
        with pytest.raises(Exception) as exc_info:
            await service_no_llm.import_from_file_async(
                file_content="Some CV content",
                file_format='txt',
                cv_title='Test CV',
                use_ai_parsing=True
            )
        
        # Verify appropriate error
        assert "AI parsing not available" in str(exc_info.value) or "LLM provider" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_parsing_workflow_fallback_to_traditional(self):
        """
        Test fallback to traditional parsing when AI parsing fails.
        Validates: Requirement 15.2
        """
        # Markdown content that can be parsed traditionally
        markdown_content = """---
title: Test CV
---

# John Smith

Software Engineer

john@example.com

## Experience

### Developer
**TechCo** | 2020 - Present

Building applications
"""
        
        # Mock AI parsing failure
        self.mock_provider.generate_structured_output = AsyncMock(
            side_effect=Exception("LLM service unavailable")
        )
        
        # Should fall back to traditional markdown parsing
        cv_model, parsing_result = await self.import_service.import_from_file_async(
            file_content=markdown_content,
            file_format='markdown',
            cv_title='John Smith CV',
            use_ai_parsing=False  # Explicitly use traditional parsing
        )
        
        # Verify traditional parsing succeeded
        assert isinstance(cv_model, CVModel)
        assert cv_model.personal_info.name == 'John Smith'
        assert parsing_result is None  # No AI parsing result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
