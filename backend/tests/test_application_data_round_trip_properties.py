"""
Property-Based Tests for Application Data Round-Trip Consistency

Tests Property 1: Application Data Round-Trip Consistency
Validates: Requirements 1.1, 1.3, 4.2, 4.3, 4.4, 4.5, 6.1, 6.2, 6.4

Ensures that creating an application with valid data and then retrieving it
returns equivalent data with all fields preserved.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
import tempfile
import shutil
from pathlib import Path
from contextlib import contextmanager

from app.models.application_tracker_models import (
    Application,
    CreateApplicationRequest,
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
def valid_application_data_strategy(draw):
    """Generate valid application data for testing round-trip consistency."""
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


class TestApplicationDataRoundTripProperty:
    """
    Property 1: Application Data Round-Trip Consistency
    
    For any valid application data (including company name, position title, dates,
    contact information, interviews, notes, tasks, feedback, and CV associations),
    creating an application with that data and then retrieving it should return
    equivalent data with all fields preserved.
    """
    
    @given(app_data=valid_application_data_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_1_application_data_round_trip(self, app_data):
        """
        Feature: job-application-tracker, Property 1: Application Data Round-Trip Consistency
        
        For any valid application data, creating and retrieving should return equivalent data.
        
        Validates: Requirements 1.1, 1.3, 4.2, 4.3, 4.4, 4.5, 6.1, 6.2, 6.4
        """
        with temp_storage() as storage:
            # Create application from request data
            application = Application(
                company_name=app_data.company_name,
                position_title=app_data.position_title,
                stage=app_data.stage,
                application_date=app_data.application_date,
                job_description_url=app_data.job_description_url,
                application_deadline=app_data.application_deadline,
                recruiter_name=app_data.recruiter_name,
                recruiter_email=app_data.recruiter_email,
                recruiter_phone=app_data.recruiter_phone,
                hiring_manager_name=app_data.hiring_manager_name,
                interviews=app_data.interviews,
                notes=app_data.notes,
                tasks=app_data.tasks,
                feedback=app_data.feedback,
                outcome=app_data.outcome,
                cv_version_id=app_data.cv_version_id,
                follow_up_date=app_data.follow_up_date
            )
            
            # Store the application
            created = storage.create_application(application)
            
            # Retrieve the application
            retrieved = storage.get_application(created.id)
            
            # Assert all fields are preserved
            # Required fields
            assert retrieved.company_name == app_data.company_name, \
                "Company name not preserved"
            assert retrieved.position_title == app_data.position_title, \
                "Position title not preserved"
            assert retrieved.stage == app_data.stage, \
                "Stage not preserved"
            assert retrieved.application_date == app_data.application_date, \
                "Application date not preserved"
            
            # Optional fields
            assert retrieved.job_description_url == app_data.job_description_url, \
                "Job description URL not preserved"
            assert retrieved.application_deadline == app_data.application_deadline, \
                "Application deadline not preserved"
            
            # Contact information (Requirement 4.2)
            assert retrieved.recruiter_name == app_data.recruiter_name, \
                "Recruiter name not preserved"
            assert retrieved.recruiter_email == app_data.recruiter_email, \
                "Recruiter email not preserved"
            assert retrieved.recruiter_phone == app_data.recruiter_phone, \
                "Recruiter phone not preserved"
            assert retrieved.hiring_manager_name == app_data.hiring_manager_name, \
                "Hiring manager name not preserved"
            
            # Interviews (Requirement 4.3, 6.2)
            assert len(retrieved.interviews) == len(app_data.interviews), \
                "Interview count not preserved"
            for orig_interview, retr_interview in zip(app_data.interviews, retrieved.interviews):
                assert retr_interview.date == orig_interview.date, \
                    "Interview date not preserved"
                assert retr_interview.type == orig_interview.type, \
                    "Interview type not preserved"
                assert retr_interview.meeting_link == orig_interview.meeting_link, \
                    "Interview meeting link not preserved"
                assert retr_interview.notes == orig_interview.notes, \
                    "Interview notes not preserved"
                assert retr_interview.interviewer_name == orig_interview.interviewer_name, \
                    "Interviewer name not preserved"
            
            # Notes and tasks (Requirement 4.4)
            assert retrieved.notes == app_data.notes, \
                "Notes not preserved"
            assert retrieved.tasks == app_data.tasks, \
                "Tasks not preserved"
            
            # Outcome (Requirement 4.5)
            assert retrieved.feedback == app_data.feedback, \
                "Feedback not preserved"
            assert retrieved.outcome == app_data.outcome, \
                "Outcome not preserved"
            
            # CV association (Requirement 1.3)
            assert retrieved.cv_version_id == app_data.cv_version_id, \
                "CV version ID not preserved"
            
            # Follow-up date (Requirement 6.4)
            assert retrieved.follow_up_date == app_data.follow_up_date, \
                "Follow-up date not preserved"
            
            # Verify ID and timestamps are set
            assert retrieved.id is not None, "ID not set"
            assert retrieved.created_at is not None, "Created timestamp not set"
            assert retrieved.updated_at is not None, "Updated timestamp not set"
    
    @given(app_data=valid_application_data_strategy())
    @settings(max_examples=100, deadline=None)
    def test_required_fields_preserved(self, app_data):
        """
        Test that required fields are always preserved.
        
        Validates: Requirement 1.1 - Required fields must be stored and retrieved
        """
        with temp_storage() as storage:
            application = Application(
                company_name=app_data.company_name,
                position_title=app_data.position_title,
                stage=app_data.stage,
                application_date=app_data.application_date
            )
            
            created = storage.create_application(application)
            retrieved = storage.get_application(created.id)
            
            # Verify required fields
            assert retrieved.company_name == app_data.company_name
            assert retrieved.position_title == app_data.position_title
            assert retrieved.stage == app_data.stage
            assert retrieved.application_date == app_data.application_date
    
    @given(
        app_data=valid_application_data_strategy(),
        interviews=st.lists(valid_interview_strategy(), min_size=1, max_size=5)
    )
    @settings(max_examples=100, deadline=None)
    def test_multiple_interviews_preserved(self, app_data, interviews):
        """
        Test that multiple interview entries are preserved.
        
        Validates: Requirement 4.3 - Multiple interview schedules with dates, times, and meeting links
        """
        # Ensure we have interviews
        assume(len(interviews) > 0)
        
        with temp_storage() as storage:
            application = Application(
                company_name=app_data.company_name,
                position_title=app_data.position_title,
                stage=app_data.stage,
                application_date=app_data.application_date,
                interviews=interviews
            )
            
            created = storage.create_application(application)
            retrieved = storage.get_application(created.id)
            
            # Verify all interviews are preserved
            assert len(retrieved.interviews) == len(interviews)
            
            for orig, retr in zip(interviews, retrieved.interviews):
                assert retr.date == orig.date
                assert retr.type == orig.type
                assert retr.meeting_link == orig.meeting_link
                assert retr.notes == orig.notes
                assert retr.interviewer_name == orig.interviewer_name
    
    @given(
        app_data=valid_application_data_strategy(),
        tasks=st.lists(st.text(min_size=1, max_size=200), min_size=1, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_task_list_preserved(self, app_data, tasks):
        """
        Test that task lists are preserved.
        
        Validates: Requirement 4.4 - Task lists associated with each application
        """
        # Ensure we have tasks
        assume(len(tasks) > 0)
        
        with temp_storage() as storage:
            application = Application(
                company_name=app_data.company_name,
                position_title=app_data.position_title,
                stage=app_data.stage,
                application_date=app_data.application_date,
                tasks=tasks
            )
            
            created = storage.create_application(application)
            retrieved = storage.get_application(created.id)
            
            # Verify task list is preserved
            assert retrieved.tasks == tasks
            assert len(retrieved.tasks) == len(tasks)
    
    @given(app_data=valid_application_data_strategy())
    @settings(max_examples=100, deadline=None)
    def test_contact_information_preserved(self, app_data):
        """
        Test that contact information is preserved.
        
        Validates: Requirement 4.2 - Contact information including recruiter name, email, and phone number
        """
        with temp_storage() as storage:
            application = Application(
                company_name=app_data.company_name,
                position_title=app_data.position_title,
                stage=app_data.stage,
                application_date=app_data.application_date,
                recruiter_name=app_data.recruiter_name,
                recruiter_email=app_data.recruiter_email,
                recruiter_phone=app_data.recruiter_phone,
                hiring_manager_name=app_data.hiring_manager_name
            )
            
            created = storage.create_application(application)
            retrieved = storage.get_application(created.id)
            
            # Verify contact information
            assert retrieved.recruiter_name == app_data.recruiter_name
            assert retrieved.recruiter_email == app_data.recruiter_email
            assert retrieved.recruiter_phone == app_data.recruiter_phone
            assert retrieved.hiring_manager_name == app_data.hiring_manager_name
    
    @given(app_data=valid_application_data_strategy())
    @settings(max_examples=100, deadline=None)
    def test_dates_preserved(self, app_data):
        """
        Test that all date fields are preserved.
        
        Validates: Requirements 6.1, 6.2, 6.4 - Date tracking for applications, interviews, and follow-ups
        """
        with temp_storage() as storage:
            application = Application(
                company_name=app_data.company_name,
                position_title=app_data.position_title,
                stage=app_data.stage,
                application_date=app_data.application_date,
                application_deadline=app_data.application_deadline,
                follow_up_date=app_data.follow_up_date
            )
            
            created = storage.create_application(application)
            retrieved = storage.get_application(created.id)
            
            # Verify dates
            assert retrieved.application_date == app_data.application_date
            assert retrieved.application_deadline == app_data.application_deadline
            assert retrieved.follow_up_date == app_data.follow_up_date
    
    @given(app_data=valid_application_data_strategy())
    @settings(max_examples=100, deadline=None)
    def test_outcome_fields_preserved(self, app_data):
        """
        Test that outcome and feedback fields are preserved.
        
        Validates: Requirement 4.5 - Feedback received and final outcome information
        """
        with temp_storage() as storage:
            application = Application(
                company_name=app_data.company_name,
                position_title=app_data.position_title,
                stage=app_data.stage,
                application_date=app_data.application_date,
                feedback=app_data.feedback,
                outcome=app_data.outcome
            )
            
            created = storage.create_application(application)
            retrieved = storage.get_application(created.id)
            
            # Verify outcome fields
            assert retrieved.feedback == app_data.feedback
            assert retrieved.outcome == app_data.outcome


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
