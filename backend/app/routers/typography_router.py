"""
Typography Router

REST API endpoints for CV typography configuration and templates.
"""

import logging
from fastapi import APIRouter, HTTPException, status, Request
from typing import List, Optional

from ..models.typography_models import (
    TypographyTemplate,
    TypographyTemplateListResponse,
    TypographyConfig,
    TypographyUpdateRequest,
    TypographyResponse,
    TYPOGRAPHY_TEMPLATES
)
from ..services.cv_service import CVService, CVNotFoundError
from ..services.template_service import TemplateService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/typography",
    tags=["Typography"],
    responses={404: {"description": "Not found"}}
)

# Initialize services lazily
_cv_service = None
_template_service = None

def get_cv_service() -> CVService:
    """Get CV service instance with lazy initialization."""
    global _cv_service
    if _cv_service is None:
        _cv_service = CVService()
    return _cv_service

def get_template_service() -> TemplateService:
    """Get template service instance with lazy initialization."""
    global _template_service
    if _template_service is None:
        _template_service = TemplateService()
    return _template_service


@router.get("/templates", response_model=TypographyTemplateListResponse)
async def list_templates():
    """
    List all available typography templates (built-in and custom).
    
    Returns:
        List of typography templates with previews
    """
    try:
        logger.info("Listing typography templates")
        
        # Get built-in templates
        templates = list(TYPOGRAPHY_TEMPLATES.values())
        
        # Add custom templates
        template_service = get_template_service()
        custom_templates = template_service.list_custom_templates()
        templates.extend(custom_templates)
        
        return TypographyTemplateListResponse(
            templates=templates,
            total=len(templates)
        )
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list typography templates"
        )


@router.get("/templates/{template_id}", response_model=TypographyTemplate)
async def get_template(template_id: str):
    """
    Get a specific typography template by ID (built-in or custom).
    
    Args:
        template_id: Template identifier
        
    Returns:
        Typography template details
        
    Raises:
        HTTPException: If template not found
    """
    try:
        logger.info(f"Getting template: {template_id}")
        
        # Check built-in templates first
        if template_id in TYPOGRAPHY_TEMPLATES:
            return TYPOGRAPHY_TEMPLATES[template_id]
        
        # Check custom templates
        template_service = get_template_service()
        custom_template = template_service.get_custom_template(template_id)
        
        if custom_template:
            return custom_template
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve template"
        )


@router.put("/cv/{cv_id}/typography", response_model=TypographyResponse)
async def update_cv_typography(cv_id: str, typography: TypographyConfig):
    """
    Update typography configuration for a CV.
    
    Args:
        cv_id: CV identifier
        typography: New typography configuration
        
    Returns:
        Updated typography configuration
        
    Raises:
        HTTPException: If CV not found or update fails
    """
    try:
        logger.info(f"Updating typography for CV {cv_id}")
        logger.info(f"New typography: {typography.model_dump()}")
        
        from ..services.file_service import FileService
        from datetime import datetime
        
        file_service = FileService()
        
        # Load CV directly
        cv = file_service.load_cv(cv_id)
        
        logger.info(f"Loaded CV version: {getattr(cv, 'version', 'N/A')}")
        
        # Update typography directly on the CV object
        cv.typography = typography
        
        # Clear applied_template_id since this is custom typography (for V2 CVs)
        if hasattr(cv, 'version') and cv.version == 2:
            cv.applied_template_id = None
            cv.updated_at = datetime.utcnow()
        
        # Save the updated CV
        file_service.save_cv(cv)
        
        logger.info(f"Typography updated and saved for CV {cv_id}")
        
        return TypographyResponse(
            cv_id=cv_id,
            typography=typography,
            message="Typography updated successfully"
        )
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV not found: {cv_id}"
        )
    except Exception as e:
        logger.error(f"Failed to update typography for CV {cv_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update typography: {str(e)}"
        )


