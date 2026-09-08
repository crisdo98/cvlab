"""
ATS Analyzer for CV Compatibility Analysis

This module provides ATS (Applicant Tracking System) compatibility analysis including
keyword optimization, formatting checks, and compatibility scoring.
"""

from typing import List, Dict, Any, Optional
import logging
import re
from datetime import datetime

from app.llm.providers.base import BaseLLMProvider, LLMResponse
from app.models.llm_models import (
    ATSAnalysisRequest,
    ATSAnalysisResult,
    ATSCompatibilityScore,
    ATSRecommendation,
    RecommendationPriority
)
from app.llm.cv_normalisation import flatten_cv

logger = logging.getLogger(__name__)


class ATSAnalyzer:
    """AI-powered ATS compatibility analyzer for CV content.
    
    This class provides methods for:
    - Analyzing ATS compatibility and scoring
    - Identifying industry-standard keywords
    - Detecting keyword stuffing
    - Analyzing keyword density
    - Checking for ATS-unfriendly formatting
    """
    
    # Common ATS-unfriendly elements
    ATS_UNFRIENDLY_ELEMENTS = [
        "tables", "text boxes", "headers/footers", "images", "graphics",
        "columns", "special characters", "unusual fonts", "embedded objects"
    ]
    
    # Industry keyword databases (simplified - would be expanded in production)
    INDUSTRY_KEYWORDS = {
        "software": [
            "python", "java", "javascript", "typescript", "react", "vue", "angular",
            "node.js", "sql", "nosql", "mongodb", "postgresql", "aws", "azure", "gcp",
            "docker", "kubernetes", "ci/cd", "agile", "scrum", "api", "rest", "graphql",
            "microservices", "devops", "git", "testing", "tdd", "architecture"
        ],
        "data": [
            "python", "r", "sql", "machine learning", "deep learning", "tensorflow",
            "pytorch", "pandas", "numpy", "scikit-learn", "data analysis", "statistics",
            "visualization", "tableau", "power bi", "spark", "hadoop", "etl", "data warehouse",
            "big data", "predictive modeling", "a/b testing"
        ],
        "management": [
            "leadership", "team management", "project management", "strategic planning",
            "budgeting", "stakeholder management", "agile", "scrum", "pmp", "change management",
            "performance management", "coaching", "mentoring", "cross-functional", "p&l"
        ],
        "marketing": [
            "seo", "sem", "google analytics", "social media", "content marketing",
            "email marketing", "marketing automation", "crm", "salesforce", "hubspot",
            "campaign management", "brand management", "digital marketing", "analytics",
            "conversion optimization", "a/b testing", "roi"
        ]
    }
    
    def __init__(self, llm_provider: BaseLLMProvider):
        """Initialize ATS analyzer with LLM provider.
        
        Args:
            llm_provider: LLM provider instance to use for analysis
        """
        self.llm_provider = llm_provider
    
    async def analyze_ats_compatibility(
        self,
        request: ATSAnalysisRequest
    ) -> ATSAnalysisResult:
        """Analyze CV for ATS compatibility.
        
        Args:
            request: ATS analysis request with CV data
            
        Returns:
            ATSAnalysisResult with compatibility analysis
            
        Raises:
            ValueError: If request is invalid
            RuntimeError: If analysis fails
        """
        # A stored CV is section-based; every lookup below expects the flat
        # shape. Without this the analysis reports each section missing even
        # when the CV is complete.
        cv_data = flatten_cv(request.cv_data)
        
        # Build comprehensive ATS analysis prompt
        system_prompt = self._build_ats_system_prompt()
        user_prompt = self._build_ats_user_prompt(
            cv_data,
            request.industry,
            request.job_title
        )
        
        # Get LLM analysis
        response = await self.llm_provider.generate_completion(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,  # Lower temperature for consistent analysis
            max_tokens=2000
        )
        
        # Parse LLM response into structured recommendations
        llm_recommendations = self._parse_ats_response(response.content)
        
        # Perform rule-based analysis.
        #
        # Keywords come from the role being targeted — an explicit job title
        # if one was given, otherwise the CV's most current role. The static
        # INDUSTRY_KEYWORDS buckets are only a fallback for when the model
        # cannot be reached, since routing by substring across four broad
        # fields matches most roles badly.
        target_role = request.job_title or self._current_role(cv_data)
        industry_keywords: List[str] = []
        if target_role:
            try:
                industry_keywords = await self._keywords_for_role(
                    target_role, request.industry
                )
            except Exception as exc:
                logger.warning(
                    "Could not derive keywords for '%s', falling back to the "
                    "static industry lists: %s",
                    target_role,
                    exc,
                )

        if not industry_keywords:
            industry_keywords = self._identify_industry_keywords(
                cv_data,
                request.industry,
                request.job_title
            )
        
        present_keywords = self._find_present_keywords(cv_data, industry_keywords)
        missing_keywords = [kw for kw in industry_keywords if kw not in present_keywords]
        
        keyword_density = self._analyze_keyword_density(cv_data, industry_keywords)
        
        stuffing_issues = self._detect_keyword_stuffing(cv_data, keyword_density)
        
        formatting_issues = self._check_formatting_issues(cv_data)
        
        # Calculate compatibility scores
        compatibility_score = self._calculate_compatibility_scores(
            cv_data,
            present_keywords,
            missing_keywords,
            formatting_issues,
            stuffing_issues
        )
        
        # Combine all recommendations
        all_recommendations = llm_recommendations + stuffing_issues
        
        # Add keyword recommendations
        if missing_keywords:
            all_recommendations.append(ATSRecommendation(
                category="Keywords",
                issue=f"Missing {len(missing_keywords)} industry-standard keywords",
                suggestion=f"Consider incorporating these relevant keywords: {', '.join(missing_keywords[:5])}",
                impact="Improves ATS keyword matching and search visibility",
                priority=RecommendationPriority.HIGH
            ))
        
        # Add formatting recommendations
        if formatting_issues:
            for issue in formatting_issues[:3]:  # Top 3 formatting issues
                all_recommendations.append(ATSRecommendation(
                    category="Formatting",
                    issue=issue,
                    suggestion=self._get_formatting_suggestion(issue),
                    impact="Ensures ATS can properly parse your CV",
                    priority=RecommendationPriority.HIGH
                ))
        
        # Generate summary
        summary = self._generate_ats_summary(
            compatibility_score,
            len(present_keywords),
            len(missing_keywords),
            len(formatting_issues)
        )
        
        return ATSAnalysisResult(
            cv_id=request.cv_id,
            compatibility_score=compatibility_score,
            recommendations=all_recommendations,
            industry_keywords=industry_keywords,
            present_keywords=present_keywords,
            missing_keywords=missing_keywords,
            keyword_density=keyword_density,
            formatting_issues=formatting_issues,
            summary=summary,
            analyzed_at=datetime.now(),
            model=response.model,
            provider=response.provider
        )
    
    # ------------------------------------------------- role-derived keywords

    @staticmethod
    def _current_role(cv_data: Dict[str, Any]) -> Optional[str]:
        """The role the CV is currently positioned as.

        Prefers an entry flagged `current`, then the latest start date, then
        the headline title. Returned as "Title at Company" when a company is
        known, since the employer adds useful signal about the domain.
        """
        experience = cv_data.get("experience") or []
        entries = [e for e in experience if isinstance(e, dict) and e.get("title")]

        chosen = None
        for entry in entries:
            if entry.get("current"):
                chosen = entry
                break
        if chosen is None and entries:
            # `start_date` is free text, so sort as a string: ISO-ish values
            # order correctly and anything else falls back to CV order.
            chosen = max(entries, key=lambda e: str(e.get("start_date") or ""))

        if chosen:
            title = str(chosen["title"]).strip()
            company = str(chosen.get("company") or "").strip()
            return f"{title} at {company}" if company else title

        headline = (cv_data.get("personal_info") or {}).get("title")
        return str(headline).strip() if headline else None

    async def _keywords_for_role(
        self,
        role: str,
        industry: Optional[str]
    ) -> List[str]:
        """Ask the model which keywords an ATS would screen this role on.

        The static INDUSTRY_KEYWORDS buckets cover four broad fields and route
        by substring, which sends anything containing "engineer" to the
        software list regardless of what the role actually is. Deriving the
        vocabulary from the role itself avoids that.

        Keywords are derived from the *role*, never from the CV's own text:
        matching a CV against words lifted out of that same CV would score
        every CV highly and measure nothing.
        """
        context = f"Role: {role}"
        if industry:
            context += f"\nIndustry: {industry}"

        schema = {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lowercase ATS keywords for this role",
                }
            },
            "required": ["keywords"],
        }

        response = await self.llm_provider.generate_structured_output(
            prompt=(
                f"{context}\n\n"
                "List the 20-30 skills, tools and competencies an applicant "
                "tracking system would most likely screen for when filling "
                "this role. Cover both technical and non-technical "
                "requirements appropriate to its seniority — a leadership "
                "role should include leadership terms, not only tooling. "
                "Return short lowercase terms as they would appear in a CV."
            ),
            schema=schema,
            system_prompt=(
                "You are an ATS keyword specialist. Reply with realistic, "
                "widely-used terms for the role given, not aspirational ones."
            ),
            temperature=0.2,
            max_tokens=600,
        )

        raw = (response.data or {}).get("keywords") or []
        keywords = []
        for item in raw:
            if isinstance(item, str) and item.strip():
                keyword = item.strip().lower()
                if keyword not in keywords:
                    keywords.append(keyword)
        return keywords[:30]

    def _identify_industry_keywords(
        self,
        cv_data: Dict[str, Any],
        industry: Optional[str],
        job_title: Optional[str]
    ) -> List[str]:
        """Identify relevant industry keywords for the CV.
        
        Args:
            cv_data: Complete CV data
            industry: Target industry
            job_title: Target job title
            
        Returns:
            List of relevant industry keywords
        """
        keywords = set()
        
        # Determine industry from job title or explicit industry
        detected_industry = None
        
        if industry:
            industry_lower = industry.lower()
            for key in self.INDUSTRY_KEYWORDS.keys():
                if key in industry_lower:
                    detected_industry = key
                    break
        
        # Try to detect from job title
        if not detected_industry and job_title:
            job_title_lower = job_title.lower()
            if any(term in job_title_lower for term in ["engineer", "developer", "programmer", "software"]):
                detected_industry = "software"
            elif any(term in job_title_lower for term in ["data", "analyst", "scientist", "ml", "ai"]):
                detected_industry = "data"
            elif any(term in job_title_lower for term in ["manager", "director", "lead", "head"]):
                detected_industry = "management"
            elif any(term in job_title_lower for term in ["marketing", "seo", "content", "brand"]):
                detected_industry = "marketing"
        
        # Try to detect from CV content
        if not detected_industry:
            cv_text = self._extract_cv_text(cv_data).lower()
            
            # Count keyword matches for each industry
            industry_scores = {}
            for ind, ind_keywords in self.INDUSTRY_KEYWORDS.items():
                score = sum(1 for kw in ind_keywords if kw.lower() in cv_text)
                industry_scores[ind] = score
            
            # Pick industry with highest score
            if industry_scores:
                detected_industry = max(industry_scores.items(), key=lambda x: x[1])[0]
        
        # Get keywords for detected industry
        if detected_industry and detected_industry in self.INDUSTRY_KEYWORDS:
            keywords.update(self.INDUSTRY_KEYWORDS[detected_industry])
        else:
            # Use a general set if no specific industry detected
            for ind_keywords in self.INDUSTRY_KEYWORDS.values():
                keywords.update(ind_keywords[:5])  # Take top 5 from each
        
        # Sorted, not raw set order: Python randomises string hashing per
        # process, so an unsorted set gave a different "missing keywords"
        # list on every run for an unchanged CV.
        return sorted(keywords)[:30]
    
    def _find_present_keywords(
        self,
        cv_data: Dict[str, Any],
        industry_keywords: List[str]
    ) -> List[str]:
        """Find which industry keywords are present in the CV.
        
        Args:
            cv_data: Complete CV data
            industry_keywords: List of industry keywords to check
            
        Returns:
            List of keywords found in CV
        """
        cv_text = self._extract_cv_text(cv_data).lower()
        present = []
        
        for keyword in industry_keywords:
            # Check for exact match or word boundary match
            keyword_lower = keyword.lower()
            if keyword_lower in cv_text:
                # Verify it's a word boundary match, not just substring
                pattern = r'\b' + re.escape(keyword_lower) + r'\b'
                if re.search(pattern, cv_text):
                    present.append(keyword)
        
        return present
    
    def _analyze_keyword_density(
        self,
        cv_data: Dict[str, Any],
        industry_keywords: List[str]
    ) -> Dict[str, float]:
        """Analyze keyword density in the CV.
        
        Args:
            cv_data: Complete CV data
            industry_keywords: List of industry keywords
            
        Returns:
            Dictionary mapping keywords to their density (occurrences per 100 words)
        """
        cv_text = self._extract_cv_text(cv_data).lower()
        total_words = len(cv_text.split())
        
        if total_words == 0:
            return {}
        
        density = {}
        
        for keyword in industry_keywords:
            keyword_lower = keyword.lower()
            # Count occurrences
            pattern = r'\b' + re.escape(keyword_lower) + r'\b'
            count = len(re.findall(pattern, cv_text))
            
            if count > 0:
                # Calculate density (occurrences per 100 words)
                density[keyword] = (count / total_words) * 100
        
        return density
    
    def _detect_keyword_stuffing(
        self,
        cv_data: Dict[str, Any],
        keyword_density: Dict[str, float]
    ) -> List[ATSRecommendation]:
        """Detect keyword stuffing in the CV.
        
        Args:
            cv_data: Complete CV data
            keyword_density: Keyword density analysis
            
        Returns:
            List of recommendations for keyword stuffing issues
        """
        recommendations = []
        
        # Threshold for keyword stuffing (more than 3% density is suspicious)
        STUFFING_THRESHOLD = 3.0
        
        stuffed_keywords = [
            (kw, density) for kw, density in keyword_density.items()
            if density > STUFFING_THRESHOLD
        ]
        
        if stuffed_keywords:
            # Sort by density
            stuffed_keywords.sort(key=lambda x: x[1], reverse=True)
            
            for keyword, density in stuffed_keywords[:3]:  # Top 3 offenders
                recommendations.append(ATSRecommendation(
                    category="Keyword Stuffing",
                    issue=f"Keyword '{keyword}' appears too frequently ({density:.1f}% density)",
                    suggestion=f"Reduce usage of '{keyword}' and use natural variations or synonyms",
                    impact="Keyword stuffing can trigger ATS spam filters and hurt your ranking",
                    priority=RecommendationPriority.HIGH
                ))
        
        return recommendations
    
    def _check_formatting_issues(self, cv_data: Dict[str, Any]) -> List[str]:
        """Check for ATS-unfriendly formatting issues.
        
        Args:
            cv_data: Complete CV data
            
        Returns:
            List of formatting issues found
        """
        issues = []
        
        # Check for missing standard sections
        if not cv_data.get("personal_info"):
            issues.append("Missing personal information section")
        
        if not cv_data.get("experience"):
            issues.append("Missing work experience section")
        
        if not cv_data.get("education"):
            issues.append("Missing education section")
        
        if not cv_data.get("skills"):
            issues.append("Missing skills section")
        
        # Check for contact information
        personal_info = cv_data.get("personal_info", {})
        contact = personal_info.get("contact", {})
        
        if not contact.get("email"):
            issues.append("Missing email address")
        
        if not contact.get("phone"):
            issues.append("Missing phone number")
        
        # Check for date formatting in experience
        for exp in cv_data.get("experience", []):
            start_date = exp.get("start_date", "")
            end_date = exp.get("end_date", "")
            
            # Check if dates are in a reasonable format
            if start_date and not self._is_valid_date_format(start_date):
                issues.append(f"Inconsistent date format in experience: {start_date}")
                break
        
        # Check for overly complex structure
        if len(cv_data.get("skills", {}).get("categories", [])) > 8:
            issues.append("Too many skill categories may confuse ATS parsers")
        
        return issues
    
    def _is_valid_date_format(self, date_str: str) -> bool:
        """Check if date string is in a valid format.
        
        Args:
            date_str: Date string to check
            
        Returns:
            True if format is valid
        """
        # Common valid formats: "2020-01", "Jan 2020", "January 2020", "2020"
        valid_patterns = [
            r'^\d{4}-\d{2}$',  # 2020-01
            r'^\d{4}$',  # 2020
            r'^[A-Za-z]{3,9}\s+\d{4}$',  # Jan 2020 or January 2020
            r'^\d{2}/\d{4}$',  # 01/2020
        ]
        
        return any(re.match(pattern, date_str.strip()) for pattern in valid_patterns)
    
    def _get_formatting_suggestion(self, issue: str) -> str:
        """Get suggestion for a formatting issue.
        
        Args:
            issue: Formatting issue description
            
        Returns:
            Suggestion for fixing the issue
        """
        suggestions = {
            "Missing personal information section": "Add a clear personal information section with your name and title",
            "Missing work experience section": "Add a work experience section with your employment history",
            "Missing education section": "Add an education section with your academic background",
            "Missing skills section": "Add a skills section listing your relevant technical and professional skills",
            "Missing email address": "Include a professional email address in your contact information",
            "Missing phone number": "Include a phone number in your contact information",
            "Too many skill categories": "Consolidate to 4-6 focused skill categories for better ATS parsing",
        }
        
        for key, suggestion in suggestions.items():
            if key in issue:
                return suggestion
        
        return "Review and simplify formatting for better ATS compatibility"
    
    def _calculate_compatibility_scores(
        self,
        cv_data: Dict[str, Any],
        present_keywords: List[str],
        missing_keywords: List[str],
        formatting_issues: List[str],
        stuffing_issues: List[ATSRecommendation]
    ) -> ATSCompatibilityScore:
        """Calculate ATS compatibility scores.
        
        Args:
            cv_data: Complete CV data
            present_keywords: Keywords present in CV
            missing_keywords: Keywords missing from CV
            formatting_issues: List of formatting issues
            stuffing_issues: List of keyword stuffing issues
            
        Returns:
            ATSCompatibilityScore with breakdown
        """
        # Keyword score (0-100)
        total_keywords = len(present_keywords) + len(missing_keywords)
        if total_keywords > 0:
            keyword_score = (len(present_keywords) / total_keywords) * 100
        else:
            keyword_score = 50.0  # Neutral score if no keywords identified
        
        # Deduct for keyword stuffing
        keyword_score -= len(stuffing_issues) * 10
        keyword_score = max(0.0, keyword_score)
        
        # Formatting score (0-100)
        # Start with 100 and deduct for issues
        formatting_score = 100.0
        formatting_score -= len(formatting_issues) * 10
        formatting_score = max(0.0, formatting_score)
        
        # Structure score (0-100)
        structure_score = 100.0
        
        # Check for standard sections
        if not cv_data.get("summary"):
            structure_score -= 10
        if not cv_data.get("experience"):
            structure_score -= 30
        if not cv_data.get("education"):
            structure_score -= 20
        if not cv_data.get("skills"):
            structure_score -= 20
        
        structure_score = max(0.0, structure_score)
        
        # Completeness score (0-100)
        completeness_score = 100.0
        
        # Check for complete information
        personal_info = cv_data.get("personal_info", {})
        if not personal_info.get("name"):
            completeness_score -= 20
        
        contact = personal_info.get("contact", {})
        if not contact.get("email"):
            completeness_score -= 15
        if not contact.get("phone"):
            completeness_score -= 15
        
        # Check experience completeness
        for exp in cv_data.get("experience", []):
            if not exp.get("description") and not exp.get("achievements"):
                completeness_score -= 5
                break
        
        completeness_score = max(0.0, completeness_score)
        
        # Overall score (weighted average)
        overall_score = (
            keyword_score * 0.35 +
            formatting_score * 0.25 +
            structure_score * 0.25 +
            completeness_score * 0.15
        )
        
        return ATSCompatibilityScore(
            overall_score=round(overall_score, 1),
            keyword_score=round(keyword_score, 1),
            formatting_score=round(formatting_score, 1),
            structure_score=round(structure_score, 1),
            completeness_score=round(completeness_score, 1)
        )
    
    def _extract_cv_text(self, cv_data: Dict[str, Any]) -> str:
        """Extract all text content from CV data.
        
        Args:
            cv_data: Complete CV data
            
        Returns:
            Concatenated text content
        """
        text_parts = []
        
        # Personal info
        personal_info = cv_data.get("personal_info", {})
        if personal_info.get("name"):
            text_parts.append(personal_info["name"])
        if personal_info.get("title"):
            text_parts.append(personal_info["title"])
        
        # Summary
        if cv_data.get("summary"):
            text_parts.append(cv_data["summary"])
        
        # Experience
        for exp in cv_data.get("experience", []):
            if exp.get("title"):
                text_parts.append(exp["title"])
            if exp.get("company"):
                text_parts.append(exp["company"])
            if exp.get("description"):
                text_parts.append(exp["description"])
            for achievement in exp.get("achievements", []):
                text_parts.append(achievement)
        
        # Education
        for edu in cv_data.get("education", []):
            if edu.get("degree"):
                text_parts.append(edu["degree"])
            if edu.get("institution"):
                text_parts.append(edu["institution"])
            if edu.get("description"):
                text_parts.append(edu["description"])
        
        # Skills
        for category in cv_data.get("skills", {}).get("categories", []):
            text_parts.extend(category.get("skills", []))
        
        # Certifications
        for cert in cv_data.get("certifications", []):
            if cert.get("name"):
                text_parts.append(cert["name"])
        
        return " ".join(text_parts)
    
    def _build_ats_system_prompt(self) -> str:
        """Build system prompt for ATS analysis."""
        return """You are an expert ATS (Applicant Tracking System) compatibility analyst. 
Your role is to analyze CVs and provide specific recommendations for improving ATS compatibility.

Focus on:
- Keyword optimization and natural incorporation
- ATS-friendly formatting and structure
- Completeness of information
- Industry-standard terminology
- Avoiding keyword stuffing while maintaining relevance

Provide specific, actionable recommendations that will improve the CV's chances of passing 
ATS screening while maintaining professional quality and readability."""
    
    def _build_ats_user_prompt(
        self,
        cv_data: Dict[str, Any],
        industry: Optional[str],
        job_title: Optional[str]
    ) -> str:
        """Build user prompt for ATS analysis.
        
        Args:
            cv_data: Complete CV data
            industry: Target industry
            job_title: Target job title
            
        Returns:
            Formatted user prompt
        """
        # Extract key CV information
        personal_info = cv_data.get("personal_info", {})
        name = personal_info.get("name", "Candidate")
        current_title = personal_info.get("title", "Professional")
        summary = cv_data.get("summary", "")
        
        experiences_text = ""
        for i, exp in enumerate(cv_data.get("experience", [])[:3], 1):
            experiences_text += f"\n{i}. {exp.get('title', '')} at {exp.get('company', '')}"
        
        skills_text = ""
        for category in cv_data.get("skills", {}).get("categories", [])[:3]:
            skills_text += f"\n- {category.get('name', '')}: {', '.join(category.get('skills', [])[:5])}"
        
        target_info = ""
        if industry or job_title:
            target_info = f"\nTarget Industry: {industry or 'Not specified'}\nTarget Job Title: {job_title or 'Not specified'}"
        
        prompt = f"""Analyze this CV for ATS (Applicant Tracking System) compatibility:

CANDIDATE CV:
Name: {name}
Current Title: {current_title}
Summary: {summary[:300] if summary else 'No summary'}

Recent Experience:{experiences_text}

Skills:{skills_text}

{target_info}

Provide ATS compatibility recommendations in this format:

1. [Category] [Priority: High/Medium/Low]
   Issue: [specific issue description]
   Suggestion: [actionable suggestion]
   Impact: [how this affects ATS compatibility]

Focus on:
- Keyword optimization (natural incorporation, not stuffing)
- Formatting issues that ATS systems struggle with
- Missing standard sections or information
- Industry-standard terminology
- Structure and organization

Provide 5-8 specific recommendations."""
        
        return prompt
    
    def _parse_ats_response(self, response_text: str) -> List[ATSRecommendation]:
        """Parse LLM response into ATS recommendations.
        
        Args:
            response_text: Raw LLM response
            
        Returns:
            List of ATSRecommendation objects
        """
        recommendations = []
        lines = response_text.split('\n')
        current_rec = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for new recommendation (starts with number)
            if re.match(r'^\d+\.', line):
                # Save previous recommendation
                if current_rec:
                    rec = self._create_ats_recommendation(current_rec)
                    if rec:
                        recommendations.append(rec)
                    current_rec = {}
                
                # Parse header
                category_match = re.search(r'\[([^\]]+)\]', line)
                priority_match = re.search(r'Priority:\s*(High|Medium|Low)', line, re.IGNORECASE)
                
                if category_match:
                    current_rec['category'] = category_match.group(1).strip()
                if priority_match:
                    current_rec['priority'] = priority_match.group(1).strip().lower()
            
            # Parse fields
            elif line.startswith('Issue:'):
                current_rec['issue'] = line.replace('Issue:', '').strip()
            elif line.startswith('Suggestion:'):
                current_rec['suggestion'] = line.replace('Suggestion:', '').strip()
            elif line.startswith('Impact:'):
                current_rec['impact'] = line.replace('Impact:', '').strip()
        
        # Add last recommendation
        if current_rec:
            rec = self._create_ats_recommendation(current_rec)
            if rec:
                recommendations.append(rec)
        
        return recommendations
    
    def _create_ats_recommendation(
        self,
        parsed_data: Dict[str, str]
    ) -> Optional[ATSRecommendation]:
        """Create ATSRecommendation from parsed data.
        
        Args:
            parsed_data: Dictionary with parsed recommendation data
            
        Returns:
            ATSRecommendation or None if invalid
        """
        if not all(k in parsed_data for k in ['issue', 'suggestion', 'impact']):
            return None
        
        # Map priority string to enum
        priority_map = {
            'high': RecommendationPriority.HIGH,
            'medium': RecommendationPriority.MEDIUM,
            'low': RecommendationPriority.LOW
        }
        
        priority = priority_map.get(
            parsed_data.get('priority', 'medium').lower(),
            RecommendationPriority.MEDIUM
        )
        
        return ATSRecommendation(
            category=parsed_data.get('category', 'General'),
            issue=parsed_data['issue'],
            suggestion=parsed_data['suggestion'],
            impact=parsed_data['impact'],
            priority=priority
        )
    
    def _generate_ats_summary(
        self,
        compatibility_score: ATSCompatibilityScore,
        num_present_keywords: int,
        num_missing_keywords: int,
        num_formatting_issues: int
    ) -> str:
        """Generate summary of ATS analysis.
        
        Args:
            compatibility_score: Compatibility score breakdown
            num_present_keywords: Number of present keywords
            num_missing_keywords: Number of missing keywords
            num_formatting_issues: Number of formatting issues
            
        Returns:
            Summary text
        """
        overall = compatibility_score.overall_score
        
        if overall >= 85:
            quality = "excellent"
        elif overall >= 70:
            quality = "good"
        elif overall >= 50:
            quality = "fair"
        else:
            quality = "needs improvement"
        
        summary = f"Your CV has {quality} ATS compatibility with an overall score of {overall}/100. "
        
        if num_present_keywords > 0:
            summary += f"You're using {num_present_keywords} industry-relevant keywords. "
        
        if num_missing_keywords > 0:
            summary += f"Consider adding {num_missing_keywords} additional keywords to improve matching. "
        
        if num_formatting_issues > 0:
            summary += f"There are {num_formatting_issues} formatting issues that may affect ATS parsing. "
        
        if overall >= 80:
            summary += "Your CV is well-optimized for ATS systems."
        elif overall >= 60:
            summary += "With some improvements, your CV will perform better in ATS screening."
        else:
            summary += "Significant improvements are needed to optimize for ATS systems."
        
        return summary
    
    def get_provider_info(self) -> Dict[str, str]:
        """Get information about the current LLM provider.
        
        Returns:
            Dictionary with provider name and status
        """
        return {
            "provider": self.llm_provider.get_provider_name(),
            "enabled": str(self.llm_provider.is_enabled()),
            "model": self.llm_provider.config.model
        }


class ATSAnalyzerFactory:
    """Factory for creating ATSAnalyzer instances."""
    
    @staticmethod
    def create_analyzer(llm_provider: BaseLLMProvider) -> ATSAnalyzer:
        """Create an ATSAnalyzer with the specified provider.
        
        Args:
            llm_provider: LLM provider instance
            
        Returns:
            ATSAnalyzer instance
        """
        return ATSAnalyzer(llm_provider)
    
    @staticmethod
    async def create_and_test_analyzer(
        llm_provider: BaseLLMProvider
    ) -> ATSAnalyzer:
        """Create an ATSAnalyzer and test the connection.
        
        Args:
            llm_provider: LLM provider instance
            
        Returns:
            ATSAnalyzer instance
            
        Raises:
            RuntimeError: If connection test fails
        """
        # Test connection first
        await llm_provider.test_connection()
        
        # Create and return analyzer
        return ATSAnalyzer(llm_provider)
