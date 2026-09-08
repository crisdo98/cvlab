"""
Export Router

REST API endpoints for CV export operations.
Provides export functionality with proper error handling and integration
with ExportService and CVService.
"""

from fastapi import APIRouter, HTTPException, status, Response
from fastapi.responses import FileResponse
from typing import List, Optional
from pydantic import BaseModel, Field
import logging
import os
from pathlib import Path
from datetime import datetime

from ..models.export_models import (
    ExportRequest,
    ExportResponse, 
    ExportHistoryResponse,
    ExportHistoryEntry,
    ExportFormat,
    ExportStatus,
    TemplateListResponse,
    TemplateInfo
)
from ..routers.llm_router import get_llm_provider
from ..services.recommendations_report import build_report
from ..services.export_service import (
    ExportService,
    ExportServiceError,
    PandocError,
    LaTeXError,
    PDFEngineError,
    ValidationError
)
from ..services.cv_service import (
    CVService,
    CVServiceError,
    CVNotFoundError
)
from ..services.cleanup_service import (
    CleanupService,
    CleanupServiceError,
    CleanupResult,
    CleanupConfig
)

logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter(
    prefix="/api/export",
    tags=["Export"],
    responses={404: {"description": "Resource not found"}}
)

# Initialize services lazily to avoid directory creation during import
_export_service = None
_cv_service = None
_cleanup_service = None

def get_export_service() -> ExportService:
    """Get export service instance with lazy initialization."""
    global _export_service
    if _export_service is None:
        # Use container-appropriate paths
        root_dir = "/app"
        export_script_path = "/app/scripts/export.sh"
        _export_service = ExportService(
            root_dir=root_dir,
            export_script_path=export_script_path
        )
    return _export_service

def get_cv_service() -> CVService:
    """Get CV service instance with lazy initialization."""
    global _cv_service
    if _cv_service is None:
        _cv_service = CVService()
    return _cv_service

def get_cleanup_service() -> CleanupService:
    """Get cleanup service instance with lazy initialization."""
    global _cleanup_service
    if _cleanup_service is None:
        _cleanup_service = CleanupService()
    return _cleanup_service


class RecommendationsExportRequest(BaseModel):
    """What to assess when exporting a CV with its recommendations."""

    include_ats: bool = Field(True, description="Include the ATS assessment")
    include_grammar: bool = Field(False, description="Include language findings")
    industry: Optional[str] = Field(None, description="Target industry for keyword matching")
    job_title: Optional[str] = Field(None, description="Target role; defaults to the CV's current one")
    job_description: Optional[str] = Field(
        None,
        description="When given, the CV is also assessed against this specific role"
    )


@router.post(
    "/{cv_id}/recommendations/{format}",
    response_model=ExportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def export_cv_with_recommendations(
    cv_id: str,
    format: ExportFormat,
    options: RecommendationsExportRequest = RecommendationsExportRequest(),
):
    """
    Export a CV followed by its assessment and recommendations.

    The assessment is appended as Markdown and goes through the same pandoc
    pipeline as the CV, so it inherits the document's typography instead of
    arriving as a separate artefact.

    An analysis that fails is reported in the document rather than failing the
    export: a CV with two of three assessments is more useful than no file.

    Args:
        cv_id: UUID string of the CV to export
        format: Export format (pdf, docx, txt)
        options: Which assessments to run

    Returns:
        ExportResponse: Export operation details with download information

    Raises:
        HTTPException: If the CV is not found or the export itself fails
    """
    try:
        logger.info(f"Exporting CV {cv_id} with recommendations to {format}")

        cv_data = get_cv_service().get_cv(cv_id).cv

        ats_result = None
        grammar_result = None
        suitability_result = None
        failures: List[str] = []

        cv_payload = cv_data.model_dump(mode="json")

        if options.include_ats:
            try:
                from ..llm.ats_analyzer import ATSAnalyzer
                from ..models.llm_models import ATSAnalysisRequest

                analyzer = ATSAnalyzer(get_llm_provider())
                ats_result = await analyzer.analyze_ats_compatibility(
                    ATSAnalysisRequest(
                        cv_id=cv_id,
                        cv_data=cv_payload,
                        industry=options.industry,
                        job_title=options.job_title,
                    )
                )
            except Exception as exc:
                logger.warning(f"ATS assessment failed for {cv_id}: {exc}")
                failures.append(f"The ATS assessment could not be produced: {exc}")

        if options.include_grammar:
            try:
                from ..llm.grammar_checker import GrammarChecker
                from ..models.llm_models import GrammarCheckRequest

                checker = GrammarChecker(get_llm_provider())
                grammar_result = await checker.check_grammar(
                    GrammarCheckRequest(cv_id=cv_id, cv_data=cv_payload)
                )
            except Exception as exc:
                logger.warning(f"Grammar check failed for {cv_id}: {exc}")
                failures.append(f"The language check could not be produced: {exc}")

        if options.job_description:
            try:
                from ..llm.job_suitability_analyzer import JobSuitabilityAnalyzer
                from ..models.job_suitability_models import JobSuitabilityRequest

                analyzer = JobSuitabilityAnalyzer(get_llm_provider())
                suitability_result = await analyzer.analyze_suitability(
                    cv_data,
                    JobSuitabilityRequest(
                        cv_id=cv_id,
                        job_description=options.job_description,
                        job_title=options.job_title,
                    ),
                )
            except Exception as exc:
                logger.warning(f"Suitability analysis failed for {cv_id}: {exc}")
                failures.append(f"The role assessment could not be produced: {exc}")

        appendix = build_report(
            ats=ats_result,
            grammar=grammar_result,
            suitability=suitability_result,
        )

        if failures:
            notes = "\n".join(f"- {failure}" for failure in failures)
            if appendix:
                appendix = f"{appendix}\n## Not assessed\n\n{notes}\n"
            else:
                appendix = (
                    "\\newpage\n\n# Assessment and recommendations\n\n"
                    f"## Not assessed\n\n{notes}\n"
                )

        export_request = ExportRequest(cv_id=cv_id, format=format, template_id="default")

        export_service = get_export_service()
        validation_error = export_service.validate_export_request(export_request)
        if validation_error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=validation_error.message,
            )

        export_response = export_service.export_cv(
            cv_data, export_request, appendix_markdown=appendix or None
        )

        if export_response.status == ExportStatus.COMPLETED:
            return export_response

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {export_response.error_message}",
        )

    except HTTPException:
        raise
    except CVNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV not found: {cv_id}",
        )
    except Exception as exc:
        logger.error(f"Recommendations export failed for {cv_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not export the CV with recommendations. The server log has the details.",
        )


