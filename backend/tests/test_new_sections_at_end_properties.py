"""
Property-Based Tests for New Sections Placed at End

Tests Property 3: New sections placed at end
Validates: Requirements 1.5, 2.5
"""

import pytest
from hypothesis import given, strategies as st, settings, assume

from app.models.cv_models import CVModelV2
from app.models.cv_section_models import SectionType, Section, FreeTextSectionContent
from app.services.section_management_service import SectionManagementService


# Strategy for predefined section types (excluding CUSTOM and duplicates)
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

# Strategy for custom section titles
custom_titles = st.text(min_size=1, max_size=50).filter(lambda s: s.strip() != "")


@settings(max_examples=100)
@given(
    existing_count=st.integers(min_value=0, max_value=5),
    section_type=predefined_section_types
)
def test_property_new_predefined_section_at_end(existing_count, section_type):
    """
    Property 3a: New predefined sections placed at end
    
    For any CV and any new predefined section, when the section is added,
    its order value should be greater than all existing section order values.
    
    **Validates: Requirements 1.5**
    """
    service = SectionManagementService()
    cv = CVModelV2(id="test-cv", sections=[])
    
    # Create existing sections with sequential order
    existing_sections = []
    for i in range(existing_count):
        section = Section(
            id=f"section-{i}",
            type=SectionType.CUSTOM,
            title=f"Section {i}",
            content=FreeTextSectionContent(text=""),
            order=i,
            visible=True
        )
        cv.sections.append(section)
        existing_sections.append(section)
    
    # Get max order before adding new section
    max_order_before = max([s.order for s in cv.sections], default=-1)
    
    # Add new predefined section
    new_section = service.add_predefined_section(cv, section_type)
    
    # Verify new section is at the end
    assert new_section.order > max_order_before
    assert new_section.order == max_order_before + 1
    
    # Verify all existing sections maintain their order
    for section in existing_sections:
        assert section.order < new_section.order


@settings(max_examples=100)
@given(
    existing_count=st.integers(min_value=0, max_value=5),
    custom_title=custom_titles
)
def test_property_new_custom_section_at_end(existing_count, custom_title):
    """
    Property 3b: New custom sections placed at end
    
    For any CV and any new custom section, when the section is added,
    its order value should be greater than all existing section order values.
    
    **Validates: Requirements 2.5**
    """
    service = SectionManagementService()
    cv = CVModelV2(id="test-cv", sections=[])
    
    # Create existing sections with sequential order
    existing_sections = []
    for i in range(existing_count):
        section = Section(
            id=f"section-{i}",
            type=SectionType.CUSTOM,
            title=f"Section {i}",
            content=FreeTextSectionContent(text=""),
            order=i,
            visible=True
        )
        cv.sections.append(section)
        existing_sections.append(section)
    
    # Get max order before adding new section
    max_order_before = max([s.order for s in cv.sections], default=-1)
    
    # Add new custom section
    new_section = service.add_custom_section(cv, custom_title)
    
    # Verify new section is at the end
    assert new_section.order > max_order_before
    assert new_section.order == max_order_before + 1
    
    # Verify all existing sections maintain their order
    for section in existing_sections:
        assert section.order < new_section.order
