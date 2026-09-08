"""
Property-based tests for manual export deletion.

Feature: cv-web-app, Property 12: Manual Export Deletion
Validates: Requirements 5.4
"""
import tempfile
import shutil
import os
from pathlib import Path
from typing import Dict, Any, List
import uuid
import json
from datetime import datetime, timedelta
import time

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck, assume

from app.services.cleanup_service import CleanupService, CleanupServiceError
from app.models.export_models import ExportFormat


# Test data generators
@st.composite
def export_format_strategy(draw):
    """Generate valid export format."""
    return draw(st.sampled_from([ExportFormat.PDF, ExportFormat.DOCX, ExportFormat.TXT]))


@st.composite
def file_size_strategy(draw):
    """Generate reasonable file size in bytes."""
    return draw(st.integers(min_value=100, max_value=10240))  # 100 bytes to 10KB


@pytest.fixture
def temp_root_dir():
    """Fixture providing temporary root directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="cv_manual_deletion_test_")
    
    # Create required directory structure
    directories = [
        "exports/pdf", "exports/docx", "exports/txt", "data"
    ]
    
    for directory in directories:
        (Path(temp_dir) / directory).mkdir(parents=True, exist_ok=True)
    
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def cleanup_service(temp_root_dir):
    """Fixture providing CleanupService with temporary directory."""
    return CleanupService(root_dir=temp_root_dir)


def _create_export_file(exports_dir: Path, format_value: str, file_size: int = 1024) -> Path:
    """
    Create a test export file.
    
    Args:
        exports_dir: Root exports directory
        format_value: Export format (pdf, docx, txt)
        file_size: Size of file in bytes
        
    Returns:
        Path to created file
    """
    format_dir = exports_dir / format_value
    format_dir.mkdir(parents=True, exist_ok=True)
    
    # Create unique filename
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    file_name = f"test-cv-{timestamp}-{uuid.uuid4().hex[:8]}.{format_value}"
    file_path = format_dir / file_name
    
    # Create file with content
    with open(file_path, 'wb') as f:
        f.write(b'X' * file_size)
    
    return file_path


def _get_relative_path(file_path: Path, exports_dir: Path) -> str:
    """
    Get relative path from exports directory.
    
    Args:
        file_path: Absolute file path
        exports_dir: Exports directory
        
    Returns:
        Relative path string
    """
    return str(file_path.relative_to(exports_dir))


def _validate_file_removed_from_filesystem(file_path: Path) -> bool:
    """Validate that a file has been removed from the filesystem."""
    return not file_path.exists()


def _validate_file_exists_on_filesystem(file_path: Path) -> bool:
    """Validate that a file still exists on the filesystem."""
    return file_path.exists() and file_path.is_file()


def _count_files_in_directory(directory: Path) -> int:
    """Count files in a directory (excluding hidden files)."""
    if not directory.exists():
        return 0
    
    count = 0
    for item in directory.iterdir():
        if item.is_file() and not item.name.startswith('.'):
            count += 1
    
    return count


class TestManualExportDeletion:
    """Property-based tests for manual export deletion."""
    
    @given(
        export_format=export_format_strategy(),
        file_size=file_size_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_manual_deletion_removes_file_from_filesystem(self, cleanup_service, temp_root_dir, export_format, file_size):
        """
        Property 12: Manual Export Deletion - File Removed from Filesystem
        
        For any export file in the history, manual deletion should remove it 
        from the filesystem.
        
        **Validates: Requirements 5.4**
        """
        # Step 1: Create an export file
        exports_dir = Path(temp_root_dir) / "exports"
        export_file = _create_export_file(exports_dir, export_format.value, file_size)
        
        # Verify file was created
        assert _validate_file_exists_on_filesystem(export_file), \
            "Export file should be created"
        
        # Step 2: Get relative path for deletion
        relative_path = _get_relative_path(export_file, exports_dir)
        
        # Step 3: Perform manual deletion
        success = cleanup_service.delete_export_file(relative_path)
        
        # Step 4: Validate deletion was successful (Requirements 5.4)
        assert success, "Manual deletion should return success"
        
        # Step 5: Validate file was removed from filesystem (Requirements 5.4)
        assert _validate_file_removed_from_filesystem(export_file), \
            "Manually deleted file should be removed from filesystem"
    
    @given(
        export_format=export_format_strategy(),
        num_files=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_manual_deletion_removes_only_specified_file(self, cleanup_service, temp_root_dir, export_format, num_files):
        """
        Property 12: Manual Export Deletion - Selective Deletion
        
        For any export file in the history, manual deletion should remove only 
        that specific file and not affect other files.
        
        **Validates: Requirements 5.4**
        """
        # Step 1: Create multiple export files
        exports_dir = Path(temp_root_dir) / "exports"
        created_files = []
        
        for i in range(num_files):
            export_file = _create_export_file(exports_dir, export_format.value)
            created_files.append(export_file)
            time.sleep(0.01)  # Ensure unique filenames
        
        # Verify all files were created
        initial_count = _count_files_in_directory(exports_dir / export_format.value)
        assert initial_count >= num_files, "All files should be created"
        
        # Step 2: Select one file to delete
        file_to_delete = created_files[0]
        files_to_keep = created_files[1:]
        
        # Step 3: Perform manual deletion
        relative_path = _get_relative_path(file_to_delete, exports_dir)
        success = cleanup_service.delete_export_file(relative_path)
        
        # Step 4: Validate deletion was successful
        assert success, "Manual deletion should return success"
        
        # Step 5: Validate only the specified file was removed (Requirements 5.4)
        assert _validate_file_removed_from_filesystem(file_to_delete), \
            "Deleted file should be removed from filesystem"
        
        # Step 6: Validate other files were not affected (Requirements 5.4)
        for file_to_keep in files_to_keep:
            assert _validate_file_exists_on_filesystem(file_to_keep), \
                f"Other files should not be affected: {file_to_keep.name}"
        
        # Step 7: Validate file count decreased by exactly one
        final_count = _count_files_in_directory(exports_dir / export_format.value)
        assert final_count == initial_count - 1, \
            "File count should decrease by exactly one"
    
    @given(
        file_size=file_size_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_manual_deletion_works_across_all_formats(self, cleanup_service, temp_root_dir, file_size):
        """
        Property 12: Manual Export Deletion - All Formats Supported
        
        For any export file in any format, manual deletion should successfully 
        remove the file from the filesystem.
        
        **Validates: Requirements 5.4**
        """
        exports_dir = Path(temp_root_dir) / "exports"
        
        # Step 1: Create export files in all formats
        created_files = {}
        for export_format in [ExportFormat.PDF, ExportFormat.DOCX, ExportFormat.TXT]:
            export_file = _create_export_file(exports_dir, export_format.value, file_size)
            created_files[export_format.value] = export_file
            time.sleep(0.01)
        
        # Verify all files were created
        for format_value, file_path in created_files.items():
            assert _validate_file_exists_on_filesystem(file_path), \
                f"File should be created for {format_value}"
        
        # Step 2: Delete each file manually
        for format_value, file_path in created_files.items():
            relative_path = _get_relative_path(file_path, exports_dir)
            success = cleanup_service.delete_export_file(relative_path)
            
            # Step 3: Validate deletion was successful (Requirements 5.4)
            assert success, f"Manual deletion should succeed for {format_value}"
            
            # Step 4: Validate file was removed from filesystem (Requirements 5.4)
            assert _validate_file_removed_from_filesystem(file_path), \
                f"File should be removed from filesystem for {format_value}"
    
    @given(
        export_format=export_format_strategy(),
        file_size=file_size_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_manual_deletion_idempotent(self, cleanup_service, temp_root_dir, export_format, file_size):
        """
        Property 12: Manual Export Deletion - Idempotent Operation
        
        For any export file, attempting to delete it multiple times should 
        handle gracefully (first deletion succeeds, subsequent attempts return False).
        
        **Validates: Requirements 5.4**
        """
        # Step 1: Create an export file
        exports_dir = Path(temp_root_dir) / "exports"
        export_file = _create_export_file(exports_dir, export_format.value, file_size)
        
        assert _validate_file_exists_on_filesystem(export_file), \
            "Export file should be created"
        
        relative_path = _get_relative_path(export_file, exports_dir)
        
        # Step 2: First deletion should succeed
        success_first = cleanup_service.delete_export_file(relative_path)
        
        assert success_first, "First deletion should return success"
        assert _validate_file_removed_from_filesystem(export_file), \
            "File should be removed after first deletion"
        
        # Step 3: Second deletion should return False (file doesn't exist)
        success_second = cleanup_service.delete_export_file(relative_path)
        
        assert not success_second, \
            "Second deletion should return False (file already deleted)"
        
        # Step 4: File should still not exist
        assert _validate_file_removed_from_filesystem(export_file), \
            "File should remain deleted"
    
    @given(
        export_format=export_format_strategy(),
        file_size=file_size_strategy()
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_manual_deletion_security_path_traversal(self, cleanup_service, temp_root_dir, export_format, file_size):
        """
        Property 12: Manual Export Deletion - Security (Path Traversal)
        
        For any deletion request with path traversal attempts, the system should 
        reject the request and not delete files outside the exports directory.
        
        **Validates: Requirements 5.4**
        """
        # Step 1: Create an export file
        exports_dir = Path(temp_root_dir) / "exports"
        export_file = _create_export_file(exports_dir, export_format.value, file_size)
        
        assert _validate_file_exists_on_filesystem(export_file), \
            "Export file should be created"
        
        # Step 2: Create a file outside exports directory
        outside_dir = Path(temp_root_dir) / "data"
        outside_file = outside_dir / "sensitive_file.txt"
        with open(outside_file, 'w') as f:
            f.write("sensitive data")
        
        assert outside_file.exists(), "Outside file should be created"
        
        # Step 3: Attempt path traversal attacks
        malicious_paths = [
            f"../{outside_file.name}",
            f"../../data/{outside_file.name}",
            f"pdf/../../data/{outside_file.name}"
        ]
        
        for malicious_path in malicious_paths:
            # Step 4: Attempt deletion with malicious path
            try:
                result = cleanup_service.delete_export_file(malicious_path)
                # If it returns False, that's acceptable (file not found)
                # But it should not delete the outside file
                assert _validate_file_exists_on_filesystem(outside_file), \
                    f"Outside file should not be deleted with path: {malicious_path}"
            except CleanupServiceError:
                # Raising an error is also acceptable security behavior
                assert _validate_file_exists_on_filesystem(outside_file), \
                    f"Outside file should not be deleted with path: {malicious_path}"
        
        # Step 5: Verify the legitimate export file still exists
        assert _validate_file_exists_on_filesystem(export_file), \
            "Legitimate export file should not be affected by failed attacks"
        
        # Step 6: Verify outside file was never deleted
        assert _validate_file_exists_on_filesystem(outside_file), \
            "File outside exports directory should never be deleted"
    
    @given(
        export_format=export_format_strategy(),
        num_deletions=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_manual_deletion_multiple_sequential(self, cleanup_service, temp_root_dir, export_format, num_deletions):
        """
        Property 12: Manual Export Deletion - Multiple Sequential Deletions
        
        For any sequence of export files, manual deletion should successfully 
        remove each file in sequence without affecting subsequent deletions.
        
        **Validates: Requirements 5.4**
        """
        # Step 1: Create multiple export files
        exports_dir = Path(temp_root_dir) / "exports"
        created_files = []
        
        for i in range(num_deletions):
            export_file = _create_export_file(exports_dir, export_format.value)
            created_files.append(export_file)
            time.sleep(0.01)
        
        initial_count = _count_files_in_directory(exports_dir / export_format.value)
        assert initial_count >= num_deletions, "All files should be created"
        
        # Step 2: Delete files sequentially
        for i, file_to_delete in enumerate(created_files):
            relative_path = _get_relative_path(file_to_delete, exports_dir)
            
            # Step 3: Perform deletion
            success = cleanup_service.delete_export_file(relative_path)
            
            # Step 4: Validate deletion was successful (Requirements 5.4)
            assert success, f"Deletion {i+1} should succeed"
            
            # Step 5: Validate file was removed (Requirements 5.4)
            assert _validate_file_removed_from_filesystem(file_to_delete), \
                f"File {i+1} should be removed from filesystem"
            
            # Step 6: Validate file count decreased
            current_count = _count_files_in_directory(exports_dir / export_format.value)
            expected_count = initial_count - (i + 1)
            assert current_count == expected_count, \
                f"File count should be {expected_count} after {i+1} deletions"
        
        # Step 7: Validate all files were deleted
        final_count = _count_files_in_directory(exports_dir / export_format.value)
        assert final_count == initial_count - num_deletions, \
            "All deleted files should be removed"
    
    @given(
        export_format=export_format_strategy(),
        file_size=file_size_strategy()
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_manual_deletion_preserves_directory_structure(self, cleanup_service, temp_root_dir, export_format, file_size):
        """
        Property 12: Manual Export Deletion - Directory Structure Preserved
        
        For any export file deletion, the directory structure should remain intact
        even when all files are deleted from a format directory.
        
        **Validates: Requirements 5.4**
        """
        # Step 1: Create an export file
        exports_dir = Path(temp_root_dir) / "exports"
        export_file = _create_export_file(exports_dir, export_format.value, file_size)
        
        format_dir = exports_dir / export_format.value
        
        assert format_dir.exists() and format_dir.is_dir(), \
            "Format directory should exist"
        
        # Step 2: Delete the file
        relative_path = _get_relative_path(export_file, exports_dir)
        success = cleanup_service.delete_export_file(relative_path)
        
        assert success, "Deletion should succeed"
        assert _validate_file_removed_from_filesystem(export_file), \
            "File should be removed"
        
        # Step 3: Validate directory structure is preserved (Requirements 5.4)
        assert format_dir.exists() and format_dir.is_dir(), \
            "Format directory should still exist after file deletion"
        
        assert exports_dir.exists() and exports_dir.is_dir(), \
            "Exports directory should still exist"


# Additional unit tests for specific manual deletion scenarios
class TestManualExportDeletionEdgeCases:
    """Unit tests for specific manual export deletion edge cases."""
    
    def test_delete_nonexistent_file(self, cleanup_service):
        """Test deleting a file that doesn't exist."""
        result = cleanup_service.delete_export_file("pdf/nonexistent-file.pdf")
        
        # Should return False for non-existent file
        assert result is False
    
    def test_delete_with_invalid_path(self, cleanup_service):
        """Test deletion with invalid path characters."""
        invalid_paths = [
            "pdf/../../../etc/passwd",
            "pdf/./../../sensitive.txt",
            "../data/config.json"
        ]
        
        for invalid_path in invalid_paths:
            try:
                result = cleanup_service.delete_export_file(invalid_path)
                # If it returns False, that's acceptable
                assert result is False or result is None
            except CleanupServiceError:
                # Raising an error is also acceptable
                pass
    
    def test_delete_directory_instead_of_file(self, cleanup_service, temp_root_dir):
        """Test attempting to delete a directory instead of a file."""
        # Try to delete a directory
        try:
            result = cleanup_service.delete_export_file("pdf")
            # Should fail or return False
            assert result is False
        except CleanupServiceError as e:
            # Raising an error is acceptable
            assert "not a file" in str(e).lower()
    
    def test_delete_hidden_file(self, cleanup_service, temp_root_dir):
        """Test deleting hidden files (starting with .)."""
        exports_dir = Path(temp_root_dir) / "exports" / "txt"
        exports_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a hidden file
        hidden_file = exports_dir / ".hidden_export.txt"
        with open(hidden_file, 'w') as f:
            f.write("hidden content")
        
        assert hidden_file.exists()
        
        # Attempt to delete hidden file
        relative_path = f"txt/{hidden_file.name}"
        result = cleanup_service.delete_export_file(relative_path)
        
        # Should succeed in deleting hidden file
        assert result is True
        assert not hidden_file.exists()
    
    def test_delete_file_with_special_characters(self, cleanup_service, temp_root_dir):
        """Test deleting files with special characters in filename."""
        exports_dir = Path(temp_root_dir) / "exports" / "txt"
        exports_dir.mkdir(parents=True, exist_ok=True)
        
        # Create file with special characters (but valid for filesystem)
        special_file = exports_dir / "cv-with-special_chars-2024.txt"
        with open(special_file, 'w') as f:
            f.write("content")
        
        assert special_file.exists()
        
        # Delete the file
        relative_path = f"txt/{special_file.name}"
        result = cleanup_service.delete_export_file(relative_path)
        
        assert result is True
        assert not special_file.exists()
    
    def test_delete_large_file(self, cleanup_service, temp_root_dir):
        """Test deleting a large export file."""
        exports_dir = Path(temp_root_dir) / "exports" / "pdf"
        exports_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a larger file (1MB)
        large_file = exports_dir / "large-cv.pdf"
        with open(large_file, 'wb') as f:
            f.write(b'X' * (1024 * 1024))  # 1MB
        
        assert large_file.exists()
        initial_size = large_file.stat().st_size
        assert initial_size >= 1024 * 1024
        
        # Delete the large file
        relative_path = f"pdf/{large_file.name}"
        result = cleanup_service.delete_export_file(relative_path)
        
        assert result is True
        assert not large_file.exists()
    
    def test_delete_file_concurrent_access(self, cleanup_service, temp_root_dir):
        """Test deleting a file that might be accessed concurrently."""
        exports_dir = Path(temp_root_dir) / "exports" / "txt"
        exports_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a file
        test_file = exports_dir / "concurrent-test.txt"
        with open(test_file, 'w') as f:
            f.write("test content")
        
        assert test_file.exists()
        
        # Delete the file
        relative_path = f"txt/{test_file.name}"
        result = cleanup_service.delete_export_file(relative_path)
        
        assert result is True
        assert not test_file.exists()
        
        # Attempting to delete again should return False
        result_second = cleanup_service.delete_export_file(relative_path)
        assert result_second is False