@router.post("/{cv_id}/{format}", response_model=ExportResponse, status_code=status.HTTP_201_CREATED)
async def export_cv(cv_id: str, format: ExportFormat):
    """
    Export a CV to the specified format.
    
    Args:
        cv_id: UUID string of the CV to export
        format: Export format (pdf, docx, txt)
        
    Returns:
        ExportResponse: Export operation details with download information
        
    Raises:
        HTTPException: If CV not found, export fails, or validation errors occur
    """
    try:
        logger.info(f"Starting export of CV {cv_id} to {format} format")
        
        # Get CV data
        cv_response = get_cv_service().get_cv(cv_id)
        cv_data = cv_response.cv
        
        # Use default template (typography is embedded in CV data)
        template_id = "default"
        
        # Create export request
        export_request = ExportRequest(
            cv_id=cv_id,
            format=format,
            template_id=template_id
        )
        
        # Validate export request
        export_service = get_export_service()
        validation_error = export_service.validate_export_request(export_request)
        if validation_error:
            logger.warning(f"Export validation failed: {validation_error.message}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=validation_error.message
            )
        
        # Perform export
        export_response = export_service.export_cv(cv_data, export_request)
        
        if export_response.status == ExportStatus.COMPLETED:
            logger.info(f"Successfully exported CV {cv_id} to {format}")
            return export_response
        else:
            logger.error(f"Export failed for CV {cv_id}: {export_response.error_message}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Export failed: {export_response.error_message}"
            )
            
    except CVNotFoundError:
        logger.warning(f"CV not found for export: {cv_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV not found: {cv_id}"
        )
    except PandocError as e:
        logger.error(f"Pandoc error during export: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export processing error: {str(e)}"
        )
    except (LaTeXError, PDFEngineError) as e:
        logger.error(f"PDF generation error during export: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation error: {str(e)}"
        )
    except ValidationError as e:
        logger.error(f"Validation error during export: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {str(e)}"
        )
    except ExportServiceError as e:
        logger.error(f"Export service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export service error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during export: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during export"
        )


