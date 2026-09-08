"""
Content Generator for CV Sections

This module provides AI-powered content generation for various CV sections
including summaries, experience descriptions, achievement statements, and more.
"""

from typing import List, Dict, Any, Optional
import re
from pydantic import BaseModel, Field

from app.llm.providers.base import BaseLLMProvider, LLMResponse
from app.utils.prompt_templates import PromptTemplates, ContextBuilder, SectionType


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


class ContentGenerator:
    """AI-powered content generator for CV sections.
    
    This class provides methods for generating various types of CV content
    using LLM providers. It handles prompt construction, LLM interaction,
    and response parsing.
    """
    
    def __init__(self, llm_provider: BaseLLMProvider):
        """Initialize content generator with LLM provider.
        
        Args:
            llm_provider: LLM provider instance to use for generation
        """
        self.llm_provider = llm_provider
        self.prompt_templates = PromptTemplates()
    
    async def generate_summary(
        self,
        request: SummaryGenerationRequest
    ) -> ContentGenerationResult:
        """Generate professional summary variations.
        
        Args:
            request: Summary generation request with context
            
        Returns:
            ContentGenerationResult with generated summary variations
            
        Raises:
            ValueError: If request is invalid
            RuntimeError: If generation fails
        """
        # Build prompts
        system_prompt, user_prompt = PromptTemplates.build_summary_prompt(
            job_title=request.job_title,
            years_experience=request.years_experience,
            skills=request.skills,
            industry=request.industry,
            career_level=request.career_level,
            num_variations=request.num_variations
        )
        
        # Generate content
        response = await self.llm_provider.generate_completion(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=500
        )
        
        # Parse variations from response
        variations = self._parse_variations(response.content, request.num_variations)
        
        return ContentGenerationResult(
            variations=variations,
            section_type="summary",
            context_used={
                "job_title": request.job_title,
                "years_experience": request.years_experience,
                "skills": request.skills[:5]
            },
            model=response.model,
            provider=response.provider
        )
    
    async def expand_notes(
        self,
        request: NoteExpansionRequest
    ) -> ContentGenerationResult:
        """Expand brief notes into full professional descriptions.
        
        Args:
            request: Note expansion request with context
            
        Returns:
            ContentGenerationResult with expanded descriptions
            
        Raises:
            ValueError: If request is invalid
            RuntimeError: If generation fails
        """
        # Build prompts
        system_prompt, user_prompt = PromptTemplates.build_expand_notes_prompt(
            notes=request.notes,
            job_title=request.job_title,
            company=request.company,
            section_type=request.section_type,
            target_length=request.target_length,
            num_variations=request.num_variations
        )
        
        # Generate content
        response = await self.llm_provider.generate_completion(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=400
        )
        
        # Parse variations
        variations = self._parse_variations(response.content, request.num_variations)
        
        return ContentGenerationResult(
            variations=variations,
            section_type="note_expansion",
            context_used={
                "notes": request.notes,
                "job_title": request.job_title,
                "company": request.company
            },
            model=response.model,
            provider=response.provider
        )
    
    async def generate_achievements(
        self,
        request: AchievementGenerationRequest
    ) -> ContentGenerationResult:
        """Generate achievement statements from descriptions or notes.
        
        Args:
            request: Achievement generation request
            
        Returns:
            ContentGenerationResult with achievement statements
            
        Raises:
            ValueError: If request is invalid (neither description nor notes provided)
            RuntimeError: If generation fails
        """
        # Build prompts
        system_prompt, user_prompt = PromptTemplates.build_achievement_prompt(
            description=request.description,
            notes=request.notes,
            job_title=request.job_title,
            company=request.company,
            context_info=request.context_info,
            num_variations=request.num_variations
        )
        
        # Generate content
        response = await self.llm_provider.generate_completion(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=400
        )
        
        # Parse variations
        variations = self._parse_variations(response.content, request.num_variations)
        
        return ContentGenerationResult(
            variations=variations,
            section_type="achievement",
            context_used={
                "description": request.description,
                "notes": request.notes,
                "job_title": request.job_title
            },
            model=response.model,
            provider=response.provider
        )
    
    async def generate_experience_description(
        self,
        job_title: str,
        company: str,
        duration: str,
        responsibilities: str,
        skills: List[str],
        num_variations: int = 3
    ) -> ContentGenerationResult:
        """Generate experience description variations.
        
        Args:
            job_title: Job title
            company: Company name
            duration: Duration of employment
            responsibilities: Brief description of responsibilities
            skills: List of relevant skills/technologies
            num_variations: Number of variations to generate
            
        Returns:
            ContentGenerationResult with experience descriptions
            
        Raises:
            RuntimeError: If generation fails
        """
        # Build prompts
        system_prompt, user_prompt = PromptTemplates.build_experience_prompt(
            job_title=job_title,
            company=company,
            duration=duration,
            responsibilities=responsibilities,
            skills=skills,
            num_variations=num_variations
        )
        
        # Generate content
        response = await self.llm_provider.generate_completion(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=400
        )
        
        # Parse variations
        variations = self._parse_variations(response.content, num_variations)
        
        return ContentGenerationResult(
            variations=variations,
            section_type="experience",
            context_used={
                "job_title": job_title,
                "company": company,
                "duration": duration
            },
            model=response.model,
            provider=response.provider
        )
    
    async def generate_education_description(
        self,
        degree: str,
        institution: str,
        field_of_study: Optional[str] = None,
        achievements: Optional[str] = None,
        coursework: Optional[str] = None,
        num_variations: int = 3
    ) -> ContentGenerationResult:
        """Generate education description variations.
        
        Args:
            degree: Degree name
            institution: Institution name
            field_of_study: Field or major
            achievements: Notable achievements
            coursework: Relevant coursework
            num_variations: Number of variations to generate
            
        Returns:
            ContentGenerationResult with education descriptions
            
        Raises:
            RuntimeError: If generation fails
        """
        # Build prompts
        system_prompt, user_prompt = PromptTemplates.build_education_prompt(
            degree=degree,
            institution=institution,
            field_of_study=field_of_study,
            achievements=achievements,
            coursework=coursework,
            num_variations=num_variations
        )
        
        # Generate content
        response = await self.llm_provider.generate_completion(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=300
        )
        
        # Parse variations
        variations = self._parse_variations(response.content, num_variations)
        
        return ContentGenerationResult(
            variations=variations,
            section_type="education",
            context_used={
                "degree": degree,
                "institution": institution
            },
            model=response.model,
            provider=response.provider
        )
    
    async def generate_skills_summary(
        self,
        technical_skills: List[str],
        soft_skills: List[str],
        years_experience: int,
        industry: Optional[str] = None,
        num_variations: int = 3
    ) -> ContentGenerationResult:
        """Generate skills summary variations.
        
        Args:
            technical_skills: List of technical skills
            soft_skills: List of soft skills
            years_experience: Years of experience
            industry: Industry or field
            num_variations: Number of variations to generate
            
        Returns:
            ContentGenerationResult with skills summaries
            
        Raises:
            RuntimeError: If generation fails
        """
        # Build prompts
        system_prompt, user_prompt = PromptTemplates.build_skills_summary_prompt(
            technical_skills=technical_skills,
            soft_skills=soft_skills,
            years_experience=years_experience,
            industry=industry,
            num_variations=num_variations
        )
        
        # Generate content
        response = await self.llm_provider.generate_completion(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=300
        )
        
        # Parse variations
        variations = self._parse_variations(response.content, num_variations)
        
        return ContentGenerationResult(
            variations=variations,
            section_type="skills_summary",
            context_used={
                "technical_skills": technical_skills[:5],
                "years_experience": years_experience
            },
            model=response.model,
            provider=response.provider
        )
    
    async def generate_content_from_cv(
        self,
        cv_data: Dict[str, Any],
        section_type: str,
        num_variations: int = 3
    ) -> ContentGenerationResult:
        """Generate content for a CV section using full CV context.
        
        This is a convenience method that extracts context from CV data
        and generates appropriate content based on section type.
        
        Args:
            cv_data: Complete CV data dictionary
            section_type: Type of section to generate (summary, experience, etc.)
            num_variations: Number of variations to generate
            
        Returns:
            ContentGenerationResult with generated content
            
        Raises:
            ValueError: If section_type is not supported
            RuntimeError: If generation fails
        """
        # Build context from CV data
        context = ContextBuilder.build_context_from_cv(cv_data)
        
        if section_type == "summary":
            request = SummaryGenerationRequest(
                job_title=context["job_title"],
                years_experience=context["years_experience"],
                skills=context["skills"],
                career_level=context["career_level"],
                num_variations=num_variations
            )
            return await self.generate_summary(request)
        
        elif section_type == "skills_summary":
            return await self.generate_skills_summary(
                technical_skills=context["technical_skills"],
                soft_skills=[],  # Could be extracted if available
                years_experience=context["years_experience"],
                num_variations=num_variations
            )
        
        else:
            raise ValueError(f"Unsupported section type for CV-based generation: {section_type}")
    
    def _parse_variations(self, content: str, expected_count: int) -> List[ContentVariation]:
        """Parse content variations from LLM response.
        
        The LLM may return variations in different formats:
        - Numbered list (1. ..., 2. ..., etc.)
        - Labeled variations (Variation 1:, Option 2:, Alternative version 3:, etc.)
        - Separated by blank lines
        - Separated by "---" or similar delimiters
        - Mixed format with some numbered and some not
        - As a single block (if only one variation requested)
        
        Args:
            content: Raw content from LLM response
            expected_count: Expected number of variations
            
        Returns:
            List of ContentVariation objects
        """
        # Clean up the content
        content = content.strip()
        
        # Pattern for numbered variations (1. or 1) at start of line or after whitespace)
        numbered_pattern = r'(?:^|\n)\s*(\d+)[\.\)]\s+'
        
        # Pattern for labeled variations (Variation 1:, Option 2:, Alternative version 3:, etc.)
        # More flexible to handle "Alternative version 2:" or "Variation 1:" etc.
        labeled_pattern = r'(?:^|\n)\s*(?:Variation|Option|Alternative|Version)(?:\s+version)?\s+(\d+)\s*:\s*'
        
        # Try to find all numbered variations in the content
        numbered_matches = list(re.finditer(numbered_pattern, content, re.MULTILINE))
        labeled_matches = list(re.finditer(labeled_pattern, content, re.MULTILINE | re.IGNORECASE))
        
        # Combine and sort all matches by position
        all_matches = []
        for match in numbered_matches:
            all_matches.append(('numbered', match))
        for match in labeled_matches:
            all_matches.append(('labeled', match))
        
        # Sort by position in content
        all_matches.sort(key=lambda x: x[1].start())
        
        variations = []
        
        if all_matches:
            # Parse based on variation markers
            for i, (match_type, match) in enumerate(all_matches):
                start_pos = match.end()
                
                # Find the end position (start of next variation or end of content)
                if i + 1 < len(all_matches):
                    end_pos = all_matches[i + 1][1].start()
                else:
                    end_pos = len(content)
                
                # Extract the text for this variation
                text = content[start_pos:end_pos].strip()
                
                # Clean up any trailing whitespace or newlines
                text = ' '.join(text.split())
                
                if text:
                    variations.append(ContentVariation(
                        text=text,
                        variation_number=len(variations) + 1
                    ))
        
        # If no numbered/labeled variations found, try splitting by paragraphs
        if not variations:
            # Split by double newlines (paragraphs)
            paragraphs = re.split(r'\n\s*\n', content)
            paragraphs = [p.strip() for p in paragraphs if p.strip()]
            
            # Clean up each paragraph
            for p in paragraphs[:expected_count]:
                # Remove any leading numbers or labels if present
                cleaned = re.sub(r'^\d+[\.\)]\s+', '', p)
                cleaned = re.sub(r'^(?:Variation|Option|Alternative|Version)(?:\s+version)?\s+\d+\s*:\s*', '', cleaned, flags=re.IGNORECASE)
                cleaned = ' '.join(cleaned.split())
                if cleaned:
                    variations.append(ContentVariation(
                        text=cleaned,
                        variation_number=len(variations) + 1
                    ))
        
        # If still no variations, treat entire content as single variation
        if not variations:
            # Clean up the content
            cleaned = ' '.join(content.split())
            if cleaned:
                variations = [ContentVariation(text=cleaned, variation_number=1)]
        
        # Ensure we have at least one variation
        if not variations:
            variations = [ContentVariation(
                text="Unable to generate content. Please try again.",
                variation_number=1
            )]
        
        # Limit to expected count and ensure sequential numbering
        variations = variations[:expected_count]
        
        # Re-number variations to ensure they're sequential
        for i, variation in enumerate(variations):
            variation.variation_number = i + 1
        
        return variations
    
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


class ContentGeneratorFactory:
    """Factory for creating ContentGenerator instances with different providers."""
    
    @staticmethod
    def create_generator(llm_provider: BaseLLMProvider) -> ContentGenerator:
        """Create a ContentGenerator with the specified provider.
        
        Args:
            llm_provider: LLM provider instance
            
        Returns:
            ContentGenerator instance
        """
        return ContentGenerator(llm_provider)
    
    @staticmethod
    async def create_and_test_generator(
        llm_provider: BaseLLMProvider
    ) -> ContentGenerator:
        """Create a ContentGenerator and test the connection.
        
        Args:
            llm_provider: LLM provider instance
            
        Returns:
            ContentGenerator instance
            
        Raises:
            RuntimeError: If connection test fails
        """
        # Test connection first
        await llm_provider.test_connection()
        
        # Create and return generator
        return ContentGenerator(llm_provider)
