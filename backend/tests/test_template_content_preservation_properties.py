"""
Property-based tests for template content preservation.

Feature: cv-web-app, Property 5: Template Content Preservation
Validates: Requirements 2.4, 3.3
"""
import tempfile
import shutil
import os
import json
from pathlib import Path
from typing import Dict, Any, List
import uuid

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime

from app.models.cv_models import (
    CVModel, PersonalInfo, CVMetadata, ContactInfo,
    Experience, Education, SkillCategory, Skills, Certification
)
from app.models.export_models import ExportFormat, ExportRequest
from app.services.export_service import ExportService


# Test data generators for valid CV data (reusing from other tests)
@st.composite
def contact_info_strategy(draw):
    """Generate valid ContactInfo data."""
    return ContactInfo(
        address=draw(st.one_of(st.none(), st.text(min_size=5, max_size=200))),
        phone=draw(st.one_of(st.none(), st.text(min_size=5, max_size=20))),
        email=draw(st.one_of(st.none(), st.emails())),
        linkedin=draw(st.one_of(st.none(), st.text(min_size=5, max_size=100))),
        website=draw(st.one_of(st.none(), st.text(min_size=5, max_size=100)))
    )


@st.composite
def personal_info_strategy(draw):
    """Generate valid PersonalInfo data."""
    # Generate non-whitespace-only name
    name = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs', 'Z'))))
    if not name or not name.strip():
        name = "John Doe"  # Fallback
    
    return PersonalInfo(
        name=name,
        title=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        contact=draw(contact_info_strategy())
    )


@st.composite
def cv_metadata_strategy(draw):
    """Generate valid CVMetadata data."""
    return CVMetadata(
        title=draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs')))),
        template_id=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))
    )


@st.composite
def experience_strategy(draw):
    """Generate valid Experience data."""
    current = draw(st.booleans())
    
    # Generate non-whitespace-only strings for required fields
    title = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs', 'Z'))))
    if not title or not title.strip():
        title = "Job Title"
    
    company = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs', 'Z'))))
    if not company or not company.strip():
        company = "Company"
    
    start_date = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=('Cc', 'Cs', 'Z'))))
    if not start_date or not start_date.strip():
        start_date = "2020"
    
    return Experience(
        title=title,
        company=company,
        location=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        start_date=start_date,
        end_date=None if current else draw(st.one_of(st.none(), st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        current=current,
        description=draw(st.one_of(st.none(), st.text(min_size=10, max_size=500, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        achievements=draw(st.lists(st.text(min_size=5, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))), min_size=0, max_size=5))
    )


@st.composite
def education_strategy(draw):
    """Generate valid Education data."""
    # Generate non-whitespace-only strings for required fields
    degree = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs', 'Z'))))
    if not degree or not degree.strip():
        degree = "Degree"
    
    institution = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs', 'Z'))))
    if not institution or not institution.strip():
        institution = "Institution"
    
    return Education(
        degree=degree,
        institution=institution,
        location=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        start_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        end_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        gpa=draw(st.one_of(st.none(), st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        description=draw(st.one_of(st.none(), st.text(min_size=10, max_size=300, alphabet=st.characters(blacklist_categories=('Cc', 'Cs')))))
    )


@st.composite
def skill_category_strategy(draw):
    """Generate valid SkillCategory data."""
    # Generate non-whitespace-only category name
    name = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cc', 'Cs', 'Z'))))
    if not name or not name.strip():
        name = "Skills"  # Fallback
    
    return SkillCategory(
        name=name,
        skills=draw(st.lists(st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))), min_size=0, max_size=10))
    )


@st.composite
def skills_strategy(draw):
    """Generate valid Skills data."""
    return Skills(
        categories=draw(st.lists(skill_category_strategy(), min_size=0, max_size=5))
    )


@st.composite
def certification_strategy(draw):
    """Generate valid Certification data."""
    # Generate non-whitespace-only strings
    name = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs', 'Z'))))
    if not name or not name.strip():
        name = "Certification"  # Fallback to avoid empty/whitespace-only names
    
    issuer = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs', 'Z'))))
    if not issuer or not issuer.strip():
        issuer = "Issuer"  # Fallback
    
    return Certification(
        name=name,
        issuer=issuer,
        date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        expiry_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=('Cc', 'Cs')))))
    )


