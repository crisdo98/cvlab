"""
Unit Tests for Application Tracker Service Layer Edge Cases

Tests specific examples and edge cases for the service layer including:
- Creating applications with minimal and maximal data
- Error handling for non-existent applications
- Invalid stage transitions
- CSV import with malformed data
- CSV export with empty application list

Validates: Requirements 1.1, 1.2, 1.5, 11.2, 11.3
"""

import pytest
import tempfile
import shutil
from datetime import datetime
from contextlib import contextmanager

from app.models.application_tracker_models import (
    Application,
    CreateApplicationRequest,
    UpdateApplicationRequest,
    StageChangeRequest,
    Stage
)
from app.services.application_tracker_service import (
    ApplicationTrackerService,
    ApplicationTrackerServiceError
)
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


class TestCreateApplicationEdgeCases:
    """Test creating applications with minimal and maximal data."""
    
    def test_create_application_with_minimal_required_fields(self):
        """
        Test creating application with only required fields.
        
        Validates: Requirement 1.1 - Application creation with minimal data
        """
        with temp_service() as service:
            # Create request with only required fields
            request = CreateApplicationRequest(
                company_name="Example Corp",
                position_title="Software Developer",
                stage=Stage.WISHLIST,
                application_date=datetime(2024, 1, 15, 10, 0, 0)
            )
            
            # Create application
            created = service.create_application(request)
            
            # Verify required fields are set
            assert created.id is not None
            assert created.company_name == "Example Corp"
            assert created.position_title == "Software Developer"
            assert created.stage == Stage.WISHLIST
            assert created.application_date == datetime(2024, 1, 15, 10, 0, 0)
            assert created.created_at is not None
            assert created.updated_at is not None
            
            # Verify optional fields are None or empty
            assert created.job_description_url is None
            assert created.application_deadline is None
            assert created.recruiter_name is None
            assert created.recruiter_email is None
            assert created.recruiter_phone is None
            assert created.hiring_manager_name is None
            assert created.interviews == []
            assert created.notes is None
            assert created.tasks == []
            assert created.feedback is None
            assert created.outcome is None
            assert created.cv_version_id is None
            assert created.follow_up_date is None
    
    def test_create_application_with_all_optional_fields(self):
        """
        Test creating application with all optional fields populated.
        
        Validates: Requirement 1.1 - Application creation with complete data
        """
        with temp_service() as service:
            # Create request with all fields
            request = CreateApplicationRequest(
                company_name="Tech Giant Inc",
                position_title="Senior Backend Engineer",
                stage=Stage.APPLIED,
                application_date=datetime(2024, 2, 1, 9, 0, 0),
                job_description_url="https://example.com/jobs/123",
                application_deadline=datetime(2024, 2, 15, 23, 59, 59),
                recruiter_name="Jane Smith",
                recruiter_email="jane.smith@example.com",
                recruiter_phone="+1-555-0123",
                hiring_manager_name="John Doe",
                interviews=[],
                notes="Referred by colleague",
                tasks=["Prepare portfolio", "Research company"],
                feedback="Positive initial response",
                outcome="Moved to next round",
                cv_version_id="cv-123-456",
                follow_up_date=datetime(2024, 2, 20, 10, 0, 0)
            )
            
            # Create application
            created = service.create_application(request)
            
            # Verify all fields are set correctly
            assert created.id is not None
            assert created.company_name == "Tech Giant Inc"
            assert created.position_title == "Senior Backend Engineer"
            assert created.stage == Stage.APPLIED
            assert created.application_date == datetime(2024, 2, 1, 9, 0, 0)
            assert created.job_description_url == "https://example.com/jobs/123"
            assert created.application_deadline == datetime(2024, 2, 15, 23, 59, 59)
            assert created.recruiter_name == "Jane Smith"
            assert created.recruiter_email == "jane.smith@example.com"
            assert created.recruiter_phone == "+1-555-0123"
            assert created.hiring_manager_name == "John Doe"
            assert created.notes == "Referred by colleague"
            assert created.tasks == ["Prepare portfolio", "Research company"]
            assert created.feedback == "Positive initial response"
            assert created.outcome == "Moved to next round"
            assert created.cv_version_id == "cv-123-456"
            assert created.follow_up_date == datetime(2024, 2, 20, 10, 0, 0)
            assert created.created_at is not None
            assert created.updated_at is not None


