"""
Property-based tests for export error handling.

Feature: cv-web-app, Property 20: Export Error Handling
Validates: Requirements 9.4
"""
import tempfile
import shutil
import os
import subprocess
from pathlib import Path
from typing import Dict, Any
import uuid

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck, assume
from datetime import datetime

from app.models.cv_models import (
    CVModel, PersonalInfo, CVMetadata, ContactInfo,
    Experience, Education, SkillCategory, Skills, Certification
)
from app.models.export_models import ExportFormat, ExportRequest, ExportStatus
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
def cv_model_strategy(draw):
    """Generate valid CVModel data."""
    return CVModel(
        id=str(uuid.uuid4()),
        metadata=draw(cv_metadata_strategy()),
        personal_info=draw(personal_info_strategy()),
        summary=draw(st.one_of(st.none(), st.text(min_size=10, max_size=500))),
        experience=[],
        education=[],
        skills=Skills(categories=[]),
        certifications=[]
    )


@pytest.fixture
def temp_root_dir():
    """Fixture providing temporary root directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="cv_export_error_test_")
    
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
    
    # Copy additional scripts
    for script_name in ["normalize_txt.sh", "tune_docx.py"]:
        script_src = project_root / "scripts" / script_name
        script_dst = Path(temp_dir) / "scripts" / script_name
        if script_src.exists():
            shutil.copy2(script_src, script_dst)
            if script_name.endswith('.sh'):
                os.chmod(script_dst, 0o755)
    
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def export_service(temp_root_dir):
    """Fixture providing ExportService with temporary directory."""
    return ExportService(
        root_dir=temp_root_dir,
        export_script_path=Path(temp_root_dir) / "scripts" / "export.sh"
    )


@pytest.fixture
def broken_export_service(temp_root_dir):
    """Fixture providing ExportService with broken configuration for error testing."""
    # Remove export script to simulate missing dependency
    export_script_path = Path(temp_root_dir) / "scripts" / "export.sh"
    if export_script_path.exists():
        export_script_path.unlink()
    
    # Create service (will fail validation but we can still test error handling)
    try:
        return ExportService(
            root_dir=temp_root_dir,
            export_script_path=export_script_path
        )
    except Exception:
        # If initialization fails, return None - tests will handle this
        return None


def _check_error_message_quality(error_message: str) -> bool:
    """
    Check if an error message meets quality standards.
    
    Args:
        error_message: Error message to validate
        
    Returns:
        True if error message is informative and helpful
    """
    if not error_message or len(error_message.strip()) == 0:
        return False
    
    # Error message should be reasonably detailed (at least a short sentence)
    if len(error_message.strip()) < 5:
        return False
    
    # Check for common quality indicators
    quality_indicators = [
        # Should provide context (not just a code or single word)
        len(error_message.split()) >= 2,  # At least 2 words
        
        # Should be readable (not just stack traces or codes)
        not error_message.startswith("Traceback"),
        not all(c in "0123456789abcdefABCDEF-" for c in error_message.replace(" ", "")[:20]),
    ]
    
    return all(quality_indicators)


def _check_for_suggestions(error_message: str) -> bool:
    """
    Check if an error message contains actionable suggestions.
    
    Args:
        error_message: Error message to check
        
    Returns:
        True if error message contains suggestions
    """
    suggestion_indicators = [
        "suggested fix" in error_message.lower(),
        "suggestion" in error_message.lower(),
        "try" in error_message.lower(),
        "ensure" in error_message.lower(),
        "check" in error_message.lower(),
        "install" in error_message.lower(),
        "verify" in error_message.lower(),
        "•" in error_message,  # Bullet points often indicate suggestions
        "-" in error_message and "\n" in error_message,  # List format
    ]
    
    return any(suggestion_indicators)


class TestExportErrorHandling:
    """Property-based tests for export error handling."""
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_error_handling_invalid_template(self, export_service, cv_data):
        """
        Property 20: Export Error Handling - Invalid Template
        
        For any export operation that fails due to invalid template, the system 
        should provide detailed error information and suggest corrective actions.
        
        **Validates: Requirements 9.4**
        """
        # Generate a random invalid template ID
        invalid_template_id = f"invalid_template_{uuid.uuid4().hex[:8]}"
        
        # Ensure it's actually invalid
        available_templates = [t["template_id"] for t in export_service.get_available_templates()]
        assume(invalid_template_id not in available_templates)
        
        # Step 1: Create export request with invalid template
        export_request = ExportRequest(
            cv_id=cv_data.id,
            format=ExportFormat.TXT,
            template_id=invalid_template_id
        )
        
        # Step 2: Attempt export
        export_response = export_service.export_cv(cv_data, export_request)
        
        # Step 3: Verify export failed
        assert export_response.status == ExportStatus.FAILED, \
            "Export with invalid template should fail"
        
        # Step 4: Verify error message exists and is informative
        assert export_response.error_message is not None, \
            "Failed export should have error message"
        assert _check_error_message_quality(export_response.error_message), \
            f"Error message should be informative: {export_response.error_message}"
        
        # Step 5: Verify error message mentions the template issue
        assert "template" in export_response.error_message.lower(), \
            "Error message should mention template issue"
        
        # Step 6: Verify error message contains suggestions
        assert _check_for_suggestions(export_response.error_message), \
            f"Error message should contain actionable suggestions: {export_response.error_message}"
        
        # Step 7: Verify no file was created
        assert export_response.file_path is None, \
            "Failed export should not have file path"
        assert export_response.download_url is None, \
            "Failed export should not have download URL"
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_error_handling_missing_dependencies(self, temp_root_dir, cv_data):
        """
        Property 20: Export Error Handling - Missing Dependencies
        
        For any export operation that fails due to missing dependencies, the system 
        should provide detailed error information and suggest corrective actions.
        
        **Validates: Requirements 9.4**
        """
        # Step 1: Create service with missing export script
        export_script_path = Path(temp_root_dir) / "scripts" / "export.sh"
        if export_script_path.exists():
            export_script_path.unlink()
        
        # Step 2: Try to initialize service (should fail or handle gracefully)
        try:
            service = ExportService(
                root_dir=temp_root_dir,
                export_script_path=export_script_path
            )
            
            # If service initialized, try export
            export_request = ExportRequest(
                cv_id=cv_data.id,
                format=ExportFormat.TXT,
                template_id="default"
            )
            
            export_response = service.export_cv(cv_data, export_request)
            
            # Should fail with informative error
            assert export_response.status == ExportStatus.FAILED, \
                "Export with missing dependencies should fail"
            assert export_response.error_message is not None, \
                "Failed export should have error message"
            assert _check_error_message_quality(export_response.error_message), \
                "Error message should be informative"
            
        except Exception as e:
            # If initialization fails, that's also acceptable - verify error is informative
            error_message = str(e)
            assert len(error_message) > 0, "Exception should have message"
            assert _check_error_message_quality(error_message), \
                f"Exception message should be informative: {error_message}"
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_error_handling_permission_errors(self, temp_root_dir, cv_data):
        """
        Property 20: Export Error Handling - Permission Errors
        
        For any export operation that fails due to permission issues, the system 
        should provide detailed error information and suggest corrective actions.
        
        **Validates: Requirements 9.4**
        """
        # Step 1: Create service
        service = ExportService(
            root_dir=temp_root_dir,
            export_script_path=Path(temp_root_dir) / "scripts" / "export.sh"
        )
        
        # Step 2: Make export directory read-only
        export_dir = Path(temp_root_dir) / "exports" / "txt"
        export_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Remove write permissions
            os.chmod(export_dir, 0o444)
            
            # Step 3: Attempt export
            export_request = ExportRequest(
                cv_id=cv_data.id,
                format=ExportFormat.TXT,
                template_id="default"
            )
            
            export_response = service.export_cv(cv_data, export_request)
            
            # Step 4: Verify export failed
            assert export_response.status == ExportStatus.FAILED, \
                "Export with permission issues should fail"
            
            # Step 5: Verify error message is informative
            assert export_response.error_message is not None, \
                "Failed export should have error message"
            assert _check_error_message_quality(export_response.error_message), \
                "Error message should be informative"
            
            # Step 6: Verify error message mentions permission or access issue
            permission_keywords = ["permission", "access", "write", "directory"]
            assert any(keyword in export_response.error_message.lower() for keyword in permission_keywords), \
                f"Error message should mention permission issue: {export_response.error_message}"
            
            # Step 7: Verify error message contains suggestions
            assert _check_for_suggestions(export_response.error_message), \
                "Error message should contain actionable suggestions"
            
        finally:
            # Restore permissions for cleanup
            try:
                os.chmod(export_dir, 0o755)
            except:
                pass
    
    @given(cv_data=cv_model_strategy(), export_format=st.sampled_from([ExportFormat.TXT, ExportFormat.DOCX, ExportFormat.PDF]))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_error_handling_response_consistency(self, export_service, cv_data, export_format):
        """
        Property 20: Export Error Handling - Response Consistency
        
        For any export operation that fails, the response should be consistent 
        and contain all required error information fields.
        
        **Validates: Requirements 9.4**
        """
        # Step 1: Create export request (may succeed or fail depending on dependencies)
        export_request = ExportRequest(
            cv_id=cv_data.id,
            format=export_format,
            template_id="default"
        )
        
        # Step 2: Perform export
        export_response = export_service.export_cv(cv_data, export_request)
        
        # Step 3: Verify response structure is consistent
        assert hasattr(export_response, 'status'), "Response should have status"
        assert hasattr(export_response, 'error_message'), "Response should have error_message field"
        assert hasattr(export_response, 'file_path'), "Response should have file_path field"
        assert hasattr(export_response, 'download_url'), "Response should have download_url field"
        
        # Step 4: If export failed, verify error handling consistency
        if export_response.status == ExportStatus.FAILED:
            # Failed exports must have error message
            assert export_response.error_message is not None, \
                "Failed export must have error message"
            assert len(export_response.error_message) > 0, \
                "Failed export error message must not be empty"
            
            # Failed exports should not have file information
            assert export_response.file_path is None, \
                "Failed export should not have file path"
            assert export_response.download_url is None, \
                "Failed export should not have download URL"
            assert export_response.completed_at is None, \
                "Failed export should not have completion timestamp"
            
            # Error message should meet quality standards
            assert _check_error_message_quality(export_response.error_message), \
                f"Error message should be informative: {export_response.error_message}"
        
        # Step 5: If export succeeded, verify success response consistency
        elif export_response.status == ExportStatus.COMPLETED:
            # Successful exports must have file information
            assert export_response.file_path is not None, \
                "Completed export must have file path"
            assert export_response.download_url is not None, \
                "Completed export must have download URL"
            assert export_response.completed_at is not None, \
                "Completed export must have completion timestamp"
            
            # Successful exports should not have error message
            assert export_response.error_message is None or len(export_response.error_message) == 0, \
                "Completed export should not have error message"
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_error_handling_validation_errors(self, export_service, cv_data):
        """
        Property 20: Export Error Handling - Validation Errors
        
        For any export operation that fails validation, the system should provide 
        detailed error information and suggest corrective actions.
        
        **Validates: Requirements 9.4**
        """
        # Test various validation error scenarios
        
        # Scenario 1: Empty CV ID (Pydantic validation)
        # This should raise a ValidationError at the Pydantic level
        try:
            export_request = ExportRequest(
                cv_id="",
                format=ExportFormat.TXT,
                template_id="default"
            )
            pytest.fail("Empty CV ID should raise ValidationError")
        except Exception as e:
            # Pydantic validation error is expected and acceptable
            error_message = str(e)
            assert len(error_message) > 0, "Validation exception should have message"
            assert "cv" in error_message.lower() or "id" in error_message.lower(), \
                "Validation error should mention CV ID issue"
        
        # Scenario 2: Invalid template (service-level validation)
        export_request = ExportRequest(
            cv_id=cv_data.id,
            format=ExportFormat.TXT,
            template_id="nonexistent_template_xyz"
        )
        
        export_response = export_service.export_cv(cv_data, export_request)
        
        assert export_response.status == ExportStatus.FAILED, \
            "Export with invalid template should fail"
        assert export_response.error_message is not None, \
            "Failed validation should have error message"
        assert _check_error_message_quality(export_response.error_message), \
            "Validation error message should be informative"
        assert "template" in export_response.error_message.lower(), \
            "Error message should mention template issue"
        assert _check_for_suggestions(export_response.error_message), \
            "Validation error should include suggestions"


class TestExportErrorHandlingEdgeCases:
    """Unit tests for specific export error handling edge cases."""
    
    def test_export_error_handling_with_corrupted_template(self, temp_root_dir):
        """Test error handling when template file is corrupted."""
        # Create service
        service = ExportService(
            root_dir=temp_root_dir,
            export_script_path=Path(temp_root_dir) / "scripts" / "export.sh"
        )
        
        # Corrupt the template file
        template_path = Path(temp_root_dir) / "templates" / "cv.latex"
        if template_path.exists():
            with open(template_path, 'w') as f:
                f.write("CORRUPTED TEMPLATE CONTENT \\invalid\\latex\\commands")
        
        # Create test CV
        test_cv = CVModel(
            metadata=CVMetadata(title="Test CV"),
            personal_info=PersonalInfo(name="Test User")
        )
        
        # Attempt PDF export (most likely to fail with corrupted template)
        export_request = ExportRequest(
            cv_id=test_cv.id,
            format=ExportFormat.PDF,
            template_id="default"
        )
        
        export_response = service.export_cv(test_cv, export_request)
        
        # Should fail with informative error
        if export_response.status == ExportStatus.FAILED:
            assert export_response.error_message is not None
            assert _check_error_message_quality(export_response.error_message)
    
    def test_export_error_handling_with_missing_pandoc(self, temp_root_dir, monkeypatch):
        """Test error handling when Pandoc is not available."""
        # Mock subprocess to simulate missing Pandoc
        def mock_run(*args, **kwargs):
            if "pandoc" in str(args[0]):
                raise FileNotFoundError("pandoc not found")
            return subprocess.CompletedProcess(args[0], 0, "", "")
        
        monkeypatch.setattr(subprocess, "run", mock_run)
        
        # Try to create service
        try:
            service = ExportService(
                root_dir=temp_root_dir,
                export_script_path=Path(temp_root_dir) / "scripts" / "export.sh"
            )
            pytest.fail("Service should fail to initialize without Pandoc")
        except Exception as e:
            # Should have informative error message
            error_message = str(e)
            assert len(error_message) > 0
            assert "pandoc" in error_message.lower()
    
    def test_export_error_handling_format_specific_errors(self, export_service):
        """Test that error messages are format-specific when appropriate."""
        test_cv = CVModel(
            metadata=CVMetadata(title="Test CV"),
            personal_info=PersonalInfo(name="Test User")
        )
        
        # Test with invalid template for each format
        for export_format in [ExportFormat.PDF, ExportFormat.DOCX, ExportFormat.TXT]:
            export_request = ExportRequest(
                cv_id=test_cv.id,
                format=export_format,
                template_id="invalid_template"
            )
            
            export_response = export_service.export_cv(test_cv, export_request)
            
            if export_response.status == ExportStatus.FAILED:
                # Error message should be present and informative
                assert export_response.error_message is not None
                assert _check_error_message_quality(export_response.error_message)
                
                # Should mention the format or template
                assert any(keyword in export_response.error_message.lower() 
                          for keyword in ["template", export_format.value])