@router.post("/cv/{cv_id}/typography/apply-template", response_model=TypographyResponse)
async def apply_template_to_cv(cv_id: str, template_id: str):
    """
    Apply a typography template to a CV.
    
    Args:
        cv_id: CV identifier
        template_id: Template identifier to apply
        
    Returns:
        Updated typography configuration
        
    Raises:
        HTTPException: If CV or template not found
    """
    try:
        logger.info(f"Applying template {template_id} to CV {cv_id}")
        
        # Get template (check both built-in and custom)
        template = None
        if template_id in TYPOGRAPHY_TEMPLATES:
            template = TYPOGRAPHY_TEMPLATES[template_id]
        else:
            template_service = get_template_service()
            template = template_service.get_custom_template(template_id)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template not found: {template_id}"
            )
        typography = template.typography
        
        logger.info(f"Template typography: {typography.model_dump()}")
        
        # Load CV using file service directly to handle V2 CVs properly
        from ..services.file_service import FileService
        from datetime import datetime
        
        file_service = FileService()
        cv = file_service.load_cv(cv_id)
        
        logger.info(f"Loaded CV version: {getattr(cv, 'version', 'N/A')}")
        logger.info(f"Current typography before update: {getattr(cv, 'typography', None)}")
        
        # Apply template typography
        cv.typography = typography
        
        # Store which template was applied (for V2 CVs)
        if hasattr(cv, 'version') and cv.version == 2:
            cv.applied_template_id = template_id
            cv.updated_at = datetime.utcnow()
        
        # Save the updated CV
        file_service.save_cv(cv)
        
        logger.info(f"Template {template_id} applied and saved to CV {cv_id}")
        logger.info(f"Typography after save: {cv.typography.model_dump()}")
        
        return TypographyResponse(
            cv_id=cv_id,
            typography=typography,
            message=f"Template '{template.name}' applied successfully"
        )
        
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV not found: {cv_id}"
        )
    except Exception as e:
        logger.error(f"Failed to apply template to CV {cv_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply template: {str(e)}"
        )


@router.get("/cv/{cv_id}/typography", response_model=TypographyResponse)
async def get_cv_typography(cv_id: str):
    """
    Get typography configuration for a CV.
    
    Args:
        cv_id: CV identifier
        
    Returns:
        Current typography configuration
        
    Raises:
        HTTPException: If CV not found
    """
    try:
        logger.info(f"Getting typography for CV {cv_id}")
        
        cv_service = get_cv_service()
        cv_response = cv_service.get_cv(cv_id)
        cv = cv_response.cv
        
        # Return typography or default - works for both V1 and V2
        typography = getattr(cv, 'typography', None) or TypographyConfig()
        
        return TypographyResponse(
            cv_id=cv_id,
            typography=typography,
            message=None
        )
        
    except CVNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV not found: {cv_id}"
        )
    except Exception as e:
        logger.error(f"Failed to get typography for CV {cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve typography"
        )


@router.post("/templates/save", response_model=TypographyTemplate)
async def save_custom_template(name: str, description: str, typography: TypographyConfig):
    """
    Save custom typography configuration as a new template.
    
    Args:
        name: Template name
        description: Template description
        typography: Typography configuration to save
        
    Returns:
        Created template
        
    Raises:
        HTTPException: If save fails or template name already exists
    """
    try:
        logger.info(f"Saving custom template: {name}")
        
        template_service = get_template_service()
        
        # Save template (service will handle ID generation and uniqueness)
        new_template = template_service.save_template(
            name=name,
            description=description,
            typography=typography
        )
        
        logger.info(f"Custom template saved: {new_template.id}")
        
        return new_template
        
    except ValueError as e:
        # Template already exists
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to save custom template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save custom template"
        )


@router.put("/templates/{template_id}", response_model=TypographyTemplate)
async def update_custom_template(
    template_id: str,
    request: Request
):
    """
    Update an existing custom template.
    
    Args:
        template_id: Template identifier
        request: HTTP request with update data
        
    Returns:
        Updated template
        
    Raises:
        HTTPException: If template not found or update fails
    """
    try:
        logger.info(f"Updating custom template: {template_id}")
        
        # Parse request body
        update_data = await request.json()
        logger.info(f"Update data: {update_data.keys()}")
        
        template_service = get_template_service()
        
        # Extract fields from request
        name = update_data.get('name')
        description = update_data.get('description')
        typography_data = update_data.get('typography')
        
        # Parse typography if provided
        typography = None
        if typography_data:
            typography = TypographyConfig(**typography_data)
            logger.info(f"Typography config parsed successfully")
        
        # Update template
        updated_template = template_service.update_template(
            template_id=template_id,
            name=name,
            description=description,
            typography=typography
        )
        
        logger.info(f"Custom template updated: {template_id}")
        
        return updated_template
        
    except ValueError as e:
        # Template not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update custom template: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update custom template: {str(e)}"
        )


@router.delete("/templates/{template_id}")
async def delete_custom_template(template_id: str):
    """
    Delete a custom template.
    
    Args:
        template_id: Template identifier
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If template not found or is a built-in template
    """
    try:
        logger.info(f"Deleting custom template: {template_id}")
        
        # Prevent deletion of built-in templates
        if template_id in TYPOGRAPHY_TEMPLATES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete built-in templates"
            )
        
        template_service = get_template_service()
        template_service.delete_template(template_id)
        
        logger.info(f"Custom template deleted: {template_id}")
        
        return {"message": f"Template '{template_id}' deleted successfully"}
        
    except ValueError as e:
        # Template not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete custom template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete custom template"
        )

