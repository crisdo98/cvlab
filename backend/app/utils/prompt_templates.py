"""
Prompt Templates for LLM Content Generation

This module provides prompt templates for various CV content generation tasks.
Templates are designed to produce professional, concise, and achievement-focused content.
"""

from typing import Dict, List, Optional, Any
from enum import Enum


class SectionType(str, Enum):
    """CV section types for content generation."""
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    ACHIEVEMENT = "achievement"
    EDUCATION = "education"
    SKILLS = "skills"
    CERTIFICATION = "certification"


class PromptTemplates:
    """Collection of prompt templates for CV content generation."""
    
    # System prompts for different content generation tasks
    SYSTEM_PROMPTS = {
        "content_generation": """You are a professional CV writing assistant. Your role is to help create compelling, 
professional CV content that is:
- Achievement-focused with quantifiable results
- Concise and impactful
- Written in active voice
- Free of clichés and buzzwords
- Tailored to professional standards
- Honest and accurate

Always maintain a professional tone and focus on demonstrating value and impact.""",
        
        "note_expansion": """You are a professional CV writing assistant specializing in expanding brief notes 
into well-written professional descriptions. Your expansions should:
- Preserve the core meaning and facts from the original notes
- Add professional context and clarity
- Use active voice and strong action verbs
- Be concise yet comprehensive
- Maintain accuracy without embellishment""",
        
        "achievement_generation": """You are a professional CV writing assistant specializing in creating 
achievement statements. Your statements should:
- Start with strong action verbs
- Include specific, quantifiable metrics
- Demonstrate clear impact and results
- Be concise (under 20 words when possible)
- Follow the format: Action Verb + Task + Result/Impact""",
        
        "job_tailoring": """You are an expert CV tailoring consultant. Your role is to suggest specific 
modifications to align a CV with a job description while maintaining truthfulness.

Key principles:
- NEVER suggest adding false information or skills the candidate doesn't have
- Focus on emphasizing relevant existing experience
- Suggest natural incorporation of missing keywords where appropriate
- Recommend reordering or rephrasing to highlight relevant qualifications
- Maintain professional tone and accuracy

Your suggestions should be specific, actionable, and honest.""",
    }
    
    # User prompts for specific content generation tasks
    USER_PROMPTS = {
        "summary": """Generate a professional CV summary for a {job_title} with {years_experience} years of experience.

Key skills: {skills}
Industry: {industry}
Career level: {career_level}

Requirements:
- Length: 3-4 sentences
- Tone: Professional, confident, achievement-focused
- Focus on: Value proposition, key strengths, career goals
- Include relevant keywords naturally

Generate {num_variations} distinct variations.""",
        
        "experience_description": """Create a professional description for this work experience:

Job Title: {job_title}
Company: {company}
Duration: {duration}
Key Responsibilities: {responsibilities}
Technologies/Skills Used: {skills}

Requirements:
- Length: 2-3 sentences
- Focus on responsibilities and scope
- Use active voice
- Highlight technical skills and methodologies
- Be specific about role and impact

Generate {num_variations} distinct variations.""",
        
        "achievement_from_description": """Transform this work description into quantifiable achievement statements:

Description: {description}
Context: {context}

Guidelines:
- Create {num_variations} distinct achievement statements
- Start each with a strong action verb
- Include specific metrics, numbers, or percentages where possible
- Show clear impact and results
- Keep each statement under 20 words
- Format: [Action Verb] + [What you did] + [Measurable result/impact]

Examples of good achievement statements:
- "Reduced API response time by 40% through database query optimization"
- "Led team of 5 developers to deliver project 2 weeks ahead of schedule"
- "Increased user engagement by 25% by implementing new feature set"

Generate the achievement statements now.""",
        
        "achievement_from_notes": """Create professional achievement statements from these brief notes:

Notes: {notes}
Job Title: {job_title}
Company: {company}

Guidelines:
- Create {num_variations} distinct achievement statements
- Start with strong action verbs
- Add quantifiable metrics where appropriate
- Show impact and results
- Keep under 20 words each
- Maintain accuracy - don't invent facts not in the notes

Generate the achievement statements now.""",
        
        "expand_notes": """Expand these brief notes into a well-written professional description:

Notes: {notes}
Context:
- Job Title: {job_title}
- Company: {company}
- Section: {section_type}

Requirements:
- Preserve all facts from the original notes
- Add professional context and clarity
- Use active voice and strong verbs
- Length: {target_length}
- Maintain accuracy without embellishment
- Generate {num_variations} distinct variations

Expand the notes now.""",
        
        "education_description": """Create a professional description for this education entry:

Degree: {degree}
Institution: {institution}
Field of Study: {field_of_study}
Notable Achievements: {achievements}
Relevant Coursework: {coursework}

Requirements:
- Length: 1-2 sentences
- Highlight relevant achievements or coursework
- Focus on skills and knowledge gained
- Be concise and professional
- Generate {num_variations} distinct variations

Generate the descriptions now.""",
        
        "skills_summary": """Create a professional skills summary based on these skills:

Technical Skills: {technical_skills}
Soft Skills: {soft_skills}
Years of Experience: {years_experience}
Industry: {industry}

Requirements:
- Length: 2-3 sentences
- Highlight depth and breadth of expertise
- Connect skills to value delivery
- Use professional language
- Generate {num_variations} distinct variations

Generate the summaries now.""",
    }
    
    @classmethod
    def get_system_prompt(cls, task_type: str) -> str:
        """Get system prompt for a specific task type.
        
        Args:
            task_type: Type of content generation task
            
        Returns:
            System prompt string
            
        Raises:
            ValueError: If task_type is not found
        """
        if task_type not in cls.SYSTEM_PROMPTS:
            raise ValueError(f"Unknown task type: {task_type}")
        return cls.SYSTEM_PROMPTS[task_type]
    
    @classmethod
    def get_user_prompt(cls, section_type: SectionType, context: Dict[str, Any]) -> str:
        """Get user prompt for a specific section type with context injection.
        
        Args:
            section_type: Type of CV section
            context: Dictionary containing context variables for template
            
        Returns:
            Formatted user prompt string
            
        Raises:
            ValueError: If section_type is not found or required context is missing
        """
        section_key = section_type.value
        
        if section_key not in cls.USER_PROMPTS:
            raise ValueError(f"Unknown section type: {section_type}")
        
        template = cls.USER_PROMPTS[section_key]
        
        try:
            # Inject context into template
            return template.format(**context)
        except KeyError as e:
            raise ValueError(f"Missing required context variable: {e}")
    
    @classmethod
    def build_summary_prompt(
        cls,
        job_title: str,
        years_experience: int,
        skills: List[str],
        industry: Optional[str] = None,
        career_level: Optional[str] = None,
        num_variations: int = 3
    ) -> tuple[str, str]:
        """Build prompts for generating professional summary.
        
        Args:
            job_title: Current or target job title
            years_experience: Years of professional experience
            skills: List of key skills
            industry: Industry or field
            career_level: Career level (entry, mid, senior, executive)
            num_variations: Number of variations to generate
            
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        context = {
            "job_title": job_title,
            "years_experience": years_experience,
            "skills": ", ".join(skills[:5]),  # Limit to top 5 skills
            "industry": industry or "technology",
            "career_level": career_level or "professional",
            "num_variations": num_variations
        }
        
        system_prompt = cls.get_system_prompt("content_generation")
        user_prompt = cls.get_user_prompt(SectionType.SUMMARY, context)
        
        return system_prompt, user_prompt
    
    @classmethod
    def build_experience_prompt(
        cls,
        job_title: str,
        company: str,
        duration: str,
        responsibilities: str,
        skills: List[str],
        num_variations: int = 3
    ) -> tuple[str, str]:
        """Build prompts for generating experience description.
        
        Args:
            job_title: Job title
            company: Company name
            duration: Duration of employment
            responsibilities: Brief description of responsibilities
            skills: List of relevant skills/technologies
            num_variations: Number of variations to generate
            
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        context = {
            "job_title": job_title,
            "company": company,
            "duration": duration,
            "responsibilities": responsibilities,
            "skills": ", ".join(skills),
            "num_variations": num_variations
        }
        
        system_prompt = cls.get_system_prompt("content_generation")
        user_prompt = cls.USER_PROMPTS["experience_description"].format(**context)
        
        return system_prompt, user_prompt
    
    @classmethod
    def build_achievement_prompt(
        cls,
        description: Optional[str] = None,
        notes: Optional[str] = None,
        job_title: Optional[str] = None,
        company: Optional[str] = None,
        context_info: Optional[str] = None,
        num_variations: int = 3
    ) -> tuple[str, str]:
        """Build prompts for generating achievement statements.
        
        Args:
            description: Full work description to extract achievements from
            notes: Brief notes to expand into achievements
            job_title: Job title for context
            company: Company name for context
            context_info: Additional context information
            num_variations: Number of variations to generate
            
        Returns:
            Tuple of (system_prompt, user_prompt)
            
        Raises:
            ValueError: If neither description nor notes is provided
        """
        if description:
            # Generate achievements from full description
            context = {
                "description": description,
                "context": context_info or "Professional work experience",
                "num_variations": num_variations
            }
            user_prompt = cls.USER_PROMPTS["achievement_from_description"].format(**context)
        elif notes:
            # Generate achievements from brief notes
            context = {
                "notes": notes,
                "job_title": job_title or "Professional",
                "company": company or "Company",
                "num_variations": num_variations
            }
            user_prompt = cls.USER_PROMPTS["achievement_from_notes"].format(**context)
        else:
            raise ValueError("Either description or notes must be provided")
        
        system_prompt = cls.get_system_prompt("achievement_generation")
        
        return system_prompt, user_prompt
    
    @classmethod
    def build_expand_notes_prompt(
        cls,
        notes: str,
        job_title: str,
        company: str,
        section_type: str = "experience",
        target_length: str = "2-3 sentences",
        num_variations: int = 3
    ) -> tuple[str, str]:
        """Build prompts for expanding brief notes into full descriptions.
        
        Args:
            notes: Brief notes to expand
            job_title: Job title for context
            company: Company name for context
            section_type: Type of section (experience, education, etc.)
            target_length: Desired length of expanded text
            num_variations: Number of variations to generate
            
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        context = {
            "notes": notes,
            "job_title": job_title,
            "company": company,
            "section_type": section_type,
            "target_length": target_length,
            "num_variations": num_variations
        }
        
        system_prompt = cls.get_system_prompt("note_expansion")
        user_prompt = cls.USER_PROMPTS["expand_notes"].format(**context)
        
        return system_prompt, user_prompt
    
    @classmethod
    def build_education_prompt(
        cls,
        degree: str,
        institution: str,
        field_of_study: Optional[str] = None,
        achievements: Optional[str] = None,
        coursework: Optional[str] = None,
        num_variations: int = 3
    ) -> tuple[str, str]:
        """Build prompts for generating education description.
        
        Args:
            degree: Degree name
            institution: Institution name
            field_of_study: Field or major
            achievements: Notable achievements during education
            coursework: Relevant coursework
            num_variations: Number of variations to generate
            
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        context = {
            "degree": degree,
            "institution": institution,
            "field_of_study": field_of_study or "Not specified",
            "achievements": achievements or "None specified",
            "coursework": coursework or "None specified",
            "num_variations": num_variations
        }
        
        system_prompt = cls.get_system_prompt("content_generation")
        user_prompt = cls.get_user_prompt(SectionType.EDUCATION, context)
        
        return system_prompt, user_prompt
    
    @classmethod
    def build_skills_summary_prompt(
        cls,
        technical_skills: List[str],
        soft_skills: List[str],
        years_experience: int,
        industry: Optional[str] = None,
        num_variations: int = 3
    ) -> tuple[str, str]:
        """Build prompts for generating skills summary.
        
        Args:
            technical_skills: List of technical skills
            soft_skills: List of soft skills
            years_experience: Years of experience
            industry: Industry or field
            num_variations: Number of variations to generate
            
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        context = {
            "technical_skills": ", ".join(technical_skills),
            "soft_skills": ", ".join(soft_skills),
            "years_experience": years_experience,
            "industry": industry or "technology",
            "num_variations": num_variations
        }
        
        system_prompt = cls.get_system_prompt("content_generation")
        user_prompt = cls.USER_PROMPTS["skills_summary"].format(**context)
        
        return system_prompt, user_prompt


class ContextBuilder:
    """Helper class for building context from CV data models."""
    
    @staticmethod
    def extract_skills_from_cv(cv_data: Dict[str, Any]) -> List[str]:
        """Extract all skills from CV data.
        
        Args:
            cv_data: CV data dictionary
            
        Returns:
            List of skill strings
        """
        skills = []
        skills_section = cv_data.get("skills", {})
        categories = skills_section.get("categories", [])
        
        for category in categories:
            skills.extend(category.get("skills", []))
        
        return skills
    
    @staticmethod
    def calculate_years_experience(experiences: List[Dict[str, Any]]) -> int:
        """Calculate total years of experience from experience entries.
        
        Args:
            experiences: List of experience dictionaries
            
        Returns:
            Total years of experience (rounded)
        """
        from datetime import datetime
        
        total_months = 0
        
        for exp in experiences:
            try:
                # Parse start date (format: YYYY-MM or YYYY-MM-DD)
                start_str = exp.get("start_date", "")
                if not start_str:
                    continue
                
                # Handle YYYY-MM format
                if len(start_str) == 7:  # YYYY-MM
                    start_date = datetime.strptime(start_str, "%Y-%m")
                else:  # YYYY-MM-DD
                    start_date = datetime.strptime(start_str, "%Y-%m-%d")
                
                if exp.get("current"):
                    end_date = datetime.now()
                elif exp.get("end_date"):
                    end_str = exp.get("end_date")
                    if len(end_str) == 7:  # YYYY-MM
                        end_date = datetime.strptime(end_str, "%Y-%m")
                    else:  # YYYY-MM-DD
                        end_date = datetime.strptime(end_str, "%Y-%m-%d")
                else:
                    continue
                
                # Calculate months
                months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
                total_months += max(0, months)
            except (ValueError, AttributeError):
                # Skip entries with invalid dates
                continue
        
        # Convert to years, rounding up
        years = (total_months + 11) // 12
        return max(1, years)  # Minimum 1 year
    
    @staticmethod
    def infer_career_level(years_experience: int) -> str:
        """Infer career level from years of experience.
        
        Args:
            years_experience: Years of professional experience
            
        Returns:
            Career level string
        """
        if years_experience < 2:
            return "entry-level"
        elif years_experience < 5:
            return "mid-level"
        elif years_experience < 10:
            return "senior"
        else:
            return "executive"
    
    @staticmethod
    def build_context_from_cv(cv_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build comprehensive context from CV data for prompt generation.
        
        Args:
            cv_data: Complete CV data dictionary
            
        Returns:
            Context dictionary with extracted information
        """
        skills = ContextBuilder.extract_skills_from_cv(cv_data)
        experiences = cv_data.get("experience", [])
        years_exp = ContextBuilder.calculate_years_experience(experiences)
        career_level = ContextBuilder.infer_career_level(years_exp)
        
        # Get current or most recent job title
        job_title = "Professional"
        if experiences:
            # Sort by current first, then by start date
            sorted_exp = sorted(
                experiences,
                key=lambda x: (not x.get("current", False), x.get("start_date", "")),
                reverse=True
            )
            if sorted_exp:
                job_title = sorted_exp[0].get("title", "Professional")
        
        return {
            "job_title": job_title,
            "years_experience": years_exp,
            "career_level": career_level,
            "skills": skills,
            "technical_skills": skills[:10],  # Top 10 technical skills
            "experiences": experiences,
            "education": cv_data.get("education", []),
        }
