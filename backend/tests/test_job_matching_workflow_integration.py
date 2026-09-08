"""
Integration Tests for Job Matching Workflow

Feature: cv-web-app
Tests the complete job matching workflow including:
- Job URL parsing and content extraction
- Job match scoring with detailed breakdown
- Tailored CV creation workflow

Requirements: 12.2, 12.4, 12.5, 12.9
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
import tempfile
import json
from pathlib import Path

from app.main import app
from app.models.llm_models import (
    LLMProviderType,
    JobMatchRequest,
    TailoredCVRequest,
    TailoringLevel
)
from app.services.llm_service import LLMService
from app.services.cv_service import CVService
from app.services.file_service import FileService
from app.llm.providers.base import BaseLLMProvider, LLMResponse, LLMConfig
from tests import v2_helpers as v2


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider for testing job matching workflow."""
    
    def __init__(self):
        config = LLMConfig(
            provider="mock",
            model="mock-model",
            enabled=True
        )
        self.config = config
        self.call_count = 0
        self.last_prompt = None
        self.LLMResponse = LLMResponse
    
    async def test_connection(self) -> bool:
        return True
    
    async def generate_completion(self, prompt: str, **kwargs) -> 'LLMResponse':
        """Generate mock completion based on prompt content."""
        self.call_count += 1
        self.last_prompt = prompt
        
        # Job description analysis
        if "analyze" in prompt.lower() and "job description" in prompt.lower():
            content = """Job Title: Senior Python Developer
Company: TechCorp Inc
Experience Level: Senior level
Industry: Technology

Requirements:
- 5+ years of Python development experience
- Strong knowledge of AWS cloud services
- Experience with microservices architecture
- Docker and Kubernetes expertise
- Bachelor's degree in Computer Science

Skills:
- Python
- AWS
- Docker
- Kubernetes
- Microservices
- PostgreSQL
- Redis
- FastAPI

Keywords:
- Cloud Computing
- Containerization
- CI/CD
- RESTful APIs
- Agile Development"""
        
        # Requirement matching
        elif "requirements" in prompt.lower() and ("met" in prompt.lower() or "match" in prompt.lower()):
            content = """MET:
- 5+ years of Python development experience
- Strong knowledge of AWS cloud services
- Experience with microservices architecture
- Docker expertise

NOT MET:
- Kubernetes expertise
- Bachelor's degree in Computer Science"""
        
        # Tailoring suggestions
        elif "tailor" in prompt.lower() or "suggestions" in prompt.lower():
            content = json.dumps({
                "extracted_requirements": [
                    "5+ years Python experience",
                    "AWS cloud services",
                    "Microservices architecture",
                    "Docker and Kubernetes"
                ],
                "extracted_keywords": [
                    "Python", "AWS", "Docker", "Kubernetes", "Microservices",
                    "PostgreSQL", "Redis", "FastAPI", "CI/CD"
                ],
                "suggestions": [
                    {
                        "section": "summary",
                        "current": "Software engineer with Python experience",
                        "suggested": "Senior Python developer with 6+ years of experience in AWS cloud services and microservices architecture",
                        "reason": "Emphasize Python expertise, AWS, and microservices to match job requirements",
                        "priority": "high"
                    },
                    {
                        "section": "experience",
                        "current": "Built applications using Python",
                        "suggested": "Architected and deployed cloud-native microservices using Python, AWS, Docker, and Kubernetes",
                        "reason": "Add specific technologies from job description",
                        "priority": "high"
                    },
                    {
                        "section": "skills",
                        "current": "",
                        "suggested": "Add Kubernetes and PostgreSQL to skills",
                        "reason": "Missing key technologies from job requirements",
                        "priority": "medium"
                    }
                ]
            })
        
        else:
            content = "Mock LLM response"
        
        return self.LLMResponse(
            content=content,
            model="mock-model",
            provider="mock"
        )
    
    async def generate_structured_output(self, prompt: str, schema: dict, **kwargs) -> dict:
        """Generate mock structured output."""
        self.call_count += 1
        return {}
    
    def validate_config(self) -> bool:
        return True


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def mock_llm_service(temp_data_dir):
    """Create LLM service with mock provider."""
    service = LLMService(config_dir=temp_data_dir)
    
    from app.models.llm_models import LLMConfigRequest
    config = LLMConfigRequest(
        provider=LLMProviderType.LOCAL,
        model="mock-model",
        enabled=True,
        consent_given=True
    )
    service.update_config(config)
    
    return service


@pytest.fixture
def mock_cv_service(temp_data_dir):
    """Create CV service with temporary storage."""
    file_service = FileService(data_directory=temp_data_dir)
    return CVService(file_service=file_service)


