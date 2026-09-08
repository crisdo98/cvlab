"""
LLM Router

REST API endpoints for LLM-powered features including content generation,
CV optimization, job tailoring, grammar checking, ATS analysis, and AI parsing.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse

from app.models.llm_models import (
    # Content Generation
    ContentGenerationRequest,
    ContentGenerationResult,
    NoteExpansionRequest,
    AchievementGenerationRequest,
    SummaryGenerationRequest,
    # CV Optimization
    OptimizationRequest,
    OptimizationResult,
    # Job Tailoring
    JobTailoringRequest,
    JobTailoringResult,
    JobURLParseRequest,
    JobURLParseResult,
    TailoredCVRequest,
    TailoredCVResult,
    TailoringLevel,
    # Job Matching
    JobMatchRequest,
    JobMatchResult,
    # Grammar Checking
    GrammarCheckRequest,
    GrammarCheckResult,
    # ATS Analysis
    ATSAnalysisRequest,
    ATSAnalysisResult,
    # AI Parsing
    AIParsingRequest,
    AIParsingResult,
    # Configuration
    LLMConfig,
    LLMConfigRequest,
    LLMConfigResponse,
    LLMProviderType
)
from app.llm.content_generator import ContentGenerator
from app.llm.cv_optimizer import CVOptimizer
from app.llm.ats_analyzer import ATSAnalyzer
from app.llm.grammar_checker import GrammarChecker
from app.llm.ai_parser import AIParser
from app.llm.providers.base import BaseLLMProvider
from app.services.cv_service import CVService
from app.services.file_service import FileService
from app.services.llm_service import get_llm_service
from app.services.job_parser import get_job_parser, URLAccessError, ContentExtractionError
from app.utils.llm_error_recovery import (
    retry_with_exponential_backoff,
    execute_with_timeout,
    get_graceful_degradation,
    LLMErrorClassifier,
    LLMErrorType
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/llm", tags=["LLM"])


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
                detail="LLM features are disabled. Enable them in settings."
            )
        
        # Check consent for external providers
        if llm_service.requires_consent() and not llm_service.has_consent():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User consent required for external LLM services. Please review and accept the privacy policy in settings."
            )
        
        return llm_service.get_provider()
        
    except HTTPException:
        # Re-raise HTTPExceptions as-is
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


async def execute_llm_request_with_recovery(
    request_fn: Callable,
    operation_name: str,
    timeout_seconds: float = 60.0,
    enable_retry: bool = True
) -> Any:
    """
    Execute LLM request with error recovery mechanisms.
    
    Provides:
    - Automatic retry with exponential backoff
    - Timeout handling
    - Graceful degradation with fallbacks
    - Detailed error classification
    
    Args:
        request_fn: Async function to execute
        operation_name: Name of operation for logging/fallback
        timeout_seconds: Timeout in seconds
        enable_retry: Whether to enable retry logic
        
    Returns:
        Result from request or fallback
        
    Raises:
        HTTPException: With appropriate status code and error details
    """
    error_classifier = LLMErrorClassifier()
    degradation = get_graceful_degradation()
    
    try:
        # Wrap request with timeout
        async def timed_request():
            return await execute_with_timeout(
                request_fn,
                timeout_seconds=timeout_seconds
            )
        
        # Execute with retry if enabled
        if enable_retry:
            result = await retry_with_exponential_backoff(
                timed_request,
                error_classifier=error_classifier
            )
        else:
            result = await timed_request()
        
        return result
        
    except Exception as e:
        # Classify error
        error_type = error_classifier.classify_error(e)
        logger.error(f"LLM request failed for {operation_name}: {error_type} - {e}")
        
        # Try to get fallback response
        fallback = degradation.get_fallback(operation_name)
        if fallback is not None:
            logger.info(f"Returning fallback response for {operation_name}")
            return fallback
        
        # Map error type to HTTP status and message
        status_code, detail = _map_error_to_http(error_type, str(e))
        
        raise HTTPException(
            status_code=status_code,
            detail=detail
        )


def _map_error_to_http(error_type: LLMErrorType, error_message: str) -> tuple[int, str]:
    """
    Map LLM error type to HTTP status code and message.
    
    Args:
        error_type: Classified error type
        error_message: Original error message
        
    Returns:
        Tuple of (status_code, detail_message)
    """
    error_mappings = {
        LLMErrorType.RATE_LIMIT: (
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Rate limit exceeded. Please wait a moment and try again."
        ),
        LLMErrorType.TIMEOUT: (
            status.HTTP_504_GATEWAY_TIMEOUT,
            "Request timed out. Please try again with shorter input or check your connection."
        ),
        LLMErrorType.INVALID_API_KEY: (
            status.HTTP_401_UNAUTHORIZED,
            "Authentication failed. Your API credentials may be invalid, expired, or not configured. Please check your LLM settings and update your credentials."
        ),
        LLMErrorType.QUOTA_EXCEEDED: (
            status.HTTP_402_PAYMENT_REQUIRED,
            "API quota exceeded. Please check your billing settings."
        ),
        LLMErrorType.MODEL_NOT_FOUND: (
            status.HTTP_404_NOT_FOUND,
            "Requested AI model not found. Please check your LLM configuration."
        ),
        LLMErrorType.SERVICE_UNAVAILABLE: (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "LLM service temporarily unavailable. Please try again later."
        ),
        LLMErrorType.INVALID_REQUEST: (
            status.HTTP_400_BAD_REQUEST,
            f"Invalid request: {error_message}"
        ),
        LLMErrorType.PROVIDER_ERROR: (
            status.HTTP_502_BAD_GATEWAY,
            "LLM provider encountered an error. Please try again."
        ),
        LLMErrorType.NETWORK_ERROR: (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Network error connecting to LLM service. Please check your connection."
        ),
        LLMErrorType.UNKNOWN: (
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Unexpected error: {error_message}"
        )
    }
    
    return error_mappings.get(
        error_type,
        (status.HTTP_500_INTERNAL_SERVER_ERROR, f"Error: {error_message}")
    )


# ============================================================================
# Content Generation Endpoints
# ============================================================================

@router.post("/generate-content", response_model=ContentGenerationResult)
async def generate_content(
    request: ContentGenerationRequest
) -> ContentGenerationResult:
    """
    Generate content suggestions for CV sections.
    
    Generates contextually appropriate professional content based on section type
    and provided context. Returns multiple variations for user selection.
    """
    try:
        provider = get_llm_provider()
        
        generator = ContentGenerator(provider)
        
        # Route to appropriate generation method based on section type
        if request.section_type == "summary":
            # Extract summary-specific context
            summary_request = SummaryGenerationRequest(
                job_title=request.context.get("job_title", "Professional"),
                years_experience=request.context.get("years_experience", 0),
                skills=request.context.get("skills", []),
                industry=request.context.get("industry"),
                career_level=request.context.get("career_level"),
                num_variations=request.num_variations
            )
            result = await generator.generate_summary(summary_request)
        
        elif request.section_type == "experience":
            result = await generator.generate_experience_description(
                job_title=request.context.get("job_title", ""),
                company=request.context.get("company", ""),
                duration=request.context.get("duration", ""),
                responsibilities=request.context.get("responsibilities", ""),
                skills=request.context.get("skills", []),
                num_variations=request.num_variations
            )
        
        elif request.section_type == "education":
            result = await generator.generate_education_description(
                degree=request.context.get("degree", ""),
                institution=request.context.get("institution", ""),
                field_of_study=request.context.get("field_of_study"),
                achievements=request.context.get("achievements"),
                coursework=request.context.get("coursework"),
                num_variations=request.num_variations
            )
        
        elif request.section_type == "skills_summary":
            result = await generator.generate_skills_summary(
                technical_skills=request.context.get("technical_skills", []),
                soft_skills=request.context.get("soft_skills", []),
                years_experience=request.context.get("years_experience", 0),
                industry=request.context.get("industry"),
                num_variations=request.num_variations
            )
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported section type: {request.section_type}"
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Content generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Content generation failed: {str(e)}"
        )


@router.post("/expand-notes", response_model=ContentGenerationResult)
async def expand_notes(
    request: NoteExpansionRequest
) -> ContentGenerationResult:
    """
    Expand brief notes into full professional descriptions.
    
    Takes brief bullet points or notes and expands them into well-written
    professional descriptions suitable for CV content.
    """
    try:
        provider = get_llm_provider()
        
        generator = ContentGenerator(provider)
        result = await generator.expand_notes(request)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Note expansion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Note expansion failed: {str(e)}"
        )


@router.post("/generate-achievements", response_model=ContentGenerationResult)
async def generate_achievements(
    request: AchievementGenerationRequest
) -> ContentGenerationResult:
    """
    Generate achievement statements from descriptions or notes.
    
    Creates quantifiable achievement statements following best practices
    (action verb + metric + impact).
    """
    try:
        provider = get_llm_provider()
        
        generator = ContentGenerator(provider)
        result = await generator.generate_achievements(request)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Achievement generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Achievement generation failed: {str(e)}"
        )


# ============================================================================
# CV Optimization Endpoints
# ============================================================================

@router.post("/optimize-cv", response_model=OptimizationResult)
async def optimize_cv(
    request: OptimizationRequest
) -> OptimizationResult:
    """
    Analyze CV and provide optimization recommendations.
    
    Performs comprehensive analysis including weak language detection,
    metrics gap identification, and structural improvements.
    """
    try:
        provider = get_llm_provider()
        
        optimizer = CVOptimizer(provider)
        result = await optimizer.optimize_cv(request)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CV optimization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CV optimization failed: {str(e)}"
        )


# ============================================================================
# Job Tailoring Endpoints
# ============================================================================

@router.post("/tailor-to-job", response_model=JobTailoringResult)
async def tailor_to_job(
    request: JobTailoringRequest
) -> JobTailoringResult:
    """
    Tailor CV to specific job description.
    
    Analyzes job description and provides specific suggestions for modifying
    CV content to better match the job requirements while maintaining truthfulness.
    """
    try:
        provider = get_llm_provider()
        
        optimizer = CVOptimizer(provider)
        result = await optimizer.tailor_to_job(request)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Job tailoring failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job tailoring failed: {str(e)}"
        )


@router.post("/match-job", response_model=JobMatchResult)
async def match_job(
    request: JobMatchRequest
) -> JobMatchResult:
    """
    Calculate comprehensive job match score with detailed breakdown.
    
    Analyzes how well a CV matches a job description and provides:
    - Overall match score (0-100%)
    - Detailed score breakdown (keyword alignment, experience relevance, skills match, requirements match)
    - Matched and missing skills, requirements, keywords
    - Qualification gaps and candidate strengths
    - Recommendations for improvement
    
    This is similar to LinkedIn Premium's job matching feature.
    
    Args:
        request: JobMatchRequest with CV data and job description
        
    Returns:
        JobMatchResult with comprehensive match analysis
        
    Raises:
        HTTPException: If matching analysis fails
    """
    try:
        provider = get_llm_provider()
        
        optimizer = CVOptimizer(provider)
        result = await optimizer.match_cv_to_job(request)
        
        return result
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid job match request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Job matching failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job matching failed: {str(e)}"
        )


@router.post("/create-tailored-cv")
async def create_tailored_cv(
    request: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a new CV variant tailored to a specific job description.
    
    This endpoint combines job tailoring analysis with CV creation to produce
    a new CV optimized for a specific job posting. The original CV is preserved
    unchanged.
    
    Process:
    1. Analyzes the job description to extract requirements and keywords
    2. Generates tailoring suggestions based on the source CV
    3. Applies suggestions according to the specified tailoring level
    4. Creates a new CV variant with the modifications
    
    Tailoring Levels:
    - conservative: Only applies high-priority suggestions (minimal changes)
    - moderate: Applies high and medium-priority suggestions (balanced approach)
    - aggressive: Applies all suggestions (maximum optimization)
    
    Args:
        request: Dictionary containing:
            - source_cv_id: UUID of the source CV
            - job_description: Job description text
            - tailoring_level: "conservative", "moderate", or "aggressive" (default: "moderate")
            - preserve_sections: Optional list of sections to keep unchanged
            - target_cv_title: Title for the new tailored CV
            
    Returns:
        Dictionary with:
            - source_cv_id: UUID of the source CV
            - tailored_cv_id: UUID of the newly created tailored CV
            - tailored_cv: Complete tailored CV data
            - changes_applied: List of changes made
            - tailoring_level: Level used
            - match_score: Estimated match score after tailoring
            
    Raises:
        HTTPException: If CV creation fails
    """
    try:
        from app.models.llm_models import TailoredCVRequest, TailoringLevel
        
        # Get LLM provider
        provider = get_llm_provider()
        
        # Get CV service
        file_service = FileService()
        cv_service = CVService(file_service=file_service)
        
        # Parse request into TailoredCVRequest model
        source_cv_id = request.get("source_cv_id")
        job_description = request.get("job_description")
        tailoring_level_str = request.get("tailoring_level", "moderate")
        preserve_sections = request.get("preserve_sections")
        target_cv_title = request.get("target_cv_title")
        
        if not source_cv_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="source_cv_id is required"
            )
        
        if not job_description:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="job_description is required"
            )
        
        if not target_cv_title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="target_cv_title is required"
            )
        
        # Convert tailoring level string to enum
        try:
            tailoring_level = TailoringLevel(tailoring_level_str.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid tailoring_level. Must be one of: conservative, moderate, aggressive"
            )
        
        # Load source CV
        try:
            source_cv_response = cv_service.get_cv(source_cv_id)
            source_cv = source_cv_response.cv
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source CV not found: {str(e)}"
            )
        
        # Create job tailoring request
        tailoring_request = JobTailoringRequest(
            cv_id=source_cv_id,
            cv_data=source_cv.model_dump(),
            job_description=job_description,
            focus_sections=None
        )
        
        # Get tailoring suggestions from LLM
        optimizer = CVOptimizer(provider)
        tailoring_result = await optimizer.tailor_to_job(tailoring_request)
        
        # Create tailored CV request
        tailored_cv_request = TailoredCVRequest(
            source_cv_id=source_cv_id,
            job_description=job_description,
            tailoring_level=tailoring_level,
            preserve_sections=preserve_sections,
            target_cv_title=target_cv_title
        )
        
        # Create the tailored CV
        result = cv_service.create_tailored_cv(
            tailored_cv_request,
            tailoring_result.suggestions
        )
        
        logger.info(
            f"Successfully created tailored CV {result.tailored_cv_id} "
            f"from source {source_cv_id} with {len(result.changes_applied)} changes"
        )
        
        return {
            "source_cv_id": result.source_cv_id,
            "tailored_cv_id": result.tailored_cv_id,
            "tailored_cv": result.tailored_cv,
            "changes_applied": result.changes_applied,
            "tailoring_level": result.tailoring_level.value,
            "match_score": result.match_score,
            "created_at": result.created_at.isoformat()
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid tailored CV request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Tailored CV creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tailored CV creation failed: {str(e)}"
        )


