"""
Job Suitability Analyzer

Analyzes CV suitability against job specifications using LLM.
Provides detailed breakdown of requirements met/not met with scoring.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..llm.providers.base import BaseLLMProvider
from ..models.job_suitability_models import (
    JobSuitabilityResult,
    JobSuitabilityRequest,
    SuitabilityCategory,
    SuitabilityCriterion,
    SuitabilityStatus,
    get_recommendation_text,
    calculate_overall_score
)
from ..models.cv_models import CVModel
from .cv_normalisation import flatten_cv_model

logger = logging.getLogger(__name__)


class JobSuitabilityAnalyzer:
    """
    Analyzes CV suitability for specific job roles.
    
    Provides detailed analysis of:
    - Required skills match
    - Experience alignment
    - Education requirements
    - Soft skills fit
    - Certifications
    - Overall suitability score
    """
    
    def __init__(self, provider: BaseLLMProvider):
        """
        Initialize analyzer with LLM provider.
        
        Args:
            provider: LLM provider instance
        """
        self.provider = provider
    
    async def analyze_suitability(
        self,
        # Either CV version: only the id and the flattened summary are used.
        cv: Any,
        request: JobSuitabilityRequest
    ) -> JobSuitabilityResult:
        """
        Analyze CV suitability for a job.
        
        Args:
            cv: CV model to analyze
            request: Job suitability request with job description
            
        Returns:
            Detailed suitability analysis result
        """
        logger.info(f"Analyzing job suitability for CV {cv.id}")
        
        # Build CV summary for analysis
        cv_summary = self._build_cv_summary(cv)
        
        # Build analysis prompt
        prompt = self._build_analysis_prompt(
            cv_summary=cv_summary,
            job_description=request.job_description,
            job_title=request.job_title
        )
        
        # Define response schema
        schema = {
            "type": "object",
            "properties": {
                "job_title": {"type": "string"},
                "categories": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string"},
                            "category_score": {"type": "number"},
                            "criteria": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "criterion": {"type": "string"},
                                        "status": {"type": "string", "enum": ["yes", "no", "partial", "unknown"]},
                                        "explanation": {"type": "string"},
                                        "importance": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                                        "evidence": {"type": "array", "items": {"type": "string"}}
                                    },
                                    "required": ["criterion", "status", "explanation", "importance"]
                                }
                            }
                        },
                        "required": ["category", "category_score", "criteria"]
                    }
                },
                "key_strengths": {"type": "array", "items": {"type": "string"}},
                "critical_gaps": {"type": "array", "items": {"type": "string"}},
                "improvement_suggestions": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["job_title", "categories", "key_strengths", "critical_gaps"]
        }
        
        # Get LLM analysis
        response = await self.provider.generate_structured_output(
            prompt=prompt,
            schema=schema,
            system_prompt=self._get_system_prompt(),
            temperature=0.3  # Lower temperature for more consistent analysis
        )
        
        # Parse response. The field on StructuredLLMResponse is `data`;
        # `structured_data` never existed, so this path always raised.
        analysis_data = response.data
        
        # Build categories
        categories = []
        for cat_data in analysis_data.get("categories", []):
            criteria = []
            for crit_data in cat_data.get("criteria", []):
                criteria.append(SuitabilityCriterion(
                    criterion=crit_data["criterion"],
                    status=SuitabilityStatus(crit_data["status"]),
                    explanation=crit_data["explanation"],
                    importance=crit_data.get("importance", "medium"),
                    evidence=crit_data.get("evidence", [])
                ))
            
            categories.append(SuitabilityCategory(
                category=cat_data["category"],
                criteria=criteria,
                category_score=cat_data["category_score"]
            ))
        
        # Calculate overall score
        overall_score = calculate_overall_score(categories)
        
        # Count criteria
        total_criteria = sum(len(cat.criteria) for cat in categories)
        criteria_met = sum(
            1 for cat in categories 
            for crit in cat.criteria 
            if crit.status == SuitabilityStatus.YES
        )
        criteria_partial = sum(
            1 for cat in categories 
            for crit in cat.criteria 
            if crit.status == SuitabilityStatus.PARTIAL
        )
        criteria_not_met = sum(
            1 for cat in categories 
            for crit in cat.criteria 
            if crit.status == SuitabilityStatus.NO
        )
        
        # Build result
        result = JobSuitabilityResult(
            cv_id=cv.id,
            job_title=analysis_data.get("job_title", request.job_title or "Unknown Position"),
            overall_score=overall_score,
            recommendation=get_recommendation_text(overall_score),
            categories=categories,
            total_criteria=total_criteria,
            criteria_met=criteria_met,
            criteria_partial=criteria_partial,
            criteria_not_met=criteria_not_met,
            key_strengths=analysis_data.get("key_strengths", []),
            critical_gaps=analysis_data.get("critical_gaps", []),
            improvement_suggestions=analysis_data.get("improvement_suggestions", []) if request.include_improvement_suggestions else [],
            analyzed_at=datetime.now().isoformat()
        )
        
        logger.info(f"Suitability analysis complete: {overall_score:.1f}% match")
        return result
    
    def _build_cv_summary(self, cv: Any) -> str:
        """
        Build a text summary of CV for analysis.

        Accepts either CV version. A V2 CV stores its content in sections
        rather than as top-level fields, so reading `cv.personal_info` off one
        raised AttributeError and failed the whole analysis. Flattening first
        gives one shape to read.

        Args:
            cv: CV model (V1 or V2) or an already-flat dict

        Returns:
            Text summary of CV
        """
        data = flatten_cv_model(cv)
        parts = []

        # Personal info
        personal = data.get("personal_info") or {}
        if personal.get("name"):
            parts.append(f"Name: {personal['name']}")
        if personal.get("title"):
            parts.append(f"Title: {personal['title']}")

        # Summary
        if data.get("summary"):
            parts.append(f"\nProfessional Summary:\n{data['summary']}")

        # Experience
        if data.get("experience"):
            parts.append("\nWork Experience:")
            for exp in data["experience"]:
                exp_text = f"- {exp.get('title') or ''}"
                if exp.get("company"):
                    exp_text += f" at {exp['company']}"
                if exp.get("start_date"):
                    exp_text += f" ({exp['start_date']}"
                    if exp.get("current"):
                        exp_text += " - Present)"
                    elif exp.get("end_date"):
                        exp_text += f" - {exp['end_date']})"
                    else:
                        exp_text += ")"
                parts.append(exp_text)

                if exp.get("description"):
                    parts.append(f"  {exp['description']}")

                for achievement in exp.get("achievements") or []:
                    parts.append(f"  • {achievement}")

        # Education
        if data.get("education"):
            parts.append("\nEducation:")
            for edu in data["education"]:
                edu_text = f"- {edu.get('degree') or ''} from {edu.get('institution') or ''}"
                if edu.get("end_date"):
                    edu_text += f" ({edu['end_date']})"
                parts.append(edu_text)

                if edu.get("description"):
                    parts.append(f"  {edu['description']}")

        # Skills
        categories = (data.get("skills") or {}).get("categories") or []
        if categories:
            parts.append("\nSkills:")
            for category in categories:
                skills = category.get("skills") or []
                if skills:
                    parts.append(f"- {category.get('name') or 'Skills'}: {', '.join(skills)}")

        # Certifications
        if data.get("certifications"):
            parts.append("\nCertifications:")
            for cert in data["certifications"]:
                cert_text = f"- {cert.get('name') or ''}"
                if cert.get("issuer"):
                    cert_text += f" from {cert['issuer']}"
                if cert.get("date"):
                    cert_text += f" ({cert['date']})"
                parts.append(cert_text)

        return "\n".join(parts)

    def _build_analysis_prompt(
        self,
        cv_summary: str,
        job_description: str,
        job_title: Optional[str] = None
    ) -> str:
        """
        Build prompt for suitability analysis.
        
        Args:
            cv_summary: Summary of CV
            job_description: Job description text
            job_title: Optional job title
            
        Returns:
            Analysis prompt
        """
        prompt = f"""Analyze the following CV against the job description and provide a detailed suitability assessment.

