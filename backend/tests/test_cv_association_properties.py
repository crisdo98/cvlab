"""
Property-Based Tests for CV Association

Tests Properties 9-11, 21: CV association correctness properties
Validates: Requirements 5.1, 5.2, 5.4, 5.5, 8.5

Ensures that CV version associations maintain correct behavior for:
- CV association storage and retrieval
- CV association persistence
- CV association removal
- Referential integrity maintenance
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime
import tempfile
import shutil
from contextlib import contextmanager
from unittest.mock import Mock, MagicMock

from app.models.application_tracker_models import (
    Application,
    CreateApplicationRequest,
    UpdateApplicationRequest,
    Stage
)
from app.services.application_tracker_service import (
    ApplicationTrackerService,
    CVVersionNotFoundError
)
from app.services.application_tracker_storage import ApplicationTrackerStorage
from app.services.cv_service import CVService, CVNotFoundError


@contextmanager
def temp_service_with_cv_mock(cv_exists=True):
    """Context manager for temporary service with mocked CV service."""
    temp_dir = tempfile.mkdtemp()
    storage = ApplicationTrackerStorage(data_directory=temp_dir)
    
    # Create mock CV service
    cv_service = Mock(spec=CVService)
    
    if cv_exists:
        # Mock successful CV retrieval
        cv_service.get_cv.return_value = Mock(id="test-cv-id")
    else:
        # Mock CV not found
        cv_service.get_cv.side_effect = CVNotFoundError("CV not found")
    
    service = ApplicationTrackerService(storage=storage, cv_service=cv_service)
    
    try:
        yield service, cv_service
    finally:
        shutil.rmtree(temp_dir)


@contextmanager
def temp_service_no_cv():
    """Context manager for temporary service without CV service."""
    temp_dir = tempfile.mkdtemp()
    storage = ApplicationTrackerStorage(data_directory=temp_dir)
    service = ApplicationTrackerService(storage=storage, cv_service=None)
    try:
        yield service
    finally:
        shutil.rmtree(temp_dir)


# Hypothesis strategies for generating test data

@st.composite
def valid_cv_id_strategy(draw):
    """Generate valid CV version IDs (UUID format)."""
    import uuid
    return str(uuid.uuid4())


@st.composite
def simple_application_request_strategy(draw):
    """Generate simple CreateApplicationRequest instances for CV association tests."""
    company_name = draw(st.text(min_size=1, max_size=100))
    position_title = draw(st.text(min_size=1, max_size=100))
    stage = draw(st.sampled_from(Stage))
    application_date = draw(st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31)
    ))
    
    return CreateApplicationRequest(
        company_name=company_name,
        position_title=position_title,
        stage=stage,
        application_date=application_date
    )


class TestCVAssociationStorageAndRetrievalProperty:
    """
    Property 9: CV Association Storage and Retrieval
    
    For any application and any valid CV version ID, associating the CV version
    with the application should store the reference, and retrieving the application
    should return the same CV version ID.
    
    Validates: Requirements 5.1, 5.2
    """
    
    @given(
        request=simple_application_request_strategy(),
        cv_id=valid_cv_id_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_9_cv_association_on_creation(self, request, cv_id):
        """
        Feature: job-application-tracker, Property 9: CV Association Storage and Retrieval
        
        Creating an application with a CV version ID should store and retrieve it correctly.
        
        Validates: Requirements 5.1, 5.2 - CV association on creation
        """
        with temp_service_with_cv_mock(cv_exists=True) as (service, cv_service):
            # Create application with CV association
            request.cv_version_id = cv_id
            created = service.create_application(request)
            
            # Verify CV version ID is stored
            assert created.cv_version_id == cv_id, \
                f"CV version ID not stored correctly: expected {cv_id}, got {created.cv_version_id}"
            
            # Retrieve application and verify CV version ID persists
            retrieved = service.get_application(created.id)
            assert retrieved.cv_version_id == cv_id, \
                f"CV version ID not retrieved correctly: expected {cv_id}, got {retrieved.cv_version_id}"
            
            # Verify CV service was called to validate
            cv_service.get_cv.assert_called_with(cv_id)
    
    @given(
        request=simple_application_request_strategy(),
        cv_id=valid_cv_id_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_9_cv_association_via_update(self, request, cv_id):
        """
        Feature: job-application-tracker, Property 9: CV Association Storage and Retrieval
        
        Associating a CV version via update should store and retrieve it correctly.
        
        Validates: Requirements 5.1, 5.2 - CV association via update
        """
        with temp_service_with_cv_mock(cv_exists=True) as (service, cv_service):
            # Create application without CV association
            created = service.create_application(request)
            assert created.cv_version_id is None
            
            # Associate CV version via update
            update_request = UpdateApplicationRequest(cv_version_id=cv_id)
            updated = service.update_application(created.id, update_request)
            
            # Verify CV version ID is stored
            assert updated.cv_version_id == cv_id, \
                f"CV version ID not stored via update: expected {cv_id}, got {updated.cv_version_id}"
            
            # Retrieve application and verify CV version ID persists
            retrieved = service.get_application(created.id)
            assert retrieved.cv_version_id == cv_id, \
                f"CV version ID not persisted after update: expected {cv_id}, got {retrieved.cv_version_id}"
    
    @given(
        request=simple_application_request_strategy(),
        cv_ids=st.lists(valid_cv_id_strategy(), min_size=2, max_size=5, unique=True)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_9_multiple_applications_different_cvs(self, request, cv_ids):
        """
        Feature: job-application-tracker, Property 9: CV Association Storage and Retrieval
        
        Multiple applications can have different CV associations.
        
        Validates: Requirements 5.1, 5.2 - Multiple CV associations
        """
        # Ensure we have at least 2 different CV IDs
        assume(len(cv_ids) >= 2)
        
        with temp_service_with_cv_mock(cv_exists=True) as (service, cv_service):
            created_apps = []
            
            # Create applications with different CV associations
            for cv_id in cv_ids:
                app_request = CreateApplicationRequest(
                    company_name=request.company_name,
                    position_title=request.position_title,
                    stage=request.stage,
                    application_date=request.application_date,
                    cv_version_id=cv_id
                )
                app = service.create_application(app_request)
                created_apps.append((app.id, cv_id))
            
            # Verify each application has correct CV association
            for app_id, expected_cv_id in created_apps:
                retrieved = service.get_application(app_id)
                assert retrieved.cv_version_id == expected_cv_id, \
                    f"Application {app_id} has wrong CV ID: expected {expected_cv_id}, got {retrieved.cv_version_id}"
    
    @given(
        request=simple_application_request_strategy(),
        cv_id=valid_cv_id_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_9_cv_association_without_cv_service(self, request, cv_id):
        """
        Feature: job-application-tracker, Property 9: CV Association Storage and Retrieval
        
        CV association should work even without CV service (validation skipped).
        
        Validates: Requirements 5.1, 5.2 - CV association without validation
        """
        with temp_service_no_cv() as service:
            # Create application with CV association (no validation)
            request.cv_version_id = cv_id
            created = service.create_application(request)
            
            # Verify CV version ID is stored
            assert created.cv_version_id == cv_id, \
                f"CV version ID not stored without CV service: expected {cv_id}, got {created.cv_version_id}"
            
            # Retrieve and verify
            retrieved = service.get_application(created.id)
            assert retrieved.cv_version_id == cv_id, \
                f"CV version ID not retrieved without CV service"


class TestCVAssociationPersistenceProperty:
    """
    Property 10: CV Association Persistence
    
    For any application with an associated CV version, the association should
    remain intact even if the CV is modified in the CV management system
    (referential integrity).
    
    Validates: Requirement 5.4
    """
    
    @given(
        request=simple_application_request_strategy(),
        cv_id=valid_cv_id_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_10_cv_association_persists_across_updates(self, request, cv_id):
        """
        Feature: job-application-tracker, Property 10: CV Association Persistence
        
        CV association should persist across application updates.
        
        Validates: Requirement 5.4 - Association persistence
        """
        with temp_service_with_cv_mock(cv_exists=True) as (service, cv_service):
            # Create application with CV association
            request.cv_version_id = cv_id
            created = service.create_application(request)
            
            # Perform multiple updates to other fields
            for i in range(3):
                update_request = UpdateApplicationRequest(
                    notes=f"Update {i}",
                    recruiter_name=f"Recruiter {i}"
                )
                updated = service.update_application(created.id, update_request)
                
                # Verify CV association is preserved
                assert updated.cv_version_id == cv_id, \
                    f"CV association lost after update {i}: expected {cv_id}, got {updated.cv_version_id}"
            
            # Final retrieval check
            final = service.get_application(created.id)
            assert final.cv_version_id == cv_id, \
                f"CV association not persisted: expected {cv_id}, got {final.cv_version_id}"
    
    @given(
        request=simple_application_request_strategy(),
        cv_id=valid_cv_id_strategy(),
        stages=st.lists(st.sampled_from(Stage), min_size=2, max_size=5)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_10_cv_association_persists_across_stage_changes(
        self,
        request,
        cv_id,
        stages
    ):
        """
        Feature: job-application-tracker, Property 10: CV Association Persistence
        
        CV association should persist across stage transitions.
        
        Validates: Requirement 5.4 - Association persistence during stage changes
        """
        # Ensure we have at least 2 stage changes
        assume(len(stages) >= 2)
        
        with temp_service_with_cv_mock(cv_exists=True) as (service, cv_service):
            # Create application with CV association
            request.cv_version_id = cv_id
            created = service.create_application(request)
            
            # Perform stage transitions
            from app.models.application_tracker_models import StageChangeRequest
            for new_stage in stages:
                stage_request = StageChangeRequest(new_stage=new_stage)
                updated = service.change_stage(created.id, stage_request)
                
                # Verify CV association is preserved
                assert updated.cv_version_id == cv_id, \
                    f"CV association lost after stage change to {new_stage}"
            
            # Final retrieval check
            final = service.get_application(created.id)
            assert final.cv_version_id == cv_id, \
                f"CV association not persisted after stage changes"
    
    @given(
        request=simple_application_request_strategy(),
        cv_id=valid_cv_id_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_10_cv_reference_maintained_independently(self, request, cv_id):
        """
        Feature: job-application-tracker, Property 10: CV Association Persistence
        
        CV reference in application is independent of CV system state.
        
        Validates: Requirement 5.4 - Referential integrity independence
        """
        with temp_service_with_cv_mock(cv_exists=True) as (service, cv_service):
            # Create application with CV association
            request.cv_version_id = cv_id
            created = service.create_application(request)
            
            # Simulate CV being modified (mock returns different data)
            cv_service.get_cv.return_value = Mock(id=cv_id, modified=True)
            
            # Retrieve application - CV reference should be unchanged
            retrieved = service.get_application(created.id)
            assert retrieved.cv_version_id == cv_id, \
                "CV reference changed when CV was modified"
            
            # Simulate CV service error
            cv_service.get_cv.side_effect = Exception("CV service error")
            
            # Application should still be retrievable with CV reference intact
            retrieved_again = service.get_application(created.id)
            assert retrieved_again.cv_version_id == cv_id, \
                "CV reference lost when CV service had error"


class TestCVAssociationRemovalProperty:
    """
    Property 11: CV Association Removal
    
    For any application with an associated CV version, removing the CV association
    should clear the cv_version_id field while preserving all other application data.
    
    Validates: Requirement 5.5
    """
    
    @given(
        request=simple_application_request_strategy(),
        cv_id=valid_cv_id_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_11_cv_association_removal_preserves_data(self, request, cv_id):
        """
        Feature: job-application-tracker, Property 11: CV Association Removal
        
        Removing CV association should clear cv_version_id but preserve other data.
        
        Validates: Requirement 5.5 - CV association removal
        """
        with temp_service_with_cv_mock(cv_exists=True) as (service, cv_service):
            # Create application with CV association and other data
            request.cv_version_id = cv_id
            request.notes = "Important notes"
            request.recruiter_name = "John Doe"
            request.recruiter_email = "john@example.com"
            
            created = service.create_application(request)
            
            # Store original data for comparison
            original_id = created.id
            original_company = created.company_name
            original_position = created.position_title
            original_stage = created.stage
            original_notes = created.notes
            original_recruiter = created.recruiter_name
            original_email = created.recruiter_email
            
            # Remove CV association by setting to None
            update_request = UpdateApplicationRequest(cv_version_id=None)
            updated = service.update_application(created.id, update_request)
            
            # Verify CV association is removed
            assert updated.cv_version_id is None, \
                f"CV association not removed: {updated.cv_version_id}"
            
            # Verify all other data is preserved
            assert updated.id == original_id, "ID changed"
            assert updated.company_name == original_company, "Company name changed"
            assert updated.position_title == original_position, "Position title changed"
            assert updated.stage == original_stage, "Stage changed"
            assert updated.notes == original_notes, "Notes changed"
            assert updated.recruiter_name == original_recruiter, "Recruiter name changed"
            assert updated.recruiter_email == original_email, "Recruiter email changed"
            
            # Verify removal persists
            retrieved = service.get_application(created.id)
            assert retrieved.cv_version_id is None, \
                "CV association removal not persisted"
    
    @given(
        request=simple_application_request_strategy(),
        cv_id1=valid_cv_id_strategy(),
        cv_id2=valid_cv_id_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_11_cv_association_replacement(self, request, cv_id1, cv_id2):
        """
        Feature: job-application-tracker, Property 11: CV Association Removal
        
        Replacing CV association should update to new CV ID.
        
        Validates: Requirement 5.5 - CV association replacement
        """
        # Ensure we have two different CV IDs
        assume(cv_id1 != cv_id2)
        
        with temp_service_with_cv_mock(cv_exists=True) as (service, cv_service):
            # Create application with first CV association
            request.cv_version_id = cv_id1
            created = service.create_application(request)
            
            assert created.cv_version_id == cv_id1, \
                "Initial CV association not set"
            
            # Replace with second CV association
            update_request = UpdateApplicationRequest(cv_version_id=cv_id2)
            updated = service.update_application(created.id, update_request)
            
            # Verify CV association is replaced
            assert updated.cv_version_id == cv_id2, \
                f"CV association not replaced: expected {cv_id2}, got {updated.cv_version_id}"
            
            # Verify replacement persists
            retrieved = service.get_application(created.id)
            assert retrieved.cv_version_id == cv_id2, \
                "CV association replacement not persisted"
    
    @given(
        request=simple_application_request_strategy(),
        cv_id=valid_cv_id_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_11_cv_removal_and_re_association(self, request, cv_id):
        """
        Feature: job-application-tracker, Property 11: CV Association Removal
        
        CV can be removed and then re-associated.
        
        Validates: Requirement 5.5 - CV removal and re-association
        """
        with temp_service_with_cv_mock(cv_exists=True) as (service, cv_service):
            # Create application with CV association
            request.cv_version_id = cv_id
            created = service.create_application(request)
            
            # Remove CV association
            update_request = UpdateApplicationRequest(cv_version_id=None)
            updated = service.update_application(created.id, update_request)
            assert updated.cv_version_id is None, "CV not removed"
            
            # Re-associate same CV
            update_request2 = UpdateApplicationRequest(cv_version_id=cv_id)
            updated2 = service.update_application(created.id, update_request2)
            
            # Verify CV is re-associated
            assert updated2.cv_version_id == cv_id, \
                f"CV not re-associated: expected {cv_id}, got {updated2.cv_version_id}"
            
            # Verify re-association persists
            retrieved = service.get_application(created.id)
            assert retrieved.cv_version_id == cv_id, \
                "CV re-association not persisted"


class TestReferentialIntegrityMaintenanceProperty:
    """
    Property 21: Referential Integrity Maintenance
    
    For any application with a CV version reference, the system should maintain
    the reference validity, and attempting to associate a non-existent CV version
    should fail with an error.
    
    Validates: Requirement 8.5
    """
    
    @given(
        request=simple_application_request_strategy(),
        cv_id=valid_cv_id_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_21_invalid_cv_rejected_on_creation(self, request, cv_id):
        """
        Feature: job-application-tracker, Property 21: Referential Integrity Maintenance
        
        Creating application with non-existent CV should fail.
        
        Validates: Requirement 8.5 - Referential integrity on creation
        """
        with temp_service_with_cv_mock(cv_exists=False) as (service, cv_service):
            # Attempt to create application with non-existent CV
            request.cv_version_id = cv_id
            
            # Should raise CVVersionNotFoundError
            with pytest.raises(CVVersionNotFoundError) as exc_info:
                service.create_application(request)
            
            # Verify error message contains CV ID
            assert cv_id in str(exc_info.value), \
                f"Error message doesn't mention CV ID: {exc_info.value}"
            
            # Verify CV service was called to validate
            cv_service.get_cv.assert_called_with(cv_id)
    
    @given(
        request=simple_application_request_strategy(),
        valid_cv_id=valid_cv_id_strategy(),
        invalid_cv_id=valid_cv_id_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_21_invalid_cv_rejected_on_update(
        self,
        request,
        valid_cv_id,
        invalid_cv_id
    ):
        """
        Feature: job-application-tracker, Property 21: Referential Integrity Maintenance
        
        Updating application with non-existent CV should fail.
        
        Validates: Requirement 8.5 - Referential integrity on update
        """
        # Ensure we have different CV IDs
        assume(valid_cv_id != invalid_cv_id)
        
        with temp_service_with_cv_mock(cv_exists=True) as (service, cv_service):
            # Create application with valid CV
            request.cv_version_id = valid_cv_id
            created = service.create_application(request)
            
            # Mock CV service to reject the invalid CV
            cv_service.get_cv.side_effect = lambda cv_id: (
                Mock(id=cv_id) if cv_id == valid_cv_id else (_ for _ in ()).throw(CVNotFoundError("CV not found"))
            )
            
            # Attempt to update with non-existent CV
            update_request = UpdateApplicationRequest(cv_version_id=invalid_cv_id)
            
            # Should raise CVVersionNotFoundError
            with pytest.raises(CVVersionNotFoundError):
                service.update_application(created.id, update_request)
            
            # Verify original CV association is preserved
            retrieved = service.get_application(created.id)
            assert retrieved.cv_version_id == valid_cv_id, \
                "Original CV association was modified despite error"
    
    @given(
        request=simple_application_request_strategy(),
        cv_id=valid_cv_id_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_21_valid_cv_accepted(self, request, cv_id):
        """
        Feature: job-application-tracker, Property 21: Referential Integrity Maintenance
        
        Valid CV associations should be accepted.
        
        Validates: Requirement 8.5 - Valid CV acceptance
        """
        with temp_service_with_cv_mock(cv_exists=True) as (service, cv_service):
            # Create application with valid CV
            request.cv_version_id = cv_id
            created = service.create_application(request)
            
            # Should succeed without error
            assert created.cv_version_id == cv_id, \
                "Valid CV association not stored"
            
            # Verify CV service was called to validate
            cv_service.get_cv.assert_called_with(cv_id)
    
    @given(
        request=simple_application_request_strategy(),
        cv_ids=st.lists(valid_cv_id_strategy(), min_size=2, max_size=5, unique=True)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_21_validation_per_application(self, request, cv_ids):
        """
        Feature: job-application-tracker, Property 21: Referential Integrity Maintenance
        
        Each application's CV association is validated independently.
        
        Validates: Requirement 8.5 - Independent validation
        """
        # Ensure we have at least 2 CV IDs
        assume(len(cv_ids) >= 2)
        
        with temp_service_with_cv_mock(cv_exists=True) as (service, cv_service):
            # Create applications with different CV associations
            for cv_id in cv_ids:
                app_request = CreateApplicationRequest(
                    company_name=request.company_name,
                    position_title=request.position_title,
                    stage=request.stage,
                    application_date=request.application_date,
                    cv_version_id=cv_id
                )
                created = service.create_application(app_request)
                
                # Verify each CV was validated
                assert created.cv_version_id == cv_id
            
            # Verify CV service was called for each CV ID
            assert cv_service.get_cv.call_count == len(cv_ids), \
                f"CV service not called for all CVs: expected {len(cv_ids)} calls, got {cv_service.get_cv.call_count}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
