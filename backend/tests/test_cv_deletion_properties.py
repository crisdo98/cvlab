"""
Property-based tests for CV deletion functionality.

Feature: cv-web-app, Property 3: CV Deletion Removes All Traces
Validates: Requirements 1.5
"""
import tempfile
import shutil
from pathlib import Path
from typing import List
import uuid

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from app.models.cv_models import (
    CVModel, PersonalInfo, CVMetadata, ContactInfo,
    Experience, Education, SkillCategory, Skills, Certification
)
from app.services.cv_service import CVService, CVNotFoundError
from app.services.file_service import FileService
from tests import v2_helpers as v2


# Test data generators for valid CV data (reused from persistence tests)
@st.composite
def contact_info_strategy(draw):
    """Generate valid ContactInfo data."""
    return ContactInfo(
        address=draw(st.one_of(st.none(), st.text(min_size=5, max_size=200))),
        phone=draw(st.one_of(st.none(), st.text(min_size=5, max_size=20))),
        email=draw(st.one_of(st.none(), st.emails())),
        linkedin=draw(st.one_of(st.none(), st.text(min_size=5, max_size=100))),
        website=draw(st.one_of(st.none(), st.text(min_size=5, max_size=100)))
    )


@st.composite
def personal_info_strategy(draw):
    """Generate valid PersonalInfo data."""
    return PersonalInfo(
        name=draw(st.text(min_size=1, max_size=100)),
        title=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
        contact=draw(contact_info_strategy())
    )


@st.composite
def cv_metadata_strategy(draw):
    """Generate valid CVMetadata data."""
    return CVMetadata(
        title=draw(st.text(min_size=1, max_size=100)),
        template_id=draw(st.text(min_size=1, max_size=50))
    )


@st.composite
def experience_strategy(draw):
    """Generate valid Experience data."""
    current = draw(st.booleans())
    return Experience(
        title=draw(st.text(min_size=1, max_size=100)),
        company=draw(st.text(min_size=1, max_size=100)),
        location=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
        start_date=draw(st.text(min_size=1, max_size=20)),
        end_date=None if current else draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
        current=current,
        description=draw(st.one_of(st.none(), st.text(min_size=10, max_size=500))),
        achievements=draw(st.lists(st.text(min_size=5, max_size=100), min_size=0, max_size=5))
    )


@st.composite
def education_strategy(draw):
    """Generate valid Education data."""
    return Education(
        degree=draw(st.text(min_size=1, max_size=100)),
        institution=draw(st.text(min_size=1, max_size=100)),
        location=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
        start_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
        end_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
        gpa=draw(st.one_of(st.none(), st.text(min_size=1, max_size=10))),
        description=draw(st.one_of(st.none(), st.text(min_size=10, max_size=300)))
    )


@st.composite
def skill_category_strategy(draw):
    """Generate valid SkillCategory data."""
    return SkillCategory(
        name=draw(st.text(min_size=1, max_size=50)),
        skills=draw(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=10))
    )


@st.composite
def skills_strategy(draw):
    """Generate valid Skills data."""
    return Skills(
        categories=draw(st.lists(skill_category_strategy(), min_size=0, max_size=5))
    )


@st.composite
def certification_strategy(draw):
    """Generate valid Certification data."""
    return Certification(
        name=draw(st.text(min_size=1, max_size=100)),
        issuer=draw(st.text(min_size=1, max_size=100)),
        date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
        expiry_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20)))
    )


@st.composite
def cv_model_strategy(draw):
    """Generate valid CVModel data."""
    return CVModel(
        id=str(uuid.uuid4()),
        metadata=draw(cv_metadata_strategy()),
        personal_info=draw(personal_info_strategy()),
        summary=draw(st.one_of(st.none(), st.text(min_size=10, max_size=500))),
        experience=draw(st.lists(experience_strategy(), min_size=0, max_size=3)),
        education=draw(st.lists(education_strategy(), min_size=0, max_size=3)),
        skills=draw(skills_strategy()),
        certifications=draw(st.lists(certification_strategy(), min_size=0, max_size=3))
    )


