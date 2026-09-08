"""
Property-Based Tests for Whitespace Title Rejection

Tests Property 5: Whitespace titles rejected
Validates: Requirements 2.3
"""

import pytest
from hypothesis import given, strategies as st, settings

from app.models.cv_models import CVModelV2
from app.services.section_management_service import SectionManagementService


# Strategy for whitespace-only strings
whitespace_strings = st.one_of(
    st.just(""),  # Empty string
    st.text(alphabet=" \t\n\r", min_size=1, max_size=20),  # Only whitespace characters
)


@settings(max_examples=100)
@given(title=whitespace_strings)
def test_property_whitespace_titles_rejected(title):
    """
    Property 5: Whitespace titles rejected
    
    For any string composed entirely of whitespace characters (spaces, tabs,
    newlines) or empty string, attempting to create a custom section should
    be rejected with an error.
    
    **Validates: Requirements 2.3**
    """
    service = SectionManagementService()
    cv = CVModelV2(id="test-cv", sections=[])
    
    # Attempt to add custom section with whitespace title - should fail
    with pytest.raises(ValueError) as exc_info:
        service.add_custom_section(cv, title)
    
    # Verify error message mentions empty or title
    error_msg = str(exc_info.value).lower()
    assert "empty" in error_msg or "title" in error_msg or "cannot" in error_msg
    
    # Verify no section was added to CV
    assert len(cv.sections) == 0