@router.post("/parse-job-url", response_model=JobURLParseResult)
async def parse_job_url(
    request: JobURLParseRequest
) -> JobURLParseResult:
    """
    Parse job description from URL.
    
    Fetches and extracts job information from job posting URLs.
    Supports common job boards (LinkedIn, Indeed, Glassdoor, etc.) with
    fallback to generic HTML parsing.
    
    Args:
        request: JobURLParseRequest with URL to parse
        
    Returns:
        JobURLParseResult with extracted job information
        
    Raises:
        HTTPException: If URL is invalid or cannot be accessed
    """
    try:
        parser = get_job_parser()
        
        # Parse the job URL
        result = await parser.parse_job_url(request.url)
        
        # Convert to response model
        return JobURLParseResult(
            url=result['url'],
            job_title=result.get('job_title'),
            company=result.get('company'),
            location=result.get('location'),
            description=result['description'],
            parser_used=result['parser_used'],
            success=True,
            error=None
        )
        
    except ValueError as e:
        # Invalid URL format
        logger.warning(f"Invalid URL format: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid URL: {str(e)}"
        )
    except URLAccessError as e:
        # Cannot access URL
        logger.error(f"Cannot access URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Cannot access URL: {str(e)}"
        )
    except ContentExtractionError as e:
        # Cannot extract content
        logger.error(f"Cannot extract content: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot extract job description: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Job URL parsing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job URL parsing failed: {str(e)}"
        )


