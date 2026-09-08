"""
Property-Based Tests for Service Layer Operations

Tests Properties 2-8: Service layer correctness properties
Validates: Requirements 1.2, 1.4, 1.5, 3.1, 3.2, 9.1, 9.2, 9.3, 9.4, 9.5

Ensures that service layer operations maintain correct behavior for:
- Unique application identifiers
- Identity preservation during updates
- Complete deletion
- Stage transition history
- History chronological ordering
- History persistence across updates
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
import tempfile
import shutil
from contextlib import contextmanager

from app.models.application_tracker_models import (
    Application,
    CreateApplicationRequest,
    UpdateApplicationRequest,
    StageChangeRequest,
    Interview,
    Stage
)
from app.services.application_tracker_service import ApplicationTrackerService
from app.services.application_tracker_storage import ApplicationTrackerStorage


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
def valid_email_strategy(draw):
    """Generate valid email addresses."""
    username = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'), 
        whitelist_characters='._-'
    )))
    domain = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='-'
    )))
    tld = draw(st.sampled_from(['com', 'org', 'net', 'edu', 'io']))
    return f"{username}@{domain}.{tld}"


@st.composite
def valid_url_strategy(draw):
    """Generate valid HTTP/HTTPS URLs."""
    protocol = draw(st.sampled_from(['http', 'https']))
    domain = draw(st.text(min_size=1, max_size=30, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='-'
    )))
    tld = draw(st.sampled_from(['com', 'org', 'net', 'io', 'co']))
    path = draw(st.one_of(
        st.none(),
        st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),
            whitelist_characters='/-_'
        ))
    ))
    
    url = f"{protocol}://{domain}.{tld}"
    if path:
        url += f"/{path}"
    return url


@st.composite
def valid_interview_strategy(draw):
    """Generate valid Interview instances."""
    interview_date = draw(st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31)
    ))
    interview_type = draw(st.sampled_from(['phone', 'video', 'onsite', 'technical', 'behavioral']))
    meeting_link = draw(st.one_of(st.none(), valid_url_strategy()))
    notes = draw(st.one_of(st.none(), st.text(min_size=0, max_size=500)))
    interviewer_name = draw(st.one_of(st.none(), st.text(min_size=1, max_size=100)))
    
    return Interview(
        date=interview_date,
        type=interview_type,
        meeting_link=meeting_link,
        notes=notes,
        interviewer_name=interviewer_name
    )


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
    
    job_description_url = draw(st.one_of(st.none(), valid_url_strategy()))
    application_deadline = draw(st.one_of(
        st.none(),
        st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31))
    ))
    
    recruiter_name = draw(st.one_of(st.none(), st.text(min_size=1, max_size=100)))
    recruiter_email = draw(st.one_of(st.none(), valid_email_strategy()))
    recruiter_phone = draw(st.one_of(st.none(), st.text(min_size=5, max_size=20)))
    hiring_manager_name = draw(st.one_of(st.none(), st.text(min_size=1, max_size=100)))
    
    interviews = draw(st.lists(valid_interview_strategy(), min_size=0, max_size=5))
    
    notes = draw(st.one_of(st.none(), st.text(min_size=0, max_size=1000)))
    tasks = draw(st.lists(st.text(min_size=1, max_size=200), min_size=0, max_size=10))
    
    feedback = draw(st.one_of(st.none(), st.text(min_size=0, max_size=1000)))
    outcome = draw(st.one_of(st.none(), st.text(min_size=0, max_size=500)))
    
    cv_version_id = draw(st.one_of(st.none(), st.text(min_size=1, max_size=100)))
    
    follow_up_date = draw(st.one_of(
        st.none(),
        st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31))
    ))
    
    return CreateApplicationRequest(
        company_name=company_name,
        position_title=position_title,
        stage=stage,
        application_date=application_date,
        job_description_url=job_description_url,
        application_deadline=application_deadline,
        recruiter_name=recruiter_name,
        recruiter_email=recruiter_email,
        recruiter_phone=recruiter_phone,
        hiring_manager_name=hiring_manager_name,
        interviews=interviews,
        notes=notes,
        tasks=tasks,
        feedback=feedback,
        outcome=outcome,
        cv_version_id=cv_version_id,
        follow_up_date=follow_up_date
    )


class TestUniqueApplicationIdentifiersProperty:
    """
    Property 2: Unique Application Identifiers
    
    For any set of created applications, all application IDs must be unique—
    no two applications should share the same identifier.
    
    Validates: Requirement 1.4
    """
    
    @given(requests=st.lists(valid_application_request_strategy(), min_size=2, max_size=20))
    @settings(max_examples=100, deadline=None)
    def test_property_2_unique_application_identifiers(self, requests):
        """
        Feature: job-application-tracker, Property 2: Unique Application Identifiers
        
        For any set of created applications, all application IDs must be unique.
        
        Validates: Requirement 1.4 - Unique identifier assignment
        """
        # Ensure we have at least 2 applications
        assume(len(requests) >= 2)
        
        with temp_service() as service:
            created_apps = []
            
            # Create multiple applications
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Extract all IDs
            app_ids = [app.id for app in created_apps]
            
            # Verify all IDs are unique
            assert len(app_ids) == len(set(app_ids)), \
                f"Duplicate IDs found: {len(app_ids)} applications but only {len(set(app_ids))} unique IDs"
            
            # Verify each ID is not None and is a string
            for app_id in app_ids:
                assert app_id is not None, "Application ID is None"
                assert isinstance(app_id, str), f"Application ID is not a string: {type(app_id)}"
                assert len(app_id) > 0, "Application ID is empty string"
    
    @given(
        request1=valid_application_request_strategy(),
        request2=valid_application_request_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_2_different_apps_different_ids(self, request1, request2):
        """
        Feature: job-application-tracker, Property 2: Unique Application Identifiers
        
        Creating two applications should result in different IDs.
        
        Validates: Requirement 1.4 - ID uniqueness across creations
        """
        with temp_service() as service:
            app1 = service.create_application(request1)
            app2 = service.create_application(request2)
            
            # Verify IDs are different
            assert app1.id != app2.id, \
                f"Two different applications have the same ID: {app1.id}"
    
    @given(request=valid_application_request_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_2_id_format_validity(self, request):
        """
        Feature: job-application-tracker, Property 2: Unique Application Identifiers
        
        Generated IDs should be valid UUID format.
        
        Validates: Requirement 1.4 - ID format validity
        """
        with temp_service() as service:
            app = service.create_application(request)
            
            # Verify ID is a valid UUID format (contains hyphens, correct length)
            assert app.id is not None
            assert isinstance(app.id, str)
            # UUID format: 8-4-4-4-12 characters
            parts = app.id.split('-')
            assert len(parts) == 5, f"ID doesn't have UUID format: {app.id}"


class TestApplicationUpdatePreservesIdentityProperty:
    """
    Property 3: Application Update Preserves Identity
    
    For any application and any valid update data, updating the application should
    preserve its ID and created_at timestamp while updating the updated_at timestamp
    to be later than the previous value.
    
    Validates: Requirement 1.2
    """
    
    @given(
        create_request=valid_application_request_strategy(),
        update_company=st.text(min_size=1, max_size=200),
        update_position=st.text(min_size=1, max_size=200)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_3_update_preserves_id_and_created_at(
        self,
        create_request,
        update_company,
        update_position
    ):
        """
        Feature: job-application-tracker, Property 3: Application Update Preserves Identity
        
        Updating an application should preserve its ID and created_at timestamp.
        
        Validates: Requirement 1.2 - Identity preservation during updates
        """
        with temp_service() as service:
            # Create application
            created = service.create_application(create_request)
            original_id = created.id
            original_created_at = created.created_at
            original_updated_at = created.updated_at
            
            # Update application
            update_request = UpdateApplicationRequest(
                company_name=update_company,
                position_title=update_position
            )
            updated = service.update_application(created.id, update_request)
            
            # Verify ID is preserved
            assert updated.id == original_id, \
                f"ID changed during update: {original_id} -> {updated.id}"
            
            # Verify created_at is preserved
            assert updated.created_at == original_created_at, \
                f"created_at changed during update: {original_created_at} -> {updated.created_at}"
            
            # Verify updated_at is updated (should be later or equal)
            assert updated.updated_at >= original_updated_at, \
                f"updated_at not updated: {original_updated_at} -> {updated.updated_at}"
    
    @given(
        create_request=valid_application_request_strategy(),
        notes=st.text(min_size=0, max_size=1000)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_3_multiple_updates_preserve_identity(self, create_request, notes):
        """
        Feature: job-application-tracker, Property 3: Application Update Preserves Identity
        
        Multiple sequential updates should preserve ID and created_at.
        
        Validates: Requirement 1.2 - Identity preservation across multiple updates
        """
        with temp_service() as service:
            # Create application
            created = service.create_application(create_request)
            original_id = created.id
            original_created_at = created.created_at
            
            # Perform multiple updates
            for i in range(3):
                update_request = UpdateApplicationRequest(
                    notes=f"{notes} - Update {i}"
                )
                updated = service.update_application(created.id, update_request)
                
                # Verify identity preserved after each update
                assert updated.id == original_id, \
                    f"ID changed during update {i}: {original_id} -> {updated.id}"
                assert updated.created_at == original_created_at, \
                    f"created_at changed during update {i}"
    
    @given(create_request=valid_application_request_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_3_updated_at_increases(self, create_request):
        """
        Feature: job-application-tracker, Property 3: Application Update Preserves Identity
        
        The updated_at timestamp should increase with each update.
        
        Validates: Requirement 1.2 - Modification timestamp tracking
        """
        with temp_service() as service:
            # Create application
            created = service.create_application(create_request)
            previous_updated_at = created.updated_at
            
            # Perform updates and verify timestamp increases
            for i in range(3):
                update_request = UpdateApplicationRequest(
                    notes=f"Update {i}"
                )
                updated = service.update_application(created.id, update_request)
                
                # Verify updated_at is later than or equal to previous
                assert updated.updated_at >= previous_updated_at, \
                    f"updated_at decreased: {previous_updated_at} -> {updated.updated_at}"
                
                previous_updated_at = updated.updated_at


class TestApplicationDeletionCompletenessProperty:
    """
    Property 4: Application Deletion Completeness
    
    For any application, after deleting it, attempting to retrieve that application
    by ID should fail with a not-found error, and the application should not appear
    in any list queries.
    
    Validates: Requirement 1.5
    """
    
    @given(request=valid_application_request_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_4_deleted_app_not_retrievable(self, request):
        """
        Feature: job-application-tracker, Property 4: Application Deletion Completeness
        
        After deleting an application, it should not be retrievable by ID.
        
        Validates: Requirement 1.5 - Complete deletion
        """
        with temp_service() as service:
            # Create application
            created = service.create_application(request)
            app_id = created.id
            
            # Verify it exists
            retrieved = service.get_application(app_id)
            assert retrieved.id == app_id
            
            # Delete application
            service.delete_application(app_id)
            
            # Verify it's not retrievable
            from app.services.application_tracker_storage import ApplicationNotFoundError
            with pytest.raises(ApplicationNotFoundError):
                service.get_application(app_id)
    
    @given(request=valid_application_request_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_4_deleted_app_not_in_list(self, request):
        """
        Feature: job-application-tracker, Property 4: Application Deletion Completeness
        
        After deleting an application, it should not appear in list queries.
        
        Validates: Requirement 1.5 - Deletion from list operations
        """
        with temp_service() as service:
            # Create application
            created = service.create_application(request)
            app_id = created.id
            
            # Verify it appears in list
            all_apps = service.list_applications()
            app_ids = [app.id for app in all_apps]
            assert app_id in app_ids
            
            # Delete application
            service.delete_application(app_id)
            
            # Verify it doesn't appear in list
            all_apps_after = service.list_applications()
            app_ids_after = [app.id for app in all_apps_after]
            assert app_id not in app_ids_after, \
                "Deleted application still appears in list"
    
    @given(requests=st.lists(valid_application_request_strategy(), min_size=3, max_size=10))
    @settings(max_examples=100, deadline=None)
    def test_property_4_deletion_doesnt_affect_others(self, requests):
        """
        Feature: job-application-tracker, Property 4: Application Deletion Completeness
        
        Deleting one application should not affect other applications.
        
        Validates: Requirement 1.5 - Isolated deletion
        """
        # Ensure we have at least 3 applications
        assume(len(requests) >= 3)
        
        with temp_service() as service:
            # Create multiple applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Delete the middle application
            middle_index = len(created_apps) // 2
            deleted_id = created_apps[middle_index].id
            service.delete_application(deleted_id)
            
            # Verify other applications are still retrievable
            for i, app in enumerate(created_apps):
                if i != middle_index:
                    retrieved = service.get_application(app.id)
                    assert retrieved.id == app.id, \
                        f"Application {app.id} affected by deletion of {deleted_id}"
            
            # Verify list contains all except deleted
            all_apps = service.list_applications()
            app_ids = [app.id for app in all_apps]
            
            assert deleted_id not in app_ids, "Deleted application in list"
            assert len(app_ids) == len(created_apps) - 1, \
                f"Expected {len(created_apps) - 1} applications but got {len(app_ids)}"


class TestStageTransitionCreatesHistoryProperty:
    """
    Property 5: Stage Transition Creates History
    
    For any application and any valid stage transition, changing the application's
    stage should create a history entry recording the previous stage, new stage,
    and a timestamp, and this entry should be retrievable in the application's history.
    
    Validates: Requirements 3.1, 3.2, 9.1
    """
    
    @given(
        request=valid_application_request_strategy(),
        new_stage=st.sampled_from(Stage)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_5_stage_change_creates_history(self, request, new_stage):
        """
        Feature: job-application-tracker, Property 5: Stage Transition Creates History
        
        Changing an application's stage should create a history entry.
        
        Validates: Requirements 3.1, 3.2, 9.1 - History creation on stage change
        """
        with temp_service() as service:
            # Create application
            created = service.create_application(request)
            original_stage = created.stage
            
            # Get initial history (should have creation entry)
            initial_history = service.get_history(created.id)
            initial_count = len(initial_history)
            
            # Change stage
            stage_request = StageChangeRequest(new_stage=new_stage)
            updated = service.change_stage(created.id, stage_request)
            
            # Get updated history
            updated_history = service.get_history(created.id)
            
            # Verify history entry was created
            assert len(updated_history) == initial_count + 1, \
                f"Expected {initial_count + 1} history entries but got {len(updated_history)}"
            
            # Verify the new history entry has correct data
            latest_entry = updated_history[-1]  # Last entry should be the newest
            assert latest_entry.application_id == created.id, \
                "History entry has wrong application ID"
            assert latest_entry.from_stage == original_stage, \
                f"History entry from_stage incorrect: expected {original_stage}, got {latest_entry.from_stage}"
            assert latest_entry.to_stage == new_stage, \
                f"History entry to_stage incorrect: expected {new_stage}, got {latest_entry.to_stage}"
            assert latest_entry.timestamp is not None, \
                "History entry timestamp is None"
    
    @given(
        request=valid_application_request_strategy(),
        stages=st.lists(st.sampled_from(Stage), min_size=2, max_size=5)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_5_multiple_transitions_create_multiple_entries(self, request, stages):
        """
        Feature: job-application-tracker, Property 5: Stage Transition Creates History
        
        Multiple stage transitions should create multiple history entries.
        
        Validates: Requirements 3.1, 3.2, 9.1 - Multiple history entries
        """
        # Ensure we have at least 2 stage transitions
        assume(len(stages) >= 2)
        
        with temp_service() as service:
            # Create application
            created = service.create_application(request)
            
            # Get initial history count
            initial_history = service.get_history(created.id)
            initial_count = len(initial_history)
            
            # Perform multiple stage transitions
            for new_stage in stages:
                stage_request = StageChangeRequest(new_stage=new_stage)
                service.change_stage(created.id, stage_request)
            
            # Get final history
            final_history = service.get_history(created.id)
            
            # Verify correct number of entries
            expected_count = initial_count + len(stages)
            assert len(final_history) == expected_count, \
                f"Expected {expected_count} history entries but got {len(final_history)}"
    
    @given(
        request=valid_application_request_strategy(),
        new_stage=st.sampled_from(Stage),
        notes=st.text(min_size=0, max_size=500)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_5_history_entry_includes_notes(self, request, new_stage, notes):
        """
        Feature: job-application-tracker, Property 5: Stage Transition Creates History
        
        History entries should include optional notes if provided.
        
        Validates: Requirements 3.2, 9.1 - History entry completeness
        """
        with temp_service() as service:
            # Create application
            created = service.create_application(request)
            
            # Change stage with notes
            stage_request = StageChangeRequest(new_stage=new_stage, notes=notes)
            service.change_stage(created.id, stage_request)
            
            # Get history
            history = service.get_history(created.id)
            
            # Find the stage change entry (last one)
            latest_entry = history[-1]
            
            # Verify notes are stored
            assert latest_entry.notes == notes, \
                f"History entry notes incorrect: expected '{notes}', got '{latest_entry.notes}'"


class TestInitialApplicationHasHistoryEntryProperty:
    """
    Property 6: Initial Application Has History Entry
    
    For any newly created application, the application should have exactly one
    history entry with from_stage as null, to_stage matching the initial stage,
    and a timestamp matching the creation time.
    
    Validates: Requirement 9.4
    """
    
    @given(request=valid_application_request_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_6_initial_history_entry_exists(self, request):
        """
        Feature: job-application-tracker, Property 6: Initial Application Has History Entry
        
        A newly created application should have exactly one initial history entry.
        
        Validates: Requirement 9.4 - Initial history entry creation
        """
        with temp_service() as service:
            # Create application
            created = service.create_application(request)
            
            # Get history
            history = service.get_history(created.id)
            
            # Verify exactly one entry exists
            assert len(history) == 1, \
                f"Expected exactly 1 history entry for new application but got {len(history)}"
            
            # Verify the entry has correct properties
            entry = history[0]
            assert entry.application_id == created.id, \
                "History entry has wrong application ID"
            assert entry.from_stage is None, \
                f"Initial history entry should have from_stage=None, got {entry.from_stage}"
            assert entry.to_stage == request.stage, \
                f"Initial history entry to_stage should be {request.stage}, got {entry.to_stage}"
            assert entry.timestamp is not None, \
                "History entry timestamp is None"
    
    @given(request=valid_application_request_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_6_initial_history_timestamp_matches_creation(self, request):
        """
        Feature: job-application-tracker, Property 6: Initial Application Has History Entry
        
        The initial history entry timestamp should match the creation time.
        
        Validates: Requirement 9.4 - Timestamp accuracy
        """
        with temp_service() as service:
            # Create application
            created = service.create_application(request)
            
            # Get history
            history = service.get_history(created.id)
            entry = history[0]
            
            # Verify timestamp is close to created_at (within 1 second tolerance)
            time_diff = abs((entry.timestamp - created.created_at).total_seconds())
            assert time_diff < 1.0, \
                f"History timestamp differs from created_at by {time_diff} seconds"
    
    @given(requests=st.lists(valid_application_request_strategy(), min_size=1, max_size=10))
    @settings(max_examples=100, deadline=None)
    def test_property_6_each_application_has_initial_history(self, requests):
        """
        Feature: job-application-tracker, Property 6: Initial Application Has History Entry
        
        Every created application should have its own initial history entry.
        
        Validates: Requirement 9.4 - Consistent history initialization
        """
        # Ensure we have at least one application
        assume(len(requests) > 0)
        
        with temp_service() as service:
            # Create multiple applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Verify each has initial history
            for app in created_apps:
                history = service.get_history(app.id)
                assert len(history) >= 1, \
                    f"Application {app.id} has no history entries"
                
                # Verify first entry is initial entry
                first_entry = history[0]
                assert first_entry.from_stage is None, \
                    f"First history entry for {app.id} should have from_stage=None"
                assert first_entry.to_stage == app.stage, \
                    f"First history entry for {app.id} should have to_stage={app.stage}"


class TestHistoryChronologicalOrderingProperty:
    """
    Property 7: History Chronological Ordering
    
    For any application with multiple stage transitions, retrieving the status
    history should return entries in chronological order (earliest to latest)
    based on timestamps.
    
    Validates: Requirements 9.2, 9.5
    """
    
    @given(
        request=valid_application_request_strategy(),
        stages=st.lists(st.sampled_from(Stage), min_size=3, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_7_history_chronological_order(self, request, stages):
        """
        Feature: job-application-tracker, Property 7: History Chronological Ordering
        
        History entries should be returned in chronological order.
        
        Validates: Requirements 9.2, 9.5 - Chronological ordering
        """
        # Ensure we have at least 3 stage transitions
        assume(len(stages) >= 3)
        
        with temp_service() as service:
            # Create application
            created = service.create_application(request)
            
            # Perform multiple stage transitions
            for new_stage in stages:
                stage_request = StageChangeRequest(new_stage=new_stage)
                service.change_stage(created.id, stage_request)
            
            # Get history
            history = service.get_history(created.id)
            
            # Verify entries are in chronological order
            for i in range(len(history) - 1):
                current_timestamp = history[i].timestamp
                next_timestamp = history[i + 1].timestamp
                
                assert current_timestamp <= next_timestamp, \
                    f"History not in chronological order: entry {i} timestamp {current_timestamp} " \
                    f"is after entry {i+1} timestamp {next_timestamp}"
    
    @given(
        request=valid_application_request_strategy(),
        stages=st.lists(st.sampled_from(Stage), min_size=2, max_size=5)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_7_timestamps_increase(self, request, stages):
        """
        Feature: job-application-tracker, Property 7: History Chronological Ordering
        
        Timestamps should increase (or stay equal) through history.
        
        Validates: Requirements 9.2, 9.5 - Timestamp ordering
        """
        # Ensure we have at least 2 stage transitions
        assume(len(stages) >= 2)
        
        with temp_service() as service:
            # Create application
            created = service.create_application(request)
            
            # Perform stage transitions
            for new_stage in stages:
                stage_request = StageChangeRequest(new_stage=new_stage)
                service.change_stage(created.id, stage_request)
            
            # Get history
            history = service.get_history(created.id)
            
            # Extract timestamps
            timestamps = [entry.timestamp for entry in history]
            
            # Verify timestamps are non-decreasing
            for i in range(len(timestamps) - 1):
                assert timestamps[i] <= timestamps[i + 1], \
                    f"Timestamp at index {i} is greater than timestamp at index {i+1}"
    
    @given(
        request=valid_application_request_strategy(),
        stages=st.lists(st.sampled_from(Stage), min_size=2, max_size=5)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_7_first_entry_is_creation(self, request, stages):
        """
        Feature: job-application-tracker, Property 7: History Chronological Ordering
        
        The first entry in history should always be the creation entry.
        
        Validates: Requirements 9.2, 9.5 - Creation entry ordering
        """
        # Ensure we have at least 2 stage transitions
        assume(len(stages) >= 2)
        
        with temp_service() as service:
            # Create application
            created = service.create_application(request)
            creation_time = created.created_at
            
            # Perform stage transitions
            for new_stage in stages:
                stage_request = StageChangeRequest(new_stage=new_stage)
                service.change_stage(created.id, stage_request)
            
            # Get history
            history = service.get_history(created.id)
            
            # Verify first entry is the creation entry
            first_entry = history[0]
            assert first_entry.from_stage is None, \
                "First history entry should be creation entry with from_stage=None"
            
            # Verify first entry has earliest timestamp
            for entry in history[1:]:
                assert first_entry.timestamp <= entry.timestamp, \
                    "Creation entry timestamp is not the earliest"


class TestHistoryPersistenceAcrossUpdatesProperty:
    """
    Property 8: History Persistence Across Updates
    
    For any application with existing history, updating any application fields
    (except stage) should preserve all existing history entries unchanged.
    
    Validates: Requirement 9.3
    """
    
    @given(
        request=valid_application_request_strategy(),
        initial_stage_changes=st.lists(st.sampled_from(Stage), min_size=2, max_size=5),
        update_company=st.text(min_size=1, max_size=200),
        update_notes=st.text(min_size=0, max_size=1000)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_8_history_preserved_on_update(
        self,
        request,
        initial_stage_changes,
        update_company,
        update_notes
    ):
        """
        Feature: job-application-tracker, Property 8: History Persistence Across Updates
        
        Updating application fields should preserve existing history.
        
        Validates: Requirement 9.3 - History preservation during updates
        """
        # Ensure we have at least 2 stage changes
        assume(len(initial_stage_changes) >= 2)
        
        with temp_service() as service:
            # Create application
            created = service.create_application(request)
            
            # Perform stage transitions to build history
            for new_stage in initial_stage_changes:
                stage_request = StageChangeRequest(new_stage=new_stage)
                service.change_stage(created.id, stage_request)
            
            # Get history before update
            history_before = service.get_history(created.id)
            history_count_before = len(history_before)
            
            # Store history entry IDs and data
            history_ids_before = [entry.id for entry in history_before]
            history_data_before = [
                (entry.from_stage, entry.to_stage, entry.timestamp)
                for entry in history_before
            ]
            
            # Update application (non-stage fields)
            update_request = UpdateApplicationRequest(
                company_name=update_company,
                notes=update_notes
            )
            service.update_application(created.id, update_request)
            
            # Get history after update
            history_after = service.get_history(created.id)
            
            # Verify history count unchanged
            assert len(history_after) == history_count_before, \
                f"History count changed: {history_count_before} -> {len(history_after)}"
            
            # Verify all history entry IDs are preserved
            history_ids_after = [entry.id for entry in history_after]
            assert history_ids_before == history_ids_after, \
                "History entry IDs changed after update"
            
            # Verify history data is unchanged
            history_data_after = [
                (entry.from_stage, entry.to_stage, entry.timestamp)
                for entry in history_after
            ]
            assert history_data_before == history_data_after, \
                "History entry data changed after update"
    
    @given(
        request=valid_application_request_strategy(),
        stages=st.lists(st.sampled_from(Stage), min_size=1, max_size=3)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_8_multiple_updates_preserve_history(self, request, stages):
        """
        Feature: job-application-tracker, Property 8: History Persistence Across Updates
        
        Multiple updates should preserve history across all updates.
        
        Validates: Requirement 9.3 - History preservation across multiple updates
        """
        # Ensure we have at least 1 stage change
        assume(len(stages) >= 1)
        
        with temp_service() as service:
            # Create application
            created = service.create_application(request)
            
            # Build initial history
            for new_stage in stages:
                stage_request = StageChangeRequest(new_stage=new_stage)
                service.change_stage(created.id, stage_request)
            
            # Get initial history
            initial_history = service.get_history(created.id)
            initial_count = len(initial_history)
            
            # Perform multiple non-stage updates
            for i in range(3):
                update_request = UpdateApplicationRequest(
                    notes=f"Update {i}"
                )
                service.update_application(created.id, update_request)
                
                # Verify history unchanged after each update
                current_history = service.get_history(created.id)
                assert len(current_history) == initial_count, \
                    f"History count changed after update {i}: {initial_count} -> {len(current_history)}"
    
    @given(
        request=valid_application_request_strategy(),
        stage=st.sampled_from(Stage),
        update_fields=st.lists(
            st.sampled_from(['recruiter_name', 'recruiter_email', 'notes', 'feedback']),
            min_size=1,
            max_size=4,
            unique=True
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_8_various_field_updates_preserve_history(
        self,
        request,
        stage,
        update_fields
    ):
        """
        Feature: job-application-tracker, Property 8: History Persistence Across Updates
        
        Updating various non-stage fields should preserve history.
        
        Validates: Requirement 9.3 - History preservation for all field types
        """
        with temp_service() as service:
            # Create application
            created = service.create_application(request)
            
            # Create initial history
            stage_request = StageChangeRequest(new_stage=stage)
            service.change_stage(created.id, stage_request)
            
            # Get initial history
            initial_history = service.get_history(created.id)
            initial_count = len(initial_history)
            
            # Update various fields
            update_data = {}
            if 'recruiter_name' in update_fields:
                update_data['recruiter_name'] = "Updated Recruiter"
            if 'recruiter_email' in update_fields:
                update_data['recruiter_email'] = "updated@example.com"
            if 'notes' in update_fields:
                update_data['notes'] = "Updated notes"
            if 'feedback' in update_fields:
                update_data['feedback'] = "Updated feedback"
            
            update_request = UpdateApplicationRequest(**update_data)
            service.update_application(created.id, update_request)
            
            # Verify history unchanged
            final_history = service.get_history(created.id)
            assert len(final_history) == initial_count, \
                f"History count changed after updating {update_fields}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