@st.composite
def cv_model_strategy(draw):
    """Generate valid CVModel data."""
    return CVModel(
        id=str(uuid.uuid4()),
        metadata=draw(cv_metadata_strategy()),
        personal_info=draw(personal_info_strategy()),
        summary=draw(st.one_of(st.none(), st.text(min_size=10, max_size=500, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))),
        experience=draw(st.lists(experience_strategy(), min_size=0, max_size=3)),
        education=draw(st.lists(education_strategy(), min_size=0, max_size=3)),
        skills=draw(skills_strategy()),
        certifications=draw(st.lists(certification_strategy(), min_size=0, max_size=3))
    )


@pytest.fixture
def temp_root_dir():
    """Fixture providing temporary root directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="cv_template_preservation_test_")
    
    # Create required directory structure
    directories = [
        "cv", "exports/pdf", "exports/docx", "exports/txt", 
        "templates", "pandoc", "scripts"
    ]
    
    for directory in directories:
        (Path(temp_dir) / directory).mkdir(parents=True, exist_ok=True)
    
    # Copy required files from the actual project
    project_root = Path(__file__).parent.parent.parent
    
    # Copy export script
    export_script_src = project_root / "scripts" / "export.sh"
    export_script_dst = Path(temp_dir) / "scripts" / "export.sh"
    if export_script_src.exists():
        shutil.copy2(export_script_src, export_script_dst)
        os.chmod(export_script_dst, 0o755)  # Make executable
    
    # Copy templates
    template_src = project_root / "templates" / "cv.latex"
    template_dst = Path(temp_dir) / "templates" / "cv.latex"
    if template_src.exists():
        shutil.copy2(template_src, template_dst)
    
    # Copy pandoc configuration
    pandoc_src = project_root / "pandoc" / "defaults.yaml"
    pandoc_dst = Path(temp_dir) / "pandoc" / "defaults.yaml"
    if pandoc_src.exists():
        shutil.copy2(pandoc_src, pandoc_dst)
    
    # Copy pandoc filter
    filter_src = project_root / "pandoc" / "no_em_dash.lua"
    filter_dst = Path(temp_dir) / "pandoc" / "no_em_dash.lua"
    if filter_src.exists():
        shutil.copy2(filter_src, filter_dst)
    
    # Copy reference docx
    ref_docx_src = project_root / "scripts" / "reference.docx"
    ref_docx_dst = Path(temp_dir) / "scripts" / "reference.docx"
    if ref_docx_src.exists():
        shutil.copy2(ref_docx_src, ref_docx_dst)
    
    # Copy additional scripts that might be needed
    for script_name in ["normalize_txt.sh", "tune_docx.py"]:
        script_src = project_root / "scripts" / script_name
        script_dst = Path(temp_dir) / "scripts" / script_name
        if script_src.exists():
            shutil.copy2(script_src, script_dst)
            if script_name.endswith('.sh'):
                os.chmod(script_dst, 0o755)  # Make executable
    
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def export_service(temp_root_dir):
    """Fixture providing ExportService with temporary directory."""
    return ExportService(
        root_dir=temp_root_dir,
        export_script_path=Path(temp_root_dir) / "scripts" / "export.sh"
    )


def _extract_content_from_markdown(markdown_content: str) -> Dict[str, Any]:
    """
    Extract structured content from markdown for comparison.
    
    Args:
        markdown_content: Markdown content to parse
        
    Returns:
        Dictionary with extracted content fields
    """
    content = {
        "name": None,
        "title": None,
        "contact": {},
        "summary": None,
        "experience": [],
        "education": [],
        "skills": [],
        "certifications": []
    }
    
    lines = markdown_content.split('\n')
    current_section = None
    in_frontmatter = False
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Handle YAML frontmatter
        if line == '---':
            in_frontmatter = not in_frontmatter
            continue
        
        if in_frontmatter:
            continue
        
        # Main heading (name) - must be first non-frontmatter heading
        if line.startswith('# ') and content["name"] is None:
            content["name"] = line[2:].strip()
            continue
        
        # Professional title: the first line after the name and before any
        # section heading. Exports render it as plain text; older ones
        # italicised it, so accept both.
        if (content["name"] is not None and
                content["title"] is None and
                current_section is None and
                line and not line.startswith('#')):
            if line.startswith('*') and line.endswith('*') and len(line) > 2:
                content["title"] = line[1:-1].strip()
            else:
                content["title"] = line
            continue
        
        # Section headings
        if line.startswith('## '):
            current_section = line[3:].lower().strip()
            continue
        
        # Skip empty lines
        if not line:
            continue
        
        # Experience entries
        if current_section == "experience" and line.startswith('### '):
            content["experience"].append(line[4:].strip())
            continue
        
        # Education entries
        if current_section == "education" and line.startswith('### '):
            content["education"].append(line[4:].strip())
            continue
        
        # Skills entries - handle multiple formats
        if current_section == "skills":
            # Format: **Category:** skills or **Category:**
            if line.startswith('**') and '**' in line[2:]:
                # Find the closing **
                closing_pos = line.find('**', 2)
                if closing_pos > 2:
                    skill_category = line[2:closing_pos].rstrip(':').strip()
                    if skill_category:  # Only add non-empty categories
                        content["skills"].append(skill_category)
            continue
        
        # Certifications entries - format: - **Name** - Issuer (Date)
        if current_section == "certifications" and line.startswith('- **'):
            # Extract certification name from: - **Name** - Issuer
            closing_pos = line.find('**', 4)
            if closing_pos > 4:
                cert_name = line[4:closing_pos]  # Don't strip yet
                # Only add if not empty or whitespace-only after stripping
                if cert_name.strip():
                    content["certifications"].append(cert_name.strip())
            continue
        
        # Summary content - collect all non-heading lines in summary section
        if current_section == "summary" and not line.startswith('#'):
            if content["summary"] is None:
                content["summary"] = line
            else:
                content["summary"] += " " + line
            continue
        
        # Contact information (email, phone, etc.) - only before first section
        if current_section is None and content["name"] is not None:
            # Email links
            if 'mailto:' in line:
                email_start = line.find('mailto:') + 7
                email_end = line.find(')', email_start)
                if email_end > email_start:
                    content["contact"]["email"] = line[email_start:email_end]
            # LinkedIn links
            elif 'linkedin' in line.lower() and '](' in line:
                content["contact"]["linkedin"] = True
            # Website links
            elif 'http' in line.lower() and '](' in line and 'linkedin' not in line.lower():
                content["contact"]["website"] = True
            # Phone and address (simple text lines without links)
            elif not line.startswith('[') and not line.startswith('#') and not line.startswith('*'):
                if any(char.isdigit() for char in line):
                    content["contact"]["phone"] = line
                elif len(line) > 5:  # Likely address
                    content["contact"]["address"] = line
    
    return content


def _compare_cv_content(cv_data: CVModel, markdown_content: str) -> bool:
    """
    Compare CV data with extracted markdown content to verify preservation.
    
    Args:
        cv_data: Original CV data
        markdown_content: Generated markdown content
        
    Returns:
        True if content is preserved, False otherwise
    """
    extracted = _extract_content_from_markdown(markdown_content)
    
    # Check name preservation (required field)
    if extracted["name"] != cv_data.personal_info.name:
        return False
    
    # Check title preservation (optional field)
    if cv_data.personal_info.title:
        if extracted["title"] != cv_data.personal_info.title:
            return False
    
    # Check experience preservation
    if cv_data.experience:
        expected_titles = [exp.title for exp in cv_data.experience]
        # All expected titles should be in extracted experience
        for title in expected_titles:
            if title not in extracted["experience"]:
                return False
        # Should have same number of entries
        if len(expected_titles) != len(extracted["experience"]):
            return False
    else:
        # If no experience in CV, should have no experience in extracted
        if extracted["experience"]:
            return False
    
    # Check education preservation
    if cv_data.education:
        expected_degrees = [edu.degree for edu in cv_data.education]
        # All expected degrees should be in extracted education
        for degree in expected_degrees:
            if degree not in extracted["education"]:
                return False
        # Should have same number of entries
        if len(expected_degrees) != len(extracted["education"]):
            return False
    else:
        # If no education in CV, should have no education in extracted
        if extracted["education"]:
            return False
    
    # Check skills preservation - only check categories that have skills
    if cv_data.skills and cv_data.skills.categories:
        categories_with_skills = [cat for cat in cv_data.skills.categories if cat.skills]
        if categories_with_skills:
            expected_categories = [cat.name for cat in categories_with_skills]
            # All expected categories should be in extracted skills
            for category in expected_categories:
                if category not in extracted["skills"]:
                    return False
            # Should have same number of categories
            if len(expected_categories) != len(extracted["skills"]):
                return False
        else:
            # If no categories with skills, should have no skills in extracted
            if extracted["skills"]:
                return False
    else:
        # If no skills in CV, should have no skills in extracted
        if extracted["skills"]:
            return False
    
    # Check certifications preservation
    if cv_data.certifications:
        expected_cert_names = [cert.name for cert in cv_data.certifications]
        for cert_name in expected_cert_names:
            if cert_name not in extracted["certifications"]:
                return False
        if len(expected_cert_names) != len(extracted["certifications"]):
            return False
    else:
        if extracted["certifications"]:
            return False
    
    # Check summary preservation (if present)
    if cv_data.summary:
        if not extracted["summary"]:
            return False
        # Allow for minor formatting differences
        original_words = set(cv_data.summary.lower().split())
        extracted_words = set(extracted["summary"].lower().split())
        # Check that most words are preserved (allowing for some formatting differences)
        if len(original_words.intersection(extracted_words)) < len(original_words) * 0.8:
            return False
    else:
        # If no summary in CV, extracted summary should be None or empty
        if extracted["summary"]:
            return False
    
    return True


class TestTemplateContentPreservation:
    """Property-based tests for template content preservation."""
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_template_content_preservation_markdown_conversion(self, export_service, cv_data):
        """
        Property 5: Template Content Preservation - Markdown Conversion
        
        For any CV data and template change, all content fields should remain 
        identical while only visual presentation changes. This test verifies
        that the markdown conversion preserves all content data.
        
        **Validates: Requirements 2.4, 3.3**
        """
        # Step 1: Convert CV to markdown with default template
        original_template_id = cv_data.metadata.template_id
        markdown_content_original = export_service.json_to_markdown(cv_data)
        
        # Step 2: Change template ID and convert again
        cv_data_with_new_template = cv_data.model_copy(deep=True)
        cv_data_with_new_template.metadata.template_id = "alternative_template"
        markdown_content_new_template = export_service.json_to_markdown(cv_data_with_new_template)
        
        # Step 3: Verify that content is preserved in both conversions
        assert _compare_cv_content(cv_data, markdown_content_original), \
            "Original template conversion should preserve all CV content"
        
        assert _compare_cv_content(cv_data_with_new_template, markdown_content_new_template), \
            "New template conversion should preserve all CV content"
        
        # Step 4: Extract content from both markdown versions
        original_content = _extract_content_from_markdown(markdown_content_original)
        new_template_content = _extract_content_from_markdown(markdown_content_new_template)
        
        # Step 5: Verify content fields are identical between templates
        assert original_content["name"] == new_template_content["name"], \
            "Name should be identical across template changes"
        
        assert original_content["title"] == new_template_content["title"], \
            "Professional title should be identical across template changes"
        
        assert original_content["experience"] == new_template_content["experience"], \
            "Experience entries should be identical across template changes"
        
        assert original_content["education"] == new_template_content["education"], \
            "Education entries should be identical across template changes"
        
        assert original_content["skills"] == new_template_content["skills"], \
            "Skills categories should be identical across template changes"
        
        # Step 6: Verify that summary content is preserved (allowing for minor formatting)
        if original_content["summary"] and new_template_content["summary"]:
            original_words = set(original_content["summary"].lower().split())
            new_words = set(new_template_content["summary"].lower().split())
            assert original_words == new_words, \
                "Summary content should be identical across template changes"
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_template_content_preservation_export_consistency(self, export_service, cv_data):
        """
        Property 5: Template Content Preservation - Export Consistency
        
        For any CV data, exporting with different template IDs should preserve
        all content while only changing visual presentation.
        
        **Validates: Requirements 2.4, 3.3**
        """
        # Use TXT format for content comparison (easiest to parse)
        export_format = ExportFormat.TXT
        
        # Step 1: Export with default template
        export_request_default = ExportRequest(
            cv_id=cv_data.id,
            format=export_format,
            template_id="default"
        )
        
        export_response_default = export_service.export_cv(cv_data, export_request_default)
        
        # Step 2: Export with alternative template (simulated by changing metadata)
        cv_data_alt_template = cv_data.model_copy(deep=True)
        cv_data_alt_template.metadata.template_id = "alternative"
        
        export_request_alt = ExportRequest(
            cv_id=cv_data_alt_template.id,
            format=export_format,
            template_id="alternative"
        )
        
        export_response_alt = export_service.export_cv(cv_data_alt_template, export_request_alt)
        
        # Step 3: If both exports succeeded, compare content
        if (export_response_default.status.value == "completed" and 
            export_response_alt.status.value == "completed"):
            
            # Read content from both exported files
            default_file_path = Path(export_response_default.file_path)
            alt_file_path = Path(export_response_alt.file_path)
            
            assert default_file_path.exists(), "Default template export file should exist"
            assert alt_file_path.exists(), "Alternative template export file should exist"
            
            with open(default_file_path, 'r', encoding='utf-8') as f:
                default_content = f.read()
            
            with open(alt_file_path, 'r', encoding='utf-8') as f:
                alt_content = f.read()
            
            # Step 4: Verify essential content is present in both files
            assert cv_data.personal_info.name in default_content, \
                "Name should be present in default template export"
            assert cv_data.personal_info.name in alt_content, \
                "Name should be present in alternative template export"
            
            # Check experience titles
            if cv_data.experience:
                for exp in cv_data.experience:
                    assert exp.title in default_content, \
                        f"Experience title '{exp.title}' should be in default template export"
                    assert exp.title in alt_content, \
                        f"Experience title '{exp.title}' should be in alternative template export"
            
            # Check education degrees
            if cv_data.education:
                for edu in cv_data.education:
                    assert edu.degree in default_content, \
                        f"Education degree '{edu.degree}' should be in default template export"
                    assert edu.degree in alt_content, \
                        f"Education degree '{edu.degree}' should be in alternative template export"
            
            # Check skills
            if cv_data.skills.categories:
                categories_with_skills = [cat for cat in cv_data.skills.categories if cat.skills]
                for category in categories_with_skills:
                    assert category.name in default_content, \
                        f"Skill category '{category.name}' should be in default template export"
                    assert category.name in alt_content, \
                        f"Skill category '{category.name}' should be in alternative template export"
        
        # Step 5: Verify that both exports have consistent metadata
        assert export_response_default.cv_id == cv_data.id, \
            "Default export should have correct CV ID"
        assert export_response_alt.cv_id == cv_data_alt_template.id, \
            "Alternative export should have correct CV ID"
        
        assert export_response_default.format == export_format, \
            "Default export should have correct format"
        assert export_response_alt.format == export_format, \
            "Alternative export should have correct format"
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_template_content_preservation_data_integrity(self, export_service, cv_data):
        """
        Property 5: Template Content Preservation - Data Integrity
        
        For any CV data, the original CV object should remain unchanged
        after template operations and exports.
        
        **Validates: Requirements 2.4, 3.3**
        """
        # Step 1: Create a deep copy of original CV data for comparison
        original_cv_json = cv_data.model_dump_json()
        original_cv_dict = json.loads(original_cv_json)
        
        # Step 2: Perform markdown conversion (simulating template change)
        markdown_content = export_service.json_to_markdown(cv_data)
        
        # Step 3: Verify original CV data is unchanged
        current_cv_json = cv_data.model_dump_json()
        current_cv_dict = json.loads(current_cv_json)
        
        assert original_cv_dict == current_cv_dict, \
            "Original CV data should remain unchanged after markdown conversion"
        
        # Step 4: Perform export operation
        export_request = ExportRequest(
            cv_id=cv_data.id,
            format=ExportFormat.TXT,
            template_id="default"
        )
        
        export_response = export_service.export_cv(cv_data, export_request)
        
        # Step 5: Verify CV data is still unchanged after export
        post_export_cv_json = cv_data.model_dump_json()
        post_export_cv_dict = json.loads(post_export_cv_json)
        
        assert original_cv_dict == post_export_cv_dict, \
            "Original CV data should remain unchanged after export operation"
        
        # Step 6: Verify specific fields are preserved
        assert cv_data.personal_info.name == original_cv_dict["personal_info"]["name"], \
            "Personal name should be unchanged"
        
        assert cv_data.metadata.title == original_cv_dict["metadata"]["title"], \
            "CV title should be unchanged"
        
        if cv_data.experience:
            for i, exp in enumerate(cv_data.experience):
                original_exp = original_cv_dict["experience"][i]
                assert exp.title == original_exp["title"], \
                    f"Experience {i} title should be unchanged"
                assert exp.company == original_exp["company"], \
                    f"Experience {i} company should be unchanged"
        
        if cv_data.education:
            for i, edu in enumerate(cv_data.education):
                original_edu = original_cv_dict["education"][i]
                assert edu.degree == original_edu["degree"], \
                    f"Education {i} degree should be unchanged"
                assert edu.institution == original_edu["institution"], \
                    f"Education {i} institution should be unchanged"
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_template_content_preservation_markdown_structure(self, export_service, cv_data):
        """
        Property 5: Template Content Preservation - Markdown Structure
        
        For any CV data, the generated markdown should maintain consistent
        structure regardless of template changes, preserving all content sections.
        
        **Validates: Requirements 2.4, 3.3**
        """
        # Step 1: Generate markdown with original template
        markdown_original = export_service.json_to_markdown(cv_data)
        
        # Step 2: Change template and generate markdown again
        cv_data_new_template = cv_data.model_copy(deep=True)
        cv_data_new_template.metadata.template_id = "new_template"
        markdown_new_template = export_service.json_to_markdown(cv_data_new_template)
        
        # Step 3: Verify both markdown versions contain required sections
        required_sections = ["# " + cv_data.personal_info.name]  # Name as main heading
        
        if cv_data.experience:
            required_sections.append("## Experience")
        
        if cv_data.education:
            required_sections.append("## Education")
        
        # Only expect skills section if there are categories with actual skills
        if cv_data.skills.categories:
            categories_with_skills = [cat for cat in cv_data.skills.categories if cat.skills]
            if categories_with_skills:
                required_sections.append("## Skills")
        
        if cv_data.certifications:
            required_sections.append("## Certifications")
        
        if cv_data.summary:
            required_sections.append("## Summary")
        
        # Check original template markdown
        for section in required_sections:
            assert section in markdown_original, \
                f"Section '{section}' should be present in original template markdown"
        
        # Check new template markdown
        for section in required_sections:
            assert section in markdown_new_template, \
                f"Section '{section}' should be present in new template markdown"
        
        # Step 4: Verify YAML frontmatter is present in both
        assert markdown_original.startswith("---"), \
            "Original template markdown should start with YAML frontmatter"
        assert markdown_new_template.startswith("---"), \
            "New template markdown should start with YAML frontmatter"
        
        # Step 5: Verify content preservation in both versions
        assert _compare_cv_content(cv_data, markdown_original), \
            "Original template markdown should preserve all CV content"
        assert _compare_cv_content(cv_data_new_template, markdown_new_template), \
            "New template markdown should preserve all CV content"


# Additional unit tests for specific template preservation scenarios
class TestTemplateContentPreservationEdgeCases:
    """Unit tests for specific template content preservation edge cases."""
    
    def test_minimal_cv_template_preservation(self, export_service):
        """Test template preservation with minimal CV data."""
        minimal_cv = CVModel(
            metadata=CVMetadata(title="Minimal CV", template_id="default"),
            personal_info=PersonalInfo(name="Test User")
        )
        
        # Convert with original template
        markdown_original = export_service.json_to_markdown(minimal_cv)
        
        # Change template
        minimal_cv.metadata.template_id = "alternative"
        markdown_new = export_service.json_to_markdown(minimal_cv)
        
        # Both should contain the name
        assert "# Test User" in markdown_original
        assert "# Test User" in markdown_new
        
        # Content should be preserved
        assert _compare_cv_content(minimal_cv, markdown_original)
        assert _compare_cv_content(minimal_cv, markdown_new)
    
    def test_cv_with_special_characters_template_preservation(self, export_service):
        """Test template preservation with special characters in CV data."""
        special_cv = CVModel(
            metadata=CVMetadata(title="CV with Special Characters", template_id="default"),
            personal_info=PersonalInfo(
                name="José María García-López",
                title="Senior Developer & Team Lead"
            ),
            summary="Experience with C++, .NET, and other technologies: @#$%^&*()"
        )
        
        # Convert with original template
        markdown_original = export_service.json_to_markdown(special_cv)
        
        # Change template
        special_cv.metadata.template_id = "alternative"
        markdown_new = export_service.json_to_markdown(special_cv)
        
        # Special characters should be preserved in both
        assert "José María García-López" in markdown_original
        assert "José María García-López" in markdown_new
        assert "Senior Developer & Team Lead" in markdown_original
        assert "Senior Developer & Team Lead" in markdown_new
        assert "C++, .NET" in markdown_original
        assert "C++, .NET" in markdown_new
    
    def test_empty_sections_template_preservation(self, export_service):
        """Test template preservation with empty sections."""
        cv_with_empty_sections = CVModel(
            metadata=CVMetadata(title="CV with Empty Sections", template_id="default"),
            personal_info=PersonalInfo(name="Test User"),
            experience=[],  # Empty experience
            education=[],   # Empty education
            skills=Skills(categories=[]),  # Empty skills
            certifications=[]  # Empty certifications
        )
        
        # Convert with original template
        markdown_original = export_service.json_to_markdown(cv_with_empty_sections)
        
        # Change template
        cv_with_empty_sections.metadata.template_id = "alternative"
        markdown_new = export_service.json_to_markdown(cv_with_empty_sections)
        
        # Name should be preserved
        assert "# Test User" in markdown_original
        assert "# Test User" in markdown_new
        
        # Empty sections should not create section headers
        assert "## Experience" not in markdown_original
        assert "## Experience" not in markdown_new
        assert "## Education" not in markdown_original
        assert "## Education" not in markdown_new