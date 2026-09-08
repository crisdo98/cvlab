"""
LLM Models

Pydantic models for LLM service requests and responses including content generation,
CV optimization, job tailoring, grammar checking, and ATS analysis.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import uuid4

from pydantic import BaseModel, Field, validator


# ============================================================================
# Content Generation Models
# ============================================================================

class ContentVariation(BaseModel):
    """A single content variation."""
    text: str = Field(..., description="Generated content text")
    variation_number: int = Field(..., description="Variation number (1-indexed)")


class ContentGenerationResult(BaseModel):
    """Result from content generation."""
    variations: List[ContentVariation] = Field(..., description="List of content variations")
    section_type: str = Field(..., description="Type of section generated")
    context_used: Dict[str, Any] = Field(default_factory=dict, description="Context used for generation")
    model: str = Field(..., description="Model used for generation")
    provider: str = Field(..., description="Provider used for generation")


class ContentGenerationRequest(BaseModel):
    """Request for content generation."""
    section_type: str = Field(..., description="Type of content to generate")
    context: Dict[str, Any] = Field(..., description="Context for generation")
    num_variations: int = Field(default=3, ge=1, le=5, description="Number of variations to generate")


class NoteExpansionRequest(BaseModel):
    """Request for expanding brief notes."""
    notes: str = Field(..., min_length=1, description="Brief notes to expand")
    job_title: str = Field(..., description="Job title for context")
    company: str = Field(..., description="Company name for context")
    section_type: str = Field(default="experience", description="Section type")
    target_length: str = Field(default="2-3 sentences", description="Target length")
    num_variations: int = Field(default=3, ge=1, le=5, description="Number of variations")


class AchievementGenerationRequest(BaseModel):
    """Request for generating achievement statements."""
    description: Optional[str] = Field(None, description="Full description to extract achievements from")
    notes: Optional[str] = Field(None, description="Brief notes to create achievements from")
    job_title: Optional[str] = Field(None, description="Job title for context")
    company: Optional[str] = Field(None, description="Company name for context")
    context_info: Optional[str] = Field(None, description="Additional context")
    num_variations: int = Field(default=3, ge=1, le=5, description="Number of variations")


class SummaryGenerationRequest(BaseModel):
    """Request for generating professional summary."""
    job_title: str = Field(..., description="Current or target job title")
    years_experience: int = Field(..., ge=0, description="Years of experience")
    skills: List[str] = Field(..., min_items=1, description="Key skills")
    industry: Optional[str] = Field(None, description="Industry or field")
    career_level: Optional[str] = Field(None, description="Career level")
    num_variations: int = Field(default=3, ge=1, le=5, description="Number of variations")


# ============================================================================
# CV Optimization Models
# ============================================================================

class RecommendationCategory(str, Enum):
    """Categories for optimization recommendations."""
    LANGUAGE = "language"  # Weak or vague language
    METRICS = "metrics"  # Missing quantifiable metrics
    STRUCTURE = "structure"  # Organizational improvements
    FORMATTING = "formatting"  # Formatting issues
    CONTENT = "content"  # Content improvements
    KEYWORDS = "keywords"  # Keyword optimization
    CLARITY = "clarity"  # Clarity and conciseness
    IMPACT = "impact"  # Impact and achievement focus


class RecommendationPriority(str, Enum):
    """Priority levels for recommendations."""
    HIGH = "high"  # Critical issues that significantly impact CV quality
    MEDIUM = "medium"  # Important improvements that enhance CV
    LOW = "low"  # Minor suggestions for polish


class OptimizationRecommendation(BaseModel):
    """A single optimization recommendation."""
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique recommendation ID")
    category: RecommendationCategory = Field(..., description="Recommendation category")
    priority: RecommendationPriority = Field(..., description="Priority level")
    issue: str = Field(..., description="Description of the issue identified")
    suggestion: str = Field(..., description="Specific suggestion for improvement")
    location: str = Field(..., description="Location in CV (e.g., 'Experience: Senior Engineer at TechCorp')")
    current_text: Optional[str] = Field(None, description="Current text that needs improvement")
    suggested_text: Optional[str] = Field(None, description="Suggested replacement text")
    reasoning: Optional[str] = Field(None, description="Explanation of why this change is recommended")


class OptimizationRequest(BaseModel):
    """Request for CV optimization analysis."""
    cv_id: str = Field(..., description="UUID of the CV to optimize")
    cv_data: Dict[str, Any] = Field(..., description="Complete CV data")
    focus_areas: Optional[List[RecommendationCategory]] = Field(
        None,
        description="Specific areas to focus on (if None, analyze all areas)"
    )
    include_reasoning: bool = Field(default=True, description="Include reasoning for recommendations")


class OptimizationResult(BaseModel):
    """Result from CV optimization analysis."""
    cv_id: str = Field(..., description="UUID of the analyzed CV")
    overall_score: float = Field(..., ge=0.0, le=100.0, description="Overall CV quality score (0-100)")
    recommendations: List[OptimizationRecommendation] = Field(
        default_factory=list,
        description="List of optimization recommendations"
    )
    summary: str = Field(..., description="Summary of key findings")
    strengths: List[str] = Field(default_factory=list, description="Identified strengths in the CV")
    areas_for_improvement: List[str] = Field(
        default_factory=list,
        description="High-level areas needing improvement"
    )
    analyzed_at: datetime = Field(default_factory=datetime.now, description="Analysis timestamp")
    model: str = Field(..., description="Model used for analysis")
    provider: str = Field(..., description="Provider used for analysis")
    
    @property
    def high_priority_count(self) -> int:
        """Count of high priority recommendations."""
        return sum(1 for r in self.recommendations if r.priority == RecommendationPriority.HIGH)
    
    @property
    def medium_priority_count(self) -> int:
        """Count of medium priority recommendations."""
        return sum(1 for r in self.recommendations if r.priority == RecommendationPriority.MEDIUM)
    
    @property
    def low_priority_count(self) -> int:
        """Count of low priority recommendations."""
        return sum(1 for r in self.recommendations if r.priority == RecommendationPriority.LOW)
    
    @property
    def recommendations_by_category(self) -> Dict[str, List[OptimizationRecommendation]]:
        """Group recommendations by category."""
        result: Dict[str, List[OptimizationRecommendation]] = {}
        for rec in self.recommendations:
            category = rec.category.value
            if category not in result:
                result[category] = []
            result[category].append(rec)
        return result


class WeakLanguageDetection(BaseModel):
    """Detection of weak or vague language."""
    location: str = Field(..., description="Location where weak language was found")
    weak_phrase: str = Field(..., description="The weak or vague phrase")
    issue_type: str = Field(..., description="Type of issue (passive voice, vague term, etc.)")
    suggested_replacement: str = Field(..., description="Stronger alternative")
    context: str = Field(..., description="Surrounding context")


class MetricsGap(BaseModel):
    """Identification of missing quantifiable metrics."""
    location: str = Field(..., description="Location where metrics are missing")
    description: str = Field(..., description="Description of what could be quantified")
    suggestion: str = Field(..., description="Suggestion for adding metrics")
    examples: List[str] = Field(default_factory=list, description="Example metrics that could be added")


class StructuralIssue(BaseModel):
    """Structural or organizational issue."""
    section: str = Field(..., description="Section with structural issue")
    issue: str = Field(..., description="Description of the structural issue")
    suggestion: str = Field(..., description="Suggestion for improvement")
    impact: str = Field(..., description="Impact of fixing this issue")


# ============================================================================
# Job Tailoring Models
# ============================================================================

class JobDescriptionAnalysis(BaseModel):
    """Analysis of a job description."""
    job_title: str = Field(..., description="Extracted job title")
    company: Optional[str] = Field(None, description="Company name if available")
    requirements: List[str] = Field(default_factory=list, description="Key requirements")
    skills: List[str] = Field(default_factory=list, description="Required skills")
    keywords: List[str] = Field(default_factory=list, description="Important keywords")
    experience_level: Optional[str] = Field(None, description="Required experience level")
    industry: Optional[str] = Field(None, description="Industry or field")


class TailoringSuggestion(BaseModel):
    """A suggestion for tailoring CV to job description."""
    section: str = Field(..., description="CV section to modify")
    current: str = Field(..., description="Current content")
    suggested: str = Field(..., description="Suggested modification")
    reason: str = Field(..., description="Reason for this suggestion")
    keywords_added: List[str] = Field(default_factory=list, description="Keywords incorporated")
    priority: RecommendationPriority = Field(..., description="Priority of this suggestion")


class JobTailoringRequest(BaseModel):
    """Request for tailoring CV to job description."""
    cv_id: str = Field(..., description="UUID of the CV to tailor")
    cv_data: Dict[str, Any] = Field(..., description="Complete CV data")
    job_description: str = Field(..., min_length=10, description="Job description text")
    focus_sections: Optional[List[str]] = Field(
        None,
        description="Specific sections to focus on (if None, analyze all)"
    )


class JobTailoringResult(BaseModel):
    """Result from job tailoring analysis."""
    cv_id: str = Field(..., description="UUID of the CV")
    job_analysis: JobDescriptionAnalysis = Field(..., description="Analysis of job description")
    suggestions: List[TailoringSuggestion] = Field(
        default_factory=list,
        description="Tailoring suggestions"
    )
    missing_keywords: List[str] = Field(
        default_factory=list,
        description="Keywords from job description missing in CV"
    )
    matching_keywords: List[str] = Field(
        default_factory=list,
        description="Keywords already present in CV"
    )
    match_score: float = Field(..., ge=0.0, le=100.0, description="Overall match score (0-100)")
    summary: str = Field(..., description="Summary of tailoring recommendations")
    analyzed_at: datetime = Field(default_factory=datetime.now, description="Analysis timestamp")
    model: str = Field(..., description="Model used for analysis")
    provider: str = Field(..., description="Provider used for analysis")


# ============================================================================
# Grammar and Style Models
# ============================================================================

class GrammarIssueType(str, Enum):
    """Types of grammar and style issues."""
    GRAMMAR = "grammar"  # Grammatical errors
    SPELLING = "spelling"  # Spelling errors
    PUNCTUATION = "punctuation"  # Punctuation issues
    PASSIVE_VOICE = "passive_voice"  # Passive voice usage
    TENSE = "tense"  # Tense inconsistency
    STYLE = "style"  # Style issues
    CLARITY = "clarity"  # Clarity issues
    REDUNDANCY = "redundancy"  # Redundant content


class GrammarIssue(BaseModel):
    """A grammar or style issue."""
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique issue ID")
    type: GrammarIssueType = Field(..., description="Type of issue")
    location: str = Field(..., description="Location in CV")
    issue_text: str = Field(..., description="Text with the issue")
    correction: str = Field(..., description="Suggested correction")
    explanation: str = Field(..., description="Explanation of the issue")
    severity: RecommendationPriority = Field(..., description="Severity of the issue")


class GrammarCheckRequest(BaseModel):
    """Request for grammar and style checking."""
    cv_id: str = Field(..., description="UUID of the CV to check")
    cv_data: Dict[str, Any] = Field(..., description="Complete CV data")
    check_types: Optional[List[GrammarIssueType]] = Field(
        None,
        description="Specific types to check (if None, check all)"
    )


class GrammarCheckResult(BaseModel):
    """Result from grammar and style checking."""
    cv_id: str = Field(..., description="UUID of the CV")
    issues: List[GrammarIssue] = Field(default_factory=list, description="List of issues found")
    overall_quality: str = Field(..., description="Overall quality assessment")
    checked_at: datetime = Field(default_factory=datetime.now, description="Check timestamp")
    model: str = Field(..., description="Model used for checking")
    provider: str = Field(..., description="Provider used for checking")
    
    @property
    def issue_count_by_type(self) -> Dict[str, int]:
        """Count issues by type."""
        result: Dict[str, int] = {}
        for issue in self.issues:
            issue_type = issue.type.value
            result[issue_type] = result.get(issue_type, 0) + 1
        return result


# ============================================================================
# ATS Analysis Models
# ============================================================================

class ATSCompatibilityScore(BaseModel):
    """ATS compatibility scoring breakdown."""
    overall_score: float = Field(..., ge=0.0, le=100.0, description="Overall ATS compatibility (0-100)")
    keyword_score: float = Field(..., ge=0.0, le=100.0, description="Keyword optimization score")
    formatting_score: float = Field(..., ge=0.0, le=100.0, description="Formatting compatibility score")
    structure_score: float = Field(..., ge=0.0, le=100.0, description="Structure score")
    completeness_score: float = Field(..., ge=0.0, le=100.0, description="Completeness score")


class ATSRecommendation(BaseModel):
    """ATS-specific recommendation."""
    category: str = Field(..., description="Recommendation category")
    issue: str = Field(..., description="Issue description")
    suggestion: str = Field(..., description="Suggestion for improvement")
    impact: str = Field(..., description="Impact on ATS compatibility")
    priority: RecommendationPriority = Field(..., description="Priority level")


class ATSAnalysisRequest(BaseModel):
    """Request for ATS compatibility analysis."""
    cv_id: str = Field(..., description="UUID of the CV to analyze")
    cv_data: Dict[str, Any] = Field(..., description="Complete CV data")
    industry: Optional[str] = Field(None, description="Target industry for keyword analysis")
    job_title: Optional[str] = Field(None, description="Target job title for keyword analysis")


class ATSAnalysisResult(BaseModel):
    """Result from ATS compatibility analysis."""
    cv_id: str = Field(..., description="UUID of the CV")
    compatibility_score: ATSCompatibilityScore = Field(..., description="Compatibility scoring breakdown")
    recommendations: List[ATSRecommendation] = Field(
        default_factory=list,
        description="ATS-specific recommendations"
    )
    industry_keywords: List[str] = Field(
        default_factory=list,
        description="Relevant industry keywords"
    )
    present_keywords: List[str] = Field(
        default_factory=list,
        description="Industry keywords present in CV"
    )
    missing_keywords: List[str] = Field(
        default_factory=list,
        description="Industry keywords missing from CV"
    )
    keyword_density: Dict[str, float] = Field(
        default_factory=dict,
        description="Keyword density analysis"
    )
    formatting_issues: List[str] = Field(
        default_factory=list,
        description="ATS-unfriendly formatting issues"
    )
    summary: str = Field(..., description="Summary of ATS analysis")
    analyzed_at: datetime = Field(default_factory=datetime.now, description="Analysis timestamp")
    model: str = Field(..., description="Model used for analysis")
    provider: str = Field(..., description="Provider used for analysis")


# ============================================================================
# AI Parsing Models
# ============================================================================

class ParsedSection(BaseModel):
    """A parsed CV section."""
    section_type: str = Field(..., description="Type of section (experience, education, etc.)")
    content: Dict[str, Any] = Field(..., description="Parsed content")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    raw_text: str = Field(..., description="Original raw text")


class ParsingAmbiguity(BaseModel):
    """An ambiguity in parsing that requires user confirmation."""
    field: str = Field(..., description="Field with ambiguity")
    options: List[str] = Field(..., description="Possible interpretations")
    context: str = Field(..., description="Context for the ambiguity")
    recommendation: Optional[str] = Field(None, description="Recommended option")


class AIParsingRequest(BaseModel):
    """Request for AI-powered CV parsing."""
    file_content: str = Field(..., description="Raw file content")
    file_format: str = Field(..., description="File format (pdf, docx, txt, html)")
    filename: Optional[str] = Field(None, description="Original filename")


class AIParsingResult(BaseModel):
    """Result from AI-powered CV parsing."""
    parsed_sections: List[ParsedSection] = Field(
        default_factory=list,
        description="Parsed CV sections"
    )
    ambiguities: List[ParsingAmbiguity] = Field(
        default_factory=list,
        description="Ambiguities requiring user confirmation"
    )
    overall_confidence: float = Field(..., ge=0.0, le=1.0, description="Overall parsing confidence")
    cv_data: Optional[Dict[str, Any]] = Field(None, description="Structured CV data if parsing succeeded")
    errors: List[str] = Field(default_factory=list, description="Parsing errors encountered")
    parsed_at: datetime = Field(default_factory=datetime.now, description="Parsing timestamp")
    model: str = Field(..., description="Model used for parsing")
    provider: str = Field(..., description="Provider used for parsing")


# ============================================================================
# LLM Configuration Models
# ============================================================================

class LLMProviderType(str, Enum):
    """Supported LLM provider types."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    LOCAL = "local"
    # Claude Code via the Agent SDK. Authenticates through Claude Code itself,
    # so it needs no API key.
    CLAUDE_CODE = "claude_code"


