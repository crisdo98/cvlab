"""
Property-Based Tests for No Duplicate Predefined Sections

Tests Property 2: No duplicate predefined sections
Validates: Requirements 1.4
"""

import pytest
from hypothesis import given, strategies as st, settings

from app.models.cv_models import CVModelV2
from app.models.cv_section_models import SectionType
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


@settings(max_examples=100)
@given(section_type=predefined_section_types)
def test_property_no_duplicate_predefined_sections(section_type):
    """
    Property 2: No duplicate predefined sections
    
    For any predefined section type, attempting to add it twice to the same CV
    should result in rejection on the second attempt.
    
    **Validates: Requirements 1.4**
    """
    service = SectionManagementService()
    cv = CVModelV2(id="test-cv", sections=[])
    
    # Add the section first time - should succeed
    section1 = service.add_predefined_section(cv, section_type)
    assert section1 in cv.sections
    assert len(cv.sections) == 1
    
    # Attempt to add the same section type again - should fail
    with pytest.raises(ValueError) as exc_info:
        service.add_predefined_section(cv, section_type)
    
    # Verify error message mentions the section type
    assert section_type.value in str(exc_info.value).lower() or "already exists" in str(exc_info.value).lower()
    
    # Verify CV still has only one section
    assert len(cv.sections) == 1
    assert cv.sections[0] == section1
