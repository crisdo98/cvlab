"""
Backup Service

Provides functionality for creating and restoring full system backups.
Handles exporting all user data (CVs, applications, templates, config) into
a single zip file and importing from backup archives.
"""

import json
import zipfile
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class BackupServiceError(Exception):
    """Base exception for backup service operations."""
    pass


class BackupCreationError(BackupServiceError):
    """Raised when backup creation fails."""
    pass


class BackupRestoreError(BackupServiceError):
    """Raised when backup restoration fails."""
    pass


class BackupValidationError(BackupServiceError):
    """Raised when backup validation fails."""
    pass


class BackupService:
    """
    Service for creating and restoring full system backups.
    
    Handles packaging all user data into a single zip archive and
    restoring from backup archives with validation.
    """
    
    # Backup format version for compatibility checking
    BACKUP_VERSION = "1.0"
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize BackupService.
        
        Args:
            data_dir: Path to data directory (defaults to /app/data)
        """
        self.data_dir = data_dir or Path("/app/data")
        
        # Ensure data directory exists
        if not self.data_dir.exists():
            raise BackupServiceError(f"Data directory not found: {self.data_dir}")
    
    def create_backup(self, include_exports: bool = False) -> Path:
        """
        Create a full backup of all user data.
        
        Args:
            include_exports: Whether to include exported files (PDF, DOCX, TXT)
            
        Returns:
            Path to created backup zip file
            
        Raises:
            BackupCreationError: If backup creation fails
        """
        try:
            logger.info("Starting backup creation")
            
            # Create temporary directory for backup staging
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                backup_root = temp_path / "cvlab_backup"
                backup_root.mkdir()
                
                # Create backup metadata
                metadata = self._create_backup_metadata()
                
                # Copy data directories
                self._backup_cvs(backup_root)
                self._backup_applications(backup_root)
                self._backup_templates(backup_root)
                self._backup_config(backup_root)
                
                if include_exports:
                    self._backup_exports(backup_root)
                
                # Write metadata
                metadata_file = backup_root / "backup_metadata.json"
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, default=str)
                
                # Create zip archive
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"cvlab_backup_{timestamp}.zip"
                backup_path = self.data_dir / "backups" / backup_filename
                
                # Ensure backups directory exists
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Create zip file
                with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file_path in backup_root.rglob('*'):
                        if file_path.is_file():
                            arcname = file_path.relative_to(backup_root)
                            zipf.write(file_path, arcname)
                
                logger.info(f"Backup created successfully: {backup_path}")
                return backup_path
                
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise BackupCreationError(f"Failed to create backup: {e}")
    
    def restore_backup(self, backup_path: Path, overwrite: bool = False) -> Dict[str, Any]:
        """
        Restore data from a backup archive.
        
        Args:
            backup_path: Path to backup zip file
            overwrite: Whether to overwrite existing data
            
        Returns:
            Dictionary with restoration summary
            
        Raises:
            BackupRestoreError: If restoration fails
            BackupValidationError: If backup validation fails
        """
        try:
            logger.info(f"Starting backup restoration from: {backup_path}")
            
            # Validate backup file
            if not backup_path.exists():
                raise BackupValidationError(f"Backup file not found: {backup_path}")
            
            if not zipfile.is_zipfile(backup_path):
                raise BackupValidationError(f"Invalid backup file: not a zip archive")
            
            # Create temporary directory for extraction
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                extract_path = temp_path / "extracted"
                extract_path.mkdir()
                
                # Extract backup
                with zipfile.ZipFile(backup_path, 'r') as zipf:
                    zipf.extractall(extract_path)
                
                # Validate backup structure and metadata
                metadata = self._validate_backup(extract_path)
                
                # Create backup of current data if overwriting
                if overwrite:
                    self._create_pre_restore_backup()
                
                # Restore data
                summary = {
                    'backup_version': metadata.get('version'),
                    'backup_date': metadata.get('created_at'),
                    'restored_items': {}
                }
                
                summary['restored_items']['cvs'] = self._restore_cvs(extract_path, overwrite)
                summary['restored_items']['applications'] = self._restore_applications(extract_path, overwrite)
                summary['restored_items']['templates'] = self._restore_templates(extract_path, overwrite)
                summary['restored_items']['config'] = self._restore_config(extract_path, overwrite)
                
                # Restore exports if present
                if (extract_path / "exports").exists():
                    summary['restored_items']['exports'] = self._restore_exports(extract_path, overwrite)
                
                logger.info(f"Backup restored successfully: {summary}")
                return summary
                
        except (BackupValidationError, BackupRestoreError):
            raise
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            raise BackupRestoreError(f"Failed to restore backup: {e}")
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """
        List all available backups.
        
        Returns:
            List of backup information dictionaries
        """
        try:
            backups_dir = self.data_dir / "backups"
            if not backups_dir.exists():
                return []
            
            backups = []
            for backup_file in backups_dir.glob("cvlab_backup_*.zip"):
                try:
                    # Extract metadata without full extraction
                    with zipfile.ZipFile(backup_file, 'r') as zipf:
                        if 'backup_metadata.json' in zipf.namelist():
                            metadata_content = zipf.read('backup_metadata.json')
                            metadata = json.loads(metadata_content)
                            
                            backups.append({
                                'filename': backup_file.name,
                                'path': str(backup_file),
                                'size': backup_file.stat().st_size,
                                'created_at': metadata.get('created_at'),
                                'version': metadata.get('version'),
                                'summary': metadata.get('summary')
                            })
                except Exception as e:
                    logger.warning(f"Failed to read backup metadata from {backup_file}: {e}")
                    # Include file anyway with basic info
                    backups.append({
                        'filename': backup_file.name,
                        'path': str(backup_file),
                        'size': backup_file.stat().st_size,
                        'created_at': None,
                        'version': None,
                        'summary': None
                    })
            
            # Sort by creation date (newest first)
            backups.sort(key=lambda x: x.get('created_at') or '', reverse=True)
            return backups
            
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []
    
    def delete_backup(self, backup_filename: str) -> bool:
        """
        Delete a backup file.
        
        Args:
            backup_filename: Name of backup file to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            BackupServiceError: If deletion fails
        """
        try:
            backup_path = self.data_dir / "backups" / backup_filename
            
            if not backup_path.exists():
                raise BackupServiceError(f"Backup not found: {backup_filename}")
            
            backup_path.unlink()
            logger.info(f"Deleted backup: {backup_filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete backup: {e}")
            raise BackupServiceError(f"Failed to delete backup: {e}")
    
    # Private helper methods
    
    def _create_backup_metadata(self) -> Dict[str, Any]:
        """Create comprehensive backup metadata."""
        # Count CVs
        cvs_count = len(list((self.data_dir / "cvs").glob("*.json"))) - 1  # Exclude metadata.json
        
        # Count historical CV backups
        historical_cvs_count = 0
        for backup_dir_name in ["cvs_backup", "cvs_backup_before_v2_fix"]:
            backup_dir = self.data_dir / backup_dir_name
            if backup_dir.exists():
                historical_cvs_count += len(list(backup_dir.glob("*.json"))) - 1  # Exclude metadata.json
        
        # Count applications
        apps_file = self.data_dir / "applications.json"
        apps_count = 0
        if apps_file.exists():
            with open(apps_file, 'r') as f:
                apps_data = json.load(f)
                apps_count = len(apps_data.get('applications', []))
        
        # Count templates
        templates_file = self.data_dir / "templates" / "custom_templates.json"
        templates_count = 0
        if templates_file.exists():
            with open(templates_file, 'r') as f:
                templates_data = json.load(f)
                templates_count = len(templates_data.get('templates', []))
        
        # Count config files
        config_files_count = 0
        config_dir = self.data_dir / "config"
        if config_dir.exists():
            config_files_count += len([f for f in config_dir.glob("*") if f.is_file() and f.name != ".llm_key"])
        
        # Count root-level config files
        root_config_files = ["cleanup_config.json"]
        for config_file_name in root_config_files:
            if (self.data_dir / config_file_name).exists():
                config_files_count += 1
        
        # Count exports (if included)
        exports_count = 0
        exports_dir = Path("/app/exports")
        if exports_dir.exists():
            for export_type in ["pdf", "docx", "txt"]:
                type_dir = exports_dir / export_type
                if type_dir.exists():
                    exports_count += len(list(type_dir.glob("*")))
        
        return {
            'version': self.BACKUP_VERSION,
            'created_at': datetime.now().isoformat(),
            'application': 'CV Lab',
            'summary': {
                'cvs': cvs_count,
                'historical_cvs': historical_cvs_count,
                'applications': apps_count,
                'templates': templates_count,
                'config_files': config_files_count,
                'exports': exports_count
            },
            'included_data': {
                'cvs': True,
                'historical_cv_backups': historical_cvs_count > 0,
                'applications': apps_count > 0,
                'templates': templates_count > 0,
                'config_files': config_files_count > 0,
                'exports': exports_count > 0
            }
        }
    
    def _backup_cvs(self, backup_root: Path):
        """Backup CV data including all CV directories."""
        # Main CVs directory
        cvs_dir = self.data_dir / "cvs"
        if cvs_dir.exists():
            dest_dir = backup_root / "cvs"
            shutil.copytree(cvs_dir, dest_dir)
            logger.info(f"Backed up CVs from {cvs_dir}")
        
        # Backup CV backup directories (historical data)
        for backup_dir_name in ["cvs_backup", "cvs_backup_before_v2_fix"]:
            backup_dir = self.data_dir / backup_dir_name
            if backup_dir.exists():
                dest_dir = backup_root / backup_dir_name
                shutil.copytree(backup_dir, dest_dir)
                logger.info(f"Backed up historical CVs from {backup_dir}")
    
    def _backup_applications(self, backup_root: Path):
        """Backup application tracking data."""
        apps_file = self.data_dir / "applications.json"
        history_file = self.data_dir / "application_history.json"
        
        dest_dir = backup_root / "applications"
        dest_dir.mkdir()
        
        if apps_file.exists():
            shutil.copy2(apps_file, dest_dir / "applications.json")
        
        if history_file.exists():
            shutil.copy2(history_file, dest_dir / "application_history.json")
        
        logger.info("Backed up application data")
    
    def _backup_templates(self, backup_root: Path):
        """Backup custom templates."""
        templates_dir = self.data_dir / "templates"
        if templates_dir.exists():
            dest_dir = backup_root / "templates"
            shutil.copytree(templates_dir, dest_dir)
            logger.info("Backed up templates")
    
    def _backup_config(self, backup_root: Path):
        """Backup all configuration files and settings (excluding sensitive keys)."""
        config_dir = self.data_dir / "config"
        dest_dir = backup_root / "config"
        dest_dir.mkdir()
        
        # Copy all config files except sensitive ones
        if config_dir.exists():
            for config_file in config_dir.glob("*"):
                if config_file.is_file() and config_file.name not in [".llm_key"]:
                    shutil.copy2(config_file, dest_dir / config_file.name)
        
        # Copy other configuration files from data root
        config_files = [
            "cleanup_config.json",
            # Add other config files as they're discovered
        ]
        
        for config_file_name in config_files:
            config_file = self.data_dir / config_file_name
            if config_file.exists():
                shutil.copy2(config_file, dest_dir / config_file_name)
        
        logger.info("Backed up all configuration files (excluding sensitive keys)")
    
    def _backup_exports(self, backup_root: Path):
        """Backup exported files."""
        exports_dir = Path("/app/exports")
        if exports_dir.exists():
            dest_dir = backup_root / "exports"
            shutil.copytree(exports_dir, dest_dir)
            logger.info("Backed up exports")
    
    def _validate_backup(self, extract_path: Path) -> Dict[str, Any]:
        """Validate backup structure and metadata."""
        metadata_file = extract_path / "backup_metadata.json"
        
        if not metadata_file.exists():
            raise BackupValidationError("Backup metadata not found")
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        # Check version compatibility
        backup_version = metadata.get('version')
        if not backup_version:
            raise BackupValidationError("Backup version not specified")
        
        # For now, only support same version
        if backup_version != self.BACKUP_VERSION:
            logger.warning(f"Backup version mismatch: {backup_version} vs {self.BACKUP_VERSION}")
        
        return metadata
    
    def _create_pre_restore_backup(self):
        """Create a backup before restoring to allow rollback."""
        try:
            logger.info("Creating pre-restore backup")
            backup_path = self.create_backup(include_exports=False)
            
            # Rename to indicate it's a pre-restore backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pre_restore_path = backup_path.parent / f"pre_restore_{timestamp}.zip"
            backup_path.rename(pre_restore_path)
            
            logger.info(f"Pre-restore backup created: {pre_restore_path}")
        except Exception as e:
            logger.warning(f"Failed to create pre-restore backup: {e}")
    
    def _restore_cvs(self, extract_path: Path, overwrite: bool) -> Dict[str, int]:
        """Restore CV data including historical backups."""
        restored = 0
        skipped = 0
        
        # Restore main CVs directory
        source_dir = extract_path / "cvs"
        dest_dir = self.data_dir / "cvs"
        
        if source_dir.exists():
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            for cv_file in source_dir.glob("*.json"):
                dest_file = dest_dir / cv_file.name
                
                if dest_file.exists() and not overwrite and cv_file.name != "metadata.json":
                    skipped += 1
                    continue
                
                shutil.copy2(cv_file, dest_file)
                if cv_file.name != "metadata.json":
                    restored += 1
        
        # Restore historical CV backup directories
        for backup_dir_name in ["cvs_backup", "cvs_backup_before_v2_fix"]:
            source_backup_dir = extract_path / backup_dir_name
            dest_backup_dir = self.data_dir / backup_dir_name
            
            if source_backup_dir.exists():
                if dest_backup_dir.exists() and not overwrite:
                    # Merge historical backups
                    for cv_file in source_backup_dir.glob("*.json"):
                        dest_file = dest_backup_dir / cv_file.name
                        if not dest_file.exists():
                            shutil.copy2(cv_file, dest_file)
                            if cv_file.name != "metadata.json":
                                restored += 1
                        else:
                            skipped += 1
                else:
                    # Copy entire directory
                    if dest_backup_dir.exists():
                        shutil.rmtree(dest_backup_dir)
                    shutil.copytree(source_backup_dir, dest_backup_dir)
                    # Count files
                    cv_files = len([f for f in source_backup_dir.glob("*.json") if f.name != "metadata.json"])
                    restored += cv_files
        
        logger.info(f"Restored {restored} CVs, skipped {skipped}")
        return {'restored': restored, 'skipped': skipped}
    
    def _restore_applications(self, extract_path: Path, overwrite: bool) -> Dict[str, int]:
        """Restore application tracking data."""
        source_dir = extract_path / "applications"
        
        if not source_dir.exists():
            return {'restored': 0, 'skipped': 0}
        
        restored = 0
        skipped = 0
        
        for app_file in ["applications.json", "application_history.json"]:
            source_file = source_dir / app_file
            dest_file = self.data_dir / app_file
            
            if source_file.exists():
                if dest_file.exists() and not overwrite:
                    # Merge application data instead of overwriting
                    self._merge_applications(source_file, dest_file)
                    restored += 1
                else:
                    shutil.copy2(source_file, dest_file)
                    restored += 1
        
        logger.info(f"Restored application data")
        return {'restored': restored, 'skipped': skipped}
    
    def _restore_templates(self, extract_path: Path, overwrite: bool) -> Dict[str, int]:
        """Restore custom templates."""
        source_dir = extract_path / "templates"
        dest_dir = self.data_dir / "templates"
        
        if not source_dir.exists():
            return {'restored': 0, 'skipped': 0}
        
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        restored = 0
        skipped = 0
        
        # Restore all template files
        for template_file in source_dir.glob("*"):
            if template_file.is_file():
                dest_file = dest_dir / template_file.name
                
                if dest_file.exists() and not overwrite:
                    if template_file.name == "custom_templates.json":
                        # Merge templates
                        self._merge_templates(template_file, dest_file)
                        restored += 1
                    else:
                        skipped += 1
                else:
                    shutil.copy2(template_file, dest_file)
                    restored += 1
        
        logger.info(f"Restored {restored} template files, skipped {skipped}")
        return {'restored': restored, 'skipped': skipped}
    
    def _restore_config(self, extract_path: Path, overwrite: bool) -> Dict[str, int]:
        """Restore all configuration files and settings."""
        source_dir = extract_path / "config"
        dest_config_dir = self.data_dir / "config"
        
        if not source_dir.exists():
            return {'restored': 0, 'skipped': 0}
        
        dest_config_dir.mkdir(parents=True, exist_ok=True)
        
        restored = 0
        skipped = 0
        
        # Restore all config files
        for config_file in source_dir.glob("*"):
            if config_file.is_file():
                # Determine destination
                if config_file.name in ["cleanup_config.json"]:
                    # Root-level config files
                    dest_file = self.data_dir / config_file.name
                else:
                    # Config directory files
                    dest_file = dest_config_dir / config_file.name
                
                if dest_file.exists() and not overwrite:
                    skipped += 1
                    continue
                
                shutil.copy2(config_file, dest_file)
                restored += 1
        
        logger.info(f"Restored {restored} config files, skipped {skipped}")
        return {'restored': restored, 'skipped': skipped}
    
    def _restore_exports(self, extract_path: Path, overwrite: bool) -> Dict[str, int]:
        """Restore exported files."""
        source_dir = extract_path / "exports"
        dest_dir = Path("/app/exports")
        
        if not source_dir.exists():
            return {'restored': 0, 'skipped': 0}
        
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        restored = 0
        
        for export_type in ["pdf", "docx", "txt"]:
            source_type_dir = source_dir / export_type
            if source_type_dir.exists():
                dest_type_dir = dest_dir / export_type
                dest_type_dir.mkdir(exist_ok=True)
                
                for export_file in source_type_dir.glob("*"):
                    if export_file.is_file():
                        dest_file = dest_type_dir / export_file.name
                        if not dest_file.exists() or overwrite:
                            shutil.copy2(export_file, dest_file)
                            restored += 1
        
        logger.info(f"Restored {restored} export files")
        return {'restored': restored, 'skipped': 0}
    
    def _merge_applications(self, source_file: Path, dest_file: Path):
        """Merge application data from backup with existing data."""
        try:
            with open(source_file, 'r') as f:
                source_data = json.load(f)
            
            with open(dest_file, 'r') as f:
                dest_data = json.load(f)
            
            # Merge applications by ID
            existing_ids = {app['id'] for app in dest_data.get('applications', [])}
            new_apps = [app for app in source_data.get('applications', []) 
                       if app['id'] not in existing_ids]
            
            dest_data.setdefault('applications', []).extend(new_apps)
            
            with open(dest_file, 'w') as f:
                json.dump(dest_data, f, indent=2)
            
            logger.info(f"Merged {len(new_apps)} new applications")
            
        except Exception as e:
            logger.error(f"Failed to merge applications: {e}")
            # Fall back to copying
            shutil.copy2(source_file, dest_file)
    
    def _merge_templates(self, source_file: Path, dest_file: Path):
        """Merge template data from backup with existing data."""
        try:
            with open(source_file, 'r') as f:
                source_data = json.load(f)
            
            with open(dest_file, 'r') as f:
                dest_data = json.load(f)
            
            # Merge templates by ID
            existing_ids = {tpl['id'] for tpl in dest_data.get('templates', [])}
            new_templates = [tpl for tpl in source_data.get('templates', []) 
                           if tpl['id'] not in existing_ids]
            
            dest_data.setdefault('templates', []).extend(new_templates)
            
            with open(dest_file, 'w') as f:
                json.dump(dest_data, f, indent=2)
            
            logger.info(f"Merged {len(new_templates)} new templates")
            
        except Exception as e:
            logger.error(f"Failed to merge templates: {e}")
            # Fall back to copying
            shutil.copy2(source_file, dest_file)
