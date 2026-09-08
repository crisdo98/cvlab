"""
Grammar and Style Checker for CV Content

This module provides AI-powered grammar checking, style consistency analysis,
and writing quality improvements for CV content.
"""

from typing import List, Dict, Any, Optional
import re
from pydantic import BaseModel, Field

from app.llm.providers.base import BaseLLMProvider, LLMResponse
from app.models.llm_models import (
    GrammarCheckRequest,
    GrammarCheckResult,
    GrammarIssue,
    GrammarIssueType,
    RecommendationPriority
)


class GrammarChecker:
    """AI-powered grammar and style checker for CV content.
    
    This class provides comprehensive grammar checking, style consistency analysis,
    passive voice detection, sentence complexity analysis, and tense consistency
    verification for CV content.
    """
    
    # System prompt for grammar checking
    GRAMMAR_CHECK_SYSTEM_PROMPT = """You are an expert grammar and style checker specializing in professional CV content.

Your role is to identify and correct:
1. Grammar errors (subject-verb agreement, articles, prepositions, etc.)
2. Spelling errors
3. Punctuation issues
4. Passive voice constructions (suggest active voice alternatives)
5. Tense inconsistencies (CVs should use past tense for previous roles, present for current)
6. Style issues (wordiness, redundancy, unclear phrasing)
7. Sentence complexity (overly complex sentences that reduce clarity)

For each issue found, provide:
- The exact text with the issue
- The type of issue
- A specific correction
- A clear explanation
- Severity level (high/medium/low)

Focus on professional CV writing standards:
- Use active voice
- Be concise and clear
- Maintain consistent tense
- Use strong action verbs
- Avoid redundancy and filler words"""

    def __init__(self, llm_provider: BaseLLMProvider):
        """Initialize grammar checker with LLM provider.
        
        Args:
            llm_provider: LLM provider instance to use for checking
        """
        self.llm_provider = llm_provider
    
    async def check_grammar(
        self,
        request: GrammarCheckRequest
    ) -> GrammarCheckResult:
        """Perform comprehensive grammar and style checking on CV content.
        
        Args:
            request: Grammar check request with CV data
            
        Returns:
            GrammarCheckResult with identified issues and corrections
            
        Raises:
            RuntimeError: If checking fails
        """
        # Extract text content from CV
        cv_text = self._extract_cv_text(request.cv_data)
        
        # Build prompt for grammar checking
        user_prompt = self._build_grammar_check_prompt(
            cv_text,
            request.check_types
        )
        
        # Generate analysis
        response = await self.llm_provider.generate_completion(
            prompt=user_prompt,
            system_prompt=self.GRAMMAR_CHECK_SYSTEM_PROMPT,
            temperature=0.3,  # Lower temperature for more consistent checking
            max_tokens=2000
        )
        
        # Parse issues from response
        issues = self._parse_grammar_issues(response.content, cv_text)
        
        # Determine overall quality
        overall_quality = self._assess_overall_quality(issues)
        
        return GrammarCheckResult(
            cv_id=request.cv_id,
            issues=issues,
            overall_quality=overall_quality,
            model=response.model,
            provider=response.provider
        )
    
    async def check_passive_voice(
        self,
        text: str,
        location: str = "CV"
    ) -> List[GrammarIssue]:
        """Detect passive voice constructions and suggest active alternatives.
        
        Args:
            text: Text to check for passive voice
            location: Location identifier for the text
            
        Returns:
            List of GrammarIssue objects for passive voice instances
            
        Raises:
            RuntimeError: If checking fails
        """
        prompt = f"""Analyze this CV text for passive voice constructions:

{text}

For each passive voice construction found:
1. Identify the exact phrase
2. Suggest an active voice alternative
3. Explain why active voice is better

Format your response as:
ISSUE: [passive voice phrase]
CORRECTION: [active voice alternative]
EXPLANATION: [why this is better]
---

If no passive voice is found, respond with: "NO_ISSUES_FOUND"
"""
        
        response = await self.llm_provider.generate_completion(
            prompt=prompt,
            system_prompt=self.GRAMMAR_CHECK_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=1000
        )
        
        # Parse passive voice issues
        issues = self._parse_passive_voice_issues(
            response.content,
            location
        )
        
        return issues
    
    async def check_tense_consistency(
        self,
        cv_data: Dict[str, Any]
    ) -> List[GrammarIssue]:
        """Verify tense consistency throughout the CV.
        
        CVs should use:
        - Past tense for previous positions
        - Present tense for current positions
        
        Args:
            cv_data: Complete CV data
            
        Returns:
            List of GrammarIssue objects for tense inconsistencies
            
        Raises:
            RuntimeError: If checking fails
        """
        issues = []
        
        # Check experience sections
        experiences = cv_data.get("experience", [])
        for exp in experiences:
            is_current = exp.get("current", False)
            expected_tense = "present" if is_current else "past"
            
            description = exp.get("description", "")
            achievements = exp.get("achievements", [])
            
            # Check description tense
            if description:
                location = f"Experience: {exp.get('title', 'Unknown')} at {exp.get('company', 'Unknown')}"
                tense_issues = await self._check_text_tense(
                    description,
                    expected_tense,
                    location
                )
                issues.extend(tense_issues)
            
            # Check achievements tense
            for i, achievement in enumerate(achievements):
                location = f"Experience: {exp.get('title', 'Unknown')} - Achievement {i+1}"
                tense_issues = await self._check_text_tense(
                    achievement,
                    expected_tense,
                    location
                )
                issues.extend(tense_issues)
        
        return issues
    
    async def check_sentence_complexity(
        self,
        text: str,
        location: str = "CV"
    ) -> List[GrammarIssue]:
        """Analyze sentence complexity and suggest simpler alternatives.
        
        Args:
            text: Text to analyze
            location: Location identifier for the text
            
        Returns:
            List of GrammarIssue objects for overly complex sentences
            
        Raises:
            RuntimeError: If checking fails
        """
        prompt = f"""Analyze this CV text for overly complex sentences that reduce clarity:

{text}

Identify sentences that are:
- Too long (more than 25-30 words)
- Have too many clauses
- Use complex nested structures
- Could be split into simpler sentences
- Use unnecessarily complex vocabulary

For each complex sentence:
1. Identify the exact sentence
2. Suggest a clearer, simpler alternative
3. Explain how the alternative improves clarity

Format your response as:
ISSUE: [complex sentence]
CORRECTION: [simpler alternative]
EXPLANATION: [how this improves clarity]
---

If no overly complex sentences are found, respond with: "NO_ISSUES_FOUND"
"""
        
        response = await self.llm_provider.generate_completion(
            prompt=prompt,
            system_prompt=self.GRAMMAR_CHECK_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=1500
        )
        
        # Parse complexity issues
        issues = self._parse_complexity_issues(
            response.content,
            location
        )
        
        return issues
    
    async def check_style_consistency(
        self,
        cv_data: Dict[str, Any]
    ) -> List[GrammarIssue]:
        """Check for style consistency issues across the CV.
        
        Args:
            cv_data: Complete CV data
            
        Returns:
            List of GrammarIssue objects for style inconsistencies
            
        Raises:
            RuntimeError: If checking fails
        """
        # Extract all text content
        cv_text = self._extract_cv_text(cv_data)
        
        prompt = f"""Analyze this CV for style consistency issues:

{cv_text}

Check for:
1. Inconsistent formatting of dates, locations, or titles
2. Mixing of formal and informal language
3. Inconsistent use of abbreviations
4. Varying levels of detail across similar sections
5. Inconsistent bullet point or list formatting
6. Mixing of first person and third person perspective

For each inconsistency:
1. Identify the specific issue
2. Show examples of the inconsistency
3. Suggest how to make it consistent
4. Explain why consistency matters

Format your response as:
ISSUE: [description of inconsistency]
EXAMPLES: [examples showing the inconsistency]
CORRECTION: [how to make it consistent]
EXPLANATION: [why this matters]
---

If no style inconsistencies are found, respond with: "NO_ISSUES_FOUND"
"""
        
        response = await self.llm_provider.generate_completion(
            prompt=prompt,
            system_prompt=self.GRAMMAR_CHECK_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=1500
        )
        
        # Parse style issues
        issues = self._parse_style_issues(response.content)
        
        return issues
    
    def _extract_cv_text(self, cv_data: Dict[str, Any]) -> str:
        """Extract all text content from CV data for analysis.
        
        Args:
            cv_data: Complete CV data
            
        Returns:
            Concatenated text content from all CV sections
        """
        text_parts = []
        
        # Personal info
        personal_info = cv_data.get("personal_info", {})
        if personal_info.get("name"):
            text_parts.append(f"Name: {personal_info['name']}")
        if personal_info.get("title"):
            text_parts.append(f"Title: {personal_info['title']}")
        
        # Summary
        if cv_data.get("summary"):
            text_parts.append(f"\nSummary:\n{cv_data['summary']}")
        
        # Experience
        experiences = cv_data.get("experience", [])
        for exp in experiences:
            text_parts.append(f"\nExperience: {exp.get('title', '')} at {exp.get('company', '')}")
            if exp.get("description"):
                text_parts.append(exp["description"])
            for achievement in exp.get("achievements", []):
                text_parts.append(f"- {achievement}")
        
        # Education
        education_list = cv_data.get("education", [])
        for edu in education_list:
            text_parts.append(f"\nEducation: {edu.get('degree', '')} from {edu.get('institution', '')}")
            if edu.get("description"):
                text_parts.append(edu["description"])
        
        # Skills
        skills = cv_data.get("skills", {})
        for category in skills.get("categories", []):
            text_parts.append(f"\nSkills - {category.get('name', '')}: {', '.join(category.get('skills', []))}")
        
        # Certifications
        certifications = cv_data.get("certifications", [])
        for cert in certifications:
            text_parts.append(f"\nCertification: {cert.get('name', '')} from {cert.get('issuer', '')}")
        
        return "\n".join(text_parts)
    
    def _build_grammar_check_prompt(
        self,
        cv_text: str,
        check_types: Optional[List[GrammarIssueType]] = None
    ) -> str:
        """Build prompt for comprehensive grammar checking.
        
        Args:
            cv_text: CV text to check
            check_types: Specific types to check (if None, check all)
            
        Returns:
            Formatted prompt string
        """
        if check_types:
            types_str = ", ".join([t.value for t in check_types])
            focus = f"Focus specifically on: {types_str}"
        else:
            focus = "Check for all types of grammar, spelling, style, and clarity issues."
        
        prompt = f"""Analyze this CV content for grammar and style issues:

{cv_text}

{focus}

For each issue found, provide:
1. The exact text with the issue
2. The type of issue (grammar, spelling, punctuation, passive_voice, tense, style, clarity, redundancy)
3. The specific correction
4. A clear explanation of why this is an issue
5. Severity (high, medium, or low)

Format your response as:
LOCATION: [where in the CV this appears]
ISSUE_TYPE: [type of issue]
ISSUE_TEXT: [exact text with the issue]
CORRECTION: [corrected version]
EXPLANATION: [why this is an issue and how the correction improves it]
SEVERITY: [high/medium/low]
---

Repeat this format for each issue found.

If no issues are found, respond with: "NO_ISSUES_FOUND"
"""
        
        return prompt
    
    def _parse_grammar_issues(
        self,
        response_content: str,
        cv_text: str
    ) -> List[GrammarIssue]:
        """Parse grammar issues from LLM response.
        
        Args:
            response_content: Raw response from LLM
            cv_text: Original CV text for context
            
        Returns:
            List of GrammarIssue objects
        """
        if "NO_ISSUES_FOUND" in response_content:
            return []
        
        issues = []
        
        # Split by separator
        issue_blocks = response_content.split("---")
        
        for block in issue_blocks:
            block = block.strip()
            if not block:
                continue
            
            # Extract fields using regex
            location_match = re.search(r'LOCATION:\s*(.+?)(?:\n|$)', block, re.IGNORECASE)
            type_match = re.search(r'ISSUE_TYPE:\s*(.+?)(?:\n|$)', block, re.IGNORECASE)
            text_match = re.search(r'ISSUE_TEXT:\s*(.+?)(?:\n|CORRECTION:)', block, re.IGNORECASE | re.DOTALL)
            correction_match = re.search(r'CORRECTION:\s*(.+?)(?:\n|EXPLANATION:)', block, re.IGNORECASE | re.DOTALL)
            explanation_match = re.search(r'EXPLANATION:\s*(.+?)(?:\n|SEVERITY:)', block, re.IGNORECASE | re.DOTALL)
            severity_match = re.search(r'SEVERITY:\s*(.+?)(?:\n|$)', block, re.IGNORECASE)
            
            if all([location_match, type_match, text_match, correction_match, explanation_match]):
                location = location_match.group(1).strip()
                issue_type_str = type_match.group(1).strip().lower()
                issue_text = text_match.group(1).strip()
                correction = correction_match.group(1).strip()
                explanation = explanation_match.group(1).strip()
                severity_str = severity_match.group(1).strip().lower() if severity_match else "medium"
                
                # Map issue type string to enum
                issue_type = self._map_issue_type(issue_type_str)
                
                # Map severity string to enum
                severity = self._map_severity(severity_str)
                
                issues.append(GrammarIssue(
                    type=issue_type,
                    location=location,
                    issue_text=issue_text,
                    correction=correction,
                    explanation=explanation,
                    severity=severity
                ))
        
        return issues
    
    def _parse_passive_voice_issues(
        self,
        response_content: str,
        location: str
    ) -> List[GrammarIssue]:
        """Parse passive voice issues from LLM response.
        
        Args:
            response_content: Raw response from LLM
            location: Location identifier
            
        Returns:
            List of GrammarIssue objects for passive voice
        """
        if "NO_ISSUES_FOUND" in response_content:
            return []
        
        issues = []
        issue_blocks = response_content.split("---")
        
        for block in issue_blocks:
            block = block.strip()
            if not block:
                continue
            
            issue_match = re.search(r'ISSUE:\s*(.+?)(?:\n|CORRECTION:)', block, re.IGNORECASE | re.DOTALL)
            correction_match = re.search(r'CORRECTION:\s*(.+?)(?:\n|EXPLANATION:)', block, re.IGNORECASE | re.DOTALL)
            explanation_match = re.search(r'EXPLANATION:\s*(.+?)(?:\n|$)', block, re.IGNORECASE | re.DOTALL)
            
            if all([issue_match, correction_match, explanation_match]):
                issues.append(GrammarIssue(
                    type=GrammarIssueType.PASSIVE_VOICE,
                    location=location,
                    issue_text=issue_match.group(1).strip(),
                    correction=correction_match.group(1).strip(),
                    explanation=explanation_match.group(1).strip(),
                    severity=RecommendationPriority.MEDIUM
                ))
        
        return issues
    
    def _parse_complexity_issues(
        self,
        response_content: str,
        location: str
    ) -> List[GrammarIssue]:
        """Parse sentence complexity issues from LLM response.
        
        Args:
            response_content: Raw response from LLM
            location: Location identifier
            
        Returns:
            List of GrammarIssue objects for complexity
        """
        if "NO_ISSUES_FOUND" in response_content:
            return []
        
        issues = []
        issue_blocks = response_content.split("---")
        
        for block in issue_blocks:
            block = block.strip()
            if not block:
                continue
            
            issue_match = re.search(r'ISSUE:\s*(.+?)(?:\n|CORRECTION:)', block, re.IGNORECASE | re.DOTALL)
            correction_match = re.search(r'CORRECTION:\s*(.+?)(?:\n|EXPLANATION:)', block, re.IGNORECASE | re.DOTALL)
            explanation_match = re.search(r'EXPLANATION:\s*(.+?)(?:\n|$)', block, re.IGNORECASE | re.DOTALL)
            
            if all([issue_match, correction_match, explanation_match]):
                issues.append(GrammarIssue(
                    type=GrammarIssueType.CLARITY,
                    location=location,
                    issue_text=issue_match.group(1).strip(),
                    correction=correction_match.group(1).strip(),
                    explanation=explanation_match.group(1).strip(),
                    severity=RecommendationPriority.MEDIUM
                ))
        
        return issues
    
    def _parse_style_issues(
        self,
        response_content: str
    ) -> List[GrammarIssue]:
        """Parse style consistency issues from LLM response.
        
        Args:
            response_content: Raw response from LLM
            
        Returns:
            List of GrammarIssue objects for style issues
        """
        if "NO_ISSUES_FOUND" in response_content:
            return []
        
        issues = []
        issue_blocks = response_content.split("---")
        
        for block in issue_blocks:
            block = block.strip()
            if not block:
                continue
            
            issue_match = re.search(r'ISSUE:\s*(.+?)(?:\n|EXAMPLES:)', block, re.IGNORECASE | re.DOTALL)
            examples_match = re.search(r'EXAMPLES:\s*(.+?)(?:\n|CORRECTION:)', block, re.IGNORECASE | re.DOTALL)
            correction_match = re.search(r'CORRECTION:\s*(.+?)(?:\n|EXPLANATION:)', block, re.IGNORECASE | re.DOTALL)
            explanation_match = re.search(r'EXPLANATION:\s*(.+?)(?:\n|$)', block, re.IGNORECASE | re.DOTALL)
            
            if all([issue_match, correction_match, explanation_match]):
                issue_text = issue_match.group(1).strip()
                if examples_match:
                    issue_text += f"\nExamples: {examples_match.group(1).strip()}"
                
                issues.append(GrammarIssue(
                    type=GrammarIssueType.STYLE,
                    location="Multiple sections",
                    issue_text=issue_text,
                    correction=correction_match.group(1).strip(),
                    explanation=explanation_match.group(1).strip(),
                    severity=RecommendationPriority.MEDIUM
                ))
        
        return issues
    
    async def _check_text_tense(
        self,
        text: str,
        expected_tense: str,
        location: str
    ) -> List[GrammarIssue]:
        """Check if text uses the expected tense.
        
        Args:
            text: Text to check
            expected_tense: Expected tense ("past" or "present")
            location: Location identifier
            
        Returns:
            List of GrammarIssue objects for tense inconsistencies
        """
        prompt = f"""Check if this CV text uses {expected_tense} tense consistently:

{text}

This text should be in {expected_tense} tense. Identify any verbs or phrases that use the wrong tense.

For each tense error:
1. Identify the exact phrase with wrong tense
2. Provide the corrected version in {expected_tense} tense
3. Explain the tense issue

Format your response as:
ISSUE: [phrase with wrong tense]
CORRECTION: [corrected version in {expected_tense} tense]
EXPLANATION: [explanation of the tense issue]
---

If the tense is consistent and correct, respond with: "NO_ISSUES_FOUND"
"""
        
        response = await self.llm_provider.generate_completion(
            prompt=prompt,
            system_prompt=self.GRAMMAR_CHECK_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=800
        )
        
        if "NO_ISSUES_FOUND" in response.content:
            return []
        
        issues = []
        issue_blocks = response.content.split("---")
        
        for block in issue_blocks:
            block = block.strip()
            if not block:
                continue
            
            issue_match = re.search(r'ISSUE:\s*(.+?)(?:\n|CORRECTION:)', block, re.IGNORECASE | re.DOTALL)
            correction_match = re.search(r'CORRECTION:\s*(.+?)(?:\n|EXPLANATION:)', block, re.IGNORECASE | re.DOTALL)
            explanation_match = re.search(r'EXPLANATION:\s*(.+?)(?:\n|$)', block, re.IGNORECASE | re.DOTALL)
            
            if all([issue_match, correction_match, explanation_match]):
                issues.append(GrammarIssue(
                    type=GrammarIssueType.TENSE,
                    location=location,
                    issue_text=issue_match.group(1).strip(),
                    correction=correction_match.group(1).strip(),
                    explanation=explanation_match.group(1).strip(),
                    severity=RecommendationPriority.HIGH
                ))
        
        return issues
    
    def _map_issue_type(self, issue_type_str: str) -> GrammarIssueType:
        """Map issue type string to enum.
        
        Args:
            issue_type_str: Issue type as string
            
        Returns:
            GrammarIssueType enum value
        """
        type_mapping = {
            "grammar": GrammarIssueType.GRAMMAR,
            "spelling": GrammarIssueType.SPELLING,
            "punctuation": GrammarIssueType.PUNCTUATION,
            "passive_voice": GrammarIssueType.PASSIVE_VOICE,
            "passive voice": GrammarIssueType.PASSIVE_VOICE,
            "tense": GrammarIssueType.TENSE,
            "style": GrammarIssueType.STYLE,
            "clarity": GrammarIssueType.CLARITY,
            "redundancy": GrammarIssueType.REDUNDANCY,
        }
        
        return type_mapping.get(issue_type_str, GrammarIssueType.GRAMMAR)
    
    def _map_severity(self, severity_str: str) -> RecommendationPriority:
        """Map severity string to enum.
        
        Args:
            severity_str: Severity as string
            
        Returns:
            RecommendationPriority enum value
        """
        severity_mapping = {
            "high": RecommendationPriority.HIGH,
            "medium": RecommendationPriority.MEDIUM,
            "low": RecommendationPriority.LOW,
        }
        
        return severity_mapping.get(severity_str, RecommendationPriority.MEDIUM)
    
    def _assess_overall_quality(self, issues: List[GrammarIssue]) -> str:
        """Assess overall quality based on issues found.
        
        Args:
            issues: List of grammar issues
            
        Returns:
            Overall quality assessment string
        """
        if not issues:
            return "Excellent - No grammar or style issues found"
        
        high_count = sum(1 for i in issues if i.severity == RecommendationPriority.HIGH)
        medium_count = sum(1 for i in issues if i.severity == RecommendationPriority.MEDIUM)
        low_count = sum(1 for i in issues if i.severity == RecommendationPriority.LOW)
        
        if high_count > 5:
            return f"Needs Improvement - {high_count} critical issues, {medium_count} moderate issues, {low_count} minor issues"
        elif high_count > 0 or medium_count > 10:
            return f"Good with Issues - {high_count} critical issues, {medium_count} moderate issues, {low_count} minor issues"
        elif medium_count > 0 or low_count > 5:
            return f"Very Good - {medium_count} moderate issues, {low_count} minor issues"
        else:
            return f"Excellent - Only {low_count} minor issues"
    
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


class GrammarCheckerFactory:
    """Factory for creating GrammarChecker instances with different providers."""
    
    @staticmethod
    def create_checker(llm_provider: BaseLLMProvider) -> GrammarChecker:
        """Create a GrammarChecker with the specified provider.
        
        Args:
            llm_provider: LLM provider instance
            
        Returns:
            GrammarChecker instance
        """
        return GrammarChecker(llm_provider)
    
    @staticmethod
    async def create_and_test_checker(
        llm_provider: BaseLLMProvider
    ) -> GrammarChecker:
        """Create a GrammarChecker and test the connection.
        
        Args:
            llm_provider: LLM provider instance
            
        Returns:
            GrammarChecker instance
            
        Raises:
            RuntimeError: If connection test fails
        """
        # Test connection first
        await llm_provider.test_connection()
        
        # Create and return checker
        return GrammarChecker(llm_provider)
