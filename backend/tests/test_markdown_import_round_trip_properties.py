"""
Property-Based Tests for Markdown Import Round Trip

Tests the universal property that importing a markdown CV file and then
exporting it back to markdown should preserve all content and metadata.

Feature: cv-web-app, Property 8: Markdown Import Round Trip
Validates: Requirements 4.1, 4.2, 4.4, 7.2
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from datetime import datetime
import re

from app.services.import_service import ImportService
from app.services.export_service import ExportService
from app.models.cv_models import (
    CVModel, CVMetadata, PersonalInfo, ContactInfo,
    Experience, Education, Skills, SkillCategory, Certification
)


# Custom strategies for generating CV data
@st.composite
def contact_info_strategy(draw):
    """Generate valid contact information."""
    return ContactInfo(
        address=draw(st.one_of(st.none(), st.text(min_size=10, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Zs'))))),
        phone=draw(st.one_of(st.none(), st.from_regex(r'\+?[0-9]{1,3}[-\s]?[0-9]{3}[-\s]?[0-9]{3}[-\s]?[0-9]{4}', fullmatch=True))),
        email=draw(st.one_of(st.none(), st.emails())),
        linkedin=draw(st.one_of(st.none(), st.from_regex(r'https?://linkedin\.com/in/[a-z0-9\-]+', fullmatch=True))),
        website=draw(st.one_of(st.none(), st.from_regex(r'https?://[a-z0-9\-\.]+\.[a-z]{2,}', fullmatch=True)))
    )


@st.composite
def personal_info_strategy(draw):
    """Generate valid personal information."""
    return PersonalInfo(
        name=draw(st.text(min_size=3, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'Zs')))),
        title=draw(st.one_of(st.none(), st.text(min_size=5, max_size=80, alphabet=st.characters(whitelist_categories=('L', 'Zs'))))),
        contact=draw(contact_info_strategy())
    )


@st.composite
def experience_strategy(draw):
    """Generate valid work experience entry."""
    current = draw(st.booleans())
    return Experience(
        title=draw(st.text(min_size=5, max_size=80, alphabet=st.characters(whitelist_categories=('L', 'Zs')))),
        company=draw(st.text(min_size=3, max_size=80, alphabet=st.characters(whitelist_categories=('L', 'Zs')))),
        location=draw(st.one_of(st.none(), st.text(min_size=5, max_size=80, alphabet=st.characters(whitelist_categories=('L', 'Zs', 'P'))))),
        start_date=draw(st.from_regex(r'(January|February|March|April|May|June|July|August|September|October|November|December) \d{4}', fullmatch=True)),
        end_date=None if current else draw(st.one_of(st.none(), st.from_regex(r'(January|February|March|April|May|June|July|August|September|October|November|December) \d{4}', fullmatch=True))),
        current=current,
        description=draw(st.one_of(st.none(), st.text(min_size=10, max_size=500, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Zs'))))),
        achievements=draw(st.lists(st.text(min_size=10, max_size=200, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Zs'))), max_size=5))
    )


@st.composite
def education_strategy(draw):
    """Generate valid education entry."""
    return Education(
        degree=draw(st.text(min_size=5, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'Zs')))),
        institution=draw(st.text(min_size=5, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'Zs')))),
        location=draw(st.one_of(st.none(), st.text(min_size=5, max_size=80, alphabet=st.characters(whitelist_categories=('L', 'Zs', 'P'))))),
        start_date=draw(st.one_of(st.none(), st.from_regex(r'(January|February|March|April|May|June|July|August|September|October|November|December) \d{4}', fullmatch=True))),
        end_date=draw(st.one_of(st.none(), st.from_regex(r'(January|February|March|April|May|June|July|August|September|October|November|December) \d{4}', fullmatch=True))),
        gpa=draw(st.one_of(st.none(), st.from_regex(r'[0-3]\.\d{1,2}|4\.0{1,2}', fullmatch=True))),
        description=draw(st.one_of(st.none(), st.text(min_size=10, max_size=300, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Zs')))))
    )


@st.composite
def skill_category_strategy(draw):
    """Generate valid skill category."""
    return SkillCategory(
        name=draw(st.text(min_size=3, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'Zs')))),
        skills=draw(st.lists(st.text(min_size=2, max_size=30, alphabet=st.characters(whitelist_categories=('L', 'Zs'))), min_size=1, max_size=10))
    )


@st.composite
def certification_strategy(draw):
    """Generate valid certification entry."""
    return Certification(
        name=draw(st.text(min_size=5, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'Zs')))),
        issuer=draw(st.text(min_size=3, max_size=80, alphabet=st.characters(whitelist_categories=('L', 'Zs')))),
        date=draw(st.one_of(st.none(), st.from_regex(r'(January|February|March|April|May|June|July|August|September|October|November|December) \d{4}', fullmatch=True))),
        expiry_date=draw(st.one_of(st.none(), st.from_regex(r'(January|February|March|April|May|June|July|August|September|October|November|December) \d{4}', fullmatch=True)))
    )


@st.composite
def cv_model_strategy(draw):
    """Generate valid CV model for testing."""
    return CVModel(
        metadata=CVMetadata(
            title=draw(st.text(min_size=3, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'Zs')))),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            template_id="default"
        ),
        personal_info=draw(personal_info_strategy()),
        summary=draw(st.one_of(st.none(), st.text(min_size=20, max_size=500, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Zs'))))),
        experience=draw(st.lists(experience_strategy(), max_size=3)),
        education=draw(st.lists(education_strategy(), max_size=2)),
        skills=Skills(categories=draw(st.lists(skill_category_strategy(), max_size=4))),
        certifications=draw(st.lists(certification_strategy(), max_size=3))
    )


class TestMarkdownImportRoundTrip:
    """
    Property-Based Tests for Markdown Import Round Trip.
    
    Feature: cv-web-app, Property 8: Markdown Import Round Trip
    Validates: Requirements 4.1, 4.2, 4.4, 7.2
    """
    
    def setup_method(self):
        """Set up test fixtures."""
        self.import_service = ImportService()
        self.export_service = ExportService()
    
    @given(cv_data=cv_model_strategy())
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
    )
    def test_markdown_export_import_round_trip_preserves_content(self, cv_data):
        """
        Property: For any valid CV data, exporting to markdown then importing
        should preserve all content and metadata.
        
        Feature: cv-web-app, Property 8: Markdown Import Round Trip
        Validates: Requirements 4.1, 4.2, 4.4, 7.2
        """
        # Assume we have at least a name (required field)
        assume(cv_data.personal_info.name.strip() != "")
        
        # Step 1: Export CV to markdown
        markdown_content = self.export_service.json_to_markdown(cv_data)
        
        # Verify markdown was generated
        assert markdown_content is not None
        assert len(markdown_content) > 0
        assert markdown_content.startswith("---")  # Has YAML frontmatter
        
        # Step 2: Import markdown back to CV model
        imported_cv = self.import_service.import_from_markdown(markdown_content)
        
        # Verify import succeeded
        assert imported_cv is not None
        assert isinstance(imported_cv, CVModel)
        
        # Step 3: Verify content preservation
        
        # Personal info should be preserved
        assert imported_cv.personal_info.name == cv_data.personal_info.name
        
        # Title should be preserved (if present)
        if cv_data.personal_info.title:
            assert imported_cv.personal_info.title == cv_data.personal_info.title
        
        # Contact info should be preserved
        if cv_data.personal_info.contact.email:
            assert imported_cv.personal_info.contact.email == cv_data.personal_info.contact.email
        
        if cv_data.personal_info.contact.phone:
            # Phone numbers might be reformatted, so check if they contain the same digits
            original_digits = re.sub(r'\D', '', cv_data.personal_info.contact.phone)
            imported_digits = re.sub(r'\D', '', imported_cv.personal_info.contact.phone or '')
            assert original_digits == imported_digits
        
        if cv_data.personal_info.contact.linkedin:
            assert imported_cv.personal_info.contact.linkedin is not None
            # LinkedIn URLs should be preserved (may have http/https variations)
            assert cv_data.personal_info.contact.linkedin.replace('http://', '').replace('https://', '') in \
                   imported_cv.personal_info.contact.linkedin.replace('http://', '').replace('https://', '')
        
        if cv_data.personal_info.contact.website:
            assert imported_cv.personal_info.contact.website is not None
        
        # Summary should be preserved
        if cv_data.summary:
            assert imported_cv.summary is not None
            # Summary content should be present (whitespace normalization is acceptable)
            assert cv_data.summary.strip() in imported_cv.summary or \
                   imported_cv.summary.strip() in cv_data.summary
        
        # Experience entries should be preserved
        assert len(imported_cv.experience) == len(cv_data.experience)
        for original_exp, imported_exp in zip(cv_data.experience, imported_cv.experience):
            assert imported_exp.title == original_exp.title
            assert imported_exp.company == original_exp.company
            if original_exp.location:
                assert imported_exp.location == original_exp.location
            assert imported_exp.start_date == original_exp.start_date
            assert imported_exp.current == original_exp.current
            if not original_exp.current and original_exp.end_date:
                assert imported_exp.end_date == original_exp.end_date
        
        # Education entries should be preserved
        assert len(imported_cv.education) == len(cv_data.education)
        for original_edu, imported_edu in zip(cv_data.education, imported_cv.education):
            assert imported_edu.degree == original_edu.degree
            assert imported_edu.institution == original_edu.institution
            if original_edu.location:
                assert imported_edu.location == original_edu.location
        
        # Skills should be preserved
        assert len(imported_cv.skills.categories) == len(cv_data.skills.categories)
        for original_cat, imported_cat in zip(cv_data.skills.categories, imported_cv.skills.categories):
            assert imported_cat.name == original_cat.name
            # Skills within category should be preserved (order may vary)
            assert set(imported_cat.skills) == set(original_cat.skills)
        
        # Certifications should be preserved
        assert len(imported_cv.certifications) == len(cv_data.certifications)
        for original_cert, imported_cert in zip(cv_data.certifications, imported_cv.certifications):
            assert imported_cert.name == original_cert.name
            assert imported_cert.issuer == original_cert.issuer
            if original_cert.date:
                assert imported_cert.date == original_cert.date
    
    @given(cv_data=cv_model_strategy())
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
    )
    def test_double_round_trip_produces_stable_output(self, cv_data):
        """
        Property: For any valid CV data, performing two round trips
        (export->import->export->import) should produce the same result as one round trip.
        
        This tests idempotence of the round trip operation.
        
        Feature: cv-web-app, Property 8: Markdown Import Round Trip
        Validates: Requirements 4.1, 4.2, 4.4, 7.2
        """
        # Assume we have at least a name (required field)
        assume(cv_data.personal_info.name.strip() != "")
        
        # First round trip
        markdown1 = self.export_service.json_to_markdown(cv_data)
        imported1 = self.import_service.import_from_markdown(markdown1)
        
        # Second round trip
        markdown2 = self.export_service.json_to_markdown(imported1)
        imported2 = self.import_service.import_from_markdown(markdown2)
        
        # The two imported CVs should have the same content
        assert imported1.personal_info.name == imported2.personal_info.name
        assert imported1.personal_info.title == imported2.personal_info.title
        assert len(imported1.experience) == len(imported2.experience)
        assert len(imported1.education) == len(imported2.education)
        assert len(imported1.skills.categories) == len(imported2.skills.categories)
        assert len(imported1.certifications) == len(imported2.certifications)
    
    def test_minimal_cv_round_trip(self):
        """
        Test round trip with minimal CV data (only required fields).
        
        Feature: cv-web-app, Property 8: Markdown Import Round Trip
        Validates: Requirements 4.1, 4.2, 4.4, 7.2
        """
        # Create minimal CV with only required fields
        minimal_cv = CVModel(
            metadata=CVMetadata(
                title="Minimal CV",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                template_id="default"
            ),
            personal_info=PersonalInfo(
                name="John Doe",
                contact=ContactInfo()
            )
        )
        
        # Export to markdown
        markdown_content = self.export_service.json_to_markdown(minimal_cv)
        
        # Import back
        imported_cv = self.import_service.import_from_markdown(markdown_content)
        
        # Verify essential fields are preserved
        assert imported_cv.personal_info.name == "John Doe"
        assert len(imported_cv.experience) == 0
        assert len(imported_cv.education) == 0
        assert len(imported_cv.skills.categories) == 0
        assert len(imported_cv.certifications) == 0
    
    def test_complete_cv_round_trip(self):
        """
        Test round trip with a complete CV containing all sections.
        
        Feature: cv-web-app, Property 8: Markdown Import Round Trip
        Validates: Requirements 4.1, 4.2, 4.4, 7.2
        """
        # Create complete CV with all sections populated
        complete_cv = CVModel(
            metadata=CVMetadata(
                title="Complete CV",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                template_id="default"
            ),
            personal_info=PersonalInfo(
                name="Jane Smith",
                title="Senior Software Engineer",
                contact=ContactInfo(
                    address="123 Main St, City, State 12345",
                    phone="+1-555-123-4567",
                    email="jane.smith@example.com",
                    linkedin="https://linkedin.com/in/janesmith",
                    website="https://janesmith.dev"
                )
            ),
            summary="Experienced software engineer with 10+ years in web development.",
            experience=[
                Experience(
                    title="Senior Software Engineer",
                    company="Tech Corp",
                    location="San Francisco, CA",
                    start_date="January 2020",
                    end_date=None,
                    current=True,
                    description="Lead development of web applications.",
                    achievements=[
                        "Improved system performance by 50%",
                        "Led team of 5 developers"
                    ]
                )
            ],
            education=[
                Education(
                    degree="Bachelor of Science in Computer Science",
                    institution="University of Technology",
                    location="Boston, MA",
                    start_date="September 2014",
                    end_date="May 2018",
                    gpa="3.8",
                    description="Focused on software engineering and algorithms"
                )
            ],
            skills=Skills(
                categories=[
                    SkillCategory(
                        name="Programming Languages",
                        skills=["Python", "JavaScript", "TypeScript"]
                    ),
                    SkillCategory(
                        name="Frameworks",
                        skills=["React", "Vue.js", "FastAPI"]
                    )
                ]
            ),
            certifications=[
                Certification(
                    name="AWS Certified Solutions Architect",
                    issuer="Amazon Web Services",
                    date="June 2023",
                    expiry_date="June 2026"
                )
            ]
        )
        
        # Export to markdown
        markdown_content = self.export_service.json_to_markdown(complete_cv)
        
        # Import back
        imported_cv = self.import_service.import_from_markdown(markdown_content)
        
        # Verify all sections are preserved
        assert imported_cv.personal_info.name == "Jane Smith"
        assert imported_cv.personal_info.title == "Senior Software Engineer"
        assert imported_cv.personal_info.contact.email == "jane.smith@example.com"
        assert imported_cv.summary is not None
        assert "Experienced software engineer" in imported_cv.summary
        assert len(imported_cv.experience) == 1
        assert imported_cv.experience[0].title == "Senior Software Engineer"
        assert imported_cv.experience[0].current == True
        assert len(imported_cv.education) == 1
        assert imported_cv.education[0].degree == "Bachelor of Science in Computer Science"
        assert len(imported_cv.skills.categories) == 2
        assert len(imported_cv.certifications) == 1
        assert imported_cv.certifications[0].name == "AWS Certified Solutions Architect"