class LLMConfig(BaseModel):
    """LLM service configuration."""
    provider: LLMProviderType = Field(..., description="LLM provider type")
    api_key: Optional[str] = Field(None, description="API key (encrypted)")
    model: str = Field(..., description="Model name")
    base_url: Optional[str] = Field(None, description="Base URL for local models")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature for generation")
    max_tokens: int = Field(default=1000, ge=1, le=8000, description="Maximum tokens")
    enabled: bool = Field(default=True, description="Whether LLM features are enabled")
    consent_given: bool = Field(default=False, description="User consent for external services")


class LLMConfigRequest(BaseModel):
    """Request to update LLM configuration."""
    provider: Optional[LLMProviderType] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=8000)
    enabled: Optional[bool] = None
    consent_given: Optional[bool] = None


class LLMConfigResponse(BaseModel):
    """Response with LLM configuration (without sensitive data)."""
    provider: LLMProviderType
    model: str
    base_url: Optional[str] = None
    temperature: float
    max_tokens: int
    enabled: bool
    consent_given: bool
    has_api_key: bool = Field(..., description="Whether API key is configured")


# ============================================================================
# Job URL Parsing Models
# ============================================================================

class JobURLParseRequest(BaseModel):
    """Request to parse job description from URL."""
    url: str = Field(..., min_length=1, description="URL of the job posting")


