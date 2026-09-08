"""
Property-Based Tests for Section Reordering

Tests Property 10: Section reordering updates order field
Validates: Requirements 4.1
"""

import pytest
from hypothesis import given, strategies as st, settings
import random

from app.models.cv_models import CVModelV2
from app.models.cv_section_models import SectionType, Section, FreeTextSectionContent
from app.services.section_management_service import SectionManagementService


def permutation_strategy(section_count):
    """Generate a random permutation of section indices."""
    @st.composite
    def _permutation(draw):
        indices = list(range(section_count))
        random.shuffle(indices)
        return indices
    return _permutation()


@settings(max_examples=100)
@given(section_count=st.integers(min_value=1, max_value=10))
def test_property_section_reordering_updates_order_field(section_count):
    """
    Property 10: Section reordering updates order field
    
    For any CV and any valid permutation of section IDs, reordering the
    sections should result in each section's order field matching its
    position in the new sequence.
    
    **Validates: Requirements 4.1**
    """
    service = SectionManagementService()
    cv = CVModelV2(id="test-cv", sections=[])
    
    # Create sections with sequential order
    sections = []
    for i in range(section_count):
        section = Section(
            id=f"section-{i}",
            type=SectionType.CUSTOM,
            title=f"Section {i}",
            content=FreeTextSectionContent(text=f"Content {i}"),
            order=i,
            visible=True
        )
        cv.sections.append(section)
        sections.append(section)
    
    # Create a random permutation of section IDs
    section_ids = [s.id for s in sections]
    random.shuffle(section_ids)
    
    # Reorder sections
    service.reorder_sections(cv, section_ids)
    
    # Verify each section's order field matches its position in the new sequence
    for expected_order, section_id in enumerate(section_ids):
        section = cv.get_section_by_id(section_id)
        assert section is not None
        assert section.order == expected_order
    
    # Verify all sections still present
    assert len(cv.sections) == section_count
    
    # Verify order values are consecutive starting from 0
    orders = sorted([s.order for s in cv.sections])
    assert orders == list(range(section_count))
