"""
CV Router

REST API endpoints for CV document management.
Provides CRUD operations for CV documents with proper error handling
and integration with CVService.
"""

from fastapi import APIRouter, HTTPException, status, File, UploadFile, Form, Query, Request
from typing import List, Optional
from datetime import datetime
from uuid import uuid4
import logging

from ..models.cv_models import (
    CVModelV2,
    CVCreateRequest, 
    CVUpdateRequest,
    CVUpdateRequestV2,
    CVListResponse, 
    CVResponse
)
from ..models.cv_section_models import (
    SectionType,
    Section,
    AddPredefinedSectionRequest,
    AddCustomSectionRequest,
    ReorderSectionsRequest,
    ToggleVisibilityRequest,
    SectionResponse,
    PersonalInfoContent,
    FreeTextSectionContent,
    ListSectionContent,
    ListItem,
    StructuredSectionContent,
    ExperienceEntry,
    EducationEntry,
    CertificationEntry
)
from ..services.cv_service import (
    CVService, 
    CVServiceError, 
    CVNotFoundError, 
    CVValidationError
)
from ..services.section_management_service import SectionManagementService
from ..services.import_service import (
    ImportService,
    ImportServiceError,
    MarkdownParseError,
    YAMLParseError,
    ContentParseError
)
from ..services.file_service import FileService, FileServiceError, FileNotFoundError

logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter(
    prefix="/api/cvs",
    tags=["CVs"],
    responses={404: {"description": "CV not found"}}
)

# Initialize CV service lazily to avoid directory creation during import
_cv_service = None
_import_service = None
_section_service = None
_file_service = None

def get_cv_service() -> CVService:
    """Get CV service instance with lazy initialization."""
    global _cv_service
    if _cv_service is None:
        _cv_service = CVService()
    return _cv_service

def get_import_service() -> ImportService:
    """Get import service instance with lazy initialization."""
    global _import_service
    if _import_service is None:
        _import_service = ImportService()
    return _import_service

def get_section_service() -> SectionManagementService:
    """Get section management service instance with lazy initialization."""
    global _section_service
    if _section_service is None:
        _section_service = SectionManagementService()
    return _section_service

def get_file_service() -> FileService:
    """Get file service instance with lazy initialization."""
    global _file_service
    if _file_service is None:
        _file_service = FileService()
    return _file_service


@router.get("", response_model=CVListResponse)
async def list_cvs():
    """
    List all CV documents.
    
    Returns:
        CVListResponse: List of all CVs with total count
        
    Raises:
        HTTPException: If listing fails
    """
    try:
        logger.info("Listing all CVs")
        result = get_cv_service().list_cvs()
        logger.info(f"Successfully listed {result.total} CVs")
        return result
        
    except CVServiceError as e:
        logger.error(f"Failed to list CVs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list CVs: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error listing CVs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while listing CVs"
        )