class TestUpdateNonExistentApplication:
    """Test updating non-existent applications returns appropriate errors."""
    
    def test_update_non_existent_application_returns_error(self):
        """
        Test that updating a non-existent application raises ApplicationNotFoundError.
        
        Validates: Requirement 1.2 - Error handling for invalid updates
        """
        with temp_service() as service:
            # Try to update non-existent application
            fake_id = "non-existent-id-12345"
            update_request = UpdateApplicationRequest(
                company_name="Updated Company"
            )
            
            # Verify error is raised
            with pytest.raises(ApplicationNotFoundError):
                service.update_application(fake_id, update_request)
    
    def test_update_with_invalid_uuid_format(self):
        """
        Test that updating with invalid UUID format raises ApplicationNotFoundError.
        
        Validates: Requirement 1.2 - Input validation
        """
        with temp_service() as service:
            # Try to update with invalid UUID format
            invalid_id = "not-a-valid-uuid"
            update_request = UpdateApplicationRequest(
                position_title="Updated Position"
            )
            
            # Verify error is raised
            with pytest.raises(ApplicationNotFoundError):
                service.update_application(invalid_id, update_request)


class TestDeleteNonExistentApplication:
    """Test deleting non-existent applications returns appropriate errors."""
    
    def test_delete_non_existent_application_returns_error(self):
        """
        Test that deleting a non-existent application raises ApplicationNotFoundError.
        
        Validates: Requirement 1.5 - Error handling for invalid deletions
        """
        with temp_service() as service:
            # Try to delete non-existent application
            fake_id = "non-existent-id-67890"
            
            # Verify error is raised
            with pytest.raises(ApplicationNotFoundError):
                service.delete_application(fake_id)
    
    def test_delete_already_deleted_application(self):
        """
        Test that deleting an already deleted application raises ApplicationNotFoundError.
        
        Validates: Requirement 1.5 - Idempotency of delete operations
        """
        with temp_service() as service:
            # Create and delete an application
            request = CreateApplicationRequest(
                company_name="Test Company",
                position_title="Test Position",
                stage=Stage.WISHLIST,
                application_date=datetime(2024, 1, 1, 10, 0, 0)
            )
            created = service.create_application(request)
            app_id = created.id
            
            # Delete the application
            service.delete_application(app_id)
            
            # Try to delete again
            with pytest.raises(ApplicationNotFoundError):
                service.delete_application(app_id)


class TestInvalidStageTransitionHandling:
    """Test handling of stage transitions (all transitions are valid in current design)."""
    
    def test_stage_transition_on_non_existent_application(self):
        """
        Test that changing stage on non-existent application raises error.
        
        Note: All stage transitions are valid in the current design.
        This test validates error handling for non-existent applications.
        
        Validates: Requirement 3.1 - Error handling for stage changes
        """
        with temp_service() as service:
            # Try to change stage on non-existent application
            fake_id = "non-existent-id-stage"
            stage_request = StageChangeRequest(new_stage=Stage.APPLIED)
            
            # Verify error is raised
            with pytest.raises(ApplicationNotFoundError):
                service.change_stage(fake_id, stage_request)
    
    def test_all_stage_transitions_are_valid(self):
        """
        Test that all stage transitions are allowed (no restrictions).
        
        This documents the current behavior where any stage can transition
        to any other stage without restrictions.
        
        Validates: Requirement 3.1 - Stage transition flexibility
        """
        with temp_service() as service:
            # Create application in WISHLIST stage
            request = CreateApplicationRequest(
                company_name="Test Company",
                position_title="Test Position",
                stage=Stage.WISHLIST,
                application_date=datetime(2024, 1, 1, 10, 0, 0)
            )
            created = service.create_application(request)
            
            # Test all possible stage transitions
            all_stages = [Stage.APPLIED, Stage.INTERVIEW, Stage.OFFER, Stage.REJECTED, Stage.WISHLIST]
            
            for target_stage in all_stages:
                stage_request = StageChangeRequest(new_stage=target_stage)
                updated = service.change_stage(created.id, stage_request)
                assert updated.stage == target_stage, \
                    f"Stage transition to {target_stage} should be allowed"


