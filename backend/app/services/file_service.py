"""
File Service

Handles JSON file I/O operations for CV data with proper error handling,
UUID generation, and file naming conventions. Provides a clean interface
for persisting CV documents to the filesystem.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4
import logging

from ..models.cv_models import CVModel, CVModelV2
from ..models.cv_section_models import SectionType

logger = logging.getLogger(__name__)


class FileServiceError(Exception):
    """Base exception for file service operations."""
    pass


class FileNotFoundError(FileServiceError):
    """Raised when a requested file is not found."""
    pass


class FilePermissionError(FileServiceError):
    """Raised when file operations fail due to permission issues."""
    pass


class FileCorruptionError(FileServiceError):
    """Raised when a file exists but cannot be parsed."""
    pass


class FileService:
    """
    Service for managing CV file operations including JSON I/O,
    UUID generation, and file naming conventions.
    """
    
    def __init__(self, data_directory: str = "/app/data"):
        """
        Initialize FileService with data directory.
        
        Args:
            data_directory: Base directory for storing CV files
        """
        self.data_directory = Path(data_directory)
        self.cvs_directory = self.data_directory / "cvs"
        self.metadata_file = self.cvs_directory / "metadata.json"
        
        # Ensure directories exist
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        try:
            self.cvs_directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Ensured CV directory exists: {self.cvs_directory}")
        except OSError as e:
            raise FilePermissionError(f"Cannot create CV directory: {e}")
    
    def generate_cv_id(self) -> str:
        """
        Generate a unique UUID for a new CV.
        
        Returns:
            String representation of UUID4
        """
        return str(uuid4())
    
    def get_cv_file_path(self, cv_id: str) -> Path:
        """
        Get the file path for a CV given its ID.
        
        Args:
            cv_id: UUID string of the CV
            
        Returns:
            Path object for the CV file
        """
        return self.cvs_directory / f"{cv_id}.json"
    
    def save_cv(self, cv_data) -> None:
        """
        Save CV data to JSON file.
        
        Args:
            cv_data: CVModel or CVModelV2 instance to save
            
        Raises:
            FilePermissionError: If file cannot be written
            FileServiceError: If JSON serialization fails
        """
        file_path = self.get_cv_file_path(cv_data.id)
        
        try:
            # Convert Pydantic model to dict, then to JSON
            cv_dict = cv_data.model_dump()
            
            # Write to file with proper error handling
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(cv_dict, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"Successfully saved CV {cv_data.id} to {file_path}")
            
            # Update metadata - handle both V1 and V2 models
            if isinstance(cv_data, CVModelV2):
                # V2 model doesn't have metadata.title, need to extract from sections
                title = "Untitled CV"
                personal_section = cv_data.get_section_by_type("personal_info")
                if personal_section and hasattr(personal_section.content, 'full_name'):
                    title = personal_section.content.full_name
            else:
                title = cv_data.metadata.title
            
            self._update_metadata(cv_data.id, title)
            
        except OSError as e:
            raise FilePermissionError(f"Cannot write CV file {file_path}: {e}")
        except (TypeError, ValueError) as e:
            raise FileServiceError(f"Cannot serialize CV data: {e}")
    
    def load_cv(self, cv_id: str):
        """
        Load CV data from JSON file.
        
        Detects CV version and returns appropriate model (CVModel or CVModelV2).
        
        Args:
            cv_id: UUID string of the CV to load
            
        Returns:
            CVModel or CVModelV2 instance loaded from file
            
        Raises:
            FileNotFoundError: If CV file doesn't exist
            FileCorruptionError: If file exists but cannot be parsed
            FilePermissionError: If file cannot be read
        """
        file_path = self.get_cv_file_path(cv_id)
        
        if not file_path.exists():
            raise FileNotFoundError(f"CV file not found: {cv_id}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                cv_dict = json.load(f)
            
            # Detect version and load appropriate model
            version = cv_dict.get('version', 1)
            
            if version == 2:
                # Load as V2 model with sections
                cv_data = CVModelV2(**cv_dict)
                
                # Sort sections by order field to ensure correct display order
                if cv_data.sections:
                    cv_data.sections.sort(key=lambda s: s.order)
                
                logger.info(f"Successfully loaded CV {cv_id} as V2 model from {file_path}")
            else:
                # Load as V1 model (legacy) and migrate to V2 so callers and
                # API response models only ever deal with the V2 structure
                from .cv_migration import migrate_v1_to_v2

                cv_v1 = CVModel(**cv_dict)
                cv_data = migrate_v1_to_v2(cv_v1)
                logger.info(f"Loaded CV {cv_id} as V1 model from {file_path} and migrated to V2")
            
            return cv_data
            
        except OSError as e:
            raise FilePermissionError(f"Cannot read CV file {file_path}: {e}")
        except json.JSONDecodeError as e:
            raise FileCorruptionError(f"Invalid JSON in CV file {cv_id}: {e}")
        except (TypeError, ValueError) as e:
            raise FileCorruptionError(f"Invalid CV data structure in {cv_id}: {e}")
    
    def delete_cv(self, cv_id: str) -> None:
        """
        Delete CV file from filesystem.
        
        Args:
            cv_id: UUID string of the CV to delete
            
        Raises:
            FileNotFoundError: If CV file doesn't exist
            FilePermissionError: If file cannot be deleted
        """
        file_path = self.get_cv_file_path(cv_id)
        
        if not file_path.exists():
            raise FileNotFoundError(f"CV file not found: {cv_id}")
        
        try:
            file_path.unlink()
            logger.info(f"Successfully deleted CV {cv_id} from {file_path}")
            
            # Remove from metadata
            self._remove_from_metadata(cv_id)
            
        except OSError as e:
            raise FilePermissionError(f"Cannot delete CV file {file_path}: {e}")
    
    def cv_exists(self, cv_id: str) -> bool:
        """
        Check if a CV file exists.
        
        Args:
            cv_id: UUID string of the CV to check
            
        Returns:
            True if CV file exists, False otherwise
        """
        file_path = self.get_cv_file_path(cv_id)
        return file_path.exists()
    
    def list_cv_files(self) -> List[str]:
        """
        List all CV file IDs in the directory.
        
        Returns:
            List of CV ID strings
            
        Raises:
            FilePermissionError: If directory cannot be read
        """
        try:
            cv_files = []
            for file_path in self.cvs_directory.glob("*.json"):
                # Skip metadata file
                if file_path.name == "metadata.json":
                    continue
                
                # Extract CV ID from filename (remove .json extension)
                cv_id = file_path.stem
                cv_files.append(cv_id)
            
            logger.info(f"Found {len(cv_files)} CV files")
            return cv_files
            
        except OSError as e:
            raise FilePermissionError(f"Cannot read CV directory: {e}")
    
    def _update_metadata(self, cv_id: str, title: str) -> None:
        """
        Update metadata file with CV information.
        
        Args:
            cv_id: UUID string of the CV
            title: Title of the CV for quick reference
        """
        try:
            # Load existing metadata or create new
            metadata = {}
            if self.metadata_file.exists():
                try:
                    with open(self.metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                except (json.JSONDecodeError, OSError):
                    # If metadata is corrupted, start fresh
                    logger.warning("Metadata file corrupted, creating new one")
                    metadata = {}
            
            # Update metadata
            metadata[cv_id] = {
                "title": title,
                "file_path": f"{cv_id}.json"
            }
            
            # Save metadata
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
                
        except OSError as e:
            # Metadata update failure shouldn't prevent CV save
            logger.warning(f"Failed to update metadata: {e}")
    
    def _remove_from_metadata(self, cv_id: str) -> None:
        """
        Remove CV from metadata file.
        
        Args:
            cv_id: UUID string of the CV to remove
        """
        try:
            if not self.metadata_file.exists():
                return
            
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            # Remove CV from metadata
            metadata.pop(cv_id, None)
            
            # Save updated metadata
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
                
        except (json.JSONDecodeError, OSError) as e:
            # Metadata update failure shouldn't prevent CV deletion
            logger.warning(f"Failed to update metadata during deletion: {e}")
    
    def get_metadata(self) -> Dict[str, Dict[str, str]]:
        """
        Get metadata for all CVs.
        
        Returns:
            Dictionary mapping CV IDs to their metadata
        """
        try:
            if not self.metadata_file.exists():
                return {}
            
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read metadata: {e}")
            return {}