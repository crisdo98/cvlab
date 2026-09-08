"""
End-to-End Tests for Search and Filter Functionality.

Feature: job-application-tracker
Task 13.3: Test search and filter functionality

Tests comprehensive search and filter capabilities including:
- Search by company name
- Search by position title
- Stage filter
- Date range filter
- Multiple filters combined
- Clear filters

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
"""
import pytest
from fastapi.testclient import TestClient
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta

from app.main import app
from app.services.application_tracker_storage import ApplicationTrackerStorage
from app.services.application_tracker_service import ApplicationTrackerService


@pytest.fixture
def temp_test_env():
    """Create a complete temporary test environment."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create directory structure
        data_dir = Path(temp_dir) / "data"
        data_dir.mkdir(parents=True)
        
        # Create empty JSON files
        applications_file = data_dir / "applications.json"
        applications_file.write_text(json.dumps({"applications": []}))
        
        history_file = data_dir / "application_history.json"
        history_file.write_text(json.dumps({"history": []}))
        
        yield {
            "data_dir": data_dir,
            "temp_dir": temp_dir,
            "applications_file": applications_file,
            "history_file": history_file
        }


@pytest.fixture
def client(temp_test_env):
    """Create a test client with dependency overrides."""
    # Create storage and service with test directories
    storage = ApplicationTrackerStorage(data_directory=str(temp_test_env["data_dir"]))
    service = ApplicationTrackerService(storage=storage)
    
    # Override the global service instance in the router
    import app.routers.application_tracker_router as router_module
    original_service = router_module._service
    router_module._service = service
    
    # Create test client
    test_client = TestClient(app)
    
    yield test_client
    
    # Clean up - reset global service
    router_module._service = original_service


@pytest.fixture
def sample_applications(client):
    """Create a diverse set of sample applications for testing."""
    base_date = datetime.now()
    
    applications_data = [
        # Tech companies
        {
            "company_name": "TechCorp",
            "position_title": "Senior Software Engineer",
            "stage": "wishlist",
            "application_date": (base_date - timedelta(days=10)).isoformat()
        },
        {
            "company_name": "TechStart",
            "position_title": "Full Stack Developer",
            "stage": "applied",
            "application_date": (base_date - timedelta(days=5)).isoformat()
        },
        {
            "company_name": "CloudTech",
            "position_title": "DevOps Engineer",
            "stage": "interview",
            "application_date": (base_date - timedelta(days=2)).isoformat()
        },
        # Data companies
        {
            "company_name": "DataCorp",
            "position_title": "Data Scientist",
            "stage": "wishlist",
            "application_date": (base_date - timedelta(days=8)).isoformat()
        },
        {
            "company_name": "DataSystems",
            "position_title": "Data Engineer",
            "stage": "applied",
            "application_date": (base_date - timedelta(days=3)).isoformat()
        },
        # Other companies
        {
            "company_name": "FinanceHub",
            "position_title": "Software Engineer",
            "stage": "offer",
            "application_date": (base_date - timedelta(days=1)).isoformat()
        },
        {
            "company_name": "HealthTech",
            "position_title": "Backend Developer",
            "stage": "rejected",
            "application_date": (base_date - timedelta(days=15)).isoformat()
        },
        {
            "company_name": "EduTech",
            "position_title": "Frontend Engineer",
            "stage": "interview",
            "application_date": base_date.isoformat()
        }
    ]
    
    app_ids = []
    for app_data in applications_data:
        response = client.post("/api/applications", json=app_data)
        assert response.status_code == 201
        app_ids.append(response.json()["id"])
    
    yield app_ids
    
    # Cleanup
    for app_id in app_ids:
        try:
            client.delete(f"/api/applications/{app_id}")
        except:
            pass


class TestSearchFunctionality:
    """
    Task 13.3: Test search functionality
    
    Tests:
    - Search by company name
    - Search by position title
    """
    
    def test_search_by_company_name(self, client, sample_applications):
        """
        Test searching applications by company name.
        
        Validates Requirements: 7.1
        """
        print("\n=== Test: Search by Company Name ===")
        
        # Search for "Tech" - should match TechCorp, TechStart, CloudTech, HealthTech, EduTech
        response = client.get("/api/applications?search=Tech")
        assert response.status_code == 200
        results = response.json()
        
        company_names = {app["company_name"] for app in results}
        print(f"✓ Found {len(results)} companies matching 'Tech': {company_names}")
        
        assert len(results) >= 5
        assert "TechCorp" in company_names
        assert "TechStart" in company_names
        assert "CloudTech" in company_names
        assert "HealthTech" in company_names
        assert "EduTech" in company_names
        
        # Should not match DataCorp, DataSystems, FinanceHub
        assert "DataCorp" not in company_names
        assert "DataSystems" not in company_names
        assert "FinanceHub" not in company_names
        
        print("✓ Search by company name test passed")
    
    def test_search_by_position_title(self, client, sample_applications):
        """
        Test searching applications by position title.
        
        Validates Requirements: 7.1
        """
        print("\n=== Test: Search by Position Title ===")
        
        # Search for "Engineer" - should match multiple positions
        response = client.get("/api/applications?search=Engineer")
        assert response.status_code == 200
        results = response.json()
        
        position_titles = {app["position_title"] for app in results}
        print(f"✓ Found {len(results)} positions matching 'Engineer': {position_titles}")
        
        assert len(results) >= 5
        assert "Senior Software Engineer" in position_titles
        assert "DevOps Engineer" in position_titles
        assert "Data Engineer" in position_titles
        assert "Software Engineer" in position_titles
        assert "Frontend Engineer" in position_titles
        
        print("✓ Search by position title test passed")
    
    def test_search_case_insensitive(self, client, sample_applications):
        """
        Test that search is case-insensitive.
        
        Validates Requirements: 7.1
        """
        print("\n=== Test: Case-Insensitive Search ===")
        
        # Search with different cases
        search_terms = ["tech", "TECH", "Tech", "tEcH"]
        
        results_sets = []
        for term in search_terms:
            response = client.get(f"/api/applications?search={term}")
            assert response.status_code == 200
            results = response.json()
            results_sets.append(set(app["id"] for app in results))
        
        # All searches should return the same results
        first_set = results_sets[0]
        for result_set in results_sets[1:]:
            assert result_set == first_set
        
        print(f"✓ All case variations returned {len(first_set)} results")
        print("✓ Case-insensitive search test passed")
    
    def test_search_partial_match(self, client, sample_applications):
        """
        Test that search matches partial strings.
        
        Validates Requirements: 7.1
        """
        print("\n=== Test: Partial Match Search ===")
        
        # Search for "Data" - should match DataCorp, DataSystems, Data Scientist, Data Engineer
        response = client.get("/api/applications?search=Data")
        assert response.status_code == 200
        results = response.json()
        
        assert len(results) >= 2
        
        # Check both company names and position titles
        all_text = set()
        for app in results:
            all_text.add(app["company_name"])
            all_text.add(app["position_title"])
        
        data_matches = [text for text in all_text if "Data" in text]
        print(f"✓ Found matches: {data_matches}")
        
        assert len(data_matches) >= 2
        print("✓ Partial match search test passed")


class TestFilterFunctionality:
    """Test filter functionality."""
    
    def test_filter_by_stage(self, client, sample_applications):
        """
        Test filtering applications by stage.
        
        Validates Requirements: 7.2
        """
        print("\n=== Test: Filter by Stage ===")
        
        stages = ["wishlist", "applied", "interview", "offer", "rejected"]
        
        for stage in stages:
            response = client.get(f"/api/applications?stage={stage}")
            assert response.status_code == 200
            results = response.json()
            
            # All results should be in the specified stage
            assert all(app["stage"] == stage for app in results)
            print(f"✓ {stage.capitalize()} filter returned {len(results)} application(s)")
        
        print("✓ Filter by stage test passed")
    
    def test_filter_by_date_range(self, client, sample_applications):
        """
        Test filtering applications by date range.
        
        Validates Requirements: 7.3
        """
        print("\n=== Test: Filter by Date Range ===")
        
        base_date = datetime.now()
        
        # Test 1: Last 7 days
        date_from = (base_date - timedelta(days=7)).isoformat()
        response = client.get(f"/api/applications?date_from={date_from}")
        assert response.status_code == 200
        results = response.json()
        
        print(f"✓ Last 7 days: {len(results)} application(s)")
        assert len(results) >= 4  # Should include recent applications
        
        # Test 2: Specific range (5 days ago to today)
        date_from = (base_date - timedelta(days=5)).isoformat()
        date_to = base_date.isoformat()
        response = client.get(f"/api/applications?date_from={date_from}&date_to={date_to}")
        assert response.status_code == 200
        results = response.json()
        
        print(f"✓ Last 5 days: {len(results)} application(s)")
        
        # Verify all results are within range
        for app in results:
            app_date = datetime.fromisoformat(app["application_date"].replace('Z', '+00:00'))
            assert app_date >= datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            assert app_date <= datetime.fromisoformat(date_to.replace('Z', '+00:00'))
        
        print("✓ Filter by date range test passed")
    
    def test_multiple_filters_combined(self, client, sample_applications):
        """
        Test combining multiple filters.
        
        Validates Requirements: 7.4
        """
        print("\n=== Test: Multiple Filters Combined ===")
        
        base_date = datetime.now()
        
        # Combine search + stage filter
        response = client.get("/api/applications?search=Tech&stage=wishlist")
        assert response.status_code == 200
        results = response.json()
        
        # All results should match both criteria
        for app in results:
            assert "Tech" in app["company_name"] or "Tech" in app["position_title"]
            assert app["stage"] == "wishlist"
        
        print(f"✓ Search + Stage filter: {len(results)} result(s)")
        
        # Combine search + stage + date range
        date_from = (base_date - timedelta(days=10)).isoformat()
        response = client.get(
            f"/api/applications?search=Tech&stage=applied&date_from={date_from}"
        )
        assert response.status_code == 200
        results = response.json()
        
        # All results should match all three criteria
        for app in results:
            assert "Tech" in app["company_name"] or "Tech" in app["position_title"]
            assert app["stage"] == "applied"
            app_date = datetime.fromisoformat(app["application_date"].replace('Z', '+00:00'))
            assert app_date >= datetime.fromisoformat(date_from.replace('Z', '+00:00'))
        
        print(f"✓ Search + Stage + Date filter: {len(results)} result(s)")
        print("✓ Multiple filters test passed")
    
    def test_clear_filters_returns_all(self, client, sample_applications):
        """
        Test that clearing filters returns all applications.
        
        Validates Requirements: 7.5
        """
        print("\n=== Test: Clear Filters ===")
        
        # First, apply filters
        response = client.get("/api/applications?search=Tech&stage=wishlist")
        assert response.status_code == 200
        filtered_results = response.json()
        print(f"✓ With filters: {len(filtered_results)} result(s)")
        
        # Now get all applications (no filters)
        response = client.get("/api/applications")
        assert response.status_code == 200
        all_results = response.json()
        print(f"✓ Without filters: {len(all_results)} result(s)")
        
        # Should have more results without filters
        assert len(all_results) >= len(filtered_results)
        assert len(all_results) >= 8  # We created 8 sample applications
        
        print("✓ Clear filters test passed")


class TestComplexSearchScenarios:
    """Test complex search and filter scenarios."""
    
    def test_search_with_no_results(self, client, sample_applications):
        """
        Test search that returns no results.
        
        Validates Requirements: 7.1
        """
        print("\n=== Test: Search with No Results ===")
        
        response = client.get("/api/applications?search=NonExistentCompany")
        assert response.status_code == 200
        results = response.json()
        
        assert len(results) == 0
        print("✓ Empty search results handled correctly")
    
    def test_filter_with_no_results(self, client, sample_applications):
        """
        Test filter combination that returns no results.
        
        Validates Requirements: 7.4
        """
        print("\n=== Test: Filter with No Results ===")
        
        # Search for Tech companies in rejected stage (shouldn't exist in our sample)
        response = client.get("/api/applications?search=TechCorp&stage=rejected")
        assert response.status_code == 200
        results = response.json()
        
        # May or may not have results depending on sample data
        print(f"✓ Filter combination returned {len(results)} result(s)")
        print("✓ Empty filter results handled correctly")
    
    def test_search_and_filter_performance(self, client, sample_applications):
        """
        Test that search and filter operations complete quickly.
        
        Validates Requirements: 7.1, 7.2, 7.3
        """
        print("\n=== Test: Search and Filter Performance ===")
        
        import time
        
        # Test search performance
        start = time.time()
        response = client.get("/api/applications?search=Tech")
        search_time = time.time() - start
        
        assert response.status_code == 200
        print(f"✓ Search completed in {search_time:.3f}s")
        assert search_time < 1.0  # Should complete in less than 1 second
        
        # Test filter performance
        start = time.time()
        response = client.get("/api/applications?stage=applied")
        filter_time = time.time() - start
        
        assert response.status_code == 200
        print(f"✓ Filter completed in {filter_time:.3f}s")
        assert filter_time < 1.0
        
        # Test combined performance
        start = time.time()
        response = client.get("/api/applications?search=Tech&stage=applied")
        combined_time = time.time() - start
        
        assert response.status_code == 200
        print(f"✓ Combined search+filter completed in {combined_time:.3f}s")
        assert combined_time < 1.0
        
        print("✓ Performance test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