# ============================================================================
# Grammar Checking Endpoints
# ============================================================================

@router.post("/check-grammar", response_model=GrammarCheckResult)
async def check_grammar(
    request: GrammarCheckRequest
) -> GrammarCheckResult:
    """
    Check grammar and style in CV content.
    
    Performs comprehensive grammar checking, style consistency analysis,
    passive voice detection, and tense verification.
    """
    try:
        provider = get_llm_provider()
        
        checker = GrammarChecker(provider)
        result = await checker.check_grammar(request)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Grammar checking failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Grammar checking failed: {str(e)}"
        )


# ============================================================================
# ATS Analysis Endpoints
# ============================================================================

@router.post("/analyze-ats", response_model=ATSAnalysisResult)
async def analyze_ats(
    request: ATSAnalysisRequest
) -> ATSAnalysisResult:
    """
    Analyze CV for ATS compatibility.
    
    Evaluates CV against ATS requirements including keyword optimization,
    formatting checks, and provides compatibility scoring with recommendations.
    """
    try:
        provider = get_llm_provider()
        
        analyzer = ATSAnalyzer(provider)
        result = await analyzer.analyze_ats_compatibility(request)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ATS analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ATS analysis failed: {str(e)}"
        )


# ============================================================================
# AI Parsing Endpoints
# ============================================================================

