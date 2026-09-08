"""
Property-Based Tests for Content Preservation Invariant

Tests Property 11: Content preservation invariant
Validates: Requirements 4.3, 5.3
"""

import pytest
from hypothesis import given, strategies as st, settings
import random
import copy

from app.models.cv_models import CVModelV2
from app.models.cv_section_models import (
    SectionType,
    Section,
    FreeTextSectionContent,
    ListSectionContent,
    ListItem,
)
from app.services.section_management_service import SectionManagementService


@settings(max_examples=100)
@given(
    section_count=st.integers(min_value=1, max_value=5),
    content_text=st.text(min_size=1, max_size=100)
)
def test_property_content_preservation_reordering(section_count, content_text):
    """
    Property 11a: Content preservation during reordering
    
    For any CV and any section, performing reordering operations should
    leave the section's content unchanged.
    
    **Validates: Requirements 4.3**
    """
    service = SectionManagementService()
    cv = CVModelV2(id="test-cv", sections=[])
    
    # Create sections with specific content
    sections = []
    for i in range(section_count):
        section = Section(
            id=f"section-{i}",
            type=SectionType.CUSTOM,
            title=f"Section {i}",
            content=FreeTextSectionContent(text=f"{content_text}-{i}"),
            order=i,
            visible=True
        )
        cv.sections.append(section)
        sections.append(section)
    
    # Store original content for each section
    original_content = {s.id: copy.deepcopy(s.content) for s in sections}
    
    # Reorder sections
    section_ids = [s.id for s in sections]
    random.shuffle(section_ids)
    service.reorder_sections(cv, section_ids)
    
    # Verify content is unchanged for all sections
    for section_id, original in original_content.items():
        section = cv.get_section_by_id(section_id)
        assert section is not None
        assert section.content == original
        # For FreeTextSectionContent, verify text specifically
        if isinstance(section.content, FreeTextSectionContent):
            assert section.content.text == original.text


@settings(max_examples=100)
@given(
    content_text=st.text(min_size=1, max_size=100),
    visible=st.booleans()
)
def test_property_content_preservation_visibility_toggle(content_text, visible):
    """
    Property 11b: Content preservation during visibility toggle
    
    For any CV and any section, toggling visibility should leave the
    section's content unchanged.
    
    **Validates: Requirements 5.3**
    """
    service = SectionManagementService()
    cv = CVModelV2(id="test-cv", sections=[])
    
    # Create a section with specific content
    section = Section(
        id="test-section",
        type=SectionType.CUSTOM,
        title="Test Section",
        content=FreeTextSectionContent(text=content_text),
        order=0,
        visible=True
    )
    cv.sections.append(section)
    
    # Store original content
    original_content = copy.deepcopy(section.content)
    
    # Toggle visibility
    service.toggle_visibility(cv, section.id, visible)
    
    # Verify content is unchanged
    assert section.content == original_content
    if isinstance(section.content, FreeTextSectionContent):
        assert section.content.text == original_content.text
    
    # Verify visibility was changed
    assert section.visible == visible


@settings(max_examples=100)
@given(items_count=st.integers(min_value=1, max_value=5))
def test_property_content_preservation_list_sections(items_count):
    """
    Property 11c: Content preservation for list sections
    
    For any section with list content, reordering and visibility operations
    should preserve the list items.
    
    **Validates: Requirements 4.3, 5.3**
    """
    service = SectionManagementService()
    cv = CVModelV2(id="test-cv", sections=[])
    
    # Create a list section with items
    items = [ListItem(text=f"Item {i}") for i in range(items_count)]
    section = Section(
        id="list-section",
        type=SectionType.SKILLS,
        title="Skills",
        content=ListSectionContent(items=items),
        order=0,
        visible=True
    )
    cv.sections.append(section)
    
    # Store original items
    original_items = [item.text for item in section.content.items]
    
    # Toggle visibility
    service.toggle_visibility(cv, section.id, False)
    
    # Verify items are unchanged
    current_items = [item.text for item in section.content.items]
    assert current_items == original_items
    
    # Toggle back
    service.toggle_visibility(cv, section.id, True)
    
    # Verify items still unchanged
    current_items = [item.text for item in section.content.items]
    assert current_items == original_items
