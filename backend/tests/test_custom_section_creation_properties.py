"""
Property-Based Tests for Custom Section Creation

Tests Property 4: Custom section creation
Validates: Requirements 2.2
"""

import pytest
from hypothesis import given, strategies as st, settings

from app.models.cv_models import CVModelV2
from app.models.cv_section_models import SectionType, FreeTextSectionContent
from app.services.section_management_service import SectionManagementService


# Strategy for valid custom section titles (non-empty, non-whitespace)
valid_custom_titles = st.text(min_size=1, max_size=100).filter(lambda s: s.strip() != "")


@settings(max_examples=100)
@given(title=valid_custom_titles)
def test_property_custom_section_creation(title):
    """
    Property 4: Custom section creation
    
    For any non-empty, non-whitespace title string, creating a custom section
    should result in a section with type CUSTOM, free-text content structure,
    and the provided title.
    
    **Validates: Requirements 2.2**
    """
    service = SectionManagementService()
    cv = CVModelV2(id="test-cv", sections=[])
    
    # Add custom section
    section = service.add_custom_section(cv, title)
    
    # Verify section was added to CV
    assert section in cv.sections
    assert len(cv.sections) == 1
    
    # Verify section has CUSTOM type
    assert section.type == SectionType.CUSTOM
    
    # Verify section has free-text content structure
    assert isinstance(section.content, FreeTextSectionContent)
    assert section.content_structure == "free_text"
    
    # Verify section has the provided title (trimmed)
    assert section.title == title.strip()
    
    # Verify section has required fields
    assert section.id is not None
    assert section.visible is True
    assert section.order >= 0