@router.post("/parse-cv", response_model=AIParsingResult)
async def parse_cv(
    request: AIParsingRequest
) -> AIParsingResult:
    """
    Parse CV from various formats using AI.
    
    Intelligently extracts structured data from PDF, DOCX, TXT, or HTML files
    with robust section identification and entity extraction.
    """
    try:
        provider = get_llm_provider()
        
        parser = AIParser(provider)
        result = await parser.parse_cv(request)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI parsing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI parsing failed: {str(e)}"
        )


# ============================================================================
# Configuration Endpoints
# ============================================================================

@router.get("/config", response_model=LLMConfigResponse)
async def get_config() -> LLMConfigResponse:
    """
    Get current LLM configuration (without sensitive data).
    
    Returns configuration including provider, model, and settings
    but excludes API keys for security.
    """
    try:
        llm_service = get_llm_service()
        return llm_service.get_config()
        
    except Exception as e:
        logger.error(f"Failed to get LLM config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get configuration: {str(e)}"
        )


@router.put("/config", response_model=LLMConfigResponse)
async def update_config(
    request: LLMConfigRequest
) -> LLMConfigResponse:
    """
    Update LLM configuration.
    
    Updates provider settings, API keys, and preferences.
    Recreates provider instance with new configuration.
    """
    try:
        llm_service = get_llm_service()
        result = llm_service.update_config(request)
        
        logger.info(f"LLM configuration updated: provider={result.provider}, model={result.model}")
        
        return result
        
    except ValueError as e:
        logger.error(f"Invalid LLM config: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update LLM config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update configuration: {str(e)}"
        )