class TestCSVImportWithMalformedData:
    """Test CSV import with various types of malformed data."""
    
    def test_csv_import_with_missing_required_fields(self):
        """
        Test CSV import with missing required fields.
        
        Validates: Requirement 11.2 - Validation of imported entries
        """
        with temp_service() as service:
            # CSV with missing company_name
            csv_content = b"""company_name,position_title,stage,application_date
,Developer,wishlist,2024-01-15T10:00:00
Example Corp,,wishlist,2024-01-15T10:00:00
Example Corp,Developer,wishlist,"""
            
            # Import CSV
            result = service.import_from_csv(csv_content)
            
            # Verify all rows failed validation
            assert result.total_rows == 3
            assert result.successful == 0
            assert result.failed == 3
            assert len(result.errors) == 3
            
            # Verify error messages mention missing fields
            error_messages = [error['error'] for error in result.errors]
            assert any('company_name' in msg for msg in error_messages)
            assert any('position_title' in msg for msg in error_messages)
            assert any('application_date' in msg for msg in error_messages)
    
    def test_csv_import_with_invalid_date_format(self):
        """
        Test CSV import with invalid date formats.
        
        Validates: Requirement 11.2 - Date format validation
        """
        with temp_service() as service:
            # CSV with invalid date formats
            csv_content = b"""company_name,position_title,stage,application_date
Example Corp,Developer,wishlist,2024-13-45
Tech Inc,Engineer,applied,not-a-date
Startup LLC,Designer,interview,01/15/2024"""
            
            # Import CSV
            result = service.import_from_csv(csv_content)
            
            # Verify all rows failed validation
            assert result.total_rows == 3
            assert result.successful == 0
            assert result.failed == 3
            assert len(result.errors) == 3
            
            # Verify error messages mention date format
            error_messages = [error['error'] for error in result.errors]
            assert all('date' in msg.lower() for msg in error_messages)
    
    def test_csv_import_with_invalid_stage_values(self):
        """
        Test CSV import with invalid stage values.
        
        Validates: Requirement 11.2 - Stage value validation
        """
        with temp_service() as service:
            # CSV with invalid stage values
            csv_content = b"""company_name,position_title,stage,application_date
Example Corp,Developer,invalid_stage,2024-01-15T10:00:00
Tech Inc,Engineer,pending,2024-01-16T10:00:00
Startup LLC,Designer,completed,2024-01-17T10:00:00"""
            
            # Import CSV
            result = service.import_from_csv(csv_content)
            
            # Verify all rows failed validation
            assert result.total_rows == 3
            assert result.successful == 0
            assert result.failed == 3
            assert len(result.errors) == 3
            
            # Verify error messages mention invalid stage
            error_messages = [error['error'] for error in result.errors]
            assert all('stage' in msg.lower() for msg in error_messages)
    
    def test_csv_import_with_mixed_valid_and_invalid_rows(self):
        """
        Test CSV import with mix of valid and invalid rows.
        
        Validates: Requirement 11.3 - Partial import success reporting
        """
        with temp_service() as service:
            # CSV with mix of valid and invalid rows
            csv_content = b"""company_name,position_title,stage,application_date
Example Corp,Developer,wishlist,2024-01-15T10:00:00
,Engineer,applied,2024-01-16T10:00:00
Tech Inc,Designer,interview,2024-01-17T10:00:00
Startup LLC,,offer,2024-01-18T10:00:00
Good Company,Manager,rejected,2024-01-19T10:00:00"""
            
            # Import CSV
            result = service.import_from_csv(csv_content)
            
            # Verify partial success
            assert result.total_rows == 5
            assert result.successful == 3  # Rows 1, 3, 5
            assert result.failed == 2  # Rows 2, 4
            assert len(result.errors) == 2
            
            # Verify valid applications were created
            all_apps = service.list_applications()
            assert len(all_apps) == 3
            
            company_names = [app.company_name for app in all_apps]
            assert "Example Corp" in company_names
            assert "Tech Inc" in company_names
            assert "Good Company" in company_names
    
    def test_csv_import_with_empty_file(self):
        """
        Test CSV import with empty file (only headers).
        
        Validates: Requirement 11.3 - Handling of empty imports
        """
        with temp_service() as service:
            # CSV with only headers
            csv_content = b"""company_name,position_title,stage,application_date"""
            
            # Import CSV
            result = service.import_from_csv(csv_content)
            
            # Verify no rows processed
            assert result.total_rows == 0
            assert result.successful == 0
            assert result.failed == 0
            assert len(result.errors) == 0
    
    def test_csv_import_with_invalid_encoding(self):
        """
        Test CSV import with invalid encoding.
        
        Validates: Requirement 11.2 - File encoding validation
        """
        with temp_service() as service:
            # Invalid UTF-8 bytes
            csv_content = b'\xff\xfe\x00\x00invalid encoding'
            
            # Verify error is raised
            with pytest.raises(ApplicationTrackerServiceError) as exc_info:
                service.import_from_csv(csv_content)
            
            assert "encoding" in str(exc_info.value).lower()