class JobURLParseResult(BaseModel):
    """Result from parsing job URL."""
    url: str = Field(..., description="Original URL")
    job_title: Optional[str] = Field(None, description="Extracted job title")
    company: Optional[str] = Field(None, description="Company name")
    location: Optional[str] = Field(None, description="Job location")
    description: str = Field(..., description="Full job description text")
    parser_used: str = Field(..., description="Which parser was used (linkedin.com, indeed.com, generic, etc.)")
    success: bool = Field(default=True, description="Whether parsing was successful")
    error: Optional[str] = Field(None, description="Error message if parsing failed")


# ============================================================================
# Tailored CV Creation Models
# ============================================================================

class TailoringLevel(str, Enum):
    """Levels of aggressiveness for CV tailoring."""
    CONSERVATIVE = "conservative"  # Minimal changes, only add missing keywords naturally
    MODERATE = "moderate"  # Balanced changes, reword some content to match job description
    AGGRESSIVE = "aggressive"  # Significant changes, rewrite content to maximize match


class TailoredCVRequest(BaseModel):
    """Request to create a tailored CV variant."""
    source_cv_id: str = Field(..., description="UUID of the source CV to tailor")
    job_description: str = Field(..., min_length=10, description="Job description to tailor for")
    tailoring_level: TailoringLevel = Field(
        default=TailoringLevel.MODERATE,
        description="Level of tailoring to apply"
    )
    preserve_sections: Optional[List[str]] = Field(
        None,
        description="Sections to preserve unchanged (e.g., ['personal_info', 'education'])"
    )
    target_cv_title: str = Field(..., min_length=1, description="Title for the new tailored CV")


