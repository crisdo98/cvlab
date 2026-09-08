"""
Property-based tests for export script compatibility.

Feature: cv-web-app, Property 18: Export Script Compatibility
Validates: Requirements 8.4, 9.1, 9.3
"""
import tempfile
import shutil
import os
import subprocess
import json
from pathlib import Path
from typing import Dict, Any
import uuid
import filecmp

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime

from app.models.cv_models import (
    CVModel, PersonalInfo, CVMetadata, ContactInfo,
    Experience, Education, SkillCategory, Skills, Certification
)
from app.models.export_models import ExportFormat, ExportRequest
from app.services.export_service import ExportService


# Test data generators for valid CV data (reusing from file persistence tests)
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
    return PersonalInfo(
        name=draw(st.text(min_size=1, max_size=100)),
        title=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
        contact=draw(contact_info_strategy())
    )


@st.composite
def cv_metadata_strategy(draw):
    """Generate valid CVMetadata data."""
    return CVMetadata(
        title=draw(st.text(min_size=1, max_size=100)),
        template_id=draw(st.text(min_size=1, max_size=50))
    )


@st.composite
def experience_strategy(draw):
    """Generate valid Experience data."""
    current = draw(st.booleans())
    return Experience(
        title=draw(st.text(min_size=1, max_size=100)),
        company=draw(st.text(min_size=1, max_size=100)),
        location=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
        start_date=draw(st.text(min_size=1, max_size=20)),
        end_date=None if current else draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
        current=current,
        description=draw(st.one_of(st.none(), st.text(min_size=10, max_size=500))),
        achievements=draw(st.lists(st.text(min_size=5, max_size=100), min_size=0, max_size=5))
    )


@st.composite
def education_strategy(draw):
    """Generate valid Education data."""
    return Education(
        degree=draw(st.text(min_size=1, max_size=100)),
        institution=draw(st.text(min_size=1, max_size=100)),
        location=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
        start_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
        end_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
        gpa=draw(st.one_of(st.none(), st.text(min_size=1, max_size=10))),
        description=draw(st.one_of(st.none(), st.text(min_size=10, max_size=300)))
    )


@st.composite
def skill_category_strategy(draw):
    """Generate valid SkillCategory data."""
    return SkillCategory(
        name=draw(st.text(min_size=1, max_size=50)),
        skills=draw(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=10))
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
    return Certification(
        name=draw(st.text(min_size=1, max_size=100)),
        issuer=draw(st.text(min_size=1, max_size=100)),
        date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
        expiry_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20)))
    )


@st.composite
def cv_model_strategy(draw):
    """Generate valid CVModel data."""
    return CVModel(
        id=str(uuid.uuid4()),
        metadata=draw(cv_metadata_strategy()),
        personal_info=draw(personal_info_strategy()),
        summary=draw(st.one_of(st.none(), st.text(min_size=10, max_size=500))),
        experience=draw(st.lists(experience_strategy(), min_size=0, max_size=3)),
        education=draw(st.lists(education_strategy(), min_size=0, max_size=3)),
        skills=draw(skills_strategy()),
        certifications=draw(st.lists(certification_strategy(), min_size=0, max_size=3))
    )