@pytest.fixture
def temp_data_dir():
    """Fixture providing temporary data directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="cv_deletion_test_")
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


class TestCVDeletionRemovesAllTraces:
    """Property-based tests for CV deletion functionality."""
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cv_deletion_removes_all_traces(self, cv_service, cv_data):
        """
        Property 3: CV Deletion Removes All Traces
        
        For any existing CV, after deletion the CV should not appear in the CV list 
        and should not be retrievable by ID.
        
        **Validates: Requirements 1.5**
        """
        # Step 1: Create and save the CV to ensure it exists
        cv_service.file_service.save_cv(cv_data)
        
        # Step 2: Verify CV exists before deletion
        # Check that CV exists in file system
        assert cv_service.file_service.cv_exists(cv_data.id), "CV should exist before deletion"
        
        # Check that CV can be retrieved
        retrieved_cv = cv_service.file_service.load_cv(cv_data.id)
        assert retrieved_cv.id == cv_data.id, "CV should be retrievable before deletion"
        
        # Check that CV appears in CV list
        cv_list_before = cv_service.list_cvs()
        cv_ids_before = [cv.id for cv in cv_list_before.cvs]
        assert cv_data.id in cv_ids_before, "CV should appear in CV list before deletion"
        
        # Step 3: Delete the CV
        delete_response = cv_service.delete_cv(cv_data.id)
        
        # Verify delete response contains the deleted CV data
        assert delete_response.cv.id == cv_data.id, "Delete response should contain deleted CV data"
        assert delete_response.message is not None, "Delete response should contain success message"
        
        # Step 4: Verify CV no longer exists after deletion
        # Check that CV file no longer exists
        assert not cv_service.file_service.cv_exists(cv_data.id), "CV file should not exist after deletion"
        
        # Check that CV file path does not exist on filesystem
        cv_file_path = cv_service.file_service.get_cv_file_path(cv_data.id)
        assert not cv_file_path.exists(), "CV file path should not exist after deletion"
        
        # Check that CV cannot be retrieved (should raise CVNotFoundError)
        with pytest.raises(CVNotFoundError):
            cv_service.get_cv(cv_data.id)
        
        # Check that CV does not appear in CV list
        cv_list_after = cv_service.list_cvs()
        cv_ids_after = [cv.id for cv in cv_list_after.cvs]
        assert cv_data.id not in cv_ids_after, "CV should not appear in CV list after deletion"
        
        # Verify CV list count decreased by 1
        assert cv_list_after.total == cv_list_before.total - 1, "CV list count should decrease by 1 after deletion"
        
        # Step 5: Verify metadata is cleaned up
        # Check that CV is removed from metadata file
        metadata = cv_service.file_service.get_metadata()
        assert cv_data.id not in metadata, "CV should be removed from metadata after deletion"
    
    @given(cv_data_list=st.lists(cv_model_strategy(), min_size=2, max_size=5))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cv_deletion_only_removes_target_cv(self, cv_service, cv_data_list):
        """
        Test that deleting one CV does not affect other CVs.
        
        **Validates: Requirements 1.5**
        """
        # Step 1: Create multiple CVs
        for cv_data in cv_data_list:
            cv_service.file_service.save_cv(cv_data)
        
        # Step 2: Verify all CVs exist
        initial_cv_list = cv_service.list_cvs()
        initial_cv_ids = [cv.id for cv in initial_cv_list.cvs]
        
        for cv_data in cv_data_list:
            assert cv_data.id in initial_cv_ids, f"CV {cv_data.id} should exist before deletion"
        
        # Step 3: Delete one specific CV (first one)
        target_cv = cv_data_list[0]
        remaining_cvs = cv_data_list[1:]
        
        cv_service.delete_cv(target_cv.id)
        
        # Step 4: Verify only target CV is deleted, others remain
        final_cv_list = cv_service.list_cvs()
        final_cv_ids = [cv.id for cv in final_cv_list.cvs]
        
        # Target CV should be gone
        assert target_cv.id not in final_cv_ids, "Target CV should be deleted"
        
        # All other CVs should still exist
        for remaining_cv in remaining_cvs:
            assert remaining_cv.id in final_cv_ids, f"Remaining CV {remaining_cv.id} should still exist"
            
            # Verify remaining CVs can still be retrieved
            retrieved_response = cv_service.get_cv(remaining_cv.id)
            assert retrieved_response.cv.id == remaining_cv.id, f"Remaining CV {remaining_cv.id} should be retrievable"
        
        # Verify count is correct
        assert final_cv_list.total == initial_cv_list.total - 1, "CV count should decrease by exactly 1"
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cv_deletion_idempotent_behavior(self, cv_service, cv_data):
        """
        Test that attempting to delete a non-existent CV raises appropriate error.
        
        **Validates: Requirements 1.5**
        """
        # Step 1: Ensure CV does not exist
        assert not cv_service.file_service.cv_exists(cv_data.id), "CV should not exist initially"
        
        # Step 2: Attempt to delete non-existent CV
        with pytest.raises(CVNotFoundError) as exc_info:
            cv_service.delete_cv(cv_data.id)
        
        # Step 3: Verify appropriate error message
        error_message = str(exc_info.value)
        assert cv_data.id in error_message, "Error message should contain CV ID"
        assert "not found" in error_message.lower(), "Error message should indicate CV not found"
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cv_deletion_file_system_cleanup(self, cv_service, cv_data):
        """
        Test that CV deletion properly cleans up all file system traces.
        
        **Validates: Requirements 1.5**
        """
        # Step 1: Create CV and verify file system state
        cv_service.file_service.save_cv(cv_data)
        
        cv_file_path = cv_service.file_service.get_cv_file_path(cv_data.id)
        metadata_file_path = cv_service.file_service.metadata_file
        
        # Verify CV file exists
        assert cv_file_path.exists(), "CV file should exist after creation"
        
        # Verify CV is in metadata (if metadata file exists)
        if metadata_file_path.exists():
            metadata_before = cv_service.file_service.get_metadata()
            assert cv_data.id in metadata_before, "CV should be in metadata before deletion"
        
        # Step 2: Delete CV
        cv_service.delete_cv(cv_data.id)
        
        # Step 3: Verify complete file system cleanup
        # CV file should be gone
        assert not cv_file_path.exists(), "CV file should be deleted from file system"
        
        # CV should be removed from metadata
        metadata_after = cv_service.file_service.get_metadata()
        assert cv_data.id not in metadata_after, "CV should be removed from metadata"
        
        # Verify no orphaned files remain
        cv_files = list(cv_service.file_service.cvs_directory.glob(f"{cv_data.id}*"))
        assert len(cv_files) == 0, f"No files should remain for CV {cv_data.id}"
    
    @given(cv_data=cv_model_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cv_deletion_across_service_instances(self, temp_data_dir, cv_data):
        """
        Test that CV deletion is persistent across service instances.
        
        **Validates: Requirements 1.5**
        """
        # Step 1: Create CV using first service instance
        file_service_1 = FileService(data_directory=temp_data_dir)
        cv_service_1 = CVService(file_service=file_service_1)
        
        file_service_1.save_cv(cv_data)
        assert file_service_1.cv_exists(cv_data.id), "CV should exist in first service instance"
        
        # Step 2: Delete CV using first service instance
        cv_service_1.delete_cv(cv_data.id)
        assert not file_service_1.cv_exists(cv_data.id), "CV should be deleted in first service instance"
        
        # Step 3: Verify deletion persists in second service instance
        file_service_2 = FileService(data_directory=temp_data_dir)
        cv_service_2 = CVService(file_service=file_service_2)
        
        # CV should not exist in second service instance
        assert not file_service_2.cv_exists(cv_data.id), "CV should not exist in second service instance"
        
        # Attempting to retrieve should fail
        with pytest.raises(CVNotFoundError):
            cv_service_2.get_cv(cv_data.id)
        
        # CV should not appear in listing
        cv_list = cv_service_2.list_cvs()
        cv_ids = [cv.id for cv in cv_list.cvs]
        assert cv_data.id not in cv_ids, "CV should not appear in listing from second service instance"


# Additional unit tests for specific deletion edge cases
class TestCVDeletionEdgeCases:
    """Unit tests for specific edge cases in CV deletion."""
    
    def test_delete_cv_with_minimal_data(self, cv_service):
        """Test deletion of CV with minimal data."""
        minimal_cv = CVModel(
            metadata=CVMetadata(title="Minimal CV"),
            personal_info=PersonalInfo(name="Test User")
        )
        
        # Create and delete minimal CV
        cv_service.file_service.save_cv(minimal_cv)
        assert cv_service.file_service.cv_exists(minimal_cv.id), "Minimal CV should exist after creation"
        
        delete_response = cv_service.delete_cv(minimal_cv.id)
        
        # Verify deletion
        assert delete_response.cv.id == minimal_cv.id, "Delete response should contain minimal CV data"
        assert not cv_service.file_service.cv_exists(minimal_cv.id), "Minimal CV should be deleted"
    
    def test_delete_cv_with_unicode_content(self, cv_service):
        """Test deletion of CV with Unicode characters."""
        unicode_cv = CVModel(
            metadata=CVMetadata(title="CV with Unicode: 测试 🚀"),
            personal_info=PersonalInfo(
                name="José María García-López",
                title="Développeur Senior"
            )
        )
        
        # Create and delete Unicode CV
        cv_service.file_service.save_cv(unicode_cv)
        assert cv_service.file_service.cv_exists(unicode_cv.id), "Unicode CV should exist after creation"
        
        delete_response = cv_service.delete_cv(unicode_cv.id)
        
        # Verify deletion
        assert v2.cv_title(delete_response.cv) == "CV with Unicode: 测试 🚀", "Delete response should preserve Unicode content"
        assert not cv_service.file_service.cv_exists(unicode_cv.id), "Unicode CV should be deleted"
    
    def test_delete_nonexistent_cv_error_message(self, cv_service):
        """Test that deleting non-existent CV provides clear error message."""
        fake_cv_id = str(uuid.uuid4())
        
        with pytest.raises(CVNotFoundError) as exc_info:
            cv_service.delete_cv(fake_cv_id)
        
        error_message = str(exc_info.value)
        assert fake_cv_id in error_message, "Error message should contain the CV ID"
        assert "not found" in error_message.lower(), "Error message should clearly indicate CV not found"