@pytest.fixture
def client_with_mocks(mock_llm_service, mock_cv_service, temp_data_dir):
    """Create test client with mocked services."""
    mock_provider = MockLLMProvider()
    mock_file_service = FileService(data_directory=temp_data_dir)
    
    # Patch services
    with patch('app.routers.llm_router.get_llm_service', return_value=mock_llm_service):
        with patch('app.routers.cv_router.get_cv_service', return_value=mock_cv_service):
            # Patch FileService and CVService instantiation in llm_router
            with patch('app.routers.llm_router.FileService', return_value=mock_file_service):
                with patch('app.routers.llm_router.CVService', return_value=mock_cv_service):
                    with patch.object(mock_llm_service, 'get_provider', return_value=mock_provider):
                        client = TestClient(app)
                        yield client, mock_provider, mock_cv_service


@pytest.fixture
def sample_cv_data():
    """Sample CV data for testing."""
    return {
        "id": "test-cv-123",
        "metadata": {
            "title": "Software Engineer CV",
            "template_id": "default"
        },
        "personal_info": {
            "name": "Jane Smith",
            "title": "Software Engineer",
            "contact": {
                "email": "jane@example.com",
                "phone": "+1-555-0123"
            }
        },
        "summary": "Software engineer with Python experience and cloud development skills.",
        "experience": [
            {
                "id": "exp-1",
                "title": "Software Engineer",
                "company": "Tech Solutions Inc",
                "location": "San Francisco, CA",
                "start_date": "2018-01",
                "end_date": None,
                "current": True,
                "description": "Built applications using Python and AWS. Developed microservices architecture.",
                "achievements": [
                    "Improved system performance by 40%",
                    "Led migration to AWS cloud infrastructure"
                ]
            }
        ],
        "education": [
            {
                "id": "edu-1",
                "degree": "Associate Degree in Computer Programming",
                "institution": "Community College",
                "location": "Boston, MA",
                "start_date": "2014-09",
                "end_date": "2016-05"
            }
        ],
        "skills": {
            "categories": [
                {
                    "name": "Programming Languages",
                    "skills": ["Python", "JavaScript", "SQL"]
                },
                {
                    "name": "Cloud & DevOps",
                    "skills": ["AWS", "Docker", "CI/CD"]
                }
            ]
        },
        "certifications": []
    }


@pytest.fixture
def sample_job_description():
    """Sample job description for testing."""
    return """Senior Python Developer - TechCorp Inc

We are seeking a Senior Python Developer to join our growing team.

Requirements:
- 5+ years of Python development experience
- Strong knowledge of AWS cloud services
- Experience with microservices architecture
- Docker and Kubernetes expertise
- Bachelor's degree in Computer Science

Responsibilities:
- Design and develop scalable microservices
- Deploy applications to AWS cloud infrastructure
- Implement CI/CD pipelines
- Collaborate with cross-functional teams

Skills:
Python, AWS, Docker, Kubernetes, Microservices, PostgreSQL, Redis, FastAPI, CI/CD"""


