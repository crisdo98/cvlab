"""
Job Suitability Models

Models for analyzing CV suitability against job specifications.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class SuitabilityStatus(str, Enum):
    """Status for suitability criteria."""
    YES = "yes"
    NO = "no"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class SuitabilityCriterion(BaseModel):
    """Individual suitability criterion."""
    criterion: str = Field(..., description="The criterion being evaluated")
    status: SuitabilityStatus = Field(..., description="Whether criterion is met")
    explanation: str = Field(..., description="Explanation of the assessment")
    importance: str = Field(default="medium", description="Importance level: low, medium, high, critical")
    evidence: Optional[List[str]] = Field(default_factory=list, description="Evidence from CV supporting this assessment")


class SuitabilityCategory(BaseModel):
    """Category of suitability criteria."""
    category: str = Field(..., description="Category name (e.g., 'Required Skills', 'Experience')")
    criteria: List[SuitabilityCriterion] = Field(..., description="Criteria in this category")
    category_score: float = Field(..., ge=0.0, le=100.0, description="Score for this category (0-100)")


class JobSuitabilityResult(BaseModel):
    """Complete job suitability analysis result."""
    cv_id: str = Field(..., description="CV ID that was analyzed")
    job_title: str = Field(..., description="Job title from specification")
    overall_score: float = Field(..., ge=0.0, le=100.0, description="Overall suitability score (0-100)")
    recommendation: str = Field(..., description="Overall recommendation (e.g., 'Highly Suitable', 'Not Suitable')")
    
    # Categorized criteria
    categories: List[SuitabilityCategory] = Field(..., description="Suitability criteria by category")
    
    # Summary counts
    total_criteria: int = Field(..., description="Total number of criteria evaluated")
    criteria_met: int = Field(..., description="Number of criteria fully met")
    criteria_partial: int = Field(..., description="Number of criteria partially met")
    criteria_not_met: int = Field(..., description="Number of criteria not met")
    
    # Strengths and gaps
    key_strengths: List[str] = Field(default_factory=list, description="Key strengths for this role")
    critical_gaps: List[str] = Field(default_factory=list, description="Critical gaps or missing requirements")
    improvement_suggestions: List[str] = Field(default_factory=list, description="Suggestions to improve suitability")
    
    # Metadata
    analyzed_at: str = Field(..., description="Timestamp of analysis")


class JobSuitabilityRequest(BaseModel):
    """Request for job suitability analysis."""
    cv_id: str = Field(..., description="CV ID to analyze")
    job_description: str = Field(..., description="Job description or specification text")
    job_title: Optional[str] = Field(None, description="Job title (extracted if not provided)")
    include_improvement_suggestions: bool = Field(default=True, description="Include improvement suggestions")


class JobSuitabilityResponse(BaseModel):
    """Response for job suitability analysis."""
    result: JobSuitabilityResult
    message: Optional[str] = None


def get_recommendation_text(score: float) -> str:
    """
    Get recommendation text based on overall score.
    
    Args:
        score: Overall suitability score (0-100)
        
    Returns:
        Recommendation text
    """
    if score >= 85:
        return "Highly Suitable - Excellent match for this role"
    elif score >= 70:
        return "Suitable - Good match with minor gaps"
    elif score >= 55:
        return "Moderately Suitable - Some key requirements met"
    elif score >= 40:
        return "Marginally Suitable - Significant gaps present"
    else:
        return "Not Suitable - Major requirements not met"


def calculate_overall_score(categories: List[SuitabilityCategory]) -> float:
    """
    Calculate overall score from category scores.
    
    Args:
        categories: List of suitability categories
        
    Returns:
        Overall score (0-100)
    """
    if not categories:
        return 0.0
    
    # Weight categories by importance
    weights = {
        "required skills": 0.30,
        "experience": 0.25,
        "education": 0.15,
        "soft skills": 0.15,
        "certifications": 0.10,
        "other": 0.05
    }
    
    total_score = 0.0
    total_weight = 0.0
    
    for category in categories:
        category_name = category.category.lower()
        weight = weights.get(category_name, weights["other"])
        total_score += category.category_score * weight
        total_weight += weight
    
    return total_score / total_weight if total_weight > 0 else 0.0