@router.post("/consent/grant")
async def grant_consent() -> Dict[str, Any]:
    """
    Grant consent for external LLM services.
    
    Records user consent for sending data to external LLM providers
    and logs the consent event for audit purposes.
    """
    try:
        llm_service = get_llm_service()
        
        # Update config to grant consent
        llm_service.update_config(LLMConfigRequest(consent_given=True))
        
        return {
            "status": "success",
            "message": "Consent granted for external LLM services",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to grant consent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to grant consent: {str(e)}"
        )


@router.post("/consent/revoke")
async def revoke_consent() -> Dict[str, Any]:
    """
    Revoke consent for external LLM services.
    
    Revokes user consent and logs the revocation event.
    LLM features using external providers will be disabled.
    """
    try:
        llm_service = get_llm_service()
        llm_service.revoke_consent()
        
        return {
            "status": "success",
            "message": "Consent revoked for external LLM services",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to revoke consent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke consent: {str(e)}"
        )


@router.get("/consent/log")
async def get_consent_log() -> Dict[str, Any]:
    """
    Get consent audit log.
    
    Returns history of consent grants and revocations for audit purposes.
    """
    try:
        llm_service = get_llm_service()
        log = llm_service.get_consent_log()
        
        return {
            "log": log,
            "count": len(log)
        }
        
    except Exception as e:
        logger.error(f"Failed to get consent log: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get consent log: {str(e)}"
        )


