"""
Property-Based Tests for Data Validation Rejection

Tests Property 18: Data Validation Rejection
Validates: Requirements 8.4

Ensures that invalid application data (missing required fields, invalid date formats,
invalid stage values, invalid email formats, invalid URL formats) is rejected with
validation errors and not persisted to storage.
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime
from pydantic import ValidationError
import tempfile
import shutil
from contextlib import contextmanager

from app.models.application_tracker_models import (
    Application,
    CreateApplicationRequest,
    UpdateApplicationRequest,
    Interview,
    Stage
)
from app.services.application_tracker_storage import ApplicationTrackerStorage
from app.services.application_tracker_service import ApplicationTrackerService


@contextmanager
def temp_storage():
    """Context manager for temporary storage directory."""
    temp_dir = tempfile.mkdtemp()
    storage = ApplicationTrackerStorage(data_directory=temp_dir)
    service = ApplicationTrackerService(storage=storage)
    try:
        yield service, storage
    finally:
        shutil.rmtree(temp_dir)


# Hypothesis strategies for generating invalid data

@st.composite
def invalid_email_strategy(draw):
    """Generate invalid email addresses."""
    invalid_emails = [
        draw(st.text(min_size=1, max_size=50)),  # No @ symbol
        draw(st.text(min_size=1, max_size=20)) + "@",  # Missing domain
        "@" + draw(st.text(min_size=1, max_size=20)),  # Missing username
        draw(st.text(min_size=1, max_size=20)) + "@" + draw(st.text(min_size=1, max_size=20)),  # Missing TLD
    ]
    return draw(st.sampled_from(invalid_emails))


@st.composite
def invalid_url_strategy(draw):
    """Generate invalid URLs."""
    invalid_urls = [
        draw(st.text(min_size=1, max_size=50)),  # No protocol
        "ftp://" + draw(st.text(min_size=1, max_size=50)),  # Wrong protocol
        "htp://" + draw(st.text(min_size=1, max_size=50)),  # Typo in protocol
    ]
    return draw(st.sampled_from(invalid_urls))


class TestDataValidationRejectionProperty:
    """
    Property 18: Data Validation Rejection
    
    For any invalid application data (missing required fields, invalid date formats,
    invalid stage values), attempting to create or update an application should fail
    with a validation error and not persist the invalid data.
    """
    
    @given(
        position_title=st.text(min_size=1, max_size=200),
        stage=st.sampled_from(Stage),
        application_date=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31))
    )
    @settings(max_examples=100, deadline=None)
    def test_property_18_missing_company_name_rejected(self, position_title, stage, application_date):
        """
        Feature: job-application-tracker, Property 18: Data Validation Rejection
        
        Test that applications with missing company_name are rejected.
        
        Validates: Requirements 8.4 - Data validation before persistence
        """
        with temp_storage() as (service, storage):
            # Attempt to create application without company_name (empty string)
            with pytest.raises(ValidationError) as exc_info:
                CreateApplicationRequest(
                    company_name="",  # Empty string should fail min_length=1
                    position_title=position_title,
                    stage=stage,
                    application_date=application_date
                )
            
            # Verify validation error occurred
            assert exc_info.value is not None
            
            # Verify no data was persisted
            all_apps = storage.list_applications()
            assert len(all_apps) == 0, "Invalid data should not be persisted"
    
    @given(
        company_name=st.text(min_size=1, max_size=200),
        stage=st.sampled_from(Stage),
        application_date=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31))
    )
    @settings(max_examples=100, deadline=None)
    def test_property_18_missing_position_title_rejected(self, company_name, stage, application_date):
        """
        Feature: job-application-tracker, Property 18: Data Validation Rejection
        
        Test that applications with missing position_title are rejected.
        
        Validates: Requirements 8.4 - Data validation before persistence
        """
        with temp_storage() as (service, storage):
            # Attempt to create application without position_title (empty string)
            with pytest.raises(ValidationError) as exc_info:
                CreateApplicationRequest(
                    company_name=company_name,
                    position_title="",  # Empty string should fail min_length=1
                    stage=stage,
                    application_date=application_date
                )
            
            # Verify validation error occurred
            assert exc_info.value is not None
            
            # Verify no data was persisted
            all_apps = storage.list_applications()
            assert len(all_apps) == 0, "Invalid data should not be persisted"
    
    @given(
        company_name=st.text(min_size=1, max_size=200),
        position_title=st.text(min_size=1, max_size=200),
        stage=st.sampled_from(Stage)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_18_invalid_date_format_rejected(self, company_name, position_title, stage):
        """
        Feature: job-application-tracker, Property 18: Data Validation Rejection
        
        Test that applications with invalid date formats are rejected.
        
        Validates: Requirements 8.4 - Data validation before persistence
        """
        with temp_storage() as (service, storage):
            # Attempt to create application with invalid date (string instead of datetime)
            with pytest.raises((ValidationError, TypeError)) as exc_info:
                CreateApplicationRequest(
                    company_name=company_name,
                    position_title=position_title,
                    stage=stage,
                    application_date="not-a-date"  # Invalid date format
                )
            
            # Verify validation error occurred
            assert exc_info.value is not None
            
            # Verify no data was persisted
            all_apps = storage.list_applications()
            assert len(all_apps) == 0, "Invalid data should not be persisted"
    
    @given(
        company_name=st.text(min_size=1, max_size=200),
        position_title=st.text(min_size=1, max_size=200),
        application_date=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31))
    )
    @settings(max_examples=100, deadline=None)
    def test_property_18_invalid_stage_value_rejected(self, company_name, position_title, application_date):
        """
        Feature: job-application-tracker, Property 18: Data Validation Rejection
        
        Test that applications with invalid stage values are rejected.
        
        Validates: Requirements 8.4 - Data validation before persistence
        """
        with temp_storage() as (service, storage):
            # Attempt to create application with invalid stage value
            with pytest.raises(ValidationError) as exc_info:
                CreateApplicationRequest(
                    company_name=company_name,
                    position_title=position_title,
                    stage="invalid_stage",  # Not a valid Stage enum value
                    application_date=application_date
                )
            
            # Verify validation error occurred
            assert exc_info.value is not None
            
            # Verify no data was persisted
            all_apps = storage.list_applications()
            assert len(all_apps) == 0, "Invalid data should not be persisted"
    
    @given(
        company_name=st.text(min_size=1, max_size=200),
        position_title=st.text(min_size=1, max_size=200),
        stage=st.sampled_from(Stage),
        application_date=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)),
        invalid_email=invalid_email_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_18_invalid_email_format_rejected(self, company_name, position_title, stage, application_date, invalid_email):
        """
        Feature: job-application-tracker, Property 18: Data Validation Rejection
        
        Test that applications with invalid email formats are rejected.
        
        Validates: Requirements 8.4 - Data validation before persistence
        """
        with temp_storage() as (service, storage):
            # Attempt to create application with invalid email
            with pytest.raises(ValidationError) as exc_info:
                CreateApplicationRequest(
                    company_name=company_name,
                    position_title=position_title,
                    stage=stage,
                    application_date=application_date,
                    recruiter_email=invalid_email
                )
            
            # Verify validation error occurred
            assert exc_info.value is not None
            
            # Verify no data was persisted
            all_apps = storage.list_applications()
            assert len(all_apps) == 0, "Invalid data should not be persisted"
    
    @given(
        company_name=st.text(min_size=1, max_size=200),
        position_title=st.text(min_size=1, max_size=200),
        stage=st.sampled_from(Stage),
        application_date=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)),
        invalid_url=invalid_url_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_18_invalid_url_format_rejected(self, company_name, position_title, stage, application_date, invalid_url):
        """
        Feature: job-application-tracker, Property 18: Data Validation Rejection
        
        Test that applications with invalid URL formats are rejected.
        
        Validates: Requirements 8.4 - Data validation before persistence
        """
        with temp_storage() as (service, storage):
            # Attempt to create application with invalid job description URL
            with pytest.raises(ValidationError) as exc_info:
                CreateApplicationRequest(
                    company_name=company_name,
                    position_title=position_title,
                    stage=stage,
                    application_date=application_date,
                    job_description_url=invalid_url
                )
            
            # Verify validation error occurred
            assert exc_info.value is not None
            
            # Verify no data was persisted
            all_apps = storage.list_applications()
            assert len(all_apps) == 0, "Invalid data should not be persisted"
    
    @given(
        company_name=st.text(min_size=1, max_size=200),
        position_title=st.text(min_size=1, max_size=200),
        stage=st.sampled_from(Stage),
        application_date=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)),
        invalid_url=invalid_url_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_18_invalid_interview_meeting_link_rejected(self, company_name, position_title, stage, application_date, invalid_url):
        """
        Feature: job-application-tracker, Property 18: Data Validation Rejection
        
        Test that applications with invalid interview meeting links are rejected.
        
        Validates: Requirements 8.4 - Data validation before persistence
        """
        with temp_storage() as (service, storage):
            # Attempt to create application with invalid interview meeting link
            with pytest.raises(ValidationError) as exc_info:
                interview = Interview(
                    date=application_date,
                    type="video",
                    meeting_link=invalid_url
                )
                CreateApplicationRequest(
                    company_name=company_name,
                    position_title=position_title,
                    stage=stage,
                    application_date=application_date,
                    interviews=[interview]
                )
            
            # Verify validation error occurred
            assert exc_info.value is not None
            
            # Verify no data was persisted
            all_apps = storage.list_applications()
            assert len(all_apps) == 0, "Invalid data should not be persisted"
    
    @given(
        company_name=st.text(min_size=1, max_size=200),
        stage=st.sampled_from(Stage),
        application_date=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31))
    )
    @settings(max_examples=100, deadline=None)
    def test_property_18_update_with_empty_required_field_rejected(self, company_name, stage, application_date):
        """
        Feature: job-application-tracker, Property 18: Data Validation Rejection
        
        Test that updates with empty required fields are rejected.
        
        Validates: Requirements 8.4 - Data validation before persistence
        """
        with temp_storage() as (service, storage):
            # First create a valid application
            valid_request = CreateApplicationRequest(
                company_name=company_name,
                position_title="Valid Position",
                stage=stage,
                application_date=application_date
            )
            created_app = service.create_application(valid_request)
            
            # Verify it was created
            assert storage.get_application(created_app.id) is not None
            
            # Attempt to update with empty position_title
            with pytest.raises(ValidationError) as exc_info:
                UpdateApplicationRequest(
                    position_title=""  # Empty string should fail min_length=1
                )
            
            # Verify validation error occurred
            assert exc_info.value is not None
            
            # Verify original data is unchanged
            retrieved = storage.get_application(created_app.id)
            assert retrieved.position_title == "Valid Position"
    
    @given(
        company_name=st.text(min_size=1, max_size=200),
        position_title=st.text(min_size=1, max_size=200),
        stage=st.sampled_from(Stage),
        application_date=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31))
    )
    @settings(max_examples=100, deadline=None)
    def test_property_18_interview_with_empty_type_rejected(self, company_name, position_title, stage, application_date):
        """
        Feature: job-application-tracker, Property 18: Data Validation Rejection
        
        Test that interviews with empty type field are rejected.
        
        Validates: Requirements 8.4 - Data validation before persistence
        """
        with temp_storage() as (service, storage):
            # Attempt to create interview with empty type
            with pytest.raises(ValidationError) as exc_info:
                interview = Interview(
                    date=application_date,
                    type=""  # Empty string should fail min_length=1
                )
                CreateApplicationRequest(
                    company_name=company_name,
                    position_title=position_title,
                    stage=stage,
                    application_date=application_date,
                    interviews=[interview]
                )
            
            # Verify validation error occurred
            assert exc_info.value is not None
            
            # Verify no data was persisted
            all_apps = storage.list_applications()
            assert len(all_apps) == 0, "Invalid data should not be persisted"
    
    @given(
        company_name=st.text(min_size=1, max_size=200),
        position_title=st.text(min_size=1, max_size=200),
        stage=st.sampled_from(Stage),
        application_date=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)),
        invalid_email=invalid_email_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_18_update_with_invalid_email_rejected(self, company_name, position_title, stage, application_date, invalid_email):
        """
        Feature: job-application-tracker, Property 18: Data Validation Rejection
        
        Test that updates with invalid email formats are rejected.
        
        Validates: Requirements 8.4 - Data validation before persistence
        """
        with temp_storage() as (service, storage):
            # First create a valid application
            valid_request = CreateApplicationRequest(
                company_name=company_name,
                position_title=position_title,
                stage=stage,
                application_date=application_date
            )
            created_app = service.create_application(valid_request)
            
            # Attempt to update with invalid email
            with pytest.raises(ValidationError) as exc_info:
                UpdateApplicationRequest(
                    recruiter_email=invalid_email
                )
            
            # Verify validation error occurred
            assert exc_info.value is not None
            
            # Verify original data is unchanged
            retrieved = storage.get_application(created_app.id)
            assert retrieved.recruiter_email is None  # Original had no email


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