@router.post("", response_model=CVResponse, status_code=status.HTTP_201_CREATED)
async def create_cv(cv_request: CVCreateRequest):
    """
    Create a new CV document directly in V2 format with sections.
    
    Args:
        cv_request: CV creation request with CV data
        
    Returns:
        CVResponse: Created CV with success message
        
    Raises:
        HTTPException: If creation fails or validation errors occur
    """
    try:
        logger.info(f"Creating new CV in V2 format: {cv_request.metadata.title}")
        
        # Generate new CV ID
        cv_id = str(uuid4())
        now = datetime.utcnow()
        
        # Create sections list
        sections = []
        order = 0
        
        # 1. Personal Info Section (always first, always visible)
        personal_section = Section(
            id=str(uuid4()),
            type=SectionType.PERSONAL_INFO,
            title="Personal Information",
            visible=True,
            order=order,
            content=PersonalInfoContent(
                content_type="personal",
                cv_title=cv_request.metadata.title or None,
                full_name=cv_request.personal_info.name or "",
                email=cv_request.personal_info.contact.email or "",
                phone=cv_request.personal_info.contact.phone or None,
                location=cv_request.personal_info.contact.address or None,
                linkedin=cv_request.personal_info.contact.linkedin or None,
                website=cv_request.personal_info.contact.website or None,
                title=cv_request.personal_info.title or None
            )
        )
        sections.append(personal_section)
        order += 1
        # 2. Summary Section (if provided)
        if cv_request.summary and cv_request.summary.strip():
            summary_section = Section(
                id=str(uuid4()),
                type=SectionType.SUMMARY,
                title="Professional Summary",
                visible=True,
                order=order,
                content=FreeTextSectionContent(
                    content_type="free_text",
                    text=cv_request.summary
                )
            )
            sections.append(summary_section)
            order += 1
        
        # 3. Experience Section (if provided)
        if cv_request.experience:
            # Filter valid entries
            valid_experience = [
                exp for exp in cv_request.experience
                if exp.title and exp.company and exp.start_date
            ]
            if valid_experience:
                experience_entries = []
                for exp in valid_experience:
                    experience_entries.append(ExperienceEntry(
                        id=exp.id if hasattr(exp, 'id') and exp.id else str(uuid4()),
                        title=exp.title,
                        company=exp.company,
                        location=exp.location or None,
                        start_date=exp.start_date,
                        end_date=exp.end_date or None,
                        current=exp.current if hasattr(exp, 'current') else False,
                        description=exp.description or None,
                        achievements=exp.achievements if hasattr(exp, 'achievements') else []
                    ))
                
                experience_section = Section(
                    id=str(uuid4()),
                    type=SectionType.EXPERIENCE,
                    title="Work Experience",
                    visible=True,
                    order=order,
                    content=StructuredSectionContent(
                        content_type="structured",
                        entries=experience_entries
                    )
                )
                sections.append(experience_section)
                order += 1
        
        # 4. Education Section (if provided)
        if cv_request.education:
            # Filter valid entries
            valid_education = [
                edu for edu in cv_request.education
                if edu.degree and edu.institution
            ]
            if valid_education:
                education_entries = []
                for edu in valid_education:
                    education_entries.append(EducationEntry(
                        id=edu.id if hasattr(edu, 'id') and edu.id else str(uuid4()),
                        degree=edu.degree,
                        institution=edu.institution,
                        location=edu.location or None,
                        start_date=edu.start_date or None,
                        end_date=edu.end_date or None,
                        gpa=edu.gpa or None,
                        description=edu.description or None
                    ))
                
                education_section = Section(
                    id=str(uuid4()),
                    type=SectionType.EDUCATION,
                    title="Education",
                    visible=True,
                    order=order,
                    content=StructuredSectionContent(
                        content_type="structured",
                        entries=education_entries
                    )
                )
                sections.append(education_section)
                order += 1
        
        # 5. Skills Section (if provided)
        if cv_request.skills and cv_request.skills.categories:
            # Flatten all skills from all categories
            all_skills = []
            for category in cv_request.skills.categories:
                if hasattr(category, 'skills') and category.skills:
                    all_skills.extend(category.skills)
            
            if all_skills:
                skill_items = [ListItem(text=skill) for skill in all_skills if skill and skill.strip()]
                if skill_items:
                    skills_section = Section(
                        id=str(uuid4()),
                        type=SectionType.SKILLS,
                        title="Skills",
                        visible=True,
                        order=order,
                        content=ListSectionContent(
                            content_type="list",
                            items=skill_items
                        )
                    )
                    sections.append(skills_section)
                    order += 1
        
        # 6. Certifications Section (if provided)
        if cv_request.certifications:
            # Filter valid entries
            valid_certifications = [
                cert for cert in cv_request.certifications
                if cert.name and cert.issuer
            ]
            if valid_certifications:
                certification_entries = []
                for cert in valid_certifications:
                    certification_entries.append(CertificationEntry(
                        id=cert.id if hasattr(cert, 'id') and cert.id else str(uuid4()),
                        name=cert.name,
                        issuer=cert.issuer,
                        date=cert.date or None,
                        expiry_date=cert.expiry_date if hasattr(cert, 'expiry_date') else None,
                        credential_id=cert.credential_id if hasattr(cert, 'credential_id') else None
                    ))
                
                certifications_section = Section(
                    id=str(uuid4()),
                    type=SectionType.CERTIFICATIONS,
                    title="Certifications",
                    visible=True,
                    order=order,
                    content=StructuredSectionContent(
                        content_type="structured",
                        entries=certification_entries
                    )
                )
                sections.append(certifications_section)
                order += 1
        
        # Create V2 CV directly
        cv_v2 = CVModelV2(
            id=cv_id,
            version=2,
            created_at=now,
            updated_at=now,
            sections=sections
        )
        
        # Save V2 CV
        file_service = get_file_service()
        file_service.save_cv(cv_v2)
        
        logger.info(f"Successfully created CV {cv_v2.id} in V2 format with {len(cv_v2.sections)} sections")
        
        return CVResponse(
            cv=cv_v2,
            message=f"CV created successfully"
        )
        
    except CVValidationError as e:
        logger.warning(f"CV validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {str(e)}"
        )
    except CVServiceError as e:
        logger.error(f"Failed to create CV: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create CV: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error creating CV: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating CV"
        )


