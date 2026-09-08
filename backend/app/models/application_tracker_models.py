"""
Job Application Tracker Data Models

Pydantic models for job application tracking with validation for required fields,
email formats, URL formats, and date formats. These models define the data structure
for tracking job applications through various stages of the application process.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, HttpUrl


class Stage(str, Enum):
    """Application stage enumeration."""
    WISHLIST = "wishlist"
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"


class Interview(BaseModel):
    """Interview details for an application."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    date: datetime = Field(..., description="Interview date and time")
    type: str = Field(..., min_length=1, description="Interview type (phone, video, onsite, technical, etc.)")
    meeting_link: Optional[str] = Field(None, description="Meeting link for virtual interviews")
    notes: Optional[str] = Field(None, description="Notes about the interview")
    interviewer_name: Optional[str] = Field(None, description="Name of the interviewer")

    @field_validator('meeting_link')
    @classmethod
    def validate_meeting_link(cls, v: Optional[str]) -> Optional[str]:
        """Validate meeting link is a valid URL if provided."""
        if v is not None and v.strip():
            # Basic URL validation
            if not (v.startswith('http://') or v.startswith('https://')):
                raise ValueError('Meeting link must be a valid HTTP or HTTPS URL')
        return v


class StatusHistoryEntry(BaseModel):
    """Status history entry tracking stage transitions."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    application_id: str = Field(..., description="ID of the application this history belongs to")
    from_stage: Optional[Stage] = Field(None, description="Previous stage (None for initial creation)")
    to_stage: Stage = Field(..., description="New stage")
    timestamp: datetime = Field(default_factory=datetime.now, description="When the transition occurred")
    notes: Optional[str] = Field(None, description="Optional notes about the transition")


class Application(BaseModel):
    """Complete application data model."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    company_name: str = Field(..., min_length=1, description="Company name is required")
    position_title: str = Field(..., min_length=1, description="Position title is required")
    stage: Stage = Field(..., description="Current application stage")
    application_date: datetime = Field(..., description="Date when application was submitted or planned")
    created_at: datetime = Field(default_factory=datetime.now, description="When this record was created")
    updated_at: datetime = Field(default_factory=datetime.now, description="When this record was last updated")
    
    # Optional fields
    job_description_url: Optional[str] = Field(None, description="URL to the job posting")
    application_deadline: Optional[datetime] = Field(None, description="Application deadline date")
    
    # Contact information
    recruiter_name: Optional[str] = Field(None, description="Name of the recruiter")
    recruiter_email: Optional[str] = Field(None, description="Email of the recruiter")
    recruiter_phone: Optional[str] = Field(None, description="Phone number of the recruiter")
    hiring_manager_name: Optional[str] = Field(None, description="Name of the hiring manager")
    
    # Interviews
    interviews: List[Interview] = Field(default_factory=list, description="List of scheduled interviews")
    
    # Notes and tracking
    notes: Optional[str] = Field(None, description="Free-form notes about the application")
    tasks: List[str] = Field(default_factory=list, description="Task list for this application")
    
    # Outcome
    feedback: Optional[str] = Field(None, description="Feedback received from the company")
    outcome: Optional[str] = Field(None, description="Final outcome of the application")
    
    # CV association
    cv_version_id: Optional[str] = Field(None, description="ID of the CV version used for this application")
    
    # Follow-up
    follow_up_date: Optional[datetime] = Field(None, description="Date to follow up on this application")

    @field_validator('job_description_url')
    @classmethod
    def validate_job_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate job description URL format if provided."""
        if v is not None and v.strip():
            if not (v.startswith('http://') or v.startswith('https://')):
                raise ValueError('Job description URL must be a valid HTTP or HTTPS URL')
        return v

    @field_validator('recruiter_email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Validate email format if provided."""
        if v is not None and v.strip():
            # Basic email validation
            if '@' not in v or '.' not in v.split('@')[-1]:
                raise ValueError('Invalid email format')
        return v

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "company_name": "Example Corp",
                "position_title": "Senior Software Engineer",
                "stage": "interview",
                "application_date": "2024-01-15T10:00:00Z",
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-20T14:30:00Z",
                "job_description_url": "https://example.com/jobs/senior-engineer",
                "recruiter_email": "recruiter@example.com",
                "interviews": [
                    {
                        "id": "int-1",
                        "date": "2024-01-25T15:00:00Z",
                        "type": "video",
                        "meeting_link": "https://zoom.us/j/123456",
                        "notes": "Technical interview with team lead"
                    }
                ],
                "cv_version_id": "cv-uuid-here",
                "notes": "Referred by John Doe"
            }
        }


# Request/Response models for API endpoints

