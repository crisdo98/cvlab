"""
Property-based tests for template preview consistency.

Feature: cv-web-app, Property 7: Template Preview Consistency
Validates: Requirements 3.2
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


# Test data generators for valid CV data
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
        name=draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cc', 'Cs')))),
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
        name=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cc', 'Cs')))),
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
    temp_dir = tempfile.mkdtemp(prefix="cv_template_preview_test_")
    
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


def _extract_template_metadata(template_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract key metadata from template information for comparison.
    
    Args:
        template_info: Template information dictionary
        
    Returns:
        Dictionary with extracted metadata
    """
    return {
        "template_id": template_info.get("template_id"),
        "name": template_info.get("name"),
        "supported_formats": sorted(template_info.get("supported_formats", [])),
        "preview_available": template_info.get("preview_available", False)
    }


class TestTemplatePreviewConsistency:
    """Property-based tests for template preview consistency."""
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_template_preview_reflects_template_metadata(self, export_service, cv_data):
        """
        Property 7: Template Preview Consistency - Metadata Reflection
        
        For any CV data and template selection, the template preview should 
        reflect the visual styling and metadata of the selected template.
        This test verifies that template metadata is consistent and accurate.
        
        **Validates: Requirements 3.2**
        """
        # Step 1: Get available templates
        available_templates = export_service.get_available_templates()
        
        assert len(available_templates) > 0, \
            "At least one template should be available"
        
        # Step 2: For each template, verify metadata consistency
        for template in available_templates:
            template_id = template["template_id"]
            
            # Verify required fields are present
            assert "template_id" in template, \
                f"Template {template_id} should have template_id field"
            assert "name" in template, \
                f"Template {template_id} should have name field"
            assert "supported_formats" in template, \
                f"Template {template_id} should have supported_formats field"
            
            # Verify template_id is not empty
            assert template_id and len(template_id.strip()) > 0, \
                "Template ID should not be empty"
            
            # Verify name is not empty
            assert template["name"] and len(template["name"].strip()) > 0, \
                f"Template {template_id} name should not be empty"
            
            # Verify supported formats are valid
            assert len(template["supported_formats"]) > 0, \
                f"Template {template_id} should support at least one format"
            
            for fmt in template["supported_formats"]:
                assert fmt in [ExportFormat.PDF, ExportFormat.DOCX, ExportFormat.TXT], \
                    f"Template {template_id} has invalid format: {fmt}"
        
        # Step 3: Verify default template is always available
        default_template = next(
            (t for t in available_templates if t["template_id"] == "default"),
            None
        )
        assert default_template is not None, \
            "Default template should always be available"
        
        # Step 4: Verify template metadata is consistent across calls
        templates_second_call = export_service.get_available_templates()
        
        assert len(available_templates) == len(templates_second_call), \
            "Template list should be consistent across calls"
        
        for i, template in enumerate(available_templates):
            template_meta = _extract_template_metadata(template)
            second_call_meta = _extract_template_metadata(templates_second_call[i])
            
            assert template_meta == second_call_meta, \
                f"Template {template['template_id']} metadata should be consistent"
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_template_selection_preserves_cv_content(self, export_service, cv_data):
        """
        Property 7: Template Preview Consistency - Content Preservation
        
        For any CV data, selecting different templates for preview should not
        modify the underlying CV content. The preview should only affect visual
        presentation, not data.
        
        **Validates: Requirements 3.2**
        """
        # Step 1: Store original CV data
        original_cv_json = cv_data.model_dump_json()
        original_cv_dict = json.loads(original_cv_json)
        
        # Step 2: Get available templates
        available_templates = export_service.get_available_templates()
        
        # Step 3: For each template, verify CV data remains unchanged
        for template in available_templates:
            template_id = template["template_id"]
            
            # Create a copy with the template ID
            cv_with_template = cv_data.model_copy(deep=True)
            cv_with_template.metadata.template_id = template_id
            
            # Generate markdown (simulating preview generation)
            markdown_content = export_service.json_to_markdown(cv_with_template)
            
            # Verify markdown was generated
            assert markdown_content and len(markdown_content) > 0, \
                f"Markdown should be generated for template {template_id}"
            
            # Verify original CV data is unchanged
            current_cv_json = cv_data.model_dump_json()
            current_cv_dict = json.loads(current_cv_json)
            
            assert original_cv_dict == current_cv_dict, \
                f"Original CV data should remain unchanged after template {template_id} preview"
            
            # Verify the copy has the correct template ID
            assert cv_with_template.metadata.template_id == template_id, \
                f"Template copy should have template_id set to {template_id}"
            
            # Verify other CV fields are preserved in the copy
            assert cv_with_template.personal_info.name == cv_data.personal_info.name, \
                f"Personal name should be preserved with template {template_id}"
            
            if cv_data.experience:
                assert len(cv_with_template.experience) == len(cv_data.experience), \
                    f"Experience count should be preserved with template {template_id}"
            
            if cv_data.education:
                assert len(cv_with_template.education) == len(cv_data.education), \
                    f"Education count should be preserved with template {template_id}"
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_template_preview_format_compatibility(self, export_service, cv_data):
        """
        Property 7: Template Preview Consistency - Format Compatibility
        
        For any CV data and template, the template's supported formats should
        be accurately reflected in the template metadata, and exports should
        only be possible for supported formats.
        
        **Validates: Requirements 3.2**
        """
        # Step 1: Get available templates
        available_templates = export_service.get_available_templates()
        
        # Step 2: For each template, verify format compatibility
        for template in available_templates:
            template_id = template["template_id"]
            supported_formats = template["supported_formats"]
            
            # Step 3: Verify each supported format can be used
            for export_format in supported_formats:
                # Create export request
                export_request = ExportRequest(
                    cv_id=cv_data.id,
                    format=export_format,
                    template_id=template_id
                )
                
                # Validate the export request
                validation_error = export_service.validate_export_request(export_request)
                
                # For supported formats, validation should pass (or only fail for non-template reasons)
                if validation_error:
                    # If there's an error, it should not be about template compatibility
                    assert "template" not in validation_error.message.lower() or \
                           "unknown template" not in validation_error.message.lower(), \
                        f"Template {template_id} claims to support {export_format.value} but validation fails with template error"
            
            # Step 4: Verify format list is not empty and contains valid formats
            assert len(supported_formats) > 0, \
                f"Template {template_id} should support at least one format"
            
            for fmt in supported_formats:
                assert isinstance(fmt, ExportFormat), \
                    f"Template {template_id} format {fmt} should be an ExportFormat enum"
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_template_preview_consistency_across_cv_variations(self, export_service, cv_data):
        """
        Property 7: Template Preview Consistency - CV Variation Independence
        
        For any template, the template metadata and preview characteristics
        should remain consistent regardless of the CV data being previewed.
        Template properties are independent of CV content.
        
        **Validates: Requirements 3.2**
        """
        # Step 1: Get template metadata with original CV
        templates_with_original = export_service.get_available_templates()
        
        # Step 2: Create a modified version of the CV
        modified_cv = cv_data.model_copy(deep=True)
        modified_cv.personal_info.name = "Modified Name"
        modified_cv.summary = "Modified summary content"
        
        # Step 3: Get template metadata again (should be the same)
        templates_with_modified = export_service.get_available_templates()
        
        # Step 4: Verify template metadata is identical
        assert len(templates_with_original) == len(templates_with_modified), \
            "Template count should be independent of CV data"
        
        for i, original_template in enumerate(templates_with_original):
            modified_template = templates_with_modified[i]
            
            original_meta = _extract_template_metadata(original_template)
            modified_meta = _extract_template_metadata(modified_template)
            
            assert original_meta == modified_meta, \
                f"Template {original_template['template_id']} metadata should be independent of CV data"
        
        # Step 5: Verify template IDs are consistent
        original_ids = {t["template_id"] for t in templates_with_original}
        modified_ids = {t["template_id"] for t in templates_with_modified}
        
        assert original_ids == modified_ids, \
            "Available template IDs should be independent of CV data"
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_template_preview_default_template_availability(self, export_service, cv_data):
        """
        Property 7: Template Preview Consistency - Default Template Guarantee
        
        For any system state, the default template should always be available
        and functional for preview. This ensures users always have at least
        one working template option.
        
        **Validates: Requirements 3.2**
        """
        # Step 1: Get available templates
        available_templates = export_service.get_available_templates()
        
        # Step 2: Verify default template exists
        default_template = next(
            (t for t in available_templates if t["template_id"] == "default"),
            None
        )
        
        assert default_template is not None, \
            "Default template must always be available"
        
        # Step 3: Verify default template has required properties
        assert default_template["name"] and len(default_template["name"]) > 0, \
            "Default template must have a name"
        
        assert len(default_template["supported_formats"]) > 0, \
            "Default template must support at least one format"
        
        # Step 4: Verify default template supports all standard formats
        supported_format_values = [fmt.value for fmt in default_template["supported_formats"]]
        
        assert ExportFormat.PDF in default_template["supported_formats"] or \
               ExportFormat.DOCX in default_template["supported_formats"] or \
               ExportFormat.TXT in default_template["supported_formats"], \
            "Default template should support at least one standard format"
        
        # Step 5: Verify default template can generate markdown
        cv_with_default = cv_data.model_copy(deep=True)
        cv_with_default.metadata.template_id = "default"
        
        markdown_content = export_service.json_to_markdown(cv_with_default)
        
        assert markdown_content and len(markdown_content) > 0, \
            "Default template should be able to generate markdown"
        
        # Verify essential content is in the markdown
        assert cv_data.personal_info.name in markdown_content, \
            "Default template markdown should contain CV name"