class TailoredCVResult(BaseModel):
    """Result from creating a tailored CV."""
    source_cv_id: str = Field(..., description="UUID of the source CV")
    tailored_cv_id: str = Field(..., description="UUID of the newly created tailored CV")
    tailored_cv: Dict[str, Any] = Field(..., description="Complete tailored CV data")
    changes_applied: List[str] = Field(
        default_factory=list,
        description="List of changes applied during tailoring"
    )
    tailoring_level: TailoringLevel = Field(..., description="Tailoring level used")
    match_score: float = Field(..., ge=0.0, le=100.0, description="Match score after tailoring")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")


# ============================================================================
# Job Matching Models
# ============================================================================

class JobMatchScoreBreakdown(BaseModel):
    """Detailed breakdown of job match scoring."""
    overall_score: float = Field(..., ge=0.0, le=100.0, description="Overall match score (0-100)")
    keyword_alignment_score: float = Field(..., ge=0.0, le=100.0, description="Keyword alignment score")
    experience_relevance_score: float = Field(..., ge=0.0, le=100.0, description="Experience relevance score")
    skills_match_score: float = Field(..., ge=0.0, le=100.0, description="Skills match score")
    requirements_match_score: float = Field(..., ge=0.0, le=100.0, description="Requirements match score")


class JobMatchRequest(BaseModel):
    """Request for job matching analysis."""
    cv_id: str = Field(..., description="UUID of the CV to match")
    cv_data: Dict[str, Any] = Field(..., description="Complete CV data")
    job_description: str = Field(..., min_length=10, description="Job description text")