@router.get("/history/{cv_id}", response_model=ExportHistoryResponse)
async def get_export_history(cv_id: str):
    """
    Get export history for a specific CV.
    
    Args:
        cv_id: UUID string of the CV
        
    Returns:
        ExportHistoryResponse: List of previous exports for the CV
        
    Raises:
        HTTPException: If CV not found or history retrieval fails
    """
    try:
        logger.info(f"Retrieving export history for CV {cv_id}")
        
        # Verify CV exists
        cv_response = get_cv_service().get_cv(cv_id)
        cv = cv_response.cv
        
        # Get title - handle both V1 (metadata.title) and V2 (no metadata)
        if hasattr(cv, 'metadata') and cv.metadata:
            cv_title = cv.metadata.title
        else:
            # For V2, try to get name from personal info section
            from ..models.cv_section_models import SectionType
            personal_section = cv.get_section_by_type(SectionType.PERSONAL_INFO) if hasattr(cv, 'get_section_by_type') else None
            if personal_section and hasattr(personal_section.content, 'full_name'):
                cv_title = personal_section.content.full_name
            else:
                cv_title = f"CV {cv.id[:8]}"
        
        # Get export service and find export files
        export_service = get_export_service()
        exports_dir = export_service.exports_dir
        
        history_entries = []
        
        # Scan export directories for files related to this CV
        for format_dir in exports_dir.iterdir():
            if format_dir.is_dir() and format_dir.name in [f.value for f in ExportFormat]:
                format_name = format_dir.name
                
                # Look for files that might belong to this CV
                # This is a simplified approach - in a production system, 
                # you'd want to maintain a proper export history database
                for export_file in format_dir.glob("*.{}".format(format_name)):
                    if export_file.is_file():
                        # Extract timestamp from filename if possible
                        file_stat = export_file.stat()
                        
                        # Create history entry
                        history_entry = ExportHistoryEntry(
                            export_id=f"{cv_id}_{format_name}_{int(file_stat.st_mtime)}",
                            cv_id=cv_id,
                            cv_title=cv_title,
                            format=ExportFormat(format_name),
                            template_id="default",  # TODO: Track template used
                            file_name=export_file.name,
                            file_path=str(export_file),
                            file_size=file_stat.st_size,
                            created_at=datetime.fromtimestamp(file_stat.st_mtime),
                            download_url=f"/api/export/download/{export_file.name}"
                        )
                        history_entries.append(history_entry)
        
        # Sort by creation date (newest first)
        history_entries.sort(key=lambda x: x.created_at, reverse=True)
        
        response = ExportHistoryResponse(
            cv_id=cv_id,
            exports=history_entries,
            total=len(history_entries)
        )
        
        logger.info(f"Retrieved {len(history_entries)} export history entries for CV {cv_id}")
        return response
        
    except CVNotFoundError:
        logger.warning(f"CV not found for export history: {cv_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV not found: {cv_id}"
        )
    except Exception as e:
        logger.error(f"Unexpected error retrieving export history for CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving export history"
        )


