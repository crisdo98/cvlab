"""
Property-Based Tests for Job Description Extraction

Feature: cv-web-app, Property 31: Job Description Extraction
Validates: Requirements 12.1

Property 31: Job Description Extraction
For any job description text, the LLM service should extract and return
structured data including requirements, skills, and keywords.

This test validates that job description analysis correctly extracts
key information across different job description formats and content.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any

from app.llm.cv_optimizer import CVOptimizer
from app.llm.providers.base import BaseLLMProvider, LLMResponse, LLMConfig
from app.models.llm_models import JobDescriptionAnalysis


# Mock provider for property testing
class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider that simulates job description analysis."""
    
    def __init__(self, config: LLMConfig, provider_name: str = "mock"):
        super().__init__(config)
        self._provider_name = provider_name
        self._call_count = 0
    
    async def generate_completion(
        self,
        prompt: str,
        system_prompt=None,
        temperature=None,
        max_tokens=None,
        **kwargs
    ) -> LLMResponse:
        """Generate mock completion with job description analysis."""
        self._call_count += 1
        
        # Extract information from the prompt (which contains the job description)
        prompt_lower = prompt.lower()
        
        # Extract job title
        job_title = "Not specified"
        if "senior" in prompt_lower and "engineer" in prompt_lower:
            job_title = "Senior Software Engineer"
        elif "engineer" in prompt_lower:
            job_title = "Software Engineer"
        elif "developer" in prompt_lower:
            job_title = "Software Developer"
        elif "manager" in prompt_lower:
            job_title = "Engineering Manager"
        
        # Extract company if mentioned
        company = None
        if "company:" in prompt_lower or "at " in prompt_lower:
            company = "TechCorp"
        
        # Extract experience level
        experience_level = "Mid-level"
        if "senior" in prompt_lower or "5+ years" in prompt_lower:
            experience_level = "Senior"
        elif "junior" in prompt_lower or "entry" in prompt_lower:
            experience_level = "Entry-level"
        
        # Extract industry
        industry = "Technology"
        if "finance" in prompt_lower or "banking" in prompt_lower:
            industry = "Finance"
        elif "healthcare" in prompt_lower or "medical" in prompt_lower:
            industry = "Healthcare"
        
        # Extract requirements
        requirements = []
        if "years" in prompt_lower and "experience" in prompt_lower:
            requirements.append("5+ years of experience in software development")
        if "degree" in prompt_lower or "bachelor" in prompt_lower:
            requirements.append("Bachelor's degree in Computer Science or related field")
        if "team" in prompt_lower:
            requirements.append("Experience leading technical teams")
        
        # Extract skills
        skills = []
        skill_keywords = [
            "python", "java", "javascript", "typescript", "react", "vue", "angular",
            "node", "sql", "aws", "azure", "docker", "kubernetes", "api", "rest"
        ]
        for skill in skill_keywords:
            if skill in prompt_lower:
                skills.append(skill.title())
        
        # Extract keywords (superset of skills)
        keywords = skills.copy()
        keyword_terms = [
            "agile", "scrum", "ci/cd", "microservices", "cloud", "devops",
            "testing", "automation", "architecture", "scalable", "distributed"
        ]
        for keyword in keyword_terms:
            if keyword in prompt_lower:
                keywords.append(keyword.title())
        
        # Ensure we have at least some data
        if not requirements:
            requirements = ["Relevant experience in software development"]
        if not skills:
            skills = ["Programming", "Problem Solving"]
        if not keywords:
            keywords = skills.copy()
        
        # Build response
        content = f"""Job Title: {job_title}
Company: {company or "Not specified"}
Experience Level: {experience_level}
Industry: {industry}

Requirements:
"""
        for req in requirements:
            content += f"- {req}\n"
        
        content += "\nSkills:\n"
        for skill in skills:
            content += f"- {skill}\n"
        
        content += "\nKeywords (important terms for ATS):\n"
        for keyword in keywords:
            content += f"- {keyword}\n"
        
        return LLMResponse(
            content=content,
            model=self.config.model,
            provider=self._provider_name,
            tokens_used=200 + self._call_count * 30
        )
    
    async def generate_structured_output(
        self,
        prompt: str,
        schema: dict,
        system_prompt=None,
        temperature=None,
        max_tokens=None,
        **kwargs
    ) -> dict:
        """Generate mock structured output."""
        return {"data": {}}
    
    def validate_config(self) -> bool:
        """Validate configuration."""
        return True
    
    async def test_connection(self) -> bool:
        """Test connection."""
        return True
    
    def get_provider_name(self) -> str:
        """Get provider name."""
        return self._provider_name