JOB DESCRIPTION:
{job_description}

CV:
{cv_summary}

Analyze the CV's suitability for this role by evaluating specific criteria in these categories:
1. Required Skills - Technical and domain-specific skills mentioned in the job description
2. Experience - Years of experience, relevant roles, and industry background
3. Education - Degree requirements, field of study, academic achievements
4. Soft Skills - Communication, leadership, teamwork, problem-solving abilities
5. Certifications - Professional certifications and licenses
6. Other - Any other relevant requirements (languages, location, etc.)

For each criterion:
- Determine if it's met (yes), not met (no), partially met (partial), or cannot be determined (unknown)
- Provide a clear explanation with specific evidence from the CV
- Rate the importance: low, medium, high, or critical
- Include relevant quotes or examples from the CV as evidence

Also provide:
- Key strengths that make this candidate suitable
- Critical gaps or missing requirements
- Specific suggestions for improving the CV to better match this role

Be thorough, objective, and specific in your analysis."""
        
        return prompt
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for analysis."""
        return """You are an expert recruiter and career advisor specializing in CV analysis and job matching.

Your role is to:
1. Carefully analyze CVs against job requirements
2. Identify specific matches and gaps
3. Provide objective, evidence-based assessments
4. Give actionable feedback for improvement

Be thorough, fair, and constructive in your analysis. Focus on facts from the CV and job description.
When assessing criteria, be specific about what evidence supports your conclusion."""
