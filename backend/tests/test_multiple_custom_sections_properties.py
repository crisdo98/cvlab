"""
Property-Based Tests for Multiple Custom Sections

Tests Property 6: Multiple custom sections allowed
Validates: Requirements 2.4
"""

import pytest
from hypothesis import given, strategies as st, settings

from app.models.cv_models import CVModelV2
from app.models.cv_section_models import SectionType
from app.services.section_management_service import SectionManagementService


# Strategy for lists of unique custom section titles
def unique_titles_strategy():
    """Generate lists of unique non-empty titles."""
    return st.lists(
        st.text(min_size=1, max_size=50).filter(lambda s: s.strip() != ""),
        min_size=1,
        max_size=10,
        unique=True
    )


@settings(max_examples=100)
@given(titles=unique_titles_strategy())
def test_property_multiple_custom_sections_allowed(titles):
    """
    Property 6: Multiple custom sections allowed
    
    For any CV, adding multiple custom sections with different titles should
    succeed, and all custom sections should be present in the CV.
    
    **Validates: Requirements 2.4**
    """
    service = SectionManagementService()
    cv = CVModelV2(id="test-cv", sections=[])
    
    added_sections = []
    
    # Add all custom sections
    for title in titles:
        section = service.add_custom_section(cv, title)
        added_sections.append(section)
    
    # Verify all sections were added
    assert len(cv.sections) == len(titles)
    
    # Verify all added sections are in the CV
    for section in added_sections:
        assert section in cv.sections
    
    # Verify all sections are CUSTOM type
    for section in cv.sections:
        assert section.type == SectionType.CUSTOM
    
    # Verify all sections have unique titles (trimmed)
    section_titles = [s.title for s in cv.sections]
    assert len(section_titles) == len(set(section_titles))
    
    # Verify titles match (after trimming)
    expected_titles = {title.strip() for title in titles}
    actual_titles = {s.title for s in cv.sections}
    assert expected_titles == actual_titles
