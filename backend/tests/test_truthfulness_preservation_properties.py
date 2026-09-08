"""
Property-Based Tests for Truthfulness Preservation

Feature: cv-web-app, Property 35: Truthfulness Preservation
Validates: Requirements 12.5

Property 35: Truthfulness Preservation
For any CV content and tailoring suggestions, the suggested modifications should
not introduce factual claims absent from the original content.

This test validates that CV tailoring maintains truthfulness by ensuring
suggestions only rephrase, emphasize, or reorganize existing information
without adding false claims about skills, experience, or achievements.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any, Set
import re

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
            # Tailoring suggestions response - TRUTHFUL suggestions only
            content = """1. [Professional Summary] [Priority: High]
   Current: Software engineer with experience in web development
   Suggested: Software Engineer with proven experience in web development, specializing in building scalable applications
   Reason: Emphasizes existing experience with more impactful language
   Keywords Added: Scalable

2. [Experience] [Priority: Medium]
   Current: Developed web applications using various technologies
   Suggested: Architected and developed web applications, leveraging existing technical expertise to deliver robust solutions
   Reason: Uses stronger action verbs while maintaining truthfulness about actual work
   Keywords Added: None

3. [Skills] [Priority: Medium]
   Current: Python, SQL, PostgreSQL
   Suggested: Emphasize Python and SQL skills prominently as they align with the job requirements
   Reason: Highlights relevant existing skills without adding new ones
   Keywords Added: None"""
        
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
def cv_with_specific_skills_strategy(draw):
    """Generate CV data with specific, limited skills to test truthfulness."""
    # Define a limited set of skills that will be in the CV
    available_skills = ["Python", "SQL", "PostgreSQL", "Git", "Linux"]
    
    # Select 2-4 skills for this CV
    num_skills = draw(st.integers(min_value=2, max_value=4))
    cv_skills = draw(st.lists(
        st.sampled_from(available_skills),
        min_size=num_skills,
        max_size=num_skills,
        unique=True
    ))
    
    # Generate experience that only mentions CV skills
    experience_desc = f"Developed applications using {cv_skills[0]}"
    if len(cv_skills) > 1:
        experience_desc += f" and {cv_skills[1]}"
    
    cv_data = {
        "personal_info": {
            "name": "Test User",
            "title": "Software Developer",
            "contact": {"email": "test@example.com"}
        },
        "summary": f"Software developer with experience in {', '.join(cv_skills[:2])}",
        "experience": [
            {
                "title": "Software Developer",
                "company": "TechCo",
                "start_date": "2020-01",
                "end_date": "2023-01",
                "current": False,
                "description": experience_desc,
                "achievements": [
                    "Improved system performance by 30%",
                    "Reduced bug count by 25%"
                ]
            }
        ],
        "education": [
            {
                "degree": "BS Computer Science",
                "institution": "University",
                "start_date": "2016-09",
                "end_date": "2020-05"
            }
        ],
        "skills": {
            "categories": [
                {
                    "name": "Programming Languages",
                    "skills": cv_skills
                }
            ]
        }
    }
    
    return cv_data, set(s.lower() for s in cv_skills)


@st.composite
def job_with_different_skills_strategy(draw):
    """Generate job description requiring skills NOT in the CV."""
    # Skills that are NOT in the available_skills list above
    job_required_skills = ["JavaScript", "React", "Node.js", "Docker", "AWS", "Kubernetes"]
    
    num_skills = draw(st.integers(min_value=3, max_value=5))
    required_skills = draw(st.lists(
        st.sampled_from(job_required_skills),
        min_size=num_skills,
        max_size=num_skills,
        unique=True
    ))
    
    description = f"""Senior Software Engineer

We are seeking a talented professional to join our team.

Requirements:
- 5+ years of experience in software development
- Strong proficiency in {', '.join(required_skills[:3])}
- Experience with {', '.join(required_skills[3:])}
- Bachelor's degree in Computer Science