@router.get("/{cv_id}", response_model=CVResponse)
async def get_cv(cv_id: str):
    """
    Retrieve a specific CV document by ID.
    
    Args:
        cv_id: UUID string of the CV to retrieve
        
    Returns:
        CVResponse: CV data
        
    Raises:
        HTTPException: If CV not found or retrieval fails
    """
    try:
        logger.info(f"Retrieving CV {cv_id}")
        result = get_cv_service().get_cv(cv_id)
        logger.info(f"Successfully retrieved CV {cv_id}")
        return result
        
    except CVNotFoundError as e:
        logger.warning(f"CV not found: {cv_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV not found: {cv_id}"
        )
    except CVServiceError as e:
        logger.error(f"Failed to retrieve CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve CV: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error retrieving CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving CV"
        )


@router.put("/{cv_id}", response_model=CVResponse)
async def update_cv(cv_id: str, request: Request):
    """
    Update an existing CV document.
    
    Supports both V1 (legacy) and V2 (sections-based) CV formats.
    
    Args:
        cv_id: UUID string of the CV to update
        request: HTTP request containing CV update data
        
    Returns:
        CVResponse: Updated CV with success message
        
    Raises:
        HTTPException: If CV not found, validation fails, or update fails
    """
    try:
        logger.info(f"Updating CV {cv_id}")
        
        # Parse request body
        request_data = await request.json()
        logger.info(f"Request data keys: {list(request_data.keys())}")
        
        # Load existing CV to determine version
        file_service = get_file_service()
        try:
            existing_cv = file_service.load_cv(cv_id)
        except FileNotFoundError:
            logger.warning(f"CV not found: {cv_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"CV not found: {cv_id}"
            )
        
        logger.info(f"CV version: {getattr(existing_cv, 'version', 'N/A')}")
        
        # Check if this is a V2 CV
        if hasattr(existing_cv, 'version') and existing_cv.version == 2:
            # V2 CV - check if request contains sections (V2 format)
            if 'sections' in request_data:
                logger.info("Processing as V2 update (sections-based)")
                # Parse as V2 update request
                cv_request = CVUpdateRequestV2(**request_data)
                update_data = cv_request.model_dump(exclude_unset=True)
                
                # Update sections if provided
                if 'sections' in update_data and update_data['sections'] is not None:
                    existing_cv.sections = [Section(**s) if isinstance(s, dict) else s for s in update_data['sections']]
                
                # Update typography if provided
                if 'typography' in update_data and update_data['typography'] is not None:
                    existing_cv.typography = update_data['typography']
                
                # Update timestamp
                existing_cv.updated_at = datetime.utcnow()
                
                # Save updated CV
                file_service.save_cv(existing_cv)
                
                # Get name from personal info section for logging
                cv_title = "Untitled CV"
                personal_section = existing_cv.get_section_by_type(SectionType.PERSONAL_INFO)
                if personal_section and hasattr(personal_section.content, 'full_name'):
                    cv_title = personal_section.content.full_name or "Untitled CV"
                
                logger.info(f"Successfully updated V2 CV {cv_id}: {cv_title}")
                
                return CVResponse(
                    cv=existing_cv,
                    message=f"CV '{cv_title}' updated successfully"
                )
            else:
                # V1-style update request on V2 CV - not supported
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot apply V1 update format to V2 CV. Please use sections-based update."
                )
        else:
            # V1 CV - parse as V1 update request and use legacy update service
            cv_request = CVUpdateRequest(**request_data)
            result = get_cv_service().update_cv(cv_id, cv_request)
            
            # Get name from personal info section for logging
            cv_title = "Untitled CV"
            personal_section = result.cv.get_section_by_type(SectionType.PERSONAL_INFO)
            if personal_section and hasattr(personal_section.content, 'full_name'):
                cv_title = personal_section.content.full_name or "Untitled CV"
            
            logger.info(f"Successfully updated CV {cv_id}: {cv_title}")
            return result
        
    except HTTPException:
        raise
    except CVNotFoundError as e:
        logger.warning(f"CV not found for update: {cv_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV not found: {cv_id}"
        )
    except CVValidationError as e:
        logger.warning(f"CV update validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {str(e)}"
        )
    except CVServiceError as e:
        logger.error(f"Failed to update CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update CV: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error updating CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating CV"
        )


