"""
Performance tests for Job Application Tracker with large datasets.

Tests verify that the system performs efficiently with 100+ applications,
including Kanban board rendering, search/filter operations, and drag-and-drop.

Validates: Requirements 2.5
"""

import pytest
import time
import json
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
def large_dataset(service) -> List[Application]:
    """Create 100+ applications for performance testing."""
    companies = [
        "TechCorp", "DataSystems", "CloudInnovate", "AIStartup", "DevTools",
        "SecureNet", "FinTech Solutions", "HealthTech", "EduPlatform", "GameStudio",
        "MediaGroup", "RetailTech", "LogisticsHub", "EnergyTech", "BioInnovate",
        "RoboticsCo", "SpaceTech", "QuantumLabs", "NanoSystems", "GreenEnergy"
    ]
    
    positions = [
        "Senior Software Engineer", "Backend Developer", "Frontend Developer",
        "Full Stack Engineer", "DevOps Engineer", "Data Scientist",
        "Machine Learning Engineer", "Product Manager", "Engineering Manager",
        "Technical Lead", "Solutions Architect", "Security Engineer"
    ]
    
    stages = list(Stage)
    applications = []
    
    # Create 120 applications
    for i in range(120):
        company = companies[i % len(companies)]
        position = positions[i % len(positions)]
        stage = stages[i % len(stages)]
        
        # Vary application dates over the past 90 days
        days_ago = i % 90
        app_date = datetime.now() - timedelta(days=days_ago)
        
        request = CreateApplicationRequest(
            company_name=f"{company} {i // len(companies) + 1}",
            position_title=position,
            stage=stage,
            application_date=app_date,
            job_description_url=f"https://example.com/job/{i}",
            notes=f"Application notes for position {i}"
        )
        
        app = service.create_application(request)
        applications.append(app)
    
    return applications


