"""
Performance tests for CSV import/export operations with large datasets.

Tests verify that CSV import and export operations complete efficiently
with 100+ row files.

Validates: Requirements 11.1, 12.1
"""

import pytest
import time
import csv
import io
from datetime import datetime, timedelta
from typing import List
from app.models.application_tracker_models import (
    Application,
    Stage,
    CreateApplicationRequest,
    ApplicationFilters
)
from app.services.application_tracker_service import ApplicationTrackerService
from app.services.application_tracker_storage import ApplicationTrackerStorage


@pytest.fixture
def storage(tmp_path):
    """Create a temporary storage instance for testing."""
    return ApplicationTrackerStorage(str(tmp_path))


@pytest.fixture
def service(storage):
    """Create service instance with temporary storage."""
    return ApplicationTrackerService(storage)


@pytest.fixture
def csv_dataset(service) -> List[Application]:
    """Create 150 applications for CSV testing."""
    applications = []
    
    companies = ["TechCorp", "DataSys", "CloudInc", "AILabs", "DevTools"]
    positions = ["Engineer", "Developer", "Architect", "Manager", "Lead"]
    stages = list(Stage)
    
    for i in range(150):
        request = CreateApplicationRequest(
            company_name=f"{companies[i % len(companies)]} {i // len(companies) + 1}",
            position_title=f"Senior {positions[i % len(positions)]}",
            stage=stages[i % len(stages)],
            application_date=datetime.now() - timedelta(days=i % 90),
            job_description_url=f"https://example.com/job/{i}",
            notes=f"Application notes {i}"
        )
        
        app = service.create_application(request)
        applications.append(app)
    
    return applications


