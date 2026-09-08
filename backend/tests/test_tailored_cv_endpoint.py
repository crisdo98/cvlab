"""
Integration tests for the create-tailored-cv endpoint.

Tests the complete workflow of creating a tailored CV through the API endpoint.
"""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import shutil
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.cv_models import (
    CVModel, CVMetadata, PersonalInfo, ContactInfo,
    Experience, Education, SkillCategory, Skills
)
from app.models.llm_models import (
    JobTailoringResult, JobDescriptionAnalysis, TailoringSuggestion,
    RecommendationPriority
)
from app.services.cv_service import CVService
from app.services.file_service import FileService
from tests import v2_helpers as v2


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for test data."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def test_client(temp_data_dir):
    """Create a test client with temporary data directory."""
    # Override the file service to use temp directory
    with patch('app.routers.llm_router.FileService') as mock_file_service_class:
        mock_file_service = FileService(data_directory=temp_data_dir)
        mock_file_service_class.return_value = mock_file_service
        
        client = TestClient(app)
        yield client


@pytest.fixture
def sample_cv(temp_data_dir):
    """Create and save a sample CV."""
    cv = CVModel(
        id="test-cv-123",
        metadata=CVMetadata(
            title="Software Engineer CV",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            template_id="default"
        ),
        personal_info=PersonalInfo(
            name="John Doe",
            title="Software Engineer",
            contact=ContactInfo(
                email="john@example.com",
                phone="+1234567890"
            )
        ),
        summary="Experienced software engineer with 5 years in web development.",
        experience=[
            Experience(
                id="exp1",
                title="Software Engineer",
                company="Tech Corp",
                location="San Francisco, CA",
                start_date="2020-01",
                end_date="2023-12",
                current=False,
                description="Developed web applications using Python and JavaScript.",
                achievements=[
                    "Built scalable REST APIs",
                    "Improved system performance by 30%"
                ]
            )
        ],
        education=[
            Education(
                id="edu1",
                degree="BS Computer Science",
                institution="University of Tech",
                location="Boston, MA",
                start_date="2015-09",
                end_date="2019-05"
            )
        ],
        skills=Skills(
            categories=[
                SkillCategory(
                    name="Programming Languages",
                    skills=["Python", "JavaScript", "Java"]
                )
            ]
        ),
        certifications=[]
    )
    
    # Save CV to temp directory
    file_service = FileService(data_directory=temp_data_dir)
    file_service.save_cv(cv)
    
    return cv


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider."""
    mock_provider = MagicMock()
    mock_provider.generate_completion = AsyncMock()
    return mock_provider


@pytest.fixture
def mock_tailoring_result():
    """Create a mock job tailoring result."""
    return JobTailoringResult(
        cv_id="test-cv-123",
        job_analysis=JobDescriptionAnalysis(
            job_title="Senior Software Engineer",
            company="Tech Company",
            requirements=["5+ years experience", "Cloud experience"],
            skills=["Python", "AWS", "Docker"],
            keywords=["cloud", "microservices", "scalable"]
        ),
        suggestions=[
            TailoringSuggestion(
                section="summary",
                current="Experienced software engineer with 5 years in web development.",
                suggested="Experienced cloud-native software engineer with 5 years specializing in scalable web development.",
                reason="Add cloud and scalability keywords",
                keywords_added=["cloud-native", "scalable"],
                priority=RecommendationPriority.HIGH
            ),
            TailoringSuggestion(
                section="skills",
                current="",
                suggested="Add cloud skills",
                reason="Missing cloud technologies",
                keywords_added=["AWS", "Docker"],
                priority=RecommendationPriority.MEDIUM
            )
        ],
        missing_keywords=["AWS", "Docker", "Kubernetes"],
        matching_keywords=["Python"],
        match_score=65.0,
        summary="Good match with some areas for improvement",
        analyzed_at=datetime.now(),
        model="gpt-4",
        provider="openai"
    )


class TestTailoredCVEndpoint:
    """Test suite for the create-tailored-cv endpoint."""
    
    @pytest.mark.asyncio
    async def test_create_tailored_cv_success(
        self,
        test_client,
        sample_cv,
        mock_llm_provider,
        mock_tailoring_result,
        temp_data_dir
    ):
        """Test successful creation of tailored CV through API endpoint."""
        
        # Mock the LLM provider and optimizer
        with patch('app.routers.llm_router.get_llm_provider') as mock_get_provider, \
             patch('app.routers.llm_router.CVOptimizer') as mock_optimizer_class, \
             patch('app.routers.llm_router.FileService') as mock_file_service_class:
            
            # Setup mocks
            mock_get_provider.return_value = mock_llm_provider
            
            mock_optimizer = MagicMock()
            mock_optimizer.tailor_to_job = AsyncMock(return_value=mock_tailoring_result)
            mock_optimizer_class.return_value = mock_optimizer
            
            # Use real file service with temp directory
            mock_file_service_class.return_value = FileService(data_directory=temp_data_dir)
            
            # Make request
            request_data = {
                "source_cv_id": sample_cv.id,
                "job_description": "Looking for a senior software engineer with cloud experience...",
                "tailoring_level": "moderate",
                "target_cv_title": "Software Engineer CV - Cloud Position"
            }
            
            response = test_client.post("/api/llm/create-tailored-cv", json=request_data)
            
            # Verify response
            assert response.status_code == 200
            data = response.json()
            
            assert data["source_cv_id"] == sample_cv.id
            assert data["tailored_cv_id"] != sample_cv.id
            assert data["tailoring_level"] == "moderate"
            assert "changes_applied" in data
            assert "match_score" in data
            assert "tailored_cv" in data
            
            # Verify tailored CV has the correct title
            assert v2.cv_title(data["tailored_cv"]) == "Software Engineer CV - Cloud Position"
    
    def test_create_tailored_cv_missing_source_cv_id(self, test_client, mock_llm_provider):
        """Test error handling when source_cv_id is missing."""
        
        with patch('app.routers.llm_router.get_llm_provider') as mock_get_provider:
            mock_get_provider.return_value = mock_llm_provider
            
            request_data = {
                "job_description": "Job description...",
                "target_cv_title": "Tailored CV"
            }
            
            response = test_client.post("/api/llm/create-tailored-cv", json=request_data)
            
            assert response.status_code == 400
            assert "source_cv_id is required" in response.json()["detail"]
    
    def test_create_tailored_cv_missing_job_description(self, test_client, mock_llm_provider):
        """Test error handling when job_description is missing."""
        
        with patch('app.routers.llm_router.get_llm_provider') as mock_get_provider:
            mock_get_provider.return_value = mock_llm_provider
            
            request_data = {
                "source_cv_id": "test-cv-123",
                "target_cv_title": "Tailored CV"
            }
            
            response = test_client.post("/api/llm/create-tailored-cv", json=request_data)
            
            assert response.status_code == 400
            assert "job_description is required" in response.json()["detail"]
    
    def test_create_tailored_cv_missing_target_title(self, test_client, mock_llm_provider):
        """Test error handling when target_cv_title is missing."""
        
        with patch('app.routers.llm_router.get_llm_provider') as mock_get_provider:
            mock_get_provider.return_value = mock_llm_provider
            
            request_data = {
                "source_cv_id": "test-cv-123",
                "job_description": "Job description..."
            }
            
            response = test_client.post("/api/llm/create-tailored-cv", json=request_data)
            
            assert response.status_code == 400
            assert "target_cv_title is required" in response.json()["detail"]
    
    def test_create_tailored_cv_invalid_tailoring_level(self, test_client, mock_llm_provider):
        """Test error handling with invalid tailoring level."""
        
        with patch('app.routers.llm_router.get_llm_provider') as mock_get_provider:
            mock_get_provider.return_value = mock_llm_provider
            
            request_data = {
                "source_cv_id": "test-cv-123",
                "job_description": "Job description...",
                "tailoring_level": "invalid_level",
                "target_cv_title": "Tailored CV"
            }
            
            response = test_client.post("/api/llm/create-tailored-cv", json=request_data)
            
            assert response.status_code == 400
            assert "Invalid tailoring_level" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_create_tailored_cv_source_not_found(
        self,
        test_client,
        mock_llm_provider,
        temp_data_dir
    ):
        """Test error handling when source CV doesn't exist."""
        
        with patch('app.routers.llm_router.get_llm_provider') as mock_get_provider, \
             patch('app.routers.llm_router.FileService') as mock_file_service_class:
            
            mock_get_provider.return_value = mock_llm_provider
            mock_file_service_class.return_value = FileService(data_directory=temp_data_dir)
            
            request_data = {
                "source_cv_id": "nonexistent-cv-id",
                "job_description": "Job description...",
                "target_cv_title": "Tailored CV"
            }
            
            response = test_client.post("/api/llm/create-tailored-cv", json=request_data)
            
            assert response.status_code == 404
            assert "Source CV not found" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_create_tailored_cv_with_preserve_sections(
        self,
        test_client,
        sample_cv,
        mock_llm_provider,
        mock_tailoring_result,
        temp_data_dir
    ):
        """Test creating tailored CV with preserved sections."""
        
        with patch('app.routers.llm_router.get_llm_provider') as mock_get_provider, \
             patch('app.routers.llm_router.CVOptimizer') as mock_optimizer_class, \
             patch('app.routers.llm_router.FileService') as mock_file_service_class:
            
            mock_get_provider.return_value = mock_llm_provider
            
            mock_optimizer = MagicMock()
            mock_optimizer.tailor_to_job = AsyncMock(return_value=mock_tailoring_result)
            mock_optimizer_class.return_value = mock_optimizer
            
            mock_file_service_class.return_value = FileService(data_directory=temp_data_dir)
            
            request_data = {
                "source_cv_id": sample_cv.id,
                "job_description": "Job description...",
                "tailoring_level": "aggressive",
                "preserve_sections": ["education", "personal_info"],
                "target_cv_title": "Tailored CV with Preserved Sections"
            }
            
            response = test_client.post("/api/llm/create-tailored-cv", json=request_data)
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify preserved sections weren't modified
            assert len(v2.education(data["tailored_cv"])) == len(sample_cv.education)
            assert v2.full_name(data["tailored_cv"]) == sample_cv.personal_info.name


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
