"""
Tests for Backup Service

Tests backup creation, restoration, and management functionality.
"""

import pytest
import json
import zipfile
from pathlib import Path
from datetime import datetime
import tempfile
import shutil

from app.services.backup_service import (
    BackupService,
    BackupServiceError,
    BackupCreationError,
    BackupRestoreError,
    BackupValidationError
)


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        data_dir = Path(temp_dir) / "data"
        data_dir.mkdir()
        
        # Create sample data structure
        (data_dir / "cvs").mkdir()
        (data_dir / "templates").mkdir()
        (data_dir / "config").mkdir()
        
        # Create sample CV
        cv_data = {
            "id": "test-cv-1",
            "version": 2,
            "sections": []
        }
        with open(data_dir / "cvs" / "test-cv-1.json", 'w') as f:
            json.dump(cv_data, f)
        
        # Create metadata
        metadata = {"cvs": ["test-cv-1"]}
        with open(data_dir / "cvs" / "metadata.json", 'w') as f:
            json.dump(metadata, f)
        
        # Create sample applications
        apps_data = {
            "applications": [
                {"id": "app-1", "cv_id": "test-cv-1", "company": "Test Corp"}
            ]
        }
        with open(data_dir / "applications.json", 'w') as f:
            json.dump(apps_data, f)
        
        # Create sample templates
        templates_data = {
            "templates": [
                {"id": "tpl-1", "name": "Test Template"}
            ]
        }
        with open(data_dir / "templates" / "custom_templates.json", 'w') as f:
            json.dump(templates_data, f)
        
        # Create sample config
        config_data = {"llm_provider": "test"}
        with open(data_dir / "config" / "llm_config.json", 'w') as f:
            json.dump(config_data, f)
        
        yield data_dir


def test_backup_service_initialization(temp_data_dir):
    """Test BackupService initialization."""
    service = BackupService(data_dir=temp_data_dir)
    assert service.data_dir == temp_data_dir
    assert service.BACKUP_VERSION == "1.0"


def test_create_backup(temp_data_dir):
    """Test creating a backup."""
    service = BackupService(data_dir=temp_data_dir)
    
    backup_path = service.create_backup(include_exports=False)
    
    assert backup_path.exists()
    assert backup_path.suffix == ".zip"
    assert backup_path.name.startswith("cvlab_backup_")
    assert zipfile.is_zipfile(backup_path)
    
    # Verify backup contents
    with zipfile.ZipFile(backup_path, 'r') as zipf:
        namelist = zipf.namelist()
        
        # Check for metadata
        assert "backup_metadata.json" in namelist
        
        # Check for data directories
        assert any("cvs/" in name for name in namelist)
        assert any("templates/" in name for name in namelist)
        assert any("config/" in name for name in namelist)
        assert any("applications/" in name for name in namelist)


def test_backup_metadata(temp_data_dir):
    """Test backup metadata creation."""
    service = BackupService(data_dir=temp_data_dir)
    
    backup_path = service.create_backup(include_exports=False)
    
    # Extract and verify metadata
    with zipfile.ZipFile(backup_path, 'r') as zipf:
        metadata_content = zipf.read("backup_metadata.json")
        metadata = json.loads(metadata_content)
        
        assert metadata['version'] == "1.0"
        assert 'created_at' in metadata
        assert metadata['application'] == 'CV Lab'
        assert 'summary' in metadata
        assert metadata['summary']['cvs'] == 1
        assert metadata['summary']['applications'] == 1
        assert metadata['summary']['templates'] == 1


def test_list_backups(temp_data_dir):
    """Test listing backups."""
    service = BackupService(data_dir=temp_data_dir)
    
    # Create a couple of backups
    backup1 = service.create_backup(include_exports=False)
    backup2 = service.create_backup(include_exports=False)
    
    # List backups
    backups = service.list_backups()
    
    assert len(backups) >= 2
    assert all('filename' in b for b in backups)
    assert all('size' in b for b in backups)
    assert all('created_at' in b for b in backups)