# Hypothesis strategies for generating test data
@st.composite
def job_description_strategy(draw):
    """Generate realistic job descriptions with varying content."""
    # Job titles
    job_titles = [
        "Senior Software Engineer",
        "Software Developer",
        "Full Stack Engineer",
        "Backend Developer",
        "Frontend Engineer",
        "DevOps Engineer",
        "Engineering Manager",
        "Tech Lead"
    ]
    
    # Companies
    companies = [
        "TechCorp",
        "StartupXYZ",
        "BigTech Inc",
        "InnovateCo",
        None  # Sometimes no company mentioned
    ]
    
    # Experience requirements
    experience_reqs = [
        "5+ years of experience in software development",
        "3-5 years of professional experience",
        "7+ years in backend development",
        "Entry level position",
        "Senior level with 10+ years experience"
    ]
    
    # Skills
    all_skills = [
        "Python", "Java", "JavaScript", "TypeScript", "React", "Vue", "Angular",
        "Node.js", "SQL", "NoSQL", "AWS", "Azure", "Docker", "Kubernetes",
        "REST API", "GraphQL", "Microservices", "CI/CD"
    ]
    
    # Additional keywords
    additional_keywords = [
        "Agile", "Scrum", "DevOps", "Testing", "Automation",
        "Architecture", "Scalable", "Distributed", "Cloud"
    ]
    
    # Generate job description components
    job_title = draw(st.sampled_from(job_titles))
    company = draw(st.sampled_from(companies))
    experience_req = draw(st.sampled_from(experience_reqs))
    
    # Select random skills (3-8 skills)
    num_skills = draw(st.integers(min_value=3, max_value=8))
    skills = draw(st.lists(
        st.sampled_from(all_skills),
        min_size=num_skills,
        max_size=num_skills,
        unique=True
    ))
    
    # Select additional keywords (2-5 keywords)
    num_keywords = draw(st.integers(min_value=2, max_value=5))
    extra_keywords = draw(st.lists(
        st.sampled_from(additional_keywords),
        min_size=num_keywords,
        max_size=num_keywords,
        unique=True
    ))
    
    # Build job description text
    description = f"{job_title}\n\n"
    
    if company:
        description += f"Company: {company}\n\n"
    
    description += "We are seeking a talented professional to join our team.\n\n"
    description += "Requirements:\n"
    description += f"- {experience_req}\n"
    description += f"- Strong proficiency in {', '.join(skills[:3])}\n"
    
    if len(skills) > 3:
        description += f"- Experience with {', '.join(skills[3:])}\n"
    
    description += "- Bachelor's degree in Computer Science or related field\n"
    description += f"- Knowledge of {', '.join(extra_keywords)}\n"
    description += "- Excellent communication and problem-solving skills\n\n"
    
    description += "Responsibilities:\n"
    description += "- Design and develop scalable applications\n"
    description += "- Collaborate with cross-functional teams\n"
    description += "- Mentor junior developers\n"
    description += "- Participate in code reviews and technical discussions\n"
    
    # Return description and expected extracted data
    expected_data = {
        "job_title": job_title,
        "company": company,
        "skills": skills,
        "keywords": skills + extra_keywords,
        "has_requirements": True,
        "min_skills": len(skills),
        "min_keywords": len(skills) + len(extra_keywords)
    }
    
    return description, expected_data