@router.delete("/{cv_id}", response_model=CVResponse)
async def delete_cv(cv_id: str):
    """
    Delete a CV document.
    
    Args:
        cv_id: UUID string of the CV to delete
        
    Returns:
        CVResponse: Deleted CV data with success message
        
    Raises:
        HTTPException: If CV not found or deletion fails
    """
    try:
        logger.info(f"Deleting CV {cv_id}")
        result = get_cv_service().delete_cv(cv_id)
        
        # Get name from personal info section for logging
        cv_title = "Untitled CV"
        personal_section = result.cv.get_section_by_type(SectionType.PERSONAL_INFO)
        if personal_section and hasattr(personal_section.content, 'full_name'):
            cv_title = personal_section.content.full_name or "Untitled CV"
        
        logger.info(f"Successfully deleted CV {cv_id}: {cv_title}")
        return result
        
    except CVNotFoundError as e:
        logger.warning(f"CV not found for deletion: {cv_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV not found: {cv_id}"
        )
    except CVServiceError as e:
        logger.error(f"Failed to delete CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete CV: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error deleting CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting CV"
        )


@router.post("/{cv_id}/duplicate", response_model=CVResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_cv(
    cv_id: str,
    title: Optional[str] = Query(None, description="Title for the copy; defaults to '<name> (copy)'")
):
    """
    Create an independent copy of a CV.

    Every id is regenerated, so editing the copy cannot affect the original.
    Typography and the applied template are carried over, since a duplicate is
    usually the start of a variation on the same design.

    Args:
        cv_id: UUID of the CV to copy
        title: Optional title for the copy

    Returns:
        CVResponse: The new CV

    Raises:
        HTTPException: If the CV does not exist or the copy cannot be saved
    """
    try:
        logger.info(f"Duplicating CV {cv_id}")
        cv_service = get_cv_service()
        return cv_service.duplicate_cv(cv_id, title)

    except CVNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV not found: {cv_id}"
        )
    except CVServiceError as e:
        logger.error(f"Failed to duplicate CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not duplicate that CV. The server log has the details."
        )


