"""
Unit Tests for Section Rendering

Tests LaTeX/Markdown output for each section type.
Validates: Requirements 6.5, 8.4
"""

import pytest
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


class TestSectionRendering:
    """Unit tests for section rendering to markdown."""
    
    @pytest.fixture
    def export_service(self, tmp_path, monkeypatch):
        """Create an ExportService instance for testing."""
        # Mock the validation to avoid dependency checks
        def mock_validate_dependencies(self):
            pass
        
        monkeypatch.setattr(ExportService, '_validate_dependencies', mock_validate_dependencies)
        return ExportService(root_dir=str(tmp_path))
    
    def test_personal_info_section_rendering(self, export_service):
        """Test that personal info section renders with H1 heading and contact info."""
        personal_section = Section(
            type=SectionType.PERSONAL_INFO,
            title="Personal Information",
            content=PersonalInfoContent(
                full_name="John Doe",
                email="john@example.com",
                phone="+1234567890",
                location="San Francisco, CA",
                linkedin="linkedin.com/in/johndoe",
                website="johndoe.com",
                title="Senior Software Engineer"
            ),
            visible=True,
            order=0
        )
        
        cv = CVModelV2(sections=[personal_section])
        markdown = export_service.json_to_markdown(cv)
        
        # Check H1 heading
        assert "# John Doe" in markdown
        
        # Check professional title
        assert "Senior Software Engineer" in markdown
        
        # Check contact info
        assert "+1234567890" in markdown
        assert "San Francisco, CA" in markdown
        assert "mailto:john@example.com" in markdown or "john@example.com" in markdown
        assert "linkedin.com/in/johndoe" in markdown or "LinkedIn" in markdown
        assert "johndoe.com" in markdown or "Website" in markdown
    
    def test_summary_section_rendering(self, export_service):
        """Test that summary section renders with H2 heading and text content."""
        personal_section = Section(
            type=SectionType.PERSONAL_INFO,
            title="Personal Information",
            content=PersonalInfoContent(full_name="John Doe", email="john@example.com"),
            visible=True,
            order=0
        )
        
        summary_section = Section(
            type=SectionType.SUMMARY,
            title="Professional Summary",
            content=FreeTextSectionContent(
                text="Experienced software engineer with 10+ years in web development."
            ),
            visible=True,
            order=1
        )
        
        cv = CVModelV2(sections=[personal_section, summary_section])
        markdown = export_service.json_to_markdown(cv)
        
        # Check H2 heading
        assert "## Professional Summary" in markdown
        
        # Check content
        assert "Experienced software engineer with 10+ years in web development." in markdown
    
    def test_list_section_rendering(self, export_service):
        """Test that list sections render with bullet points."""
        personal_section = Section(
            type=SectionType.PERSONAL_INFO,
            title="Personal Information",
            content=PersonalInfoContent(full_name="John Doe", email="john@example.com"),
            visible=True,
            order=0
        )
        
        skills_section = Section(
            type=SectionType.SKILLS,
            title="Technical Skills",
            content=ListSectionContent(
                items=[
                    ListItem(text="Python"),
                    ListItem(text="JavaScript"),
                    ListItem(text="React")
                ]
            ),
            visible=True,
            order=1
        )
        
        cv = CVModelV2(sections=[personal_section, skills_section])
        markdown = export_service.json_to_markdown(cv)
        
        # Check H2 heading
        assert "## Technical Skills" in markdown
        
        # Skills render as a comma-separated run rather than one bullet per
        # skill, so twenty skills do not take most of a page.
        assert "Python, JavaScript, React" in markdown
    
    def test_experience_section_rendering(self, export_service):
        """Test that experience section renders with structured formatting."""
        personal_section = Section(
            type=SectionType.PERSONAL_INFO,
            title="Personal Information",
            content=PersonalInfoContent(full_name="John Doe", email="john@example.com"),
            visible=True,
            order=0
        )
        
        experience_section = Section(
            type=SectionType.EXPERIENCE,
            title="Work Experience",
            content=StructuredSectionContent(
                entries=[
                    ExperienceEntry(
                        title="Senior Software Engineer",
                        company="Tech Corp",
                        location="San Francisco, CA",
                        start_date="2020-01",
                        current=True,
                        description="Lead development of web applications",
                        achievements=[
                            "Improved performance by 50%",
                            "Led team of 5 developers"
                        ]
                    )
                ]
            ),
            visible=True,
            order=1
        )
        
        cv = CVModelV2(sections=[personal_section, experience_section])
        markdown = export_service.json_to_markdown(cv)
        
        # Check section heading
        assert "## Work Experience" in markdown
        
        # Check job title (H3)
        assert "### Senior Software Engineer" in markdown
        
        # Check company (bold)
        assert "**Tech Corp**" in markdown
        
        # Check location
        assert "San Francisco, CA" in markdown
        
        # Check date range
        assert "2020-01" in markdown
        assert "Present" in markdown
        
        # Check description
        assert "Lead development of web applications" in markdown
        
        # Check achievements (bullet points)
        assert "- Improved performance by 50%" in markdown
        assert "- Led team of 5 developers" in markdown
    
    def test_education_section_rendering(self, export_service):
        """Test that education section renders with structured formatting."""
        personal_section = Section(
            type=SectionType.PERSONAL_INFO,
            title="Personal Information",
            content=PersonalInfoContent(full_name="John Doe", email="john@example.com"),
            visible=True,
            order=0
        )
        
        education_section = Section(
            type=SectionType.EDUCATION,
            title="Education",
            content=StructuredSectionContent(
                entries=[
                    EducationEntry(
                        degree="Bachelor of Science in Computer Science",
                        institution="University of Technology",
                        location="Boston, MA",
                        start_date="2016-09",
                        end_date="2020-05",
                        gpa="3.8",
                        description="Focused on software engineering and algorithms"
                    )
                ]
            ),
            visible=True,
            order=1
        )
        
        cv = CVModelV2(sections=[personal_section, education_section])
        markdown = export_service.json_to_markdown(cv)
        
        # Check section heading
        assert "## Education" in markdown
        
        # Check degree (H3)
        assert "### Bachelor of Science in Computer Science" in markdown
        
        # Check institution (bold)
        assert "**University of Technology**" in markdown
        
        # Check location
        assert "Boston, MA" in markdown
        
        # Check date range
        assert "2016-09" in markdown
        assert "2020-05" in markdown
        
        # Check GPA
        assert "GPA: 3.8" in markdown
        
        # Check description
        assert "Focused on software engineering and algorithms" in markdown
    
    def test_certification_section_rendering(self, export_service):
        """Test that certification section renders as list items."""
        personal_section = Section(
            type=SectionType.PERSONAL_INFO,
            title="Personal Information",
            content=PersonalInfoContent(full_name="John Doe", email="john@example.com"),
            visible=True,
            order=0
        )
        
        cert_section = Section(
            type=SectionType.CERTIFICATIONS,
            title="Certifications",
            content=StructuredSectionContent(
                entries=[
                    CertificationEntry(
                        name="AWS Certified Solutions Architect",
                        issuer="Amazon Web Services",
                        date="2023-06",
                        expiry_date="2026-06",
                        credential_id="ABC123"
                    )
                ]
            ),
            visible=True,
            order=1
        )
        
        cv = CVModelV2(sections=[personal_section, cert_section])
        markdown = export_service.json_to_markdown(cv)
        
        # Check section heading
        assert "## Certifications" in markdown
        
        # Check certification as bullet point with bold name
        assert "- **AWS Certified Solutions Architect**" in markdown
        assert "Amazon Web Services" in markdown
        assert "2023-06" in markdown
        assert "2026-06" in markdown
    
    def test_custom_section_rendering(self, export_service):
        """Test that custom sections render with H2 heading and free text."""
        personal_section = Section(
            type=SectionType.PERSONAL_INFO,
            title="Personal Information",
            content=PersonalInfoContent(full_name="John Doe", email="john@example.com"),
            visible=True,
            order=0
        )
        
        custom_section = Section(
            type=SectionType.CUSTOM,
            title="Publications",
            content=FreeTextSectionContent(
                text="Published multiple papers on machine learning and AI."
            ),
            visible=True,
            order=1
        )
        
        cv = CVModelV2(sections=[personal_section, custom_section])
        markdown = export_service.json_to_markdown(cv)
        
        # Check H2 heading
        assert "## Publications" in markdown
        
        # Check content
        assert "Published multiple papers on machine learning and AI." in markdown
    
    def test_all_sections_hidden_edge_case(self, export_service):
        """Test edge case where all sections except personal info are hidden."""
        personal_section = Section(
            type=SectionType.PERSONAL_INFO,
            title="Personal Information",
            content=PersonalInfoContent(full_name="John Doe", email="john@example.com"),
            visible=True,
            order=0
        )
        
        hidden_section1 = Section(
            type=SectionType.SUMMARY,
            title="Summary",
            content=FreeTextSectionContent(text="This should not appear"),
            visible=False,
            order=1
        )
        
        hidden_section2 = Section(
            type=SectionType.SKILLS,
            title="Skills",
            content=ListSectionContent(items=[ListItem(text="Python")]),
            visible=False,
            order=2
        )
        
        cv = CVModelV2(sections=[personal_section, hidden_section1, hidden_section2])
        markdown = export_service.json_to_markdown(cv)
        
        # Check that personal info is present
        assert "# John Doe" in markdown
        
        # Check that hidden sections are not present
        assert "## Summary" not in markdown
        assert "This should not appear" not in markdown
        assert "## Skills" not in markdown
        assert "- Python" not in markdown
    
    def test_empty_list_section_rendering(self, export_service):
        """Test that empty list sections render with heading but no items."""
        personal_section = Section(
            type=SectionType.PERSONAL_INFO,
            title="Personal Information",
            content=PersonalInfoContent(full_name="John Doe", email="john@example.com"),
            visible=True,
            order=0
        )
        
        empty_skills_section = Section(
            type=SectionType.SKILLS,
            title="Skills",
            content=ListSectionContent(items=[]),
            visible=True,
            order=1
        )
        
        cv = CVModelV2(sections=[personal_section, empty_skills_section])
        markdown = export_service.json_to_markdown(cv)
        
        # Check that section heading is present
        assert "## Skills" in markdown
        
        # No bullet points should be present (empty list)
        # Just verify the section exists
    
    def test_section_order_preserved(self, export_service):
        """Test that sections appear in the correct order in the output."""
        sections = [
            Section(
                type=SectionType.PERSONAL_INFO,
                title="Personal Information",
                content=PersonalInfoContent(full_name="John Doe", email="john@example.com"),
                visible=True,
                order=0
            ),
            Section(
                type=SectionType.SUMMARY,
                title="Summary",
                content=FreeTextSectionContent(text="Summary text"),
                visible=True,
                order=1
            ),
            Section(
                type=SectionType.SKILLS,
                title="Skills",
                content=ListSectionContent(items=[ListItem(text="Python")]),
                visible=True,
                order=2
            ),
            Section(
                type=SectionType.EDUCATION,
                title="Education",
                content=StructuredSectionContent(entries=[
                    EducationEntry(degree="BS CS", institution="University")
                ]),
                visible=True,
                order=3
            )
        ]
        
        cv = CVModelV2(sections=sections)
        markdown = export_service.json_to_markdown(cv)
        
        # Find positions of each section
        personal_pos = markdown.find("# John Doe")
        summary_pos = markdown.find("## Summary")
        skills_pos = markdown.find("## Skills")
        education_pos = markdown.find("## Education")
        
        # Verify order
        assert personal_pos < summary_pos < skills_pos < education_pos, \
            "Sections should appear in order specified by order field"