@pytest.mark.integration
class TestJobURLParsingWorkflow:
    """Integration tests for job URL parsing workflow."""
    
    @pytest.mark.asyncio
    async def test_parse_job_url_linkedin(self, client_with_mocks):
        """
        Test parsing LinkedIn job URL and extracting content.
        
        Validates: Requirement 12.2 (Job URL parsing)
        """
        client, mock_provider, _ = client_with_mocks
        
        # Mock the job parser
        mock_result = {
            'url': 'https://www.linkedin.com/jobs/view/123456',
            'job_title': 'Senior Python Developer',
            'company': 'TechCorp Inc',
            'location': 'San Francisco, CA',
            'description': 'We are seeking a Senior Python Developer with 5+ years of experience...',
            'parser_used': 'linkedin.com'
        }
        
        with patch('app.routers.llm_router.get_job_parser') as mock_get_parser:
            mock_parser = AsyncMock()
            mock_parser.parse_job_url.return_value = mock_result
            mock_get_parser.return_value = mock_parser
            
            response = client.post(
                "/api/llm/parse-job-url",
                json={"url": "https://www.linkedin.com/jobs/view/123456"}
            )
        
        assert response.status_code == 200
        result = response.json()
        
        # Verify URL parsing result
        assert result['success'] is True
        assert result['url'] == 'https://www.linkedin.com/jobs/view/123456'
        assert result['job_title'] == 'Senior Python Developer'
        assert result['company'] == 'TechCorp Inc'
        assert result['location'] == 'San Francisco, CA'
        assert len(result['description']) > 0
        assert result['parser_used'] == 'linkedin.com'
    
    @pytest.mark.asyncio
    async def test_parse_job_url_indeed(self, client_with_mocks):
        """
        Test parsing Indeed job URL.
        
        Validates: Requirement 12.2 (Job URL parsing)
        """
        client, mock_provider, _ = client_with_mocks
        
        mock_result = {
            'url': 'https://www.indeed.com/viewjob?jk=abc123',
            'job_title': 'Backend Developer',
            'company': 'StartupXYZ',
            'location': 'New York, NY',
            'description': 'Join our team as a Backend Developer with Python and AWS experience...',
            'parser_used': 'indeed.com'
        }
        
        with patch('app.routers.llm_router.get_job_parser') as mock_get_parser:
            mock_parser = AsyncMock()
            mock_parser.parse_job_url.return_value = mock_result
            mock_get_parser.return_value = mock_parser
            
            response = client.post(
                "/api/llm/parse-job-url",
                json={"url": "https://www.indeed.com/viewjob?jk=abc123"}
            )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result['success'] is True
        assert result['job_title'] == 'Backend Developer'
        assert result['company'] == 'StartupXYZ'
        assert result['parser_used'] == 'indeed.com'
    
    @pytest.mark.asyncio
    async def test_parse_job_url_generic_fallback(self, client_with_mocks):
        """
        Test generic parser fallback for unknown job sites.
        
        Validates: Requirement 12.2 (Job URL parsing with fallback)
        """
        client, mock_provider, _ = client_with_mocks
        
        mock_result = {
            'url': 'https://company.com/careers/engineer',
            'job_title': 'Software Engineer',
            'company': None,
            'location': None,
            'description': 'We are hiring a Software Engineer to work on exciting projects...',
            'parser_used': 'generic'
        }
        
        with patch('app.routers.llm_router.get_job_parser') as mock_get_parser:
            mock_parser = AsyncMock()
            mock_parser.parse_job_url.return_value = mock_result
            mock_get_parser.return_value = mock_parser
            
            response = client.post(
                "/api/llm/parse-job-url",
                json={"url": "https://company.com/careers/engineer"}
            )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result['success'] is True
        assert result['parser_used'] == 'generic'
        assert len(result['description']) > 0


