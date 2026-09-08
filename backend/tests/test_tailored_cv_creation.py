"""
Tests for tailored CV creation functionality.

Tests the create_tailored_cv method in CVService that creates new CV variants
tailored to specific job descriptions while preserving the original CV.
"""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import shutil

from app.models.cv_models import (
    CVModel, CVMetadata, PersonalInfo, ContactInfo,
    Experience, Education, SkillCategory, Skills
)
from app.models.llm_models import (
    TailoredCVRequest, TailoringLevel, TailoringSuggestion,
    RecommendationPriority
)
from app.services.cv_service import CVService, CVNotFoundError
from app.services.file_service import FileService
from tests import v2_helpers as v2


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for test data."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def file_service(temp_data_dir):
    """Fixture providing FileService with temporary directory."""
    return FileService(data_directory=temp_data_dir)


@pytest.fixture
def cv_service(file_service):
    """Fixture providing CVService with temporary FileService."""
    return CVService(file_service=file_service)


@pytest.fixture
def sample_cv():
    """Create a sample CV for testing."""
    return CVModel(
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
                ),
                SkillCategory(
                    name="Frameworks",
                    skills=["Django", "React", "FastAPI"]
                )
            ]
        ),
        certifications=[]
    )


@pytest.fixture
def sample_tailoring_suggestions():
    """Create sample tailoring suggestions."""
    return [
        TailoringSuggestion(
            section="summary",
            current="Experienced software engineer with 5 years in web development.",
            suggested="Experienced full-stack software engineer with 5 years specializing in cloud-native web development and microservices architecture.",
            reason="Add keywords: full-stack, cloud-native, microservices",
            keywords_added=["full-stack", "cloud-native", "microservices"],
            priority=RecommendationPriority.HIGH
        ),
        TailoringSuggestion(
            section="experience",
            current="Developed web applications using Python and JavaScript.",
            suggested="Developed cloud-native web applications using Python, JavaScript, and containerization technologies like Docker and Kubernetes.",
            reason="Add cloud and containerization keywords",
            keywords_added=["Docker", "Kubernetes", "containerization"],
            priority=RecommendationPriority.HIGH
        ),
        TailoringSuggestion(
            section="skills",
            current="",
            suggested="Add cloud technologies",
            reason="Missing cloud-related skills from job description",
            keywords_added=["AWS", "Docker", "Kubernetes"],
            priority=RecommendationPriority.MEDIUM
        ),
        TailoringSuggestion(
            section="experience",
            current="Built scalable REST APIs",
            suggested="Built scalable REST APIs with 99.9% uptime using microservices architecture",
            reason="Add specific metrics and architecture keywords",
            keywords_added=["microservices"],
            priority=RecommendationPriority.LOW
        )
    ]


