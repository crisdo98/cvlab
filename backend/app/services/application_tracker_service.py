"""
Application Tracker Service Layer

Business logic layer for job application tracking. Handles validation, stage transitions,
history tracking, CSV import/export, and CV version integration. Coordinates between
storage layer and API endpoints.
"""

import csv
import io
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import uuid4
import logging

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
from .application_tracker_storage import (
    ApplicationTrackerStorage,
    ApplicationNotFoundError,
    ApplicationStorageError
)
from .cv_service import CVService, CVNotFoundError

logger = logging.getLogger(__name__)


class ApplicationTrackerServiceError(Exception):
    """Base exception for application tracker service operations."""
    pass


class CVVersionNotFoundError(ApplicationTrackerServiceError):
    """Raised when a referenced CV version doesn't exist."""
    pass


class ApplicationTrackerService:
    """
    Service layer for job application tracking.
    
    Provides business logic for application management including CRUD operations,
    stage transitions with history tracking, bulk operations, and CSV import/export.
    """
    
    def __init__(
        self,
        storage: Optional[ApplicationTrackerStorage] = None,
        cv_service: Optional[CVService] = None
    ):
        """
        Initialize ApplicationTrackerService with dependencies.
        
        Args:
            storage: ApplicationTrackerStorage instance for data persistence
            cv_service: CVService instance for CV version validation (optional)
        """
        self.storage = storage or ApplicationTrackerStorage()
        # CV service is optional - only used for validation if provided
        self.cv_service = cv_service
    
    def create_application(self, data: CreateApplicationRequest) -> Application:
        """
        Create a new application with generated ID, timestamps, and initial history entry.
        
        Args:
            data: Application creation request
            
        Returns:
            Created Application instance
            
        Raises:
            CVVersionNotFoundError: If CV version doesn't exist
            ApplicationTrackerServiceError: If creation fails
        """
        try:
            # Validate CV version if provided
            if data.cv_version_id:
                self.validate_cv_version_exists(data.cv_version_id)
            
            # Generate UUID and timestamps
            app_id = str(uuid4())
            now = datetime.now()
            
            # Create application instance
            application = Application(
                id=app_id,
                company_name=data.company_name,
                position_title=data.position_title,
                stage=data.stage,
                application_date=data.application_date,
                created_at=now,
                updated_at=now,
                job_description_url=data.job_description_url,
                application_deadline=data.application_deadline,
                recruiter_name=data.recruiter_name,
                recruiter_email=data.recruiter_email,
                recruiter_phone=data.recruiter_phone,
                hiring_manager_name=data.hiring_manager_name,
                interviews=data.interviews,
                notes=data.notes,
                tasks=data.tasks,
                feedback=data.feedback,
                outcome=data.outcome,
                cv_version_id=data.cv_version_id,
                follow_up_date=data.follow_up_date
            )
            
            # Save application
            created_app = self.storage.create_application(application)
            
            # Create initial history entry
            history_entry = StatusHistoryEntry(
                id=str(uuid4()),
                application_id=app_id,
                from_stage=None,  # None for initial creation
                to_stage=data.stage,
                timestamp=now,
                notes="Application created"
            )
            self.storage.add_history_entry(history_entry)
            
            logger.info(
                f"Created application {app_id}: {data.company_name} - {data.position_title}"
            )
            
            return created_app
            
        except CVVersionNotFoundError:
            raise
        except ApplicationStorageError as e:
            raise ApplicationTrackerServiceError(f"Failed to create application: {e}")
        except Exception as e:
            raise ApplicationTrackerServiceError(f"Unexpected error creating application: {e}")
    
    def get_application(self, application_id: str) -> Application:
        """
        Retrieve a single application by ID.
        
        Args:
            application_id: UUID string of the application
            
        Returns:
            Application instance
            
        Raises:
            ApplicationNotFoundError: If application doesn't exist
            ApplicationTrackerServiceError: If retrieval fails
        """
        try:
            return self.storage.get_application(application_id)
        except ApplicationNotFoundError:
            raise
        except ApplicationStorageError as e:
            raise ApplicationTrackerServiceError(f"Failed to retrieve application: {e}")
    
    def list_applications(self, filters: Optional[ApplicationFilters] = None) -> List[Application]:
        """
        List applications with optional filtering by stage, search, and date range.
        
        Args:
            filters: Optional filters for stage, search query, and date range
            
        Returns:
            List of Application instances matching filters
            
        Raises:
            ApplicationTrackerServiceError: If listing fails
        """
        try:
            return self.storage.list_applications(filters)
        except ApplicationStorageError as e:
            raise ApplicationTrackerServiceError(f"Failed to list applications: {e}")
    
    def update_application(
        self,
        application_id: str,
        data: UpdateApplicationRequest
    ) -> Application:
        """
        Update an existing application, preserving ID and created_at timestamp.
        
        Args:
            application_id: UUID string of the application to update
            data: Update request with partial application data
            
        Returns:
            Updated Application instance
            
        Raises:
            ApplicationNotFoundError: If application doesn't exist
            CVVersionNotFoundError: If CV version doesn't exist
            ApplicationTrackerServiceError: If update fails
        """
        try:
            # Get existing application
            existing_app = self.storage.get_application(application_id)
            
            # Validate CV version if being updated
            if data.cv_version_id is not None:
                self.validate_cv_version_exists(data.cv_version_id)
            
            # Update fields that are provided
            update_dict = data.model_dump(exclude_unset=True)
            
            # Preserve ID and created_at
            update_dict['id'] = existing_app.id
            update_dict['created_at'] = existing_app.created_at
            update_dict['updated_at'] = datetime.now()
            
            # Merge with existing data
            app_dict = existing_app.model_dump()
            app_dict.update(update_dict)
            
            # Create updated application
            updated_app = Application(**app_dict)
            
            # Save updated application
            result = self.storage.update_application(application_id, updated_app)
            
            logger.info(f"Updated application {application_id}")
            
            return result
            
        except (ApplicationNotFoundError, CVVersionNotFoundError):
            raise
        except ApplicationStorageError as e:
            raise ApplicationTrackerServiceError(f"Failed to update application: {e}")
        except Exception as e:
            raise ApplicationTrackerServiceError(f"Unexpected error updating application: {e}")
    
    def delete_application(self, application_id: str) -> DeleteResponse:
        """
        Delete an application permanently.
        
        Args:
            application_id: UUID string of the application to delete
            
        Returns:
            DeleteResponse with success status
            
        Raises:
            ApplicationNotFoundError: If application doesn't exist
            ApplicationTrackerServiceError: If deletion fails
        """
        try:
            self.storage.delete_application(application_id)
            logger.info(f"Deleted application {application_id}")
            return DeleteResponse(
                success=True,
                message=f"Application {application_id} deleted successfully"
            )
        except ApplicationNotFoundError:
            raise
        except ApplicationStorageError as e:
            raise ApplicationTrackerServiceError(f"Failed to delete application: {e}")
    
    def change_stage(
        self,
        application_id: str,
        request: StageChangeRequest
    ) -> Application:
        """
        Change application stage and create history entry.
        
        Args:
            application_id: UUID string of the application
            request: Stage change request with new stage and optional notes
            
        Returns:
            Updated Application instance
            
        Raises:
            ApplicationNotFoundError: If application doesn't exist
            ApplicationTrackerServiceError: If stage change fails
        """
        try:
            # Get existing application
            existing_app = self.storage.get_application(application_id)
            old_stage = existing_app.stage
            
            # Update stage
            existing_app.stage = request.new_stage
            existing_app.updated_at = datetime.now()
            
            # Save updated application
            updated_app = self.storage.update_application(application_id, existing_app)
            
            # Create history entry
            history_entry = StatusHistoryEntry(
                id=str(uuid4()),
                application_id=application_id,
                from_stage=old_stage,
                to_stage=request.new_stage,
                timestamp=datetime.now(),
                notes=request.notes
            )
            self.storage.add_history_entry(history_entry)
            
            logger.info(
                f"Changed stage for application {application_id}: {old_stage} -> {request.new_stage}"
            )
            
            return updated_app
            
        except ApplicationNotFoundError:
            raise
        except ApplicationStorageError as e:
            raise ApplicationTrackerServiceError(f"Failed to change stage: {e}")
        except Exception as e:
            raise ApplicationTrackerServiceError(f"Unexpected error changing stage: {e}")
    
    def bulk_change_stage(self, request: BulkStageChangeRequest) -> BulkOperationResponse:
        """
        Change stage for multiple applications.
        
        Args:
            request: Bulk stage change request with application IDs and new stage
            
        Returns:
            BulkOperationResponse with successful and failed operations
        """
        successful = []
        failed = []
        
        for app_id in request.application_ids:
            try:
                stage_request = StageChangeRequest(new_stage=request.new_stage)
                self.change_stage(app_id, stage_request)
                successful.append(app_id)
            except ApplicationNotFoundError:
                failed.append({"id": app_id, "error": "Application not found"})
            except Exception as e:
                failed.append({"id": app_id, "error": str(e)})
        
        logger.info(
            f"Bulk stage change: {len(successful)} successful, {len(failed)} failed"
        )
        
        return BulkOperationResponse(successful=successful, failed=failed)
    
    def bulk_delete(self, request: BulkDeleteRequest) -> BulkOperationResponse:
        """
        Delete multiple applications.
        
        Args:
            request: Bulk delete request with application IDs
            
        Returns:
            BulkOperationResponse with successful and failed operations
        """
        successful = []
        failed = []
        
        for app_id in request.application_ids:
            try:
                self.delete_application(app_id)
                successful.append(app_id)
            except ApplicationNotFoundError:
                failed.append({"id": app_id, "error": "Application not found"})
            except Exception as e:
                failed.append({"id": app_id, "error": str(e)})
        
        logger.info(
            f"Bulk delete: {len(successful)} successful, {len(failed)} failed"
        )
        
        return BulkOperationResponse(successful=successful, failed=failed)
    
    def get_history(self, application_id: str) -> List[StatusHistoryEntry]:
        """
        Retrieve status history for an application.
        
        Args:
            application_id: UUID string of the application
            
        Returns:
            List of StatusHistoryEntry instances in chronological order
            
        Raises:
            ApplicationTrackerServiceError: If retrieval fails
        """
        try:
            return self.storage.get_application_history(application_id)
        except ApplicationStorageError as e:
            raise ApplicationTrackerServiceError(f"Failed to retrieve history: {e}")
    
    def import_from_csv(self, file_content: bytes) -> ImportResponse:
        """
        Parse CSV file and create applications for valid entries.
        
        Expected CSV columns:
        - company_name (required)
        - position_title (required)
        - stage (optional, defaults to wishlist)
        - application_date (required, ISO 8601 format)
        - job_description_url (optional)
        - recruiter_name (optional)
        - recruiter_email (optional)
        - notes (optional)
        - cv_version_id (optional)
        
        Args:
            file_content: CSV file content as bytes
            
        Returns:
            ImportResponse with import summary and errors
        """
        successful = 0
        failed = 0
        errors = []
        
        try:
            # Decode CSV content
            csv_text = file_content.decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(csv_text))
            
            total_rows = 0
            
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (header is row 1)
                total_rows += 1
                
                try:
                    # Validate required fields
                    if not row.get('company_name') or not row['company_name'].strip():
                        raise ValueError("Missing required field: company_name")
                    
                    if not row.get('position_title') or not row['position_title'].strip():
                        raise ValueError("Missing required field: position_title")
                    
                    if not row.get('application_date') or not row['application_date'].strip():
                        raise ValueError("Missing required field: application_date")
                    
                    # Parse application date
                    try:
                        app_date = datetime.fromisoformat(row['application_date'].replace('Z', '+00:00'))
                    except ValueError:
                        raise ValueError("Invalid date format for application_date. Expected ISO 8601 format.")
                    
                    # Parse stage (default to wishlist)
                    stage_str = row.get('stage', 'wishlist').strip().lower()
                    try:
                        stage = Stage(stage_str)
                    except ValueError:
                        raise ValueError(f"Invalid stage: {stage_str}. Must be one of: wishlist, applied, interview, offer, rejected")
                    
                    # Create application request
                    app_request = CreateApplicationRequest(
                        company_name=row['company_name'].strip(),
                        position_title=row['position_title'].strip(),
                        stage=stage,
                        application_date=app_date,
                        job_description_url=row.get('job_description_url', '').strip() or None,
                        recruiter_name=row.get('recruiter_name', '').strip() or None,
                        recruiter_email=row.get('recruiter_email', '').strip() or None,
                        notes=row.get('notes', '').strip() or None,
                        cv_version_id=row.get('cv_version_id', '').strip() or None
                    )
                    
                    # Create application
                    self.create_application(app_request)
                    successful += 1
                    
                except ValueError as e:
                    failed += 1
                    errors.append({"row": row_num, "error": str(e)})
                except Exception as e:
                    failed += 1
                    errors.append({"row": row_num, "error": f"Unexpected error: {str(e)}"})
            
            logger.info(
                f"CSV import completed: {total_rows} total, {successful} successful, {failed} failed"
            )
            
            return ImportResponse(
                total_rows=total_rows,
                successful=successful,
                failed=failed,
                errors=errors
            )
            
        except UnicodeDecodeError:
            raise ApplicationTrackerServiceError("Invalid CSV file encoding. Expected UTF-8.")
        except csv.Error as e:
            raise ApplicationTrackerServiceError(f"CSV parsing error: {e}")
        except Exception as e:
            raise ApplicationTrackerServiceError(f"Import failed: {e}")
    
    def export_to_csv(self, filters: Optional[ApplicationFilters] = None) -> str:
        """
        Generate CSV content from applications matching filters.
        
        Args:
            filters: Optional filters to apply before export
            
        Returns:
            CSV content as string
            
        Raises:
            ApplicationTrackerServiceError: If export fails
        """
        try:
            # Get applications
            applications = self.list_applications(filters)
            
            # Create CSV in memory
            output = io.StringIO()
            
            # Define CSV columns
            fieldnames = [
                'id',
                'company_name',
                'position_title',
                'stage',
                'application_date',
                'created_at',
                'updated_at',
                'job_description_url',
                'application_deadline',
                'recruiter_name',
                'recruiter_email',
                'recruiter_phone',
                'hiring_manager_name',
                'notes',
                'feedback',
                'outcome',
                'cv_version_id',
                'follow_up_date'
            ]
            
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            # Write application data
            for app in applications:
                row = {
                    'id': app.id,
                    'company_name': app.company_name,
                    'position_title': app.position_title,
                    'stage': app.stage.value,
                    'application_date': app.application_date.isoformat(),
                    'created_at': app.created_at.isoformat(),
                    'updated_at': app.updated_at.isoformat(),
                    'job_description_url': app.job_description_url or '',
                    'application_deadline': app.application_deadline.isoformat() if app.application_deadline else '',
                    'recruiter_name': app.recruiter_name or '',
                    'recruiter_email': app.recruiter_email or '',
                    'recruiter_phone': app.recruiter_phone or '',
                    'hiring_manager_name': app.hiring_manager_name or '',
                    'notes': app.notes or '',
                    'feedback': app.feedback or '',
                    'outcome': app.outcome or '',
                    'cv_version_id': app.cv_version_id or '',
                    'follow_up_date': app.follow_up_date.isoformat() if app.follow_up_date else ''
                }
                writer.writerow(row)
            
            csv_content = output.getvalue()
            output.close()
            
            logger.info(f"Exported {len(applications)} applications to CSV")
            
            return csv_content
            
        except ApplicationStorageError as e:
            raise ApplicationTrackerServiceError(f"Failed to export applications: {e}")
        except Exception as e:
            raise ApplicationTrackerServiceError(f"Unexpected error during export: {e}")
    
    def validate_cv_version_exists(self, cv_version_id: str) -> bool:
        """
        Check if a CV version exists via the existing CV service.
        
        Args:
            cv_version_id: UUID string of the CV version
            
        Returns:
            True if CV version exists
            
        Raises:
            CVVersionNotFoundError: If CV version doesn't exist
        """
        # If CV service is not available, skip validation
        if self.cv_service is None:
            logger.info(f"CV service not available, skipping validation for CV version {cv_version_id}")
            return True
            
        try:
            self.cv_service.get_cv(cv_version_id)
            return True
        except CVNotFoundError:
            raise CVVersionNotFoundError(f"CV version not found: {cv_version_id}")
        except Exception as e:
            # Log but don't fail - allow association even if CV service has issues
            logger.warning(f"Could not validate CV version {cv_version_id}: {e}")
            return True