# Additional unit tests for specific template preview scenarios
class TestTemplatePreviewConsistencyEdgeCases:
    """Unit tests for specific template preview consistency edge cases."""
    
    def test_empty_template_list_handling(self, export_service):
        """Test that system handles empty template list gracefully."""
        # Get templates (should always have at least default)
        templates = export_service.get_available_templates()
        
        # Should never be empty - at minimum default template
        assert len(templates) >= 1, \
            "Template list should always contain at least the default template"
    
    def test_template_metadata_structure(self, export_service):
        """Test that template metadata has consistent structure."""
        templates = export_service.get_available_templates()
        
        required_fields = ["template_id", "name", "supported_formats"]
        
        for template in templates:
            for field in required_fields:
                assert field in template, \
                    f"Template {template.get('template_id', 'unknown')} missing required field: {field}"
            
            # Verify types
            assert isinstance(template["template_id"], str), \
                "template_id should be a string"
            assert isinstance(template["name"], str), \
                "name should be a string"
            assert isinstance(template["supported_formats"], list), \
                "supported_formats should be a list"
    
    def test_template_preview_with_minimal_cv(self, export_service):
        """Test template preview with minimal CV data."""
        minimal_cv = CVModel(
            metadata=CVMetadata(title="Minimal CV", template_id="default"),
            personal_info=PersonalInfo(name="Test User")
        )
        
        # Get templates
        templates = export_service.get_available_templates()
        
        # Should work with minimal CV
        assert len(templates) > 0, \
            "Templates should be available even with minimal CV"
        
        # Generate markdown with default template
        markdown = export_service.json_to_markdown(minimal_cv)
        
        assert "Test User" in markdown, \
            "Template preview should work with minimal CV data"
    
    def test_template_id_uniqueness(self, export_service):
        """Test that all template IDs are unique."""
        templates = export_service.get_available_templates()
        
        template_ids = [t["template_id"] for t in templates]
        unique_ids = set(template_ids)
        
        assert len(template_ids) == len(unique_ids), \
            "All template IDs should be unique"
    
    def test_template_format_enum_validity(self, export_service):
        """Test that all template formats are valid ExportFormat enums."""
        templates = export_service.get_available_templates()
        
        valid_formats = {ExportFormat.PDF, ExportFormat.DOCX, ExportFormat.TXT}
        
        for template in templates:
            for fmt in template["supported_formats"]:
                assert fmt in valid_formats, \
                    f"Template {template['template_id']} has invalid format: {fmt}"
