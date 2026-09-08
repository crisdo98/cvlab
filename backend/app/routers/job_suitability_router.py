"""
Job Suitability Router

REST API endpoints for analyzing CV suitability against job descriptions.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, status

from ..models.job_suitability_models import (
    JobSuitabilityRequest,
    JobSuitabilityResponse,
    JobSuitabilityResult
)
from ..services.cv_service import CVService, CVNotFoundError
from ..services.llm_service import get_llm_service
from ..llm.job_suitability_analyzer import JobSuitabilityAnalyzer
from ..llm.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/job-suitability",
    tags=["Job Suitability"],
    responses={404: {"description": "Not found"}}
)

# Initialize services lazily
_cv_service = None

def get_cv_service() -> CVService:
    """Get CV service instance with lazy initialization."""
    global _cv_service
    if _cv_service is None:
        _cv_service = CVService()
    return _cv_service


def get_llm_provider() -> BaseLLMProvider:
    """
    Get LLM provider instance from service.
    
    Returns:
        BaseLLMProvider instance
        
    Raises:
        HTTPException: If LLM is not configured or disabled
    """
    try:
        llm_service = get_llm_service()
        
        if not llm_service.is_enabled():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM features are disabled. Enable them in settings to use job suitability analysis."
            )
        
        # Check consent for external providers
        if llm_service.requires_consent() and not llm_service.has_consent():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User consent required for external LLM services. Please review and accept the privacy policy in settings."
            )
        
        return llm_service.get_provider()
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Failed to get LLM provider: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error getting LLM provider: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize LLM provider: {str(e)}"
        )


@router.post("/analyze-suitability", response_model=JobSuitabilityResponse)
async def analyze_job_suitability(
    request: JobSuitabilityRequest,
    provider: BaseLLMProvider = Depends(get_llm_provider)
) -> JobSuitabilityResponse:
    """
    Analyze CV suitability for a specific job.
    
    Provides detailed analysis including:
    - Overall suitability score (0-100)
    - Breakdown by category (Skills, Experience, Education, etc.)
    - Specific criteria with Yes/No/Partial assessments
    - Key strengths and critical gaps
    - Improvement suggestions
    
    Args:
        request: Job suitability request with CV ID and job description
        provider: LLM provider (injected)
        
    Returns:
        Detailed suitability analysis result
        
    Raises:
        HTTPException: If CV not found or analysis fails
    """
    try:
        logger.info(f"Analyzing job suitability for CV {request.cv_id}")
        
        # Get CV
        cv_service = get_cv_service()
        cv_response = cv_service.get_cv(request.cv_id)
        cv = cv_response.cv
        
        # Create analyzer
        analyzer = JobSuitabilityAnalyzer(provider)
        
        # Perform analysis
        result = await analyzer.analyze_suitability(cv, request)
        
        logger.info(
            f"Job suitability analysis complete for CV {request.cv_id}: "
            f"{result.overall_score:.1f}% match"
        )
        
        return JobSuitabilityResponse(
            result=result,
            message="Job suitability analysis completed successfully"
        )
        
    except CVNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV not found: {request.cv_id}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Job suitability analysis failed: {e}")
        
        # Extract error message if available
        error_detail = str(e)
        if hasattr(e, 'response') and hasattr(e.response, 'data'):
            error_detail = e.response.data.get('detail', str(e))
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job suitability analysis failed: {error_detail}"
        )


@router.get("/cv/{cv_id}/suitability-history")
async def get_suitability_history(cv_id: str):
    """
    Get job suitability analysis history for a CV.
    
    Note: This endpoint is a placeholder for future implementation.
    Currently returns empty history.
    
    Args:
        cv_id: CV identifier
        
    Returns:
        List of past suitability analyses
        
    Raises:
        HTTPException: If CV not found
    """
    try:
        logger.info(f"Getting suitability history for CV {cv_id}")
        
        # Verify CV exists
        cv_service = get_cv_service()
        cv_service.get_cv(cv_id)
        
        # TODO: Implement history storage and retrieval
        # For now, return empty history
        return {
            "cv_id": cv_id,
            "analyses": [],
            "total": 0,
            "message": "Suitability history feature coming soon"
        }
        
    except CVNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV not found: {cv_id}"
        )
    except Exception as e:
        logger.error(f"Failed to get suitability history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve suitability history"
        )
