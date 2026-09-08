"""
Export Models

Pydantic models for export request/response handling and export format
validation. These models define the structure for export operations
and ensure proper validation of export parameters.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import uuid4

from pydantic import BaseModel, Field, validator


class ExportFormat(str, Enum):
    """Supported export formats."""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"


class ExportStatus(str, Enum):
    """Export operation status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ExportRequest(BaseModel):
    """Request model for CV export operations."""
    cv_id: str = Field(..., description="UUID of the CV to export")
    format: ExportFormat = Field(..., description="Export format")
    template_id: Optional[str] = Field(default="default", description="Template to use for export")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional export options")

    @validator('cv_id')
    def validate_cv_id(cls, v):
        """Validate CV ID format."""
        if not v or len(v.strip()) == 0:
            raise ValueError("CV ID cannot be empty")
        return v.strip()


class ExportResponse(BaseModel):
    """Response model for export operations."""
    export_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique export operation ID")
    cv_id: str = Field(..., description="UUID of the exported CV")
    format: ExportFormat = Field(..., description="Export format")
    status: ExportStatus = Field(default=ExportStatus.PENDING, description="Export status")
    file_path: Optional[str] = Field(None, description="Path to exported file (when completed)")
    download_url: Optional[str] = Field(None, description="URL to download exported file")
    created_at: datetime = Field(default_factory=datetime.now, description="Export creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Export completion timestamp")
    error_message: Optional[str] = Field(None, description="Error message if export failed")
    file_size: Optional[int] = Field(None, description="Size of exported file in bytes")


class ExportHistoryEntry(BaseModel):
    """Export history entry for tracking past exports."""
    export_id: str = Field(..., description="Unique export operation ID")
    cv_id: str = Field(..., description="UUID of the exported CV")
    cv_title: str = Field(..., description="Title of the CV at time of export")
    format: ExportFormat = Field(..., description="Export format")
    template_id: str = Field(..., description="Template used for export")
    file_name: str = Field(..., description="Name of the exported file")
    file_path: str = Field(..., description="Path to exported file")
    file_size: int = Field(..., description="Size of exported file in bytes")
    created_at: datetime = Field(..., description="Export creation timestamp")
    download_url: str = Field(..., description="URL to download the file")


class ExportHistoryResponse(BaseModel):
    """Response model for export history listing."""
    cv_id: str = Field(..., description="UUID of the CV")
    exports: list[ExportHistoryEntry] = Field(default_factory=list, description="List of export history entries")
    total: int = Field(default=0, description="Total number of exports")


class ExportError(BaseModel):
    """Export error details."""
    error_type: str = Field(..., description="Type of error (e.g., 'pandoc_error', 'template_error')")
    error_code: Optional[str] = Field(None, description="Specific error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[str] = Field(None, description="Detailed error information")
    suggestions: Optional[list[str]] = Field(default_factory=list, description="Suggested fixes")


class ExportOptions(BaseModel):
    """Export configuration options."""
    pdf_engine: Optional[str] = Field(default=None, description="PDF engine to use (xelatex, tectonic)")
    include_metadata: bool = Field(default=True, description="Include metadata in export")
    custom_variables: Optional[Dict[str, str]] = Field(default_factory=dict, description="Custom Pandoc variables")
    
    @validator('pdf_engine')
    def validate_pdf_engine(cls, v):
        """Validate PDF engine selection."""
        if v is not None and v not in ['xelatex', 'tectonic']:
            raise ValueError("PDF engine must be 'xelatex' or 'tectonic'")
        return v


class TemplateInfo(BaseModel):
    """Template information model."""
    template_id: str = Field(..., description="Unique template identifier")
    name: str = Field(..., description="Human-readable template name")
    description: Optional[str] = Field(None, description="Template description")
    supported_formats: list[ExportFormat] = Field(..., description="Formats supported by this template")
    preview_available: bool = Field(default=False, description="Whether preview is available")


class TemplateListResponse(BaseModel):
    """Response model for template listing."""
    templates: list[TemplateInfo] = Field(default_factory=list, description="Available templates")
    default_template: str = Field(default="default", description="Default template ID")


class ExportJobStatus(BaseModel):
    """Export job status for tracking long-running exports."""
    export_id: str = Field(..., description="Export operation ID")
    status: ExportStatus = Field(..., description="Current status")
    progress: Optional[float] = Field(None, description="Progress percentage (0-100)")
    stage: Optional[str] = Field(None, description="Current processing stage")
    started_at: datetime = Field(..., description="Job start time")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")


# Validation models for export pipeline
class PandocConfig(BaseModel):
    """Pandoc configuration for export operations."""
    input_format: str = Field(default="markdown+yaml_metadata_block+smart", description="Pandoc input format")
    output_format: str = Field(..., description="Pandoc output format")
    template_path: Optional[str] = Field(None, description="Path to template file")
    defaults_file: Optional[str] = Field(None, description="Path to defaults YAML file")
    lua_filters: list[str] = Field(default_factory=list, description="Lua filter files")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Pandoc variables")
    extra_args: list[str] = Field(default_factory=list, description="Additional Pandoc arguments")


class ExportMetrics(BaseModel):
    """Export operation metrics for monitoring."""
    export_id: str = Field(..., description="Export operation ID")
    processing_time: float = Field(..., description="Total processing time in seconds")
    file_size: int = Field(..., description="Output file size in bytes")
    pandoc_version: Optional[str] = Field(None, description="Pandoc version used")
    pdf_engine: Optional[str] = Field(None, description="PDF engine used (if applicable)")
    template_used: str = Field(..., description="Template ID used")
    success: bool = Field(..., description="Whether export succeeded")
    error_details: Optional[ExportError] = Field(None, description="Error details if failed")