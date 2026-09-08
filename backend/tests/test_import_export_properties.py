"""
Property-Based Tests for CSV Import/Export Operations

Tests Properties 25-30: CSV Import/Export Correctness
Validates: Requirements 11.1, 11.2, 11.4, 11.5, 12.1, 12.2, 12.3, 12.4

Ensures that CSV import and export operations maintain data integrity,
validate input correctly, and produce accurate summaries.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime
import tempfile
import shutil
import csv
import io
from contextlib import contextmanager

from app.models.application_tracker_models import (
    Application,
    CreateApplicationRequest,
    Stage,
    ApplicationFilters
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
def valid_csv_row_strategy(draw):
    """Generate valid CSV row data."""
    # Generate non-empty strings that aren't just whitespace
    company_name = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='.,&- '
    )))
    # Ensure it's not just whitespace
    assume(company_name.strip())
    
    position_title = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='.,&- '
    )))
    # Ensure it's not just whitespace
    assume(position_title.strip())
    
    stage = draw(st.sampled_from(['wishlist', 'applied', 'interview', 'offer', 'rejected']))
    application_date = draw(st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31)
    ))
    
    # Optional fields
    job_url = draw(st.one_of(
        st.none(),
        st.just('https://example.com/job')
    ))
    recruiter_name = draw(st.one_of(
        st.none(),
        st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Zs')
        ))
    ))
    recruiter_email = draw(st.one_of(
        st.none(),
        st.just('recruiter@example.com')
    ))
    notes = draw(st.one_of(
        st.none(),
        st.text(min_size=0, max_size=200, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po')
        ))
    ))
    
    return {
        'company_name': company_name,
        'position_title': position_title,
        'stage': stage,
        'application_date': application_date.isoformat(),
        'job_description_url': job_url or '',
        'recruiter_name': recruiter_name or '',
        'recruiter_email': recruiter_email or '',
        'notes': notes or ''
    }


@st.composite
def invalid_csv_row_strategy(draw):
    """Generate invalid CSV row data (missing required fields or invalid formats)."""
    invalid_type = draw(st.sampled_from([
        'missing_company',
        'missing_position',
        'missing_date',
        'invalid_date',
        'invalid_stage'
    ]))
    
    if invalid_type == 'missing_company':
        return {
            'company_name': '',
            'position_title': 'Developer',
            'stage': 'applied',
            'application_date': datetime.now().isoformat()
        }
    elif invalid_type == 'missing_position':
        return {
            'company_name': 'Example Corp',
            'position_title': '',
            'stage': 'applied',
            'application_date': datetime.now().isoformat()
        }
    elif invalid_type == 'missing_date':
        return {
            'company_name': 'Example Corp',
            'position_title': 'Developer',
            'stage': 'applied',
            'application_date': ''
        }
    elif invalid_type == 'invalid_date':
        return {
            'company_name': 'Example Corp',
            'position_title': 'Developer',
            'stage': 'applied',
            'application_date': 'not-a-date'
        }
    else:  # invalid_stage
        return {
            'company_name': 'Example Corp',
            'position_title': 'Developer',
            'stage': 'invalid_stage',
            'application_date': datetime.now().isoformat()
        }


def create_csv_content(rows):
    """Create CSV content from list of row dictionaries."""
    if not rows:
        return "company_name,position_title,stage,application_date\n"
    
    output = io.StringIO()
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    
    content = output.getvalue()
    output.close()
    return content


@st.composite
def valid_application_for_export_strategy(draw):
    """Generate valid application data for export testing."""
    company_name = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs')
    )))
    position_title = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs')
    )))
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


class TestCSVImportProperties:
    """
    Property 25: CSV Import Valid Entry Creation
    Property 26: CSV Import Validation
    Property 27: Import Summary Accuracy
    
    Tests that CSV import correctly creates applications for valid entries,
    rejects invalid entries with appropriate errors, and provides accurate summaries.
    """
    
    @given(rows=st.lists(valid_csv_row_strategy(), min_size=1, max_size=10))
    @settings(max_examples=100, deadline=None)
    def test_property_25_csv_import_valid_entry_creation(self, rows):
        """
        Feature: job-application-tracker, Property 25: CSV Import Valid Entry Creation
        
        For any CSV file containing valid application data, importing the file should
        create applications for all valid entries with data matching the CSV content.
        
        Validates: Requirements 11.1, 11.5
        """
        with temp_service() as service:
            # Create CSV content
            csv_content = create_csv_content(rows)
            csv_bytes = csv_content.encode('utf-8')
            
            # Import CSV
            result = service.import_from_csv(csv_bytes)
            
            # Verify all entries were created successfully
            assert result.successful == len(rows), \
                f"Expected {len(rows)} successful imports, got {result.successful}"
            assert result.failed == 0, \
                f"Expected 0 failed imports, got {result.failed}"
            assert result.total_rows == len(rows), \
                f"Expected {len(rows)} total rows, got {result.total_rows}"
            
            # Verify applications were created with correct data
            applications = service.list_applications()
            assert len(applications) == len(rows), \
                f"Expected {len(rows)} applications, got {len(applications)}"
            
            # Create a list of expected data from rows for matching
            expected_data = []
            for row in rows:
                expected_date = datetime.fromisoformat(row['application_date'].replace('Z', '+00:00'))
                expected_data.append({
                    'company_name': row['company_name'].strip(),
                    'position_title': row['position_title'].strip(),
                    'stage': row['stage'],
                    'application_date': expected_date.replace(tzinfo=None, microsecond=0)
                })
            
            # Create a list of actual data from applications for matching
            actual_data = []
            for app in applications:
                actual_data.append({
                    'company_name': app.company_name,
                    'position_title': app.position_title,
                    'stage': app.stage.value,
                    'application_date': app.application_date.replace(tzinfo=None, microsecond=0)
                })
            
            # Sort both lists for comparison (to handle order differences)
            expected_sorted = sorted(expected_data, key=lambda x: (x['company_name'], x['position_title'], x['application_date'].isoformat(), x['stage']))
            actual_sorted = sorted(actual_data, key=lambda x: (x['company_name'], x['position_title'], x['application_date'].isoformat(), x['stage']))
            
            # Verify each expected entry has a matching actual entry
            assert expected_sorted == actual_sorted, \
                f"Mismatch between expected and actual data.\nExpected: {expected_sorted}\nActual: {actual_sorted}"
    
    @given(invalid_rows=st.lists(invalid_csv_row_strategy(), min_size=1, max_size=5))
    @settings(max_examples=100, deadline=None)
    def test_property_26_csv_import_validation(self, invalid_rows):
        """
        Feature: job-application-tracker, Property 26: CSV Import Validation
        
        For any CSV file containing entries with missing required fields or invalid data,
        importing should reject those entries and report validation errors without
        creating applications for them.
        
        Validates: Requirements 11.2
        """
        with temp_service() as service:
            # Create CSV content with invalid rows
            csv_content = create_csv_content(invalid_rows)
            csv_bytes = csv_content.encode('utf-8')
            
            # Import CSV
            result = service.import_from_csv(csv_bytes)
            
            # Verify all entries failed validation
            assert result.failed == len(invalid_rows), \
                f"Expected {len(invalid_rows)} failed imports, got {result.failed}"
            assert result.successful == 0, \
                f"Expected 0 successful imports, got {result.successful}"
            assert result.total_rows == len(invalid_rows), \
                f"Expected {len(invalid_rows)} total rows, got {result.total_rows}"
            
            # Verify errors were reported
            assert len(result.errors) == len(invalid_rows), \
                f"Expected {len(invalid_rows)} errors, got {len(result.errors)}"
            
            # Verify no applications were created
            applications = service.list_applications()
            assert len(applications) == 0, \
                f"Expected 0 applications, got {len(applications)}"
    
    @given(
        valid_rows=st.lists(valid_csv_row_strategy(), min_size=1, max_size=5),
        invalid_rows=st.lists(invalid_csv_row_strategy(), min_size=1, max_size=5)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_27_import_summary_accuracy(self, valid_rows, invalid_rows):
        """
        Feature: job-application-tracker, Property 27: Import Summary Accuracy
        
        For any CSV import operation, the import summary should accurately report
        the total number of rows processed, number of successful imports, and
        number of failed imports, where successful + failed = total.
        
        Validates: Requirements 11.4
        """
        with temp_service() as service:
            # Combine valid and invalid rows
            all_rows = valid_rows + invalid_rows
            
            # Create CSV content
            csv_content = create_csv_content(all_rows)
            csv_bytes = csv_content.encode('utf-8')
            
            # Import CSV
            result = service.import_from_csv(csv_bytes)
            
            # Verify summary accuracy
            assert result.total_rows == len(all_rows), \
                f"Total rows mismatch: expected {len(all_rows)}, got {result.total_rows}"
            
            assert result.successful + result.failed == result.total_rows, \
                f"successful ({result.successful}) + failed ({result.failed}) != total ({result.total_rows})"
            
            # Verify successful count matches valid rows
            assert result.successful == len(valid_rows), \
                f"Expected {len(valid_rows)} successful, got {result.successful}"
            
            # Verify failed count matches invalid rows
            assert result.failed == len(invalid_rows), \
                f"Expected {len(invalid_rows)} failed, got {result.failed}"
            
            # Verify error count matches failed count
            assert len(result.errors) == result.failed, \
                f"Error count ({len(result.errors)}) != failed count ({result.failed})"


class TestCSVExportProperties:
    """
    Property 28: Export Data Completeness
    Property 29: Filtered Export Correctness
    Property 30: Export Date Format Compliance
    
    Tests that CSV export produces complete data, respects filters, and
    formats dates correctly.
    """
    
    @given(apps=st.lists(valid_application_for_export_strategy(), min_size=1, max_size=10))
    @settings(max_examples=100, deadline=None)
    def test_property_28_export_data_completeness(self, apps):
        """
        Feature: job-application-tracker, Property 28: Export Data Completeness
        
        For any set of applications, exporting to CSV should produce a file that,
        when parsed, contains all application data including all fields.
        
        Validates: Requirements 12.1, 12.2
        """
        with temp_service() as service:
            # Create applications
            created_apps = []
            for app_data in apps:
                created = service.create_application(app_data)
                created_apps.append(created)
            
            # Export to CSV
            csv_content = service.export_to_csv()
            
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            exported_rows = list(csv_reader)
            
            # Verify all applications are in export
            assert len(exported_rows) == len(created_apps), \
                f"Expected {len(created_apps)} rows, got {len(exported_rows)}"
            
            # Verify all required fields are present
            required_fields = [
                'id', 'company_name', 'position_title', 'stage',
                'application_date', 'created_at', 'updated_at'
            ]
            
            for row in exported_rows:
                for field in required_fields:
                    assert field in row, f"Missing required field: {field}"
                    assert row[field], f"Empty required field: {field}"
            
            # Verify data matches created applications
            for created_app in created_apps:
                # Find matching row
                matching_rows = [
                    row for row in exported_rows
                    if row['id'] == created_app.id
                ]
                
                assert len(matching_rows) == 1, \
                    f"Expected 1 matching row for {created_app.id}, got {len(matching_rows)}"
                
                row = matching_rows[0]
                
                # Verify key fields match
                assert row['company_name'] == created_app.company_name, \
                    "Company name mismatch in export"
                assert row['position_title'] == created_app.position_title, \
                    "Position title mismatch in export"
                assert row['stage'] == created_app.stage.value, \
                    "Stage mismatch in export"
    
    @given(
        apps=st.lists(valid_application_for_export_strategy(), min_size=5, max_size=10),
        filter_stage=st.sampled_from(Stage)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_29_filtered_export_correctness(self, apps, filter_stage):
        """
        Feature: job-application-tracker, Property 29: Filtered Export Correctness
        
        For any active filters and any set of applications, exporting should produce
        a CSV containing only the applications matching the filter criteria.
        
        Validates: Requirements 12.3
        """
        # Ensure we have at least one app with the filter stage
        assume(any(app.stage == filter_stage for app in apps))
        
        with temp_service() as service:
            # Create applications
            created_apps = []
            for app_data in apps:
                created = service.create_application(app_data)
                created_apps.append(created)
            
            # Count expected matches
            expected_count = sum(1 for app in created_apps if app.stage == filter_stage)
            
            # Export with filter
            filters = ApplicationFilters(stage=filter_stage)
            csv_content = service.export_to_csv(filters)
            
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            exported_rows = list(csv_reader)
            
            # Verify only filtered applications are exported
            assert len(exported_rows) == expected_count, \
                f"Expected {expected_count} rows with stage {filter_stage.value}, got {len(exported_rows)}"
            
            # Verify all exported rows match the filter
            for row in exported_rows:
                assert row['stage'] == filter_stage.value, \
                    f"Exported row has wrong stage: {row['stage']} != {filter_stage.value}"
    
    @given(apps=st.lists(valid_application_for_export_strategy(), min_size=1, max_size=10))
    @settings(max_examples=100, deadline=None)
    def test_property_30_export_date_format_compliance(self, apps):
        """
        Feature: job-application-tracker, Property 30: Export Date Format Compliance
        
        For any exported CSV file, all date fields should be formatted in
        ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ).
        
        Validates: Requirements 12.4
        """
        with temp_service() as service:
            # Create applications
            for app_data in apps:
                service.create_application(app_data)
            
            # Export to CSV
            csv_content = service.export_to_csv()
            
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            exported_rows = list(csv_reader)
            
            # Date fields to check
            date_fields = ['application_date', 'created_at', 'updated_at']
            
            for row in exported_rows:
                for field in date_fields:
                    date_str = row[field]
                    
                    # Verify field is not empty
                    assert date_str, f"Date field {field} is empty"
                    
                    # Verify ISO 8601 format by parsing
                    try:
                        parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        
                        # Verify the format matches ISO 8601
                        # Should contain 'T' separator and have time component
                        assert 'T' in date_str, \
                            f"Date {date_str} missing 'T' separator (not ISO 8601)"
                        
                        # Verify it can be round-tripped
                        reformatted = parsed_date.isoformat()
                        assert reformatted.startswith(date_str.split('+')[0].split('Z')[0]), \
                            f"Date format not ISO 8601 compliant: {date_str}"
                        
                    except ValueError as e:
                        pytest.fail(f"Date field {field} has invalid ISO 8601 format: {date_str} - {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
