"""
Property-based tests for export completion workflow.

Feature: cv-web-app, Property 6: Export Completion Workflow
Validates: Requirements 2.5
"""
import tempfile
import shutil
import os
from pathlib import Path
from typing import Dict, Any
import uuid

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime

from app.models.cv_models import (
    CVModel, PersonalInfo, CVMetadata, ContactInfo,
    Experience, Education, SkillCategory, Skills, Certification
)
from app.models.export_models import ExportFormat, ExportRequest, ExportStatus
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
    temp_dir = tempfile.mkdtemp(prefix="cv_export_completion_test_")
    
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


def _validate_download_url_format(download_url: str, export_id: str) -> bool:
    """
    Validate that download URL has the expected format.
    
    Args:
        download_url: The download URL to validate
        export_id: The export ID that should be in the URL
        
    Returns:
        True if URL format is valid
    """
    if not download_url:
        return False
    
    # Expected format: /api/export/download/{export_id}
    expected_pattern = f"/api/export/download/{export_id}"
    return download_url == expected_pattern


def _validate_file_exists_at_path(file_path: str) -> bool:
    """
    Validate that the exported file exists at the specified path.
    
    Args:
        file_path: Path to the exported file
        
    Returns:
        True if file exists and is readable
    """
    if not file_path:
        return False
    
    path = Path(file_path)
    return path.exists() and path.is_file() and os.access(path, os.R_OK)


def _validate_file_in_expected_location(file_path: str, format: ExportFormat, root_dir: str) -> bool:
    """
    Validate that the exported file is in the expected directory structure.
    
    Args:
        file_path: Path to the exported file
        format: Export format
        root_dir: Root directory of the export service
        
    Returns:
        True if file is in the expected location
    """
    if not file_path:
        return False
    
    path = Path(file_path)
    expected_dir = Path(root_dir) / "exports" / format.value
    
    # Check if file is in the correct format directory
    try:
        path.relative_to(expected_dir)
        return True
    except ValueError:
        return False


def _validate_file_size_reasonable(file_path: str) -> bool:
    """
    Validate that the exported file has a reasonable size (not empty, not too large).
    
    Args:
        file_path: Path to the exported file
        
    Returns:
        True if file size is reasonable
    """
    if not file_path:
        return False
    
    path = Path(file_path)
    if not path.exists():
        return False
    
    file_size = path.stat().st_size
    
    # File should not be empty and should not be unreasonably large (>100MB)
    return 0 < file_size < 100 * 1024 * 1024


def _validate_completion_timestamp(export_response) -> bool:
    """
    Validate that completion timestamp is set and reasonable.
    
    Args:
        export_response: The export response to validate
        
    Returns:
        True if completion timestamp is valid
    """
    if not export_response.completed_at:
        return False
    
    # Completion time should be after creation time
    if export_response.created_at and export_response.completed_at < export_response.created_at:
        return False
    
    # Completion time should not be in the future (with small tolerance for clock skew)
    now = datetime.now()
    if export_response.completed_at > now:
        return False
    
    return True