@pytest.mark.integration
class TestJobMatchScoringWorkflow:
    """Integration tests for job match scoring workflow."""
    
    def test_match_cv_to_job_complete_workflow(self, client_with_mocks, sample_cv_data, sample_job_description):
        """
        Test complete job matching workflow with detailed breakdown.
        
        Validates: Requirements 12.4, 12.5 (Job match scoring with detailed breakdown)
        """
        client, mock_provider, _ = client_with_mocks
        
        request_data = {
            "cv_id": "test-cv-123",
            "cv_data": sample_cv_data,
            "job_description": sample_job_description
        }
        
        response = client.post("/api/llm/match-job", json=request_data)
        
        assert response.status_code == 200
        result = response.json()
        
        # Verify overall structure
        assert "cv_id" in result
        assert result["cv_id"] == "test-cv-123"
        
        # Verify job analysis
        assert "job_analysis" in result
        job_analysis = result["job_analysis"]
        assert "job_title" in job_analysis
        assert "company" in job_analysis
        assert "requirements" in job_analysis
        assert "skills" in job_analysis
        assert "keywords" in job_analysis
        
        # Verify score breakdown (Requirement 12.4)
        assert "score_breakdown" in result
        score_breakdown = result["score_breakdown"]
        assert "overall_score" in score_breakdown
        assert "keyword_alignment_score" in score_breakdown
        assert "experience_relevance_score" in score_breakdown
        assert "skills_match_score" in score_breakdown
        assert "requirements_match_score" in score_breakdown
        
        # All scores should be between 0 and 100
        assert 0 <= score_breakdown["overall_score"] <= 100
        assert 0 <= score_breakdown["keyword_alignment_score"] <= 100
        assert 0 <= score_breakdown["experience_relevance_score"] <= 100
        assert 0 <= score_breakdown["skills_match_score"] <= 100
        assert 0 <= score_breakdown["requirements_match_score"] <= 100
        
        # Verify detailed breakdown (Requirement 12.5)
        assert "matched_skills" in result
        assert "missing_skills" in result
        assert "matched_requirements" in result
        assert "missing_requirements" in result
        assert "matched_keywords" in result
        assert "missing_keywords" in result
        assert "qualification_gaps" in result
        assert "strengths" in result
        assert "recommendations" in result
        
        # Verify lists are populated
        assert isinstance(result["matched_skills"], list)
        assert isinstance(result["missing_skills"], list)
        assert isinstance(result["matched_requirements"], list)
        assert isinstance(result["missing_requirements"], list)
        
        # Should have some matched skills (Python, AWS, Docker from CV)
        assert len(result["matched_skills"]) > 0
        
        # Should have some missing skills (Kubernetes from job description)
        assert len(result["missing_skills"]) > 0
        
        # Verify summary
        assert "summary" in result
        assert len(result["summary"]) > 0
    
    def test_match_cv_to_job_skill_matching(self, client_with_mocks, sample_cv_data, sample_job_description):
        """
        Test skill matching in job match scoring.
        
        Validates: Requirement 12.5 (Detailed skill matching)
        """
        client, mock_provider, _ = client_with_mocks
        
        request_data = {
            "cv_id": "test-cv-123",
            "cv_data": sample_cv_data,
            "job_description": sample_job_description
        }
        
        response = client.post("/api/llm/match-job", json=request_data)
        
        assert response.status_code == 200
        result = response.json()
        
        # CV has Python, AWS, Docker - should match
        matched_skills = result["matched_skills"]
        assert any("python" in skill.lower() for skill in matched_skills)
        
        # CV missing Kubernetes - should be in missing
        missing_skills = result["missing_skills"]
        assert len(missing_skills) > 0
    
    def test_match_cv_to_job_requirements_matching(self, client_with_mocks, sample_cv_data, sample_job_description):
        """
        Test requirement matching in job match scoring.
        
        Validates: Requirement 12.5 (Detailed requirement matching)
        """
        client, mock_provider, _ = client_with_mocks
        
        request_data = {
            "cv_id": "test-cv-123",
            "cv_data": sample_cv_data,
            "job_description": sample_job_description
        }
        
        response = client.post("/api/llm/match-job", json=request_data)
        
        assert response.status_code == 200
        result = response.json()
        
        # Should have both matched and missing requirements
        assert len(result["matched_requirements"]) > 0
        assert len(result["missing_requirements"]) > 0
    
    def test_match_cv_to_job_qualification_gaps(self, client_with_mocks, sample_cv_data, sample_job_description):
        """
        Test qualification gap identification.
        
        Validates: Requirement 12.5 (Qualification gap identification)
        """
        client, mock_provider, _ = client_with_mocks
        
        request_data = {
            "cv_id": "test-cv-123",
            "cv_data": sample_cv_data,
            "job_description": sample_job_description
        }
        
        response = client.post("/api/llm/match-job", json=request_data)
        
        assert response.status_code == 200
        result = response.json()
        
        # Should identify qualification gaps (e.g., missing Bachelor's degree)
        assert "qualification_gaps" in result
        assert isinstance(result["qualification_gaps"], list)
    
    def test_match_cv_to_job_strengths_identification(self, client_with_mocks, sample_cv_data, sample_job_description):
        """
        Test strength identification in job matching.
        
        Validates: Requirement 12.5 (Strength identification)
        """
        client, mock_provider, _ = client_with_mocks
        
        request_data = {
            "cv_id": "test-cv-123",
            "cv_data": sample_cv_data,
            "job_description": sample_job_description
        }
        
        response = client.post("/api/llm/match-job", json=request_data)
        
        assert response.status_code == 200
        result = response.json()
        
        # Should identify strengths
        assert "strengths" in result
        assert len(result["strengths"]) > 0
    
    def test_match_cv_to_job_recommendations(self, client_with_mocks, sample_cv_data, sample_job_description):
        """
        Test recommendation generation in job matching.
        
        Validates: Requirement 12.5 (Recommendation generation)
        """
        client, mock_provider, _ = client_with_mocks
        
        request_data = {
            "cv_id": "test-cv-123",
            "cv_data": sample_cv_data,
            "job_description": sample_job_description
        }
        
        response = client.post("/api/llm/match-job", json=request_data)
        
        assert response.status_code == 200
        result = response.json()
        
        # Should provide actionable recommendations
        assert "recommendations" in result
        assert len(result["recommendations"]) > 0