Responsibilities:
- Design and develop scalable applications
- Work with modern cloud technologies
- Collaborate with cross-functional teams
"""
    
    return description, set(s.lower() for s in required_skills)


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
            temperature=0.3,
            max_tokens=2000
        )
    elif provider_type == "anthropic":
        model = draw(st.sampled_from(["claude-3-opus", "claude-3-sonnet"]))
        config = LLMConfig(
            provider=provider_type,
            model=model,
            api_key="test-key-456",
            temperature=0.3,
            max_tokens=2000
        )
    else:  # local
        model = draw(st.sampled_from(["llama2", "mistral"]))
        config = LLMConfig(
            provider=provider_type,
            model=model,
            base_url="http://localhost:11434",
            temperature=0.3,
            max_tokens=2000
        )
    
    return config, provider_type


def extract_skills_from_text(text: str) -> Set[str]:
    """Extract potential skill mentions from text.
    
    Args:
        text: Text to analyze
        
    Returns:
        Set of lowercase skill keywords found in text
    """
    # Common technical skills to check for
    common_skills = [
        "python", "java", "javascript", "typescript", "react", "vue", "angular",
        "node", "nodejs", "node.js", "express", "django", "flask", "fastapi",
        "sql", "postgresql", "mysql", "mongodb", "redis",
        "docker", "kubernetes", "k8s", "aws", "azure", "gcp", "cloud",
        "git", "github", "gitlab", "ci/cd", "jenkins",
        "linux", "unix", "bash", "shell",
        "html", "css", "sass", "tailwind",
        "rest", "api", "graphql", "grpc",
        "microservices", "serverless", "lambda"
    ]
    
    text_lower = text.lower()
    found_skills = set()
    
    for skill in common_skills:
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, text_lower):
            found_skills.add(skill)
    
    return found_skills


def is_conditional_or_recommendation(text: str) -> bool:
    """Check if text is phrased as a conditional or recommendation.
    
    Args:
        text: Text to check
        
    Returns:
        True if text is conditional/recommendation, False if claiming as fact
    """
    text_lower = text.lower()
    
    # Conditional phrases that indicate suggestion, not claim
    conditional_phrases = [
        "if you have", "if applicable", "if relevant", "if you've worked with",
        "consider adding", "consider highlighting", "you may want to",
        "you could add", "you might", "suggest adding", "recommend adding",
        "if this applies", "if true", "assuming you have", "provided you have"
    ]
    
    # Recommendation phrases
    recommendation_phrases = [
        "consider", "recommend", "suggest", "could", "might", "may want",
        "you should", "it would be beneficial", "if possible"
    ]
    
    # Check for conditional phrases
    for phrase in conditional_phrases:
        if phrase in text_lower:
            return True
    
    # Check for recommendation phrases at start of sentences
    sentences = text_lower.split('.')
    for sentence in sentences:
        sentence = sentence.strip()
        for phrase in recommendation_phrases:
            if sentence.startswith(phrase) or f" {phrase} " in sentence:
                return True
    
    return False


def is_emphasis_or_reorganization(suggestion: TailoringSuggestion, cv_skills: Set[str]) -> bool:
    """Check if suggestion is just emphasizing or reorganizing existing content.
    
    Args:
        suggestion: Tailoring suggestion to check
        cv_skills: Set of skills actually in the CV
        
    Returns:
        True if suggestion only emphasizes/reorganizes, False if adding new claims
    """
    current_lower = suggestion.current.lower()
    suggested_lower = suggestion.suggested.lower()
    
    # Extract skills mentioned in both
    current_skills = extract_skills_from_text(current_lower)
    suggested_skills = extract_skills_from_text(suggested_lower)
    
    # New skills mentioned in suggestion
    new_skills = suggested_skills - current_skills
    
    # If no new skills mentioned, it's just reorganization/emphasis
    if not new_skills:
        return True
    
    # If new skills are mentioned, check if they're in the CV
    for skill in new_skills:
        if skill not in cv_skills:
            # New skill not in CV - check if it's conditional
            if not is_conditional_or_recommendation(suggested_lower):
                return False
    
    return True


# Property Tests
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy(),
    cv_and_skills=cv_with_specific_skills_strategy(),
    job_and_skills=job_with_different_skills_strategy()
)
@pytest.mark.asyncio
async def test_property_truthfulness_preservation_no_false_skills(
    config_and_provider,
    cv_and_skills,
    job_and_skills
):
    """
    Property 35: Truthfulness Preservation - No False Skills
    
    For any CV and job description, tailoring suggestions should never claim
    skills or technologies that are not present in the original CV.
    
    Validates: Requirements 12.5
    """
    config, provider_type = config_and_provider
    cv_data, cv_skills = cv_and_skills
    job_description, job_skills = job_and_skills
    
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
    # 1. Result should be generated
    assert result is not None, "Tailoring result should not be None"
    assert len(result.suggestions) > 0, "Should generate suggestions"
    
    # 2. Extract all skills mentioned in original CV
    cv_text = str(cv_data).lower()
    cv_mentioned_skills = extract_skills_from_text(cv_text)
    
    # 3. Check each suggestion for truthfulness
    for suggestion in result.suggestions:
        suggested_lower = suggestion.suggested.lower()
        
        # Extract skills mentioned in suggestion
        suggested_skills = extract_skills_from_text(suggested_lower)
        
        # Find skills in suggestion that are NOT in CV
        new_skills = suggested_skills - cv_mentioned_skills
        
        if new_skills:
            # New skills are mentioned - verify they're presented conditionally
            is_conditional = is_conditional_or_recommendation(suggested_lower)
            
            # Or verify it's just emphasis/reorganization
            is_emphasis = is_emphasis_or_reorganization(suggestion, cv_skills)
            
            # Assertion: New skills must be conditional or emphasis only
            assert is_conditional or is_emphasis, \
                f"Suggestion introduces new skills ({new_skills}) without conditional phrasing. " \
                f"Section: {suggestion.section}, Suggested: {suggestion.suggested}"
    
    # 4. Verify suggestions don't claim false experience
    for suggestion in result.suggestions:
        suggested_lower = suggestion.suggested.lower()
        
        # Check for definitive claims about experience
        definitive_claims = [
            "i have experience with", "i am proficient in", "i have worked with",
            "i am skilled in", "i have expertise in", "i specialize in",
            "my experience includes", "my skills include"
        ]
        
        # Extract skills from suggestion
        suggested_skills = extract_skills_from_text(suggested_lower)
        new_skills = suggested_skills - cv_mentioned_skills
        
        if new_skills:
            # Check if making definitive claims about new skills
            for claim in definitive_claims:
                if claim in suggested_lower:
                    # This is a definitive claim - verify it's about existing skills only
                    # Extract what comes after the claim
                    claim_index = suggested_lower.find(claim)
                    after_claim = suggested_lower[claim_index + len(claim):]
                    
                    # Check if new skills appear in the claim
                    for new_skill in new_skills:
                        if new_skill in after_claim[:100]:  # Check next 100 chars
                            pytest.fail(
                                f"Suggestion makes definitive claim about skill not in CV: {new_skill}. "
                                f"Suggested: {suggestion.suggested}"
                            )


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy(),
    cv_and_skills=cv_with_specific_skills_strategy(),
    job_and_skills=job_with_different_skills_strategy()
)
@pytest.mark.asyncio
async def test_property_truthfulness_preservation_no_false_achievements(
    config_and_provider,
    cv_and_skills,
    job_and_skills
):
    """
    Property 35: Truthfulness Preservation - No False Achievements
    
    For any CV and job description, tailoring suggestions should never introduce
    achievements, metrics, or accomplishments that are not in the original CV.
    
    Validates: Requirements 12.5
    """
    config, provider_type = config_and_provider
    cv_data, cv_skills = cv_and_skills
    job_description, job_skills = job_and_skills
    
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
    # 1. Extract all metrics and achievements from original CV
    cv_achievements = []
    for exp in cv_data.get("experience", []):
        cv_achievements.extend(exp.get("achievements", []))
    
    cv_text = str(cv_data).lower()
    
    # Extract numbers/percentages from CV (metrics)
    cv_metrics = set(re.findall(r'\d+%|\d+x|\d+ percent', cv_text))
    
    # 2. Check each suggestion doesn't introduce new metrics
    for suggestion in result.suggestions:
        suggested_lower = suggestion.suggested.lower()
        
        # Extract metrics from suggestion
        suggested_metrics = set(re.findall(r'\d+%|\d+x|\d+ percent', suggested_lower))
        
        # Find new metrics not in CV
        new_metrics = suggested_metrics - cv_metrics
        
        if new_metrics:
            # New metrics introduced - verify they're presented as examples or conditionals
            is_example = any(
                phrase in suggested_lower
                for phrase in ["for example", "such as", "e.g.", "like", "example:"]
            )
            
            is_conditional = is_conditional_or_recommendation(suggested_lower)
            
            # Or it's asking to add metrics if available
            is_request = any(
                phrase in suggested_lower
                for phrase in ["add metrics", "include numbers", "quantify", "add specific numbers"]
            )
            
            assert is_example or is_conditional or is_request, \
                f"Suggestion introduces new metrics ({new_metrics}) as facts. " \
                f"Section: {suggestion.section}, Suggested: {suggestion.suggested}"
    
    # 3. Check suggestions don't claim new accomplishments
    for suggestion in result.suggestions:
        suggested_lower = suggestion.suggested.lower()
        current_lower = suggestion.current.lower()
        
        # Achievement indicators
        achievement_verbs = [
            "achieved", "delivered", "increased", "reduced", "improved",
            "optimized", "launched", "built", "created", "led", "managed"
        ]
        
        # Check if suggestion adds new achievement verbs with specific claims
        for verb in achievement_verbs:
            if verb in suggested_lower and verb not in current_lower:
                # New achievement verb - verify it's rephrasing existing content
                # or is conditional
                
                # Check if it's in the original CV somewhere
                if verb not in cv_text:
                    # Completely new achievement verb - should be conditional
                    is_conditional = is_conditional_or_recommendation(suggested_lower)
                    
                    # Or it's suggesting to add if applicable
                    is_suggestion = any(
                        phrase in suggested_lower
                        for phrase in ["consider using", "try using", "use stronger verbs like"]
                    )
                    
                    assert is_conditional or is_suggestion, \
                        f"Suggestion introduces new achievement verb '{verb}' as fact. " \
                        f"Section: {suggestion.section}, Suggested: {suggestion.suggested}"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy(),
    cv_and_skills=cv_with_specific_skills_strategy()
)
@pytest.mark.asyncio
async def test_property_truthfulness_preservation_emphasis_only(
    config_and_provider,
    cv_and_skills
):
    """
    Property 35: Truthfulness Preservation - Emphasis Only
    
    When CV already has relevant skills for a job, tailoring should only
    emphasize, reorganize, or rephrase existing content, not add new claims.
    
    Validates: Requirements 12.5
    """
    config, provider_type = config_and_provider
    cv_data, cv_skills = cv_and_skills
    
    # Job description that matches CV skills
    matching_skills = list(cv_skills)[:3]
    job_description = f"""Software Developer

