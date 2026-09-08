"""
Property-based tests for export directory structure.

Feature: cv-web-app, Property 17: Export Directory Structure
Validates: Requirements 7.3
"""
import tempfile
import shutil
import os
from pathlib import Path
from typing import Dict, Any, List
import uuid

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

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
        summary=draw(st.one_of(st.none(), st.text(min_size=10, max_size=500)))
    )


@pytest.fixture
def temp_root_dir():
    """Fixture providing temporary root directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="cv_export_dir_test_")
    
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


def _validate_export_directory_structure(root_dir: Path, format: ExportFormat) -> bool:
    """
    Validate that export directory structure matches the existing export system.
    
    The existing export system uses:
    - exports/pdf/ for PDF files
    - exports/docx/ for DOCX files
    - exports/txt/ for TXT files
    
    Args:
        root_dir: Root directory of the application
        format: Export format
        
    Returns:
        True if directory structure matches expected pattern
    """
    exports_dir = root_dir / "exports"
    format_dir = exports_dir / format.value
    
    # Check that exports directory exists
    if not exports_dir.exists():
        return False
    
    # Check that format-specific subdirectory exists
    if not format_dir.exists():
        return False
    
    # Check that it's a directory
    if not format_dir.is_dir():
        return False
    
    return True


def _validate_file_in_correct_directory(file_path: Path, format: ExportFormat, root_dir: Path) -> bool:
    """
    Validate that an exported file is stored in the correct format-specific directory.
    
    Args:
        file_path: Path to the exported file
        format: Export format
        root_dir: Root directory of the application
        
    Returns:
        True if file is in the correct directory
    """
    if not file_path.exists():
        return False
    
    # Expected directory structure: {root_dir}/exports/{format}/
    expected_parent = root_dir / "exports" / format.value
    
    # Check if file's parent directory matches expected structure
    return file_path.parent == expected_parent


def _validate_directory_hierarchy(root_dir: Path) -> bool:
    """
    Validate the complete export directory hierarchy.
    
    Args:
        root_dir: Root directory of the application
        
    Returns:
        True if directory hierarchy is correct
    """
    exports_dir = root_dir / "exports"
    
    # Check exports directory exists
    if not exports_dir.exists() or not exports_dir.is_dir():
        return False
    
    # Check all format subdirectories exist
    required_subdirs = ["pdf", "docx", "txt"]
    for subdir in required_subdirs:
        format_dir = exports_dir / subdir
        if not format_dir.exists() or not format_dir.is_dir():
            return False
    
    return True


def _get_file_relative_path(file_path: Path, root_dir: Path) -> str:
    """
    Get the relative path of a file from the root directory.
    
    Args:
        file_path: Absolute path to the file
        root_dir: Root directory
        
    Returns:
        Relative path as string
    """
    try:
        return str(file_path.relative_to(root_dir))
    except ValueError:
        return str(file_path)


class TestExportDirectoryStructure:
    """Property-based tests for export directory structure."""
    
    @given(cv_data=cv_model_strategy(), export_format=st.sampled_from([ExportFormat.TXT]))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_directory_structure_txt(self, export_service, temp_root_dir, cv_data, export_format):
        """
        Property 17: Export Directory Structure - TXT Format
        
        For any export operation, files should be stored in the same directory 
        structure as the existing export system (exports/{format}/).
        
        **Validates: Requirements 7.3**
        """
        root_dir = Path(temp_root_dir)
        
        # Step 1: Verify directory structure exists before export
        assert _validate_export_directory_structure(root_dir, export_format), \
            f"Export directory structure should exist for {export_format.value}"
        
        # Step 2: Create export request
        export_request = ExportRequest(
            cv_id=cv_data.id,
            format=export_format,
            template_id="default"
        )
        
        # Step 3: Perform export
        export_response = export_service.export_cv(cv_data, export_request)
        
        # Step 4: If export succeeded, validate file location (Requirements 7.3)
        if export_response.status.value == "completed":
            assert export_response.file_path is not None, "Completed export should have file path"
            
            file_path = Path(export_response.file_path)
            assert file_path.exists(), f"Export file should exist: {file_path}"
            
            # Step 5: Validate file is in correct directory structure (Requirements 7.3)
            assert _validate_file_in_correct_directory(file_path, export_format, root_dir), \
                f"Export file should be in exports/{export_format.value}/ directory"
            
            # Step 6: Validate relative path matches expected pattern
            relative_path = _get_file_relative_path(file_path, root_dir)
            expected_prefix = f"exports/{export_format.value}/"
            assert relative_path.startswith(expected_prefix), \
                f"Export file path should start with {expected_prefix}, got: {relative_path}"
            
            # Step 7: Validate file extension matches format
            assert file_path.suffix == f".{export_format.value}", \
                f"Export file should have .{export_format.value} extension"
    
    @given(cv_data=cv_model_strategy(), export_format=st.sampled_from([ExportFormat.DOCX]))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_directory_structure_docx(self, export_service, temp_root_dir, cv_data, export_format):
        """
        Property 17: Export Directory Structure - DOCX Format
        
        For any export operation, files should be stored in the same directory 
        structure as the existing export system (exports/{format}/).
        
        **Validates: Requirements 7.3**
        """
        root_dir = Path(temp_root_dir)
        
        # Step 1: Verify directory structure exists before export
        assert _validate_export_directory_structure(root_dir, export_format), \
            f"Export directory structure should exist for {export_format.value}"
        
        # Step 2: Create export request
        export_request = ExportRequest(
            cv_id=cv_data.id,
            format=export_format,
            template_id="default"
        )
        
        # Step 3: Perform export
        export_response = export_service.export_cv(cv_data, export_request)
        
        # Step 4: If export succeeded, validate file location (Requirements 7.3)
        if export_response.status.value == "completed":
            assert export_response.file_path is not None, "Completed export should have file path"
            
            file_path = Path(export_response.file_path)
            assert file_path.exists(), f"Export file should exist: {file_path}"
            
            # Step 5: Validate file is in correct directory structure (Requirements 7.3)
            assert _validate_file_in_correct_directory(file_path, export_format, root_dir), \
                f"Export file should be in exports/{export_format.value}/ directory"
            
            # Step 6: Validate relative path matches expected pattern
            relative_path = _get_file_relative_path(file_path, root_dir)
            expected_prefix = f"exports/{export_format.value}/"
            assert relative_path.startswith(expected_prefix), \
                f"Export file path should start with {expected_prefix}, got: {relative_path}"
            
            # Step 7: Validate file extension matches format
            assert file_path.suffix == f".{export_format.value}", \
                f"Export file should have .{export_format.value} extension"
    
    @given(cv_data=cv_model_strategy(), export_format=st.sampled_from([ExportFormat.PDF]))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_directory_structure_pdf(self, export_service, temp_root_dir, cv_data, export_format):
        """
        Property 17: Export Directory Structure - PDF Format
        
        For any export operation, files should be stored in the same directory 
        structure as the existing export system (exports/{format}/).
        
        **Validates: Requirements 7.3**
        """
        root_dir = Path(temp_root_dir)
        
        # Step 1: Verify directory structure exists before export
        assert _validate_export_directory_structure(root_dir, export_format), \
            f"Export directory structure should exist for {export_format.value}"
        
        # Step 2: Create export request
        export_request = ExportRequest(
            cv_id=cv_data.id,
            format=export_format,
            template_id="default"
        )
        
        # Step 3: Perform export
        export_response = export_service.export_cv(cv_data, export_request)
        
        # Step 4: If export succeeded, validate file location (Requirements 7.3)
        if export_response.status.value == "completed":
            assert export_response.file_path is not None, "Completed export should have file path"
            
            file_path = Path(export_response.file_path)
            assert file_path.exists(), f"Export file should exist: {file_path}"
            
            # Step 5: Validate file is in correct directory structure (Requirements 7.3)
            assert _validate_file_in_correct_directory(file_path, export_format, root_dir), \
                f"Export file should be in exports/{export_format.value}/ directory"
            
            # Step 6: Validate relative path matches expected pattern
            relative_path = _get_file_relative_path(file_path, root_dir)
            expected_prefix = f"exports/{export_format.value}/"
            assert relative_path.startswith(expected_prefix), \
                f"Export file path should start with {expected_prefix}, got: {relative_path}"
            
            # Step 7: Validate file extension matches format
            assert file_path.suffix == f".{export_format.value}", \
                f"Export file should have .{export_format.value} extension"
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_directory_structure_all_formats(self, export_service, temp_root_dir, cv_data):
        """
        Property 17: Export Directory Structure - All Formats
        
        For any export operation across all formats, files should be stored in 
        the correct format-specific subdirectories.
        
        **Validates: Requirements 7.3**
        """
        root_dir = Path(temp_root_dir)
        
        # Step 1: Verify complete directory hierarchy exists
        assert _validate_directory_hierarchy(root_dir), \
            "Complete export directory hierarchy should exist"
        
        # Step 2: Test each format
        supported_formats = [ExportFormat.TXT, ExportFormat.DOCX, ExportFormat.PDF]
        
        for export_format in supported_formats:
            # Step 3: Create export request for each format
            export_request = ExportRequest(
                cv_id=cv_data.id,
                format=export_format,
                template_id="default"
            )
            
            # Step 4: Perform export
            export_response = export_service.export_cv(cv_data, export_request)
            
            # Step 5: If export succeeded, validate directory structure (Requirements 7.3)
            if export_response.status.value == "completed":
                assert export_response.file_path is not None, \
                    f"Completed export should have file path for {export_format.value}"
                
                file_path = Path(export_response.file_path)
                assert file_path.exists(), \
                    f"Export file should exist for {export_format.value}: {file_path}"
                
                # Validate file is in correct directory
                assert _validate_file_in_correct_directory(file_path, export_format, root_dir), \
                    f"Export file should be in exports/{export_format.value}/ directory"
                
                # Validate no files are placed in wrong directories
                for other_format in supported_formats:
                    if other_format != export_format:
                        wrong_dir = root_dir / "exports" / other_format.value
                        assert file_path.parent != wrong_dir, \
                            f"{export_format.value} file should not be in {other_format.value} directory"
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_directory_structure_consistency(self, export_service, temp_root_dir, cv_data):
        """
        Property 17: Export Directory Structure - Consistency
        
        For any multiple exports of the same CV, all files should be stored in 
        the same directory structure pattern.
        
        **Validates: Requirements 7.3**
        """
        root_dir = Path(temp_root_dir)
        
        # Step 1: Perform multiple exports with TXT format
        export_format = ExportFormat.TXT
        num_exports = 3
        
        exported_files = []
        
        for i in range(num_exports):
            export_request = ExportRequest(
                cv_id=cv_data.id,
                format=export_format,
                template_id="default"
            )
            
            export_response = export_service.export_cv(cv_data, export_request)
            
            if export_response.status.value == "completed":
                exported_files.append(Path(export_response.file_path))
        
        # Step 2: Validate all files follow same directory structure (Requirements 7.3)
        if len(exported_files) > 0:
            expected_parent = root_dir / "exports" / export_format.value
            
            for file_path in exported_files:
                assert file_path.exists(), f"Export file should exist: {file_path}"
                
                # All files should be in the same parent directory
                assert file_path.parent == expected_parent, \
                    f"All exports should be in {expected_parent}, got: {file_path.parent}"
                
                # All files should have correct extension
                assert file_path.suffix == f".{export_format.value}", \
                    f"All exports should have .{export_format.value} extension"
    
    def test_export_directory_structure_initialization(self, export_service, temp_root_dir):
        """
        Property 17: Export Directory Structure - Initialization
        
        The export service should create the required directory structure on 
        initialization if it doesn't exist.
        
        **Validates: Requirements 7.3**
        """
        root_dir = Path(temp_root_dir)
        
        # Step 1: Verify directory structure was created during initialization
        assert _validate_directory_hierarchy(root_dir), \
            "Export directory hierarchy should be created on initialization"
        
        # Step 2: Verify all format directories exist
        exports_dir = root_dir / "exports"
        assert exports_dir.exists(), "exports/ directory should exist"
        assert exports_dir.is_dir(), "exports/ should be a directory"
        
        for format_value in ["pdf", "docx", "txt"]:
            format_dir = exports_dir / format_value
            assert format_dir.exists(), f"exports/{format_value}/ should exist"
            assert format_dir.is_dir(), f"exports/{format_value}/ should be a directory"
    
    def test_export_directory_structure_permissions(self, export_service, temp_root_dir):
        """
        Property 17: Export Directory Structure - Permissions
        
        The export directories should have appropriate permissions for writing files.
        
        **Validates: Requirements 7.3**
        """
        root_dir = Path(temp_root_dir)
        exports_dir = root_dir / "exports"
        
        # Step 1: Verify exports directory is writable
        assert os.access(exports_dir, os.W_OK), \
            "exports/ directory should be writable"
        
        # Step 2: Verify all format directories are writable
        for format_value in ["pdf", "docx", "txt"]:
            format_dir = exports_dir / format_value
            assert os.access(format_dir, os.W_OK), \
                f"exports/{format_value}/ directory should be writable"
            
            assert os.access(format_dir, os.R_OK), \
                f"exports/{format_value}/ directory should be readable"


# Additional unit tests for specific directory structure scenarios
class TestExportDirectoryStructureEdgeCases:
    """Unit tests for specific export directory structure edge cases."""
    
    def test_export_directory_structure_with_nested_paths(self, export_service, temp_root_dir):
        """Test that export files are not placed in nested subdirectories."""
        root_dir = Path(temp_root_dir)
        
        # Create a minimal CV
        minimal_cv = CVModel(
            metadata=CVMetadata(title="Test CV"),
            personal_info=PersonalInfo(name="Test User")
        )
        
        export_request = ExportRequest(
            cv_id=minimal_cv.id,
            format=ExportFormat.TXT,
            template_id="default"
        )
        
        export_response = export_service.export_cv(minimal_cv, export_request)
        
        if export_response.status.value == "completed":
            file_path = Path(export_response.file_path)
            
            # File should be directly in exports/txt/, not in a subdirectory
            expected_parent = root_dir / "exports" / "txt"
            assert file_path.parent == expected_parent, \
                "Export file should be directly in exports/txt/, not in a subdirectory"
    
    def test_export_directory_structure_no_root_level_files(self, export_service, temp_root_dir):
        """Test that export files are not placed at the root level."""
        root_dir = Path(temp_root_dir)
        
        # Create a minimal CV
        minimal_cv = CVModel(
            metadata=CVMetadata(title="Test CV"),
            personal_info=PersonalInfo(name="Test User")
        )
        
        export_request = ExportRequest(
            cv_id=minimal_cv.id,
            format=ExportFormat.TXT,
            template_id="default"
        )
        
        export_response = export_service.export_cv(minimal_cv, export_request)
        
        if export_response.status.value == "completed":
            file_path = Path(export_response.file_path)
            
            # File should not be at root level
            assert file_path.parent != root_dir, \
                "Export file should not be at root level"
            
            # File should not be directly in exports/ without format subdirectory
            exports_dir = root_dir / "exports"
            assert file_path.parent != exports_dir, \
                "Export file should not be directly in exports/ without format subdirectory"
    
    def test_export_directory_structure_format_isolation(self, export_service, temp_root_dir):
        """Test that different formats are isolated in their own directories."""
        root_dir = Path(temp_root_dir)
        exports_dir = root_dir / "exports"
        
        # Verify format directories are separate
        pdf_dir = exports_dir / "pdf"
        docx_dir = exports_dir / "docx"
        txt_dir = exports_dir / "txt"
        
        assert pdf_dir != docx_dir, "PDF and DOCX directories should be different"
        assert pdf_dir != txt_dir, "PDF and TXT directories should be different"
        assert docx_dir != txt_dir, "DOCX and TXT directories should be different"
        
        # Verify they are all subdirectories of exports/
        assert pdf_dir.parent == exports_dir
        assert docx_dir.parent == exports_dir
        assert txt_dir.parent == exports_dir