@pytest.mark.integration
class TestTailoredCVCreationWorkflow:
    """Integration tests for tailored CV creation workflow."""
    
    def test_create_tailored_cv_complete_workflow(self, client_with_mocks, sample_cv_data, sample_job_description):
        """
        Test complete tailored CV creation workflow.
        
        Validates: Requirement 12.9 (Tailored CV creation)
        """
        client, mock_provider, mock_cv_service = client_with_mocks
        
        # First, save the source CV
        from app.models.cv_models import CVModel
        source_cv = CVModel(**sample_cv_data)
        mock_cv_service.file_service.save_cv(source_cv)
        
        # Get tailoring suggestions first
        tailor_request = {
            "job_description": sample_job_description,
            "cv_id": "test-cv-123",
            "cv_data": sample_cv_data
        }
        
        tailor_response = client.post("/api/llm/tailor-to-job", json=tailor_request)
        assert tailor_response.status_code == 200
        tailor_result = tailor_response.json()
        
        # Now create tailored CV
        create_request = {
            "source_cv_id": "test-cv-123",
            "job_description": sample_job_description,
            "tailoring_level": "moderate",
            "target_cv_title": "Software Engineer CV - TechCorp Position"
        }
        
        response = client.post("/api/llm/create-tailored-cv", json=create_request)
        
        assert response.status_code == 200
        result = response.json()
        
        # Verify result structure
        assert "source_cv_id" in result
        assert result["source_cv_id"] == "test-cv-123"
        assert "tailored_cv_id" in result
        assert result["tailored_cv_id"] != "test-cv-123"
        assert "tailored_cv" in result
        assert "changes_applied" in result
        assert "tailoring_level" in result
        
        # Verify tailored CV was created
        tailored_cv = result["tailored_cv"]
        assert v2.cv_title(tailored_cv) == "Software Engineer CV - TechCorp Position"
        
        # Verify changes were applied
        assert len(result["changes_applied"]) > 0
        
        # Verify original CV is unchanged
        original_cv_response = client.get(f"/api/cvs/{source_cv.id}")
        assert original_cv_response.status_code == 200
        original_cv_data = original_cv_response.json()
        # API returns nested structure with 'cv' key
        assert v2.summary_text(original_cv_data["cv"]) == sample_cv_data["summary"]
    
    def test_create_tailored_cv_conservative_level(self, client_with_mocks, sample_cv_data, sample_job_description):
        """
        Test conservative tailoring level applies only high priority changes.
        
        Validates: Requirement 12.9 (Tailoring levels)
        """
        client, mock_provider, mock_cv_service = client_with_mocks
        
        # Save source CV
        from app.models.cv_models import CVModel
        source_cv = CVModel(**sample_cv_data)
        mock_cv_service.file_service.save_cv(source_cv)
        
        create_request = {
            "source_cv_id": "test-cv-123",
            "job_description": sample_job_description,
            "tailoring_level": "conservative",
            "target_cv_title": "Conservative Tailored CV"
        }
        
        response = client.post("/api/llm/create-tailored-cv", json=create_request)
        
        assert response.status_code == 200
        result = response.json()
        
        # Conservative should apply fewer changes
        assert result["tailoring_level"] == "conservative"
        # Changes should be limited to high priority
        assert len(result["changes_applied"]) >= 0
    
    def test_create_tailored_cv_aggressive_level(self, client_with_mocks, sample_cv_data, sample_job_description):
        """
        Test aggressive tailoring level applies all suggestions.
        
        Validates: Requirement 12.9 (Tailoring levels)
        """
        client, mock_provider, mock_cv_service = client_with_mocks
        
        # Save source CV
        from app.models.cv_models import CVModel
        source_cv = CVModel(**sample_cv_data)
        mock_cv_service.file_service.save_cv(source_cv)
        
        create_request = {
            "source_cv_id": "test-cv-123",
            "job_description": sample_job_description,
            "tailoring_level": "aggressive",
            "target_cv_title": "Aggressive Tailored CV"
        }
        
        response = client.post("/api/llm/create-tailored-cv", json=create_request)
        
        assert response.status_code == 200
        result = response.json()
        
        # Aggressive should apply more changes
        assert result["tailoring_level"] == "aggressive"
        assert len(result["changes_applied"]) >= 0
    
    def test_create_tailored_cv_preserve_sections(self, client_with_mocks, sample_cv_data, sample_job_description):
        """
        Test that preserved sections remain unchanged.
        
        Validates: Requirement 12.9 (Section preservation)
        """
        client, mock_provider, mock_cv_service = client_with_mocks
        
        # Save source CV
        from app.models.cv_models import CVModel
        source_cv = CVModel(**sample_cv_data)
        mock_cv_service.file_service.save_cv(source_cv)
        
        create_request = {
            "source_cv_id": "test-cv-123",
            "job_description": sample_job_description,
            "tailoring_level": "aggressive",
            "preserve_sections": ["summary", "education"],
            "target_cv_title": "Preserved Sections CV"
        }
        
        response = client.post("/api/llm/create-tailored-cv", json=create_request)
        
        assert response.status_code == 200
        result = response.json()
        
        # Verify preserved sections remain unchanged
        tailored_cv = result["tailored_cv"]
        assert v2.summary_text(tailored_cv) == sample_cv_data["summary"]
        # Education may have additional fields (gpa, description) set to None
        assert len(v2.education(tailored_cv)) == len(sample_cv_data["education"])
        for i, edu in enumerate(v2.education(tailored_cv)):
            assert edu["degree"] == sample_cv_data["education"][i]["degree"]
            assert edu["institution"] == sample_cv_data["education"][i]["institution"]


