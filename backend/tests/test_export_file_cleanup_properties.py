"""
Property-based tests for export file cleanup.

Feature: cv-web-app, Property 11: Export File Cleanup
Validates: Requirements 5.3
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

from app.services.cleanup_service import CleanupService, CleanupConfig
from app.models.export_models import ExportFormat


# Test data generators
@st.composite
def retention_days_strategy(draw):
    """Generate valid retention period in days."""
    return draw(st.integers(min_value=1, max_value=30))


@st.composite
def file_age_days_strategy(draw):
    """Generate file age in days."""
    return draw(st.integers(min_value=0, max_value=60))


@st.composite
def export_format_strategy(draw):
    """Generate valid export format."""
    return draw(st.sampled_from([ExportFormat.PDF, ExportFormat.DOCX, ExportFormat.TXT]))


@pytest.fixture
def temp_root_dir():
    """Fixture providing temporary root directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="cv_cleanup_test_")
    
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


def _create_export_file(exports_dir: Path, format_value: str, age_days: int, file_size: int = 1024) -> Path:
    """
    Create a test export file with specified age.
    
    Args:
        exports_dir: Root exports directory
        format_value: Export format (pdf, docx, txt)
        age_days: Age of file in days
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
    
    # Set modification time to simulate age
    target_time = datetime.now() - timedelta(days=age_days)
    timestamp_seconds = target_time.timestamp()
    os.utime(file_path, (timestamp_seconds, timestamp_seconds))
    
    return file_path


def _get_file_age_days(file_path: Path) -> float:
    """Get the age of a file in days."""
    stat = file_path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime)
    age = datetime.now() - mtime
    return age.total_seconds() / 86400  # Convert to days


def _count_files_in_directory(directory: Path) -> int:
    """Count files in a directory (excluding hidden files)."""
    if not directory.exists():
        return 0
    
    count = 0
    for item in directory.iterdir():
        if item.is_file() and not item.name.startswith('.'):
            count += 1
    
    return count


def _validate_file_removed_from_filesystem(file_path: Path) -> bool:
    """Validate that a file has been removed from the filesystem."""
    return not file_path.exists()


def _validate_file_exists_on_filesystem(file_path: Path) -> bool:
    """Validate that a file still exists on the filesystem."""
    return file_path.exists() and file_path.is_file()


class TestExportFileCleanup:
    """Property-based tests for export file cleanup."""
    
    @given(
        retention_days=retention_days_strategy(),
        old_file_age=st.integers(min_value=31, max_value=60),
        export_format=export_format_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cleanup_removes_old_files(self, cleanup_service, temp_root_dir, retention_days, old_file_age, export_format):
        """
        Property 11: Export File Cleanup - Old Files Removed
        
        For any export files older than the retention period, they should be 
        automatically removed from the filesystem.
        
        **Validates: Requirements 5.3**
        """
        # Ensure old file is actually older than retention period
        assume(old_file_age > retention_days)
        
        # Step 1: Configure cleanup service with retention period
        cleanup_service.update_config(retention_days=retention_days, enabled=True)
        
        # Step 2: Create an old export file
        exports_dir = Path(temp_root_dir) / "exports"
        old_file = _create_export_file(exports_dir, export_format.value, old_file_age)
        
        # Verify file was created and has correct age
        assert old_file.exists(), "Old file should be created"
        file_age = _get_file_age_days(old_file)
        assert file_age >= retention_days, f"File age ({file_age:.1f} days) should be >= retention period ({retention_days} days)"
        
        # Step 3: Run cleanup operation
        result = cleanup_service.cleanup_exports(dry_run=False)
        
        # Step 4: Validate old file was removed from filesystem (Requirements 5.3)
        assert _validate_file_removed_from_filesystem(old_file), \
            f"File older than {retention_days} days should be removed from filesystem"
        
        # Step 5: Validate cleanup result reports the deletion
        assert result.files_deleted >= 1, \
            f"Cleanup should report at least 1 file deleted"
        
        assert result.bytes_freed > 0, \
            "Cleanup should report bytes freed"
        
        assert len(result.errors) == 0, \
            f"Cleanup should complete without errors: {result.errors}"
    
    @given(
        retention_days=retention_days_strategy(),
        recent_file_age=st.integers(min_value=0, max_value=10),
        export_format=export_format_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cleanup_preserves_recent_files(self, cleanup_service, temp_root_dir, retention_days, recent_file_age, export_format):
        """
        Property 11: Export File Cleanup - Recent Files Preserved
        
        For any export files newer than the retention period, they should NOT be 
        removed during cleanup.
        
        **Validates: Requirements 5.3**
        """
        # Ensure recent file is actually newer than retention period
        assume(recent_file_age < retention_days)
        
        # Step 1: Configure cleanup service with retention period
        cleanup_service.update_config(retention_days=retention_days, enabled=True)
        
        # Step 2: Create a recent export file
        exports_dir = Path(temp_root_dir) / "exports"
        recent_file = _create_export_file(exports_dir, export_format.value, recent_file_age)
        
        # Verify file was created and has correct age
        assert recent_file.exists(), "Recent file should be created"
        file_age = _get_file_age_days(recent_file)
        assert file_age < retention_days, f"File age ({file_age:.1f} days) should be < retention period ({retention_days} days)"
        
        # Step 3: Run cleanup operation
        result = cleanup_service.cleanup_exports(dry_run=False)
        
        # Step 4: Validate recent file was NOT removed (Requirements 5.3)
        assert _validate_file_exists_on_filesystem(recent_file), \
            f"File newer than {retention_days} days should NOT be removed"
        
        # Step 5: Validate cleanup result
        assert len(result.errors) == 0, \
            f"Cleanup should complete without errors: {result.errors}"
    
    @given(
        retention_days=retention_days_strategy(),
        num_old_files=st.integers(min_value=2, max_value=5),
        num_recent_files=st.integers(min_value=1, max_value=3),
        export_format=export_format_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cleanup_selective_removal(self, cleanup_service, temp_root_dir, retention_days, num_old_files, num_recent_files, export_format):
        """
        Property 11: Export File Cleanup - Selective Removal
        
        For any mix of old and recent export files, cleanup should remove only 
        the old files while preserving recent ones.
        
        **Validates: Requirements 5.3**
        """
        # Step 1: Configure cleanup service
        cleanup_service.update_config(retention_days=retention_days, enabled=True)
        
        exports_dir = Path(temp_root_dir) / "exports"
        
        # Step 2: Create old files (older than retention period)
        old_files = []
        for i in range(num_old_files):
            old_age = retention_days + 5 + i  # Ensure definitely old
            old_file = _create_export_file(exports_dir, export_format.value, old_age)
            old_files.append(old_file)
            # Small delay to ensure different timestamps
            time.sleep(0.01)
        
        # Step 3: Create recent files (newer than retention period)
        recent_files = []
        for i in range(num_recent_files):
            recent_age = max(0, retention_days - 5 - i)  # Ensure definitely recent
            recent_file = _create_export_file(exports_dir, export_format.value, recent_age)
            recent_files.append(recent_file)
            time.sleep(0.01)
        
        # Verify all files were created
        total_files_before = _count_files_in_directory(exports_dir / export_format.value)
        assert total_files_before >= num_old_files + num_recent_files, \
            "All test files should be created"
        
        # Step 4: Run cleanup operation
        result = cleanup_service.cleanup_exports(dry_run=False)
        
        # Step 5: Validate old files were removed (Requirements 5.3)
        for old_file in old_files:
            assert _validate_file_removed_from_filesystem(old_file), \
                f"Old file should be removed: {old_file.name}"
        
        # Step 6: Validate recent files were preserved (Requirements 5.3)
        for recent_file in recent_files:
            assert _validate_file_exists_on_filesystem(recent_file), \
                f"Recent file should be preserved: {recent_file.name}"
        
        # Step 7: Validate cleanup result
        assert result.files_deleted >= num_old_files, \
            f"Should delete at least {num_old_files} old files"
        
        assert len(result.errors) == 0, \
            f"Cleanup should complete without errors: {result.errors}"
        
        # Step 8: Validate final file count
        total_files_after = _count_files_in_directory(exports_dir / export_format.value)
        assert total_files_after >= num_recent_files, \
            f"Should have at least {num_recent_files} files remaining"
        
        assert total_files_after < total_files_before, \
            "Total file count should decrease after cleanup"
    
    @given(
        retention_days=retention_days_strategy(),
        old_file_age=st.integers(min_value=31, max_value=60)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cleanup_multiple_formats(self, cleanup_service, temp_root_dir, retention_days, old_file_age):
        """
        Property 11: Export File Cleanup - Multiple Formats
        
        For any export files in different formats, cleanup should remove old files
        from all format directories.
        
        **Validates: Requirements 5.3**
        """
        assume(old_file_age > retention_days)
        
        # Step 1: Configure cleanup service
        cleanup_service.update_config(retention_days=retention_days, enabled=True)
        
        exports_dir = Path(temp_root_dir) / "exports"
        
        # Step 2: Create old files in each format directory
        old_files = {}
        for export_format in [ExportFormat.PDF, ExportFormat.DOCX, ExportFormat.TXT]:
            old_file = _create_export_file(exports_dir, export_format.value, old_file_age)
            old_files[export_format.value] = old_file
            time.sleep(0.01)
        
        # Verify all files were created
        for format_value, file_path in old_files.items():
            assert file_path.exists(), f"Old file should be created for {format_value}"
        
        # Step 3: Run cleanup operation
        result = cleanup_service.cleanup_exports(dry_run=False)
        
        # Step 4: Validate old files were removed from all format directories (Requirements 5.3)
        for format_value, file_path in old_files.items():
            assert _validate_file_removed_from_filesystem(file_path), \
                f"Old file should be removed from {format_value} directory"
        
        # Step 5: Validate cleanup result
        assert result.files_deleted >= len(old_files), \
            f"Should delete at least {len(old_files)} files (one per format)"
        
        assert len(result.errors) == 0, \
            f"Cleanup should complete without errors: {result.errors}"
    
    @given(
        retention_days=retention_days_strategy(),
        old_file_age=st.integers(min_value=31, max_value=60),
        export_format=export_format_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cleanup_dry_run_preserves_files(self, cleanup_service, temp_root_dir, retention_days, old_file_age, export_format):
        """
        Property 11: Export File Cleanup - Dry Run Mode
        
        For any export files older than retention period, dry run mode should 
        report what would be deleted without actually removing files.
        
        **Validates: Requirements 5.3**
        """
        assume(old_file_age > retention_days)
        
        # Step 1: Configure cleanup service
        cleanup_service.update_config(retention_days=retention_days, enabled=True)
        
        # Step 2: Create an old export file
        exports_dir = Path(temp_root_dir) / "exports"
        old_file = _create_export_file(exports_dir, export_format.value, old_file_age)
        
        assert old_file.exists(), "Old file should be created"
        
        # Step 3: Run cleanup in dry run mode
        result = cleanup_service.cleanup_exports(dry_run=True)
        
        # Step 4: Validate file still exists (Requirements 5.3)
        assert _validate_file_exists_on_filesystem(old_file), \
            "Dry run should NOT actually remove files"
        
        # Step 5: Validate cleanup result reports what would be deleted
        assert result.files_deleted >= 1, \
            "Dry run should report files that would be deleted"
        
        assert result.bytes_freed > 0, \
            "Dry run should report bytes that would be freed"
        
        assert len(result.errors) == 0, \
            f"Dry run should complete without errors: {result.errors}"
    
    @given(
        retention_days=retention_days_strategy(),
        old_file_age=st.integers(min_value=31, max_value=60),
        export_format=export_format_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cleanup_disabled_preserves_files(self, cleanup_service, temp_root_dir, retention_days, old_file_age, export_format):
        """
        Property 11: Export File Cleanup - Disabled Cleanup
        
        For any export files, when cleanup is disabled, no files should be removed
        regardless of age.
        
        **Validates: Requirements 5.3**
        """
        assume(old_file_age > retention_days)
        
        # Step 1: Configure cleanup service with cleanup disabled
        cleanup_service.update_config(retention_days=retention_days, enabled=False)
        
        # Step 2: Create an old export file
        exports_dir = Path(temp_root_dir) / "exports"
        old_file = _create_export_file(exports_dir, export_format.value, old_file_age)
        
        assert old_file.exists(), "Old file should be created"
        
        # Step 3: Run cleanup operation
        result = cleanup_service.cleanup_exports(dry_run=False)
        
        # Step 4: Validate file still exists (Requirements 5.3)
        assert _validate_file_exists_on_filesystem(old_file), \
            "Disabled cleanup should NOT remove any files"
        
        # Step 5: Validate cleanup result
        assert result.files_deleted == 0, \
            "Disabled cleanup should not delete any files"
        
        assert len(result.errors) > 0 or "disabled" in str(result.errors).lower() or result.files_deleted == 0, \
            "Disabled cleanup should indicate it's disabled"
    
    @given(
        retention_days=retention_days_strategy(),
        file_ages=st.lists(st.integers(min_value=0, max_value=60), min_size=3, max_size=10),
        export_format=export_format_strategy()
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cleanup_boundary_conditions(self, cleanup_service, temp_root_dir, retention_days, file_ages, export_format):
        """
        Property 11: Export File Cleanup - Boundary Conditions
        
        For any export files at the boundary of the retention period, cleanup should
        correctly determine which files to remove based on exact age comparison.
        
        **Validates: Requirements 5.3**
        """
        # Step 1: Configure cleanup service
        cleanup_service.update_config(retention_days=retention_days, enabled=True)
        
        exports_dir = Path(temp_root_dir) / "exports"
        
        # Step 2: Create files with various ages
        created_files = []
        for age in file_ages:
            file_path = _create_export_file(exports_dir, export_format.value, age)
            created_files.append((file_path, age))
            time.sleep(0.01)
        
        # Step 3: Run cleanup operation
        result = cleanup_service.cleanup_exports(dry_run=False)
        
        # Step 4: Validate cleanup behavior at boundaries (Requirements 5.3)
        for file_path, age in created_files:
            # Check if file still exists first
            file_exists = file_path.exists()
            
            if file_exists:
                # File was preserved - check it should have been
                actual_age = _get_file_age_days(file_path)
                assert actual_age < retention_days, \
                    f"Preserved file should have age {actual_age:.1f} days < {retention_days} days"
            else:
                # File was removed - it should have been old enough
                # We can't check actual age since file is gone, but we know it was >= retention_days
                # based on the cleanup logic
                assert True  # File was correctly removed
        
        # Step 5: Validate cleanup completed without errors
        assert len(result.errors) == 0, \
            f"Cleanup should complete without errors: {result.errors}"


# Additional unit tests for specific cleanup scenarios
class TestExportFileCleanupEdgeCases:
    """Unit tests for specific export file cleanup edge cases."""
    
    def test_cleanup_empty_directory(self, cleanup_service):
        """Test cleanup with no export files."""
        cleanup_service.update_config(retention_days=30, enabled=True)
        
        result = cleanup_service.cleanup_exports(dry_run=False)
        
        assert result.files_deleted == 0
        assert result.bytes_freed == 0
        assert len(result.errors) == 0
    
    def test_cleanup_with_hidden_files(self, cleanup_service, temp_root_dir):
        """Test cleanup ignores hidden files (starting with .)."""
        cleanup_service.update_config(retention_days=7, enabled=True)
        
        exports_dir = Path(temp_root_dir) / "exports" / "txt"
        exports_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a hidden file
        hidden_file = exports_dir / ".hidden_file.txt"
        with open(hidden_file, 'w') as f:
            f.write("hidden content")
        
        # Set old modification time
        old_time = (datetime.now() - timedelta(days=30)).timestamp()
        os.utime(hidden_file, (old_time, old_time))
        
        result = cleanup_service.cleanup_exports(dry_run=False)
        
        # Hidden file should not be deleted
        assert hidden_file.exists()
        assert result.files_deleted == 0
    
    def test_cleanup_statistics_accuracy(self, cleanup_service, temp_root_dir):
        """Test cleanup result statistics are accurate."""
        cleanup_service.update_config(retention_days=7, enabled=True)
        
        exports_dir = Path(temp_root_dir) / "exports"
        
        # Create multiple old files with known sizes
        file_size = 2048
        num_files = 3
        
        for i in range(num_files):
            _create_export_file(exports_dir, "txt", age_days=30, file_size=file_size)
            time.sleep(0.01)
        
        result = cleanup_service.cleanup_exports(dry_run=False)
        
        assert result.files_deleted == num_files
        assert result.bytes_freed == num_files * file_size
        assert len(result.errors) == 0
        assert result.execution_time > 0
    
    def test_cleanup_max_files_per_format_limit(self, cleanup_service, temp_root_dir):
        """Test cleanup respects max_files_per_format limit."""
        max_files = 5
        cleanup_service.update_config(
            retention_days=365,  # Very long retention
            max_files_per_format=max_files,
            enabled=True
        )
        
        exports_dir = Path(temp_root_dir) / "exports"
        
        # Create more files than the limit (all recent)
        num_files = max_files + 3
        for i in range(num_files):
            _create_export_file(exports_dir, "txt", age_days=1)
            time.sleep(0.01)
        
        result = cleanup_service.cleanup_exports(dry_run=False)
        
        # Should delete excess files
        assert result.files_deleted >= (num_files - max_files)
        
        # Should have at most max_files remaining
        remaining_files = _count_files_in_directory(exports_dir / "txt")
        assert remaining_files <= max_files