@router.post("/enable")
async def enable_llm_features() -> Dict[str, Any]:
    """
    Enable LLM features globally.
    
    Enables all LLM-powered features. Requires valid configuration
    and consent for external providers.
    """
    try:
        llm_service = get_llm_service()
        llm_service.enable_llm_features()
        
        return {
            "status": "success",
            "message": "LLM features enabled",
            "enabled": True,
            "timestamp": datetime.now().isoformat()
        }
        
    except ValueError as e:
        logger.error(f"Cannot enable LLM features: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to enable LLM features: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable LLM features: {str(e)}"
        )


@router.post("/disable")
async def disable_llm_features() -> Dict[str, Any]:
    """
    Disable LLM features globally.
    
    Disables all LLM-powered features. Core CV functionality
    remains available.
    """
    try:
        llm_service = get_llm_service()
        llm_service.disable_llm_features()
        
        return {
            "status": "success",
            "message": "LLM features disabled",
            "enabled": False,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to disable LLM features: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable LLM features: {str(e)}"
        )


@router.get("/status")
async def get_llm_status() -> Dict[str, Any]:
    """
    Get LLM service status.
    
    Returns current status including whether LLM features are enabled,
    consent status, and provider information.
    """
    try:
        llm_service = get_llm_service()
        config = llm_service.get_config()
        
        return {
            "enabled": config.enabled,
            "provider": config.provider.value,
            "model": config.model,
            "has_api_key": config.has_api_key,
            "consent_given": config.consent_given,
            "requires_consent": llm_service.requires_consent(),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get LLM status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get LLM status: {str(e)}"
        )


@router.post("/test-connection")
async def test_connection() -> Dict[str, Any]:
    """
    Test LLM provider connection.
    
    Verifies that the configured LLM provider is accessible and working.
    """
    try:
        provider = get_llm_provider()

        llm_service = get_llm_service()
        config = llm_service.get_config()

        # test_connection() reports failure by returning False, not by raising.
        # Discarding the result made this endpoint answer "success" no matter
        # what the provider actually said.
        connected = await provider.test_connection()
        if not connected:
            # Claude Code authenticates from the environment rather than from a
            # key in AI settings, so the generic "check your credentials" advice
            # sends people to a field that does not exist for it.
            if config.provider == LLMProviderType.CLAUDE_CODE:
                hint = (
                    "Claude Code is not authenticated here. It reads "
                    "CLAUDE_CODE_OAUTH_TOKEN from the environment; a browser "
                    "login on your machine is not visible to this server. Mint "
                    "a token with `claude setup-token` and set it in .env, then "
                    "restart. The server log has the underlying error."
                )
            else:
                hint = (
                    "Check the credentials and model in AI settings; the server "
                    "log has the underlying error."
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Could not reach the {config.provider.value} provider. {hint}",
            )

        return {
            "status": "success",
            "message": "LLM provider connection successful",
            "provider": config.provider.value,
            "model": config.model
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Connection test failed: {str(e)}"
        )
