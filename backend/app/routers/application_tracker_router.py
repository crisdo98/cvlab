"""
Application Tracker Router

REST API endpoints for job application tracking.
Provides CRUD operations, stage management, bulk operations, history tracking,
and CSV import/export with proper error handling.
"""

from fastapi import APIRouter, HTTPException, status, File, UploadFile, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional
import logging
import io
from datetime import datetime

from ..models.application_tracker_models import (
    Application,
    Stage,
    StatusHistoryEntry,
    CreateApplicationRequest,
    UpdateApplicationRequest,
    StageChangeRequest,
    BulkStageChangeRequest,
    BulkDeleteRequest,
    BulkOperationResponse,
    ImportResponse,
    ApplicationFilters,
    DeleteResponse
)
from ..services.application_tracker_service import (
    ApplicationTrackerService,
    ApplicationTrackerServiceError,
    CVVersionNotFoundError
)
from ..services.application_tracker_storage import (
    ApplicationNotFoundError,
    ApplicationStorageError
)

logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter(
    prefix="/api/applications",
    tags=["Applications"],
    responses={404: {"description": "Application not found"}}
)

# Initialize service lazily
_service = None

def get_service() -> ApplicationTrackerService:
    """Get application tracker service instance with lazy initialization."""
    global _service
    if _service is None:
        _service = ApplicationTrackerService()
    return _service


@router.post("", response_model=Application, status_code=status.HTTP_201_CREATED)
async def create_application(request: CreateApplicationRequest):
    """
    Create a new job application.
    
    Args:
        request: Application creation request with required and optional fields
        
    Returns:
        Application: Created application with generated ID and timestamps
        
    Raises:
        HTTPException: If creation fails or validation errors occur
    """
    try:
        logger.info(f"Creating application: {request.company_name} - {request.position_title}")
        application = get_service().create_application(request)
        logger.info(f"Successfully created application {application.id}")
        return application
        
    except CVVersionNotFoundError as e:
        logger.warning(f"CV version not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ApplicationTrackerServiceError as e:
        logger.error(f"Failed to create application: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create application: {str(e)}"
        )
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error creating application: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating application"
        )


@router.get("", response_model=List[Application])
async def list_applications(
    stage: Optional[Stage] = Query(None, description="Filter by stage"),
    search: Optional[str] = Query(None, description="Search in company name or position title"),
    date_from: Optional[datetime] = Query(None, description="Filter applications from this date"),
    date_to: Optional[datetime] = Query(None, description="Filter applications until this date")
):
    """
    List all job applications with optional filtering.
    
    Args:
        stage: Optional stage filter
        search: Optional search query for company name or position title
        date_from: Optional start date filter
        date_to: Optional end date filter
        
    Returns:
        List[Application]: List of applications matching filters
        
    Raises:
        HTTPException: If listing fails
    """
    try:
        logger.info(f"Listing applications with filters: stage={stage}, search={search}, date_from={date_from}, date_to={date_to}")
        
        filters = ApplicationFilters(
            stage=stage,
            search=search,
            date_from=date_from,
            date_to=date_to
        )
        
        applications = get_service().list_applications(filters)
        logger.info(f"Successfully listed {len(applications)} applications")
        return applications
        
    except ApplicationTrackerServiceError as e:
        logger.error(f"Failed to list applications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list applications: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error listing applications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while listing applications"
        )