class TestExportCompletionWorkflow:
    """Property-based tests for export completion workflow."""
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_completion_workflow_txt_format(self, export_service, cv_data):
        """
        Property 6: Export Completion Workflow - TXT Format
        
        For any successful export operation, a download link should be available 
        and the exported file should exist in the expected location.
        
        **Validates: Requirements 2.5**
        """
        # Step 1: Create export request for TXT format (most likely to succeed)
        export_request = ExportRequest(
            cv_id=cv_data.id,
            format=ExportFormat.TXT,
            template_id="default"
        )
        
        # Step 2: Perform export
        export_response = export_service.export_cv(cv_data, export_request)
        
        # Step 3: Validate export response structure
        assert export_response is not None, "Export should return a response"
        assert export_response.export_id is not None, "Export response should have an export ID"
        assert export_response.cv_id == cv_data.id, "Export response should have correct CV ID"
        assert export_response.format == ExportFormat.TXT, "Export response should have correct format"
        assert export_response.created_at is not None, "Export response should have creation timestamp"
        
        # Step 4: If export completed successfully, validate completion workflow
        if export_response.status == ExportStatus.COMPLETED:
            # Validate download URL is available and properly formatted
            assert export_response.download_url is not None, \
                "Completed export should have a download URL"
            assert _validate_download_url_format(export_response.download_url, export_response.export_id), \
                f"Download URL should have correct format: {export_response.download_url}"
            
            # Validate exported file exists at the specified path
            assert export_response.file_path is not None, \
                "Completed export should have a file path"
            assert _validate_file_exists_at_path(export_response.file_path), \
                f"Exported file should exist at specified path: {export_response.file_path}"
            
            # Validate file is in the expected location (exports/txt directory)
            assert _validate_file_in_expected_location(
                export_response.file_path, 
                ExportFormat.TXT, 
                export_service.root_dir
            ), f"Exported file should be in expected location: {export_response.file_path}"
            
            # Validate file size is reasonable
            assert _validate_file_size_reasonable(export_response.file_path), \
                f"Exported file should have reasonable size: {export_response.file_path}"
            
            # Validate completion timestamp is set and reasonable
            assert _validate_completion_timestamp(export_response), \
                "Completed export should have valid completion timestamp"
            
            # Validate file size in response matches actual file size
            if export_response.file_size is not None:
                actual_size = Path(export_response.file_path).stat().st_size
                assert export_response.file_size == actual_size, \
                    f"Response file size ({export_response.file_size}) should match actual file size ({actual_size})"
            
            # Validate no error message is present for successful export
            assert export_response.error_message is None, \
                "Completed export should not have error message"
        
        elif export_response.status == ExportStatus.FAILED:
            # For failed exports, validate that completion workflow fields are not set
            assert export_response.download_url is None, \
                "Failed export should not have download URL"
            assert export_response.file_path is None, \
                "Failed export should not have file path"
            assert export_response.completed_at is None, \
                "Failed export should not have completion timestamp"
            assert export_response.file_size is None, \
                "Failed export should not have file size"
            
            # Failed exports should have error message
            assert export_response.error_message is not None, \
                "Failed export should have error message"
            assert len(export_response.error_message.strip()) > 0, \
                "Failed export error message should not be empty"
        
        else:
            # For in-progress exports, validate intermediate state
            assert export_response.status == ExportStatus.IN_PROGRESS, \
                f"Export status should be valid: {export_response.status}"
            
            # In-progress exports should not have completion fields set
            assert export_response.download_url is None, \
                "In-progress export should not have download URL"
            assert export_response.completed_at is None, \
                "In-progress export should not have completion timestamp"
    
    @given(cv_data=cv_model_strategy(), export_format=st.sampled_from([ExportFormat.TXT, ExportFormat.DOCX]))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_completion_workflow_multiple_formats(self, export_service, cv_data, export_format):
        """
        Property 6: Export Completion Workflow - Multiple Formats
        
        For any successful export operation in any supported format, 
        the completion workflow should be consistent.
        
        **Validates: Requirements 2.5**
        """
        # Step 1: Create export request
        export_request = ExportRequest(
            cv_id=cv_data.id,
            format=export_format,
            template_id="default"
        )
        
        # Step 2: Perform export
        export_response = export_service.export_cv(cv_data, export_request)
        
        # Step 3: Validate basic response structure
        assert export_response is not None, f"Export should return response for {export_format.value}"
        assert export_response.format == export_format, f"Response format should match request for {export_format.value}"
        
        # Step 4: If export completed, validate completion workflow consistency
        if export_response.status == ExportStatus.COMPLETED:
            # All completed exports should have these fields regardless of format
            completion_fields = [
                ("download_url", export_response.download_url),
                ("file_path", export_response.file_path),
                ("completed_at", export_response.completed_at)
            ]
            
            for field_name, field_value in completion_fields:
                assert field_value is not None, \
                    f"Completed {export_format.value} export should have {field_name}"
            
            # Validate download URL format consistency
            assert _validate_download_url_format(export_response.download_url, export_response.export_id), \
                f"Download URL format should be consistent for {export_format.value}"
            
            # Validate file location consistency
            assert _validate_file_in_expected_location(
                export_response.file_path, 
                export_format, 
                export_service.root_dir
            ), f"File location should be consistent for {export_format.value}"
            
            # Validate file exists and is accessible
            assert _validate_file_exists_at_path(export_response.file_path), \
                f"Exported {export_format.value} file should exist and be accessible"
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_completion_workflow_response_consistency(self, export_service, cv_data):
        """
        Property 6: Export Completion Workflow - Response Consistency
        
        For any export operation, the response should be internally consistent
        and follow the completion workflow contract.
        
        **Validates: Requirements 2.5**
        """
        # Step 1: Create export request
        export_request = ExportRequest(
            cv_id=cv_data.id,
            format=ExportFormat.TXT,  # Use TXT for reliability
            template_id="default"
        )
        
        # Step 2: Perform export
        export_response = export_service.export_cv(cv_data, export_request)
        
        # Step 3: Validate response consistency based on status
        if export_response.status == ExportStatus.COMPLETED:
            # Completed exports must have all completion fields
            required_completion_fields = [
                "download_url", "file_path", "completed_at"
            ]
            
            for field in required_completion_fields:
                field_value = getattr(export_response, field)
                assert field_value is not None, \
                    f"Completed export must have {field} field set"
            
            # Completed exports must not have error information
            assert export_response.error_message is None, \
                "Completed export should not have error message"
            
            # Validate timestamp consistency
            assert export_response.completed_at >= export_response.created_at, \
                "Completion timestamp should be after creation timestamp"
            
            # Validate file information consistency
            if export_response.file_size is not None:
                assert export_response.file_size > 0, \
                    "Completed export file size should be positive"
        
        elif export_response.status == ExportStatus.FAILED:
            # Failed exports must have error information
            assert export_response.error_message is not None, \
                "Failed export must have error message"
            assert len(export_response.error_message.strip()) > 0, \
                "Failed export error message must not be empty"
            
            # Failed exports must not have completion fields
            completion_fields = [
                "download_url", "file_path", "completed_at", "file_size"
            ]
            
            for field in completion_fields:
                field_value = getattr(export_response, field)
                assert field_value is None, \
                    f"Failed export should not have {field} field set"
        
        elif export_response.status == ExportStatus.IN_PROGRESS:
            # In-progress exports should not have completion or error fields
            intermediate_fields = [
                "download_url", "file_path", "completed_at", "file_size", "error_message"
            ]
            
            for field in intermediate_fields:
                field_value = getattr(export_response, field)
                assert field_value is None, \
                    f"In-progress export should not have {field} field set"
        
        # Step 4: Validate common fields are always present
        common_fields = [
            ("export_id", export_response.export_id),
            ("cv_id", export_response.cv_id),
            ("format", export_response.format),
            ("status", export_response.status),
            ("created_at", export_response.created_at)
        ]
        
        for field_name, field_value in common_fields:
            assert field_value is not None, \
                f"Export response should always have {field_name} field"
        
        # Validate field types and formats
        assert isinstance(export_response.export_id, str), "Export ID should be string"
        assert len(export_response.export_id) > 0, "Export ID should not be empty"
        assert export_response.cv_id == cv_data.id, "CV ID should match request"
        assert export_response.format == ExportFormat.TXT, "Format should match request"