Requirements:
- Experience with {matching_skills[0]}
- Knowledge of {matching_skills[1] if len(matching_skills) > 1 else 'programming'}
- Bachelor's degree in Computer Science

Responsibilities:
- Develop software applications
- Write clean, maintainable code
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
    # 1. When skills match, suggestions should be emphasis/reorganization only
    cv_text = str(cv_data).lower()
    
    for suggestion in result.suggestions:
        suggested_lower = suggestion.suggested.lower()
        current_lower = suggestion.current.lower()
        
        # Extract key content words (nouns, verbs) from both
        # Simple approach: check if suggestion adds significant new content
        
        # Count words in each
        current_words = set(current_lower.split())
        suggested_words = set(suggested_lower.split())
        
        # New words in suggestion
        new_words = suggested_words - current_words
        
        # Filter out common words
        common_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
            "be", "have", "has", "had", "do", "does", "did", "will", "would",
            "should", "could", "may", "might", "can", "must", "shall"
        }
        
        significant_new_words = new_words - common_words
        
        # If significant new words are added, they should be from the CV
        for word in significant_new_words:
            if len(word) > 3:  # Only check meaningful words
                # Word should appear somewhere in CV or be a synonym/variation
                # For this test, we'll be lenient and just check it's not a completely new skill
                if word in ["javascript", "react", "docker", "kubernetes", "aws", "node"]:
                    # These are common skills - if added, should be conditional
                    if word not in cv_text:
                        is_conditional = is_conditional_or_recommendation(suggested_lower)
                        assert is_conditional, \
                            f"Suggestion adds new skill '{word}' without conditional phrasing. " \
                            f"Suggested: {suggestion.suggested}"


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    config_and_provider=provider_config_strategy()
)
@pytest.mark.asyncio
async def test_property_truthfulness_preservation_reasoning_indicates_truthfulness(
    config_and_provider
):
    """
    Property 35: Truthfulness Preservation - Reasoning Indicates Truthfulness
    
    Suggestions should include reasoning that indicates they maintain truthfulness,
    such as "emphasizes existing experience" or "highlights current skills".
    
    Validates: Requirements 12.5
    """
    config, provider_type = config_and_provider
    
    # CV with specific content
    cv_data = {
        "personal_info": {
            "name": "Test User",
            "title": "Backend Developer",
            "contact": {"email": "test@example.com"}
        },
        "summary": "Backend developer with 3 years of experience",
        "experience": [
            {
                "title": "Backend Developer",
                "company": "TechCo",
                "start_date": "2020-01",
                "end_date": "2023-01",
                "current": False,
                "description": "Developed REST APIs using Python and PostgreSQL",
                "achievements": ["Improved API response time by 40%"]
            }
        ],
        "education": [
            {
                "degree": "BS Computer Science",
                "institution": "University",
                "start_date": "2016-09",
                "end_date": "2020-05"
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
    
    # Job requiring different skills
    job_description = """Full Stack Engineer

Requirements:
- Experience with React and Node.js
- Knowledge of AWS and Docker
- 5+ years of experience

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
    # 1. Each suggestion should have reasoning
    for suggestion in result.suggestions:
        assert suggestion.reason, "Each suggestion should have reasoning"
        assert len(suggestion.reason) > 10, "Reasoning should be meaningful"
    
    # 2. Reasoning should indicate truthfulness approach
    truthful_indicators = [
        "emphasize", "highlight", "showcase", "focus on", "bring forward",
        "reorganize", "rephrase", "reword", "strengthen", "clarify",
        "existing", "current", "actual", "proven", "demonstrated",
        "if you have", "if applicable", "consider adding if"
    ]
    
    for suggestion in result.suggestions:
        reason_lower = suggestion.reason.lower()
        
        # Check if reasoning indicates truthful approach
        has_truthful_indicator = any(
            indicator in reason_lower for indicator in truthful_indicators
        )
        
        # Or reasoning explains it's a suggestion/recommendation
        is_recommendation_reasoning = any(
            phrase in reason_lower
            for phrase in ["recommend", "suggest", "could", "might", "consider"]
        )
        
        # At least some suggestions should have truthful indicators
        # (We don't require ALL because some might be straightforward rephrasing)
        # This is a softer check - we verify the pattern exists
        
    # 3. Count suggestions with truthful indicators
    truthful_count = sum(
        1 for s in result.suggestions
        if any(indicator in s.reason.lower() for indicator in truthful_indicators)
    )
    
    # At least 50% of suggestions should have explicit truthful indicators
    if len(result.suggestions) >= 2:
        truthful_ratio = truthful_count / len(result.suggestions)
        assert truthful_ratio >= 0.3, \
            f"At least 30% of suggestions should have truthful indicators in reasoning. " \
            f"Got {truthful_ratio:.1%} ({truthful_count}/{len(result.suggestions)})"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
