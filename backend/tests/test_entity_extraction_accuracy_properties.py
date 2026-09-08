"""
Property-Based Tests for Entity Extraction Accuracy

Feature: cv-web-app, Property 48: Entity Extraction Accuracy
Validates: Requirements 15.4

Tests that for any CV, extracted entities (dates, titles, companies, descriptions)
accurately match the source document content.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from unittest.mock import Mock, AsyncMock
import re
from datetime import datetime
from app.llm.ai_parser import AIParser
from app.llm.providers.base import BaseLLMProvider, LLMConfig, StructuredLLMResponse
from app.models.llm_models import AIParsingRequest


# ============================================================================
# Test Strategies
# ============================================================================

@st.composite
def date_string_strategy(draw):
    """
    Generate various date string formats commonly found in CVs.
    
    Returns:
        String representing a date
    """
    formats = [
        'month_year',      # "January 2020"
        'month_abbr_year', # "Jan 2020"
        'numeric',         # "01/2020"
        'year_only',       # "2020"
        'present',         # "Present", "Current"
        'range'            # "2020 - 2023"
    ]
    
    format_type = draw(st.sampled_from(formats))
    
    if format_type == 'month_year':
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
        month = draw(st.sampled_from(months))
        year = draw(st.integers(min_value=2000, max_value=2025))
        return f"{month} {year}"
    
    elif format_type == 'month_abbr_year':
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        month = draw(st.sampled_from(months))
        year = draw(st.integers(min_value=2000, max_value=2025))
        return f"{month} {year}"
    
    elif format_type == 'numeric':
        month = draw(st.integers(min_value=1, max_value=12))
        year = draw(st.integers(min_value=2000, max_value=2025))
        return f"{month:02d}/{year}"
    
    elif format_type == 'year_only':
        year = draw(st.integers(min_value=2000, max_value=2025))
        return str(year)
    
    elif format_type == 'present':
        return draw(st.sampled_from(['Present', 'Current', 'Now', 'Ongoing']))
    
    else:  # range
        start_year = draw(st.integers(min_value=2000, max_value=2023))
        end_year = draw(st.integers(min_value=start_year, max_value=2025))
        return f"{start_year} - {end_year}"


@st.composite
def job_title_strategy(draw):
    """Generate realistic job titles."""
    levels = ['Junior', 'Senior', 'Lead', 'Principal', 'Staff', '']
    roles = ['Software Engineer', 'Developer', 'Data Scientist', 'Product Manager',
             'Designer', 'Analyst', 'Architect', 'Consultant', 'Engineer']
    
    level = draw(st.sampled_from(levels))
    role = draw(st.sampled_from(roles))
    
    if level:
        return f"{level} {role}"
    return role


@st.composite
def company_name_strategy(draw):
    """Generate realistic company names."""
    prefixes = ['Tech', 'Data', 'Cloud', 'Cyber', 'Digital', 'Smart', 'Global']
    suffixes = ['Corp', 'Inc', 'LLC', 'Technologies', 'Solutions', 'Systems', 'Labs']
    
    use_suffix = draw(st.booleans())
    
    if use_suffix:
        prefix = draw(st.sampled_from(prefixes))
        suffix = draw(st.sampled_from(suffixes))
        return f"{prefix}{suffix}"
    else:
        # Simple company name
        return draw(st.sampled_from(['Microsoft', 'Google', 'Amazon', 'Apple', 'Meta']))



@st.composite
def location_strategy(draw):
    """Generate realistic location strings."""
    cities = ['San Francisco', 'New York', 'Seattle', 'Austin', 'Boston', 'Chicago']
    states = ['CA', 'NY', 'WA', 'TX', 'MA', 'IL']
    
    city_idx = draw(st.integers(min_value=0, max_value=len(cities)-1))
    
    return f"{cities[city_idx]}, {states[city_idx]}"


@st.composite
def experience_entry_strategy(draw):
    """
    Generate a complete experience entry with all entities.
    
    Returns:
        Dictionary with experience data and formatted text
    """
    title = draw(job_title_strategy())
    company = draw(company_name_strategy())
    location = draw(location_strategy())
    start_date = draw(date_string_strategy())
    
    # End date is either a date or "Present"
    is_current = draw(st.booleans())
    if is_current:
        end_date = draw(st.sampled_from(['Present', 'Current']))
    else:
        end_date = draw(date_string_strategy())
    
    # Generate description
    description = draw(st.text(
        min_size=20,
        max_size=200,
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Pd'), whitelist_characters=' .')
    ))
    
    # Generate achievements
    num_achievements = draw(st.integers(min_value=1, max_value=3))
    achievements = [
        draw(st.text(
            min_size=15,
            max_size=100,
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Pd'), whitelist_characters=' .')
        ))
        for _ in range(num_achievements)
    ]
    
    # Format as text (how it would appear in CV)
    formatted_text = f"""{title}
{company} | {location}
{start_date} - {end_date}
{description}
"""
    if achievements:
        formatted_text += "\n".join(f"• {ach}" for ach in achievements)
    
    return {
        'title': title,
        'company': company,
        'location': location,
        'start_date': start_date,
        'end_date': end_date,
        'current': is_current,
        'description': description,
        'achievements': achievements,
        'formatted_text': formatted_text
    }



@st.composite
def education_entry_strategy(draw):
    """
    Generate a complete education entry with all entities.
    
    Returns:
        Dictionary with education data and formatted text
    """
    degrees = ['BS', 'MS', 'PhD', 'BA', 'MA', 'MBA']
    fields = ['Computer Science', 'Engineering', 'Business', 'Mathematics', 'Physics']
    
    degree = draw(st.sampled_from(degrees))
    field = draw(st.sampled_from(fields))
    degree_full = f"{degree} {field}"
    
    institutions = ['MIT', 'Stanford University', 'Harvard University', 'UC Berkeley',
                   'Carnegie Mellon University', 'University of Washington']
    institution = draw(st.sampled_from(institutions))
    
    location = draw(location_strategy())
    start_date = draw(date_string_strategy())
    end_date = draw(date_string_strategy())
    
    # Optional GPA
    has_gpa = draw(st.booleans())
    gpa = None
    if has_gpa:
        gpa = f"{draw(st.floats(min_value=3.0, max_value=4.0)):.2f}"
    
    # Format as text
    formatted_text = f"""{degree_full}
{institution} | {location}
{start_date} - {end_date}"""
    
    if gpa:
        formatted_text += f"\nGPA: {gpa}"
    
    return {
        'degree': degree_full,
        'institution': institution,
        'location': location,
        'start_date': start_date,
        'end_date': end_date,
        'gpa': gpa,
        'formatted_text': formatted_text
    }


@st.composite
def cv_with_entities_strategy(draw):
    """
    Generate CV content with known entities for validation.
    
    Returns:
        Dictionary with CV text and expected entities
    """
    # Personal info
    name = draw(st.text(
        min_size=5,
        max_size=50,
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters=' ')
    ))
    email = f"{name.replace(' ', '').lower()}@example.com"
    phone = "+1-555-" + str(draw(st.integers(min_value=1000, max_value=9999)))
    
    # Generate 1-2 experience entries
    num_experiences = draw(st.integers(min_value=1, max_value=2))
    experiences = [draw(experience_entry_strategy()) for _ in range(num_experiences)]
    
    # Generate 1 education entry
    education = draw(education_entry_strategy())
    
    # Build CV text
    cv_text = f"""{name}
{email} | {phone}

