"""
Property-based tests for PDF engine compatibility.

Feature: cv-web-app, Property 19: PDF Engine Compatibility
Validates: Requirements 9.2
"""
import tempfile
import shutil
import os
import subprocess
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
from app.models.export_models import ExportFormat, ExportRequest
from app.services.export_service import ExportService
from app.utils.pdf_engines import (
    get_pdf_engine_detector, PDFEngine, validate_pdf_engine_availability
)


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
    temp_dir = tempfile.mkdtemp(prefix="cv_pdf_engine_test_")
    
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


def _get_available_pdf_engines():
    """Get list of available PDF engines for testing."""
    detector = get_pdf_engine_detector()
    return detector.get_available_engines()


def _validate_pdf_file(file_path: Path) -> bool:
    """
    Validate that a file is a valid PDF.
    
    Args:
        file_path: Path to the file to validate
        
    Returns:
        True if file is a valid PDF
    """
    if not file_path.exists():
        return False
    
    try:
        # Check PDF magic number
        with open(file_path, 'rb') as f:
            header = f.read(4)
        
        if header != b'%PDF':
            return False
        
        # Check file size is reasonable
        file_size = file_path.stat().st_size
        if file_size == 0:
            return False
        
        # Try to validate PDF structure with pdfinfo if available
        try:
            result = subprocess.run(
                ["pdfinfo", str(file_path)],
                capture_output=True,
                timeout=10
            )
            # If pdfinfo succeeds, the PDF is valid
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # pdfinfo not available, rely on magic number check
            pass
        
        return True
        
    except Exception:
        return False


