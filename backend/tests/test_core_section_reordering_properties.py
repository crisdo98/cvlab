"""
Property-Based Tests for Core Section Reordering

Tests Property 12: Core sections can be reordered
Validates: Requirements 4.4
"""

import pytest
from hypothesis import given, strategies as st, settings
import random

from app.models.cv_models import CVModelV2
from app.models.cv_section_models import SectionType, Section, FreeTextSectionContent
from app.services.section_management_service import SectionManagementService


@settings(max_examples=100)
@given(
    additional_sections=st.integers(min_value=0, max_value=5),
    core_position=st.integers(min_value=0, max_value=5)
)
def test_property_core_sections_can_be_reordered(additional_sections, core_position):
    """
    Property 12: Core sections can be reordered
    
    For any CV containing core sections, reordering operations should succeed
    even when core sections are moved to different positions.
    
    **Validates: Requirements 4.4**
    """
    # Ensure core_position is valid
    total_sections = additional_sections + 1  # +1 for core section
    if core_position >= total_sections:
        core_position = total_sections - 1
    
    service = SectionManagementService()
    cv = CVModelV2(id="test-cv", sections=[])
    
    # Add core section (Personal Info)
    core_section = service.add_predefined_section(cv, SectionType.PERSONAL_INFO)
    
    # Add additional optional sections
    for i in range(additional_sections):
        section = Section(
            id=f"section-{i}",
            type=SectionType.CUSTOM,
            title=f"Section {i}",
            content=FreeTextSectionContent(text=f"Content {i}"),
            order=i + 1,  # Core section is at 0
            visible=True
        )
        cv.sections.append(section)
    
    # Verify core section is present
    assert core_section.is_core is True
    assert core_section in cv.sections
    
    # Create new order with core section at specified position
    section_ids = [s.id for s in cv.sections]
    # Remove core section from current position
    section_ids.remove(core_section.id)
    # Insert at new position
    section_ids.insert(core_position, core_section.id)
    
    # Reorder sections - should succeed even with core section moved
    service.reorder_sections(cv, section_ids)
    
    # Verify reordering succeeded
    assert core_section.order == core_position
    
    # Verify core section is still in CV
    assert core_section in cv.sections
    assert cv.get_section_by_id(core_section.id) is not None
    
    # Verify all sections have correct order values
    for expected_order, section_id in enumerate(section_ids):
        section = cv.get_section_by_id(section_id)
        assert section is not None
        assert section.order == expected_order