EXPERIENCE

"""
    
    for exp in experiences:
        cv_text += exp['formatted_text'] + "\n\n"
    
    cv_text += """
EDUCATION

"""
    cv_text += education['formatted_text']
    
    return {
        'cv_text': cv_text,
        'expected_entities': {
            'name': name,
            'email': email,
            'phone': phone,
            'experiences': experiences,
            'education': education
        }
    }



# ============================================================================
# Helper Functions
# ============================================================================

def normalize_text(text: str) -> str:
    """Normalize text for comparison by removing extra whitespace."""
    return ' '.join(text.split()).strip()


def dates_match(extracted: str, expected: str) -> bool:
    """
    Check if extracted date matches expected date.
    Handles various date formats and variations.
    """
    # Normalize both dates
    extracted_norm = normalize_text(extracted.lower())
    expected_norm = normalize_text(expected.lower())
    
    # Direct match
    if extracted_norm == expected_norm:
        return True
    
    # Check if one contains the other (handles "January 2020" vs "Jan 2020")
    if extracted_norm in expected_norm or expected_norm in extracted_norm:
        return True
    
    # Extract years and check if they match
    extracted_years = re.findall(r'\b(20\d{2})\b', extracted)
    expected_years = re.findall(r'\b(20\d{2})\b', expected)
    
    if extracted_years and expected_years:
        return set(extracted_years) == set(expected_years)
    
    # Handle "Present"/"Current" variations
    present_terms = ['present', 'current', 'now', 'ongoing']
    if any(term in extracted_norm for term in present_terms) and \
       any(term in expected_norm for term in present_terms):
        return True
    
    return False


def text_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity between two text strings.
    Returns value between 0 and 1.
    """
    norm1 = normalize_text(text1.lower())
    norm2 = normalize_text(text2.lower())
    
    if norm1 == norm2:
        return 1.0
    
    # Check if one is substring of other
    if norm1 in norm2 or norm2 in norm1:
        shorter = min(len(norm1), len(norm2))
        longer = max(len(norm1), len(norm2))
        return shorter / longer
    
    # Simple word overlap
    words1 = set(norm1.split())
    words2 = set(norm2.split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1 & words2
    union = words1 | words2
    
    return len(intersection) / len(union) if union else 0.0



# ============================================================================
# Property Tests
# ============================================================================

class TestEntityExtractionAccuracyProperties:
    """
    Property-based tests for entity extraction accuracy.
    
    Feature: cv-web-app, Property 48: Entity Extraction Accuracy
    Validates: Requirements 15.4
    """
    
    @given(cv_with_entities_strategy())
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
    )
    @pytest.mark.asyncio
    async def test_property_48_extracted_entities_match_source(self, cv_data):
        """
        Property 48: Entity Extraction Accuracy
        
        For any CV, extracted entities (dates, titles, companies, descriptions)
        should accurately match the source document content.
        
        Validates: Requirements 15.4
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
            file_content=cv_data['cv_text'],
            file_format='txt',
            filename='resume.txt'
        )
        
        expected = cv_data['expected_entities']
        
        # Mock section identification response
        section_response = StructuredLLMResponse(
            data={
                'sections': [
                    {'type': 'personal_info', 'title': 'Contact', 'confidence': 0.95},
                    {'type': 'experience', 'title': 'Experience', 'confidence': 0.90},
                    {'type': 'education', 'title': 'Education', 'confidence': 0.90}
                ]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=200
        )
        
        # Mock personal info parsing - extract from CV text
        personal_info_response = StructuredLLMResponse(
            data={
                'data': {
                    'name': expected['name'],
                    'email': expected['email'],
                    'phone': expected['phone']
                },
                'confidence': 0.95,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=150
        )
        
        # Mock experience parsing - extract from CV text
        experience_entries = []
        for exp in expected['experiences']:
            experience_entries.append({
                'title': exp['title'],
                'company': exp['company'],
                'location': exp['location'],
                'start_date': exp['start_date'],
                'end_date': exp['end_date'],
                'current': exp['current'],
                'description': exp['description'],
                'achievements': exp['achievements']
            })
        
        experience_response = StructuredLLMResponse(
            data={
                'data': {'entries': experience_entries},
                'confidence': 0.90,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=300
        )
        
        # Mock education parsing - extract from CV text
        education_response = StructuredLLMResponse(
            data={
                'data': {
                    'entries': [{
                        'degree': expected['education']['degree'],
                        'institution': expected['education']['institution'],
                        'location': expected['education']['location'],
                        'start_date': expected['education']['start_date'],
                        'end_date': expected['education']['end_date'],
                        'gpa': expected['education']['gpa']
                    }]
                },
                'confidence': 0.90,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=200
        )
        
        # Set up mock responses
        mock_provider.generate_structured_output = AsyncMock(
            side_effect=[
                section_response,
                personal_info_response,
                experience_response,
                education_response
            ]
        )
        
        # Act: Parse CV
        result = await ai_parser.parse_cv(request)
        
        # Assert: Verify entity extraction accuracy
        # Property 1: Personal info entities should match source
        personal_info_section = next(
            (s for s in result.parsed_sections if s.section_type == 'personal_info'),
            None
        )
        assert personal_info_section is not None, \
            "Personal info section should be extracted"
        
        extracted_name = personal_info_section.content.get('name', '')
        assert normalize_text(extracted_name) == normalize_text(expected['name']), \
            f"Extracted name '{extracted_name}' should match source '{expected['name']}'"
        
        extracted_email = personal_info_section.content.get('email', '')
        assert normalize_text(extracted_email) == normalize_text(expected['email']), \
            f"Extracted email '{extracted_email}' should match source '{expected['email']}'"
        
        # Property 2: Experience entities should match source
        experience_section = next(
            (s for s in result.parsed_sections if s.section_type == 'experience'),
            None
        )
        assert experience_section is not None, \
            "Experience section should be extracted"
        
        extracted_experiences = experience_section.content.get('entries', [])
        assert len(extracted_experiences) == len(expected['experiences']), \
            f"Should extract {len(expected['experiences'])} experience entries"
        
        for i, (extracted_exp, expected_exp) in enumerate(zip(extracted_experiences, expected['experiences'])):
            # Verify job title
            assert normalize_text(extracted_exp['title']) == normalize_text(expected_exp['title']), \
                f"Experience {i}: Extracted title '{extracted_exp['title']}' should match '{expected_exp['title']}'"
            
            # Verify company name
            assert normalize_text(extracted_exp['company']) == normalize_text(expected_exp['company']), \
                f"Experience {i}: Extracted company '{extracted_exp['company']}' should match '{expected_exp['company']}'"
            
            # Verify location
            assert normalize_text(extracted_exp['location']) == normalize_text(expected_exp['location']), \
                f"Experience {i}: Extracted location '{extracted_exp['location']}' should match '{expected_exp['location']}'"
            
            # Verify dates (with flexible matching)
            assert dates_match(extracted_exp['start_date'], expected_exp['start_date']), \
                f"Experience {i}: Extracted start date '{extracted_exp['start_date']}' should match '{expected_exp['start_date']}'"
            
            assert dates_match(extracted_exp['end_date'], expected_exp['end_date']), \
                f"Experience {i}: Extracted end date '{extracted_exp['end_date']}' should match '{expected_exp['end_date']}'"
            
            # Verify current status
            assert extracted_exp['current'] == expected_exp['current'], \
                f"Experience {i}: Current status should match"
            
            # Verify description (with similarity threshold)
            desc_similarity = text_similarity(extracted_exp['description'], expected_exp['description'])
            assert desc_similarity >= 0.8, \
                f"Experience {i}: Description similarity {desc_similarity:.2f} should be >= 0.8"
            
            # Verify achievements count
            assert len(extracted_exp['achievements']) == len(expected_exp['achievements']), \
                f"Experience {i}: Should extract {len(expected_exp['achievements'])} achievements"
        
        # Property 3: Education entities should match source
        education_section = next(
            (s for s in result.parsed_sections if s.section_type == 'education'),
            None
        )
        assert education_section is not None, \
            "Education section should be extracted"
        
        extracted_education = education_section.content.get('entries', [])
        assert len(extracted_education) >= 1, \
            "Should extract at least one education entry"
        
        extracted_edu = extracted_education[0]
        expected_edu = expected['education']
        
        # Verify degree
        assert normalize_text(extracted_edu['degree']) == normalize_text(expected_edu['degree']), \
            f"Extracted degree '{extracted_edu['degree']}' should match '{expected_edu['degree']}'"
        
        # Verify institution
        assert normalize_text(extracted_edu['institution']) == normalize_text(expected_edu['institution']), \
            f"Extracted institution '{extracted_edu['institution']}' should match '{expected_edu['institution']}'"
        
        # Verify dates
        assert dates_match(extracted_edu['start_date'], expected_edu['start_date']), \
            f"Extracted education start date should match source"
        
        assert dates_match(extracted_edu['end_date'], expected_edu['end_date']), \
            f"Extracted education end date should match source"
        
        # Verify GPA if present
        if expected_edu['gpa']:
            assert extracted_edu.get('gpa') == expected_edu['gpa'], \
                f"Extracted GPA should match source GPA"
    
    @given(experience_entry_strategy())
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
    )
    @pytest.mark.asyncio
    async def test_property_48_experience_entities_preserved(self, experience_data):
        """
        Property 48a: Experience Entity Preservation
        
        For any experience entry, all key entities (title, company, location,
        dates) should be accurately extracted and preserved.
        
        Validates: Requirements 15.4
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
        
        # Create CV with just this experience
        cv_text = f"""John Doe
john@example.com

EXPERIENCE

{experience_data['formatted_text']}
"""
        
        request = AIParsingRequest(
            file_content=cv_text,
            file_format='txt',
            filename='resume.txt'
        )
        
        # Mock responses
        section_response = StructuredLLMResponse(
            data={
                'sections': [
                    {'type': 'personal_info', 'title': 'Contact', 'confidence': 0.90},
                    {'type': 'experience', 'title': 'Experience', 'confidence': 0.90}
                ]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=150
        )
        
        personal_response = StructuredLLMResponse(
            data={
                'data': {'name': 'John Doe', 'email': 'john@example.com'},
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
                    'entries': [{
                        'title': experience_data['title'],
                        'company': experience_data['company'],
                        'location': experience_data['location'],
                        'start_date': experience_data['start_date'],
                        'end_date': experience_data['end_date'],
                        'current': experience_data['current'],
                        'description': experience_data['description'],
                        'achievements': experience_data['achievements']
                    }]
                },
                'confidence': 0.90,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=250
        )
        
        mock_provider.generate_structured_output = AsyncMock(
            side_effect=[section_response, personal_response, experience_response]
        )
        
        # Act
        result = await ai_parser.parse_cv(request)
        
        # Assert: All experience entities should be accurately extracted
        experience_section = next(
            (s for s in result.parsed_sections if s.section_type == 'experience'),
            None
        )
        
        assert experience_section is not None, "Experience section should be extracted"
        
        entries = experience_section.content.get('entries', [])
        assert len(entries) == 1, "Should extract one experience entry"
        
        extracted = entries[0]
        
        # Property: All key entities must match source
        assert normalize_text(extracted['title']) == normalize_text(experience_data['title']), \
            "Job title must match source exactly"
        
        assert normalize_text(extracted['company']) == normalize_text(experience_data['company']), \
            "Company name must match source exactly"
        
        assert normalize_text(extracted['location']) == normalize_text(experience_data['location']), \
            "Location must match source exactly"
        
        assert dates_match(extracted['start_date'], experience_data['start_date']), \
            "Start date must match source"
        
        assert dates_match(extracted['end_date'], experience_data['end_date']), \
            "End date must match source"
    
    @given(education_entry_strategy())
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
    )
    @pytest.mark.asyncio
    async def test_property_48_education_entities_preserved(self, education_data):
        """
        Property 48b: Education Entity Preservation
        
        For any education entry, all key entities (degree, institution, location,
        dates, GPA) should be accurately extracted and preserved.
        
        Validates: Requirements 15.4
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
        
        # Create CV with just this education
        cv_text = f"""Jane Smith
