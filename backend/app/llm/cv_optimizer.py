"""
CV Optimizer for AI-Powered CV Analysis and Improvement

This module provides CV optimization functionality including weak language detection,
metrics gap identification, and structural analysis.
"""

from typing import List, Dict, Any, Optional
import re
from datetime import datetime

from app.llm.providers.base import BaseLLMProvider, LLMResponse
from app.models.llm_models import (
    OptimizationRequest,
    OptimizationResult,
    OptimizationRecommendation,
    RecommendationCategory,
    RecommendationPriority,
    WeakLanguageDetection,
    MetricsGap,
    StructuralIssue,
    JobTailoringRequest,
    JobTailoringResult,
    JobDescriptionAnalysis,
    TailoringSuggestion,
    JobMatchRequest,
    JobMatchResult,
    JobMatchScoreBreakdown
)


class CVOptimizer:
    """AI-powered CV optimizer for analyzing and improving CV content.
    
    This class provides methods for:
    - Detecting weak or vague language
    - Identifying missing quantifiable metrics
    - Analyzing CV structure and organization
    - Generating actionable improvement recommendations
    """
    
    # Weak language patterns to detect
    WEAK_PHRASES = [
        "responsible for", "duties included", "worked on", "helped with",
        "assisted in", "participated in", "involved in", "contributed to",
        "familiar with", "knowledge of", "exposure to", "some experience",
        "various", "several", "many", "multiple", "numerous"
    ]
    
    # Passive voice indicators
    PASSIVE_INDICATORS = [
        "was", "were", "been", "being", "is", "are", "am"
    ]
    
    # Action verbs for suggestions
    STRONG_ACTION_VERBS = [
        "led", "managed", "developed", "implemented", "designed",
        "created", "built", "optimized", "improved", "increased",
        "reduced", "achieved", "delivered", "launched", "established"
    ]
    
    def __init__(self, llm_provider: BaseLLMProvider):
        """Initialize CV optimizer with LLM provider.
        
        Args:
            llm_provider: LLM provider instance to use for analysis
        """
        self.llm_provider = llm_provider

    
    async def optimize_cv(
        self,
        request: OptimizationRequest
    ) -> OptimizationResult:
        """Analyze CV and provide optimization recommendations.
        
        Args:
            request: Optimization request with CV data
            
        Returns:
            OptimizationResult with recommendations and analysis
            
        Raises:
            ValueError: If request is invalid
            RuntimeError: If analysis fails
        """
        cv_data = request.cv_data
        
        # Build comprehensive analysis prompt
        system_prompt = self._build_optimization_system_prompt()
        user_prompt = self._build_optimization_user_prompt(
            cv_data,
            request.focus_areas,
            request.include_reasoning
        )
        
        # Get LLM analysis
        response = await self.llm_provider.generate_completion(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,  # Lower temperature for more consistent analysis
            max_tokens=2000
        )
        
        # Parse LLM response into structured recommendations
        recommendations = self._parse_optimization_response(response.content, cv_data)
        
        # Perform rule-based analysis to supplement LLM
        weak_language_recs = self._detect_weak_language(cv_data)
        metrics_recs = self._identify_metrics_gaps(cv_data)
        structural_recs = self._analyze_structure(cv_data)
        
        # Combine all recommendations
        all_recommendations = recommendations + weak_language_recs + metrics_recs + structural_recs
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(all_recommendations, cv_data)
        
        # Generate summary and identify strengths
        summary = self._generate_summary(all_recommendations, overall_score)
        strengths = self._identify_strengths(cv_data)
        areas_for_improvement = self._identify_improvement_areas(all_recommendations)
        
        return OptimizationResult(
            cv_id=request.cv_id,
            overall_score=overall_score,
            recommendations=all_recommendations,
            summary=summary,
            strengths=strengths,
            areas_for_improvement=areas_for_improvement,
            analyzed_at=datetime.now(),
            model=response.model,
            provider=response.provider
        )

    
    def _detect_weak_language(self, cv_data: Dict[str, Any]) -> List[OptimizationRecommendation]:
        """Detect weak or vague language in CV content.
        
        Args:
            cv_data: Complete CV data
            
        Returns:
            List of recommendations for weak language issues
        """
        recommendations = []
        
        # Check experience descriptions
        for exp in cv_data.get("experience", []):
            description = exp.get("description", "")
            location = f"Experience: {exp.get('title', 'Unknown')} at {exp.get('company', 'Unknown')}"
            
            # Check for weak phrases
            for weak_phrase in self.WEAK_PHRASES:
                if weak_phrase.lower() in description.lower():
                    # Find a strong alternative
                    suggestion = self._suggest_strong_alternative(weak_phrase, description)
                    
                    recommendations.append(OptimizationRecommendation(
                        category=RecommendationCategory.LANGUAGE,
                        priority=RecommendationPriority.MEDIUM,
                        issue=f"Weak phrase detected: '{weak_phrase}'",
                        suggestion=f"Replace with stronger action verb: {suggestion}",
                        location=location,
                        current_text=description,
                        reasoning="Weak phrases reduce impact. Use strong action verbs to demonstrate ownership and achievement."
                    ))
            
            # Check for passive voice
            if self._contains_passive_voice(description):
                recommendations.append(OptimizationRecommendation(
                    category=RecommendationCategory.LANGUAGE,
                    priority=RecommendationPriority.MEDIUM,
                    issue="Passive voice detected",
                    suggestion="Rewrite in active voice to show direct ownership of accomplishments",
                    location=location,
                    current_text=description,
                    reasoning="Active voice is more engaging and clearly demonstrates your role and impact."
                ))
            
            # Check achievements
            for i, achievement in enumerate(exp.get("achievements", [])):
                if self._contains_weak_language(achievement):
                    recommendations.append(OptimizationRecommendation(
                        category=RecommendationCategory.LANGUAGE,
                        priority=RecommendationPriority.HIGH,
                        issue="Achievement statement uses weak language",
                        suggestion="Start with a strong action verb and include quantifiable results",
                        location=f"{location} - Achievement {i+1}",
                        current_text=achievement,
                        reasoning="Achievement statements should be impactful and demonstrate clear results."
                    ))
        
        # Check summary
        summary = cv_data.get("summary", "")
        if summary and self._contains_weak_language(summary):
            recommendations.append(OptimizationRecommendation(
                category=RecommendationCategory.LANGUAGE,
                priority=RecommendationPriority.HIGH,
                issue="Professional summary contains weak language",
                suggestion="Use confident, achievement-focused language in your summary",
                location="Professional Summary",
                current_text=summary,
                reasoning="Your summary is the first thing recruiters read. Make it impactful."
            ))
        
        return recommendations

    
    def _identify_metrics_gaps(self, cv_data: Dict[str, Any]) -> List[OptimizationRecommendation]:
        """Identify missing quantifiable metrics in CV content.
        
        Args:
            cv_data: Complete CV data
            
        Returns:
            List of recommendations for adding metrics
        """
        recommendations = []
        
        # Check experience entries
        for exp in cv_data.get("experience", []):
            location = f"Experience: {exp.get('title', 'Unknown')} at {exp.get('company', 'Unknown')}"
            description = exp.get("description", "")
            achievements = exp.get("achievements", [])
            
            # Check if description lacks numbers
            if description and not self._contains_metrics(description):
                recommendations.append(OptimizationRecommendation(
                    category=RecommendationCategory.METRICS,
                    priority=RecommendationPriority.HIGH,
                    issue="Description lacks quantifiable metrics",
                    suggestion="Add specific numbers, percentages, or metrics to demonstrate impact (e.g., team size, budget, performance improvements)",
                    location=location,
                    current_text=description,
                    reasoning="Quantifiable metrics make your impact concrete and memorable."
                ))
            
            # Check achievements for metrics
            for i, achievement in enumerate(achievements):
                if not self._contains_metrics(achievement):
                    recommendations.append(OptimizationRecommendation(
                        category=RecommendationCategory.METRICS,
                        priority=RecommendationPriority.HIGH,
                        issue="Achievement lacks quantifiable results",
                        suggestion="Add specific metrics: percentages, dollar amounts, time saved, or other measurable outcomes",
                        location=f"{location} - Achievement {i+1}",
                        current_text=achievement,
                        reasoning="Achievements without metrics are less credible and impactful."
                    ))
            
            # If no achievements listed, suggest adding them
            if not achievements and description:
                recommendations.append(OptimizationRecommendation(
                    category=RecommendationCategory.METRICS,
                    priority=RecommendationPriority.HIGH,
                    issue="No achievement statements listed",
                    suggestion="Add 2-4 bullet points highlighting specific achievements with quantifiable results",
                    location=location,
                    reasoning="Achievement statements are crucial for demonstrating your value and impact."
                ))
        
        return recommendations

    
    def _analyze_structure(self, cv_data: Dict[str, Any]) -> List[OptimizationRecommendation]:
        """Analyze CV structure and organization.
        
        Args:
            cv_data: Complete CV data
            
        Returns:
            List of recommendations for structural improvements
        """
        recommendations = []
        
        # Check for professional summary
        if not cv_data.get("summary"):
            recommendations.append(OptimizationRecommendation(
                category=RecommendationCategory.STRUCTURE,
                priority=RecommendationPriority.HIGH,
                issue="Missing professional summary",
                suggestion="Add a 3-4 sentence professional summary at the top of your CV",
                location="Professional Summary",
                reasoning="A strong summary helps recruiters quickly understand your value proposition."
            ))
        
        # Check experience section
        experiences = cv_data.get("experience", [])
        if not experiences:
            recommendations.append(OptimizationRecommendation(
                category=RecommendationCategory.STRUCTURE,
                priority=RecommendationPriority.HIGH,
                issue="No work experience listed",
                suggestion="Add your work experience with descriptions and achievements",
                location="Experience Section",
                reasoning="Work experience is the most important section of your CV."
            ))
        elif len(experiences) > 0:
            # Check if experiences are in reverse chronological order
            if not self._is_reverse_chronological(experiences):
                recommendations.append(OptimizationRecommendation(
                    category=RecommendationCategory.STRUCTURE,
                    priority=RecommendationPriority.MEDIUM,
                    issue="Experience entries not in reverse chronological order",
                    suggestion="List experiences starting with most recent first",
                    location="Experience Section",
                    reasoning="Reverse chronological order is the standard format expected by recruiters."
                ))
        
        # Check education section
        education = cv_data.get("education", [])
        if not education:
            recommendations.append(OptimizationRecommendation(
                category=RecommendationCategory.STRUCTURE,
                priority=RecommendationPriority.MEDIUM,
                issue="No education listed",
                suggestion="Add your educational background",
                location="Education Section",
                reasoning="Education is an important credential for most positions."
            ))
        
        # Check skills section
        skills = cv_data.get("skills", {})
        skill_categories = skills.get("categories", [])
        if not skill_categories:
            recommendations.append(OptimizationRecommendation(
                category=RecommendationCategory.STRUCTURE,
                priority=RecommendationPriority.MEDIUM,
                issue="No skills listed",
                suggestion="Add a skills section with relevant technical and professional skills",
                location="Skills Section",
                reasoning="A well-organized skills section helps with ATS matching and quick scanning."
            ))
        elif len(skill_categories) > 5:
            recommendations.append(OptimizationRecommendation(
                category=RecommendationCategory.STRUCTURE,
                priority=RecommendationPriority.LOW,
                issue="Too many skill categories",
                suggestion="Consolidate to 3-5 focused skill categories for better readability",
                location="Skills Section",
                reasoning="Too many categories can dilute your core competencies."
            ))
        
        # Check overall length
        total_content_length = self._estimate_cv_length(cv_data)
        if total_content_length < 500:
            recommendations.append(OptimizationRecommendation(
                category=RecommendationCategory.CONTENT,
                priority=RecommendationPriority.MEDIUM,
                issue="CV appears too brief",
                suggestion="Expand descriptions and add more detail about your experience and achievements",
                location="Overall CV",
                reasoning="A CV that's too brief may not provide enough information to assess your qualifications."
            ))
        elif total_content_length > 5000:
            recommendations.append(OptimizationRecommendation(
                category=RecommendationCategory.CONTENT,
                priority=RecommendationPriority.MEDIUM,
                issue="CV may be too lengthy",
                suggestion="Focus on most relevant and recent experience; consider removing older or less relevant details",
                location="Overall CV",
                reasoning="Recruiters typically spend 6-10 seconds on initial CV review. Keep it concise."
            ))
        
        return recommendations

    
    # Helper methods
    
    def _build_optimization_system_prompt(self) -> str:
        """Build system prompt for CV optimization."""
        return """You are an expert CV optimization consultant with years of experience helping professionals 
improve their CVs. Your role is to analyze CVs and provide specific, actionable recommendations for improvement.

Focus on:
- Identifying weak or vague language
- Spotting missing quantifiable metrics
- Evaluating structure and organization
- Assessing overall impact and professionalism
- Providing specific, actionable suggestions

Be constructive and specific in your feedback. Always explain why a change would improve the CV."""
    
    def _build_optimization_user_prompt(
        self,
        cv_data: Dict[str, Any],
        focus_areas: Optional[List[RecommendationCategory]],
        include_reasoning: bool
    ) -> str:
        """Build user prompt for CV optimization.
        
        Args:
            cv_data: Complete CV data
            focus_areas: Specific areas to focus on
            include_reasoning: Whether to include reasoning
            
        Returns:
            Formatted user prompt
        """
        # Extract key CV information
        personal_info = cv_data.get("personal_info", {})
        name = personal_info.get("name", "Unknown")
        title = personal_info.get("title", "Professional")
        summary = cv_data.get("summary", "")
        experiences = cv_data.get("experience", [])
        education = cv_data.get("education", [])
        
        # Build CV text representation
        cv_text = f"Name: {name}\nTitle: {title}\n\n"
        
        if summary:
            cv_text += f"Summary:\n{summary}\n\n"
        
        cv_text += "Experience:\n"
        for exp in experiences[:3]:  # Limit to first 3 for prompt length
            cv_text += f"- {exp.get('title', '')} at {exp.get('company', '')}\n"
            if exp.get('description'):
                cv_text += f"  {exp.get('description', '')}\n"
            for achievement in exp.get('achievements', [])[:2]:  # Limit achievements
                cv_text += f"  • {achievement}\n"
            cv_text += "\n"
        
        # Build focus areas text
        focus_text = ""
        if focus_areas:
            focus_text = f"\nFocus specifically on these areas: {', '.join([a.value for a in focus_areas])}"
        
        reasoning_text = ""
        if include_reasoning:
            reasoning_text = "\nFor each recommendation, explain why the change would improve the CV."
        
        prompt = f"""Analyze this CV and provide specific optimization recommendations:

{cv_text}

Provide recommendations in the following format:
1. [Category] [Priority: High/Medium/Low] Issue: [description]
   Suggestion: [specific actionable suggestion]
   Location: [where in CV]
   {reasoning_text}

{focus_text}

Focus on:
- Weak or vague language that should be strengthened
- Missing quantifiable metrics and achievements
- Structural or organizational improvements
- Content clarity and impact

Provide 5-10 specific, actionable recommendations."""
        
        return prompt

    
    def _parse_optimization_response(
        self,
        response_text: str,
        cv_data: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Parse LLM response into structured recommendations.
        
        Args:
            response_text: Raw LLM response
            cv_data: CV data for context
            
        Returns:
            List of OptimizationRecommendation objects
        """
        recommendations = []
        
        # Split response into individual recommendations
        # Look for numbered list items
        lines = response_text.split('\n')
        current_rec = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this is a new recommendation (starts with number)
            if re.match(r'^\d+\.', line):
                # Save previous recommendation if exists
                if current_rec:
                    rec = self._create_recommendation_from_parsed(current_rec)
                    if rec:
                        recommendations.append(rec)
                    current_rec = {}
                
                # Parse the header line
                # Format: 1. [Category] [Priority: High] Issue: description
                category_match = re.search(r'\[([^\]]+)\]', line)
                priority_match = re.search(r'Priority:\s*(High|Medium|Low)', line, re.IGNORECASE)
                issue_match = re.search(r'Issue:\s*(.+)$', line)
                
                if category_match:
                    current_rec['category'] = category_match.group(1).strip().lower()
                if priority_match:
                    current_rec['priority'] = priority_match.group(1).strip().lower()
                if issue_match:
                    current_rec['issue'] = issue_match.group(1).strip()
            
            # Parse suggestion line
            elif line.startswith('Suggestion:'):
                current_rec['suggestion'] = line.replace('Suggestion:', '').strip()
            
            # Parse location line
            elif line.startswith('Location:'):
                current_rec['location'] = line.replace('Location:', '').strip()
            
            # Parse reasoning line
            elif line.startswith('Reasoning:') or line.startswith('Why:'):
                current_rec['reasoning'] = line.split(':', 1)[1].strip()
        
        # Add the last recommendation
        if current_rec:
            rec = self._create_recommendation_from_parsed(current_rec)
            if rec:
                recommendations.append(rec)
        
        return recommendations
    
    def _create_recommendation_from_parsed(
        self,
        parsed_data: Dict[str, str]
    ) -> Optional[OptimizationRecommendation]:
        """Create OptimizationRecommendation from parsed data.
        
        Args:
            parsed_data: Dictionary with parsed recommendation data
            
        Returns:
            OptimizationRecommendation or None if invalid
        """
        if not parsed_data.get('issue') or not parsed_data.get('suggestion'):
            return None
        
        # Map category string to enum
        category_map = {
            'language': RecommendationCategory.LANGUAGE,
            'metrics': RecommendationCategory.METRICS,
            'structure': RecommendationCategory.STRUCTURE,
            'formatting': RecommendationCategory.FORMATTING,
            'content': RecommendationCategory.CONTENT,
            'keywords': RecommendationCategory.KEYWORDS,
            'clarity': RecommendationCategory.CLARITY,
            'impact': RecommendationCategory.IMPACT
        }
        
        category = category_map.get(
            parsed_data.get('category', 'content').lower(),
            RecommendationCategory.CONTENT
        )
        
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
        
        return OptimizationRecommendation(
            category=category,
            priority=priority,
            issue=parsed_data['issue'],
            suggestion=parsed_data['suggestion'],
            location=parsed_data.get('location', 'General'),
            reasoning=parsed_data.get('reasoning')
        )

    
    def _contains_weak_language(self, text: str) -> bool:
        """Check if text contains weak language patterns.
        
        Args:
            text: Text to check
            
        Returns:
            True if weak language detected
        """
        text_lower = text.lower()
        return any(phrase in text_lower for phrase in self.WEAK_PHRASES)
    
    def _contains_passive_voice(self, text: str) -> bool:
        """Check if text contains passive voice.
        
        Args:
            text: Text to check
            
        Returns:
            True if passive voice detected
        """
        text_lower = text.lower()
        # Simple heuristic: check for "was/were" followed by past participle
        for indicator in self.PASSIVE_INDICATORS:
            if f" {indicator} " in f" {text_lower} ":
                return True
        return False
    
    def _contains_metrics(self, text: str) -> bool:
        """Check if text contains quantifiable metrics.
        
        Args:
            text: Text to check
            
        Returns:
            True if metrics found
        """
        # Look for numbers, percentages, dollar amounts
        patterns = [
            r'\d+%',  # Percentages
            r'\$\d+',  # Dollar amounts
            r'\d+\+',  # Numbers with plus
            r'\d+\s*(million|billion|thousand|k)',  # Large numbers
            r'\d+\s*(years?|months?|weeks?|days?)',  # Time periods
            r'\d+\s*(people|users|customers|clients|team)',  # Quantities
            r'\d+x',  # Multipliers
        ]
        
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        # Also check for standalone numbers
        if re.search(r'\b\d+\b', text):
            return True
        
        return False
    
    def _suggest_strong_alternative(self, weak_phrase: str, context: str) -> str:
        """Suggest a strong alternative to weak phrase.
        
        Args:
            weak_phrase: The weak phrase to replace
            context: Context for better suggestion
            
        Returns:
            Suggested strong alternative
        """
        # Map weak phrases to strong alternatives
        alternatives = {
            "responsible for": "Led, Managed, Oversaw",
            "duties included": "Delivered, Executed, Performed",
            "worked on": "Developed, Built, Created",
            "helped with": "Contributed to, Supported, Facilitated",
            "assisted in": "Collaborated on, Supported, Enabled",
            "participated in": "Contributed to, Engaged in, Drove",
            "involved in": "Led, Managed, Executed",
            "contributed to": "Delivered, Achieved, Drove",
            "familiar with": "Proficient in, Experienced with, Skilled in",
            "knowledge of": "Expertise in, Proficiency in, Mastery of"
        }
        
        return alternatives.get(weak_phrase.lower(), "Use a strong action verb")
    
    def _is_reverse_chronological(self, experiences: List[Dict[str, Any]]) -> bool:
        """Check if experiences are in reverse chronological order.
        
        Args:
            experiences: List of experience entries
            
        Returns:
            True if in reverse chronological order
        """
        if len(experiences) < 2:
            return True
        
        # Simple check: compare start dates
        # This is a basic implementation; could be enhanced
        for i in range(len(experiences) - 1):
            current_date = experiences[i].get('start_date', '')
            next_date = experiences[i + 1].get('start_date', '')
            
            # If we can compare dates and current is older than next, order is wrong
            if current_date and next_date and current_date < next_date:
                return False
        
        return True
    
    def _estimate_cv_length(self, cv_data: Dict[str, Any]) -> int:
        """Estimate total content length of CV.
        
        Args:
            cv_data: Complete CV data
            
        Returns:
            Estimated character count
        """
        total_length = 0
        
        # Count summary
        total_length += len(cv_data.get('summary', ''))
        
        # Count experience
        for exp in cv_data.get('experience', []):
            total_length += len(exp.get('description', ''))
            for achievement in exp.get('achievements', []):
                total_length += len(achievement)
        
        # Count education
        for edu in cv_data.get('education', []):
            total_length += len(edu.get('description', ''))
        
        return total_length

    
    def _calculate_overall_score(
        self,
        recommendations: List[OptimizationRecommendation],
        cv_data: Dict[str, Any]
    ) -> float:
        """Calculate overall CV quality score.
        
        Args:
            recommendations: List of recommendations
            cv_data: CV data
            
        Returns:
            Score from 0-100
        """
        # Start with base score
        base_score = 70.0
        
        # Deduct points for issues
        high_priority_count = sum(1 for r in recommendations if r.priority == RecommendationPriority.HIGH)
        medium_priority_count = sum(1 for r in recommendations if r.priority == RecommendationPriority.MEDIUM)
        low_priority_count = sum(1 for r in recommendations if r.priority == RecommendationPriority.LOW)
        
        # Deduct points based on priority
        score = base_score
        score -= high_priority_count * 5.0  # -5 points per high priority issue
        score -= medium_priority_count * 2.0  # -2 points per medium priority issue
        score -= low_priority_count * 0.5  # -0.5 points per low priority issue
        
        # Bonus points for good practices
        if cv_data.get('summary'):
            score += 5.0
        
        if len(cv_data.get('experience', [])) >= 2:
            score += 5.0
        
        # Check if experiences have achievements
        experiences_with_achievements = sum(
            1 for exp in cv_data.get('experience', [])
            if exp.get('achievements')
        )
        if experiences_with_achievements > 0:
            score += 5.0
        
        # Ensure score is in valid range
        return max(0.0, min(100.0, score))
    
    def _generate_summary(
        self,
        recommendations: List[OptimizationRecommendation],
        overall_score: float
    ) -> str:
        """Generate summary of optimization analysis.
        
        Args:
            recommendations: List of recommendations
            overall_score: Overall quality score
            
        Returns:
            Summary text
        """
        high_count = sum(1 for r in recommendations if r.priority == RecommendationPriority.HIGH)
        medium_count = sum(1 for r in recommendations if r.priority == RecommendationPriority.MEDIUM)
        
        if overall_score >= 85:
            quality = "excellent"
        elif overall_score >= 70:
            quality = "good"
        elif overall_score >= 50:
            quality = "fair"
        else:
            quality = "needs improvement"
        
        summary = f"Your CV is in {quality} shape with an overall score of {overall_score:.1f}/100. "
        
        if high_count > 0:
            summary += f"There are {high_count} high-priority issues that should be addressed immediately. "
        
        if medium_count > 0:
            summary += f"Additionally, {medium_count} medium-priority improvements would enhance your CV. "
        
        if high_count == 0 and medium_count == 0:
            summary += "Your CV is well-optimized with only minor suggestions for polish. "
        
        return summary
    
    def _identify_strengths(self, cv_data: Dict[str, Any]) -> List[str]:
        """Identify strengths in the CV.
        
        Args:
            cv_data: Complete CV data
            
        Returns:
            List of identified strengths
        """
        strengths = []
        
        # Check for professional summary
        if cv_data.get('summary'):
            strengths.append("Includes professional summary")
        
        # Check for quantifiable achievements
        has_metrics = False
        for exp in cv_data.get('experience', []):
            for achievement in exp.get('achievements', []):
                if self._contains_metrics(achievement):
                    has_metrics = True
                    break
            if has_metrics:
                break
        
        if has_metrics:
            strengths.append("Uses quantifiable achievements")
        
        # Check for multiple experiences
        if len(cv_data.get('experience', [])) >= 3:
            strengths.append("Demonstrates substantial work history")
        
        # Check for skills organization
        skill_categories = cv_data.get('skills', {}).get('categories', [])
        if len(skill_categories) >= 2:
            strengths.append("Well-organized skills section")
        
        # Check for education
        if cv_data.get('education'):
            strengths.append("Includes educational background")
        
        # Check for certifications
        if cv_data.get('certifications'):
            strengths.append("Lists relevant certifications")
        
        return strengths if strengths else ["CV has basic structure in place"]
    
    def _identify_improvement_areas(
        self,
        recommendations: List[OptimizationRecommendation]
    ) -> List[str]:
        """Identify high-level areas for improvement.
        
        Args:
            recommendations: List of recommendations
            
        Returns:
            List of improvement areas
        """
        # Group by category
        category_counts = {}
        for rec in recommendations:
            if rec.priority in [RecommendationPriority.HIGH, RecommendationPriority.MEDIUM]:
                category = rec.category.value
                category_counts[category] = category_counts.get(category, 0) + 1
        
        # Sort by count and return top areas
        sorted_areas = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        
        area_descriptions = {
            'language': 'Strengthen language and use more impactful verbs',
            'metrics': 'Add quantifiable metrics and achievements',
            'structure': 'Improve organization and structure',
            'content': 'Enhance content quality and relevance',
            'clarity': 'Improve clarity and conciseness',
            'keywords': 'Optimize keyword usage',
            'impact': 'Increase impact and achievement focus'
        }
        
        areas = [
            area_descriptions.get(area, area.title())
            for area, count in sorted_areas[:5]  # Top 5 areas
        ]
        
        return areas if areas else ["Continue refining and updating regularly"]
    
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
    
    # ========================================================================
    # Job Tailoring Methods
    # ========================================================================
    
    async def analyze_job_description(
        self,
        job_description: str
    ) -> JobDescriptionAnalysis:
        """Analyze a job description to extract requirements, skills, and keywords.
        
        Args:
            job_description: Raw job description text
            
        Returns:
            JobDescriptionAnalysis with extracted information
            
        Raises:
            ValueError: If job description is invalid
            RuntimeError: If analysis fails
        """
        if not job_description or len(job_description.strip()) < 10:
            raise ValueError("Job description must be at least 10 characters")
        
        # Build analysis prompt
        system_prompt = self._build_job_analysis_system_prompt()
        user_prompt = self._build_job_analysis_user_prompt(job_description)
        
        # Get LLM analysis
        response = await self.llm_provider.generate_completion(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2,  # Lower temperature for more consistent extraction
            max_tokens=1500
        )
        
        # Parse response into structured analysis
        analysis = self._parse_job_description_response(response.content, job_description)
        
        return analysis
    
    async def tailor_cv_to_job(
        self,
        request: JobTailoringRequest
    ) -> JobTailoringResult:
        """Tailor CV to match a specific job description.
        
        Args:
            request: Job tailoring request with CV data and job description
            
        Returns:
            JobTailoringResult with tailoring suggestions
            
        Raises:
            ValueError: If request is invalid
            RuntimeError: If tailoring fails
        """
        cv_data = request.cv_data
        job_description = request.job_description
        
        # First, analyze the job description
        job_analysis = await self.analyze_job_description(job_description)
        
        # Extract current CV keywords
        cv_keywords = self._extract_cv_keywords(cv_data)
        
        # Identify matching and missing keywords
        matching_keywords = [
            kw for kw in job_analysis.keywords
            if any(kw.lower() in cv_kw.lower() or cv_kw.lower() in kw.lower() 
                   for cv_kw in cv_keywords)
        ]
        
        missing_keywords = [
            kw for kw in job_analysis.keywords
            if kw not in matching_keywords
        ]
        
        # Calculate initial match score
        keyword_match_score = (len(matching_keywords) / max(len(job_analysis.keywords), 1)) * 100
        
        # Generate tailoring suggestions using LLM
        system_prompt = self._build_tailoring_system_prompt()
        user_prompt = self._build_tailoring_user_prompt(
            cv_data,
            job_analysis,
            missing_keywords,
            request.focus_sections
        )
        
        response = await self.llm_provider.generate_completion(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2000
        )
        
        # Parse tailoring suggestions
        suggestions = self._parse_tailoring_response(response.content, cv_data, job_analysis)
        
        # Add rule-based suggestions for missing keywords
        keyword_suggestions = self._generate_keyword_suggestions(
            cv_data,
            missing_keywords,
            job_analysis
        )
        suggestions.extend(keyword_suggestions)
        
        # Add experience prioritization suggestions
        prioritization_suggestions = self._generate_prioritization_suggestions(
            cv_data,
            job_analysis
        )
        suggestions.extend(prioritization_suggestions)
        
        # Calculate overall match score
        match_score = self._calculate_match_score(
            cv_data,
            job_analysis,
            matching_keywords,
            missing_keywords
        )
        
        # Generate summary
        summary = self._generate_tailoring_summary(
            match_score,
            len(suggestions),
            len(missing_keywords),
            job_analysis
        )
        
        return JobTailoringResult(
            cv_id=request.cv_id,
            job_analysis=job_analysis,
            suggestions=suggestions,
            missing_keywords=missing_keywords,
            matching_keywords=matching_keywords,
            match_score=match_score,
            summary=summary,
            analyzed_at=datetime.now(),
            model=response.model,
            provider=response.provider
        )
    
    # Helper methods for job tailoring
    
    def _build_job_analysis_system_prompt(self) -> str:
        """Build system prompt for job description analysis."""
        return """You are an expert job description analyzer. Your role is to extract key information 
from job descriptions including:
- Job title and company (if mentioned)
- Key requirements and qualifications
- Required skills and technologies
- Important keywords for ATS optimization
- Experience level required
- Industry or field

Be thorough and precise in your extraction. Focus on concrete requirements and skills."""
    
    def _build_job_analysis_user_prompt(self, job_description: str) -> str:
        """Build user prompt for job description analysis.
        
        Args:
            job_description: Raw job description text
            
        Returns:
            Formatted user prompt
        """
        prompt = f"""Analyze this job description and extract key information:

{job_description}

Provide the analysis in the following format:

Job Title: [extracted job title]
Company: [company name if mentioned, otherwise "Not specified"]
Experience Level: [entry/mid/senior/executive level]
Industry: [industry or field]

Requirements:
- [requirement 1]
- [requirement 2]
- [requirement 3]
...

Skills:
- [skill 1]
- [skill 2]
- [skill 3]
...

Keywords (important terms for ATS):
- [keyword 1]
- [keyword 2]
- [keyword 3]
...

Focus on extracting concrete, specific information. Include technical skills, soft skills, 
certifications, and any other qualifications mentioned."""
        
        return prompt
    
    def _parse_job_description_response(
        self,
        response_text: str,
        original_job_description: str
    ) -> JobDescriptionAnalysis:
        """Parse LLM response into JobDescriptionAnalysis.
        
        Args:
            response_text: Raw LLM response
            original_job_description: Original job description for fallback
            
        Returns:
            JobDescriptionAnalysis object
        """
        lines = response_text.split('\n')
        
        job_title = "Not specified"
        company = None
        requirements = []
        skills = []
        keywords = []
        experience_level = None
        industry = None
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for section headers
            if line.startswith("Job Title:"):
                job_title = line.replace("Job Title:", "").strip()
            elif line.startswith("Company:"):
                company_text = line.replace("Company:", "").strip()
                if company_text and company_text.lower() != "not specified":
                    company = company_text
            elif line.startswith("Experience Level:"):
                experience_level = line.replace("Experience Level:", "").strip()
            elif line.startswith("Industry:"):
                industry = line.replace("Industry:", "").strip()
            elif line.startswith("Requirements:"):
                current_section = "requirements"
            elif line.startswith("Skills:"):
                current_section = "skills"
            elif line.startswith("Keywords"):
                current_section = "keywords"
            elif line.startswith("-") or line.startswith("•"):
                # This is a list item
                item = line.lstrip("-•").strip()
                if item:
                    if current_section == "requirements":
                        requirements.append(item)
                    elif current_section == "skills":
                        skills.append(item)
                    elif current_section == "keywords":
                        keywords.append(item)
        
        # Fallback: extract keywords from job description if none found
        if not keywords:
            keywords = self._extract_keywords_from_text(original_job_description)
        
        return JobDescriptionAnalysis(
            job_title=job_title,
            company=company,
            requirements=requirements,
            skills=skills,
            keywords=keywords,
            experience_level=experience_level,
            industry=industry
        )
    
    def _extract_keywords_from_text(self, text: str) -> List[str]:
        """Extract potential keywords from text using simple heuristics.
        
        Args:
            text: Text to extract keywords from
            
        Returns:
            List of extracted keywords
        """
        # Common technical terms and skills
        common_keywords = [
            "python", "java", "javascript", "typescript", "react", "vue", "angular",
            "node", "sql", "nosql", "mongodb", "postgresql", "aws", "azure", "gcp",
            "docker", "kubernetes", "ci/cd", "agile", "scrum", "api", "rest",
            "microservices", "machine learning", "ai", "data", "analytics",
            "leadership", "management", "communication", "problem solving"
        ]
        
        text_lower = text.lower()
        found_keywords = []
        
        for keyword in common_keywords:
            if keyword in text_lower:
                found_keywords.append(keyword.title())
        
        return found_keywords[:20]  # Limit to 20 keywords
    
    def _extract_cv_keywords(self, cv_data: Dict[str, Any]) -> List[str]:
        """Extract all keywords from CV data.
        
        Args:
            cv_data: Complete CV data
            
        Returns:
            List of keywords found in CV
        """
        keywords = []
        
        # Extract from skills
        skills_section = cv_data.get("skills", {})
        for category in skills_section.get("categories", []):
            keywords.extend(category.get("skills", []))
        
        # Extract from experience descriptions
        for exp in cv_data.get("experience", []):
            # Add job title
            if exp.get("title"):
                keywords.append(exp["title"])
            
            # Extract from description
            description = exp.get("description", "")
            if description:
                # Simple word extraction (could be enhanced)
                words = description.split()
                keywords.extend([w.strip(".,;:") for w in words if len(w) > 3])
        
        # Extract from summary
        summary = cv_data.get("summary", "")
        if summary:
            words = summary.split()
            keywords.extend([w.strip(".,;:") for w in words if len(w) > 3])
        
        return keywords
    
    def _build_tailoring_system_prompt(self) -> str:
        """Build system prompt for CV tailoring."""
        return """You are an expert CV tailoring consultant. Your role is to suggest specific 
modifications to align a CV with a job description while maintaining truthfulness.

Key principles:
- NEVER suggest adding false information or skills the candidate doesn't have
- Focus on emphasizing relevant existing experience
- Suggest natural incorporation of missing keywords where appropriate
- Recommend reordering or rephrasing to highlight relevant qualifications
- Maintain professional tone and accuracy

Your suggestions should be specific, actionable, and honest."""
    
    def _build_tailoring_user_prompt(
        self,
        cv_data: Dict[str, Any],
        job_analysis: JobDescriptionAnalysis,
        missing_keywords: List[str],
        focus_sections: Optional[List[str]]
    ) -> str:
        """Build user prompt for CV tailoring.
        
        Args:
            cv_data: Complete CV data
            job_analysis: Analyzed job description
            missing_keywords: Keywords missing from CV
            focus_sections: Specific sections to focus on
            
        Returns:
            Formatted user prompt
        """
        # Build CV summary
        personal_info = cv_data.get("personal_info", {})
        name = personal_info.get("name", "Candidate")
        current_title = personal_info.get("title", "Professional")
        summary = cv_data.get("summary", "")
        
        experiences_text = ""
        for i, exp in enumerate(cv_data.get("experience", [])[:3], 1):
            experiences_text += f"\n{i}. {exp.get('title', '')} at {exp.get('company', '')}"
            if exp.get('description'):
                experiences_text += f"\n   {exp.get('description', '')[:200]}..."
        
        focus_text = ""
        if focus_sections:
            focus_text = f"\nFocus specifically on these sections: {', '.join(focus_sections)}"
        
        prompt = f"""Tailor this CV to match the job description:

TARGET JOB:
Title: {job_analysis.job_title}
Company: {job_analysis.company or 'Not specified'}
Key Requirements: {', '.join(job_analysis.requirements[:5])}
Required Skills: {', '.join(job_analysis.skills[:10])}

CURRENT CV:
Name: {name}
Current Title: {current_title}
Summary: {summary[:300] if summary else 'No summary'}

Recent Experience:{experiences_text}

MISSING KEYWORDS: {', '.join(missing_keywords[:10])}

{focus_text}

Provide specific tailoring suggestions in this format:

1. [Section] [Priority: High/Medium/Low]
   Current: [current text]
   Suggested: [modified text]
   Reason: [why this change helps]
   Keywords Added: [any keywords naturally incorporated]

Guidelines:
- Suggest 5-10 specific modifications
- Focus on emphasizing relevant experience
- Suggest natural keyword incorporation (don't keyword stuff)
- Recommend experience prioritization
- NEVER suggest adding false information
- Maintain professional tone and accuracy

Provide the tailoring suggestions now."""
        
        return prompt
    
    def _parse_tailoring_response(
        self,
        response_text: str,
        cv_data: Dict[str, Any],
        job_analysis: JobDescriptionAnalysis
    ) -> List[TailoringSuggestion]:
        """Parse LLM response into tailoring suggestions.
        
        Args:
            response_text: Raw LLM response
            cv_data: CV data for context
            job_analysis: Job analysis for context
            
        Returns:
            List of TailoringSuggestion objects
        """
        suggestions = []
        lines = response_text.split('\n')
        current_suggestion = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for new suggestion (starts with number)
            if re.match(r'^\d+\.', line):
                # Save previous suggestion
                if current_suggestion:
                    suggestion = self._create_tailoring_suggestion(current_suggestion)
                    if suggestion:
                        suggestions.append(suggestion)
                    current_suggestion = {}
                
                # Parse header
                section_match = re.search(r'\[([^\]]+)\]', line)
                priority_match = re.search(r'Priority:\s*(High|Medium|Low)', line, re.IGNORECASE)
                
                if section_match:
                    current_suggestion['section'] = section_match.group(1).strip()
                if priority_match:
                    current_suggestion['priority'] = priority_match.group(1).strip().lower()
            
            # Parse fields
            elif line.startswith('Current:'):
                current_suggestion['current'] = line.replace('Current:', '').strip()
            elif line.startswith('Suggested:'):
                current_suggestion['suggested'] = line.replace('Suggested:', '').strip()
            elif line.startswith('Reason:'):
                current_suggestion['reason'] = line.replace('Reason:', '').strip()
            elif line.startswith('Keywords Added:'):
                keywords_text = line.replace('Keywords Added:', '').strip()
                current_suggestion['keywords_added'] = [
                    kw.strip() for kw in keywords_text.split(',') if kw.strip()
                ]
        
        # Add last suggestion
        if current_suggestion:
            suggestion = self._create_tailoring_suggestion(current_suggestion)
            if suggestion:
                suggestions.append(suggestion)
        
        return suggestions
    
    def _create_tailoring_suggestion(
        self,
        parsed_data: Dict[str, Any]
    ) -> Optional[TailoringSuggestion]:
        """Create TailoringSuggestion from parsed data.
        
        Args:
            parsed_data: Dictionary with parsed suggestion data
            
        Returns:
            TailoringSuggestion or None if invalid
        """
        if not all(k in parsed_data for k in ['section', 'current', 'suggested', 'reason']):
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
        
        return TailoringSuggestion(
            section=parsed_data['section'],
            current=parsed_data['current'],
            suggested=parsed_data['suggested'],
            reason=parsed_data['reason'],
            keywords_added=parsed_data.get('keywords_added', []),
            priority=priority
        )
    
    def _generate_keyword_suggestions(
        self,
        cv_data: Dict[str, Any],
        missing_keywords: List[str],
        job_analysis: JobDescriptionAnalysis
    ) -> List[TailoringSuggestion]:
        """Generate suggestions for incorporating missing keywords.
        
        Args:
            cv_data: Complete CV data
            missing_keywords: Keywords missing from CV
            job_analysis: Job analysis
            
        Returns:
            List of keyword incorporation suggestions
        """
        suggestions = []
        
        # Suggest adding relevant keywords to skills section
        if missing_keywords and len(missing_keywords) <= 5:
            # Only suggest if there are a reasonable number of missing keywords
            skills_section = cv_data.get("skills", {})
            current_skills = []
            for category in skills_section.get("categories", []):
                current_skills.extend(category.get("skills", []))
            
            # Filter to keywords that might be skills
            skill_keywords = [kw for kw in missing_keywords if len(kw.split()) <= 3]
            
            if skill_keywords:
                suggestions.append(TailoringSuggestion(
                    section="Skills",
                    current=f"Current skills: {', '.join(current_skills[:5])}...",
                    suggested=f"Consider adding these relevant skills if you have experience: {', '.join(skill_keywords[:3])}",
                    reason=f"These keywords from the job description would improve ATS matching",
                    keywords_added=skill_keywords[:3],
                    priority=RecommendationPriority.MEDIUM
                ))
        
        return suggestions
    
    def _generate_prioritization_suggestions(
        self,
        cv_data: Dict[str, Any],
        job_analysis: JobDescriptionAnalysis
    ) -> List[TailoringSuggestion]:
        """Generate suggestions for prioritizing relevant experience.
        
        Args:
            cv_data: Complete CV data
            job_analysis: Job analysis
            
        Returns:
            List of prioritization suggestions
        """
        suggestions = []
        
        experiences = cv_data.get("experience", [])
        if not experiences or len(experiences) < 2:
            return suggestions
        
        # Check if experiences are ordered by relevance to job
        # Simple heuristic: check if job titles match
        job_title_lower = job_analysis.job_title.lower()
        
        for i, exp in enumerate(experiences[:3]):
            exp_title = exp.get("title", "").lower()
            
            # If a relevant experience is not first, suggest prioritization
            if i > 0 and any(word in exp_title for word in job_title_lower.split()):
                suggestions.append(TailoringSuggestion(
                    section="Experience",
                    current=f"Experience order: {experiences[0].get('title', '')} listed first",
                    suggested=f"Consider highlighting '{exp.get('title', '')}' experience more prominently as it closely matches the target role",
                    reason="Emphasizing relevant experience early helps recruiters quickly see your fit",
                    keywords_added=[],
                    priority=RecommendationPriority.MEDIUM
                ))
                break
        
        return suggestions
    
    def _calculate_match_score(
        self,
        cv_data: Dict[str, Any],
        job_analysis: JobDescriptionAnalysis,
        matching_keywords: List[str],
        missing_keywords: List[str]
    ) -> float:
        """Calculate overall match score between CV and job.
        
        Args:
            cv_data: Complete CV data
            job_analysis: Job analysis
            matching_keywords: Keywords that match
            missing_keywords: Keywords that are missing
            
        Returns:
            Match score from 0-100
        """
        # Keyword match component (40% of score)
        total_keywords = len(matching_keywords) + len(missing_keywords)
        keyword_score = (len(matching_keywords) / max(total_keywords, 1)) * 40
        
        # Skills match component (30% of score)
        cv_skills = []
        for category in cv_data.get("skills", {}).get("categories", []):
            cv_skills.extend([s.lower() for s in category.get("skills", [])])
        
        job_skills = [s.lower() for s in job_analysis.skills]
        matching_skills = sum(1 for js in job_skills if any(js in cvs or cvs in js for cvs in cv_skills))
        skills_score = (matching_skills / max(len(job_skills), 1)) * 30
        
        # Experience relevance component (30% of score)
        experience_score = 30  # Base score
        
        # Check if CV has relevant experience
        experiences = cv_data.get("experience", [])
        if experiences:
            job_title_words = set(job_analysis.job_title.lower().split())
            
            for exp in experiences:
                exp_title_words = set(exp.get("title", "").lower().split())
                # If there's overlap in job titles, boost score
                if job_title_words & exp_title_words:
                    experience_score = 30
                    break
            else:
                # No direct title match, reduce score slightly
                experience_score = 20
        else:
            experience_score = 10
        
        total_score = keyword_score + skills_score + experience_score
        return min(100.0, max(0.0, total_score))
    
    def _generate_tailoring_summary(
        self,
        match_score: float,
        num_suggestions: int,
        num_missing_keywords: int,
        job_analysis: JobDescriptionAnalysis
    ) -> str:
        """Generate summary of tailoring analysis.
        
        Args:
            match_score: Overall match score
            num_suggestions: Number of suggestions generated
            num_missing_keywords: Number of missing keywords
            job_analysis: Job analysis
            
        Returns:
            Summary text
        """
        if match_score >= 80:
            match_quality = "excellent"
        elif match_score >= 60:
            match_quality = "good"
        elif match_score >= 40:
            match_quality = "moderate"
        else:
            match_quality = "low"
        
        summary = f"Your CV has a {match_quality} match ({match_score:.1f}/100) with the {job_analysis.job_title} position. "
        
        if num_suggestions > 0:
            summary += f"We've identified {num_suggestions} specific ways to improve your alignment with this role. "
        
        if num_missing_keywords > 0:
            summary += f"Consider incorporating {num_missing_keywords} relevant keywords to improve ATS compatibility. "
        
        if match_score >= 70:
            summary += "Your CV is well-positioned for this role with minor adjustments."
        else:
            summary += "Implementing these suggestions will significantly strengthen your application."
        
        return summary
    
    async def match_cv_to_job(
        self,
        request: JobMatchRequest
    ) -> JobMatchResult:
        """Calculate comprehensive job match score with detailed breakdown.
        
        This method provides a detailed analysis of how well a CV matches a job description,
        including:
        - Overall match score (0-100%)
        - Keyword alignment score
        - Experience relevance score
        - Skills match score
        - Requirements match score
        - Matched and missing skills, requirements, keywords
        - Qualification gaps and strengths
        - Recommendations for improvement
        
        Args:
            request: Job match request with CV data and job description
            
        Returns:
            JobMatchResult with comprehensive match analysis
            
        Raises:
            ValueError: If request is invalid
            RuntimeError: If matching analysis fails
        """
        cv_data = request.cv_data
        job_description = request.job_description
        
        # First, analyze the job description
        job_analysis = await self.analyze_job_description(job_description)
        
        # Extract CV data for matching
        cv_keywords = self._extract_cv_keywords(cv_data)
        cv_skills = self._extract_cv_skills(cv_data)
        cv_experiences = cv_data.get("experience", [])
        
        # Match keywords
        matched_keywords = []
        missing_keywords = []
        for keyword in job_analysis.keywords:
            keyword_lower = keyword.lower()
            if any(keyword_lower in cv_kw.lower() or cv_kw.lower() in keyword_lower 
                   for cv_kw in cv_keywords):
                matched_keywords.append(keyword)
            else:
                missing_keywords.append(keyword)
        
        # Match skills
        matched_skills = []
        missing_skills = []
        for skill in job_analysis.skills:
            skill_lower = skill.lower()
            if any(skill_lower in cv_skill.lower() or cv_skill.lower() in skill_lower 
                   for cv_skill in cv_skills):
                matched_skills.append(skill)
            else:
                missing_skills.append(skill)
        
        # Match requirements using LLM for more nuanced analysis
        matched_requirements, missing_requirements = await self._match_requirements(
            cv_data,
            job_analysis.requirements
        )
        
        # Calculate individual scores
        keyword_alignment_score = self._calculate_keyword_alignment_score(
            matched_keywords,
            missing_keywords
        )
        
        skills_match_score = self._calculate_skills_match_score(
            matched_skills,
            missing_skills
        )
        
        requirements_match_score = self._calculate_requirements_match_score(
            matched_requirements,
            missing_requirements
        )
        
        experience_relevance_score = self._calculate_experience_relevance_score(
            cv_experiences,
            job_analysis
        )
        
        # Calculate overall score (weighted average)
        overall_score = (
            keyword_alignment_score * 0.25 +  # 25% weight
            skills_match_score * 0.30 +        # 30% weight
            requirements_match_score * 0.25 +  # 25% weight
            experience_relevance_score * 0.20  # 20% weight
        )
        
        # Create score breakdown
        score_breakdown = JobMatchScoreBreakdown(
            overall_score=overall_score,
            keyword_alignment_score=keyword_alignment_score,
            experience_relevance_score=experience_relevance_score,
            skills_match_score=skills_match_score,
            requirements_match_score=requirements_match_score
        )
        
        # Identify qualification gaps
        qualification_gaps = self._identify_qualification_gaps(
            missing_skills,
            missing_requirements,
            job_analysis
        )
        
        # Identify strengths
        strengths = self._identify_match_strengths(
            matched_skills,
            matched_requirements,
            cv_data,
            job_analysis
        )
        
        # Generate recommendations
        recommendations = self._generate_match_recommendations(
            missing_skills,
            missing_requirements,
            missing_keywords,
            qualification_gaps,
            overall_score
        )
        
        # Generate summary
        summary = self._generate_match_summary(
            overall_score,
            score_breakdown,
            len(matched_skills),
            len(missing_skills),
            len(qualification_gaps),
            job_analysis
        )
        
        return JobMatchResult(
            cv_id=request.cv_id,
            job_analysis=job_analysis,
            score_breakdown=score_breakdown,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            matched_requirements=matched_requirements,
            missing_requirements=missing_requirements,
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            qualification_gaps=qualification_gaps,
            strengths=strengths,
            recommendations=recommendations,
            summary=summary,
            analyzed_at=datetime.now(),
            model=self.llm_provider.config.model,
            provider=self.llm_provider.get_provider_name()
        )
    
    def _extract_cv_skills(self, cv_data: Dict[str, Any]) -> List[str]:
        """Extract all skills from CV data.
        
        Args:
            cv_data: Complete CV data
            
        Returns:
            List of skills found in CV
        """
        skills = []
        skills_section = cv_data.get("skills", {})
        for category in skills_section.get("categories", []):
            skills.extend(category.get("skills", []))
        return skills
    
    def _calculate_keyword_alignment_score(
        self,
        matched_keywords: List[str],
        missing_keywords: List[str]
    ) -> float:
        """Calculate keyword alignment score.
        
        Args:
            matched_keywords: Keywords that match
            missing_keywords: Keywords that are missing
            
        Returns:
            Score from 0-100
        """
        total_keywords = len(matched_keywords) + len(missing_keywords)
        if total_keywords == 0:
            return 50.0  # Neutral score if no keywords identified
        
        return (len(matched_keywords) / total_keywords) * 100.0
    
    def _calculate_skills_match_score(
        self,
        matched_skills: List[str],
        missing_skills: List[str]
    ) -> float:
        """Calculate skills match score.
        
        Args:
            matched_skills: Skills that match
            missing_skills: Skills that are missing
            
        Returns:
            Score from 0-100
        """
        total_skills = len(matched_skills) + len(missing_skills)
        if total_skills == 0:
            return 50.0  # Neutral score if no skills identified
        
        return (len(matched_skills) / total_skills) * 100.0
    
    def _calculate_requirements_match_score(
        self,
        matched_requirements: List[str],
        missing_requirements: List[str]
    ) -> float:
        """Calculate requirements match score.
        
        Args:
            matched_requirements: Requirements that are met
            missing_requirements: Requirements that are not met
            
        Returns:
            Score from 0-100
        """
        total_requirements = len(matched_requirements) + len(missing_requirements)
        if total_requirements == 0:
            return 50.0  # Neutral score if no requirements identified
        
        return (len(matched_requirements) / total_requirements) * 100.0
    
    def _calculate_experience_relevance_score(
        self,
        cv_experiences: List[Dict[str, Any]],
        job_analysis: JobDescriptionAnalysis
    ) -> float:
        """Calculate experience relevance score.
        
        Args:
            cv_experiences: List of experience entries from CV
            job_analysis: Analyzed job description
            
        Returns:
            Score from 0-100
        """
        if not cv_experiences:
            return 0.0
        
        score = 0.0
        max_score = 100.0
        
        # Check for job title match (40 points)
        job_title_words = set(job_analysis.job_title.lower().split())
        for exp in cv_experiences:
            exp_title_words = set(exp.get("title", "").lower().split())
            if job_title_words & exp_title_words:
                score += 40.0
                break
        
        # Check for industry/field match (30 points)
        if job_analysis.industry:
            industry_lower = job_analysis.industry.lower()
            for exp in cv_experiences:
                exp_description = exp.get("description", "").lower()
                company = exp.get("company", "").lower()
                if industry_lower in exp_description or industry_lower in company:
                    score += 30.0
                    break
        
        # Check for relevant experience level (30 points)
        if job_analysis.experience_level:
            # Count years of experience
            total_years = len(cv_experiences)  # Simplified - each job ~1 year
            
            level_lower = job_analysis.experience_level.lower()
            if "entry" in level_lower and total_years >= 0:
                score += 30.0
            elif "mid" in level_lower and total_years >= 2:
                score += 30.0
            elif "senior" in level_lower and total_years >= 5:
                score += 30.0
            elif "executive" in level_lower and total_years >= 10:
                score += 30.0
            else:
                # Partial credit
                score += 15.0
        
        return min(score, max_score)
    
    async def _match_requirements(
        self,
        cv_data: Dict[str, Any],
        requirements: List[str]
    ) -> tuple[List[str], List[str]]:
        """Match CV against job requirements using LLM analysis.
        
        Args:
            cv_data: Complete CV data
            requirements: List of job requirements
            
        Returns:
            Tuple of (matched_requirements, missing_requirements)
        """
        if not requirements:
            return [], []
        
        # Build CV summary for matching
        cv_summary = self._build_cv_summary_for_matching(cv_data)
        
        # Build prompt for requirement matching
        system_prompt = """You are an expert at matching candidate qualifications to job requirements.
Analyze the CV and determine which requirements are met and which are not met.
Be objective and thorough in your assessment."""
        
        user_prompt = f"""Analyze this CV against the job requirements:

CV SUMMARY:
{cv_summary}

JOB REQUIREMENTS:
{chr(10).join(f"{i+1}. {req}" for i, req in enumerate(requirements))}

For each requirement, determine if it is MET or NOT MET based on the CV.

Respond in this format:
MET:
- [requirement text]
- [requirement text]

NOT MET:
- [requirement text]
- [requirement text]

Be specific and only mark a requirement as MET if there is clear evidence in the CV."""
        
        try:
            response = await self.llm_provider.generate_completion(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=1000
            )
            
            # Parse response
            matched, missing = self._parse_requirements_response(response.content, requirements)
            return matched, missing
            
        except Exception as e:
            # Fallback to simple keyword matching if LLM fails
            matched = []
            missing = []
            cv_text = cv_summary.lower()
            
            for req in requirements:
                req_words = set(req.lower().split())
                # If at least 50% of requirement words are in CV, consider it matched
                matches = sum(1 for word in req_words if word in cv_text)
                if matches >= len(req_words) * 0.5:
                    matched.append(req)
                else:
                    missing.append(req)
            
            return matched, missing
    
    def _build_cv_summary_for_matching(self, cv_data: Dict[str, Any]) -> str:
        """Build a concise CV summary for requirement matching.
        
        Args:
            cv_data: Complete CV data
            
        Returns:
            Formatted CV summary
        """
        summary_parts = []
        
        # Personal info
        personal_info = cv_data.get("personal_info", {})
        name = personal_info.get("name", "Candidate")
        title = personal_info.get("title", "")
        if title:
            summary_parts.append(f"Title: {title}")
        
        # Professional summary
        if cv_data.get("summary"):
            summary_parts.append(f"Summary: {cv_data['summary'][:200]}")
        
        # Skills
        skills = self._extract_cv_skills(cv_data)
        if skills:
            summary_parts.append(f"Skills: {', '.join(skills[:15])}")
        
        # Experience
        experiences = cv_data.get("experience", [])
        if experiences:
            summary_parts.append("Experience:")
            for exp in experiences[:3]:
                exp_text = f"- {exp.get('title', '')} at {exp.get('company', '')}"
                if exp.get('description'):
                    exp_text += f": {exp.get('description', '')[:150]}"
                summary_parts.append(exp_text)
        
        # Education
        education = cv_data.get("education", [])
        if education:
            summary_parts.append("Education:")
            for edu in education[:2]:
                summary_parts.append(f"- {edu.get('degree', '')} from {edu.get('institution', '')}")
        
        return "\n".join(summary_parts)
    
    def _parse_requirements_response(
        self,
        response_text: str,
        original_requirements: List[str]
    ) -> tuple[List[str], List[str]]:
        """Parse LLM response for requirement matching.
        
        Args:
            response_text: Raw LLM response
            original_requirements: Original list of requirements
            
        Returns:
            Tuple of (matched_requirements, missing_requirements)
        """
        matched = []
        missing = []
        
        lines = response_text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.upper().startswith("MET:"):
                current_section = "met"
            elif line.upper().startswith("NOT MET:"):
                current_section = "not_met"
            elif line.startswith("-") or line.startswith("•"):
                item = line.lstrip("-•").strip()
                if item:
                    if current_section == "met":
                        matched.append(item)
                    elif current_section == "not_met":
                        missing.append(item)
        
        # Ensure all requirements are accounted for
        all_categorized = matched + missing
        for req in original_requirements:
            if not any(req.lower() in cat.lower() for cat in all_categorized):
                # If not categorized, add to missing by default
                missing.append(req)
        
        return matched, missing
    
    def _identify_qualification_gaps(
        self,
        missing_skills: List[str],
        missing_requirements: List[str],
        job_analysis: JobDescriptionAnalysis
    ) -> List[str]:
        """Identify significant qualification gaps.
        
        Args:
            missing_skills: Skills missing from CV
            missing_requirements: Requirements not met
            job_analysis: Job analysis
            
        Returns:
            List of qualification gaps
        """
        gaps = []
        
        # Critical missing skills
        if missing_skills:
            critical_skills = missing_skills[:5]  # Top 5 missing skills
            if critical_skills:
                gaps.append(f"Missing key skills: {', '.join(critical_skills)}")
        
        # Critical missing requirements
        if missing_requirements:
            critical_reqs = missing_requirements[:3]  # Top 3 missing requirements
            for req in critical_reqs:
                gaps.append(f"Requirement not met: {req}")
        
        # Experience level gap
        if job_analysis.experience_level:
            level = job_analysis.experience_level.lower()
            if "senior" in level or "executive" in level:
                gaps.append(f"Position requires {job_analysis.experience_level} level experience")
        
        return gaps
    
    def _identify_match_strengths(
        self,
        matched_skills: List[str],
        matched_requirements: List[str],
        cv_data: Dict[str, Any],
        job_analysis: JobDescriptionAnalysis
    ) -> List[str]:
        """Identify candidate strengths for this role.
        
        Args:
            matched_skills: Skills that match
            matched_requirements: Requirements that are met
            cv_data: Complete CV data
            job_analysis: Job analysis
            
        Returns:
            List of strengths
        """
        strengths = []
        
        # Strong skill match
        if len(matched_skills) >= 5:
            strengths.append(f"Strong skill alignment with {len(matched_skills)} matching skills")
        elif len(matched_skills) >= 3:
            strengths.append(f"Good skill match with {len(matched_skills)} relevant skills")
        
        # Requirements met
        if len(matched_requirements) >= 3:
            strengths.append(f"Meets {len(matched_requirements)} key job requirements")
        
        # Relevant experience
        experiences = cv_data.get("experience", [])
        if experiences:
            job_title_words = set(job_analysis.job_title.lower().split())
            for exp in experiences:
                exp_title_words = set(exp.get("title", "").lower().split())
                if job_title_words & exp_title_words:
                    strengths.append(f"Direct experience as {exp.get('title', '')}")
                    break
        
        # Education match
        if job_analysis.requirements:
            education = cv_data.get("education", [])
            if education:
                for req in job_analysis.requirements:
                    if any(word in req.lower() for word in ["degree", "bachelor", "master", "phd"]):
                        strengths.append("Educational qualifications align with requirements")
                        break
        
        # Certifications
        if cv_data.get("certifications"):
            strengths.append("Additional certifications demonstrate commitment to professional development")
        
        return strengths if strengths else ["Basic qualifications present"]
    
    def _generate_match_recommendations(
        self,
        missing_skills: List[str],
        missing_requirements: List[str],
        missing_keywords: List[str],
        qualification_gaps: List[str],
        overall_score: float
    ) -> List[str]:
        """Generate recommendations to improve match score.
        
        Args:
            missing_skills: Skills missing from CV
            missing_requirements: Requirements not met
            missing_keywords: Keywords missing from CV
            qualification_gaps: Identified gaps
            overall_score: Overall match score
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Skill recommendations
        if missing_skills:
            top_missing = missing_skills[:3]
            recommendations.append(
                f"Highlight or develop these skills: {', '.join(top_missing)}"
            )
        
        # Keyword recommendations
        if missing_keywords:
            top_keywords = missing_keywords[:5]
            recommendations.append(
                f"Incorporate these keywords naturally: {', '.join(top_keywords)}"
            )
        
        # Requirement recommendations
        if missing_requirements:
            recommendations.append(
                f"Address {len(missing_requirements)} unmet requirements in your CV or cover letter"
            )
        
        # Score-based recommendations
        if overall_score < 50:
            recommendations.append(
                "Consider significant CV tailoring or additional skill development for this role"
            )
        elif overall_score < 70:
            recommendations.append(
                "Tailor your CV to emphasize relevant experience and skills"
            )
        else:
            recommendations.append(
                "Minor adjustments to keyword usage and emphasis will strengthen your application"
            )
        
        # Gap-specific recommendations
        if qualification_gaps:
            recommendations.append(
                "Focus on addressing qualification gaps through experience examples or skill development"
            )
        
        return recommendations
    
    def _generate_match_summary(
        self,
        overall_score: float,
        score_breakdown: JobMatchScoreBreakdown,
        matched_skills_count: int,
        missing_skills_count: int,
        gaps_count: int,
        job_analysis: JobDescriptionAnalysis
    ) -> str:
        """Generate summary of match analysis.
        
        Args:
            overall_score: Overall match score
            score_breakdown: Detailed score breakdown
            matched_skills_count: Number of matched skills
            missing_skills_count: Number of missing skills
            gaps_count: Number of qualification gaps
            job_analysis: Job analysis
            
        Returns:
            Summary text
        """
        # Determine match quality
        if overall_score >= 80:
            quality = "excellent"
            outlook = "You are a strong candidate for this position."
        elif overall_score >= 65:
            quality = "good"
            outlook = "You are a competitive candidate with some areas for improvement."
        elif overall_score >= 50:
            quality = "moderate"
            outlook = "You meet some requirements but significant tailoring is recommended."
        else:
            quality = "low"
            outlook = "This role may require additional skills or experience."
        
        summary = f"Your CV shows a {quality} match ({overall_score:.1f}/100) for the {job_analysis.job_title} position. "
        
        # Add score breakdown highlights
        if score_breakdown.skills_match_score >= 70:
            summary += f"Your skills align well ({score_breakdown.skills_match_score:.0f}%). "
        elif score_breakdown.skills_match_score < 50:
            summary += f"Skills alignment needs improvement ({score_breakdown.skills_match_score:.0f}%). "
        
        if score_breakdown.experience_relevance_score >= 70:
            summary += f"Your experience is highly relevant ({score_breakdown.experience_relevance_score:.0f}%). "
        elif score_breakdown.experience_relevance_score < 50:
            summary += f"Experience relevance could be stronger ({score_breakdown.experience_relevance_score:.0f}%). "
        
        # Add specific counts
        summary += f"You match {matched_skills_count} of the required skills"
        if missing_skills_count > 0:
            summary += f" and are missing {missing_skills_count} skills"
        summary += ". "
        
        # Add gaps if significant
        if gaps_count > 0:
            summary += f"There are {gaps_count} qualification gaps to address. "
        
        # Add outlook
        summary += outlook
        
        return summary
    
    async def tailor_to_job(
        self,
        request: JobTailoringRequest
    ) -> JobTailoringResult:
        """Alias for tailor_cv_to_job for backward compatibility.
        
        Args:
            request: Job tailoring request
            
        Returns:
            JobTailoringResult with tailoring suggestions
        """
        return await self.tailor_cv_to_job(request)


class CVOptimizerFactory:
    """Factory for creating CVOptimizer instances."""
    
    @staticmethod
    def create_optimizer(llm_provider: BaseLLMProvider) -> CVOptimizer:
        """Create a CVOptimizer with the specified provider.
        
        Args:
            llm_provider: LLM provider instance
            
        Returns:
            CVOptimizer instance
        """
        return CVOptimizer(llm_provider)
