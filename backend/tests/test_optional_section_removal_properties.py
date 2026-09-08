"""
Property-Based Tests for Optional Section Removal

Tests Property 7: Optional section removal
Validates: Requirements 3.1
"""

import pytest
from hypothesis import given, strategies as st, settings

from app.models.cv_models import CVModelV2
from app.models.cv_section_models import SectionType, Section, FreeTextSectionContent
from app.services.section_management_service import SectionManagementService


# Strategy for optional (non-core) section types
optional_section_types = st.sampled_from([
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
    SectionType.CUSTOM,
])


@settings(max_examples=100)
@given(section_type=optional_section_types)
def test_property_optional_section_removal(section_type):
    """
    Property 7: Optional section removal
    
    For any optional (non-core) section in a CV, removing that section should
    result in the section no longer being present in the CV's section list.
    
    **Validates: Requirements 3.1**
    """
    service = SectionManagementService()
    cv = CVModelV2(id="test-cv", sections=[])
    
    # Add the optional section
    if section_type == SectionType.CUSTOM:
        section = service.add_custom_section(cv, "Custom Section")
    else:
        section = service.add_predefined_section(cv, section_type)
    
    section_id = section.id
    
    # Verify section was added
    assert section in cv.sections
    assert len(cv.sections) == 1
    
    # Remove the section
    service.remove_section(cv, section_id)
    
    # Verify section was removed
    assert section not in cv.sections
    assert len(cv.sections) == 0
    
    # Verify section cannot be found by ID
    assert cv.get_section_by_id(section_id) is None