@router.get("/export", response_class=StreamingResponse)
async def export_csv(
    stage: Optional[Stage] = Query(None, description="Filter by stage"),
    search: Optional[str] = Query(None, description="Search in company name or position title"),
    date_from: Optional[datetime] = Query(None, description="Filter applications from this date"),
    date_to: Optional[datetime] = Query(None, description="Filter applications until this date")
):
    """
    Export applications to a CSV file.
    
    Exports applications matching the provided filters.
    
    Args:
        stage: Optional stage filter
        search: Optional search query
        date_from: Optional start date filter
        date_to: Optional end date filter
        
    Returns:
        StreamingResponse: CSV file download
        
    Raises:
        HTTPException: If export fails
    """
    try:
        logger.info(f"Exporting applications to CSV with filters: stage={stage}, search={search}")
        
        filters = ApplicationFilters(
            stage=stage,
            search=search,
            date_from=date_from,
            date_to=date_to
        )
        
        csv_content = get_service().export_to_csv(filters)
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"applications_export_{timestamp}.csv"
        
        # Create streaming response
        output = io.BytesIO(csv_content.encode('utf-8'))
        
        logger.info(f"Successfully exported applications to CSV: {filename}")
        
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except ApplicationTrackerServiceError as e:
        logger.error(f"Failed to export applications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export applications: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error exporting applications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while exporting applications"
        )


@router.get("/{application_id}", response_model=Application)
async def get_application(application_id: str):
    """
    Retrieve a specific job application by ID.
    
    Args:
        application_id: UUID string of the application to retrieve
        
    Returns:
        Application: Application data
        
    Raises:
        HTTPException: If application not found or retrieval fails
    """
    try:
        logger.info(f"Retrieving application {application_id}")
        application = get_service().get_application(application_id)
        logger.info(f"Successfully retrieved application {application_id}")
        return application
        
    except ApplicationNotFoundError as e:
        logger.warning(f"Application not found: {application_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application not found: {application_id}"
        )
    except ApplicationTrackerServiceError as e:
        logger.error(f"Failed to retrieve application {application_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve application: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error retrieving application {application_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving application"
        )


@router.put("/{application_id}", response_model=Application)
async def update_application(application_id: str, request: UpdateApplicationRequest):
    """
    Update an existing job application.
    
    Args:
        application_id: UUID string of the application to update
        request: Update request with partial application data
        
    Returns:
        Application: Updated application data
        
    Raises:
        HTTPException: If application not found, validation fails, or update fails
    """
    try:
        logger.info(f"Updating application {application_id}")
        application = get_service().update_application(application_id, request)
        logger.info(f"Successfully updated application {application_id}")
        return application
        
    except ApplicationNotFoundError as e:
        logger.warning(f"Application not found for update: {application_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application not found: {application_id}"
        )
    except CVVersionNotFoundError as e:
        logger.warning(f"CV version not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ApplicationTrackerServiceError as e:
        logger.error(f"Failed to update application {application_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update application: {str(e)}"
        )
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error updating application {application_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating application"
        )


@router.delete("/{application_id}", response_model=DeleteResponse)
async def delete_application(application_id: str):
    """
    Delete a job application.
    
    Args:
        application_id: UUID string of the application to delete
        
    Returns:
        DeleteResponse: Deletion confirmation
        
    Raises:
        HTTPException: If application not found or deletion fails
    """
    try:
        logger.info(f"Deleting application {application_id}")
        response = get_service().delete_application(application_id)
        logger.info(f"Successfully deleted application {application_id}")
        return response
        
    except ApplicationNotFoundError as e:
        logger.warning(f"Application not found for deletion: {application_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application not found: {application_id}"
        )
    except ApplicationTrackerServiceError as e:
        logger.error(f"Failed to delete application {application_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete application: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error deleting application {application_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting application"
        )


@router.patch("/{application_id}/stage", response_model=Application)
async def change_stage(application_id: str, request: StageChangeRequest):
    """
    Change the stage of a job application.
    
    Creates a history entry recording the stage transition.
    
    Args:
        application_id: UUID string of the application
        request: Stage change request with new stage and optional notes
        
    Returns:
        Application: Updated application with new stage
        
    Raises:
        HTTPException: If application not found or stage change fails
    """
    try:
        logger.info(f"Changing stage for application {application_id} to {request.new_stage}")
        application = get_service().change_stage(application_id, request)
        logger.info(f"Successfully changed stage for application {application_id}")
        return application
        
    except ApplicationNotFoundError as e:
        logger.warning(f"Application not found for stage change: {application_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application not found: {application_id}"
        )
    except ApplicationTrackerServiceError as e:
        logger.error(f"Failed to change stage for application {application_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change stage: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error changing stage for application {application_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while changing stage"
        )


@router.post("/bulk/stage", response_model=BulkOperationResponse)
async def bulk_change_stage(request: BulkStageChangeRequest):
    """
    Change stage for multiple applications.
    
    Args:
        request: Bulk stage change request with application IDs and new stage
        
    Returns:
        BulkOperationResponse: Summary of successful and failed operations
        
    Raises:
        HTTPException: If bulk operation fails
    """
    try:
        logger.info(f"Bulk changing stage for {len(request.application_ids)} applications to {request.new_stage}")
        response = get_service().bulk_change_stage(request)
        logger.info(f"Bulk stage change completed: {len(response.successful)} successful, {len(response.failed)} failed")
        return response
        
    except ApplicationTrackerServiceError as e:
        logger.error(f"Failed to perform bulk stage change: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform bulk stage change: {str(e)}"
        )
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during bulk stage change: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during bulk stage change"
        )


