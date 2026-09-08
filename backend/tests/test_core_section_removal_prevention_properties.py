"""
Property-Based Tests for Core Section Removal Prevention

Tests Property 8: Core section removal prevented
Validates: Requirements 3.2
"""

import pytest
from hypothesis import given, strategies as st, settings

from app.models.cv_models import CVModelV2
from app.models.cv_section_models import SectionType
from app.services.section_management_service import SectionManagementService


@settings(max_examples=100)
@given(dummy=st.just(None))  # Use dummy strategy since we're testing a constant
def test_property_core_section_removal_prevented(dummy):
    """
    Property 8: Core section removal prevented
    
    For any core section (Personal_Information), attempting to remove it
    should be rejected with an error.
    
    **Validates: Requirements 3.2**
    """
    service = SectionManagementService()
    cv = CVModelV2(id="test-cv", sections=[])
    
    # Add the core section (Personal Info)
    section = service.add_predefined_section(cv, SectionType.PERSONAL_INFO)
    section_id = section.id
    
    # Verify section was added and is core
    assert section in cv.sections
    assert section.is_core is True
    assert section.type == SectionType.PERSONAL_INFO
    
    # Attempt to remove the core section - should fail
    with pytest.raises(ValueError) as exc_info:
        service.remove_section(cv, section_id)
    
    # Verify error message mentions core section
    error_msg = str(exc_info.value).lower()
    assert "core" in error_msg or "cannot remove" in error_msg
    
    # Verify section is still in CV
    assert section in cv.sections
    assert len(cv.sections) == 1
    assert cv.get_section_by_id(section_id) is not None