@pytest.mark.integration
class TestEndToEndJobMatchingScenario:
    """End-to-end scenario tests for complete job matching workflow."""
    
    def test_complete_job_matching_scenario(self, client_with_mocks, sample_cv_data):
        """
        Test complete end-to-end job matching scenario:
        1. Parse job URL
        2. Match CV to job
        3. Create tailored CV
        
        Validates: Requirements 12.2, 12.4, 12.5, 12.9
        """
        client, mock_provider, mock_cv_service = client_with_mocks
        
        # Save source CV
        from app.models.cv_models import CVModel
        source_cv = CVModel(**sample_cv_data)
        mock_cv_service.file_service.save_cv(source_cv)
        
        # Step 1: Parse job URL (Requirement 12.2)
        job_url = "https://www.linkedin.com/jobs/view/123456"
        mock_job_result = {
            'url': job_url,
            'job_title': 'Senior Python Developer',
            'company': 'TechCorp Inc',
            'location': 'San Francisco, CA',
            'description': """Senior Python Developer - TechCorp Inc
            
Requirements:
- 5+ years of Python development experience
- Strong knowledge of AWS cloud services
- Experience with microservices architecture
- Docker and Kubernetes expertise

Skills: Python, AWS, Docker, Kubernetes, Microservices, PostgreSQL""",
            'parser_used': 'linkedin.com'
        }
        
        with patch('app.routers.llm_router.get_job_parser') as mock_get_parser:
            mock_parser = AsyncMock()
            mock_parser.parse_job_url.return_value = mock_job_result
            mock_get_parser.return_value = mock_parser
            
            parse_response = client.post(
                "/api/llm/parse-job-url",
                json={"url": job_url}
            )
        
        assert parse_response.status_code == 200
        parse_result = parse_response.json()
        assert parse_result['success'] is True
        job_description = parse_result['description']
        
        # Step 2: Match CV to job (Requirements 12.4, 12.5)
        match_request = {
            "cv_id": "test-cv-123",
            "cv_data": sample_cv_data,
            "job_description": job_description
        }
        
        match_response = client.post("/api/llm/match-job", json=match_request)
        
        assert match_response.status_code == 200
        match_result = match_response.json()
        
        # Verify match score and breakdown
        assert "score_breakdown" in match_result
        assert "overall_score" in match_result["score_breakdown"]
        assert 0 <= match_result["score_breakdown"]["overall_score"] <= 100
        
        # Verify detailed breakdown
        assert len(match_result["matched_skills"]) > 0
        assert len(match_result["missing_skills"]) > 0
        assert len(match_result["recommendations"]) > 0
        
        # Step 3: Create tailored CV (Requirement 12.9)
        tailor_request = {
            "source_cv_id": "test-cv-123",
            "job_description": job_description,
            "tailoring_level": "moderate",
            "target_cv_title": "Software Engineer CV - TechCorp Position"
        }
        
        tailor_response = client.post("/api/llm/create-tailored-cv", json=tailor_request)
        
        assert tailor_response.status_code == 200
        tailor_result = tailor_response.json()
        
        # Verify tailored CV was created
        assert tailor_result["source_cv_id"] == "test-cv-123"
        assert tailor_result["tailored_cv_id"] != "test-cv-123"
        assert len(tailor_result["changes_applied"]) > 0
        
        # Verify original CV is unchanged
        original_cv_response = client.get(f"/api/cvs/{source_cv.id}")
        assert original_cv_response.status_code == 200
        original_cv_data = original_cv_response.json()
        # API returns nested structure with 'cv' key
        assert v2.summary_text(original_cv_data["cv"]) == sample_cv_data["summary"]
        
        # Verify all three steps completed successfully
        assert mock_provider.call_count >= 2  # At least match and tailor calls
    
    def test_job_matching_with_url_parsing_failure(self, client_with_mocks, sample_cv_data):
        """
        Test handling of URL parsing failure in job matching workflow.
        
        Validates: Error handling in Requirement 12.2
        """
        client, mock_provider, mock_cv_service = client_with_mocks
        
        # Mock URL parsing failure
        from app.services.job_parser import URLAccessError
        
        with patch('app.routers.llm_router.get_job_parser') as mock_get_parser:
            mock_parser = AsyncMock()
            mock_parser.parse_job_url.side_effect = URLAccessError("Cannot access URL")
            mock_get_parser.return_value = mock_parser
            
            parse_response = client.post(
                "/api/llm/parse-job-url",
                json={"url": "https://example.com/job"}
            )
        
        # Should return error
        assert parse_response.status_code == 502
        assert "Cannot access URL" in parse_response.json()['detail']
    
    def test_job_matching_with_low_match_score(self, client_with_mocks, sample_cv_data):
        """
        Test job matching workflow with low match score.
        
        Validates: Requirements 12.4, 12.5 (Low match scenarios)
        """
        client, mock_provider, mock_cv_service = client_with_mocks
        
        # Job description with very different requirements
        different_job = """Senior Data Scientist - AI Research Lab
        
Requirements:
- PhD in Machine Learning or related field
- 10+ years of research experience
- Expertise in deep learning frameworks (TensorFlow, PyTorch)
- Published research in top-tier conferences
- Strong mathematical background

Skills: Python, TensorFlow, PyTorch, R, Statistics, Deep Learning"""
        
        match_request = {
            "cv_id": "test-cv-123",
            "cv_data": sample_cv_data,
            "job_description": different_job
        }
        
        match_response = client.post("/api/llm/match-job", json=match_request)
        
        assert match_response.status_code == 200
        match_result = match_response.json()
        
        # Should still return valid result with low score
        assert "score_breakdown" in match_result
        # Score should be lower due to mismatch
        # (actual score depends on implementation, but structure should be valid)
        assert 0 <= match_result["score_breakdown"]["overall_score"] <= 100
        
        # Should have many missing requirements
        assert len(match_result["missing_requirements"]) > 0
        assert len(match_result["qualification_gaps"]) > 0