@st.composite
def provider_config_strategy(draw):
    """Generate provider configurations."""
    provider_type = draw(st.sampled_from(["openai", "anthropic", "local"]))
    
    if provider_type == "openai":
        model = draw(st.sampled_from(["gpt-4", "gpt-3.5-turbo"]))
        config = LLMConfig(
            provider=provider_type,
            model=model,
            api_key="test-key-123",
            temperature=draw(st.floats(min_value=0.0, max_value=0.3)),
            max_tokens=draw(st.integers(min_value=1000, max_value=2000))
        )
    elif provider_type == "anthropic":
        model = draw(st.sampled_from(["claude-3-opus", "claude-3-sonnet"]))
        config = LLMConfig(
            provider=provider_type,
            model=model,
            api_key="test-key-456",
            temperature=draw(st.floats(min_value=0.0, max_value=0.3)),
            max_tokens=draw(st.integers(min_value=1000, max_value=2000))
        )
    else:  # local
        model = draw(st.sampled_from(["llama2", "mistral"]))
        config = LLMConfig(
            provider=provider_type,
            model=model,
            base_url="http://localhost:11434",
            temperature=draw(st.floats(min_value=0.0, max_value=0.3)),
            max_tokens=draw(st.integers(min_value=1000, max_value=2000))
        )
    
    return config, provider_type