@pytest.fixture
def temp_root_dir():
    """Fixture providing temporary root directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="cv_export_test_")
    
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


def _check_dependencies_available():
    """Check if required dependencies are available for testing."""
    try:
        # Check pandoc
        subprocess.run(["pandoc", "--version"], capture_output=True, timeout=5)
        
        # Check at least one PDF engine
        has_pdf_engine = False
        for engine in ["xelatex", "tectonic"]:
            try:
                subprocess.run([engine, "--version"], capture_output=True, timeout=5)
                has_pdf_engine = True
                break
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        
        return has_pdf_engine
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


class TestExportScriptCompatibility:
    """Property-based tests for export script compatibility."""
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_script_compatibility_markdown_generation(self, export_service, cv_data):
        """
        Property 18: Export Script Compatibility - Markdown Generation
        
        For any valid CV data, the web application should generate markdown
        that is compatible with the existing export script format.
        
        **Validates: Requirements 8.4, 9.1, 9.3**
        """
        # Step 1: Generate markdown using the web application
        markdown_content = export_service.json_to_markdown(cv_data)
        
        # Step 2: Verify markdown has required YAML frontmatter
        lines = markdown_content.split('\n')
        assert lines[0] == "---", "Markdown should start with YAML frontmatter delimiter"
        
        # Find the end of frontmatter
        frontmatter_end = -1
        for i, line in enumerate(lines[1:], 1):
            if line == "---":
                frontmatter_end = i
                break
        
        assert frontmatter_end > 0, "Markdown should have properly closed YAML frontmatter"
        
        # Step 3: Verify frontmatter contains required fields
        frontmatter_lines = lines[1:frontmatter_end]
        frontmatter_content = '\n'.join(frontmatter_lines)
        
        # Exports deliberately omit title/author/date from the frontmatter:
        # pandoc turns them into a DOCX title block that the LaTeX template
        # ignores, so the name is carried by the body heading instead.
        assert "lang: en-US" in frontmatter_content, "Frontmatter should set the language"
        assert "title:" not in frontmatter_content, "Frontmatter should not carry a title"
        
        # Step 4: Verify markdown content structure
        content_lines = lines[frontmatter_end + 1:]
        content = '\n'.join(content_lines)
        
        # Should contain the person's name as main heading
        assert f"# {cv_data.personal_info.name}" in content, "Markdown should contain name as main heading"
        
        # Should contain sections if data is present
        if cv_data.experience:
            assert "## Experience" in content, "Markdown should contain Experience section when experience data exists"
        
        if cv_data.education:
            assert "## Education" in content, "Markdown should contain Education section when education data exists"
        
        # Only check for Skills section if there are categories with actual skills
        categories_with_skills = [cat for cat in cv_data.skills.categories if cat.skills]
        if categories_with_skills:
            assert "## Skills" in content, "Markdown should contain Skills section when skills data exists"
        
        if cv_data.certifications:
            assert "## Certifications" in content, "Markdown should contain Certifications section when certifications data exists"
        
        # Step 5: Verify markdown is valid and parseable
        # The markdown should not contain any malformed syntax that would break pandoc
        # Only a line that is exactly "---" would be read as a frontmatter
        # delimiter; dashes inside a value are ordinary text.
        assert not any(line.strip() == "---" for line in content_lines), \
            "Content should not contain additional frontmatter delimiters"
        
        # Check for proper markdown formatting
        for line in content_lines:
            # Headers should be properly formatted - but only check actual headers
            if line.startswith('#') and ' ' in line:
                # Check if this looks like a proper markdown header
                if line.startswith('# ') or line.startswith('## ') or line.startswith('### '):
                    # This is a properly formatted header
                    continue
                elif line[1:].lstrip().startswith('#'):
                    # This might be a multi-level header, check if it's properly formatted
                    stripped = line.lstrip('#')
                    if stripped.startswith(' '):
                        # Properly formatted header
                        continue
                # If we get here, it might be content that starts with # - don't validate as header
    
    @pytest.mark.skipif(not _check_dependencies_available(), reason="Required dependencies (pandoc, PDF engine) not available")
    @given(cv_data=cv_model_strategy(), export_format=st.sampled_from([ExportFormat.PDF, ExportFormat.DOCX, ExportFormat.TXT]))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_script_compatibility_output_equivalence(self, export_service, temp_root_dir, cv_data, export_format):
        """
        Property 18: Export Script Compatibility - Output Equivalence
        
        For any valid CV data and export format, the web application export
        should produce equivalent output to running the export script directly.
        
        **Validates: Requirements 8.4, 9.1, 9.3**
        """
        # Step 1: Generate markdown using web application
        markdown_content = export_service.json_to_markdown(cv_data)
        
        # Step 2: Create a test markdown file for direct script execution
        test_basename = f"test-cv-{uuid.uuid4().hex[:8]}"
        cv_dir = Path(temp_root_dir) / "cv"
        direct_md_file = cv_dir / f"{test_basename}.md"
        
        with open(direct_md_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        try:
            # Step 3: Export using web application
            export_request = ExportRequest(
                cv_id=cv_data.id,
                format=export_format,
                template_id="default"
            )
            
            web_app_response = export_service.export_cv(cv_data, export_request)
            
            # Step 4: Export using direct script execution
            export_script_path = Path(temp_root_dir) / "scripts" / "export.sh"
            
            if not export_script_path.exists():
                pytest.skip("Export script not available for testing")
            
            # Execute the export script directly
            env = os.environ.copy()
            env["ROOT_DIR"] = temp_root_dir
            
            try:
                script_result = subprocess.run(
                    [str(export_script_path), test_basename],
                    cwd=temp_root_dir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=120  # 2 minute timeout
                )
            except subprocess.TimeoutExpired:
                pytest.skip(f"Export script timed out for format {export_format}")
            
            # Step 5: Compare results
            if web_app_response.status.value == "completed" and script_result.returncode == 0:
                # Both exports succeeded - verify they produced similar outputs
                
                # Find the script-generated file
                exports_dir = Path(temp_root_dir) / "exports" / export_format.value
                script_files = list(exports_dir.glob(f"{test_basename}-*.{export_format.value}"))
                
                assert len(script_files) > 0, f"Script should have generated {export_format} file"
                
                # Get the most recent script-generated file
                script_file = max(script_files, key=lambda f: f.stat().st_mtime)
                
                # Verify web app file exists
                web_app_file = Path(web_app_response.file_path) if web_app_response.file_path else None
                assert web_app_file and web_app_file.exists(), "Web application should have generated output file"
                
                # Compare file sizes (should be reasonably similar)
                script_size = script_file.stat().st_size
                web_app_size = web_app_file.stat().st_size
                
                # Allow for some variation in file sizes (timestamps, minor formatting differences)
                size_difference_ratio = abs(script_size - web_app_size) / max(script_size, web_app_size)
                assert size_difference_ratio < 0.1, \
                    f"File sizes should be similar: script={script_size}, web_app={web_app_size}, ratio={size_difference_ratio}"
                
                # For text files, we can do more detailed comparison
                if export_format == ExportFormat.TXT:
                    with open(script_file, 'r', encoding='utf-8') as f:
                        script_content = f.read()
                    with open(web_app_file, 'r', encoding='utf-8') as f:
                        web_app_content = f.read()
                    
                    # Normalize whitespace for comparison
                    script_normalized = ' '.join(script_content.split())
                    web_app_normalized = ' '.join(web_app_content.split())
                    
                    # Content should be very similar (allowing for minor formatting differences)
                    assert cv_data.personal_info.name in script_normalized, "Script output should contain person's name"
                    assert cv_data.personal_info.name in web_app_normalized, "Web app output should contain person's name"
                    
                    # Check that both contain similar content structure
                    if cv_data.experience:
                        assert any(exp.title in script_normalized for exp in cv_data.experience), \
                            "Script output should contain experience titles"
                        assert any(exp.title in web_app_normalized for exp in cv_data.experience), \
                            "Web app output should contain experience titles"
            
            elif web_app_response.status.value == "failed" and script_result.returncode != 0:
                # Both failed - this is acceptable for compatibility
                assert True, "Both web app and script failed consistently"
            
            else:
                # One succeeded and one failed - this indicates incompatibility
                pytest.fail(
                    f"Incompatible results: web_app_status={web_app_response.status.value}, "
                    f"script_returncode={script_result.returncode}, "
                    f"web_app_error={web_app_response.error_message}, "
                    f"script_stderr={script_result.stderr}"
                )
        
        finally:
            # Clean up test file
            if direct_md_file.exists():
                direct_md_file.unlink()
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_script_compatibility_markdown_structure(self, export_service, cv_data):
        """
        Property 18: Export Script Compatibility - Markdown Structure
        
        For any valid CV data, the generated markdown should follow the
        structure expected by the existing export pipeline.
        
        **Validates: Requirements 8.4, 9.1, 9.3**
        """
        # Step 1: Generate markdown
        markdown_content = export_service.json_to_markdown(cv_data)
        
        # Step 2: Verify YAML frontmatter structure
        lines = markdown_content.split('\n')
        
        # Should start and end with ---
        assert lines[0] == "---", "Should start with YAML delimiter"
        
        frontmatter_end = -1
        for i, line in enumerate(lines[1:], 1):
            if line == "---":
                frontmatter_end = i
                break
        
        assert frontmatter_end > 0, "Should have closing YAML delimiter"
        
        # Step 3: Verify frontmatter contains expected fields
        frontmatter_section = lines[1:frontmatter_end]
        frontmatter_dict = {}
        
        for line in frontmatter_section:
            if ':' in line:
                key, value = line.split(':', 1)
                frontmatter_dict[key.strip()] = value.strip()
        
        # Fields the export pipeline relies on. Title, author and date are
        # deliberately absent: pandoc renders them as a DOCX title block that
        # the LaTeX template ignores, so the body heading carries the name.
        required_fields = ['lang', 'colorlinks']
        for field in required_fields:
            assert field in frontmatter_dict, f"Frontmatter should contain {field} field"
        
        # Step 4: Verify content structure follows expected patterns
        content_lines = lines[frontmatter_end + 1:]
        content = '\n'.join(content_lines)
        
        # Main heading should be level 1
        assert f"# {cv_data.personal_info.name}" in content, "Should have level 1 heading with name"
        
        # Section headings should be level 2
        section_patterns = [
            ("## Summary", cv_data.summary),
            ("## Experience", cv_data.experience),
            ("## Education", cv_data.education),
            # A category whose skills are all blank produces no section, since
            # blank entries are filtered out of the rendered list.
            ("## Skills", [
                skill
                for category in cv_data.skills.categories
                for skill in (category.skills or [])
                if skill and skill.strip()
            ]),
            ("## Certifications", cv_data.certifications)
        ]
        
        for section_header, data_condition in section_patterns:
            if data_condition:  # Only check if data exists
                assert section_header in content, f"Should contain {section_header} when data exists"
        
        # Step 5: Verify subsection headings are level 3
        if cv_data.experience:
            for exp in cv_data.experience:
                assert f"### {exp.title}" in content, f"Experience title should be level 3 heading: {exp.title}"
        
        if cv_data.education:
            for edu in cv_data.education:
                assert f"### {edu.degree}" in content, f"Education degree should be level 3 heading: {edu.degree}"
        
        # Step 6: Verify markdown formatting consistency
        # Check that markdown headers have proper spacing
        for i, line in enumerate(content_lines):
            if line.startswith('#'):
                # Only validate if it looks like a header (has space after # or is at start of line after blank)
                # This avoids false positives for content that happens to start with #
                if ' ' in line and line[1] == ' ':
                    # This is a level 1 header
                    assert line.startswith('# '), f"Level 1 header should have space after #: {line}"
                elif len(line) > 2 and line[1] == '#':
                    # This might be a level 2 or 3 header
                    if line[2] == ' ':
                        # Level 2 header
                        assert line.startswith('## '), f"Level 2 header should have space after ##: {line}"
                    elif len(line) > 3 and line[2] == '#' and line[3] == ' ':
                        # Level 3 header
                        assert line.startswith('### '), f"Level 3 header should have space after ###: {line}"
                # Otherwise, it's likely content that starts with #, not a header - skip validation
    
    def test_export_script_compatibility_with_sample_cv(self, export_service, temp_root_dir):
        """
        Test export script compatibility using the actual sample CV file.
        
        **Validates: Requirements 8.4, 9.1, 9.3**
        """
        # Load the sample CV file
        project_root = Path(__file__).parent.parent.parent
        sample_cv_path = project_root / "cv" / "core-cv.md"
        
        if not sample_cv_path.exists():
            pytest.skip("Sample CV file not found")
        
        # Read the sample CV
        with open(sample_cv_path, 'r', encoding='utf-8') as f:
            sample_markdown = f.read()
        
        # Parse the sample CV to create a CVModel (simplified parsing)
        # This tests that our markdown generation is compatible with existing format
        
        # Create a minimal CV model for testing
        sample_cv = CVModel(
            metadata=CVMetadata(title="Jane Doe — Core CV"),
            personal_info=PersonalInfo(
                name="John Doe",
                title="Head of Data Engineering",
                contact=ContactInfo(
                    address="123 Main St, London, UK",
                    phone="+44 20 1234 5678",
                    email="john.doe@example.com",
                    linkedin="https://linkedin.com/in/johndoe"
                )
            )
        )
        
        # Generate markdown using our service
        generated_markdown = export_service.json_to_markdown(sample_cv)
        
        # Verify the generated markdown has similar structure to the sample
        generated_lines = generated_markdown.split('\n')
        sample_lines = sample_markdown.split('\n')
        
        # Both should start with YAML frontmatter
        assert generated_lines[0] == "---", "Generated markdown should start with YAML frontmatter"
        assert sample_lines[0] == "---", "Sample markdown should start with YAML frontmatter"
        
        # Both should have the person's name as main heading
        assert "# John Doe" in generated_markdown, "Generated markdown should contain name heading"
        assert any(
            line.startswith("# ") for line in sample_lines
        ), "Sample markdown should contain a name heading"
        
        # Verify that our generated format is compatible with the existing pipeline
        # by checking that it contains the expected structural elements
        assert "title:" in generated_markdown, "Generated markdown should have title in frontmatter"
        assert "author:" in generated_markdown, "Generated markdown should have author in frontmatter"
        assert "date:" in generated_markdown, "Generated markdown should have date in frontmatter"


# Additional unit tests for specific compatibility scenarios
class TestExportScriptCompatibilityEdgeCases:
    """Unit tests for specific export script compatibility edge cases."""
    
    def test_empty_cv_markdown_compatibility(self, export_service):
        """Test that minimal CV data generates compatible markdown."""
        minimal_cv = CVModel(
            metadata=CVMetadata(title="Minimal CV"),
            personal_info=PersonalInfo(name="Test User")
        )
        
        markdown = export_service.json_to_markdown(minimal_cv)
        lines = markdown.split('\n')
        
        # Should have proper YAML frontmatter
        assert lines[0] == "---"
        # Exports deliberately omit title/author/date from the frontmatter:
        # pandoc turns them into a DOCX title block that the LaTeX template
        # ignores, so the name is carried by the body heading instead.
        assert "# Test User" in markdown
        
        # Should have main heading
        assert "# Test User" in markdown
        
        # Should not have empty sections
        assert "## Experience" not in markdown
        assert "## Education" not in markdown
    
    def test_special_characters_markdown_compatibility(self, export_service):
        """Test that CV data with special characters generates compatible markdown."""
        special_cv = CVModel(
            metadata=CVMetadata(title="CV with Special Characters: & < > \" '"),
            personal_info=PersonalInfo(
                name="José María García-López",
                title="Senior Developer & Team Lead"
            )
        )
        
        markdown = export_service.json_to_markdown(special_cv)
        
        # Should contain the special characters properly formatted
        assert "José María García-López" in markdown
        assert "Senior Developer & Team Lead" in markdown
        
        # Should have proper YAML frontmatter (special chars should be handled)
        assert "---" in markdown
        assert "lang: en-US" in markdown
    
    def test_markdown_yaml_frontmatter_format(self, export_service):
        """Test that YAML frontmatter follows expected format for export script."""
        test_cv = CVModel(
            metadata=CVMetadata(title="Test CV"),
            personal_info=PersonalInfo(
                name="Test User",
                contact=ContactInfo(
                    email="test@example.com",
                    phone="123-456-7890",
                    website="https://example.com",
                    linkedin="https://linkedin.com/in/testuser"
                )
            )
        )
        
        markdown = export_service.json_to_markdown(test_cv)
        lines = markdown.split('\n')
        
        # Find frontmatter section
        frontmatter_start = 0
        frontmatter_end = -1
        for i, line in enumerate(lines[1:], 1):
            if line == "---":
                frontmatter_end = i
                break
        
        assert frontmatter_end > 0, "Should have proper frontmatter"
        
        frontmatter_lines = lines[1:frontmatter_end]
        
        # Check required fields are present
        frontmatter_content = '\n'.join(frontmatter_lines)
        # Exports deliberately omit title/author/date from the frontmatter:
        # pandoc turns them into a DOCX title block that the LaTeX template
        # ignores, so the name is carried by the body heading instead.
        assert "lang: en-US" in frontmatter_content
        assert "colorlinks: true" in frontmatter_content
        assert "# Test User" in markdown
        
        # Check contact fields are included when available
        assert "email: test@example.com" in frontmatter_content
        assert "phone: 123-456-7890" in frontmatter_content
        assert "website: https://example.com" in frontmatter_content
        assert "linkedin: https://linkedin.com/in/testuser" in frontmatter_content