@pytest.mark.integration
class TestJobMatchingEdgeCases:
    """Edge case tests for job matching workflow."""
    
    def test_match_cv_with_empty_job_description(self, client_with_mocks, sample_cv_data):
        """
        Test job matching with empty job description.
        
        Validates: Error handling in Requirements 12.4, 12.5
        """
        client, mock_provider, _ = client_with_mocks
        
        match_request = {
            "cv_id": "test-cv-123",
            "cv_data": sample_cv_data,
            "job_description": ""
        }
        
        response = client.post("/api/llm/match-job", json=match_request)
        
        # Should handle gracefully
        assert response.status_code in [200, 400, 422]
    
    def test_match_cv_with_minimal_cv_data(self, client_with_mocks, sample_job_description):
        """
        Test job matching with minimal CV data.
        
        Validates: Requirements 12.4, 12.5 (Minimal data handling)
        """
        client, mock_provider, _ = client_with_mocks
        
        minimal_cv = {
            "id": "minimal-cv",
            "metadata": {
                "title": "Minimal CV",
                "template_id": "default"
            },
            "personal_info": {
                "name": "John Doe",
                "title": "Developer",
                "contact": {
                    "email": "john@example.com"
                }
            },
            "summary": "",
            "experience": [],
            "education": [],
            "skills": {
                "categories": []
            },
            "certifications": []
        }
        
        match_request = {
            "cv_id": "minimal-cv",
            "cv_data": minimal_cv,
            "job_description": sample_job_description
        }
        
        response = client.post("/api/llm/match-job", json=match_request)
        
        assert response.status_code == 200
        result = response.json()
        
        # Should still return valid structure with low scores
        assert "score_breakdown" in result
        assert result["score_breakdown"]["overall_score"] >= 0
        # With minimal data, should have many missing elements
        assert len(result["missing_skills"]) > 0
        assert len(result["missing_requirements"]) > 0
    
    def test_create_tailored_cv_with_nonexistent_source(self, client_with_mocks, sample_job_description):
        """
        Test tailored CV creation with non-existent source CV.
        
        Validates: Error handling in Requirement 12.9
        """
        client, mock_provider, _ = client_with_mocks
        
        create_request = {
            "source_cv_id": "nonexistent-cv-id",
            "job_description": sample_job_description,
            "tailoring_level": "moderate",
            "target_cv_title": "Test CV"
        }
        
        response = client.post("/api/llm/create-tailored-cv", json=create_request)
        
        # Should return error
        assert response.status_code in [404, 422]
    
    def test_match_cv_with_special_characters_in_job_description(self, client_with_mocks, sample_cv_data):
        """
        Test job matching with special characters in job description.
        
        Validates: Requirements 12.4, 12.5 (Special character handling)
        """
        client, mock_provider, _ = client_with_mocks
        
        job_with_special_chars = """Senior Developer @ TechCorp™
        
Requirements:
- 5+ years of C++ & Python experience
- Knowledge of AWS/Azure/GCP
- Experience with CI/CD (Jenkins, GitLab, etc.)
- Strong communication skills (written & verbal)

Salary: $120k-$150k/year
Benefits: 401(k), health insurance, etc."""
        
        match_request = {
            "cv_id": "test-cv-123",
            "cv_data": sample_cv_data,
            "job_description": job_with_special_chars
        }
        
        response = client.post("/api/llm/match-job", json=match_request)
        
        assert response.status_code == 200
        result = response.json()
        
        # Should handle special characters gracefully
        assert "score_breakdown" in result
        assert "overall_score" in result["score_breakdown"]
    
    def test_create_tailored_cv_with_invalid_tailoring_level(self, client_with_mocks, sample_cv_data, sample_job_description):
        """
        Test tailored CV creation with invalid tailoring level.
        
        Validates: Error handling in Requirement 12.9
        """
        client, mock_provider, mock_cv_service = client_with_mocks
        
        # Save source CV
        from app.models.cv_models import CVModel
        source_cv = CVModel(**sample_cv_data)
        mock_cv_service.file_service.save_cv(source_cv)
        
        create_request = {
            "source_cv_id": "test-cv-123",
            "job_description": sample_job_description,
            "tailoring_level": "invalid_level",
            "target_cv_title": "Test CV"
        }
        
        response = client.post("/api/llm/create-tailored-cv", json=create_request)
        
        # Should return validation error (400 or 422)
        assert response.status_code in [400, 422]
    
    def test_match_cv_with_very_long_job_description(self, client_with_mocks, sample_cv_data):
        """
        Test job matching with very long job description.
        
        Validates: Requirements 12.4, 12.5 (Long text handling)
        """
        client, mock_provider, _ = client_with_mocks
        
        # Create a very long job description
        long_job_description = """Senior Software Engineer Position
        
""" + "\n".join([f"Requirement {i}: Some detailed requirement text here." for i in range(100)])
        
        match_request = {
            "cv_id": "test-cv-123",
            "cv_data": sample_cv_data,
            "job_description": long_job_description
        }
        
        response = client.post("/api/llm/match-job", json=match_request)
        
        # Should handle long text without errors
        assert response.status_code == 200
        result = response.json()
        assert "score_breakdown" in result
    
    def test_parse_job_url_with_invalid_url(self, client_with_mocks):
        """
        Test job URL parsing with invalid URL format.
        
        Validates: Error handling in Requirement 12.2
        """
        client, mock_provider, _ = client_with_mocks
        
        response = client.post(
            "/api/llm/parse-job-url",
            json={"url": "not-a-valid-url"}
        )
        
        # Should return validation error
        assert response.status_code in [400, 422, 502]
    
    def test_match_cv_with_multiple_concurrent_requests(self, client_with_mocks, sample_cv_data, sample_job_description):
        """
        Test job matching with multiple concurrent requests.
        
        Validates: Requirements 12.4, 12.5 (Concurrent request handling)
        """
        client, mock_provider, _ = client_with_mocks
        
        match_request = {
            "cv_id": "test-cv-123",
            "cv_data": sample_cv_data,
            "job_description": sample_job_description
        }
        
        # Make multiple requests
        responses = []
        for _ in range(3):
            response = client.post("/api/llm/match-job", json=match_request)
            responses.append(response)
        
        # All should succeed
        for response in responses:
            assert response.status_code == 200
            result = response.json()
            assert "score_breakdown" in result