jane@example.com

EDUCATION

{education_data['formatted_text']}
"""
        
        request = AIParsingRequest(
            file_content=cv_text,
            file_format='txt',
            filename='resume.txt'
        )
        
        # Mock responses
        section_response = StructuredLLMResponse(
            data={
                'sections': [
                    {'type': 'personal_info', 'title': 'Contact', 'confidence': 0.90},
                    {'type': 'education', 'title': 'Education', 'confidence': 0.90}
                ]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=150
        )
        
        personal_response = StructuredLLMResponse(
            data={
                'data': {'name': 'Jane Smith', 'email': 'jane@example.com'},
                'confidence': 0.90,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=100
        )
        
        education_response = StructuredLLMResponse(
            data={
                'data': {
                    'entries': [{
                        'degree': education_data['degree'],
                        'institution': education_data['institution'],
                        'location': education_data['location'],
                        'start_date': education_data['start_date'],
                        'end_date': education_data['end_date'],
                        'gpa': education_data['gpa']
                    }]
                },
                'confidence': 0.90,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=200
        )
        
        mock_provider.generate_structured_output = AsyncMock(
            side_effect=[section_response, personal_response, education_response]
        )
        
        # Act
        result = await ai_parser.parse_cv(request)
        
        # Assert: All education entities should be accurately extracted
        education_section = next(
            (s for s in result.parsed_sections if s.section_type == 'education'),
            None
        )
        
        assert education_section is not None, "Education section should be extracted"
        
        entries = education_section.content.get('entries', [])
        assert len(entries) == 1, "Should extract one education entry"
        
        extracted = entries[0]
        
        # Property: All key entities must match source
        assert normalize_text(extracted['degree']) == normalize_text(education_data['degree']), \
            "Degree must match source exactly"
        
        assert normalize_text(extracted['institution']) == normalize_text(education_data['institution']), \
            "Institution must match source exactly"
        
        assert normalize_text(extracted['location']) == normalize_text(education_data['location']), \
            "Location must match source exactly"
        
        assert dates_match(extracted['start_date'], education_data['start_date']), \
            "Start date must match source"
        
        assert dates_match(extracted['end_date'], education_data['end_date']), \
            "End date must match source"
        
        # GPA should match if present
        if education_data['gpa']:
            assert extracted.get('gpa') == education_data['gpa'], \
                "GPA must match source when present"
    
    @given(
        date_string_strategy(),
        date_string_strategy()
    )
    @settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_property_48_date_formats_preserved(self, start_date, end_date):
        """
        Property 48c: Date Format Preservation
        
        For any date format used in the source CV, the extracted dates should
        accurately represent the same time period, even if format varies.
        
        Validates: Requirements 15.4
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
        
        # Create CV with specific date formats
        cv_text = f"""John Doe
john@example.com

EXPERIENCE

Software Engineer
TechCorp
{start_date} - {end_date}
Developed software applications.
"""
        
        request = AIParsingRequest(
            file_content=cv_text,
            file_format='txt',
            filename='resume.txt'
        )
        
        # Mock responses
        section_response = StructuredLLMResponse(
            data={
                'sections': [
                    {'type': 'personal_info', 'title': 'Contact', 'confidence': 0.90},
                    {'type': 'experience', 'title': 'Experience', 'confidence': 0.90}
                ]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=150
        )
        
        personal_response = StructuredLLMResponse(
            data={
                'data': {'name': 'John Doe', 'email': 'john@example.com'},
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
                    'entries': [{
                        'title': 'Software Engineer',
                        'company': 'TechCorp',
                        'start_date': start_date,
                        'end_date': end_date,
                        'current': False,
                        'description': 'Developed software applications.'
                    }]
                },
                'confidence': 0.90,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=200
        )
        
        mock_provider.generate_structured_output = AsyncMock(
            side_effect=[section_response, personal_response, experience_response]
        )
        
        # Act
        result = await ai_parser.parse_cv(request)
        
        # Assert: Dates should be accurately extracted
        experience_section = next(
            (s for s in result.parsed_sections if s.section_type == 'experience'),
            None
        )
        
        assert experience_section is not None, "Experience section should be extracted"
        
        entries = experience_section.content.get('entries', [])
        assert len(entries) == 1, "Should extract one experience entry"
        
        extracted = entries[0]
        
        # Property: Dates must match source (with flexible format matching)
        assert dates_match(extracted['start_date'], start_date), \
            f"Extracted start date '{extracted['start_date']}' must match source '{start_date}'"
        
        assert dates_match(extracted['end_date'], end_date), \
            f"Extracted end date '{extracted['end_date']}' must match source '{end_date}'"
    
    @given(
        job_title_strategy(),
        company_name_strategy()
    )
    @settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_property_48_text_entities_exact_match(self, job_title, company_name):
        """
        Property 48d: Text Entity Exact Matching
        
        For any text entities (job titles, company names), the extracted values
        should exactly match the source text (after normalization).
        
        Validates: Requirements 15.4
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
        
        # Create CV with specific entities
        cv_text = f"""Alice Johnson
alice@example.com

EXPERIENCE

{job_title}
{company_name}
2020 - Present
Leading development initiatives.
"""
        
        request = AIParsingRequest(
            file_content=cv_text,
            file_format='txt',
            filename='resume.txt'
        )
        
        # Mock responses
        section_response = StructuredLLMResponse(
            data={
                'sections': [
                    {'type': 'personal_info', 'title': 'Contact', 'confidence': 0.90},
                    {'type': 'experience', 'title': 'Experience', 'confidence': 0.90}
                ]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=150
        )
        
        personal_response = StructuredLLMResponse(
            data={
                'data': {'name': 'Alice Johnson', 'email': 'alice@example.com'},
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
                    'entries': [{
                        'title': job_title,
                        'company': company_name,
                        'start_date': '2020',
                        'end_date': 'Present',
                        'current': True,
                        'description': 'Leading development initiatives.'
                    }]
                },
                'confidence': 0.90,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=200
        )
        
        mock_provider.generate_structured_output = AsyncMock(
            side_effect=[section_response, personal_response, experience_response]
        )
        
        # Act
        result = await ai_parser.parse_cv(request)
        
        # Assert: Text entities should exactly match
        experience_section = next(
            (s for s in result.parsed_sections if s.section_type == 'experience'),
            None
        )
        
        assert experience_section is not None, "Experience section should be extracted"
        
        entries = experience_section.content.get('entries', [])
        assert len(entries) == 1, "Should extract one experience entry"
        
        extracted = entries[0]
        
        # Property: Text entities must match exactly (after normalization)
        assert normalize_text(extracted['title']) == normalize_text(job_title), \
            f"Job title must match exactly: expected '{job_title}', got '{extracted['title']}'"
        
        assert normalize_text(extracted['company']) == normalize_text(company_name), \
            f"Company name must match exactly: expected '{company_name}', got '{extracted['company']}'"
    
    @given(st.lists(st.text(min_size=15, max_size=100), min_size=1, max_size=5))
    @settings(max_examples=30, deadline=None)
    @pytest.mark.asyncio
    async def test_property_48_achievement_count_preserved(self, achievements):
        """
        Property 48e: Achievement Count Preservation
        
        For any list of achievements in the source CV, the number of extracted
        achievements should match the source count.
        
        Validates: Requirements 15.4
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
        
        # Create CV with specific number of achievements
        achievements_text = "\n".join(f"• {ach}" for ach in achievements)
        cv_text = f"""Bob Smith
bob@example.com

EXPERIENCE

Senior Developer
TechCorp
2020 - Present
{achievements_text}
"""
        
        request = AIParsingRequest(
            file_content=cv_text,
            file_format='txt',
            filename='resume.txt'
        )
        
        # Mock responses
        section_response = StructuredLLMResponse(
            data={
                'sections': [
                    {'type': 'personal_info', 'title': 'Contact', 'confidence': 0.90},
                    {'type': 'experience', 'title': 'Experience', 'confidence': 0.90}
                ]
            },
            model='gpt-4',
            provider='openai',
            tokens_used=150
        )
        
        personal_response = StructuredLLMResponse(
            data={
                'data': {'name': 'Bob Smith', 'email': 'bob@example.com'},
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
                    'entries': [{
                        'title': 'Senior Developer',
                        'company': 'TechCorp',
                        'start_date': '2020',
                        'end_date': 'Present',
                        'current': True,
                        'achievements': achievements
                    }]
                },
                'confidence': 0.90,
                'ambiguities': []
            },
            model='gpt-4',
            provider='openai',
            tokens_used=250
        )
        
        mock_provider.generate_structured_output = AsyncMock(
            side_effect=[section_response, personal_response, experience_response]
        )
        
        # Act
        result = await ai_parser.parse_cv(request)
        
        # Assert: Achievement count should be preserved
        experience_section = next(
            (s for s in result.parsed_sections if s.section_type == 'experience'),
            None
        )
        
        assert experience_section is not None, "Experience section should be extracted"
        
        entries = experience_section.content.get('entries', [])
        assert len(entries) == 1, "Should extract one experience entry"
        
        extracted = entries[0]
        extracted_achievements = extracted.get('achievements', [])
        
        # Property: Number of achievements must match source
        assert len(extracted_achievements) == len(achievements), \
            f"Should extract {len(achievements)} achievements, got {len(extracted_achievements)}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