@router.post("/import", response_model=CVResponse, status_code=status.HTTP_201_CREATED)
async def import_cv(
    file: UploadFile = File(..., description="Markdown CV file to import"),
    title: Optional[str] = Form(None, description="Optional title override for the imported CV")
):
    """
    Import a CV from a Markdown file.
    
    Args:
        file: Uploaded Markdown file with YAML frontmatter
        title: Optional title override for the CV
        
    Returns:
        CVResponse: Imported CV with success message
        
    Raises:
        HTTPException: If import fails or validation errors occur
    """
    try:
        logger.info(f"Importing CV from file: {file.filename}")
        
        # Validate file type
        if not file.filename or not file.filename.lower().endswith(('.md', '.markdown')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a Markdown file (.md or .markdown)"
            )
        
        # Read file content
        try:
            content = await file.read()
            markdown_content = content.decode('utf-8')
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be valid UTF-8 encoded text"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read file: {str(e)}"
            )
        
        # Import CV using import service
        try:
            import_service = get_import_service()
            cv_model = import_service.import_from_markdown(markdown_content, title)
        except MarkdownParseError as e:
            logger.warning(f"Markdown parsing failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Markdown parsing error: {str(e)}"
            )
        except YAMLParseError as e:
            logger.warning(f"YAML parsing failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"YAML frontmatter error: {str(e)}"
            )
        except ContentParseError as e:
            logger.warning(f"Content parsing failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Content parsing error: {str(e)}"
            )
        except ImportServiceError as e:
            logger.error(f"Import service error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Import failed: {str(e)}"
            )
        
        # Save imported CV in V2 (sections) format
        try:
            # Create CV request from imported model
            cv_request = CVCreateRequest(
                metadata=cv_model.metadata,
                personal_info=cv_model.personal_info,
                summary=cv_model.summary,
                experience=cv_model.experience,
                education=cv_model.education,
                skills=cv_model.skills,
                certifications=cv_model.certifications
            )
            
            # Reuse the V2 creation path so the imported CV is stored as CVModelV2
            result = await create_cv(cv_request)
            
            # Get name from personal info section for logging
            cv_title = "Untitled CV"
            personal_section = result.cv.get_section_by_type(SectionType.PERSONAL_INFO)
            if personal_section and hasattr(personal_section.content, 'full_name'):
                cv_title = personal_section.content.full_name or "Untitled CV"
            
            logger.info(f"Successfully imported CV {result.cv.id}: {cv_title}")
            
            return CVResponse(
                cv=result.cv,
                message=f"CV '{cv_title}' imported successfully from {file.filename}"
            )
            
        except CVValidationError as e:
            logger.warning(f"CV validation failed after import: {e}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Imported CV validation error: {str(e)}"
            )
        except CVServiceError as e:
            logger.error(f"Failed to save imported CV: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save imported CV: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error importing CV: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while importing CV"
        )



# ============================================================================
# Section Management Endpoints
# ============================================================================