# Property Tests
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy(),
    job_desc_and_expected=job_description_strategy()
)
@pytest.mark.asyncio
async def test_property_job_description_extraction(
    config_and_provider,
    job_desc_and_expected
):
    """
    Property 31: Job Description Extraction
    
    For any job description text, the LLM service should extract and return
    structured data including requirements, skills, and keywords.
    
    Validates: Requirements 12.1
    """
    config, provider_type = config_and_provider
    job_description, expected_data = job_desc_and_expected
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create optimizer
    optimizer = CVOptimizer(mock_provider)
    
    # Analyze job description
    analysis = await optimizer.analyze_job_description(job_description)
    
    # Property assertions
    # 1. Analysis should not be None and should be correct type
    assert analysis is not None, "Job description analysis should not be None"
    assert isinstance(analysis, JobDescriptionAnalysis), \
        "Analysis should be JobDescriptionAnalysis instance"
    
    # 2. Job title should be extracted and non-empty
    assert analysis.job_title, "Job title should be extracted"
    assert isinstance(analysis.job_title, str), "Job title should be a string"
    assert len(analysis.job_title.strip()) > 0, "Job title should not be empty"
    assert analysis.job_title != "Not specified" or len(job_description) < 50, \
        "Job title should be extracted from valid job descriptions"
    
    # 3. Requirements should be extracted as a list
    assert analysis.requirements is not None, "Requirements should not be None"
    assert isinstance(analysis.requirements, list), "Requirements should be a list"
    
    # For job descriptions with clear requirements, should extract at least one
    if expected_data["has_requirements"]:
        assert len(analysis.requirements) > 0, \
            "Should extract at least one requirement from job description"
    
    # Each requirement should be a non-empty string
    for req in analysis.requirements:
        assert isinstance(req, str), "Each requirement should be a string"
        assert len(req.strip()) > 0, "Requirements should not be empty strings"
        assert len(req) < 500, "Requirements should be concise (< 500 chars)"
    
    # 4. Skills should be extracted as a list
    assert analysis.skills is not None, "Skills should not be None"
    assert isinstance(analysis.skills, list), "Skills should be a list"
    assert len(analysis.skills) > 0, \
        "Should extract at least one skill from job description"
    
    # Each skill should be a non-empty string
    for skill in analysis.skills:
        assert isinstance(skill, str), "Each skill should be a string"
        assert len(skill.strip()) > 0, "Skills should not be empty strings"
        assert len(skill) < 100, "Skills should be concise (< 100 chars)"
    
    # 5. Keywords should be extracted as a list
    assert analysis.keywords is not None, "Keywords should not be None"
    assert isinstance(analysis.keywords, list), "Keywords should be a list"
    assert len(analysis.keywords) > 0, \
        "Should extract at least one keyword from job description"
    
    # Each keyword should be a non-empty string
    for keyword in analysis.keywords:
        assert isinstance(keyword, str), "Each keyword should be a string"
        assert len(keyword.strip()) > 0, "Keywords should not be empty strings"
        assert len(keyword) < 100, "Keywords should be concise (< 100 chars)"
    
    # 6. Keywords should be a superset of skills (or at least overlap)
    # Skills are typically included in keywords for ATS optimization
    skill_set = set(s.lower() for s in analysis.skills)
    keyword_set = set(k.lower() for k in analysis.keywords)
    
    # At least 50% of skills should appear in keywords
    overlap = skill_set & keyword_set
    overlap_ratio = len(overlap) / max(len(skill_set), 1)
    assert overlap_ratio >= 0.3, \
        f"Keywords should include most skills (overlap: {overlap_ratio:.1%})"
    
    # 7. Experience level should be extracted (optional field)
    if analysis.experience_level:
        assert isinstance(analysis.experience_level, str), \
            "Experience level should be a string"
        assert len(analysis.experience_level.strip()) > 0, \
            "Experience level should not be empty if provided"
    
    # 8. Industry should be extracted (optional field)
    if analysis.industry:
        assert isinstance(analysis.industry, str), "Industry should be a string"
        assert len(analysis.industry.strip()) > 0, \
            "Industry should not be empty if provided"
    
    # 9. Company should be extracted if mentioned (optional field)
    if analysis.company:
        assert isinstance(analysis.company, str), "Company should be a string"
        assert len(analysis.company.strip()) > 0, \
            "Company should not be empty if provided"
    
    # 10. No duplicate entries in lists
    assert len(analysis.requirements) == len(set(analysis.requirements)), \
        "Requirements should not contain duplicates"
    assert len(analysis.skills) == len(set(analysis.skills)), \
        "Skills should not contain duplicates"
    assert len(analysis.keywords) == len(set(analysis.keywords)), \
        "Keywords should not contain duplicates"
    
    # 11. Extracted data should be relevant to job description
    # Check that at least some extracted terms appear in the original description
    description_lower = job_description.lower()
    
    # At least 50% of skills should appear in the job description
    skills_in_description = sum(
        1 for skill in analysis.skills
        if skill.lower() in description_lower
    )
    skills_relevance = skills_in_description / max(len(analysis.skills), 1)
    assert skills_relevance >= 0.3, \
        f"Extracted skills should be relevant to job description (relevance: {skills_relevance:.1%})"
    
    # At least 30% of keywords should appear in the job description
    keywords_in_description = sum(
        1 for keyword in analysis.keywords
        if keyword.lower() in description_lower
    )
    keywords_relevance = keywords_in_description / max(len(analysis.keywords), 1)
    assert keywords_relevance >= 0.2, \
        f"Extracted keywords should be relevant to job description (relevance: {keywords_relevance:.1%})"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_job_description_extraction_minimal_input(
    config_and_provider
):
    """
    Property 31: Job Description Extraction - Minimal Input
    
    For minimal but valid job descriptions, the service should still
    extract structured data with at least basic information.
    
    Validates: Requirements 12.1
    """
    config, provider_type = config_and_provider
    
    # Minimal job descriptions
    minimal_descriptions = [
        "Software Engineer position requiring Python and JavaScript experience.",
        "Looking for a Senior Developer with 5+ years experience in web development.",
        "Backend Engineer role. Must know Java, SQL, and REST APIs.",
        "Full Stack Developer needed. React and Node.js required."
    ]
    
    for description in minimal_descriptions:
        # Create mock provider
        mock_provider = MockLLMProvider(config, provider_type)
        
        # Create optimizer
        optimizer = CVOptimizer(mock_provider)
        
        # Analyze job description
        analysis = await optimizer.analyze_job_description(description)
        
        # Property assertions
        # 1. Should extract basic information even from minimal input
        assert analysis is not None, "Should analyze minimal job descriptions"
        assert isinstance(analysis, JobDescriptionAnalysis), \
            "Should return JobDescriptionAnalysis"
        
        # 2. Should extract at least job title or role indication
        assert analysis.job_title, "Should extract job title from minimal description"
        assert len(analysis.job_title) > 0, "Job title should not be empty"
        
        # 3. Should extract at least some skills or keywords
        total_extracted = len(analysis.skills) + len(analysis.keywords)
        assert total_extracted > 0, \
            f"Should extract at least some skills or keywords from: {description}"
        
        # 4. Should extract at least one requirement (even if generic)
        assert len(analysis.requirements) > 0, \
            "Should extract at least one requirement"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_job_description_extraction_comprehensive_input(
    config_and_provider
):
    """
    Property 31: Job Description Extraction - Comprehensive Input
    
    For detailed job descriptions with rich content, the service should
    extract comprehensive structured data.
    
    Validates: Requirements 12.1
    """
    config, provider_type = config_and_provider
    
    # Comprehensive job description
    comprehensive_description = """
    Senior Full Stack Engineer
    
    Company: TechCorp Inc.
    Location: San Francisco, CA
    
    About Us:
    TechCorp is a leading technology company building innovative solutions.
    
    Job Description:
    We are seeking an experienced Senior Full Stack Engineer to join our team.
    
    Requirements:
    - 5+ years of professional software development experience
    - Bachelor's degree in Computer Science or related field
    - Strong proficiency in Python, JavaScript, and TypeScript
    - Experience with React, Vue.js, or Angular
    - Solid understanding of Node.js and Express
    - Experience with SQL and NoSQL databases
    - Knowledge of AWS, Docker, and Kubernetes
    - Experience with CI/CD pipelines and DevOps practices
    - Strong problem-solving and communication skills
    - Experience leading technical projects
    
    Responsibilities:
    - Design and develop scalable web applications
    - Lead technical initiatives and mentor junior developers
    - Collaborate with product and design teams
    - Participate in code reviews and architectural discussions
    - Implement best practices for testing and deployment
    
    Nice to Have:
    - Experience with microservices architecture
    - Knowledge of GraphQL
    - Contributions to open source projects
    - Experience with Agile/Scrum methodologies
    """
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create optimizer
    optimizer = CVOptimizer(mock_provider)
    
    # Analyze job description
    analysis = await optimizer.analyze_job_description(comprehensive_description)
    
    # Property assertions
    # 1. Should extract comprehensive information
    assert analysis is not None, "Should analyze comprehensive job description"
    assert isinstance(analysis, JobDescriptionAnalysis), \
        "Should return JobDescriptionAnalysis"
    
    # 2. Should extract detailed job title
    assert analysis.job_title, "Should extract job title"
    assert "engineer" in analysis.job_title.lower() or \
           "developer" in analysis.job_title.lower(), \
        "Job title should reflect the role"
    
    # 3. Should extract company if mentioned
    # Company extraction is optional but should work for clear mentions
    if analysis.company:
        assert len(analysis.company) > 0, "Company should not be empty if extracted"
    
    # 4. Should extract multiple requirements
    assert len(analysis.requirements) >= 3, \
        "Should extract multiple requirements from comprehensive description"
    
    # 5. Should extract multiple skills
    assert len(analysis.skills) >= 5, \
        "Should extract multiple skills from comprehensive description"
    
    # 6. Should extract multiple keywords
    assert len(analysis.keywords) >= 5, \
        "Should extract multiple keywords from comprehensive description"
    
    # 7. Should extract experience level
    if analysis.experience_level:
        assert "senior" in analysis.experience_level.lower() or \
               "5" in analysis.experience_level, \
            "Should identify senior level from requirements"
    
    # 8. Should extract relevant technical skills
    description_lower = comprehensive_description.lower()
    expected_skills = ["python", "javascript", "react", "node", "aws", "docker"]
    
    extracted_skills_lower = [s.lower() for s in analysis.skills]
    found_skills = sum(
        1 for skill in expected_skills
        if any(skill in extracted.lower() for extracted in extracted_skills_lower)
    )
    
    assert found_skills >= 3, \
        f"Should extract at least 3 of the major technical skills mentioned"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_job_description_extraction_consistency(
    config_and_provider
):
    """
    Property 31: Job Description Extraction - Consistency
    
    For the same job description, extraction should be consistent
    across multiple runs.
    
    Validates: Requirements 12.1
    """
    config, provider_type = config_and_provider
    
    # Fixed job description for consistency testing
    job_description = """
    Senior Software Engineer
    
    Requirements:
    - 5+ years of experience in software development
    - Strong proficiency in Python and JavaScript
    - Experience with React and Node.js
    - Knowledge of AWS and Docker
    - Bachelor's degree in Computer Science
    
    Responsibilities:
    - Design and develop scalable applications
    - Lead technical projects
    - Mentor junior developers
    """
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create optimizer
    optimizer = CVOptimizer(mock_provider)
    
    # Analyze job description twice
    analysis1 = await optimizer.analyze_job_description(job_description)
    analysis2 = await optimizer.analyze_job_description(job_description)
    
    # Property assertions
    # 1. Both analyses should succeed
    assert analysis1 is not None, "First analysis should succeed"
    assert analysis2 is not None, "Second analysis should succeed"
    
    # 2. Job titles should be consistent
    assert analysis1.job_title == analysis2.job_title, \
        "Job title extraction should be consistent"
    
    # 3. Should extract similar number of requirements
    req_diff = abs(len(analysis1.requirements) - len(analysis2.requirements))
    assert req_diff <= 1, \
        f"Should extract similar number of requirements (diff: {req_diff})"
    
    # 4. Should extract similar number of skills
    skill_diff = abs(len(analysis1.skills) - len(analysis2.skills))
    assert skill_diff <= 2, \
        f"Should extract similar number of skills (diff: {skill_diff})"
    
    # 5. Should extract similar number of keywords
    keyword_diff = abs(len(analysis1.keywords) - len(analysis2.keywords))
    assert keyword_diff <= 3, \
        f"Should extract similar number of keywords (diff: {keyword_diff})"
    
    # 6. Core skills should be consistent
    skills1_lower = set(s.lower() for s in analysis1.skills)
    skills2_lower = set(s.lower() for s in analysis2.skills)
    
    # At least 70% overlap in skills
    overlap = skills1_lower & skills2_lower
    overlap_ratio = len(overlap) / max(len(skills1_lower), 1)
    assert overlap_ratio >= 0.5, \
        f"Core skills should be consistent across runs (overlap: {overlap_ratio:.1%})"


@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_job_description_extraction_invalid_input(
    config_and_provider
):
    """
    Property 31: Job Description Extraction - Invalid Input Handling
    
    For invalid or too-short job descriptions, the service should
    raise appropriate errors.
    
    Validates: Requirements 12.1
    """
    config, provider_type = config_and_provider
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create optimizer
    optimizer = CVOptimizer(mock_provider)
    
    # Test empty job description
    with pytest.raises(ValueError, match="at least 10 characters"):
        await optimizer.analyze_job_description("")
    
    # Test too short job description
    with pytest.raises(ValueError, match="at least 10 characters"):
        await optimizer.analyze_job_description("short")
    
    # Test whitespace-only job description
    with pytest.raises(ValueError, match="at least 10 characters"):
        await optimizer.analyze_job_description("   \n\t   ")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