@router.get("/download/{file_id}")
async def download_export_file(file_id: str):
    """
    Download an exported file.
    
    Args:
        file_id: Filename or identifier of the exported file
        
    Returns:
        FileResponse: The exported file for download
        
    Raises:
        HTTPException: If file not found or download fails
    """
    try:
        logger.info(f"Downloading export file: {file_id}")
        
        export_service = get_export_service()
        exports_dir = export_service.exports_dir
        
        # Security: Only allow downloading from export directories
        # and prevent path traversal attacks
        if ".." in file_id or "/" in file_id or "\\" in file_id:
            logger.warning(f"Invalid file_id attempted: {file_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file identifier"
            )
        
        # Search for the file in all format directories
        file_path = None
        for format_dir in exports_dir.iterdir():
            if format_dir.is_dir():
                potential_file = format_dir / file_id
                if potential_file.exists() and potential_file.is_file():
                    file_path = potential_file
                    break
        
        if not file_path:
            logger.warning(f"Export file not found: {file_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Export file not found: {file_id}"
            )
        
        # Determine media type based on file extension
        media_type_map = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".txt": "text/plain"
        }
        
        file_extension = file_path.suffix.lower()
        media_type = media_type_map.get(file_extension, "application/octet-stream")
        
        logger.info(f"Serving export file: {file_path}")
        
        return FileResponse(
            path=str(file_path),
            media_type=media_type,
            filename=file_path.name
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error downloading file {file_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while downloading the file"
        )


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates():
    """
    List available export templates.
    
    Returns:
        TemplateListResponse: List of available templates
        
    Raises:
        HTTPException: If template listing fails
    """
    try:
        logger.info("Listing available export templates")
        
        export_service = get_export_service()
        templates_data = export_service.get_available_templates()
        
        templates = [
            TemplateInfo(
                template_id=template["template_id"],
                name=template["name"],
                description=template.get("description", ""),
                supported_formats=template["supported_formats"],
                preview_available=template.get("preview_available", False)
            )
            for template in templates_data
        ]
        
        response = TemplateListResponse(
            templates=templates,
            default_template="default"
        )
        
        logger.info(f"Listed {len(templates)} available templates")
        return response
        
    except Exception as e:
        logger.error(f"Unexpected error listing templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while listing templates"
        )


@router.post("/cleanup")
async def cleanup_exports(dry_run: bool = False):
    """
    Perform cleanup of old export files.
    
    Args:
        dry_run: If True, only simulate cleanup without deleting files
        
    Returns:
        CleanupResult: Results of the cleanup operation
        
    Raises:
        HTTPException: If cleanup fails
    """
    try:
        logger.info(f"Starting manual export cleanup (dry_run={dry_run})")
        
        cleanup_service = get_cleanup_service()
        result = cleanup_service.cleanup_exports(dry_run=dry_run)
        
        logger.info(f"Manual cleanup completed: {result.files_deleted} files processed")
        return result
        
    except CleanupServiceError as e:
        logger.error(f"Cleanup service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cleanup failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during cleanup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during cleanup"
        )


@router.get("/cleanup/config")
async def get_cleanup_config():
    """
    Get current cleanup configuration.
    
    Returns:
        CleanupConfig: Current cleanup configuration
        
    Raises:
        HTTPException: If config retrieval fails
    """
    try:
        cleanup_service = get_cleanup_service()
        config = cleanup_service.get_config()
        
        return {
            "retention_days": config.retention_days,
            "max_files_per_format": config.max_files_per_format,
            "cleanup_interval_hours": config.cleanup_interval_hours,
            "enabled": config.enabled,
            "dry_run": config.dry_run
        }
        
    except Exception as e:
        logger.error(f"Unexpected error getting cleanup config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while getting cleanup configuration"
        )


@router.put("/cleanup/config")
async def update_cleanup_config(
    retention_days: Optional[int] = None,
    max_files_per_format: Optional[int] = None,
    cleanup_interval_hours: Optional[int] = None,
    enabled: Optional[bool] = None,
    dry_run: Optional[bool] = None
):
    """
    Update cleanup configuration.
    
    Args:
        retention_days: Number of days to retain export files
        max_files_per_format: Maximum number of files per format
        cleanup_interval_hours: Hours between scheduled cleanups
        enabled: Whether cleanup is enabled
        dry_run: Whether to run in dry-run mode
        
    Returns:
        Updated cleanup configuration
        
    Raises:
        HTTPException: If config update fails
    """
    try:
        cleanup_service = get_cleanup_service()
        
        # Build update parameters
        update_params = {}
        if retention_days is not None:
            update_params['retention_days'] = retention_days
        if max_files_per_format is not None:
            update_params['max_files_per_format'] = max_files_per_format
        if cleanup_interval_hours is not None:
            update_params['cleanup_interval_hours'] = cleanup_interval_hours
        if enabled is not None:
            update_params['enabled'] = enabled
        if dry_run is not None:
            update_params['dry_run'] = dry_run
        
        if not update_params:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No configuration parameters provided"
            )
        
        config = cleanup_service.update_config(**update_params)
        
        logger.info(f"Updated cleanup configuration: {update_params}")
        
        return {
            "retention_days": config.retention_days,
            "max_files_per_format": config.max_files_per_format,
            "cleanup_interval_hours": config.cleanup_interval_hours,
            "enabled": config.enabled,
            "dry_run": config.dry_run
        }
        
    except CleanupServiceError as e:
        logger.error(f"Cleanup service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update configuration: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error updating cleanup config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating cleanup configuration"
        )


@router.get("/cleanup/stats")
async def get_export_statistics():
    """
    Get statistics about export files.
    
    Returns:
        Dictionary with export file statistics
        
    Raises:
        HTTPException: If statistics retrieval fails
    """
    try:
        cleanup_service = get_cleanup_service()
        stats = cleanup_service.get_export_statistics()
        
        return stats
        
    except CleanupServiceError as e:
        logger.error(f"Cleanup service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error getting export statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while getting export statistics"
        )


@router.get("/files/{file_path:path}/validate")
async def validate_export_file(file_path: str):
    """
    Validate export file integrity and format.
    
    Args:
        file_path: Path to the file to validate (relative to exports directory)
        
    Returns:
        Validation results
        
    Raises:
        HTTPException: If validation fails
    """
    try:
        logger.info(f"Validating export file: {file_path}")
        
        cleanup_service = get_cleanup_service()
        validation_result = cleanup_service.validate_export_file(file_path)
        
        return validation_result
        
    except Exception as e:
        logger.error(f"Unexpected error validating file {file_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while validating the file"
        )


@router.delete("/files/{file_path:path}")
async def delete_export_file(file_path: str):
    """
    Delete a specific export file.
    
    Args:
        file_path: Path to the file to delete (relative to exports directory)
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If file deletion fails
    """
    try:
        logger.info(f"Deleting export file: {file_path}")
        
        cleanup_service = get_cleanup_service()
        success = cleanup_service.delete_export_file(file_path)
        
        if success:
            return {"message": f"Successfully deleted file: {file_path}"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {file_path}"
            )
        
    except CleanupServiceError as e:
        logger.error(f"Cleanup service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting file {file_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the file"
        )