# Additional unit tests for specific completion workflow scenarios
class TestExportCompletionWorkflowEdgeCases:
    """Unit tests for specific export completion workflow edge cases."""
    
    def test_minimal_cv_export_completion_workflow(self, export_service):
        """Test export completion workflow with minimal CV data."""
        minimal_cv = CVModel(
            metadata=CVMetadata(title="Minimal CV"),
            personal_info=PersonalInfo(name="Test User")
        )
        
        export_request = ExportRequest(
            cv_id=minimal_cv.id,
            format=ExportFormat.TXT,
            template_id="default"
        )
        
        export_response = export_service.export_cv(minimal_cv, export_request)
        
        # Should handle minimal CV data and still follow completion workflow
        assert export_response is not None
        assert export_response.cv_id == minimal_cv.id
        
        if export_response.status == ExportStatus.COMPLETED:
            # Even minimal CV should have proper completion workflow
            assert export_response.download_url is not None
            assert export_response.file_path is not None
            assert export_response.completed_at is not None
            assert _validate_file_exists_at_path(export_response.file_path)
    
    def test_export_completion_workflow_with_special_characters(self, export_service):
        """Test export completion workflow with special characters in CV data."""
        special_cv = CVModel(
            metadata=CVMetadata(title="CV with Special Characters: & < > \" '"),
            personal_info=PersonalInfo(
                name="José María García-López",
                title="Senior Developer & Team Lead"
            )
        )
        
        export_request = ExportRequest(
            cv_id=special_cv.id,
            format=ExportFormat.TXT,
            template_id="default"
        )
        
        export_response = export_service.export_cv(special_cv, export_request)
        
        # Should handle special characters and still follow completion workflow
        assert export_response is not None
        
        if export_response.status == ExportStatus.COMPLETED:
            # Completion workflow should work even with special characters
            assert export_response.download_url is not None
            assert export_response.file_path is not None
            assert _validate_file_exists_at_path(export_response.file_path)
            assert _validate_file_in_expected_location(
                export_response.file_path, 
                ExportFormat.TXT, 
                export_service.root_dir
            )
    
    def test_export_completion_workflow_file_naming_consistency(self, export_service):
        """Test that export completion workflow produces consistently named files."""
        test_cv = CVModel(
            metadata=CVMetadata(title="Test CV for File Naming"),
            personal_info=PersonalInfo(name="Test User")
        )
        
        export_request = ExportRequest(
            cv_id=test_cv.id,
            format=ExportFormat.TXT,
            template_id="default"
        )
        
        export_response = export_service.export_cv(test_cv, export_request)
        
        if export_response.status == ExportStatus.COMPLETED:
            file_path = Path(export_response.file_path)
            
            # File should be in the correct format directory
            assert "exports/txt" in str(file_path)
            
            # File should have correct extension
            assert file_path.suffix == ".txt"
            
            # File name should contain timestamp pattern (YYYYMMDD-HHMMSS)
            assert "-" in file_path.stem  # Should have timestamp separator
            
            # Download URL should reference the export ID
            assert export_response.export_id in export_response.download_url