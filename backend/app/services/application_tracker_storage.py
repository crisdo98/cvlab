"""
Application Tracker Storage Layer

Handles JSON file I/O operations for job application data with atomic writes,
file locking for concurrent access, and proper error handling. Provides CRUD
operations for applications and status history.
"""

import json
import os
import tempfile
import fcntl
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import logging

from ..models.application_tracker_models import (
    Application,
    StatusHistoryEntry,
    ApplicationFilters,
    Stage
)

logger = logging.getLogger(__name__)


class ApplicationStorageError(Exception):
    """Base exception for application storage operations."""
    pass


class ApplicationNotFoundError(ApplicationStorageError):
    """Raised when a requested application is not found."""
    pass


class StoragePermissionError(ApplicationStorageError):
    """Raised when file operations fail due to permission issues."""
    pass


class StorageCorruptionError(ApplicationStorageError):
    """Raised when a file exists but cannot be parsed."""
    pass


class ApplicationTrackerStorage:
    """
    Storage layer for job application tracking with atomic writes and file locking.
    
    Manages JSON file operations for applications.json and application_history.json
    with proper concurrency control and error handling.
    """
    
    def __init__(self, data_directory: Optional[str] = None):
        """
        Initialize ApplicationTrackerStorage with data directory.
        
        Args:
            data_directory: Base directory for storing application files.
                          If None, auto-detects based on environment.
        """
        if data_directory is None:
            # Auto-detect data directory based on environment
            if os.path.exists("/app/data"):
                # Docker environment
                data_directory = "/app/data"
            else:
                # Local development - use relative path from backend directory
                backend_dir = Path(__file__).parent.parent.parent
                data_directory = str(backend_dir.parent / "data")
        
        self.data_directory = Path(data_directory)
        self.applications_file = self.data_directory / "applications.json"
        self.history_file = self.data_directory / "application_history.json"
        
        # Ensure directory exists and initialize files
        self._ensure_directory()
        self._initialize_files()
    
    def _ensure_directory(self) -> None:
        """Create data directory if it doesn't exist."""
        try:
            self.data_directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Ensured data directory exists: {self.data_directory}")
        except OSError as e:
            raise StoragePermissionError(f"Cannot create data directory: {e}")
    
    def _initialize_files(self) -> None:
        """Initialize JSON files with empty structures if they don't exist."""
        if not self.applications_file.exists():
            self._write_json_atomic(self.applications_file, {"applications": []})
            logger.info(f"Initialized applications file: {self.applications_file}")
        
        if not self.history_file.exists():
            self._write_json_atomic(self.history_file, {"history": []})
            logger.info(f"Initialized history file: {self.history_file}")
    
    def _read_json_with_lock(self, file_path: Path) -> dict:
        """
        Read JSON file with shared lock for concurrent read access.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Parsed JSON data as dictionary
            
        Raises:
            StorageCorruptionError: If file cannot be parsed
            StoragePermissionError: If file cannot be read
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Acquire shared lock for reading
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    # Release lock
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            
            return data
            
        except json.JSONDecodeError as e:
            raise StorageCorruptionError(f"Invalid JSON in {file_path}: {e}")
        except OSError as e:
            raise StoragePermissionError(f"Cannot read file {file_path}: {e}")
    
    def _write_json_atomic(self, file_path: Path, data: dict) -> None:
        """
        Write JSON file atomically using temp file and rename.
        
        This ensures that the file is never in a partially written state,
        preventing corruption from concurrent access or crashes.
        
        Args:
            file_path: Path to JSON file
            data: Data to write
            
        Raises:
            StoragePermissionError: If file cannot be written
            ApplicationStorageError: If JSON serialization fails
        """
        try:
            # Create temp file in same directory for atomic rename
            temp_fd, temp_path = tempfile.mkstemp(
                dir=file_path.parent,
                prefix=f".{file_path.name}.",
                suffix=".tmp"
            )
            
            try:
                # Write to temp file with exclusive lock
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    try:
                        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
                        f.flush()
                        os.fsync(f.fileno())  # Ensure data is written to disk
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                
                # Atomic rename
                os.replace(temp_path, file_path)
                logger.debug(f"Successfully wrote {file_path} atomically")
                
            except Exception:
                # Clean up temp file on error
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                raise
                
        except OSError as e:
            raise StoragePermissionError(f"Cannot write file {file_path}: {e}")
        except (TypeError, ValueError) as e:
            raise ApplicationStorageError(f"Cannot serialize data: {e}")
    
    def create_application(self, application: Application) -> Application:
        """
        Create a new application.
        
        Args:
            application: Application instance to create
            
        Returns:
            Created application
            
        Raises:
            ApplicationStorageError: If creation fails
        """
        try:
            # Read current applications
            data = self._read_json_with_lock(self.applications_file)
            applications = data.get("applications", [])
            
            # Add new application
            app_dict = application.model_dump(mode='json')
            applications.append(app_dict)
            
            # Write back atomically
            self._write_json_atomic(self.applications_file, {"applications": applications})
            
            logger.info(f"Created application {application.id}: {application.company_name} - {application.position_title}")
            return application
            
        except (StorageCorruptionError, StoragePermissionError):
            raise
        except Exception as e:
            raise ApplicationStorageError(f"Failed to create application: {e}")
    
    def get_application(self, application_id: str) -> Application:
        """
        Retrieve an application by ID.
        
        Args:
            application_id: UUID string of the application
            
        Returns:
            Application instance
            
        Raises:
            ApplicationNotFoundError: If application doesn't exist
            ApplicationStorageError: If retrieval fails
        """
        try:
            data = self._read_json_with_lock(self.applications_file)
            applications = data.get("applications", [])
            
            # Find application by ID
            for app_dict in applications:
                if app_dict.get("id") == application_id:
                    return Application(**app_dict)
            
            raise ApplicationNotFoundError(f"Application not found: {application_id}")
            
        except ApplicationNotFoundError:
            raise
        except (StorageCorruptionError, StoragePermissionError):
            raise
        except Exception as e:
            raise ApplicationStorageError(f"Failed to retrieve application {application_id}: {e}")
    
    def update_application(self, application_id: str, application: Application) -> Application:
        """
        Update an existing application.
        
        Args:
            application_id: UUID string of the application to update
            application: Updated application data
            
        Returns:
            Updated application
            
        Raises:
            ApplicationNotFoundError: If application doesn't exist
            ApplicationStorageError: If update fails
        """
        try:
            data = self._read_json_with_lock(self.applications_file)
            applications = data.get("applications", [])
            
            # Find and update application
            found = False
            for i, app_dict in enumerate(applications):
                if app_dict.get("id") == application_id:
                    applications[i] = application.model_dump(mode='json')
                    found = True
                    break
            
            if not found:
                raise ApplicationNotFoundError(f"Application not found: {application_id}")
            
            # Write back atomically
            self._write_json_atomic(self.applications_file, {"applications": applications})
            
            logger.info(f"Updated application {application_id}")
            return application
            
        except ApplicationNotFoundError:
            raise
        except (StorageCorruptionError, StoragePermissionError):
            raise
        except Exception as e:
            raise ApplicationStorageError(f"Failed to update application {application_id}: {e}")
    
    def delete_application(self, application_id: str) -> bool:
        """
        Delete an application.
        
        Args:
            application_id: UUID string of the application to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            ApplicationNotFoundError: If application doesn't exist
            ApplicationStorageError: If deletion fails
        """
        try:
            data = self._read_json_with_lock(self.applications_file)
            applications = data.get("applications", [])
            
            # Find and remove application
            initial_count = len(applications)
            applications = [app for app in applications if app.get("id") != application_id]
            
            if len(applications) == initial_count:
                raise ApplicationNotFoundError(f"Application not found: {application_id}")
            
            # Write back atomically
            self._write_json_atomic(self.applications_file, {"applications": applications})
            
            logger.info(f"Deleted application {application_id}")
            return True
            
        except ApplicationNotFoundError:
            raise
        except (StorageCorruptionError, StoragePermissionError):
            raise
        except Exception as e:
            raise ApplicationStorageError(f"Failed to delete application {application_id}: {e}")
    
    def list_applications(self, filters: Optional[ApplicationFilters] = None) -> List[Application]:
        """
        List all applications with optional filtering.
        
        Args:
            filters: Optional filters for stage, search, date range
            
        Returns:
            List of Application instances
            
        Raises:
            ApplicationStorageError: If listing fails
        """
        try:
            data = self._read_json_with_lock(self.applications_file)
            applications = data.get("applications", [])
            
            # Convert to Application instances
            app_instances = [Application(**app_dict) for app_dict in applications]
            
            # Apply filters if provided
            if filters:
                app_instances = self._apply_filters(app_instances, filters)
            
            logger.debug(f"Listed {len(app_instances)} applications")
            return app_instances
            
        except (StorageCorruptionError, StoragePermissionError):
            raise
        except Exception as e:
            raise ApplicationStorageError(f"Failed to list applications: {e}")
    
    def _apply_filters(self, applications: List[Application], filters: ApplicationFilters) -> List[Application]:
        """
        Apply filters to application list.
        
        Args:
            applications: List of applications to filter
            filters: Filter criteria
            
        Returns:
            Filtered list of applications
        """
        filtered = applications
        
        # Stage filter
        if filters.stage is not None:
            filtered = [app for app in filtered if app.stage == filters.stage]
        
        # Search filter (company name or position title)
        if filters.search:
            search_lower = filters.search.lower()
            filtered = [
                app for app in filtered
                if search_lower in app.company_name.lower()
                or search_lower in app.position_title.lower()
            ]
        
        # Date range filter
        if filters.date_from:
            filtered = [app for app in filtered if app.application_date >= filters.date_from]
        
        if filters.date_to:
            filtered = [app for app in filtered if app.application_date <= filters.date_to]
        
        return filtered
    
    def add_history_entry(self, entry: StatusHistoryEntry) -> StatusHistoryEntry:
        """
        Add a status history entry.
        
        Args:
            entry: StatusHistoryEntry to add
            
        Returns:
            Added history entry
            
        Raises:
            ApplicationStorageError: If addition fails
        """
        try:
            data = self._read_json_with_lock(self.history_file)
            history = data.get("history", [])
            
            # Add new entry
            entry_dict = entry.model_dump(mode='json')
            history.append(entry_dict)
            
            # Write back atomically
            self._write_json_atomic(self.history_file, {"history": history})
            
            logger.debug(f"Added history entry for application {entry.application_id}")
            return entry
            
        except (StorageCorruptionError, StoragePermissionError):
            raise
        except Exception as e:
            raise ApplicationStorageError(f"Failed to add history entry: {e}")
    
    def get_application_history(self, application_id: str) -> List[StatusHistoryEntry]:
        """
        Get status history for an application.
        
        Args:
            application_id: UUID string of the application
            
        Returns:
            List of StatusHistoryEntry instances in chronological order
            
        Raises:
            ApplicationStorageError: If retrieval fails
        """
        try:
            data = self._read_json_with_lock(self.history_file)
            history = data.get("history", [])
            
            # Filter by application ID and convert to instances
            app_history = [
                StatusHistoryEntry(**entry_dict)
                for entry_dict in history
                if entry_dict.get("application_id") == application_id
            ]
            
            # Sort by timestamp (chronological order)
            app_history.sort(key=lambda e: e.timestamp)
            
            logger.debug(f"Retrieved {len(app_history)} history entries for application {application_id}")
            return app_history
            
        except (StorageCorruptionError, StoragePermissionError):
            raise
        except Exception as e:
            raise ApplicationStorageError(f"Failed to retrieve history for {application_id}: {e}")
    
    def application_exists(self, application_id: str) -> bool:
        """
        Check if an application exists.
        
        Args:
            application_id: UUID string of the application
            
        Returns:
            True if application exists, False otherwise
        """
        try:
            data = self._read_json_with_lock(self.applications_file)
            applications = data.get("applications", [])
            return any(app.get("id") == application_id for app in applications)
        except Exception:
            return False