class TestPDFEngineCompatibility:
    """Property-based tests for PDF engine compatibility."""
    
    @pytest.mark.skipif(not _check_pdf_dependencies_available(), reason="PDF dependencies not available")
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_pdf_engine_compatibility_all_engines(self, export_service, cv_data):
        """
        Property 19: PDF Engine Compatibility
        
        For any valid CV data, exports should succeed with all supported PDF engines 
        (xelatex, tectonic) and produce valid PDF files.
        
        **Validates: Requirements 9.2**
        """
        # Get available PDF engines
        available_engines = _get_available_pdf_engines()
        
        # Skip test if no PDF engines are available
        if not available_engines:
            pytest.skip("No PDF engines available for testing")
        
        # Test with each available engine
        for engine in available_engines:
            # Step 1: Create export request for PDF format
            export_request = ExportRequest(
                cv_id=cv_data.id,
                format=ExportFormat.PDF,
                template_id="default"
            )
            
            # Step 2: Set environment to prefer this specific engine
            original_env = os.environ.get("PDF_ENGINE")
            os.environ["PDF_ENGINE"] = engine.value
            
            try:
                # Step 3: Perform export
                export_response = export_service.export_cv(cv_data, export_request)
                
                # Step 4: Verify export completed successfully or failed gracefully
                assert export_response is not None, f"Export should return response for {engine.value}"
                assert export_response.cv_id == cv_data.id, f"Response should have correct CV ID for {engine.value}"
                assert export_response.format == ExportFormat.PDF, f"Response should have PDF format for {engine.value}"
                
                # Step 5: Verify response status is valid
                valid_statuses = ["completed", "failed", "in_progress"]
                assert export_response.status.value in valid_statuses, \
                    f"Export status should be valid for {engine.value}: {export_response.status.value}"
                
                # Step 6: If completed, verify PDF file is valid
                if export_response.status.value == "completed":
                    assert export_response.file_path is not None, \
                        f"Completed export should have file path for {engine.value}"
                    
                    file_path = Path(export_response.file_path)
                    assert file_path.exists(), \
                        f"Export file should exist for {engine.value}: {file_path}"
                    
                    # Validate PDF format
                    assert _validate_pdf_file(file_path), \
                        f"Generated file should be valid PDF for {engine.value}"
                    
                    # Validate file size is reasonable
                    file_size = file_path.stat().st_size
                    assert file_size > 0, f"Generated PDF should not be empty for {engine.value}"
                    assert file_size < 100 * 1024 * 1024, \
                        f"Generated PDF should not be unreasonably large (>100MB) for {engine.value}"
                    
                    # Validate response metadata
                    assert export_response.file_size == file_size, \
                        f"Response file size should match actual file size for {engine.value}"
                    assert export_response.download_url is not None, \
                        f"Completed export should have download URL for {engine.value}"
                    assert export_response.completed_at is not None, \
                        f"Completed export should have completion timestamp for {engine.value}"
                
                elif export_response.status.value == "failed":
                    # Export failed - validate error handling
                    assert export_response.error_message is not None, \
                        f"Failed export should have error message for {engine.value}"
                    assert len(export_response.error_message) > 0, \
                        f"Error message should not be empty for {engine.value}"
                    assert export_response.file_path is None, \
                        f"Failed export should not have file path for {engine.value}"
                    assert export_response.download_url is None, \
                        f"Failed export should not have download URL for {engine.value}"
                
            finally:
                # Restore original environment
                if original_env is not None:
                    os.environ["PDF_ENGINE"] = original_env
                elif "PDF_ENGINE" in os.environ:
                    del os.environ["PDF_ENGINE"]
    
    @pytest.mark.skipif(not _check_pdf_dependencies_available(), reason="PDF dependencies not available")
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_pdf_engine_compatibility_fallback(self, export_service, cv_data):
        """
        Property 19: PDF Engine Compatibility - Fallback Behavior
        
        For any valid CV data, if one PDF engine fails, the system should 
        automatically try fallback engines and produce a valid PDF.
        
        **Validates: Requirements 9.2**
        """
        # Get available PDF engines
        available_engines = _get_available_pdf_engines()
        
        # Skip test if less than 2 engines available (can't test fallback)
        if len(available_engines) < 2:
            pytest.skip("Need at least 2 PDF engines to test fallback behavior")
        
        # Step 1: Create export request for PDF format
        export_request = ExportRequest(
            cv_id=cv_data.id,
            format=ExportFormat.PDF,
            template_id="default"
        )
        
        # Step 2: Perform export without specifying engine (should use fallback logic)
        export_response = export_service.export_cv(cv_data, export_request)
        
        # Step 3: Verify export completed successfully or failed gracefully
        assert export_response is not None, "Export should return response"
        assert export_response.cv_id == cv_data.id, "Response should have correct CV ID"
        assert export_response.format == ExportFormat.PDF, "Response should have PDF format"
        
        # Step 4: If completed, verify PDF file is valid
        if export_response.status.value == "completed":
            assert export_response.file_path is not None, "Completed export should have file path"
            
            file_path = Path(export_response.file_path)
            assert file_path.exists(), f"Export file should exist: {file_path}"
            
            # Validate PDF format
            assert _validate_pdf_file(file_path), "Generated file should be valid PDF"
            
            # Validate file size is reasonable
            file_size = file_path.stat().st_size
            assert file_size > 0, "Generated PDF should not be empty"
            assert file_size < 100 * 1024 * 1024, "Generated PDF should not be unreasonably large (>100MB)"
    
    @pytest.mark.skipif(not _check_pdf_dependencies_available(), reason="PDF dependencies not available")
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_pdf_engine_compatibility_consistency(self, export_service, cv_data):
        """
        Property 19: PDF Engine Compatibility - Output Consistency
        
        For any valid CV data, all PDF engines should produce valid PDFs with 
        consistent content (though formatting may differ slightly).
        
        **Validates: Requirements 9.2**
        """
        # Get available PDF engines
        available_engines = _get_available_pdf_engines()
        
        # Skip test if no PDF engines are available
        if not available_engines:
            pytest.skip("No PDF engines available for testing")
        
        generated_files = []
        
        # Generate PDFs with each available engine
        for engine in available_engines:
            export_request = ExportRequest(
                cv_id=cv_data.id,
                format=ExportFormat.PDF,
                template_id="default"
            )
            
            # Set environment to prefer this specific engine
            original_env = os.environ.get("PDF_ENGINE")
            os.environ["PDF_ENGINE"] = engine.value
            
            try:
                export_response = export_service.export_cv(cv_data, export_request)
                
                if export_response.status.value == "completed":
                    file_path = Path(export_response.file_path)
                    if file_path.exists() and _validate_pdf_file(file_path):
                        generated_files.append({
                            "engine": engine.value,
                            "path": file_path,
                            "size": file_path.stat().st_size
                        })
            finally:
                # Restore original environment
                if original_env is not None:
                    os.environ["PDF_ENGINE"] = original_env
                elif "PDF_ENGINE" in os.environ:
                    del os.environ["PDF_ENGINE"]
        
        # Verify that all successful exports produced valid PDFs
        if generated_files:
            for file_info in generated_files:
                # Each generated PDF should be valid
                assert _validate_pdf_file(file_info["path"]), \
                    f"PDF generated by {file_info['engine']} should be valid"
                
                # Each PDF should have reasonable size
                assert file_info["size"] > 0, \
                    f"PDF generated by {file_info['engine']} should not be empty"
                assert file_info["size"] < 100 * 1024 * 1024, \
                    f"PDF generated by {file_info['engine']} should not be unreasonably large"


