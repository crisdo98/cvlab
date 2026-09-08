"""
Property-Based Tests for Storage Operations

Tests Property 19: Immediate Persistence
Tests Property 20: Complete Data Retrieval
Validates: Requirements 8.1, 8.2

Ensures that storage operations persist data immediately and retrieve all stored data completely.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime
import tempfile
import shutil
from pathlib import Path
from contextlib import contextmanager

from app.models.application_tracker_models import (
    Application,
    Interview,
    Stage
)
from app.services.application_tracker_storage import ApplicationTrackerStorage


@contextmanager
def temp_storage():
    """Context manager for temporary storage directory."""
    temp_dir = tempfile.mkdtemp()
    storage = ApplicationTrackerStorage(data_directory=temp_dir)
    try:
        yield storage
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
def valid_application_strategy(draw):
    """Generate valid Application instances for testing."""
    # Required fields
    company_name = draw(st.text(min_size=1, max_size=200))
    position_title = draw(st.text(min_size=1, max_size=200))
    stage = draw(st.sampled_from(Stage))
    application_date = draw(st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31)
    ))
    
    # Optional fields
    job_description_url = draw(st.one_of(st.none(), valid_url_strategy()))
    application_deadline = draw(st.one_of(
        st.none(),
        st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31))
    ))
    
    # Contact information
    recruiter_name = draw(st.one_of(st.none(), st.text(min_size=1, max_size=100)))
    recruiter_email = draw(st.one_of(st.none(), valid_email_strategy()))
    recruiter_phone = draw(st.one_of(st.none(), st.text(min_size=5, max_size=20)))
    hiring_manager_name = draw(st.one_of(st.none(), st.text(min_size=1, max_size=100)))
    
    # Interviews
    interviews = draw(st.lists(valid_interview_strategy(), min_size=0, max_size=5))
    
    # Notes and tracking
    notes = draw(st.one_of(st.none(), st.text(min_size=0, max_size=1000)))
    tasks = draw(st.lists(st.text(min_size=1, max_size=200), min_size=0, max_size=10))
    
    # Outcome
    feedback = draw(st.one_of(st.none(), st.text(min_size=0, max_size=1000)))
    outcome = draw(st.one_of(st.none(), st.text(min_size=0, max_size=500)))
    
    # CV association
    cv_version_id = draw(st.one_of(st.none(), st.text(min_size=1, max_size=100)))
    
    # Follow-up
    follow_up_date = draw(st.one_of(
        st.none(),
        st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31))
    ))
    
    return Application(
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


class TestImmediatePersistenceProperty:
    """
    Property 19: Immediate Persistence
    
    For any application creation or modification, the data should be immediately
    retrievable from storage without requiring additional operations or delays.
    
    Validates: Requirement 8.1
    """
    
    @given(application=valid_application_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_19_immediate_persistence_on_create(self, application):
        """
        Feature: job-application-tracker, Property 19: Immediate Persistence
        
        For any application creation, the data should be immediately retrievable.
        
        Validates: Requirement 8.1 - Immediate persistence on creation
        """
        with temp_storage() as storage:
            # Create application
            created = storage.create_application(application)
            
            # Immediately retrieve without any additional operations
            retrieved = storage.get_application(created.id)
            
            # Verify data is immediately available
            assert retrieved is not None, "Application not immediately retrievable after creation"
            assert retrieved.id == created.id, "Retrieved application has different ID"
            assert retrieved.company_name == application.company_name, \
                "Company name not immediately persisted"
            assert retrieved.position_title == application.position_title, \
                "Position title not immediately persisted"
            assert retrieved.stage == application.stage, \
                "Stage not immediately persisted"
    
    @given(application=valid_application_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_19_immediate_persistence_on_update(self, application):
        """
        Feature: job-application-tracker, Property 19: Immediate Persistence
        
        For any application modification, the updated data should be immediately retrievable.
        
        Validates: Requirement 8.1 - Immediate persistence on update
        """
        with temp_storage() as storage:
            # Create initial application
            created = storage.create_application(application)
            
            # Modify the application
            created.company_name = "Updated Company"
            created.position_title = "Updated Position"
            
            # Update in storage
            updated = storage.update_application(created.id, created)
            
            # Immediately retrieve without any additional operations
            retrieved = storage.get_application(created.id)
            
            # Verify updated data is immediately available
            assert retrieved.company_name == "Updated Company", \
                "Updated company name not immediately persisted"
            assert retrieved.position_title == "Updated Position", \
                "Updated position title not immediately persisted"
    
    @given(application=valid_application_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_19_immediate_persistence_in_list(self, application):
        """
        Feature: job-application-tracker, Property 19: Immediate Persistence
        
        For any application creation, it should immediately appear in list queries.
        
        Validates: Requirement 8.1 - Immediate availability in list operations
        """
        with temp_storage() as storage:
            # Create application
            created = storage.create_application(application)
            
            # Immediately list all applications
            all_applications = storage.list_applications()
            
            # Verify application appears in list
            assert len(all_applications) > 0, "No applications in list after creation"
            
            app_ids = [app.id for app in all_applications]
            assert created.id in app_ids, \
                "Created application not immediately available in list"
            
            # Find the created application in the list
            found_app = next((app for app in all_applications if app.id == created.id), None)
            assert found_app is not None, "Created application not found in list"
            assert found_app.company_name == application.company_name, \
                "Application data in list doesn't match created data"
    
    @given(
        app1=valid_application_strategy(),
        app2=valid_application_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_19_immediate_persistence_multiple_operations(self, app1, app2):
        """
        Feature: job-application-tracker, Property 19: Immediate Persistence
        
        For multiple sequential operations, each should be immediately persisted.
        
        Validates: Requirement 8.1 - Immediate persistence across multiple operations
        """
        with temp_storage() as storage:
            # Create first application
            created1 = storage.create_application(app1)
            
            # Immediately verify it's retrievable
            retrieved1 = storage.get_application(created1.id)
            assert retrieved1.id == created1.id
            
            # Create second application
            created2 = storage.create_application(app2)
            
            # Immediately verify both are retrievable
            retrieved1_again = storage.get_application(created1.id)
            retrieved2 = storage.get_application(created2.id)
            
            assert retrieved1_again.id == created1.id, \
                "First application not persisted after second creation"
            assert retrieved2.id == created2.id, \
                "Second application not immediately persisted"
            
            # Verify both appear in list
            all_apps = storage.list_applications()
            assert len(all_apps) == 2, \
                "Not all applications immediately available in list"


class TestCompleteDataRetrievalProperty:
    """
    Property 20: Complete Data Retrieval
    
    For any set of stored applications, loading all applications should retrieve
    every stored application with all fields intact.
    
    Validates: Requirement 8.2
    """
    
    @given(applications=st.lists(valid_application_strategy(), min_size=1, max_size=20))
    @settings(max_examples=100, deadline=None)
    def test_property_20_complete_data_retrieval(self, applications):
        """
        Feature: job-application-tracker, Property 20: Complete Data Retrieval
        
        For any set of stored applications, loading all applications should retrieve
        every stored application with all fields intact.
        
        Validates: Requirement 8.2 - Complete data retrieval
        """
        # Ensure we have at least one application
        assume(len(applications) > 0)
        
        with temp_storage() as storage:
            # Store all applications
            created_apps = []
            for app in applications:
                created = storage.create_application(app)
                created_apps.append(created)
            
            # Retrieve all applications
            retrieved_apps = storage.list_applications()
            
            # Verify count matches
            assert len(retrieved_apps) == len(created_apps), \
                f"Retrieved {len(retrieved_apps)} applications but created {len(created_apps)}"
            
            # Verify all created applications are in retrieved list
            created_ids = {app.id for app in created_apps}
            retrieved_ids = {app.id for app in retrieved_apps}
            
            assert created_ids == retrieved_ids, \
                "Retrieved application IDs don't match created application IDs"
            
            # Verify all fields are intact for each application
            for created in created_apps:
                retrieved = next((app for app in retrieved_apps if app.id == created.id), None)
                assert retrieved is not None, f"Application {created.id} not found in retrieved list"
                
                # Verify all fields
                assert retrieved.company_name == created.company_name, \
                    "Company name not intact in retrieval"
                assert retrieved.position_title == created.position_title, \
                    "Position title not intact in retrieval"
                assert retrieved.stage == created.stage, \
                    "Stage not intact in retrieval"
                assert retrieved.application_date == created.application_date, \
                    "Application date not intact in retrieval"
                assert retrieved.job_description_url == created.job_description_url, \
                    "Job description URL not intact in retrieval"
                assert retrieved.recruiter_name == created.recruiter_name, \
                    "Recruiter name not intact in retrieval"
                assert retrieved.recruiter_email == created.recruiter_email, \
                    "Recruiter email not intact in retrieval"
                assert retrieved.notes == created.notes, \
                    "Notes not intact in retrieval"
                assert retrieved.tasks == created.tasks, \
                    "Tasks not intact in retrieval"
                assert len(retrieved.interviews) == len(created.interviews), \
                    "Interview count not intact in retrieval"
    
    @given(applications=st.lists(valid_application_strategy(), min_size=2, max_size=10))
    @settings(max_examples=100, deadline=None)
    def test_property_20_no_data_loss_on_multiple_creates(self, applications):
        """
        Feature: job-application-tracker, Property 20: Complete Data Retrieval
        
        Creating multiple applications should not cause data loss of earlier applications.
        
        Validates: Requirement 8.2 - No data loss during multiple operations
        """
        # Ensure we have at least 2 applications
        assume(len(applications) >= 2)
        
        with temp_storage() as storage:
            created_ids = []
            
            # Create applications one by one
            for app in applications:
                created = storage.create_application(app)
                created_ids.append(created.id)
                
                # After each creation, verify all previous applications are still retrievable
                retrieved_apps = storage.list_applications()
                retrieved_ids = [app.id for app in retrieved_apps]
                
                for prev_id in created_ids:
                    assert prev_id in retrieved_ids, \
                        f"Application {prev_id} lost after creating new application"
            
            # Final verification: all applications are retrievable
            final_apps = storage.list_applications()
            assert len(final_apps) == len(applications), \
                "Not all applications retrievable at the end"
    
    @given(applications=st.lists(valid_application_strategy(), min_size=1, max_size=10))
    @settings(max_examples=100, deadline=None)
    def test_property_20_complete_retrieval_after_updates(self, applications):
        """
        Feature: job-application-tracker, Property 20: Complete Data Retrieval
        
        After updating applications, all applications should still be completely retrievable.
        
        Validates: Requirement 8.2 - Complete retrieval after updates
        """
        # Ensure we have at least one application
        assume(len(applications) > 0)
        
        with temp_storage() as storage:
            # Create all applications
            created_apps = []
            for app in applications:
                created = storage.create_application(app)
                created_apps.append(created)
            
            # Update some applications
            for i, app in enumerate(created_apps):
                if i % 2 == 0:  # Update every other application
                    app.company_name = f"Updated Company {i}"
                    storage.update_application(app.id, app)
            
            # Retrieve all applications
            retrieved_apps = storage.list_applications()
            
            # Verify all applications are still retrievable
            assert len(retrieved_apps) == len(created_apps), \
                "Not all applications retrievable after updates"
            
            # Verify updated applications have new data
            for i, created in enumerate(created_apps):
                retrieved = next((app for app in retrieved_apps if app.id == created.id), None)
                assert retrieved is not None, \
                    f"Application {created.id} not found after updates"
                
                if i % 2 == 0:
                    assert retrieved.company_name == f"Updated Company {i}", \
                        "Updated data not reflected in retrieval"
    
    @given(applications=st.lists(valid_application_strategy(), min_size=3, max_size=10))
    @settings(max_examples=100, deadline=None)
    def test_property_20_complete_retrieval_after_deletions(self, applications):
        """
        Feature: job-application-tracker, Property 20: Complete Data Retrieval
        
        After deleting some applications, remaining applications should be completely retrievable.
        
        Validates: Requirement 8.2 - Complete retrieval of remaining data after deletions
        """
        # Ensure we have at least 3 applications
        assume(len(applications) >= 3)
        
        with temp_storage() as storage:
            # Create all applications
            created_apps = []
            for app in applications:
                created = storage.create_application(app)
                created_apps.append(created)
            
            # Delete some applications (every third one)
            deleted_ids = []
            remaining_ids = []
            for i, app in enumerate(created_apps):
                if i % 3 == 0:
                    storage.delete_application(app.id)
                    deleted_ids.append(app.id)
                else:
                    remaining_ids.append(app.id)
            
            # Retrieve all applications
            retrieved_apps = storage.list_applications()
            
            # Verify only remaining applications are retrievable
            assert len(retrieved_apps) == len(remaining_ids), \
                f"Expected {len(remaining_ids)} applications but got {len(retrieved_apps)}"
            
            retrieved_ids = {app.id for app in retrieved_apps}
            
            # Verify deleted applications are not in list
            for deleted_id in deleted_ids:
                assert deleted_id not in retrieved_ids, \
                    f"Deleted application {deleted_id} still in list"
            
            # Verify remaining applications are all present
            for remaining_id in remaining_ids:
                assert remaining_id in retrieved_ids, \
                    f"Remaining application {remaining_id} not in list"
    
    @given(applications=st.lists(valid_application_strategy(), min_size=1, max_size=10))
    @settings(max_examples=100, deadline=None)
    def test_property_20_all_fields_intact_in_bulk_retrieval(self, applications):
        """
        Feature: job-application-tracker, Property 20: Complete Data Retrieval
        
        When retrieving multiple applications, all fields should be intact for each.
        
        Validates: Requirement 8.2 - All fields intact during bulk retrieval
        """
        # Ensure we have at least one application
        assume(len(applications) > 0)
        
        with temp_storage() as storage:
            # Create applications with diverse data
            created_apps = []
            for app in applications:
                created = storage.create_application(app)
                created_apps.append(created)
            
            # Retrieve all applications
            retrieved_apps = storage.list_applications()
            
            # Verify all fields are intact for each application
            for created in created_apps:
                retrieved = next((app for app in retrieved_apps if app.id == created.id), None)
                assert retrieved is not None
                
                # Check all field types
                assert retrieved.company_name == created.company_name
                assert retrieved.position_title == created.position_title
                assert retrieved.stage == created.stage
                assert retrieved.application_date == created.application_date
                assert retrieved.job_description_url == created.job_description_url
                assert retrieved.application_deadline == created.application_deadline
                assert retrieved.recruiter_name == created.recruiter_name
                assert retrieved.recruiter_email == created.recruiter_email
                assert retrieved.recruiter_phone == created.recruiter_phone
                assert retrieved.hiring_manager_name == created.hiring_manager_name
                assert retrieved.notes == created.notes
                assert retrieved.tasks == created.tasks
                assert retrieved.feedback == created.feedback
                assert retrieved.outcome == created.outcome
                assert retrieved.cv_version_id == created.cv_version_id
                assert retrieved.follow_up_date == created.follow_up_date
                assert len(retrieved.interviews) == len(created.interviews)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
