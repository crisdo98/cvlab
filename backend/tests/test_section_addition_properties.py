"""
Property-Based Tests for Section Addition

Tests Property 1: Section addition with correct structure
Validates: Requirements 1.3
"""

import pytest
from hypothesis import given, strategies as st, settings

from app.models.cv_models import CVModelV2
from app.models.cv_section_models import (
    SectionType,
    PersonalInfoContent,
    ListSectionContent,
    StructuredSectionContent,
    FreeTextSectionContent,
)
from app.services.section_management_service import SectionManagementService


# Strategy for predefined section types (excluding CUSTOM)
predefined_section_types = st.sampled_from([
    SectionType.PERSONAL_INFO,
    SectionType.SUMMARY,
    SectionType.EXPERIENCE,
    SectionType.EDUCATION,
    SectionType.SKILLS,
    SectionType.LANGUAGES,
    SectionType.SOFTWARE,
    SectionType.CERTIFICATIONS,
    SectionType.ACCOMPLISHMENTS,
    SectionType.AFFILIATIONS,
    SectionType.INTERESTS,
    SectionType.WEBSITES,
])


@pytest.fixture
def service():
    """Create a section management service instance."""
    return SectionManagementService()


@pytest.fixture
def empty_cv():
    """Create an empty CV for testing."""
    return CVModelV2(id="test-cv", sections=[])


@settings(max_examples=100)
@given(section_type=predefined_section_types)
def test_property_section_addition_correct_structure(section_type):
    """
    Property 1: Section addition with correct structure
    
    For any predefined section type, when added to a CV, the section should
    have the appropriate content structure matching its type.
    
    **Validates: Requirements 1.3**
    """
    service = SectionManagementService()
    cv = CVModelV2(id="test-cv", sections=[])
    
    # Add the section
    section = service.add_predefined_section(cv, section_type)
    
    # Verify section was added
    assert section in cv.sections
    assert section.type == section_type
    
    # Verify content structure matches section type
    if section_type == SectionType.PERSONAL_INFO:
        assert isinstance(section.content, PersonalInfoContent)
        assert section.content_structure == "personal"
    elif section_type in [
        SectionType.SKILLS,
        SectionType.LANGUAGES,
        SectionType.SOFTWARE,
        SectionType.INTERESTS
    ]:
        assert isinstance(section.content, ListSectionContent)
        assert section.content_structure == "list"
    elif section_type in [
        SectionType.EXPERIENCE,
        SectionType.EDUCATION,
        SectionType.CERTIFICATIONS
    ]:
        assert isinstance(section.content, StructuredSectionContent)
        assert section.content_structure == "structured"
    elif section_type in [SectionType.SUMMARY, SectionType.ACCOMPLISHMENTS, 
                          SectionType.AFFILIATIONS, SectionType.WEBSITES]:
        assert isinstance(section.content, FreeTextSectionContent)
        assert section.content_structure == "free_text"
    
    # Verify section has required fields
    assert section.id is not None
    assert section.title is not None and len(section.title) > 0
    assert section.visible is True
    assert section.order >= 0