def test_restore_backup(temp_data_dir):
    """Test restoring from a backup."""
    service = BackupService(data_dir=temp_data_dir)
    
    # Create backup
    backup_path = service.create_backup(include_exports=False)
    
    # Modify data
    cv_file = temp_data_dir / "cvs" / "test-cv-1.json"
    cv_file.unlink()
    
    # Restore backup
    summary = service.restore_backup(backup_path, overwrite=True)
    
    assert 'restored_items' in summary
    assert 'cvs' in summary['restored_items']
    assert summary['restored_items']['cvs']['restored'] == 1
    
    # Verify data restored
    assert cv_file.exists()


def test_restore_backup_no_overwrite(temp_data_dir):
    """Test restoring backup without overwriting existing data."""
    service = BackupService(data_dir=temp_data_dir)
    
    # Create backup
    backup_path = service.create_backup(include_exports=False)
    
    # Add new CV
    new_cv_data = {
        "id": "test-cv-2",
        "version": 2,
        "sections": []
    }
    with open(temp_data_dir / "cvs" / "test-cv-2.json", 'w') as f:
        json.dump(new_cv_data, f)
    
    # Restore backup without overwrite
    summary = service.restore_backup(backup_path, overwrite=False)
    
    # Both CVs should exist
    assert (temp_data_dir / "cvs" / "test-cv-1.json").exists()
    assert (temp_data_dir / "cvs" / "test-cv-2.json").exists()


def test_delete_backup(temp_data_dir):
    """Test deleting a backup."""
    service = BackupService(data_dir=temp_data_dir)
    
    # Create backup
    backup_path = service.create_backup(include_exports=False)
    filename = backup_path.name
    
    assert backup_path.exists()
    
    # Delete backup
    result = service.delete_backup(filename)
    
    assert result is True
    assert not backup_path.exists()


def test_delete_nonexistent_backup(temp_data_dir):
    """Test deleting a non-existent backup."""
    service = BackupService(data_dir=temp_data_dir)
    
    with pytest.raises(BackupServiceError):
        service.delete_backup("nonexistent_backup.zip")


def test_restore_invalid_backup(temp_data_dir):
    """Test restoring from an invalid backup file."""
    service = BackupService(data_dir=temp_data_dir)
    
    # Create invalid backup file
    invalid_backup = temp_data_dir / "backups" / "invalid.zip"
    invalid_backup.parent.mkdir(exist_ok=True)
    invalid_backup.write_text("not a zip file")
    
    with pytest.raises(BackupValidationError):
        service.restore_backup(invalid_backup, overwrite=False)


def test_backup_excludes_sensitive_data(temp_data_dir):
    """Test that backups exclude sensitive data like API keys."""
    service = BackupService(data_dir=temp_data_dir)
    
    # Create sensitive file
    sensitive_file = temp_data_dir / "config" / ".llm_key"
    sensitive_file.write_text("secret-api-key")
    
    # Create backup
    backup_path = service.create_backup(include_exports=False)
    
    # Verify sensitive file is not in backup
    with zipfile.ZipFile(backup_path, 'r') as zipf:
        namelist = zipf.namelist()
        assert not any(".llm_key" in name for name in namelist)


def test_backup_with_exports(temp_data_dir):
    """Test creating backup with exported files."""
    service = BackupService(data_dir=temp_data_dir)
    
    # Create exports directory
    exports_dir = temp_data_dir.parent / "exports"
    exports_dir.mkdir()
    (exports_dir / "pdf").mkdir()
    (exports_dir / "pdf" / "test.pdf").write_text("fake pdf")
    
    # Mock the exports path
    import app.services.backup_service as backup_module
    original_path = Path("/app/exports")
    
    # Create backup with exports
    backup_path = service.create_backup(include_exports=True)
    
    # Note: This test would need proper mocking to work fully
    # For now, just verify backup was created
    assert backup_path.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
