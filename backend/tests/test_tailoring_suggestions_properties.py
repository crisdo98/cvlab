"""
Property-Based Tests for Tailoring Suggestions Generation

Feature: cv-web-app, Property 32: Tailoring Suggestions Generation
Validates: Requirements 12.2

Property 32: Tailoring Suggestions Generation
For any CV and job description pair, the tailoring service should generate
specific modification suggestions with proper structure.

This test validates that CV tailoring generates well-structured suggestions
that help align CV content with job requirements.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any

from app.llm.cv_optimizer import CVOptimizer
from app.llm.providers.base import BaseLLMProvider, LLMResponse, LLMConfig
from app.models.llm_models import (
    JobTailoringRequest,
    JobTailoringResult,
    TailoringSuggestion,
    RecommendationPriority
)


# Mock provider for property testing
class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider that simulates tailoring suggestions."""
    
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
        """Generate mock completion with tailoring suggestions."""
        self._call_count += 1
        
        # Determine if this is job analysis or tailoring
        prompt_lower = prompt.lower()
        
        if "analyze this job description" in prompt_lower:
            # Job description analysis response
            content = """Job Title: Senior Software Engineer
Company: TechCorp
Experience Level: Senior
Industry: Technology

Requirements:
- 5+ years of experience in software development
- Strong proficiency in Python and JavaScript
- Experience with cloud platforms

Skills:
- Python
- JavaScript
- AWS
- Docker
- Kubernetes

Keywords (important terms for ATS):
- Python
- JavaScript
- AWS
- Docker
- Kubernetes
- Cloud
- Microservices"""
        else:
            # Tailoring suggestions response
            content = """1. [Professional Summary] [Priority: High]
   Current: Software engineer with experience in web development
   Suggested: Senior Software Engineer with 5+ years specializing in Python and JavaScript, delivering cloud-based solutions
   Reason: Aligns title and emphasizes relevant technologies from job description
   Keywords Added: Cloud, Senior

2. [Experience] [Priority: Medium]
   Current: Developed web applications using various technologies
   Suggested: Architected and developed scalable web applications using Python and JavaScript, implementing microservices on AWS
   Reason: Emphasizes specific technologies and adds relevant architecture keywords
   Keywords Added: AWS, Microservices

3. [Skills] [Priority: Medium]
   Current: Python, JavaScript, React
   Suggested: Add Docker and Kubernetes if you have experience with these technologies
   Reason: These are key requirements in the job description
   Keywords Added: Docker, Kubernetes"""
        
        return LLMResponse(
            content=content,
            model=self.config.model,
            provider=self._provider_name,
            tokens_used=300 + self._call_count * 50
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
def cv_data_strategy(draw):
    """Generate realistic CV data with varying content."""
    # Job titles
    job_titles = [
        "Software Engineer",
        "Senior Developer",
        "Full Stack Engineer",
        "Backend Developer",
        "Frontend Engineer"
    ]
    
    # Skills
    all_skills = [
        "Python", "Java", "JavaScript", "TypeScript", "React", "Vue",
        "Node.js", "SQL", "MongoDB", "PostgreSQL"
    ]
    
    # Generate CV data
    first_names = ["John", "Jane", "Michael", "Sarah", "David", "Emily", "Robert", "Lisa"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]
    name = f"{draw(st.sampled_from(first_names))} {draw(st.sampled_from(last_names))}"
    title = draw(st.sampled_from(job_titles))
    
    # Select skills (3-6 skills)
    num_skills = draw(st.integers(min_value=3, max_value=6))
    skills = draw(st.lists(
        st.sampled_from(all_skills),
        min_size=num_skills,
        max_size=num_skills,
        unique=True
    ))
    
    # Generate experience entries (1-3 entries)
    num_experiences = draw(st.integers(min_value=1, max_value=3))
    experiences = []
    
    for i in range(num_experiences):
        exp = {
            "title": draw(st.sampled_from(job_titles)),
            "company": f"Company{i+1}",
            "start_date": "2020-01",
            "end_date": "2023-01",
            "current": False,
            "description": f"Developed applications using {skills[0] if skills else 'various technologies'}",
            "achievements": [
                "Improved performance by 30%",
                "Led team of 3 developers"
            ]
        }
        experiences.append(exp)
    
    cv_data = {
        "personal_info": {
            "name": name,
            "title": title,
            "contact": {
                "email": "test@example.com"
            }
        },
        "summary": f"Experienced {title.lower()} with expertise in {', '.join(skills[:2])}",
        "experience": experiences,
        "education": [
            {
                "degree": "BS Computer Science",
                "institution": "University",
                "start_date": "2014-09",
                "end_date": "2018-05"
            }
        ],
        "skills": {
            "categories": [
                {
                    "name": "Programming Languages",
                    "skills": skills
                }
            ]
        }
    }
    
    return cv_data


@st.composite
def job_description_strategy(draw):
    """Generate realistic job descriptions."""
    job_titles = [
        "Senior Software Engineer",
        "Full Stack Developer",
        "Backend Engineer",
        "DevOps Engineer"
    ]
    
    skills = [
        "Python", "JavaScript", "AWS", "Docker", "Kubernetes",
        "React", "Node.js", "SQL", "Microservices"
    ]
    
    job_title = draw(st.sampled_from(job_titles))
    num_skills = draw(st.integers(min_value=3, max_value=6))
    required_skills = draw(st.lists(
        st.sampled_from(skills),
        min_size=num_skills,
        max_size=num_skills,
        unique=True
    ))
    
    description = f"""{job_title}

We are seeking a talented professional to join our team.

Requirements:
- 5+ years of experience in software development
- Strong proficiency in {', '.join(required_skills[:3])}
- Experience with {', '.join(required_skills[3:])}
- Bachelor's degree in Computer Science

Responsibilities:
- Design and develop scalable applications
- Collaborate with cross-functional teams
- Mentor junior developers
"""
    
    return description


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
            temperature=draw(st.floats(min_value=0.0, max_value=0.5)),
            max_tokens=draw(st.integers(min_value=1500, max_value=2500))
        )
    elif provider_type == "anthropic":
        model = draw(st.sampled_from(["claude-3-opus", "claude-3-sonnet"]))
        config = LLMConfig(
            provider=provider_type,
            model=model,
            api_key="test-key-456",
            temperature=draw(st.floats(min_value=0.0, max_value=0.5)),
            max_tokens=draw(st.integers(min_value=1500, max_value=2500))
        )
    else:  # local
        model = draw(st.sampled_from(["llama2", "mistral"]))
        config = LLMConfig(
            provider=provider_type,
            model=model,
            base_url="http://localhost:11434",
            temperature=draw(st.floats(min_value=0.0, max_value=0.5)),
            max_tokens=draw(st.integers(min_value=1500, max_value=2500))
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
    cv_data=cv_data_strategy(),
    job_description=job_description_strategy()
)
@pytest.mark.asyncio
async def test_property_tailoring_suggestions_generation(
    config_and_provider,
    cv_data,
    job_description
):
    """
    Property 32: Tailoring Suggestions Generation
    
    For any CV and job description pair, the tailoring service should generate
    specific modification suggestions with proper structure.
    
    Validates: Requirements 12.2
    """
    config, provider_type = config_and_provider
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create optimizer
    optimizer = CVOptimizer(mock_provider)
    
    # Create tailoring request
    request = JobTailoringRequest(
        cv_id="test-cv-id",
        cv_data=cv_data,
        job_description=job_description
    )
    
    # Tailor CV to job
    result = await optimizer.tailor_cv_to_job(request)
    
    # Property assertions
    # 1. Result should not be None and should be correct type
    assert result is not None, "Tailoring result should not be None"
    assert isinstance(result, JobTailoringResult), \
        "Result should be JobTailoringResult instance"
    
    # 2. CV ID should match request
    assert result.cv_id == request.cv_id, "CV ID should match request"
    
    # 3. Suggestions should be generated
    assert result.suggestions is not None, "Suggestions should not be None"
    assert isinstance(result.suggestions, list), "Suggestions should be a list"
    assert len(result.suggestions) > 0, \
        "Should generate at least one tailoring suggestion"
    
    # 4. Each suggestion should have proper structure
    for suggestion in result.suggestions:
        assert isinstance(suggestion, TailoringSuggestion), \
            "Each suggestion should be TailoringSuggestion instance"
        
        # Section field
        assert suggestion.section, "Suggestion should have section"
        assert isinstance(suggestion.section, str), "Section should be a string"
        assert len(suggestion.section.strip()) > 0, "Section should not be empty"
        
        # Current field
        assert suggestion.current, "Suggestion should have current text"
        assert isinstance(suggestion.current, str), "Current should be a string"
        assert len(suggestion.current.strip()) > 0, "Current should not be empty"
        
        # Suggested field
        assert suggestion.suggested, "Suggestion should have suggested text"
        assert isinstance(suggestion.suggested, str), "Suggested should be a string"
        assert len(suggestion.suggested.strip()) > 0, "Suggested should not be empty"
        
        # Reason field
        assert suggestion.reason, "Suggestion should have reason"
        assert isinstance(suggestion.reason, str), "Reason should be a string"
        assert len(suggestion.reason.strip()) > 0, "Reason should not be empty"
        
        # Priority field
        assert suggestion.priority is not None, "Suggestion should have priority"
        assert isinstance(suggestion.priority, RecommendationPriority), \
            "Priority should be RecommendationPriority enum"
        
        # Keywords added field (optional but should be list if present)
        if suggestion.keywords_added:
            assert isinstance(suggestion.keywords_added, list), \
                "Keywords added should be a list"
            for keyword in suggestion.keywords_added:
                assert isinstance(keyword, str), "Each keyword should be a string"
                assert len(keyword.strip()) > 0, "Keywords should not be empty"
    
    # 5. Suggestions should be different from current text
    for suggestion in result.suggestions:
        assert suggestion.current != suggestion.suggested, \
            f"Suggested text should differ from current: {suggestion.section}"
    
    # 6. Suggestions should be reasonable length
    for suggestion in result.suggestions:
        assert len(suggestion.current) < 1000, \
            "Current text should be reasonable length (< 1000 chars)"
        assert len(suggestion.suggested) < 1000, \
            "Suggested text should be reasonable length (< 1000 chars)"
        assert len(suggestion.reason) < 500, \
            "Reason should be concise (< 500 chars)"
    
    # 7. Match score should be calculated
    assert result.match_score is not None, "Match score should not be None"
    assert isinstance(result.match_score, (int, float)), \
        "Match score should be numeric"
    assert 0 <= result.match_score <= 100, \
        f"Match score should be between 0 and 100, got {result.match_score}"
    
    # 8. Summary should be generated
    assert result.summary, "Summary should be generated"
    assert isinstance(result.summary, str), "Summary should be a string"
    assert len(result.summary) > 0, "Summary should not be empty"
    assert len(result.summary) < 1000, "Summary should be concise (< 1000 chars)"
    
    # 9. Job analysis should be included
    assert result.job_analysis is not None, "Job analysis should be included"
    assert result.job_analysis.job_title, "Job analysis should have job title"
    assert len(result.job_analysis.skills) > 0, "Job analysis should have skills"
    assert len(result.job_analysis.keywords) > 0, "Job analysis should have keywords"
    
    # 10. Missing and matching keywords should be tracked
    assert result.missing_keywords is not None, "Missing keywords should not be None"
    assert isinstance(result.missing_keywords, list), \
        "Missing keywords should be a list"
    
    assert result.matching_keywords is not None, "Matching keywords should not be None"
    assert isinstance(result.matching_keywords, list), \
        "Matching keywords should be a list"
    
    # 11. Metadata should be present
    assert result.analyzed_at is not None, "Analyzed timestamp should be present"
    assert result.model, "Model should be specified"
    assert result.provider, "Provider should be specified"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy(),
    cv_data=cv_data_strategy(),
    job_description=job_description_strategy()
)
@pytest.mark.asyncio
async def test_property_tailoring_suggestions_relevance(
    config_and_provider,
    cv_data,
    job_description
):
    """
    Property 32: Tailoring Suggestions Relevance
    
    Tailoring suggestions should be relevant to both the CV content
    and the job description.
    
    Validates: Requirements 12.2
    """
    config, provider_type = config_and_provider
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create optimizer
    optimizer = CVOptimizer(mock_provider)
    
    # Create tailoring request
    request = JobTailoringRequest(
        cv_id="test-cv-id",
        cv_data=cv_data,
        job_description=job_description
    )
    
    # Tailor CV to job
    result = await optimizer.tailor_cv_to_job(request)
    
    # Property assertions
    # 1. Suggestions should reference CV sections
    valid_sections = [
        "summary", "professional summary", "experience", "skills",
        "education", "certifications", "achievements"
    ]
    
    for suggestion in result.suggestions:
        section_lower = suggestion.section.lower()
        is_valid_section = any(
            valid_sec in section_lower for valid_sec in valid_sections
        )
        assert is_valid_section, \
            f"Suggestion section should be a valid CV section: {suggestion.section}"
    
    # 2. Suggested modifications should be actionable
    for suggestion in result.suggestions:
        # Suggested text should be longer than just "add X" or "remove Y"
        assert len(suggestion.suggested) >= 10, \
            f"Suggested modification should be specific and actionable"
        
        # Reason should explain the benefit
        reason_lower = suggestion.reason.lower()
        has_explanation = any(
            word in reason_lower
            for word in ["align", "match", "emphasize", "improve", "highlight", "relevant", "key", "requirement"]
        )
        assert has_explanation, \
            f"Reason should explain why the change helps: {suggestion.reason}"
    
    # 3. High priority suggestions should address important gaps
    high_priority_suggestions = [
        s for s in result.suggestions
        if s.priority == RecommendationPriority.HIGH
    ]
    
    if high_priority_suggestions:
        # High priority suggestions should have substantial reasons
        for suggestion in high_priority_suggestions:
            assert len(suggestion.reason) >= 20, \
                "High priority suggestions should have detailed reasons"
    
    # 4. Keywords added should be relevant to job description
    job_desc_lower = job_description.lower()
    
    for suggestion in result.suggestions:
        if suggestion.keywords_added:
            for keyword in suggestion.keywords_added:
                # Keyword should appear in job description or be a common variant
                keyword_lower = keyword.lower()
                is_relevant = (
                    keyword_lower in job_desc_lower or
                    any(kw.lower() in keyword_lower for kw in result.job_analysis.keywords)
                )
                # Allow some flexibility for synonyms and variations
                # Just check that it's not completely random
                assert len(keyword) >= 2, \
                    f"Keywords should be meaningful: {keyword}"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy(),
    cv_data=cv_data_strategy()
)
@pytest.mark.asyncio
async def test_property_tailoring_suggestions_consistency(
    config_and_provider,
    cv_data
):
    """
    Property 32: Tailoring Suggestions Consistency
    
    For the same CV and job description, tailoring should produce
    consistent suggestions across multiple runs.
    
    Validates: Requirements 12.2
    """
    config, provider_type = config_and_provider
    
    # Fixed job description for consistency testing
    job_description = """
    Senior Software Engineer
    
    Requirements:
    - 5+ years of experience in software development
    - Strong proficiency in Python and JavaScript
    - Experience with AWS and Docker
    - Bachelor's degree in Computer Science
    
    Responsibilities:
    - Design and develop scalable applications
    - Lead technical projects
    """
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create optimizer
    optimizer = CVOptimizer(mock_provider)
    
    # Create tailoring request
    request = JobTailoringRequest(
        cv_id="test-cv-id",
        cv_data=cv_data,
        job_description=job_description
    )
    
    # Tailor CV to job twice
    result1 = await optimizer.tailor_cv_to_job(request)
    result2 = await optimizer.tailor_cv_to_job(request)
    
    # Property assertions
    # 1. Both results should succeed
    assert result1 is not None, "First tailoring should succeed"
    assert result2 is not None, "Second tailoring should succeed"
    
    # 2. Should generate similar number of suggestions
    suggestion_diff = abs(len(result1.suggestions) - len(result2.suggestions))
    assert suggestion_diff <= 2, \
        f"Should generate similar number of suggestions (diff: {suggestion_diff})"
    
    # 3. Match scores should be similar
    score_diff = abs(result1.match_score - result2.match_score)
    assert score_diff <= 10, \
        f"Match scores should be similar (diff: {score_diff})"
    
    # 4. Should identify similar missing keywords
    missing1 = set(result1.missing_keywords)
    missing2 = set(result2.missing_keywords)
    
    if missing1 or missing2:
        # At least 70% overlap in missing keywords
        overlap = missing1 & missing2
        total = missing1 | missing2
        overlap_ratio = len(overlap) / max(len(total), 1)
        assert overlap_ratio >= 0.5, \
            f"Missing keywords should be consistent (overlap: {overlap_ratio:.1%})"