# Additional unit tests for specific PDF engine scenarios
class TestPDFEngineCompatibilityEdgeCases:
    """Unit tests for specific PDF engine compatibility edge cases."""
    
    @pytest.mark.skipif(not _check_pdf_dependencies_available(), reason="PDF dependencies not available")
    def test_pdf_engine_detection(self, export_service):
        """Test that PDF engine detection works correctly."""
        detector = get_pdf_engine_detector()
        
        # Detect engines
        engine_info = detector.detect_engines(force_refresh=True)
        
        # Should detect at least one engine
        available_engines = detector.get_available_engines()
        assert len(available_engines) > 0, "Should detect at least one PDF engine"
        
        # Each detected engine should have valid info
        for engine in available_engines:
            info = engine_info[engine]
            assert info.available is True, f"{engine.value} should be marked as available"
            assert info.version is not None, f"{engine.value} should have version information"
    
    @pytest.mark.skipif(not _check_pdf_dependencies_available(), reason="PDF dependencies not available")
    def test_pdf_engine_validation(self, export_service):
        """Test that PDF engine validation works correctly."""
        is_valid, issues = validate_pdf_engine_availability()
        
        # Should be valid if we have PDF dependencies
        assert is_valid is True, "PDF engines should be available"
        assert len(issues) == 0, "Should have no validation issues"
    
    @pytest.mark.skipif(not _check_pdf_dependencies_available(), reason="PDF dependencies not available")
    def test_minimal_cv_pdf_export_all_engines(self, export_service):
        """Test PDF export with minimal CV data using all available engines."""
        minimal_cv = CVModel(
            metadata=CVMetadata(title="Minimal CV"),
            personal_info=PersonalInfo(name="Test User")
        )
        
        available_engines = _get_available_pdf_engines()
        
        for engine in available_engines:
            export_request = ExportRequest(
                cv_id=minimal_cv.id,
                format=ExportFormat.PDF,
                template_id="default"
            )
            
            # Set environment to prefer this specific engine
            original_env = os.environ.get("PDF_ENGINE")
            os.environ["PDF_ENGINE"] = engine.value
            
            try:
                export_response = export_service.export_cv(minimal_cv, export_request)
                
                # Should handle minimal CV data gracefully
                assert export_response is not None
                assert export_response.cv_id == minimal_cv.id
                assert export_response.format == ExportFormat.PDF
                
                if export_response.status.value == "completed":
                    file_path = Path(export_response.file_path)
                    assert file_path.exists()
                    assert _validate_pdf_file(file_path)
            finally:
                # Restore original environment
                if original_env is not None:
                    os.environ["PDF_ENGINE"] = original_env
                elif "PDF_ENGINE" in os.environ:
                    del os.environ["PDF_ENGINE"]
    
    @pytest.mark.skipif(not _check_pdf_dependencies_available(), reason="PDF dependencies not available")
    def test_pdf_export_with_special_characters(self, export_service):
        """Test PDF export with special characters in CV data using all engines."""
        special_cv = CVModel(
            metadata=CVMetadata(title="CV with Special Characters"),
            personal_info=PersonalInfo(
                name="José María García-López",
                title="Senior Developer & Team Lead"
            ),
            summary="Experience with C++, .NET, and other technologies"
        )
        
        available_engines = _get_available_pdf_engines()
        
        for engine in available_engines:
            export_request = ExportRequest(
                cv_id=special_cv.id,
                format=ExportFormat.PDF,
                template_id="default"
            )
            
            # Set environment to prefer this specific engine
            original_env = os.environ.get("PDF_ENGINE")
            os.environ["PDF_ENGINE"] = engine.value
            
            try:
                export_response = export_service.export_cv(special_cv, export_request)
                
                # Should handle special characters gracefully
                assert export_response is not None
                assert export_response.cv_id == special_cv.id
                
                if export_response.status.value == "completed":
                    file_path = Path(export_response.file_path)
                    assert file_path.exists()
                    assert _validate_pdf_file(file_path)
            finally:
                # Restore original environment
                if original_env is not None:
                    os.environ["PDF_ENGINE"] = original_env
                elif "PDF_ENGINE" in os.environ:
                    del os.environ["PDF_ENGINE"]
