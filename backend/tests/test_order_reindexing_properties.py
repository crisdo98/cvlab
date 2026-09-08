"""
Property-Based Tests for Order Reindexing After Removal

Tests Property 9: Order reindexing after removal
Validates: Requirements 3.4
"""

import pytest
from hypothesis import given, strategies as st, settings, assume

from app.models.cv_models import CVModelV2
from app.models.cv_section_models import SectionType, Section, FreeTextSectionContent
from app.services.section_management_service import SectionManagementService


@settings(max_examples=100)
@given(
    section_count=st.integers(min_value=2, max_value=10),
    removal_index=st.integers(min_value=0, max_value=9)
)
def test_property_order_reindexing_after_removal(section_count, removal_index):
    """
    Property 9: Order reindexing after removal
    
    For any CV, after removing a section, all remaining sections should have
    consecutive order values starting from 0 with no gaps.
    
    **Validates: Requirements 3.4**
    """
    # Ensure removal_index is valid for section_count
    assume(removal_index < section_count)
    
    service = SectionManagementService()
    cv = CVModelV2(id="test-cv", sections=[])
    
    # Create sections with sequential order
    sections = []
    for i in range(section_count):
        section = Section(
            id=f"section-{i}",
            type=SectionType.CUSTOM,
            title=f"Section {i}",
            content=FreeTextSectionContent(text=""),
            order=i,
            visible=True
        )
        cv.sections.append(section)
        sections.append(section)
    
    # Remove the section at removal_index
    section_to_remove = sections[removal_index]
    service.remove_section(cv, section_to_remove.id)
    
    # Verify section was removed
    assert len(cv.sections) == section_count - 1
    assert section_to_remove not in cv.sections
    
    # Verify remaining sections have consecutive order values starting from 0
    orders = sorted([s.order for s in cv.sections])
    expected_orders = list(range(len(cv.sections)))
    assert orders == expected_orders
    
    # Verify no gaps in order values
    for i, order in enumerate(orders):
        assert order == i
