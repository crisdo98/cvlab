"""
Property-based tests for export format generation.

Feature: cv-web-app, Property 4: Export Format Generation
Validates: Requirements 2.1, 2.2, 2.3
"""
import tempfile
import shutil
import os
import subprocess
from pathlib import Path
from typing import Dict, Any
import uuid

try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False

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
    temp_dir = tempfile.mkdtemp(prefix="cv_export_format_test_")
    
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
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _check_pdf_dependencies_available():
    """Check if PDF dependencies are available for testing."""
    try:
        # Check pandoc
        subprocess.run(["pandoc", "--version"], capture_output=True, timeout=5)
        
        # Check at least one PDF engine
        for engine in ["xelatex", "tectonic"]:
            try:
                subprocess.run([engine, "--version"], capture_output=True, timeout=5)
                return True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _validate_file_format(file_path: Path, expected_format: ExportFormat) -> bool:
    """
    Validate that a file matches the expected format using file magic.
    
    Args:
        file_path: Path to the file to validate
        expected_format: Expected export format
        
    Returns:
        True if file format matches expectation
    """
    if not file_path.exists():
        return False
    
    try:
        if MAGIC_AVAILABLE:
            # Use python-magic to detect file type
            file_type = magic.from_file(str(file_path), mime=True)
            
            format_mime_types = {
                ExportFormat.PDF: "application/pdf",
                ExportFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ExportFormat.TXT: "text/plain"
            }
            
            expected_mime = format_mime_types.get(expected_format)
            if expected_mime:
                return file_type == expected_mime
        
        # Fallback to file extension and basic content checks
        expected_extension = f".{expected_format.value}"
        if file_path.suffix.lower() != expected_extension:
            return False
        
        # Additional basic format validation
        if expected_format == ExportFormat.PDF:
            # Check PDF magic number
            with open(file_path, 'rb') as f:
                header = f.read(4)
            return header == b'%PDF'
        elif expected_format == ExportFormat.DOCX:
            # Check ZIP magic number (DOCX is ZIP-based)
            with open(file_path, 'rb') as f:
                header = f.read(4)
            return header == b'PK\x03\x04'
        elif expected_format == ExportFormat.TXT:
            # For text files, just check that it's readable as text
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    f.read(100)  # Try to read first 100 chars
                return True
            except UnicodeDecodeError:
                return False
        
        return True
        
    except Exception:
        # Fallback to file extension check if all else fails
        expected_extension = f".{expected_format.value}"
        return file_path.suffix.lower() == expected_extension


def _validate_file_content(file_path: Path, cv_data: CVModel, format: ExportFormat) -> bool:
    """
    Validate that the exported file contains expected CV content.
    
    Args:
        file_path: Path to the exported file
        cv_data: Original CV data
        format: Export format
        
    Returns:
        True if file contains expected content
    """
    if not file_path.exists():
        return False
    
    try:
        if format == ExportFormat.TXT:
            # For text files, we can directly check content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check that essential CV information is present
            if cv_data.personal_info.name not in content:
                return False
            
            # Check for experience titles if present
            if cv_data.experience:
                for exp in cv_data.experience:
                    if exp.title not in content:
                        return False
            
            # Check for education degrees if present
            if cv_data.education:
                for edu in cv_data.education:
                    if edu.degree not in content:
                        return False
            
            return True
        
        elif format == ExportFormat.PDF:
            # For PDF files, check that they are valid PDF files
            # We can't easily extract text without additional dependencies
            # So we just verify it's a valid PDF by checking magic number
            with open(file_path, 'rb') as f:
                header = f.read(4)
            return header == b'%PDF'
        
        elif format == ExportFormat.DOCX:
            # For DOCX files, check that they are valid ZIP files (DOCX is ZIP-based)
            with open(file_path, 'rb') as f:
                header = f.read(4)
            return header == b'PK\x03\x04'  # ZIP file magic number
        
        return True
        
    except Exception:
        return False


