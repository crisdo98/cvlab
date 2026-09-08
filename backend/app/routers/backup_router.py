"""
Backup Router

REST API endpoints for backup and restore operations.
Provides endpoints for creating backups, restoring from backups,
and managing backup files.
"""

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import List, Optional
from pathlib import Path
import logging

from pydantic import BaseModel

from ..services.backup_service import (
    BackupService,
    BackupServiceError,
    BackupCreationError,
    BackupRestoreError,
    BackupValidationError
)

logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter(
    prefix="/api/backup",
    tags=["Backup"],
    responses={404: {"description": "Backup not found"}}
)

# Initialize backup service lazily
_backup_service = None


def get_backup_service() -> BackupService:
    """Get backup service instance with lazy initialization."""
    global _backup_service
    if _backup_service is None:
        _backup_service = BackupService()
    return _backup_service


# Request/Response Models

class CreateBackupRequest(BaseModel):
    """Request model for creating a backup."""
    include_exports: bool = False


class BackupInfo(BaseModel):
    """Information about a backup file."""
    filename: str
    path: str
    size: int
    created_at: Optional[str]
    version: Optional[str]
    summary: Optional[dict]


class BackupListResponse(BaseModel):
    """Response model for listing backups."""
    backups: List[BackupInfo]
    total: int


class CreateBackupResponse(BaseModel):
    """Response model for backup creation."""
    filename: str
    path: str
    size: int
    message: str


class RestoreBackupResponse(BaseModel):
    """Response model for backup restoration."""
    backup_version: Optional[str]
    backup_date: Optional[str]
    restored_items: dict
    message: str


class DeleteBackupResponse(BaseModel):
    """Response model for backup deletion."""
    filename: str
    message: str


# Endpoints

@router.post("/create", response_model=CreateBackupResponse, status_code=status.HTTP_201_CREATED)
async def create_backup(request: CreateBackupRequest):
    """
    Create a full backup of all user data.
    
    Creates a zip archive containing:
    - All CV documents
    - Application tracking data
    - Custom templates
    - Configuration (excluding sensitive keys)
    - Optionally: exported files (PDF, DOCX, TXT)
    
    Args:
        request: Backup creation request
        
    Returns:
        CreateBackupResponse: Information about created backup
        
    Raises:
        HTTPException: If backup creation fails
    """
    try:
        logger.info(f"Creating backup (include_exports={request.include_exports})")
        
        backup_service = get_backup_service()
        backup_path = backup_service.create_backup(include_exports=request.include_exports)
        
        # Get file info
        file_size = backup_path.stat().st_size
        
        logger.info(f"Backup created successfully: {backup_path.name}")
        
        return CreateBackupResponse(
            filename=backup_path.name,
            path=str(backup_path),
            size=file_size,
            message=f"Backup created successfully: {backup_path.name}"
        )
        
    except BackupCreationError as e:
        logger.error(f"Failed to create backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create backup: {str(e)}"
        )
    except BackupServiceError as e:
        logger.error(f"Backup service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backup service error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error creating backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating backup"
        )


@router.get("/list", response_model=BackupListResponse)
async def list_backups():
    """
    List all available backup files.
    
    Returns:
        BackupListResponse: List of all backups with metadata
        
    Raises:
        HTTPException: If listing fails
    """
    try:
        logger.info("Listing backups")
        
        backup_service = get_backup_service()
        backups = backup_service.list_backups()
        
        logger.info(f"Found {len(backups)} backups")
        
        return BackupListResponse(
            backups=[BackupInfo(**backup) for backup in backups],
            total=len(backups)
        )
        
    except Exception as e:
        logger.error(f"Failed to list backups: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while listing backups"
        )


@router.get("/download/{filename}")
async def download_backup(filename: str):
    """
    Download a backup file.
    
    Args:
        filename: Name of backup file to download
        
    Returns:
        FileResponse: Backup zip file
        
    Raises:
        HTTPException: If backup not found or download fails
    """
    try:
        logger.info(f"Downloading backup: {filename}")
        
        # Validate filename (security check)
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid filename"
            )
        
        backup_service = get_backup_service()
        backup_path = backup_service.data_dir / "backups" / filename
        
        if not backup_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backup not found: {filename}"
            )
        
        return FileResponse(
            path=str(backup_path),
            filename=filename,
            media_type="application/zip"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while downloading backup"
        )