@router.post("/bulk/delete", response_model=BulkOperationResponse)
async def bulk_delete(request: BulkDeleteRequest):
    """
    Delete multiple applications.
    
    Args:
        request: Bulk delete request with application IDs
        
    Returns:
        BulkOperationResponse: Summary of successful and failed operations
        
    Raises:
        HTTPException: If bulk operation fails
    """
    try:
        logger.info(f"Bulk deleting {len(request.application_ids)} applications")
        response = get_service().bulk_delete(request)
        logger.info(f"Bulk delete completed: {len(response.successful)} successful, {len(response.failed)} failed")
        return response
        
    except ApplicationTrackerServiceError as e:
        logger.error(f"Failed to perform bulk delete: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform bulk delete: {str(e)}"
        )
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during bulk delete: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during bulk delete"
        )


@router.get("/{application_id}/history", response_model=List[StatusHistoryEntry])
async def get_history(application_id: str):
    """
    Retrieve status history for an application.
    
    Args:
        application_id: UUID string of the application
        
    Returns:
        List[StatusHistoryEntry]: List of status history entries in chronological order
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        logger.info(f"Retrieving history for application {application_id}")
        history = get_service().get_history(application_id)
        logger.info(f"Successfully retrieved {len(history)} history entries for application {application_id}")
        return history
        
    except ApplicationTrackerServiceError as e:
        logger.error(f"Failed to retrieve history for application {application_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve history: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error retrieving history for application {application_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving history"
        )


@router.post("/import", response_model=ImportResponse, status_code=status.HTTP_201_CREATED)
async def import_csv(file: UploadFile = File(..., description="CSV file to import")):
    """
    Import applications from a CSV file.
    
    Expected CSV columns:
    - company_name (required)
    - position_title (required)
    - stage (optional, defaults to wishlist)
    - application_date (required, ISO 8601 format)
    - job_description_url (optional)
    - recruiter_name (optional)
    - recruiter_email (optional)
    - notes (optional)
    
    Args:
        file: Uploaded CSV file
        
    Returns:
        ImportResponse: Import summary with success/failure counts and errors
        
    Raises:
        HTTPException: If import fails or file is invalid
    """
    try:
        logger.info(f"Importing applications from CSV file: {file.filename}")
        
        # Validate file type
        if not file.filename or not file.filename.lower().endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a CSV file (.csv)"
            )
        
        # Read file content
        try:
            content = await file.read()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read file: {str(e)}"
            )
        
        # Import applications
        response = get_service().import_from_csv(content)
        logger.info(f"CSV import completed: {response.successful} successful, {response.failed} failed")
        return response
        
    except HTTPException:
        raise
    except ApplicationTrackerServiceError as e:
        logger.error(f"Failed to import CSV: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import CSV: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error importing CSV: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while importing CSV"
        )

