"""
Property-Based Tests for Export Visibility

Tests Properties 13 and 14: Hidden sections excluded, visible sections included
Validates: Requirements 5.1, 5.2, 8.1, 8.2, 8.5

Ensures that export operations respect section visibility settings.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from datetime import datetime

from app.models.cv_models import CVModelV2
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
from app.services.export_service import ExportService


# Hypothesis strategies for generating test data

@st.composite
def personal_info_content_strategy(draw):
    """Generate valid PersonalInfoContent."""
    return PersonalInfoContent(
        full_name=draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs')))),
        email=draw(st.emails()),
        phone=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        location=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        linkedin=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        website=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        title=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs')))))
    )


@st.composite
def free_text_content_strategy(draw):
    """Generate valid FreeTextSectionContent."""
    return FreeTextSectionContent(
        text=draw(st.text(min_size=0, max_size=500, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))
    )


@st.composite
def list_content_strategy(draw):
    """Generate valid ListSectionContent."""
    items = draw(st.lists(
        st.builds(ListItem, text=st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs')))),
        min_size=0,
        max_size=5
    ))
    return ListSectionContent(items=items)


@st.composite
def experience_entry_strategy(draw):
    """Generate valid ExperienceEntry."""
    return ExperienceEntry(
        title=draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs')))),
        company=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        location=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        start_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        end_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        current=draw(st.booleans()),
        description=draw(st.one_of(st.none(), st.text(min_size=0, max_size=300, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        achievements=draw(st.lists(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))), max_size=3))
    )


@st.composite
def education_entry_strategy(draw):
    """Generate valid EducationEntry."""
    return EducationEntry(
        degree=draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs')))),
        institution=draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs')))),
        location=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        start_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        end_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        gpa=draw(st.one_of(st.none(), st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        description=draw(st.one_of(st.none(), st.text(min_size=0, max_size=300, alphabet=st.characters(blacklist_categories=('Cc', 'Cs')))))
    )


@st.composite
def certification_entry_strategy(draw):
    """Generate valid CertificationEntry."""
    return CertificationEntry(
        name=draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs')))),
        issuer=draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs')))),
        date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        expiry_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        credential_id=draw(st.one_of(st.none(), st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cc', 'Cs')))))
    )


@st.composite
def section_strategy(draw, section_type=None, visible=None):
    """Generate a valid Section with appropriate content for its type."""
    if section_type is None:
        section_type = draw(st.sampled_from(list(SectionType)))
    
    # Generate appropriate content based on section type
    if section_type == SectionType.PERSONAL_INFO:
        content = draw(personal_info_content_strategy())
        title = "Personal Information"
    elif section_type in [SectionType.SKILLS, SectionType.LANGUAGES, SectionType.SOFTWARE, SectionType.INTERESTS]:
        content = draw(list_content_strategy())
        title = section_type.value.replace("_", " ").title()
    elif section_type in [SectionType.EXPERIENCE]:
        entries = draw(st.lists(experience_entry_strategy(), min_size=0, max_size=3))
        content = StructuredSectionContent(entries=entries)
        title = "Experience"
    elif section_type in [SectionType.EDUCATION]:
        entries = draw(st.lists(education_entry_strategy(), min_size=0, max_size=3))
        content = StructuredSectionContent(entries=entries)
        title = "Education"
    elif section_type in [SectionType.CERTIFICATIONS]:
        entries = draw(st.lists(certification_entry_strategy(), min_size=0, max_size=3))
        content = StructuredSectionContent(entries=entries)
        title = "Certifications"
    else:  # Free text sections (SUMMARY, CUSTOM, etc.)
        content = draw(free_text_content_strategy())
        title = section_type.value.replace("_", " ").title()
    
    if visible is None:
        visible = draw(st.booleans())
    
    order = draw(st.integers(min_value=0, max_value=20))
    
    return Section(
        type=section_type,
        title=title,
        content=content,
        visible=visible,
        order=order
    )


@st.composite
def cv_v2_with_mixed_visibility_strategy(draw):
    """Generate a CVModelV2 with mixed visible and hidden sections."""
    # Always include personal info section (visible)
    personal_section = draw(section_strategy(section_type=SectionType.PERSONAL_INFO, visible=True))
    personal_section.order = 0
    
    sections = [personal_section]
    used_types = {SectionType.PERSONAL_INFO}
    
    # Add some visible sections (ensure unique types)
    available_visible_types = [
        SectionType.SUMMARY, SectionType.EXPERIENCE, SectionType.EDUCATION,
        SectionType.SKILLS, SectionType.CERTIFICATIONS
    ]
    num_visible = draw(st.integers(min_value=1, max_value=min(4, len(available_visible_types))))
    visible_types = draw(st.lists(
        st.sampled_from(available_visible_types),
        min_size=num_visible,
        max_size=num_visible,
        unique=True
    ))
    
    for i, section_type in enumerate(visible_types):
        section = draw(section_strategy(section_type=section_type, visible=True))
        section.order = i + 1
        sections.append(section)
        used_types.add(section_type)
    
    # Add some hidden sections (ensure unique types)
    available_hidden_types = [
        t for t in [SectionType.LANGUAGES, SectionType.SOFTWARE, SectionType.INTERESTS,
                    SectionType.ACCOMPLISHMENTS, SectionType.AFFILIATIONS]
        if t not in used_types
    ]
    
    if available_hidden_types:
        num_hidden = draw(st.integers(min_value=1, max_value=min(4, len(available_hidden_types))))
        hidden_types = draw(st.lists(
            st.sampled_from(available_hidden_types),
            min_size=num_hidden,
            max_size=num_hidden,
            unique=True
        ))
        
        for i, section_type in enumerate(hidden_types):
            section = draw(section_strategy(section_type=section_type, visible=False))
            section.order = len(visible_types) + i + 1
            sections.append(section)
    
    return CVModelV2(
        sections=sections,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        version=2
    )


@st.composite
def cv_v2_all_visible_strategy(draw):
    """Generate a CVModelV2 with all sections visible."""
    # Always include personal info section
    personal_section = draw(section_strategy(section_type=SectionType.PERSONAL_INFO, visible=True))
    personal_section.order = 0
    
    sections = [personal_section]
    
    # Add other visible sections (ensure unique types)
    available_types = [
        SectionType.SUMMARY, SectionType.EXPERIENCE, SectionType.EDUCATION,
        SectionType.SKILLS, SectionType.CERTIFICATIONS, SectionType.LANGUAGES
    ]
    num_sections = draw(st.integers(min_value=2, max_value=min(6, len(available_types))))
    selected_types = draw(st.lists(
        st.sampled_from(available_types),
        min_size=num_sections,
        max_size=num_sections,
        unique=True
    ))
    
    for i, section_type in enumerate(selected_types):
        section = draw(section_strategy(section_type=section_type, visible=True))
        section.order = i + 1
        sections.append(section)
    
    return CVModelV2(
        sections=sections,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        version=2
    )


class TestExportVisibilityProperties:
    """
    Property 13: Hidden sections excluded from exports
    Property 14: Visible sections included in exports
    
    Validates: Requirements 5.1, 5.2, 8.1, 8.2, 8.5
    """
    
    @pytest.fixture
    def export_service(self, tmp_path, monkeypatch):
        """Create an ExportService instance for testing."""
        # Mock the validation to avoid dependency checks
        def mock_validate_dependencies(self):
            pass
        
        monkeypatch.setattr(ExportService, '_validate_dependencies', mock_validate_dependencies)
        return ExportService(root_dir=str(tmp_path))
    
    @given(cv_data=cv_v2_with_mixed_visibility_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_13_hidden_sections_excluded_from_exports(self, export_service, cv_data):
        """
        Feature: cv-section-management, Property 13: Hidden sections excluded from exports
        
        For any CV with mixed visible and hidden sections, exporting to markdown
        should include only sections where visible=true.
        
        Validates: Requirements 5.1, 8.1, 8.2, 8.5
        """
        # Get hidden section titles
        hidden_sections = [s for s in cv_data.sections if not s.visible]
        hidden_titles = [s.title for s in hidden_sections]
        
        # Assume we have at least one hidden section
        assume(len(hidden_sections) > 0)
        
        # Export to markdown
        markdown_output = export_service.json_to_markdown(cv_data)
        
        # Verify hidden sections are not in the output
        for title in hidden_titles:
            # Check that the section heading doesn't appear
            # (allowing for markdown heading syntax)
            assert f"## {title}" not in markdown_output, \
                f"Hidden section '{title}' should not appear in export"
    
    @given(cv_data=cv_v2_all_visible_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_14_visible_sections_included_in_exports(self, export_service, cv_data):
        """
        Feature: cv-section-management, Property 14: Visible sections included in exports
        
        For any CV, all sections with visible=true should appear in the exported output.
        
        Validates: Requirements 5.2
        """
        # Get visible section titles (excluding personal info which uses H1)
        visible_sections = [s for s in cv_data.sections if s.visible and s.type != SectionType.PERSONAL_INFO]
        visible_titles = [s.title for s in visible_sections]
        
        # Export to markdown
        markdown_output = export_service.json_to_markdown(cv_data)
        
        # Verify all visible sections appear in the output
        for title in visible_titles:
            # Check that the section heading appears
            assert f"## {title}" in markdown_output, \
                f"Visible section '{title}' should appear in export"
    
    @given(cv_data=cv_v2_with_mixed_visibility_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_13_get_visible_sections_respects_visibility(self, cv_data):
        """
        Feature: cv-section-management, Property 13: get_visible_sections() respects visibility
        
        The get_visible_sections() method should return only sections with visible=true.
        
        Validates: Requirements 5.1
        """
        visible_sections = cv_data.get_visible_sections()
        
        # All returned sections should have visible=True
        for section in visible_sections:
            assert section.visible is True, \
                f"get_visible_sections() returned hidden section: {section.title}"
        
        # Count should match the number of visible sections
        expected_count = sum(1 for s in cv_data.sections if s.visible)
        assert len(visible_sections) == expected_count, \
            f"Expected {expected_count} visible sections, got {len(visible_sections)}"
    
    @given(cv_data=cv_v2_with_mixed_visibility_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_13_export_respects_section_order(self, export_service, cv_data):
        """
        Feature: cv-section-management, Property 13: Export respects section order
        
        Visible sections should appear in the export in the order specified by their order field.
        
        Validates: Requirements 8.3
        """
        visible_sections = cv_data.get_visible_sections()
        
        # Assume we have at least 2 visible sections to test ordering
        assume(len(visible_sections) >= 2)
        
        # Export to markdown
        markdown_output = export_service.json_to_markdown(cv_data)
        
        # Find positions of section headings in the output
        section_positions = []
        for section in visible_sections:
            if section.type == SectionType.PERSONAL_INFO:
                # Personal info uses H1 (#)
                heading = f"# {section.content.full_name}"
            else:
                # Other sections use H2 (##)
                heading = f"## {section.title}"
            
            pos = markdown_output.find(heading)
            if pos != -1:
                section_positions.append((section.order, pos, section.title))
        
        # Verify sections appear in order
        if len(section_positions) >= 2:
            for i in range(len(section_positions) - 1):
                current_order, current_pos, current_title = section_positions[i]
                next_order, next_pos, next_title = section_positions[i + 1]
                
                assert current_pos < next_pos, \
                    f"Section '{current_title}' (order={current_order}) should appear before " \
                    f"'{next_title}' (order={next_order}) in export"

    @given(cv_data=cv_v2_all_visible_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_21_export_formats_by_type(self, export_service, cv_data):
        """
        Feature: cv-section-management, Property 21: Export formats by type
        
        For any CV, when exported, each section should be formatted according to its type.
        
        Validates: Requirements 8.4
        """
        # Export to markdown
        markdown_output = export_service.json_to_markdown(cv_data)
        
        # Check formatting for each visible section
        for section in cv_data.get_visible_sections():
            if section.type == SectionType.PERSONAL_INFO:
                # Personal info should use H1 for name
                assert isinstance(section.content, PersonalInfoContent)
                assert f"# {section.content.full_name}" in markdown_output
                
                # Contact info should be formatted as links where appropriate
                if section.content.email:
                    assert f"mailto:{section.content.email}" in markdown_output or section.content.email in markdown_output
            
            elif section.type in [SectionType.SKILLS, SectionType.LANGUAGES, 
                                 SectionType.SOFTWARE, SectionType.INTERESTS]:
                # List sections render as bullets, except the comma-separated
                # ones (skills), which read better as a single run of terms.
                assert isinstance(section.content, ListSectionContent)
                if section.content.items:
                    if section.type in export_service.COMMA_SEPARATED_SECTIONS:
                        expected = ", ".join(item.text for item in section.content.items)
                        assert expected in markdown_output, \
                            f"List section '{section.title}' should be comma separated"
                    else:
                        has_list_item = any(
                            f"- {item.text}" in markdown_output for item in section.content.items
                        )
                        assert has_list_item, \
                            f"List section '{section.title}' should have bullet points"
            
            elif section.type == SectionType.EXPERIENCE:
                # Experience should have structured formatting
                assert isinstance(section.content, StructuredSectionContent)
                for entry in section.content.entries:
                    if isinstance(entry, ExperienceEntry):
                        # Job title should be H3
                        assert f"### {entry.title}" in markdown_output
                        
                        # Company should be bold
                        if entry.company:
                            assert f"**{entry.company}**" in markdown_output
                        
                        # Achievements should be bullet points
                        if entry.achievements:
                            for achievement in entry.achievements:
                                assert f"- {achievement}" in markdown_output
            
            elif section.type == SectionType.EDUCATION:
                # Education should have structured formatting
                assert isinstance(section.content, StructuredSectionContent)
                for entry in section.content.entries:
                    if isinstance(entry, EducationEntry):
                        # Degree should be H3
                        assert f"### {entry.degree}" in markdown_output
                        
                        # Institution should be bold
                        assert f"**{entry.institution}**" in markdown_output
            
            elif section.type == SectionType.CERTIFICATIONS:
                # Certifications should be formatted as list items
                assert isinstance(section.content, StructuredSectionContent)
                for entry in section.content.entries:
                    if isinstance(entry, CertificationEntry):
                        # Should be a bullet point with bold name
                        assert f"- **{entry.name}**" in markdown_output
                        assert entry.issuer in markdown_output
            
            elif section.type in [SectionType.SUMMARY, SectionType.CUSTOM]:
                # Free text sections should have H2 heading
                assert isinstance(section.content, FreeTextSectionContent)
                assert f"## {section.title}" in markdown_output