@router.post("/restore", response_model=RestoreBackupResponse)
async def restore_backup(
    file: UploadFile = File(..., description="Backup zip file to restore"),
    overwrite: bool = Form(False, description="Whether to overwrite existing data")
):
    """
    Restore data from a backup file.
    
    Restores all data from a backup archive. If overwrite is False,
    existing items are preserved and only new items are added.
    
    Args:
        file: Uploaded backup zip file
        overwrite: Whether to overwrite existing data
        
    Returns:
        RestoreBackupResponse: Summary of restored items
        
    Raises:
        HTTPException: If restoration fails or validation errors occur
    """
    try:
        logger.info(f"Restoring backup from file: {file.filename} (overwrite={overwrite})")
        
        # Validate file type
        if not file.filename or not file.filename.lower().endswith('.zip'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a zip archive"
            )
        
        # Save uploaded file temporarily
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = Path(temp_file.name)
        
        try:
            # Restore backup
            backup_service = get_backup_service()
            summary = backup_service.restore_backup(temp_path, overwrite=overwrite)
            
            logger.info(f"Backup restored successfully from {file.filename}")
            
            return RestoreBackupResponse(
                backup_version=summary.get('backup_version'),
                backup_date=summary.get('backup_date'),
                restored_items=summary.get('restored_items', {}),
                message=f"Backup restored successfully from {file.filename}"
            )
            
        finally:
            # Clean up temporary file
            if temp_path.exists():
                temp_path.unlink()
        
    except BackupValidationError as e:
        logger.warning(f"Backup validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Backup validation error: {str(e)}"
        )
    except BackupRestoreError as e:
        logger.error(f"Failed to restore backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore backup: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error restoring backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while restoring backup"
        )


@router.post("/restore/{filename}", response_model=RestoreBackupResponse)
async def restore_existing_backup(
    filename: str,
    overwrite: bool = Form(False, description="Whether to overwrite existing data")
):
    """
    Restore data from an existing backup file on the server.
    
    Args:
        filename: Name of backup file to restore
        overwrite: Whether to overwrite existing data
        
    Returns:
        RestoreBackupResponse: Summary of restored items
        
    Raises:
        HTTPException: If backup not found or restoration fails
    """
    try:
        logger.info(f"Restoring existing backup: {filename} (overwrite={overwrite})")
        
        # Validate filename (security check)
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid filename"
            )
        
        backup_service = get_backup_service()
        backup_path = backup_service.data_dir / "backups" / filename
        
        if not backup_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backup not found: {filename}"
            )
        
        # Restore backup
        summary = backup_service.restore_backup(backup_path, overwrite=overwrite)
        
        logger.info(f"Backup restored successfully: {filename}")
        
        return RestoreBackupResponse(
            backup_version=summary.get('backup_version'),
            backup_date=summary.get('backup_date'),
            restored_items=summary.get('restored_items', {}),
            message=f"Backup restored successfully: {filename}"
        )
        
    except BackupValidationError as e:
        logger.warning(f"Backup validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Backup validation error: {str(e)}"
        )
    except BackupRestoreError as e:
        logger.error(f"Failed to restore backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore backup: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error restoring backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while restoring backup"
        )


@router.delete("/{filename}", response_model=DeleteBackupResponse)
async def delete_backup(filename: str):
    """
    Delete a backup file.
    
    Args:
        filename: Name of backup file to delete
        
    Returns:
        DeleteBackupResponse: Confirmation message
        
    Raises:
        HTTPException: If backup not found or deletion fails
    """
    try:
        logger.info(f"Deleting backup: {filename}")
        
        # Validate filename (security check)
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid filename"
            )
        
        backup_service = get_backup_service()
        backup_service.delete_backup(filename)
        
        logger.info(f"Backup deleted successfully: {filename}")
        
        return DeleteBackupResponse(
            filename=filename,
            message=f"Backup deleted successfully: {filename}"
        )
        
    except BackupServiceError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting backup"
        )