@router.post("/{cv_id}/sections/predefined", response_model=SectionResponse, status_code=status.HTTP_201_CREATED)
async def add_predefined_section(
    cv_id: str,
    request: AddPredefinedSectionRequest
):
    """
    Add a predefined section to a CV.
    
    Args:
        cv_id: UUID string of the CV
        request: Request containing the section type to add
        
    Returns:
        SectionResponse: Created section with success message
        
    Raises:
        HTTPException: If CV not found, section already exists, or operation fails
    """
    try:
        logger.info(f"Adding predefined section {request.section_type} to CV {cv_id}")
        
        # Load CV
        file_service = get_file_service()
        cv_data = file_service.load_cv(cv_id)
        
        # Add section using service
        section_service = get_section_service()
        section = section_service.add_predefined_section(cv_data, request.section_type)
        
        # Update the updated_at timestamp
        cv_data.updated_at = datetime.utcnow()
        
        # Save updated CV
        file_service.save_cv(cv_data)
        
        logger.info(f"Successfully added section {section.id} to CV {cv_id}")
        
        return SectionResponse(
            section=section,
            message=f"Section '{section.title}' added successfully"
        )
        
    except ValueError as e:
        logger.warning(f"Validation error adding section to CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except FileNotFoundError:
        logger.warning(f"CV not found: {cv_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV not found: {cv_id}"
        )
    except FileServiceError as e:
        logger.error(f"File service error adding section to CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error adding section to CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while adding section"
        )


@router.post("/{cv_id}/sections/custom", response_model=SectionResponse, status_code=status.HTTP_201_CREATED)
async def add_custom_section(
    cv_id: str,
    request: AddCustomSectionRequest
):
    """
    Add a custom section with user-defined title to a CV.
    
    Args:
        cv_id: UUID string of the CV
        request: Request containing the custom section title
        
    Returns:
        SectionResponse: Created section with success message
        
    Raises:
        HTTPException: If CV not found, title invalid, or operation fails
    """
    try:
        logger.info(f"Adding custom section '{request.title}' to CV {cv_id}")
        
        # Load CV
        file_service = get_file_service()
        cv_data = file_service.load_cv(cv_id)
        
        # Add section using service
        section_service = get_section_service()
        section = section_service.add_custom_section(cv_data, request.title)
        
        # Update the updated_at timestamp
        cv_data.updated_at = datetime.utcnow()
        
        # Save updated CV
        file_service.save_cv(cv_data)
        
        logger.info(f"Successfully added custom section {section.id} to CV {cv_id}")
        
        return SectionResponse(
            section=section,
            message=f"Custom section '{section.title}' added successfully"
        )
        
    except ValueError as e:
        logger.warning(f"Validation error adding custom section to CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except FileNotFoundError:
        logger.warning(f"CV not found: {cv_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV not found: {cv_id}"
        )
    except Exception as e:
        logger.error(f"Unexpected error adding custom section to CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while adding custom section"
        )


@router.delete("/{cv_id}/sections/{section_id}", status_code=status.HTTP_200_OK)
async def remove_section(
    cv_id: str,
    section_id: str
):
    """
    Remove a section from a CV.
    
    Args:
        cv_id: UUID string of the CV
        section_id: UUID string of the section to remove
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If CV not found, section not found, section is core, or operation fails
    """
    try:
        logger.info(f"Removing section {section_id} from CV {cv_id}")
        
        # Load CV
        file_service = get_file_service()
        cv_data = file_service.load_cv(cv_id)
        
        # Remove section using service
        section_service = get_section_service()
        section_service.remove_section(cv_data, section_id)
        
        # Update the updated_at timestamp
        cv_data.updated_at = datetime.utcnow()
        
        # Save updated CV
        file_service.save_cv(cv_data)
        
        logger.info(f"Successfully removed section {section_id} from CV {cv_id}")
        
        return {"message": "Section removed successfully"}
        
    except ValueError as e:
        logger.warning(f"Validation error removing section from CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except FileNotFoundError:
        logger.warning(f"CV not found: {cv_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV not found: {cv_id}"
        )
    except Exception as e:
        logger.error(f"Unexpected error removing section from CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while removing section"
        )


@router.put("/{cv_id}/sections/order", status_code=status.HTTP_200_OK)
async def reorder_sections(
    cv_id: str,
    request: ReorderSectionsRequest
):
    """
    Update the order of sections in a CV.
    
    Args:
        cv_id: UUID string of the CV
        request: Request containing ordered list of section IDs
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If CV not found, section IDs invalid, or operation fails
    """
    try:
        logger.info(f"Reordering sections in CV {cv_id}")
        
        # Load CV
        file_service = get_file_service()
        cv_data = file_service.load_cv(cv_id)
        
        # Reorder sections using service
        section_service = get_section_service()
        section_service.reorder_sections(cv_data, request.section_ids)
        
        # Update the updated_at timestamp to trigger UI refresh
        cv_data.updated_at = datetime.utcnow()
        
        # Save updated CV
        file_service.save_cv(cv_data)
        
        logger.info(f"Successfully reordered sections in CV {cv_id}")
        
        return {"message": "Sections reordered successfully"}
        
    except ValueError as e:
        logger.warning(f"Validation error reordering sections in CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except FileNotFoundError:
        logger.warning(f"CV not found: {cv_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV not found: {cv_id}"
        )
    except Exception as e:
        logger.error(f"Unexpected error reordering sections in CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while reordering sections"
        )


@router.patch("/{cv_id}/sections/{section_id}/visibility", status_code=status.HTTP_200_OK)
async def toggle_section_visibility(
    cv_id: str,
    section_id: str,
    request: ToggleVisibilityRequest
):
    """
    Toggle the visibility of a section in a CV.
    
    Args:
        cv_id: UUID string of the CV
        section_id: UUID string of the section
        request: Request containing new visibility state
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If CV not found, section not found, or operation fails
    """
    try:
        logger.info(f"Toggling visibility of section {section_id} in CV {cv_id} to {request.visible}")
        
        # Load CV
        file_service = get_file_service()
        cv_data = file_service.load_cv(cv_id)
        
        # Toggle visibility using service
        section_service = get_section_service()
        section_service.toggle_visibility(cv_data, section_id, request.visible)
        
        # Update the updated_at timestamp
        cv_data.updated_at = datetime.utcnow()
        
        # Save updated CV
        file_service.save_cv(cv_data)
        
        logger.info(f"Successfully toggled visibility of section {section_id} in CV {cv_id}")
        
        return {"message": f"Section visibility updated to {request.visible}"}
        
    except ValueError as e:
        logger.warning(f"Validation error toggling section visibility in CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except FileNotFoundError:
        logger.warning(f"CV not found: {cv_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV not found: {cv_id}"
        )
    except Exception as e:
        logger.error(f"Unexpected error toggling section visibility in CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while toggling section visibility"
        )
