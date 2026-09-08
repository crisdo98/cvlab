"""
Performance tests for bulk operations with large datasets.

Tests verify that bulk stage changes and bulk deletes complete efficiently
with 50+ applications.

Validates: Requirements 10.2, 10.3
"""

import pytest
import time
from datetime import datetime, timedelta
from typing import List
from app.models.application_tracker_models import (
    Application,
    Stage,
    CreateApplicationRequest,
    BulkStageChangeRequest,
    BulkDeleteRequest
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
def bulk_dataset(service) -> List[Application]:
    """Create 100 applications for bulk operation testing."""
    applications = []
    
    for i in range(100):
        request = CreateApplicationRequest(
            company_name=f"Company {i}",
            position_title=f"Position {i}",
            stage=Stage.WISHLIST if i < 50 else Stage.APPLIED,
            application_date=datetime.now() - timedelta(days=i % 30),
            notes=f"Test application {i}"
        )
        
        app = service.create_application(request)
        applications.append(app)
    
    return applications


class TestBulkStageChangePerformance:
    """Test bulk stage change performance."""
    
    def test_bulk_stage_change_50_applications(self, service, bulk_dataset):
        """Test bulk stage change with 50 applications."""
        # Select first 50 applications
        app_ids = [app.id for app in bulk_dataset[:50]]
        
        start_time = time.time()
        result = service.bulk_change_stage(
            BulkStageChangeRequest(
                application_ids=app_ids,
                new_stage=Stage.INTERVIEW
            )
        )
        elapsed_time = time.time() - start_time
        
        # Verify all succeeded
        assert len(result.successful) == 50
        assert len(result.failed) == 0
        
        # Verify stage changes
        for app_id in app_ids:
            app = service.get_application(app_id)
            assert app.stage == Stage.INTERVIEW
        
        # Performance assertion: should complete in under 2 seconds
        assert elapsed_time < 2.0, f"Bulk stage change (50) took {elapsed_time:.3f}s (expected < 2.0s)"
        
        print(f"\n✓ Bulk stage change (50 apps) completed in {elapsed_time:.3f}s")
    
    def test_bulk_stage_change_75_applications(self, service, bulk_dataset):
        """Test bulk stage change with 75 applications."""
        # Select 75 applications
        app_ids = [app.id for app in bulk_dataset[:75]]
        
        start_time = time.time()
        result = service.bulk_change_stage(
            BulkStageChangeRequest(
                application_ids=app_ids,
                new_stage=Stage.OFFER
            )
        )
        elapsed_time = time.time() - start_time
        
        # Verify all succeeded
        assert len(result.successful) == 75
        assert len(result.failed) == 0
        
        # Performance assertion: should complete in under 3 seconds
        assert elapsed_time < 3.0, f"Bulk stage change (75) took {elapsed_time:.3f}s (expected < 3.0s)"
        
        print(f"\n✓ Bulk stage change (75 apps) completed in {elapsed_time:.3f}s")
    
    def test_bulk_stage_change_100_applications(self, service, bulk_dataset):
        """Test bulk stage change with all 100 applications."""
        app_ids = [app.id for app in bulk_dataset]
        
        start_time = time.time()
        result = service.bulk_change_stage(
            BulkStageChangeRequest(
                application_ids=app_ids,
                new_stage=Stage.REJECTED
            )
        )
        elapsed_time = time.time() - start_time
        
        # Verify all succeeded
        assert len(result.successful) == 100
        assert len(result.failed) == 0
        
        # Performance assertion: should complete in under 4 seconds
        assert elapsed_time < 4.0, f"Bulk stage change (100) took {elapsed_time:.3f}s (expected < 4.0s)"
        
        print(f"\n✓ Bulk stage change (100 apps) completed in {elapsed_time:.3f}s")
    
    def test_bulk_stage_change_creates_history(self, service, bulk_dataset):
        """Verify bulk stage change creates history entries efficiently."""
        app_ids = [app.id for app in bulk_dataset[:50]]
        
        # Perform bulk stage change
        service.bulk_change_stage(
            BulkStageChangeRequest(
                application_ids=app_ids,
                new_stage=Stage.INTERVIEW
            )
        )
        
        # Verify history was created for each application
        start_time = time.time()
        for app_id in app_ids:
            history = service.get_history(app_id)
            assert len(history) >= 2  # Initial + stage change
            assert history[-1].to_stage == Stage.INTERVIEW
        elapsed_time = time.time() - start_time
        
        # Performance assertion: retrieving history for 50 apps should be fast
        assert elapsed_time < 1.0, f"History retrieval (50 apps) took {elapsed_time:.3f}s (expected < 1.0s)"
        
        print(f"\n✓ History verification (50 apps) completed in {elapsed_time:.3f}s")


class TestBulkDeletePerformance:
    """Test bulk delete performance."""
    
    def test_bulk_delete_50_applications(self, service, bulk_dataset):
        """Test bulk delete with 50 applications."""
        # Select first 50 applications
        app_ids = [app.id for app in bulk_dataset[:50]]
        
        start_time = time.time()
        result = service.bulk_delete(
            BulkDeleteRequest(application_ids=app_ids)
        )
        elapsed_time = time.time() - start_time
        
        # Verify all succeeded
        assert len(result.successful) == 50
        assert len(result.failed) == 0
        
        # Verify applications are deleted
        from app.models.application_tracker_models import ApplicationFilters
        remaining = service.list_applications(ApplicationFilters())
        assert len(remaining) == 50
        
        # Performance assertion: should complete in under 2 seconds
        assert elapsed_time < 2.0, f"Bulk delete (50) took {elapsed_time:.3f}s (expected < 2.0s)"
        
        print(f"\n✓ Bulk delete (50 apps) completed in {elapsed_time:.3f}s")
    
    def test_bulk_delete_75_applications(self, service, bulk_dataset):
        """Test bulk delete with 75 applications."""
        app_ids = [app.id for app in bulk_dataset[:75]]
        
        start_time = time.time()
        result = service.bulk_delete(
            BulkDeleteRequest(application_ids=app_ids)
        )
        elapsed_time = time.time() - start_time
        
        # Verify all succeeded
        assert len(result.successful) == 75
        assert len(result.failed) == 0
        
        # Performance assertion: should complete in under 3 seconds
        assert elapsed_time < 3.0, f"Bulk delete (75) took {elapsed_time:.3f}s (expected < 3.0s)"
        
        print(f"\n✓ Bulk delete (75 apps) completed in {elapsed_time:.3f}s")
    
    def test_bulk_delete_100_applications(self, service, bulk_dataset):
        """Test bulk delete with all 100 applications."""
        app_ids = [app.id for app in bulk_dataset]
        
        start_time = time.time()
        result = service.bulk_delete(
            BulkDeleteRequest(application_ids=app_ids)
        )
        elapsed_time = time.time() - start_time
        
        # Verify all succeeded
        assert len(result.successful) == 100
        assert len(result.failed) == 0
        
        # Verify all applications are deleted
        from app.models.application_tracker_models import ApplicationFilters
        remaining = service.list_applications(ApplicationFilters())
        assert len(remaining) == 0
        
        # Performance assertion: should complete in under 4 seconds
        assert elapsed_time < 4.0, f"Bulk delete (100) took {elapsed_time:.3f}s (expected < 4.0s)"
        
        print(f"\n✓ Bulk delete (100 apps) completed in {elapsed_time:.3f}s")
    
    def test_bulk_delete_with_history_cleanup(self, service, bulk_dataset):
        """Verify bulk delete removes history entries efficiently."""
        app_ids = [app.id for app in bulk_dataset[:50]]
        
        from app.models.application_tracker_models import StageChangeRequest
        
        # Perform some stage changes to create history
        for app_id in app_ids[:10]:
            service.change_stage(app_id, StageChangeRequest(new_stage=Stage.APPLIED))
        
        # Delete applications
        start_time = time.time()
        result = service.bulk_delete(
            BulkDeleteRequest(application_ids=app_ids)
        )
        elapsed_time = time.time() - start_time
        
        # Verify deletion
        assert len(result.successful) == 50
        
        # Performance assertion
        assert elapsed_time < 2.0, f"Bulk delete with history took {elapsed_time:.3f}s (expected < 2.0s)"
        
        print(f"\n✓ Bulk delete with history cleanup (50 apps) completed in {elapsed_time:.3f}s")


class TestBulkOperationScalability:
    """Test bulk operation scalability."""
    
    def test_incremental_bulk_stage_change_performance(self, service):
        """Test performance scales linearly with dataset size."""
        results = []
        
        for size in [10, 25, 50, 75, 100]:
            # Create applications
            apps = []
            for i in range(size):
                request = CreateApplicationRequest(
                    company_name=f"Company {i}",
                    position_title=f"Position {i}",
                    stage=Stage.WISHLIST,
                    application_date=datetime.now()
                )
                apps.append(service.create_application(request))
            
            # Measure bulk stage change
            app_ids = [app.id for app in apps]
            start_time = time.time()
            service.bulk_change_stage(
                BulkStageChangeRequest(
                    application_ids=app_ids,
                    new_stage=Stage.APPLIED
                )
            )
            elapsed_time = time.time() - start_time
            
            results.append((size, elapsed_time))
            
            # Clean up
            service.bulk_delete(BulkDeleteRequest(application_ids=app_ids))
        
        # Print results
        print("\n✓ Bulk stage change scalability:")
        for size, elapsed in results:
            print(f"  {size} apps: {elapsed:.3f}s ({elapsed/size*1000:.1f}ms per app)")
        
        # Verify reasonable scaling (should be roughly linear)
        # Time per app should not increase dramatically
        time_per_app = [elapsed / size for size, elapsed in results]
        max_time_per_app = max(time_per_app)
        min_time_per_app = min(time_per_app)
        
        # Max should not be more than 3x min (allows for some overhead)
        assert max_time_per_app < min_time_per_app * 3, \
            f"Performance degradation detected: {max_time_per_app:.4f}s vs {min_time_per_app:.4f}s per app"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