class TestCSVExportWithEmptyApplicationList:
    """Test CSV export with empty application list."""
    
    def test_export_csv_with_no_applications(self):
        """
        Test CSV export when no applications exist.
        
        Validates: Requirement 12.1 - Export with empty dataset
        """
        with temp_service() as service:
            # Export with no applications
            csv_content = service.export_to_csv()
            
            # Verify CSV has headers but no data rows
            lines = csv_content.strip().split('\n')
            assert len(lines) == 1  # Only header row
            
            # Verify header contains expected columns
            header = lines[0]
            assert 'company_name' in header
            assert 'position_title' in header
            assert 'stage' in header
            assert 'application_date' in header
    
    def test_export_csv_with_filters_matching_no_applications(self):
        """
        Test CSV export with filters that match no applications.
        
        Validates: Requirement 12.3 - Filtered export with no matches
        """
        with temp_service() as service:
            # Create some applications
            request1 = CreateApplicationRequest(
                company_name="Example Corp",
                position_title="Developer",
                stage=Stage.WISHLIST,
                application_date=datetime(2024, 1, 15, 10, 0, 0)
            )
            service.create_application(request1)
            
            request2 = CreateApplicationRequest(
                company_name="Tech Inc",
                position_title="Engineer",
                stage=Stage.APPLIED,
                application_date=datetime(2024, 1, 16, 10, 0, 0)
            )
            service.create_application(request2)
            
            # Export with filter that matches nothing
            from app.models.application_tracker_models import ApplicationFilters
            filters = ApplicationFilters(stage=Stage.OFFER)
            csv_content = service.export_to_csv(filters)
            
            # Verify CSV has headers but no data rows
            lines = csv_content.strip().split('\n')
            assert len(lines) == 1  # Only header row
    
    def test_export_csv_includes_all_fields(self):
        """
        Test that CSV export includes all application fields.
        
        Validates: Requirement 12.2 - Export data completeness
        """
        with temp_service() as service:
            # Create application with all fields
            request = CreateApplicationRequest(
                company_name="Complete Corp",
                position_title="Full Stack Developer",
                stage=Stage.INTERVIEW,
                application_date=datetime(2024, 1, 20, 10, 0, 0),
                job_description_url="https://example.com/job",
                recruiter_name="Jane Doe",
                recruiter_email="jane@example.com",
                notes="Test notes",
                cv_version_id="cv-123"
            )
            created = service.create_application(request)
            
            # Export to CSV
            csv_content = service.export_to_csv()
            
            # Verify all fields are in the CSV
            lines = csv_content.strip().split('\n')
            assert len(lines) == 2  # Header + 1 data row
            
            header = lines[0]
            data_row = lines[1]
            
            # Verify key fields are present in header
            assert 'id' in header
            assert 'company_name' in header
            assert 'position_title' in header
            assert 'stage' in header
            assert 'application_date' in header
            assert 'job_description_url' in header
            assert 'recruiter_name' in header
            assert 'recruiter_email' in header
            assert 'notes' in header
            assert 'cv_version_id' in header
            
            # Verify data is present in data row
            assert created.id in data_row
            assert 'Complete Corp' in data_row
            assert 'Full Stack Developer' in data_row
            assert 'interview' in data_row