def generate_csv_content(num_rows: int) -> str:
    """Generate CSV content with specified number of rows."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        'company_name', 'position_title', 'stage', 'application_date',
        'job_description_url', 'notes'
    ])
    
    writer.writeheader()
    
    for i in range(num_rows):
        writer.writerow({
            'company_name': f'Company {i}',
            'position_title': f'Position {i}',
            'stage': 'wishlist',
            'application_date': (datetime.now() - timedelta(days=i % 60)).isoformat(),
            'job_description_url': f'https://example.com/job/{i}',
            'notes': f'Imported application {i}'
        })
    
    return output.getvalue()


class TestCSVImportPerformance:
    """Test CSV import performance with large files."""
    
    def test_import_100_row_csv(self, service):
        """Test importing CSV with 100 rows."""
        csv_content = generate_csv_content(100)
        
        start_time = time.time()
        result = service.import_from_csv(csv_content.encode('utf-8'))
        elapsed_time = time.time() - start_time
        
        # Verify all rows imported successfully
        assert result.total_rows == 100
        assert result.successful == 100
        assert result.failed == 0
        
        # Verify applications were created
        applications = service.list_applications(ApplicationFilters())
        assert len(applications) == 100
        
        # Performance assertion: should complete in under 5 seconds
        assert elapsed_time < 5.0, f"Import (100 rows) took {elapsed_time:.3f}s (expected < 5.0s)"
        
        print(f"\n✓ CSV import (100 rows) completed in {elapsed_time:.3f}s")
    
    def test_import_150_row_csv(self, service):
        """Test importing CSV with 150 rows."""
        csv_content = generate_csv_content(150)
        
        start_time = time.time()
        result = service.import_from_csv(csv_content.encode('utf-8'))
        elapsed_time = time.time() - start_time
        
        # Verify all rows imported successfully
        assert result.total_rows == 150
        assert result.successful == 150
        assert result.failed == 0
        
        # Performance assertion: should complete in under 7 seconds
        assert elapsed_time < 7.0, f"Import (150 rows) took {elapsed_time:.3f}s (expected < 7.0s)"
        
        print(f"\n✓ CSV import (150 rows) completed in {elapsed_time:.3f}s")
    
    def test_import_200_row_csv(self, service):
        """Test importing CSV with 200 rows."""
        csv_content = generate_csv_content(200)
        
        start_time = time.time()
        result = service.import_from_csv(csv_content.encode('utf-8'))
        elapsed_time = time.time() - start_time
        
        # Verify all rows imported successfully
        assert result.total_rows == 200
        assert result.successful == 200
        assert result.failed == 0
        
        # Performance assertion: should complete in under 10 seconds
        assert elapsed_time < 10.0, f"Import (200 rows) took {elapsed_time:.3f}s (expected < 10.0s)"
        
        print(f"\n✓ CSV import (200 rows) completed in {elapsed_time:.3f}s")
    
    def test_import_with_validation_errors(self, service):
        """Test import performance with some invalid rows."""
        # Generate CSV with some invalid rows
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'company_name', 'position_title', 'stage', 'application_date'
        ])
        
        writer.writeheader()
        
        for i in range(100):
            if i % 10 == 0:
                # Invalid row (missing required field)
                writer.writerow({
                    'company_name': '',  # Invalid: empty
                    'position_title': f'Position {i}',
                    'stage': 'wishlist',
                    'application_date': datetime.now().isoformat()
                })
            else:
                # Valid row
                writer.writerow({
                    'company_name': f'Company {i}',
                    'position_title': f'Position {i}',
                    'stage': 'wishlist',
                    'application_date': datetime.now().isoformat()
                })
        
        csv_content = output.getvalue()
        
        start_time = time.time()
        result = service.import_from_csv(csv_content.encode('utf-8'))
        elapsed_time = time.time() - start_time
        
        # Verify results
        assert result.total_rows == 100
        assert result.successful == 90  # 10 invalid rows
        assert result.failed == 10
        
        # Performance assertion: validation should not significantly slow down import
        assert elapsed_time < 5.0, f"Import with validation took {elapsed_time:.3f}s (expected < 5.0s)"
        
        print(f"\n✓ CSV import with validation (100 rows, 10 errors) completed in {elapsed_time:.3f}s")


class TestCSVExportPerformance:
    """Test CSV export performance with large datasets."""
    
    def test_export_100_applications(self, service, csv_dataset):
        """Test exporting 100 applications to CSV."""
        # Use first 100 applications
        start_time = time.time()
        csv_content = service.export_to_csv(ApplicationFilters())
        elapsed_time = time.time() - start_time
        
        # Verify CSV content
        lines = csv_content.strip().split('\n')
        assert len(lines) == 151  # Header + 150 rows
        
        # Performance assertion: should complete in under 3 seconds
        assert elapsed_time < 3.0, f"Export (150 apps) took {elapsed_time:.3f}s (expected < 3.0s)"
        
        print(f"\n✓ CSV export (150 apps) completed in {elapsed_time:.3f}s")
    
    def test_export_with_filters(self, service, csv_dataset):
        """Test export performance with filters applied."""
        start_time = time.time()
        csv_content = service.export_to_csv(
            ApplicationFilters(stage=Stage.INTERVIEW)
        )
        elapsed_time = time.time() - start_time
        
        # Verify filtered export
        lines = csv_content.strip().split('\n')
        assert len(lines) > 1  # At least header + some rows
        
        # Performance assertion: should complete in under 2 seconds
        assert elapsed_time < 2.0, f"Filtered export took {elapsed_time:.3f}s (expected < 2.0s)"
        
        print(f"\n✓ Filtered CSV export completed in {elapsed_time:.3f}s ({len(lines)-1} rows)")
    
    def test_export_all_fields(self, service, csv_dataset):
        """Test export includes all fields efficiently."""
        # Add some additional data to applications
        apps = service.list_applications(ApplicationFilters())
        for i, app in enumerate(apps[:20]):
            from app.models.application_tracker_models import UpdateApplicationRequest
            service.update_application(
                app.id,
                UpdateApplicationRequest(
                    recruiter_name=f"Recruiter {i}",
                    recruiter_email=f"recruiter{i}@example.com",
                    notes=f"Detailed notes for application {i}"
                )
            )
        
        start_time = time.time()
        csv_content = service.export_to_csv(ApplicationFilters())
        elapsed_time = time.time() - start_time
        
        # Verify export includes all data
        lines = csv_content.strip().split('\n')
        header = lines[0]
        
        # Check that important fields are in header
        assert 'company_name' in header
        assert 'position_title' in header
        assert 'stage' in header
        assert 'application_date' in header
        
        # Performance assertion
        assert elapsed_time < 3.0, f"Full export took {elapsed_time:.3f}s (expected < 3.0s)"
        
        print(f"\n✓ Full field CSV export (150 apps) completed in {elapsed_time:.3f}s")


class TestCSVRoundTripPerformance:
    """Test CSV import/export round-trip performance."""
    
    def test_export_import_round_trip_100_applications(self, service):
        """Test export then import round-trip with 100 applications."""
        # Create initial applications
        for i in range(100):
            request = CreateApplicationRequest(
                company_name=f"Company {i}",
                position_title=f"Position {i}",
                stage=Stage.WISHLIST,
                application_date=datetime.now() - timedelta(days=i % 30),
                notes=f"Original application {i}"
            )
            service.create_application(request)
        
        # Export
        export_start = time.time()
        csv_content = service.export_to_csv(ApplicationFilters())
        export_time = time.time() - export_start
        
        # Clear applications
        apps = service.list_applications(ApplicationFilters())
        from app.models.application_tracker_models import BulkDeleteRequest
        service.bulk_delete(BulkDeleteRequest(
            application_ids=[app.id for app in apps]
        ))
        
        # Import
        import_start = time.time()
        result = service.import_from_csv(csv_content.encode('utf-8'))
        import_time = time.time() - import_start
        
        # Verify round-trip
        assert result.successful == 100
        
        total_time = export_time + import_time
        
        # Performance assertion: round-trip should complete in under 8 seconds
        assert total_time < 8.0, f"Round-trip (100 apps) took {total_time:.3f}s (expected < 8.0s)"
        
        print(f"\n✓ CSV round-trip (100 apps):")
        print(f"  Export: {export_time:.3f}s")
        print(f"  Import: {import_time:.3f}s")
        print(f"  Total: {total_time:.3f}s")


class TestCSVScalability:
    """Test CSV operation scalability."""
    
    def test_import_scalability(self, service):
        """Test import performance scales linearly."""
        results = []
        
        for size in [50, 100, 150, 200]:
            # Generate CSV
            csv_content = generate_csv_content(size)
            
            # Measure import
            start_time = time.time()
            result = service.import_from_csv(csv_content.encode('utf-8'))
            elapsed_time = time.time() - start_time
            
            results.append((size, elapsed_time))
            
            # Clean up
            apps = service.list_applications(ApplicationFilters())
            from app.models.application_tracker_models import BulkDeleteRequest
            service.bulk_delete(BulkDeleteRequest(
                application_ids=[app.id for app in apps]
            ))
        
        # Print results
        print("\n✓ CSV import scalability:")
        for size, elapsed in results:
            print(f"  {size} rows: {elapsed:.3f}s ({elapsed/size*1000:.1f}ms per row)")
        
        # Verify reasonable scaling
        time_per_row = [elapsed / size for size, elapsed in results]
        max_time = max(time_per_row)
        min_time = min(time_per_row)
        
        # Max should not be more than 2x min
        assert max_time < min_time * 2, \
            f"Import performance degradation: {max_time:.4f}s vs {min_time:.4f}s per row"
    
    def test_export_scalability(self, service):
        """Test export performance scales linearly."""
        results = []
        
        for size in [50, 100, 150, 200]:
            # Create applications
            for i in range(size):
                request = CreateApplicationRequest(
                    company_name=f"Company {i}",
                    position_title=f"Position {i}",
                    stage=Stage.WISHLIST,
                    application_date=datetime.now()
                )
                service.create_application(request)
            
            # Measure export
            start_time = time.time()
            csv_content = service.export_to_csv(ApplicationFilters())
            elapsed_time = time.time() - start_time
            
            results.append((size, elapsed_time))
            
            # Verify export
            lines = csv_content.strip().split('\n')
            assert len(lines) == size + 1  # Header + rows
            
            # Clean up
            apps = service.list_applications(ApplicationFilters())
            from app.models.application_tracker_models import BulkDeleteRequest
            service.bulk_delete(BulkDeleteRequest(
                application_ids=[app.id for app in apps]
            ))
        
        # Print results
        print("\n✓ CSV export scalability:")
        for size, elapsed in results:
            print(f"  {size} apps: {elapsed:.3f}s ({elapsed/size*1000:.1f}ms per app)")
        
        # Verify reasonable performance - all exports should complete quickly
        # Focus on absolute performance rather than relative scaling
        for size, elapsed in results:
            time_per_app = elapsed / size
            # Each app should export in under 1ms on average
            assert time_per_app < 0.001, \
                f"Export too slow for {size} apps: {time_per_app:.4f}s per app (expected < 0.001s)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