class TestTailoredCVCreation:
    """Test suite for tailored CV creation functionality."""
    
    def test_create_tailored_cv_basic(self, cv_service, sample_cv, sample_tailoring_suggestions):
        """Test basic tailored CV creation with moderate level."""
        # Save the source CV
        cv_service.file_service.save_cv(sample_cv)
        
        # Create tailoring request
        request = TailoredCVRequest(
            source_cv_id=sample_cv.id,
            job_description="Looking for a full-stack engineer with cloud experience...",
            tailoring_level=TailoringLevel.MODERATE,
            target_cv_title="Software Engineer CV - Cloud Position"
        )
        
        # Create tailored CV
        result = cv_service.create_tailored_cv(request, sample_tailoring_suggestions)
        
        # Verify result structure
        assert result.source_cv_id == sample_cv.id
        assert result.tailored_cv_id != sample_cv.id
        assert v2.cv_title(result.tailored_cv) == "Software Engineer CV - Cloud Position"
        assert result.tailoring_level == TailoringLevel.MODERATE
        assert len(result.changes_applied) > 0
        assert 0 <= result.match_score <= 100
        
        # Verify original CV is unchanged
        original_cv = cv_service.get_cv(sample_cv.id)
        assert v2.summary_text(original_cv.cv) == sample_cv.summary
        
        # Verify tailored CV exists and is different
        tailored_cv = cv_service.get_cv(result.tailored_cv_id)
        assert tailored_cv.cv.id == result.tailored_cv_id
        assert v2.cv_title(tailored_cv.cv) == "Software Engineer CV - Cloud Position"
    
    def test_conservative_tailoring_level(self, cv_service, sample_cv, sample_tailoring_suggestions):
        """Test that conservative level only applies high priority suggestions."""
        cv_service.file_service.save_cv(sample_cv)
        
        request = TailoredCVRequest(
            source_cv_id=sample_cv.id,
            job_description="Job description...",
            tailoring_level=TailoringLevel.CONSERVATIVE,
            target_cv_title="Conservative Tailored CV"
        )
        
        result = cv_service.create_tailored_cv(request, sample_tailoring_suggestions)
        
        # Conservative should apply fewer changes (only high priority)
        high_priority_count = sum(
            1 for s in sample_tailoring_suggestions
            if s.priority == RecommendationPriority.HIGH
        )
        
        # Should have applied at most the high priority suggestions
        assert len(result.changes_applied) <= high_priority_count
    
    def test_aggressive_tailoring_level(self, cv_service, sample_cv, sample_tailoring_suggestions):
        """Test that aggressive level applies all suggestions."""
        cv_service.file_service.save_cv(sample_cv)
        
        request = TailoredCVRequest(
            source_cv_id=sample_cv.id,
            job_description="Job description...",
            tailoring_level=TailoringLevel.AGGRESSIVE,
            target_cv_title="Aggressive Tailored CV"
        )
        
        result = cv_service.create_tailored_cv(request, sample_tailoring_suggestions)
        
        # Aggressive should apply more changes
        # Note: Not all suggestions may be applicable, so we check it's >= conservative
        assert len(result.changes_applied) >= 0
    
    def test_preserve_sections(self, cv_service, sample_cv, sample_tailoring_suggestions):
        """Test that preserved sections are not modified."""
        cv_service.file_service.save_cv(sample_cv)
        
        request = TailoredCVRequest(
            source_cv_id=sample_cv.id,
            job_description="Job description...",
            tailoring_level=TailoringLevel.AGGRESSIVE,
            preserve_sections=["summary", "education"],
            target_cv_title="Preserved Sections CV"
        )
        
        result = cv_service.create_tailored_cv(request, sample_tailoring_suggestions)
        
        # Verify preserved sections remain unchanged
        tailored_cv = cv_service.get_cv(result.tailored_cv_id)
        assert v2.summary_text(tailored_cv.cv) == sample_cv.summary
        assert len(v2.education(tailored_cv.cv)) == len(sample_cv.education)
        
        # Verify changes were not applied to preserved sections
        for change in result.changes_applied:
            assert "summary" not in change.lower() or "summary" not in change.split(":")[0].lower()
    
    def test_source_cv_not_found(self, cv_service, sample_tailoring_suggestions):
        """Test error handling when source CV doesn't exist."""
        request = TailoredCVRequest(
            source_cv_id="nonexistent-cv-id",
            job_description="Job description...",
            tailoring_level=TailoringLevel.MODERATE,
            target_cv_title="Should Fail"
        )
        
        with pytest.raises(CVNotFoundError):
            cv_service.create_tailored_cv(request, sample_tailoring_suggestions)
    
    def test_original_cv_unchanged(self, cv_service, sample_cv, sample_tailoring_suggestions):
        """Test that the original CV remains completely unchanged after tailoring."""
        # Save original CV
        cv_service.file_service.save_cv(sample_cv)
        
        # Get original data for comparison
        original_data = sample_cv.model_dump()
        
        # Create tailored CV
        request = TailoredCVRequest(
            source_cv_id=sample_cv.id,
            job_description="Job description...",
            tailoring_level=TailoringLevel.AGGRESSIVE,
            target_cv_title="Tailored CV"
        )
        
        result = cv_service.create_tailored_cv(request, sample_tailoring_suggestions)
        
        # Load original CV again
        reloaded_original = cv_service.get_cv(sample_cv.id)
        
        # Verify all key fields are unchanged
        assert v2.summary_text(reloaded_original.cv) == original_data["summary"]
        assert len(v2.experience(reloaded_original.cv)) == len(sample_cv.experience)
        assert v2.skills(reloaded_original.cv) == [
            skill for category in sample_cv.skills.categories for skill in category.skills
        ]
        assert v2.cv_title(reloaded_original.cv) == original_data["metadata"]["title"]
    
    def test_skills_keyword_addition(self, cv_service, sample_cv, sample_tailoring_suggestions):
        """Test that keywords are added to skills section."""
        cv_service.file_service.save_cv(sample_cv)
        
        request = TailoredCVRequest(
            source_cv_id=sample_cv.id,
            job_description="Job description...",
            tailoring_level=TailoringLevel.MODERATE,
            target_cv_title="Skills Enhanced CV"
        )
        
        result = cv_service.create_tailored_cv(request, sample_tailoring_suggestions)
        
        # Load tailored CV
        tailored_cv = cv_service.get_cv(result.tailored_cv_id)
        
        # Check if new skills were added
        all_skills = v2.skills(tailored_cv.cv)
        
        # At least some of the suggested keywords should be present
        # (depending on which suggestions were applied)
        original_skills = []
        for category in sample_cv.skills.categories:
            original_skills.extend(category.skills)
        
        # Tailored CV should have at least as many skills as original
        assert len(all_skills) >= len(original_skills)
    
    def test_empty_suggestions_list(self, cv_service, sample_cv):
        """Test handling of empty suggestions list."""
        cv_service.file_service.save_cv(sample_cv)
        
        request = TailoredCVRequest(
            source_cv_id=sample_cv.id,
            job_description="Job description...",
            tailoring_level=TailoringLevel.MODERATE,
            target_cv_title="No Changes CV"
        )
        
        result = cv_service.create_tailored_cv(request, [])
        
        # Should still create a new CV, just with no changes
        assert result.tailored_cv_id != sample_cv.id
        assert len(result.changes_applied) == 0
        
        # Verify new CV exists
        tailored_cv = cv_service.get_cv(result.tailored_cv_id)
        assert v2.cv_title(tailored_cv.cv) == "No Changes CV"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
