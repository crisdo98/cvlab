"""
Cleanup Service

Service for managing export file cleanup operations.
Provides configurable retention period settings and scheduled cleanup tasks
to maintain export directory hygiene and prevent disk space issues.
"""

import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import asyncio
from dataclasses import dataclass

from ..models.export_models import ExportFormat

logger = logging.getLogger(__name__)


@dataclass
class CleanupConfig:
    """Configuration for cleanup operations."""
    retention_days: int = 30
    max_files_per_format: int = 100
    cleanup_interval_hours: int = 24
    enabled: bool = True
    dry_run: bool = False


@dataclass
class CleanupResult:
    """Result of a cleanup operation."""
    files_deleted: int
    bytes_freed: int
    errors: List[str]
    files_processed: List[str]
    execution_time: float


class CleanupServiceError(Exception):
    """Base exception for cleanup service operations."""
    pass


class CleanupService:
    """
    Service for managing export file cleanup operations.
    
    Provides automatic cleanup of old export files based on configurable
    retention policies. Supports both time-based and count-based cleanup
    strategies to maintain export directory hygiene.
    """
    
    def __init__(self, 
                 root_dir: Optional[str] = None,
                 config_file: Optional[str] = None):
        """
        Initialize CleanupService.
        
        Args:
            root_dir: Root directory of the application (defaults to /app in container)
            config_file: Path to cleanup configuration file
        """
        # Set up paths - default to /app in container, or calculate from file location
        if root_dir:
            self.root_dir = Path(root_dir)
        else:
            # Check if we're in a container (common path is /app)
            if Path("/app").exists():
                self.root_dir = Path("/app")
            else:
                # Development environment - go up to project root
                self.root_dir = Path(__file__).parent.parent.parent.parent
        
        self.exports_dir = self.root_dir / "exports"
        self.config_file = Path(config_file) if config_file else self.root_dir / "data" / "cleanup_config.json"
        
        # Load configuration
        self.config = self._load_config()
        
        # Ensure directories exist
        self._ensure_directories()
        
        # Task management
        self._cleanup_task = None
        self._running = False
    
    def _ensure_directories(self):
        """Ensure required directories exist."""
        directories = [
            self.exports_dir / "pdf",
            self.exports_dir / "docx", 
            self.exports_dir / "txt",
            self.config_file.parent
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self) -> CleanupConfig:
        """
        Load cleanup configuration from file or create default.
        
        Returns:
            CleanupConfig: Loaded or default configuration
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                
                config = CleanupConfig(
                    retention_days=config_data.get('retention_days', 30),
                    max_files_per_format=config_data.get('max_files_per_format', 100),
                    cleanup_interval_hours=config_data.get('cleanup_interval_hours', 24),
                    enabled=config_data.get('enabled', True),
                    dry_run=config_data.get('dry_run', False)
                )
                
                logger.info(f"Loaded cleanup configuration from {self.config_file}")
                return config
            else:
                # Create default configuration
                default_config = CleanupConfig()
                self._save_config(default_config)
                logger.info(f"Created default cleanup configuration at {self.config_file}")
                return default_config
                
        except Exception as e:
            logger.warning(f"Failed to load cleanup configuration: {e}. Using defaults.")
            return CleanupConfig()
    
    def _save_config(self, config: CleanupConfig):
        """
        Save cleanup configuration to file.
        
        Args:
            config: Configuration to save
        """
        try:
            config_data = {
                'retention_days': config.retention_days,
                'max_files_per_format': config.max_files_per_format,
                'cleanup_interval_hours': config.cleanup_interval_hours,
                'enabled': config.enabled,
                'dry_run': config.dry_run
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            logger.info(f"Saved cleanup configuration to {self.config_file}")
            
        except Exception as e:
            logger.error(f"Failed to save cleanup configuration: {e}")
            raise CleanupServiceError(f"Failed to save configuration: {e}")
    
    def update_config(self, **kwargs) -> CleanupConfig:
        """
        Update cleanup configuration.
        
        Args:
            **kwargs: Configuration parameters to update
            
        Returns:
            CleanupConfig: Updated configuration
        """
        # Update configuration
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
            else:
                logger.warning(f"Unknown configuration parameter: {key}")
        
        # Save updated configuration
        self._save_config(self.config)
        
        logger.info(f"Updated cleanup configuration: {kwargs}")
        return self.config
    
    def get_config(self) -> CleanupConfig:
        """
        Get current cleanup configuration.
        
        Returns:
            CleanupConfig: Current configuration
        """
        return self.config
    
    def cleanup_exports(self, dry_run: Optional[bool] = None) -> CleanupResult:
        """
        Perform cleanup of export files based on retention policy.
        
        Args:
            dry_run: If True, only simulate cleanup without deleting files
            
        Returns:
            CleanupResult: Results of the cleanup operation
        """
        start_time = datetime.now()
        
        # Use provided dry_run or fall back to config
        is_dry_run = dry_run if dry_run is not None else self.config.dry_run
        
        result = CleanupResult(
            files_deleted=0,
            bytes_freed=0,
            errors=[],
            files_processed=[],
            execution_time=0.0
        )
        
        if not self.config.enabled:
            logger.info("Cleanup is disabled in configuration")
            result.errors.append("Cleanup is disabled in configuration")
            return result
        
        try:
            logger.info(f"Starting export cleanup (dry_run={is_dry_run})")
            
            # Calculate cutoff date for retention
            cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)
            
            # Process each export format directory
            for format_value in [f.value for f in ExportFormat]:
                format_dir = self.exports_dir / format_value
                
                if not format_dir.exists():
                    continue
                
                # Get all files in the format directory
                files = []
                for file_path in format_dir.iterdir():
                    if file_path.is_file() and not file_path.name.startswith('.'):
                        try:
                            stat = file_path.stat()
                            files.append({
                                'path': file_path,
                                'mtime': datetime.fromtimestamp(stat.st_mtime),
                                'size': stat.st_size
                            })
                        except OSError as e:
                            logger.warning(f"Failed to stat file {file_path}: {e}")
                            result.errors.append(f"Failed to stat file {file_path}: {e}")
                
                # Sort files by modification time (oldest first)
                files.sort(key=lambda x: x['mtime'])
                
                # Apply retention policy
                files_to_delete = []
                
                # 1. Delete files older than retention period
                for file_info in files:
                    if file_info['mtime'] < cutoff_date:
                        files_to_delete.append(file_info)
                
                # 2. If still too many files, delete oldest ones
                remaining_files = [f for f in files if f not in files_to_delete]
                if len(remaining_files) > self.config.max_files_per_format:
                    excess_count = len(remaining_files) - self.config.max_files_per_format
                    files_to_delete.extend(remaining_files[:excess_count])
                
                # Delete identified files
                for file_info in files_to_delete:
                    file_path = file_info['path']
                    file_size = file_info['size']
                    
                    result.files_processed.append(str(file_path))
                    
                    if not is_dry_run:
                        try:
                            file_path.unlink()
                            result.files_deleted += 1
                            result.bytes_freed += file_size
                            logger.info(f"Deleted export file: {file_path}")
                        except OSError as e:
                            error_msg = f"Failed to delete file {file_path}: {e}"
                            logger.error(error_msg)
                            result.errors.append(error_msg)
                    else:
                        result.files_deleted += 1
                        result.bytes_freed += file_size
                        logger.info(f"Would delete export file: {file_path}")
            
            # Calculate execution time
            result.execution_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                f"Cleanup completed: {result.files_deleted} files, "
                f"{result.bytes_freed} bytes freed, {len(result.errors)} errors"
            )
            
            return result
            
        except Exception as e:
            error_msg = f"Cleanup operation failed: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)
            result.execution_time = (datetime.now() - start_time).total_seconds()
            return result
    
    def get_export_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about export files.
        
        Returns:
            Dictionary with export file statistics
        """
        try:
            stats = {
                'total_files': 0,
                'total_size': 0,
                'by_format': {},
                'oldest_file': None,
                'newest_file': None
            }
            
            oldest_time = None
            newest_time = None
            
            # Process each export format directory
            for format_value in [f.value for f in ExportFormat]:
                format_dir = self.exports_dir / format_value
                
                format_stats = {
                    'files': 0,
                    'size': 0,
                    'oldest': None,
                    'newest': None
                }
                
                if format_dir.exists():
                    for file_path in format_dir.iterdir():
                        if file_path.is_file() and not file_path.name.startswith('.'):
                            try:
                                stat = file_path.stat()
                                mtime = datetime.fromtimestamp(stat.st_mtime)
                                
                                format_stats['files'] += 1
                                format_stats['size'] += stat.st_size
                                stats['total_files'] += 1
                                stats['total_size'] += stat.st_size
                                
                                # Track oldest and newest files
                                if oldest_time is None or mtime < oldest_time:
                                    oldest_time = mtime
                                    stats['oldest_file'] = str(file_path)
                                
                                if newest_time is None or mtime > newest_time:
                                    newest_time = mtime
                                    stats['newest_file'] = str(file_path)
                                
                                if format_stats['oldest'] is None or mtime < datetime.fromisoformat(format_stats['oldest']):
                                    format_stats['oldest'] = mtime.isoformat()
                                
                                if format_stats['newest'] is None or mtime > datetime.fromisoformat(format_stats['newest']):
                                    format_stats['newest'] = mtime.isoformat()
                                    
                            except OSError as e:
                                logger.warning(f"Failed to stat file {file_path}: {e}")
                
                stats['by_format'][format_value] = format_stats
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get export statistics: {e}")
            raise CleanupServiceError(f"Failed to get statistics: {e}")
    
    def delete_export_file(self, file_path: str) -> bool:
        """
        Delete a specific export file.
        
        Args:
            file_path: Path to the file to delete (relative to exports directory)
            
        Returns:
            bool: True if file was deleted successfully
        """
        try:
            # Security: Ensure file is within exports directory
            full_path = self.exports_dir / file_path
            
            # Resolve path and check it's within exports directory
            resolved_path = full_path.resolve()
            exports_resolved = self.exports_dir.resolve()
            
            if not str(resolved_path).startswith(str(exports_resolved)):
                logger.warning(f"Attempted to delete file outside exports directory: {file_path}")
                raise CleanupServiceError("File path is outside exports directory")
            
            if not resolved_path.exists():
                logger.warning(f"File not found for deletion: {file_path}")
                return False
            
            if not resolved_path.is_file():
                logger.warning(f"Path is not a file: {file_path}")
                raise CleanupServiceError("Path is not a file")
            
            # Delete the file
            resolved_path.unlink()
            logger.info(f"Manually deleted export file: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete export file {file_path}: {e}")
            raise CleanupServiceError(f"Failed to delete file: {e}")
    
    async def start_scheduled_cleanup(self):
        """Start the scheduled cleanup task."""
        if self._running:
            logger.warning("Scheduled cleanup is already running")
            return
        
        self._running = True
        logger.info(f"Starting scheduled cleanup with {self.config.cleanup_interval_hours}h interval")
        
        try:
            while self._running:
                # Wait for the cleanup interval
                await asyncio.sleep(self.config.cleanup_interval_hours * 3600)
                
                if self._running and self.config.enabled:
                    try:
                        result = self.cleanup_exports()
                        logger.info(
                            f"Scheduled cleanup completed: {result.files_deleted} files deleted, "
                            f"{result.bytes_freed} bytes freed"
                        )
                    except Exception as e:
                        logger.error(f"Scheduled cleanup failed: {e}")
                        
        except asyncio.CancelledError:
            logger.info("Scheduled cleanup task was cancelled")
        except Exception as e:
            logger.error(f"Scheduled cleanup task failed: {e}")
        finally:
            self._running = False
    
    def stop_scheduled_cleanup(self):
        """Stop the scheduled cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            logger.info("Stopped scheduled cleanup task")
        
        self._running = False
    
    def validate_export_file(self, file_path: str) -> Dict[str, Any]:
        """
        Validate export file integrity and format.
        
        Args:
            file_path: Path to the file to validate (relative to exports directory)
            
        Returns:
            Dictionary with validation results
        """
        try:
            # Security: Ensure file is within exports directory
            full_path = self.exports_dir / file_path
            
            # Resolve path and check it's within exports directory
            resolved_path = full_path.resolve()
            exports_resolved = self.exports_dir.resolve()
            
            if not str(resolved_path).startswith(str(exports_resolved)):
                return {
                    "valid": False,
                    "error": "File path is outside exports directory",
                    "file_exists": False,
                    "file_size": 0,
                    "format_valid": False
                }
            
            if not resolved_path.exists():
                return {
                    "valid": False,
                    "error": "File does not exist",
                    "file_exists": False,
                    "file_size": 0,
                    "format_valid": False
                }
            
            if not resolved_path.is_file():
                return {
                    "valid": False,
                    "error": "Path is not a file",
                    "file_exists": True,
                    "file_size": 0,
                    "format_valid": False
                }
            
            # Get file statistics
            stat = resolved_path.stat()
            file_size = stat.st_size
            
            # Validate file format based on extension
            file_extension = resolved_path.suffix.lower()
            expected_formats = {'.pdf', '.docx', '.txt'}
            format_valid = file_extension in expected_formats
            
            # Basic file integrity checks
            integrity_checks = {
                "non_empty": file_size > 0,
                "reasonable_size": file_size < 50 * 1024 * 1024,  # Less than 50MB
                "readable": os.access(resolved_path, os.R_OK)
            }
            
            # Format-specific validation
            format_validation = self._validate_file_format(resolved_path, file_extension)
            
            is_valid = (
                format_valid and 
                all(integrity_checks.values()) and 
                format_validation["valid"]
            )
            
            return {
                "valid": is_valid,
                "error": None if is_valid else format_validation.get("error", "File validation failed"),
                "file_exists": True,
                "file_size": file_size,
                "format_valid": format_valid,
                "integrity_checks": integrity_checks,
                "format_validation": format_validation,
                "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to validate export file {file_path}: {e}")
            return {
                "valid": False,
                "error": f"Validation failed: {e}",
                "file_exists": False,
                "file_size": 0,
                "format_valid": False
            }
    
    def _validate_file_format(self, file_path: Path, extension: str) -> Dict[str, Any]:
        """
        Perform format-specific validation on export files.
        
        Args:
            file_path: Path to the file
            extension: File extension
            
        Returns:
            Dictionary with format validation results
        """
        try:
            if extension == '.pdf':
                # Basic PDF validation - check for PDF header
                with open(file_path, 'rb') as f:
                    header = f.read(4)
                    if header != b'%PDF':
                        return {"valid": False, "error": "Invalid PDF file format"}
                
            elif extension == '.docx':
                # Basic DOCX validation - check if it's a valid ZIP file
                import zipfile
                try:
                    with zipfile.ZipFile(file_path, 'r') as zip_file:
                        # Check for required DOCX structure
                        required_files = ['[Content_Types].xml', 'word/document.xml']
                        zip_contents = zip_file.namelist()
                        
                        for required_file in required_files:
                            if required_file not in zip_contents:
                                return {"valid": False, "error": f"Missing required DOCX component: {required_file}"}
                except zipfile.BadZipFile:
                    return {"valid": False, "error": "Invalid DOCX file format (not a valid ZIP)"}
                
            elif extension == '.txt':
                # Basic TXT validation - check if it's readable as text
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        # Try to read first few lines
                        for i, line in enumerate(f):
                            if i >= 10:  # Check first 10 lines
                                break
                except UnicodeDecodeError:
                    return {"valid": False, "error": "Invalid text file encoding"}
            
            return {"valid": True, "error": None}
            
        except Exception as e:
            return {"valid": False, "error": f"Format validation failed: {e}"}
    
    def is_running(self) -> bool:
        """Check if scheduled cleanup is running."""
        return self._running