class TestLargeDatasetPerformance:
    """Test performance with 100+ applications."""
    
    def test_list_all_applications_performance(self, service, large_dataset):
        """Test that listing all applications completes quickly."""
        # Warm up
        service.list_applications(ApplicationFilters())
        
        # Measure performance
        start_time = time.time()
        applications = service.list_applications(ApplicationFilters())
        elapsed_time = time.time() - start_time
        
        # Verify correctness
        assert len(applications) == 120
        
        # Performance assertion: should complete in under 1 second
        assert elapsed_time < 1.0, f"Listing 120 applications took {elapsed_time:.3f}s (expected < 1.0s)"
        
        print(f"\n✓ Listed 120 applications in {elapsed_time:.3f}s")
    
    def test_search_performance(self, service, large_dataset):
        """Test search performance with large dataset."""
        # Test search by company name
        start_time = time.time()
        results = service.list_applications(
            ApplicationFilters(search="TechCorp")
        )
        elapsed_time = time.time() - start_time
        
        # Verify results
        assert len(results) > 0
        assert all("TechCorp" in app.company_name for app in results)
        
        # Performance assertion: should complete in under 0.5 seconds
        assert elapsed_time < 0.5, f"Search took {elapsed_time:.3f}s (expected < 0.5s)"
        
        print(f"\n✓ Search completed in {elapsed_time:.3f}s, found {len(results)} results")
    
    def test_stage_filter_performance(self, service, large_dataset):
        """Test stage filtering performance with large dataset."""
        start_time = time.time()
        results = service.list_applications(
            ApplicationFilters(stage=Stage.INTERVIEW)
        )
        elapsed_time = time.time() - start_time
        
        # Verify results
        assert len(results) > 0
        assert all(app.stage == Stage.INTERVIEW for app in results)
        
        # Performance assertion: should complete in under 0.5 seconds
        assert elapsed_time < 0.5, f"Stage filter took {elapsed_time:.3f}s (expected < 0.5s)"
        
        print(f"\n✓ Stage filter completed in {elapsed_time:.3f}s, found {len(results)} results")
    
    def test_date_range_filter_performance(self, service, large_dataset):
        """Test date range filtering performance with large dataset."""
        date_from = datetime.now() - timedelta(days=30)
        date_to = datetime.now()
        
        start_time = time.time()
        results = service.list_applications(
            ApplicationFilters(date_from=date_from, date_to=date_to)
        )
        elapsed_time = time.time() - start_time
        
        # Verify results
        assert len(results) > 0
        assert all(date_from <= app.application_date <= date_to for app in results)
        
        # Performance assertion: should complete in under 0.5 seconds
        assert elapsed_time < 0.5, f"Date filter took {elapsed_time:.3f}s (expected < 0.5s)"
        
        print(f"\n✓ Date range filter completed in {elapsed_time:.3f}s, found {len(results)} results")
    
    def test_combined_filters_performance(self, service, large_dataset):
        """Test performance with multiple filters applied."""
        date_from = datetime.now() - timedelta(days=60)
        
        start_time = time.time()
        results = service.list_applications(
            ApplicationFilters(
                search="Engineer",
                stage=Stage.APPLIED,
                date_from=date_from
            )
        )
        elapsed_time = time.time() - start_time
        
        # Verify results match all criteria
        for app in results:
            assert "Engineer" in app.position_title or "Engineer" in app.company_name
            assert app.stage == Stage.APPLIED
            assert app.application_date >= date_from
        
        # Performance assertion: should complete in under 0.5 seconds
        assert elapsed_time < 0.5, f"Combined filters took {elapsed_time:.3f}s (expected < 0.5s)"
        
        print(f"\n✓ Combined filters completed in {elapsed_time:.3f}s, found {len(results)} results")
    
    def test_stage_transition_performance(self, service, large_dataset):
        """Test that stage transitions remain fast with large dataset."""
        # Pick a random application
        app = large_dataset[50]
        
        from app.models.application_tracker_models import StageChangeRequest
        
        start_time = time.time()
        updated = service.change_stage(app.id, StageChangeRequest(new_stage=Stage.OFFER))
        elapsed_time = time.time() - start_time
        
        # Verify correctness
        assert updated.stage == Stage.OFFER
        
        # Performance assertion: should complete in under 0.2 seconds
        assert elapsed_time < 0.2, f"Stage transition took {elapsed_time:.3f}s (expected < 0.2s)"
        
        print(f"\n✓ Stage transition completed in {elapsed_time:.3f}s")
    
    def test_get_single_application_performance(self, service, large_dataset):
        """Test that retrieving a single application is fast."""
        app_id = large_dataset[75].id
        
        # Warm up
        service.get_application(app_id)
        
        # Measure performance
        start_time = time.time()
        app = service.get_application(app_id)
        elapsed_time = time.time() - start_time
        
        # Verify correctness
        assert app.id == app_id
        
        # Performance assertion: should complete in under 0.1 seconds
        assert elapsed_time < 0.1, f"Get application took {elapsed_time:.3f}s (expected < 0.1s)"
        
        print(f"\n✓ Get single application completed in {elapsed_time:.3f}s")
    
    def test_storage_file_size(self, service, large_dataset, storage):
        """Verify storage file size is reasonable with 100+ applications."""
        # Force a save to ensure file is written
        service.list_applications(ApplicationFilters())
        
        # Check file size
        import os
        file_size = os.path.getsize(storage.applications_file)
        file_size_kb = file_size / 1024
        
        # File should be under 500KB for 120 applications
        assert file_size_kb < 500, f"Storage file is {file_size_kb:.1f}KB (expected < 500KB)"
        
        print(f"\n✓ Storage file size: {file_size_kb:.1f}KB for 120 applications")
    
    def test_memory_efficiency(self, service, large_dataset):
        """Test that loading large dataset doesn't consume excessive memory."""
        import sys
        
        # Get initial memory usage
        initial_size = sys.getsizeof(large_dataset)
        
        # Load all applications
        applications = service.list_applications(ApplicationFilters())
        loaded_size = sys.getsizeof(applications)
        
        # Memory should be reasonable (under 10MB for 120 applications)
        assert loaded_size < 10 * 1024 * 1024, f"Loaded data uses {loaded_size / 1024 / 1024:.1f}MB"
        
        print(f"\n✓ Memory usage: {loaded_size / 1024:.1f}KB for 120 applications")


class TestKanbanBoardRenderingPerformance:
    """Test Kanban board rendering performance with large datasets."""
    
    def test_group_by_stage_performance(self, service, large_dataset):
        """Test performance of grouping applications by stage."""
        applications = service.list_applications(ApplicationFilters())
        
        start_time = time.time()
        
        # Simulate grouping by stage (as frontend would do)
        grouped = {}
        for stage in Stage:
            grouped[stage] = [app for app in applications if app.stage == stage]
        
        elapsed_time = time.time() - start_time
        
        # Verify all applications are grouped
        total = sum(len(apps) for apps in grouped.values())
        assert total == 120
        
        # Performance assertion: should complete in under 0.1 seconds
        assert elapsed_time < 0.1, f"Grouping took {elapsed_time:.3f}s (expected < 0.1s)"
        
        print(f"\n✓ Grouped 120 applications by stage in {elapsed_time:.3f}s")
    
    def test_sort_by_date_performance(self, service, large_dataset):
        """Test performance of sorting applications by date."""
        applications = service.list_applications(ApplicationFilters())
        
        start_time = time.time()
        sorted_apps = sorted(applications, key=lambda x: x.application_date, reverse=True)
        elapsed_time = time.time() - start_time
        
        # Verify sorting
        assert len(sorted_apps) == 120
        for i in range(len(sorted_apps) - 1):
            assert sorted_apps[i].application_date >= sorted_apps[i + 1].application_date
        
        # Performance assertion: should complete in under 0.05 seconds
        assert elapsed_time < 0.05, f"Sorting took {elapsed_time:.3f}s (expected < 0.05s)"
        
        print(f"\n✓ Sorted 120 applications by date in {elapsed_time:.3f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