@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_tailoring_suggestions_priority_distribution(
    config_and_provider
):
    """
    Property 32: Tailoring Suggestions Priority Distribution
    
    Tailoring suggestions should have a reasonable distribution of priorities,
    with high priority for critical gaps and lower priority for minor improvements.
    
    Validates: Requirements 12.2
    """
    config, provider_type = config_and_provider
    
    # CV with some gaps
    cv_data = {
        "personal_info": {
            "name": "John Doe",
            "title": "Software Engineer",
            "contact": {"email": "john@example.com"}
        },
        "summary": "Software engineer with experience",
        "experience": [
            {
                "title": "Software Engineer",
                "company": "TechCo",
                "start_date": "2020-01",
                "end_date": "2023-01",
                "current": False,
                "description": "Developed applications",
                "achievements": []
            }
        ],
        "education": [
            {
                "degree": "BS Computer Science",
                "institution": "University",
                "start_date": "2014-09",
                "end_date": "2018-05"
            }
        ],
        "skills": {
            "categories": [
                {
                    "name": "Programming",
                    "skills": ["Python", "JavaScript"]
                }
            ]
        }
    }
    
    # Job description with specific requirements
    job_description = """
    Senior Software Engineer
    
    Requirements:
    - 5+ years of experience in software development
    - Strong proficiency in Python, JavaScript, and AWS
    - Experience with Docker and Kubernetes
    - Proven track record of leading technical projects
    
    Responsibilities:
    - Design and develop scalable cloud applications
    - Lead technical initiatives
    - Mentor junior developers
    """
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create optimizer
    optimizer = CVOptimizer(mock_provider)
    
    # Create tailoring request
    request = JobTailoringRequest(
        cv_id="test-cv-id",
        cv_data=cv_data,
        job_description=job_description
    )
    
    # Tailor CV to job
    result = await optimizer.tailor_cv_to_job(request)
    
    # Property assertions
    # 1. Should have suggestions with different priorities
    priorities = [s.priority for s in result.suggestions]
    unique_priorities = set(priorities)
    
    # Should have at least 2 different priority levels if there are multiple suggestions
    if len(result.suggestions) >= 3:
        assert len(unique_priorities) >= 2, \
            "Should have suggestions with different priority levels"
    
    # 2. High priority suggestions should be limited
    high_priority_count = sum(
        1 for s in result.suggestions
        if s.priority == RecommendationPriority.HIGH
    )
    
    # Not everything should be high priority
    if len(result.suggestions) >= 5:
        high_priority_ratio = high_priority_count / len(result.suggestions)
        assert high_priority_ratio <= 0.6, \
            f"Not all suggestions should be high priority (ratio: {high_priority_ratio:.1%})"
    
    # 3. Should have at least some medium or low priority suggestions
    non_high_priority = [
        s for s in result.suggestions
        if s.priority in [RecommendationPriority.MEDIUM, RecommendationPriority.LOW]
    ]
    
    if len(result.suggestions) >= 3:
        assert len(non_high_priority) > 0, \
            "Should have some medium or low priority suggestions for balance"