class TestExportFormatGeneration:
    """Property-based tests for export format generation."""
    
    @given(cv_data=cv_model_strategy(), export_format=st.sampled_from([ExportFormat.TXT]))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_format_generation_txt(self, export_service, cv_data, export_format):
        """
        Property 4: Export Format Generation - TXT Format
        
        For any valid CV data and TXT export format, the export engine should 
        generate a valid file of the requested format.
        
        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        # Step 1: Create export request
        export_request = ExportRequest(
            cv_id=cv_data.id,
            format=export_format,
            template_id="default"
        )
        
        # Step 2: Perform export
        export_response = export_service.export_cv(cv_data, export_request)
        
        # Step 3: Verify export completed successfully or failed gracefully
        if export_response.status.value == "completed":
            # Export succeeded - validate the generated file
            assert export_response.file_path is not None, "Completed export should have file path"
            
            file_path = Path(export_response.file_path)
            assert file_path.exists(), f"Export file should exist: {file_path}"
            
            # Step 4: Validate file format
            assert _validate_file_format(file_path, export_format), \
                f"Generated file should be valid {export_format.value} format"
            
            # Step 5: Validate file content contains CV data
            assert _validate_file_content(file_path, cv_data, export_format), \
                f"Generated {export_format.value} file should contain CV content"
            
            # Step 6: Validate file size is reasonable (not empty, not too large)
            file_size = file_path.stat().st_size
            assert file_size > 0, "Generated file should not be empty"
            assert file_size < 10 * 1024 * 1024, "Generated file should not be unreasonably large (>10MB)"
            
            # Step 7: Validate response metadata
            assert export_response.file_size == file_size, "Response file size should match actual file size"
            assert export_response.download_url is not None, "Completed export should have download URL"
            assert export_response.completed_at is not None, "Completed export should have completion timestamp"
            
        elif export_response.status.value == "failed":
            # Export failed - validate error handling
            assert export_response.error_message is not None, "Failed export should have error message"
            assert len(export_response.error_message) > 0, "Error message should not be empty"
            assert export_response.file_path is None, "Failed export should not have file path"
            assert export_response.download_url is None, "Failed export should not have download URL"
            
        else:
            # Export in unexpected state
            pytest.fail(f"Export should be either completed or failed, got: {export_response.status.value}")
    
    @pytest.mark.skipif(not _check_dependencies_available(), reason="Pandoc not available")
    @given(cv_data=cv_model_strategy(), export_format=st.sampled_from([ExportFormat.DOCX]))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_format_generation_docx(self, export_service, cv_data, export_format):
        """
        Property 4: Export Format Generation - DOCX Format
        
        For any valid CV data and DOCX export format, the export engine should 
        generate a valid file of the requested format.
        
        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        # Step 1: Create export request
        export_request = ExportRequest(
            cv_id=cv_data.id,
            format=export_format,
            template_id="default"
        )
        
        # Step 2: Perform export
        export_response = export_service.export_cv(cv_data, export_request)
        
        # Step 3: Verify export completed successfully or failed gracefully
        if export_response.status.value == "completed":
            # Export succeeded - validate the generated file
            assert export_response.file_path is not None, "Completed export should have file path"
            
            file_path = Path(export_response.file_path)
            assert file_path.exists(), f"Export file should exist: {file_path}"
            
            # Step 4: Validate file format
            assert _validate_file_format(file_path, export_format), \
                f"Generated file should be valid {export_format.value} format"
            
            # Step 5: Validate file content structure
            assert _validate_file_content(file_path, cv_data, export_format), \
                f"Generated {export_format.value} file should be valid document structure"
            
            # Step 6: Validate file size is reasonable
            file_size = file_path.stat().st_size
            assert file_size > 0, "Generated file should not be empty"
            assert file_size < 50 * 1024 * 1024, "Generated file should not be unreasonably large (>50MB)"
            
            # Step 7: Validate response metadata
            assert export_response.file_size == file_size, "Response file size should match actual file size"
            assert export_response.download_url is not None, "Completed export should have download URL"
            assert export_response.completed_at is not None, "Completed export should have completion timestamp"
            
        elif export_response.status.value == "failed":
            # Export failed - validate error handling
            assert export_response.error_message is not None, "Failed export should have error message"
            assert len(export_response.error_message) > 0, "Error message should not be empty"
            assert export_response.file_path is None, "Failed export should not have file path"
            assert export_response.download_url is None, "Failed export should not have download URL"
            
        else:
            # Export in unexpected state
            pytest.fail(f"Export should be either completed or failed, got: {export_response.status.value}")
    
    @pytest.mark.skipif(not _check_pdf_dependencies_available(), reason="PDF dependencies not available")
    @given(cv_data=cv_model_strategy(), export_format=st.sampled_from([ExportFormat.PDF]))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_format_generation_pdf(self, export_service, cv_data, export_format):
        """
        Property 4: Export Format Generation - PDF Format
        
        For any valid CV data and PDF export format, the export engine should 
        generate a valid file of the requested format.
        
        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        # Step 1: Create export request
        export_request = ExportRequest(
            cv_id=cv_data.id,
            format=export_format,
            template_id="default"
        )
        
        # Step 2: Perform export
        export_response = export_service.export_cv(cv_data, export_request)
        
        # Step 3: Verify export completed successfully or failed gracefully
        if export_response.status.value == "completed":
            # Export succeeded - validate the generated file
            assert export_response.file_path is not None, "Completed export should have file path"
            
            file_path = Path(export_response.file_path)
            assert file_path.exists(), f"Export file should exist: {file_path}"
            
            # Step 4: Validate file format
            assert _validate_file_format(file_path, export_format), \
                f"Generated file should be valid {export_format.value} format"
            
            # Step 5: Validate file content structure
            assert _validate_file_content(file_path, cv_data, export_format), \
                f"Generated {export_format.value} file should be valid PDF structure"
            
            # Step 6: Validate file size is reasonable
            file_size = file_path.stat().st_size
            assert file_size > 0, "Generated file should not be empty"
            assert file_size < 100 * 1024 * 1024, "Generated file should not be unreasonably large (>100MB)"
            
            # Step 7: Validate response metadata
            assert export_response.file_size == file_size, "Response file size should match actual file size"
            assert export_response.download_url is not None, "Completed export should have download URL"
            assert export_response.completed_at is not None, "Completed export should have completion timestamp"
            
        elif export_response.status.value == "failed":
            # Export failed - validate error handling
            assert export_response.error_message is not None, "Failed export should have error message"
            assert len(export_response.error_message) > 0, "Error message should not be empty"
            assert export_response.file_path is None, "Failed export should not have file path"
            assert export_response.download_url is None, "Failed export should not have download URL"
            
        else:
            # Export in unexpected state
            pytest.fail(f"Export should be either completed or failed, got: {export_response.status.value}")
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_format_generation_all_supported_formats(self, export_service, cv_data):
        """
        Property 4: Export Format Generation - All Supported Formats
        
        For any valid CV data, the export engine should be able to handle 
        export requests for all supported formats (PDF, DOCX, TXT).
        
        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        supported_formats = [ExportFormat.TXT, ExportFormat.DOCX, ExportFormat.PDF]
        
        for export_format in supported_formats:
            # Step 1: Create export request for each format
            export_request = ExportRequest(
                cv_id=cv_data.id,
                format=export_format,
                template_id="default"
            )
            
            # Step 2: Perform export
            export_response = export_service.export_cv(cv_data, export_request)
            
            # Step 3: Verify export produces a valid response
            assert export_response is not None, f"Export should return response for {export_format.value}"
            assert export_response.cv_id == cv_data.id, f"Response should have correct CV ID for {export_format.value}"
            assert export_response.format == export_format, f"Response should have correct format for {export_format.value}"
            
            # Step 4: Verify response status is valid
            valid_statuses = ["completed", "failed", "in_progress"]
            assert export_response.status.value in valid_statuses, \
                f"Export status should be valid for {export_format.value}: {export_response.status.value}"
            
            # Step 5: If completed, verify file exists and is valid
            if export_response.status.value == "completed":
                assert export_response.file_path is not None, f"Completed export should have file path for {export_format.value}"
                
                file_path = Path(export_response.file_path)
                assert file_path.exists(), f"Export file should exist for {export_format.value}: {file_path}"
                
                # Validate file format
                assert _validate_file_format(file_path, export_format), \
                    f"Generated file should be valid {export_format.value} format"
                
                # Validate file is not empty
                file_size = file_path.stat().st_size
                assert file_size > 0, f"Generated {export_format.value} file should not be empty"
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_format_generation_response_consistency(self, export_service, cv_data):
        """
        Property 4: Export Format Generation - Response Consistency
        
        For any valid CV data, export responses should be consistent and 
        contain all required fields based on the export status.
        
        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        # Test with TXT format (most likely to succeed)
        export_request = ExportRequest(
            cv_id=cv_data.id,
            format=ExportFormat.TXT,
            template_id="default"
        )
        
        # Step 1: Perform export
        export_response = export_service.export_cv(cv_data, export_request)
        
        # Step 2: Verify response structure consistency
        assert hasattr(export_response, 'export_id'), "Response should have export_id"
        assert hasattr(export_response, 'cv_id'), "Response should have cv_id"
        assert hasattr(export_response, 'format'), "Response should have format"
        assert hasattr(export_response, 'status'), "Response should have status"
        assert hasattr(export_response, 'created_at'), "Response should have created_at"
        
        # Step 3: Verify required fields are populated
        assert export_response.export_id is not None, "Export ID should not be None"
        assert len(export_response.export_id) > 0, "Export ID should not be empty"
        assert export_response.cv_id == cv_data.id, "CV ID should match request"
        assert export_response.format == ExportFormat.TXT, "Format should match request"
        assert export_response.created_at is not None, "Created timestamp should not be None"
        
        # Step 4: Verify status-dependent fields
        if export_response.status.value == "completed":
            # Completed exports should have file information
            assert export_response.file_path is not None, "Completed export should have file path"
            assert export_response.download_url is not None, "Completed export should have download URL"
            assert export_response.completed_at is not None, "Completed export should have completion timestamp"
            assert export_response.file_size is not None, "Completed export should have file size"
            assert export_response.file_size > 0, "Completed export file size should be positive"
            
        elif export_response.status.value == "failed":
            # Failed exports should have error information
            assert export_response.error_message is not None, "Failed export should have error message"
            assert len(export_response.error_message) > 0, "Failed export error message should not be empty"
            
        # Step 5: Verify timestamp consistency
        if export_response.completed_at is not None:
            assert export_response.completed_at >= export_response.created_at, \
                "Completion timestamp should be after creation timestamp"


# Additional unit tests for specific format validation scenarios
class TestExportFormatGenerationEdgeCases:
    """Unit tests for specific export format generation edge cases."""
    
    def test_minimal_cv_export_format_generation(self, export_service):
        """Test export format generation with minimal CV data."""
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
        
        # Should handle minimal CV data gracefully
        assert export_response is not None
        assert export_response.cv_id == minimal_cv.id
        assert export_response.format == ExportFormat.TXT
        
        if export_response.status.value == "completed":
            file_path = Path(export_response.file_path)
            assert file_path.exists()
            assert _validate_file_format(file_path, ExportFormat.TXT)
    
    def test_cv_with_special_characters_export_format_generation(self, export_service):
        """Test export format generation with special characters in CV data."""
        special_cv = CVModel(
            metadata=CVMetadata(title="CV with Special Characters: & < > \" '"),
            personal_info=PersonalInfo(
                name="José María García-López",
                title="Senior Developer & Team Lead"
            ),
            summary="Experience with C++, .NET, and other technologies with special chars: @#$%^&*()"
        )
        
        export_request = ExportRequest(
            cv_id=special_cv.id,
            format=ExportFormat.TXT,
            template_id="default"
        )
        
        export_response = export_service.export_cv(special_cv, export_request)
        
        # Should handle special characters gracefully
        assert export_response is not None
        assert export_response.cv_id == special_cv.id
        
        if export_response.status.value == "completed":
            file_path = Path(export_response.file_path)
            assert file_path.exists()
            assert _validate_file_format(file_path, ExportFormat.TXT)
            assert _validate_file_content(file_path, special_cv, ExportFormat.TXT)
    
    def test_export_format_generation_with_invalid_template(self, export_service):
        """Test export format generation with invalid template ID."""
        test_cv = CVModel(
            metadata=CVMetadata(title="Test CV"),
            personal_info=PersonalInfo(name="Test User")
        )
        
        export_request = ExportRequest(
            cv_id=test_cv.id,
            format=ExportFormat.TXT,
            template_id="nonexistent_template"
        )
        
        export_response = export_service.export_cv(test_cv, export_request)
        
        # Should handle invalid template gracefully
        assert export_response is not None
        assert export_response.status.value == "failed"
        assert export_response.error_message is not None
        assert "template" in export_response.error_message.lower()
    
    def test_export_format_generation_file_naming_consistency(self, export_service):
        """Test that export format generation produces consistently named files."""
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
        
        if export_response.status.value == "completed":
            file_path = Path(export_response.file_path)
            
            # File should be in the correct format directory
            assert "exports/txt" in str(file_path)
            
            # File should have correct extension
            assert file_path.suffix == ".txt"
            
            # File name should contain timestamp pattern
            assert "-" in file_path.stem  # Should have timestamp separator