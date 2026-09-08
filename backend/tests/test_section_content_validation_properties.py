"""
Property-Based Tests for Section Content Validation

Tests Property 15: Content validation by type
Validates: Requirements 6.4

Ensures that section content structures match their declared section types.
"""

import pytest
from hypothesis import given, strategies as st, settings
from pydantic import ValidationError

from app.models.cv_section_models import (
    Section,
    SectionType,
    PersonalInfoContent,
    FreeTextSectionContent,
    ListSectionContent,
    StructuredSectionContent,
    ListItem,
    ExperienceEntry,
    EducationEntry,
    CertificationEntry
)


# Hypothesis strategies for generating test data

@st.composite
def personal_info_content_strategy(draw):
    """Generate valid PersonalInfoContent."""
    return PersonalInfoContent(
        full_name=draw(st.text(min_size=1, max_size=100)),
        email=draw(st.emails()),
        phone=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
        location=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
        linkedin=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
        website=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
        title=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100)))
    )


@st.composite
def free_text_content_strategy(draw):
    """Generate valid FreeTextSectionContent."""
    return FreeTextSectionContent(
        text=draw(st.text(min_size=0, max_size=1000))
    )


@st.composite
def list_content_strategy(draw):
    """Generate valid ListSectionContent."""
    items = draw(st.lists(
        st.builds(ListItem, text=st.text(min_size=1, max_size=100)),
        min_size=0,
        max_size=10
    ))
    return ListSectionContent(items=items)


@st.composite
def structured_content_strategy(draw):
    """Generate valid StructuredSectionContent with mixed entry types."""
    # Generate a mix of experience, education, and certification entries
    entries = []
    
    # Add some experience entries
    for _ in range(draw(st.integers(min_value=0, max_value=3))):
        entry = ExperienceEntry(
            title=draw(st.text(min_size=1, max_size=100)),
            company=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
            location=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
            start_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
            end_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
            current=draw(st.booleans()),
            description=draw(st.one_of(st.none(), st.text(min_size=0, max_size=500))),
            achievements=draw(st.lists(st.text(min_size=1, max_size=200), max_size=5))
        )
        entries.append(entry)
    
    return StructuredSectionContent(entries=entries)


class TestContentValidationByTypeProperty:
    """
    Property 15: Content validation by type
    
    For any section, the content structure should match the expected structure
    for its section type.
    
    Validates: Requirements 6.4
    """
    
    @given(content=personal_info_content_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_15_personal_info_content_valid(self, content):
        """
        Feature: cv-section-management, Property 15: Content validation by type
        
        Personal info sections must have PersonalInfoContent with required fields.
        """
        # Create section with personal info type and content
        section = Section(
            type=SectionType.PERSONAL_INFO,
            title="Personal Information",
            content=content,
            order=0
        )
        
        # Verify section was created successfully
        assert section.type == SectionType.PERSONAL_INFO
        assert isinstance(section.content, PersonalInfoContent)
        assert section.content.full_name == content.full_name
        assert section.content.email == content.email
    
    @given(content=free_text_content_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_15_summary_content_valid(self, content):
        """
        Feature: cv-section-management, Property 15: Content validation by type
        
        Summary sections must have FreeTextSectionContent.
        """
        section = Section(
            type=SectionType.SUMMARY,
            title="Professional Summary",
            content=content,
            order=0
        )
        
        assert section.type == SectionType.SUMMARY
        assert isinstance(section.content, FreeTextSectionContent)
        assert section.content.text == content.text
    
    @given(content=free_text_content_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_15_custom_content_valid(self, content):
        """
        Feature: cv-section-management, Property 15: Content validation by type
        
        Custom sections must have FreeTextSectionContent.
        """
        section = Section(
            type=SectionType.CUSTOM,
            title="Publications",
            content=content,
            order=0
        )
        
        assert section.type == SectionType.CUSTOM
        assert isinstance(section.content, FreeTextSectionContent)
    
    @given(
        section_type=st.sampled_from([
            SectionType.SKILLS,
            SectionType.LANGUAGES,
            SectionType.SOFTWARE,
            SectionType.INTERESTS
        ]),
        content=list_content_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_15_list_sections_content_valid(self, section_type, content):
        """
        Feature: cv-section-management, Property 15: Content validation by type
        
        List sections (Skills, Languages, Software, Interests) must have ListSectionContent.
        """
        section = Section(
            type=section_type,
            title=section_type.value.replace("_", " ").title(),
            content=content,
            order=0
        )
        
        assert section.type == section_type
        assert isinstance(section.content, ListSectionContent)
        assert len(section.content.items) == len(content.items)
    
    @given(
        section_type=st.sampled_from([
            SectionType.EXPERIENCE,
            SectionType.EDUCATION,
            SectionType.CERTIFICATIONS
        ]),
        content=structured_content_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_15_structured_sections_content_valid(self, section_type, content):
        """
        Feature: cv-section-management, Property 15: Content validation by type
        
        Structured sections (Experience, Education, Certifications) must have
        StructuredSectionContent.
        """
        section = Section(
            type=section_type,
            title=section_type.value.replace("_", " ").title(),
            content=content,
            order=0
        )
        
        assert section.type == section_type
        assert isinstance(section.content, StructuredSectionContent)
        assert len(section.content.entries) == len(content.entries)
    
    @given(content=list_content_strategy())
    @settings(max_examples=50, deadline=None)
    def test_property_15_wrong_content_type_rejected(self, content):
        """
        Feature: cv-section-management, Property 15: Content validation by type
        
        Sections with mismatched content types should be rejected.
        Personal info section cannot have list content.
        """
        with pytest.raises(ValidationError) as exc_info:
            Section(
                type=SectionType.PERSONAL_INFO,
                title="Personal Information",
                content=content,  # Wrong type - should be PersonalInfoContent
                order=0
            )
        
        # Verify the error mentions content type mismatch
        error_str = str(exc_info.value)
        assert "PersonalInfoContent" in error_str or "content" in error_str.lower()
    
    @given(content=personal_info_content_strategy())
    @settings(max_examples=50, deadline=None)
    def test_property_15_list_section_wrong_content_rejected(self, content):
        """
        Feature: cv-section-management, Property 15: Content validation by type
        
        List sections cannot have personal info content.
        """
        with pytest.raises(ValidationError) as exc_info:
            Section(
                type=SectionType.SKILLS,
                title="Skills",
                content=content,  # Wrong type - should be ListSectionContent
                order=0
            )
        
        error_str = str(exc_info.value)
        assert "ListSectionContent" in error_str or "content" in error_str.lower()
    
    @given(content=free_text_content_strategy())
    @settings(max_examples=50, deadline=None)
    def test_property_15_structured_section_wrong_content_rejected(self, content):
        """
        Feature: cv-section-management, Property 15: Content validation by type
        
        Structured sections cannot have free text content.
        """
        with pytest.raises(ValidationError) as exc_info:
            Section(
                type=SectionType.EXPERIENCE,
                title="Work Experience",
                content=content,  # Wrong type - should be StructuredSectionContent
                order=0
            )
        
        error_str = str(exc_info.value)
        assert "StructuredSectionContent" in error_str or "content" in error_str.lower()