class JobMatchResult(BaseModel):
    """Result from job matching analysis with detailed breakdown."""
    cv_id: str = Field(..., description="UUID of the CV")
    job_analysis: JobDescriptionAnalysis = Field(..., description="Analysis of job description")
    score_breakdown: JobMatchScoreBreakdown = Field(..., description="Detailed score breakdown")
    matched_skills: List[str] = Field(default_factory=list, description="Skills that match job requirements")
    missing_skills: List[str] = Field(default_factory=list, description="Skills missing from CV")
    matched_requirements: List[str] = Field(default_factory=list, description="Requirements met by CV")
    missing_requirements: List[str] = Field(default_factory=list, description="Requirements not met by CV")
    matched_keywords: List[str] = Field(default_factory=list, description="Keywords present in CV")
    missing_keywords: List[str] = Field(default_factory=list, description="Keywords missing from CV")
    qualification_gaps: List[str] = Field(default_factory=list, description="Identified qualification gaps")
    strengths: List[str] = Field(default_factory=list, description="Candidate strengths for this role")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations to improve match")
    summary: str = Field(..., description="Summary of match analysis")
    analyzed_at: datetime = Field(default_factory=datetime.now, description="Analysis timestamp")
    model: str = Field(..., description="Model used for analysis")
    provider: str = Field(..., description="Provider used for analysis")
