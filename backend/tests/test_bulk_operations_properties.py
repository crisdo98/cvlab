"""
Property-Based Tests for Bulk Operations

Tests Properties 22-24: Bulk operation correctness properties
Validates: Requirements 10.2, 10.3, 10.5

Ensures that bulk operations maintain correct behavior for:
- Bulk stage change atomicity
- Bulk delete completeness
- Bulk operation cancellation
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime
import tempfile
import shutil
from contextlib import contextmanager

from app.models.application_tracker_models import (
    Application,
    CreateApplicationRequest,
    BulkStageChangeRequest,
    BulkDeleteRequest,
    Stage
)
from app.services.application_tracker_service import ApplicationTrackerService
from app.services.application_tracker_storage import (
    ApplicationTrackerStorage,
    ApplicationNotFoundError
)


@contextmanager
def temp_service():
    """Context manager for temporary service with isolated storage."""
    temp_dir = tempfile.mkdtemp()
    storage = ApplicationTrackerStorage(data_directory=temp_dir)
    service = ApplicationTrackerService(storage=storage, cv_service=None)
    try:
        yield service
    finally:
        shutil.rmtree(temp_dir)


# Hypothesis strategies for generating test data

@st.composite
def valid_application_request_strategy(draw):
    """Generate valid CreateApplicationRequest instances."""
    company_name = draw(st.text(min_size=1, max_size=200))
    position_title = draw(st.text(min_size=1, max_size=200))
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


class TestBulkStageChangeAtomicityProperty:
    """
    Property 22: Bulk Stage Change Atomicity
    
    For any set of application IDs and any target stage, performing a bulk stage
    change should update all specified applications to the new stage, and each
    should have a corresponding history entry created.
    
    Validates: Requirement 10.2
    """
    
    @given(
        requests=st.lists(valid_application_request_strategy(), min_size=2, max_size=10),
        target_stage=st.sampled_from(Stage)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_22_bulk_stage_change_updates_all(self, requests, target_stage):
        """
        Feature: job-application-tracker, Property 22: Bulk Stage Change Atomicity
        
        Bulk stage change should update all specified applications to the new stage.
        
        Validates: Requirement 10.2 - Bulk stage change updates all applications
        """
        # Ensure we have at least 2 applications
        assume(len(requests) >= 2)
        
        with temp_service() as service:
            # Create multiple applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Get application IDs
            app_ids = [app.id for app in created_apps]
            
            # Perform bulk stage change
            bulk_request = BulkStageChangeRequest(
                application_ids=app_ids,
                new_stage=target_stage
            )
            result = service.bulk_change_stage(bulk_request)
            
            # Verify all operations succeeded
            assert len(result.successful) == len(app_ids), \
                f"Expected {len(app_ids)} successful operations but got {len(result.successful)}"
            assert len(result.failed) == 0, \
                f"Expected no failures but got {len(result.failed)}: {result.failed}"
            
            # Verify each application was updated
            for app_id in app_ids:
                updated_app = service.get_application(app_id)
                assert updated_app.stage == target_stage, \
                    f"Application {app_id} stage not updated: expected {target_stage}, got {updated_app.stage}"
    
    @given(
        requests=st.lists(valid_application_request_strategy(), min_size=2, max_size=10),
        target_stage=st.sampled_from(Stage)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_22_bulk_stage_change_creates_history(self, requests, target_stage):
        """
        Feature: job-application-tracker, Property 22: Bulk Stage Change Atomicity
        
        Bulk stage change should create history entries for all applications.
        
        Validates: Requirement 10.2 - History entry creation for bulk operations
        """
        # Ensure we have at least 2 applications
        assume(len(requests) >= 2)
        
        with temp_service() as service:
            # Create multiple applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Get initial history counts
            initial_history_counts = {}
            for app in created_apps:
                history = service.get_history(app.id)
                initial_history_counts[app.id] = len(history)
            
            # Get application IDs
            app_ids = [app.id for app in created_apps]
            
            # Perform bulk stage change
            bulk_request = BulkStageChangeRequest(
                application_ids=app_ids,
                new_stage=target_stage
            )
            service.bulk_change_stage(bulk_request)
            
            # Verify history entry created for each application
            for app_id in app_ids:
                history = service.get_history(app_id)
                expected_count = initial_history_counts[app_id] + 1
                
                assert len(history) == expected_count, \
                    f"Application {app_id} history count incorrect: expected {expected_count}, got {len(history)}"
                
                # Verify the latest history entry has correct stage
                latest_entry = history[-1]
                assert latest_entry.to_stage == target_stage, \
                    f"Latest history entry for {app_id} has wrong to_stage: expected {target_stage}, got {latest_entry.to_stage}"
    
    @given(
        requests=st.lists(valid_application_request_strategy(), min_size=3, max_size=10),
        target_stage=st.sampled_from(Stage)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_22_partial_bulk_stage_change(self, requests, target_stage):
        """
        Feature: job-application-tracker, Property 22: Bulk Stage Change Atomicity
        
        Bulk stage change with some invalid IDs should update valid ones and report failures.
        
        Validates: Requirement 10.2 - Partial success handling
        """
        # Ensure we have at least 3 applications
        assume(len(requests) >= 3)
        
        with temp_service() as service:
            # Create multiple applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Mix valid and invalid IDs
            valid_ids = [app.id for app in created_apps[:2]]
            invalid_ids = ["nonexistent-id-1", "nonexistent-id-2"]
            mixed_ids = valid_ids + invalid_ids
            
            # Perform bulk stage change
            bulk_request = BulkStageChangeRequest(
                application_ids=mixed_ids,
                new_stage=target_stage
            )
            result = service.bulk_change_stage(bulk_request)
            
            # Verify correct number of successes and failures
            assert len(result.successful) == len(valid_ids), \
                f"Expected {len(valid_ids)} successful operations but got {len(result.successful)}"
            assert len(result.failed) == len(invalid_ids), \
                f"Expected {len(invalid_ids)} failures but got {len(result.failed)}"
            
            # Verify valid applications were updated
            for app_id in valid_ids:
                updated_app = service.get_application(app_id)
                assert updated_app.stage == target_stage, \
                    f"Valid application {app_id} was not updated"
            
            # Verify failed IDs are reported
            failed_ids = [failure['id'] for failure in result.failed]
            for invalid_id in invalid_ids:
                assert invalid_id in failed_ids, \
                    f"Invalid ID {invalid_id} not reported in failures"


class TestBulkDeleteCompletenessProperty:
    """
    Property 23: Bulk Delete Completeness
    
    For any set of application IDs, performing a bulk delete should remove all
    specified applications, and none should be retrievable afterward.
    
    Validates: Requirement 10.3
    """
    
    @given(requests=st.lists(valid_application_request_strategy(), min_size=2, max_size=10))
    @settings(max_examples=100, deadline=None)
    def test_property_23_bulk_delete_removes_all(self, requests):
        """
        Feature: job-application-tracker, Property 23: Bulk Delete Completeness
        
        Bulk delete should remove all specified applications.
        
        Validates: Requirement 10.3 - Bulk delete removes all applications
        """
        # Ensure we have at least 2 applications
        assume(len(requests) >= 2)
        
        with temp_service() as service:
            # Create multiple applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Get application IDs
            app_ids = [app.id for app in created_apps]
            
            # Verify all exist before deletion
            for app_id in app_ids:
                app = service.get_application(app_id)
                assert app.id == app_id
            
            # Perform bulk delete
            bulk_request = BulkDeleteRequest(application_ids=app_ids)
            result = service.bulk_delete(bulk_request)
            
            # Verify all operations succeeded
            assert len(result.successful) == len(app_ids), \
                f"Expected {len(app_ids)} successful deletions but got {len(result.successful)}"
            assert len(result.failed) == 0, \
                f"Expected no failures but got {len(result.failed)}: {result.failed}"
            
            # Verify none are retrievable
            for app_id in app_ids:
                with pytest.raises(ApplicationNotFoundError):
                    service.get_application(app_id)
    
    @given(requests=st.lists(valid_application_request_strategy(), min_size=2, max_size=10))
    @settings(max_examples=100, deadline=None)
    def test_property_23_bulk_delete_not_in_list(self, requests):
        """
        Feature: job-application-tracker, Property 23: Bulk Delete Completeness
        
        Deleted applications should not appear in list queries.
        
        Validates: Requirement 10.3 - Deleted applications not in list
        """
        # Ensure we have at least 2 applications
        assume(len(requests) >= 2)
        
        with temp_service() as service:
            # Create multiple applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Get application IDs
            app_ids = [app.id for app in created_apps]
            
            # Verify all appear in list before deletion
            all_apps_before = service.list_applications()
            app_ids_before = [app.id for app in all_apps_before]
            for app_id in app_ids:
                assert app_id in app_ids_before, \
                    f"Application {app_id} not in list before deletion"
            
            # Perform bulk delete
            bulk_request = BulkDeleteRequest(application_ids=app_ids)
            service.bulk_delete(bulk_request)
            
            # Verify none appear in list after deletion
            all_apps_after = service.list_applications()
            app_ids_after = [app.id for app in all_apps_after]
            for app_id in app_ids:
                assert app_id not in app_ids_after, \
                    f"Deleted application {app_id} still appears in list"
    
    @given(
        requests=st.lists(valid_application_request_strategy(), min_size=5, max_size=15)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_23_bulk_delete_doesnt_affect_others(self, requests):
        """
        Feature: job-application-tracker, Property 23: Bulk Delete Completeness
        
        Bulk delete should not affect applications not in the delete list.
        
        Validates: Requirement 10.3 - Isolated bulk deletion
        """
        # Ensure we have at least 5 applications
        assume(len(requests) >= 5)
        
        with temp_service() as service:
            # Create multiple applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Split into delete and keep groups
            delete_count = len(created_apps) // 2
            apps_to_delete = created_apps[:delete_count]
            apps_to_keep = created_apps[delete_count:]
            
            delete_ids = [app.id for app in apps_to_delete]
            keep_ids = [app.id for app in apps_to_keep]
            
            # Perform bulk delete
            bulk_request = BulkDeleteRequest(application_ids=delete_ids)
            service.bulk_delete(bulk_request)
            
            # Verify deleted applications are gone
            for app_id in delete_ids:
                with pytest.raises(ApplicationNotFoundError):
                    service.get_application(app_id)
            
            # Verify kept applications are still retrievable
            for app_id in keep_ids:
                app = service.get_application(app_id)
                assert app.id == app_id, \
                    f"Application {app_id} affected by bulk delete"
            
            # Verify list contains only kept applications
            all_apps = service.list_applications()
            app_ids_in_list = [app.id for app in all_apps]
            
            for app_id in delete_ids:
                assert app_id not in app_ids_in_list, \
                    f"Deleted application {app_id} still in list"
            
            for app_id in keep_ids:
                assert app_id in app_ids_in_list, \
                    f"Kept application {app_id} not in list"
    
    @given(
        requests=st.lists(valid_application_request_strategy(), min_size=3, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_23_partial_bulk_delete(self, requests):
        """
        Feature: job-application-tracker, Property 23: Bulk Delete Completeness
        
        Bulk delete with some invalid IDs should delete valid ones and report failures.
        
        Validates: Requirement 10.3 - Partial success handling
        """
        # Ensure we have at least 3 applications
        assume(len(requests) >= 3)
        
        with temp_service() as service:
            # Create multiple applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Mix valid and invalid IDs
            valid_ids = [app.id for app in created_apps[:2]]
            invalid_ids = ["nonexistent-id-1", "nonexistent-id-2"]
            mixed_ids = valid_ids + invalid_ids
            
            # Perform bulk delete
            bulk_request = BulkDeleteRequest(application_ids=mixed_ids)
            result = service.bulk_delete(bulk_request)
            
            # Verify correct number of successes and failures
            assert len(result.successful) == len(valid_ids), \
                f"Expected {len(valid_ids)} successful deletions but got {len(result.successful)}"
            assert len(result.failed) == len(invalid_ids), \
                f"Expected {len(invalid_ids)} failures but got {len(result.failed)}"
            
            # Verify valid applications were deleted
            for app_id in valid_ids:
                with pytest.raises(ApplicationNotFoundError):
                    service.get_application(app_id)
            
            # Verify failed IDs are reported
            failed_ids = [failure['id'] for failure in result.failed]
            for invalid_id in invalid_ids:
                assert invalid_id in failed_ids, \
                    f"Invalid ID {invalid_id} not reported in failures"


class TestBulkOperationCancellationProperty:
    """
    Property 24: Bulk Operation Cancellation
    
    For any bulk operation that is cancelled before execution, no applications
    should be modified—the system state should remain unchanged.
    
    Note: The API models enforce min_length=1 for application_ids, so empty
    bulk operations are prevented at the validation layer. This property tests
    that when all operations in a bulk request fail, the system state remains
    consistent and no partial modifications occur.
    
    Validates: Requirement 10.5
    """
    
    @given(
        requests=st.lists(valid_application_request_strategy(), min_size=2, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_24_all_invalid_ids_no_modifications(self, requests):
        """
        Feature: job-application-tracker, Property 24: Bulk Operation Cancellation
        
        Bulk stage change with all invalid IDs should not modify any applications.
        
        Validates: Requirement 10.5 - Failed bulk operations leave system unchanged
        """
        # Ensure we have at least 2 applications
        assume(len(requests) >= 2)
        
        with temp_service() as service:
            # Create multiple applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Store original states
            original_states = {}
            for app in created_apps:
                original_states[app.id] = {
                    'stage': app.stage,
                    'updated_at': app.updated_at
                }
            
            # Perform bulk stage change with only invalid IDs
            invalid_ids = ["nonexistent-id-1", "nonexistent-id-2", "nonexistent-id-3"]
            bulk_request = BulkStageChangeRequest(
                application_ids=invalid_ids,
                new_stage=Stage.APPLIED
            )
            result = service.bulk_change_stage(bulk_request)
            
            # Verify no operations succeeded
            assert len(result.successful) == 0, \
                f"Expected 0 successful operations but got {len(result.successful)}"
            assert len(result.failed) == len(invalid_ids), \
                f"Expected {len(invalid_ids)} failures but got {len(result.failed)}"
            
            # Verify all existing applications unchanged
            for app_id, original_state in original_states.items():
                current_app = service.get_application(app_id)
                assert current_app.stage == original_state['stage'], \
                    f"Application {app_id} stage changed despite all operations failing"
    
    @given(requests=st.lists(valid_application_request_strategy(), min_size=2, max_size=10))
    @settings(max_examples=100, deadline=None)
    def test_property_24_all_invalid_delete_no_modifications(self, requests):
        """
        Feature: job-application-tracker, Property 24: Bulk Operation Cancellation
        
        Bulk delete with all invalid IDs should not delete any applications.
        
        Validates: Requirement 10.5 - Failed bulk deletes leave system unchanged
        """
        # Ensure we have at least 2 applications
        assume(len(requests) >= 2)
        
        with temp_service() as service:
            # Create multiple applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Get application IDs
            app_ids = [app.id for app in created_apps]
            
            # Perform bulk delete with only invalid IDs
            invalid_ids = ["nonexistent-id-1", "nonexistent-id-2", "nonexistent-id-3"]
            bulk_request = BulkDeleteRequest(application_ids=invalid_ids)
            result = service.bulk_delete(bulk_request)
            
            # Verify no operations succeeded
            assert len(result.successful) == 0, \
                f"Expected 0 successful deletions but got {len(result.successful)}"
            assert len(result.failed) == len(invalid_ids), \
                f"Expected {len(invalid_ids)} failures but got {len(result.failed)}"
            
            # Verify all applications still exist
            for app_id in app_ids:
                app = service.get_application(app_id)
                assert app.id == app_id, \
                    f"Application {app_id} affected by failed bulk delete"
    
    @given(
        requests=st.lists(valid_application_request_strategy(), min_size=2, max_size=10),
        target_stage=st.sampled_from(Stage)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_24_failed_bulk_operation_partial_state(self, requests, target_stage):
        """
        Feature: job-application-tracker, Property 24: Bulk Operation Cancellation
        
        When bulk operation has failures, successful operations should complete
        and failed ones should leave applications unchanged.
        
        Validates: Requirement 10.5 - Partial failure handling
        """
        # Ensure we have at least 2 applications
        assume(len(requests) >= 2)
        
        with temp_service() as service:
            # Create multiple applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Mix valid and invalid IDs
            valid_ids = [app.id for app in created_apps]
            invalid_ids = ["nonexistent-id-1", "nonexistent-id-2"]
            mixed_ids = valid_ids + invalid_ids
            
            # Perform bulk stage change
            bulk_request = BulkStageChangeRequest(
                application_ids=mixed_ids,
                new_stage=target_stage
            )
            result = service.bulk_change_stage(bulk_request)
            
            # Verify partial success
            assert len(result.successful) == len(valid_ids), \
                "Valid operations should succeed"
            assert len(result.failed) == len(invalid_ids), \
                "Invalid operations should fail"
            
            # Verify successful operations completed
            for app_id in valid_ids:
                app = service.get_application(app_id)
                assert app.stage == target_stage, \
                    f"Valid application {app_id} not updated"
            
            # Verify failed operations reported correctly
            failed_ids = [failure['id'] for failure in result.failed]
            for invalid_id in invalid_ids:
                assert invalid_id in failed_ids, \
                    f"Failed operation for {invalid_id} not reported"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