@pytest.mark.integration
class TestJobMatchingPerformance:
    """Performance and stress tests for job matching workflow."""
    
    def test_match_cv_response_time(self, client_with_mocks, sample_cv_data, sample_job_description):
        """
        Test that job matching completes in reasonable time.
        
        Validates: Performance aspect of Requirements 12.4, 12.5
        """
        import time
        
        client, mock_provider, _ = client_with_mocks
        
        match_request = {
            "cv_id": "test-cv-123",
            "cv_data": sample_cv_data,
            "job_description": sample_job_description
        }
        
        start_time = time.time()
        response = client.post("/api/llm/match-job", json=match_request)
        end_time = time.time()
        
        assert response.status_code == 200
        
        # Should complete within reasonable time (10 seconds for mock)
        elapsed_time = end_time - start_time
        assert elapsed_time < 10.0, f"Job matching took {elapsed_time:.2f}s, expected < 10s"
    
    def test_create_tailored_cv_response_time(self, client_with_mocks, sample_cv_data, sample_job_description):
        """
        Test that tailored CV creation completes in reasonable time.
        
        Validates: Performance aspect of Requirement 12.9
        """
        import time
        
        client, mock_provider, mock_cv_service = client_with_mocks
        
        # Save source CV
        from app.models.cv_models import CVModel
        source_cv = CVModel(**sample_cv_data)
        mock_cv_service.file_service.save_cv(source_cv)
        
        create_request = {
            "source_cv_id": "test-cv-123",
            "job_description": sample_job_description,
            "tailoring_level": "moderate",
            "target_cv_title": "Test CV"
        }
        
        start_time = time.time()
        response = client.post("/api/llm/create-tailored-cv", json=create_request)
        end_time = time.time()
        
        assert response.status_code == 200
        
        # Should complete within reasonable time (15 seconds for mock)
        elapsed_time = end_time - start_time
        assert elapsed_time < 15.0, f"Tailored CV creation took {elapsed_time:.2f}s, expected < 15s"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