class CreateApplicationRequest(BaseModel):
    """Request model for creating a new application."""
    company_name: str = Field(..., min_length=1, description="Company name is required")
    position_title: str = Field(..., min_length=1, description="Position title is required")
    stage: Stage = Field(default=Stage.WISHLIST, description="Initial stage")
    application_date: datetime = Field(..., description="Application date")
    job_description_url: Optional[str] = None
    application_deadline: Optional[datetime] = None
    recruiter_name: Optional[str] = None
    recruiter_email: Optional[str] = None
    recruiter_phone: Optional[str] = None
    hiring_manager_name: Optional[str] = None
    interviews: List[Interview] = Field(default_factory=list)
    notes: Optional[str] = None
    tasks: List[str] = Field(default_factory=list)
    feedback: Optional[str] = None
    outcome: Optional[str] = None
    cv_version_id: Optional[str] = None
    follow_up_date: Optional[datetime] = None

    @field_validator('job_description_url')
    @classmethod
    def validate_job_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate job description URL format if provided."""
        if v is not None and v.strip():
            if not (v.startswith('http://') or v.startswith('https://')):
                raise ValueError('Job description URL must be a valid HTTP or HTTPS URL')
        return v

    @field_validator('recruiter_email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Validate email format if provided."""
        if v is not None and v.strip():
            if '@' not in v or '.' not in v.split('@')[-1]:
                raise ValueError('Invalid email format')
        return v


class UpdateApplicationRequest(BaseModel):
    """Request model for updating an existing application."""
    company_name: Optional[str] = Field(None, min_length=1)
    position_title: Optional[str] = Field(None, min_length=1)
    stage: Optional[Stage] = None
    application_date: Optional[datetime] = None
    job_description_url: Optional[str] = None
    application_deadline: Optional[datetime] = None
    recruiter_name: Optional[str] = None
    recruiter_email: Optional[str] = None
    recruiter_phone: Optional[str] = None
    hiring_manager_name: Optional[str] = None
    interviews: Optional[List[Interview]] = None
    notes: Optional[str] = None
    tasks: Optional[List[str]] = None
    feedback: Optional[str] = None
    outcome: Optional[str] = None
    cv_version_id: Optional[str] = None
    follow_up_date: Optional[datetime] = None

    @field_validator('job_description_url')
    @classmethod
    def validate_job_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate job description URL format if provided."""
        if v is not None and v.strip():
            if not (v.startswith('http://') or v.startswith('https://')):
                raise ValueError('Job description URL must be a valid HTTP or HTTPS URL')
        return v

    @field_validator('recruiter_email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Validate email format if provided."""
        if v is not None and v.strip():
            if '@' not in v or '.' not in v.split('@')[-1]:
                raise ValueError('Invalid email format')
        return v


class StageChangeRequest(BaseModel):
    """Request model for changing application stage."""
    new_stage: Stage = Field(..., description="New stage to transition to")
    notes: Optional[str] = Field(None, description="Optional notes about the stage change")


class BulkStageChangeRequest(BaseModel):
    """Request model for bulk stage changes."""
    application_ids: List[str] = Field(..., min_length=1, description="List of application IDs to update")
    new_stage: Stage = Field(..., description="New stage for all applications")


class BulkDeleteRequest(BaseModel):
    """Request model for bulk delete operations."""
    application_ids: List[str] = Field(..., min_length=1, description="List of application IDs to delete")


class BulkOperationResponse(BaseModel):
    """Response model for bulk operations."""
    successful: List[str] = Field(..., description="List of successfully processed application IDs")
    failed: List[dict] = Field(..., description="List of failed operations with error messages")
    
    class Config:
        json_schema_extra = {
            "example": {
                "successful": ["app-id-1", "app-id-2"],
                "failed": [
                    {"id": "app-id-3", "error": "Application not found"}
                ]
            }
        }


class ImportResponse(BaseModel):
    """Response model for CSV import operations."""
    total_rows: int = Field(..., description="Total number of rows in the CSV")
    successful: int = Field(..., description="Number of successfully imported applications")
    failed: int = Field(..., description="Number of failed imports")
    errors: List[dict] = Field(default_factory=list, description="List of errors with row numbers")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_rows": 10,
                "successful": 8,
                "failed": 2,
                "errors": [
                    {"row": 3, "error": "Missing required field: company_name"},
                    {"row": 7, "error": "Invalid date format"}
                ]
            }
        }


class ApplicationFilters(BaseModel):
    """Filter parameters for listing applications."""
    stage: Optional[Stage] = Field(None, description="Filter by stage")
    search: Optional[str] = Field(None, description="Search in company name or position title")
    date_from: Optional[datetime] = Field(None, description="Filter applications from this date")
    date_to: Optional[datetime] = Field(None, description="Filter applications until this date")


class DeleteResponse(BaseModel):
    """Response model for delete operations."""
    success: bool = Field(..., description="Whether the deletion was successful")
    message: str = Field(..., description="Status message")