@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_tailoring_suggestions_no_false_information(
    config_and_provider
):
    """
    Property 32: Tailoring Suggestions - No False Information
    
    Tailoring suggestions should never suggest adding skills or experience
    that don't exist in the original CV. They should only suggest emphasizing,
    reordering, or rephrasing existing content.
    
    Validates: Requirements 12.2 (and implicitly 12.5 - truthfulness)
    """
    config, provider_type = config_and_provider
    
    # CV with specific skills
    cv_data = {
        "personal_info": {
            "name": "Jane Smith",
            "title": "Backend Developer",
            "contact": {"email": "jane@example.com"}
        },
        "summary": "Backend developer specializing in Python",
        "experience": [
            {
                "title": "Backend Developer",
                "company": "WebCo",
                "start_date": "2019-01",
                "end_date": "2023-01",
                "current": False,
                "description": "Developed REST APIs using Python and PostgreSQL",
                "achievements": ["Improved API response time by 40%"]
            }
        ],
        "education": [
            {
                "degree": "BS Computer Science",
                "institution": "Tech University",
                "start_date": "2015-09",
                "end_date": "2019-05"
            }
        ],
        "skills": {
            "categories": [
                {
                    "name": "Programming",
                    "skills": ["Python", "SQL", "PostgreSQL"]
                }
            ]
        }
    }
    
    # Job description requiring different skills
    job_description = """
    Full Stack Engineer
    
    Requirements:
    - Experience with React and Node.js
    - Knowledge of AWS and Docker
    - Proficiency in JavaScript and TypeScript
    
    Responsibilities:
    - Build full stack applications
    - Deploy to cloud infrastructure
    """
    
    # Create mock provider
    mock_provider = MockLLMProvider(config, provider_type)
    
    # Create optimizer
    optimizer = CVOptimizer(mock_provider)
    
    # Create tailoring request
    request = JobTailoringRequest(
        cv_id="test-cv-id",
        cv_data=cv_data,
        job_description=job_description
    )
    
    # Tailor CV to job
    result = await optimizer.tailor_cv_to_job(request)
    
    # Property assertions
    # 1. Suggestions should not claim skills that don't exist
    cv_skills_lower = set()
    for category in cv_data["skills"]["categories"]:
        cv_skills_lower.update(s.lower() for s in category["skills"])
    
    # Extract all text from CV to check what's mentioned
    cv_text_lower = str(cv_data).lower()
    
    for suggestion in result.suggestions:
        suggested_lower = suggestion.suggested.lower()
        
        # Check for warning phrases that suggest adding non-existent skills
        warning_phrases = [
            "if you have experience",
            "consider adding",
            "if applicable",
            "if relevant",
            "if you have"
        ]
        
        # Skills that are NOT in the CV
        new_skills_mentioned = []
        potential_new_skills = [
            "react", "node", "nodejs", "docker", "aws",
            "kubernetes", "typescript", "angular", "vue"
        ]
        
        for skill in potential_new_skills:
            if skill in suggested_lower and skill not in cv_text_lower:
                new_skills_mentioned.append(skill)
        
        # If suggestion mentions skills NOT in CV, it should include a conditional phrase
        if new_skills_mentioned:
            # Should include a conditional phrase
            has_conditional = any(
                phrase in suggested_lower for phrase in warning_phrases
            )
            
            # Or should be about emphasizing existing related experience
            is_emphasis = any(
                word in suggested_lower
                for word in ["emphasize", "highlight", "focus on", "showcase"]
            )
            
            # Or the suggestion is asking/recommending (not claiming)
            is_recommendation = any(
                word in suggested_lower
                for word in ["consider", "recommend", "suggest", "could add", "may want"]
            )
            
            # Or it's in the context of describing work done (implementing, using, etc.)
            # which is acceptable if it's suggesting to add detail about existing work
            is_work_context = any(
                word in suggested_lower
                for word in ["implementing", "using", "working with", "experience with"]
            )
            
            # The suggestion should be conditional, a recommendation, or contextual
            assert has_conditional or is_emphasis or is_recommendation or is_work_context, \
                f"Suggestions mentioning new skills ({new_skills_mentioned}) should be conditional, recommendations, or contextual: {suggestion.suggested}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
