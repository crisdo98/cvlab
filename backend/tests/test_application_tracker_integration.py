"""
Integration tests for Application Tracker API endpoints.

Feature: job-application-tracker
Tests the complete application lifecycle through API endpoints,
validating CRUD operations, search/filter, bulk operations, and CSV import/export.

Requirements: 1.1, 1.2, 1.5, 3.1, 7.1, 10.2, 11.1, 12.1
"""
import pytest
from fastapi.testclient import TestClient
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta
import io

from app.main import app
from app.services.application_tracker_storage import ApplicationTrackerStorage
from app.services.application_tracker_service import ApplicationTrackerService
from app.routers import application_tracker_router


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
def sample_application_data():
    """Create sample application data for testing."""
    return {
        "company_name": "TechCorp Inc",
        "position_title": "Senior Software Engineer",
        "stage": "wishlist",
        "application_date": datetime.now().isoformat(),
        "job_description_url": "https://example.com/jobs/123",
        "recruiter_name": "Jane Smith",
        "recruiter_email": "jane.smith@techcorp.com",
        "recruiter_phone": "+1-555-0123",
        "notes": "Referred by John Doe",
        "tasks": ["Update resume", "Prepare cover letter"],
        "follow_up_date": (datetime.now() + timedelta(days=7)).isoformat()
    }


class TestApplicationLifecycle:
    """Test complete application lifecycle through API (create → update → transition → delete)."""
    
    def test_full_application_lifecycle(self, client, sample_application_data):
        """
        Test complete application lifecycle: create, read, update, stage change, delete.
        
        Validates Requirements: 1.1, 1.2, 1.5, 3.1
        """
        # Step 1: Create a new application
        create_response = client.post("/api/applications", json=sample_application_data)
        assert create_response.status_code == 201, f"Failed to create application: {create_response.text}"
        
        created_app = create_response.json()
        assert "id" in created_app
        assert created_app["company_name"] == "TechCorp Inc"
        assert created_app["position_title"] == "Senior Software Engineer"
        assert created_app["stage"] == "wishlist"
        app_id = created_app["id"]
        
        # Step 2: Retrieve the application
        get_response = client.get(f"/api/applications/{app_id}")
        assert get_response.status_code == 200
        retrieved_app = get_response.json()
        assert retrieved_app["id"] == app_id
        assert retrieved_app["company_name"] == "TechCorp Inc"
        assert retrieved_app["recruiter_name"] == "Jane Smith"
        
        # Step 3: List applications and verify it appears
        list_response = client.get("/api/applications")
        assert list_response.status_code == 200
        app_list = list_response.json()
        assert len(app_list) >= 1
        assert any(app["id"] == app_id for app in app_list)
        
        # Step 4: Update the application
        update_data = {
            "company_name": "TechCorp Inc",
            "position_title": "Lead Software Engineer",
            "notes": "Updated notes after initial contact"
        }
        
        update_response = client.put(f"/api/applications/{app_id}", json=update_data)
        assert update_response.status_code == 200
        updated_app = update_response.json()
        assert updated_app["position_title"] == "Lead Software Engineer"
        assert updated_app["notes"] == "Updated notes after initial contact"
        
        # Step 5: Change stage
        stage_change_data = {
            "new_stage": "applied",
            "notes": "Submitted application online"
        }
        
        stage_response = client.patch(f"/api/applications/{app_id}/stage", json=stage_change_data)
        assert stage_response.status_code == 200
        stage_changed_app = stage_response.json()
        assert stage_changed_app["stage"] == "applied"
        
        # Step 6: Verify history was created
        history_response = client.get(f"/api/applications/{app_id}/history")
        assert history_response.status_code == 200
        history = history_response.json()
        assert len(history) >= 2  # Initial creation + stage change
        assert history[-1]["to_stage"] == "applied"
        
        # Step 7: Delete the application
        delete_response = client.delete(f"/api/applications/{app_id}")
        assert delete_response.status_code == 200
        
        # Step 8: Verify deletion
        get_deleted_response = client.get(f"/api/applications/{app_id}")
        assert get_deleted_response.status_code == 404
    
    def test_application_with_interviews(self, client, sample_application_data):
        """
        Test application lifecycle with interview management.
        
        Validates Requirements: 1.1, 1.3, 4.3
        """
        # Add interviews to sample data
        sample_application_data["interviews"] = [
            {
                "date": (datetime.now() + timedelta(days=3)).isoformat(),
                "type": "phone",
                "meeting_link": "https://zoom.us/j/123456",
                "notes": "Initial screening call",
                "interviewer_name": "Bob Johnson"
            }
        ]
        
        # Create application
        create_response = client.post("/api/applications", json=sample_application_data)
        assert create_response.status_code == 201
        app_id = create_response.json()["id"]
        
        # Retrieve and verify interviews
        get_response = client.get(f"/api/applications/{app_id}")
        assert get_response.status_code == 200
        app_data = get_response.json()
        assert len(app_data["interviews"]) == 1
        assert app_data["interviews"][0]["type"] == "phone"
        assert app_data["interviews"][0]["interviewer_name"] == "Bob Johnson"
        
        # Update to add another interview
        app_data["interviews"].append({
            "date": (datetime.now() + timedelta(days=7)).isoformat(),
            "type": "technical",
            "meeting_link": "https://meet.google.com/abc-defg-hij",
            "notes": "Technical coding interview"
        })
        
        update_response = client.put(f"/api/applications/{app_id}", json=app_data)
        assert update_response.status_code == 200
        updated_app = update_response.json()
        assert len(updated_app["interviews"]) == 2
        
        # Cleanup
        client.delete(f"/api/applications/{app_id}")


class TestSearchAndFilter:
    """Test search and filter functionality through API."""
    
    def test_search_by_company_name(self, client):
        """
        Test searching applications by company name.
        
        Validates Requirements: 7.1
        """
        # Create multiple applications
        companies = ["TechCorp", "DataSystems", "CloudTech", "TechStart"]
        app_ids = []
        
        for company in companies:
            app_data = {
                "company_name": company,
                "position_title": "Software Engineer",
                "stage": "wishlist",
                "application_date": datetime.now().isoformat()
            }
            response = client.post("/api/applications", json=app_data)
            assert response.status_code == 201
            app_ids.append(response.json()["id"])
        
        # Search for "Tech" - should match TechCorp, CloudTech, TechStart
        search_response = client.get("/api/applications?search=Tech")
        assert search_response.status_code == 200
        results = search_response.json()
        assert len(results) == 3
        company_names = {app["company_name"] for app in results}
        assert "TechCorp" in company_names
        assert "CloudTech" in company_names
        assert "TechStart" in company_names
        assert "DataSystems" not in company_names
        
        # Cleanup
        for app_id in app_ids:
            client.delete(f"/api/applications/{app_id}")
    
    def test_filter_by_stage(self, client):
        """
        Test filtering applications by stage.
        
        Validates Requirements: 7.2
        """
        # Create applications in different stages
        stages_data = [
            ("Company A", "wishlist"),
            ("Company B", "applied"),
            ("Company C", "interview"),
            ("Company D", "wishlist"),
            ("Company E", "offer")
        ]
        app_ids = []
        
        for company, stage in stages_data:
            app_data = {
                "company_name": company,
                "position_title": "Engineer",
                "stage": stage,
                "application_date": datetime.now().isoformat()
            }
            response = client.post("/api/applications", json=app_data)
            assert response.status_code == 201
            app_ids.append(response.json()["id"])
        
        # Filter by wishlist stage
        filter_response = client.get("/api/applications?stage=wishlist")
        assert filter_response.status_code == 200
        results = filter_response.json()
        assert len(results) == 2
        assert all(app["stage"] == "wishlist" for app in results)
        
        # Filter by interview stage
        filter_response = client.get("/api/applications?stage=interview")
        assert filter_response.status_code == 200
        results = filter_response.json()
        assert len(results) == 1
        assert results[0]["company_name"] == "Company C"
        
        # Cleanup
        for app_id in app_ids:
            client.delete(f"/api/applications/{app_id}")
    
    def test_filter_by_date_range(self, client):
        """
        Test filtering applications by date range.
        
        Validates Requirements: 7.3
        """
        # Create applications with different dates
        base_date = datetime.now()
        dates_data = [
            ("Company A", base_date - timedelta(days=10)),
            ("Company B", base_date - timedelta(days=5)),
            ("Company C", base_date),
            ("Company D", base_date + timedelta(days=5))
        ]
        app_ids = []
        
        for company, date in dates_data:
            app_data = {
                "company_name": company,
                "position_title": "Engineer",
                "stage": "wishlist",
                "application_date": date.isoformat()
            }
            response = client.post("/api/applications", json=app_data)
            assert response.status_code == 201
            app_ids.append(response.json()["id"])
        
        # Filter for last 7 days
        date_from = (base_date - timedelta(days=7)).isoformat()
        filter_response = client.get(f"/api/applications?date_from={date_from}")
        assert filter_response.status_code == 200
        results = filter_response.json()
        assert len(results) >= 3  # Company B, C, D
        
        # Filter for specific range
        date_from = (base_date - timedelta(days=6)).isoformat()
        date_to = (base_date + timedelta(days=1)).isoformat()
        filter_response = client.get(f"/api/applications?date_from={date_from}&date_to={date_to}")
        assert filter_response.status_code == 200
        results = filter_response.json()
        company_names = {app["company_name"] for app in results}
        assert "Company B" in company_names
        assert "Company C" in company_names
        
        # Cleanup
        for app_id in app_ids:
            client.delete(f"/api/applications/{app_id}")
    
    def test_multiple_filters_combined(self, client):
        """
        Test combining multiple filters (search + stage + date).
        
        Validates Requirements: 7.4
        """
        # Create diverse applications
        base_date = datetime.now()
        apps_data = [
            ("TechCorp", "wishlist", base_date - timedelta(days=2)),
            ("TechStart", "applied", base_date - timedelta(days=1)),
            ("DataCorp", "wishlist", base_date),
            ("TechSystems", "wishlist", base_date - timedelta(days=3))
        ]
        app_ids = []
        
        for company, stage, date in apps_data:
            app_data = {
                "company_name": company,
                "position_title": "Engineer",
                "stage": stage,
                "application_date": date.isoformat()
            }
            response = client.post("/api/applications", json=app_data)
            assert response.status_code == 201
            app_ids.append(response.json()["id"])
        
        # Combine filters: search="Tech" + stage="wishlist" + date_from
        date_from = (base_date - timedelta(days=3)).isoformat()
        filter_response = client.get(
            f"/api/applications?search=Tech&stage=wishlist&date_from={date_from}"
        )
        assert filter_response.status_code == 200
        results = filter_response.json()
        # Should match TechCorp and TechSystems (both Tech + wishlist + in date range)
        assert len(results) == 2
        company_names = {app["company_name"] for app in results}
        assert "TechCorp" in company_names
        assert "TechSystems" in company_names
        
        # Cleanup
        for app_id in app_ids:
            client.delete(f"/api/applications/{app_id}")


class TestBulkOperations:
    """Test bulk operations through API."""
    
    def test_bulk_stage_change(self, client):
        """
        Test bulk stage change operation.
        
        Validates Requirements: 10.2
        """
        # Create multiple applications
        app_ids = []
        for i in range(5):
            app_data = {
                "company_name": f"Company {i}",
                "position_title": "Engineer",
                "stage": "wishlist",
                "application_date": datetime.now().isoformat()
            }
            response = client.post("/api/applications", json=app_data)
            assert response.status_code == 201
            app_ids.append(response.json()["id"])
        
        # Perform bulk stage change on first 3 applications
        bulk_data = {
            "application_ids": app_ids[:3],
            "new_stage": "applied"
        }
        
        bulk_response = client.post("/api/applications/bulk/stage", json=bulk_data)
        assert bulk_response.status_code == 200
        bulk_result = bulk_response.json()
        assert len(bulk_result["successful"]) == 3
        assert len(bulk_result["failed"]) == 0
        
        # Verify stage changes
        for app_id in app_ids[:3]:
            get_response = client.get(f"/api/applications/{app_id}")
            assert get_response.status_code == 200
            assert get_response.json()["stage"] == "applied"
        
        # Verify unchanged applications
        for app_id in app_ids[3:]:
            get_response = client.get(f"/api/applications/{app_id}")
            assert get_response.status_code == 200
            assert get_response.json()["stage"] == "wishlist"
        
        # Cleanup
        for app_id in app_ids:
            client.delete(f"/api/applications/{app_id}")
    
    def test_bulk_delete(self, client):
        """
        Test bulk delete operation.
        
        Validates Requirements: 10.3
        """
        # Create multiple applications
        app_ids = []
        for i in range(5):
            app_data = {
                "company_name": f"Company {i}",
                "position_title": "Engineer",
                "stage": "wishlist",
                "application_date": datetime.now().isoformat()
            }
            response = client.post("/api/applications", json=app_data)
            assert response.status_code == 201
            app_ids.append(response.json()["id"])
        
        # Perform bulk delete on first 3 applications
        bulk_data = {
            "application_ids": app_ids[:3]
        }
        
        bulk_response = client.post("/api/applications/bulk/delete", json=bulk_data)
        assert bulk_response.status_code == 200
        bulk_result = bulk_response.json()
        assert len(bulk_result["successful"]) == 3
        assert len(bulk_result["failed"]) == 0
        
        # Verify deletions
        for app_id in app_ids[:3]:
            get_response = client.get(f"/api/applications/{app_id}")
            assert get_response.status_code == 404
        
        # Verify remaining applications
        for app_id in app_ids[3:]:
            get_response = client.get(f"/api/applications/{app_id}")
            assert get_response.status_code == 200
        
        # Cleanup remaining
        for app_id in app_ids[3:]:
            client.delete(f"/api/applications/{app_id}")
    
    def test_bulk_operations_with_partial_failures(self, client):
        """
        Test bulk operations with some invalid IDs.
        
        Validates Requirements: 10.4
        """
        # Create some applications
        app_ids = []
        for i in range(3):
            app_data = {
                "company_name": f"Company {i}",
                "position_title": "Engineer",
                "stage": "wishlist",
                "application_date": datetime.now().isoformat()
            }
            response = client.post("/api/applications", json=app_data)
            assert response.status_code == 201
            app_ids.append(response.json()["id"])
        
        # Add some invalid IDs
        mixed_ids = app_ids + ["invalid-id-1", "invalid-id-2"]
        
        # Attempt bulk stage change
        bulk_data = {
            "application_ids": mixed_ids,
            "new_stage": "applied"
        }
        
        bulk_response = client.post("/api/applications/bulk/stage", json=bulk_data)
        assert bulk_response.status_code == 200
        bulk_result = bulk_response.json()
        assert len(bulk_result["successful"]) == 3
        assert len(bulk_result["failed"]) == 2
        
        # Cleanup
        for app_id in app_ids:
            client.delete(f"/api/applications/{app_id}")


class TestCSVImportExport:
    """Test CSV import/export round-trip through API."""
    
    def test_csv_export(self, client):
        """
        Test exporting applications to CSV.
        
        Validates Requirements: 12.1
        """
        # Create applications
        app_ids = []
        for i in range(3):
            app_data = {
                "company_name": f"Company {i}",
                "position_title": f"Position {i}",
                "stage": "wishlist",
                "application_date": datetime.now().isoformat(),
                "notes": f"Notes for company {i}"
            }
            response = client.post("/api/applications", json=app_data)
            assert response.status_code == 201
            app_ids.append(response.json()["id"])
        
        # Export to CSV
        export_response = client.get("/api/applications/export")
        assert export_response.status_code == 200
        assert export_response.headers["content-type"] == "text/csv; charset=utf-8"
        
        # Verify CSV content
        csv_content = export_response.text
        assert "company_name" in csv_content
        assert "position_title" in csv_content
        assert "Company 0" in csv_content
        assert "Company 1" in csv_content
        assert "Company 2" in csv_content
        
        # Cleanup
        for app_id in app_ids:
            client.delete(f"/api/applications/{app_id}")
    
    def test_csv_import(self, client):
        """
        Test importing applications from CSV.
        
        Validates Requirements: 11.1
        """
        # Create CSV content
        csv_content = """company_name,position_title,stage,application_date,notes
ImportCorp,Software Engineer,wishlist,2024-01-15T10:00:00Z,Imported from CSV
DataSystems,Data Analyst,applied,2024-01-16T11:00:00Z,Another import
TechStart,DevOps Engineer,interview,2024-01-17T12:00:00Z,Third import
"""
        
        # Create file-like object
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        
        # Import CSV
        import_response = client.post(
            "/api/applications/import",
            files={"file": ("test_import.csv", csv_file, "text/csv")}
        )
        assert import_response.status_code == 201
        import_result = import_response.json()
        assert import_result["total_rows"] == 3
        assert import_result["successful"] == 3
        assert import_result["failed"] == 0
        
        # Verify imported applications
        list_response = client.get("/api/applications")
        assert list_response.status_code == 200
        apps = list_response.json()
        
        company_names = {app["company_name"] for app in apps}
        assert "ImportCorp" in company_names
        assert "DataSystems" in company_names
        assert "TechStart" in company_names
        
        # Cleanup - delete imported applications
        for app in apps:
            if app["company_name"] in ["ImportCorp", "DataSystems", "TechStart"]:
                client.delete(f"/api/applications/{app['id']}")
    
    def test_csv_import_export_round_trip(self, client):
        """
        Test complete CSV import/export round-trip.
        
        Validates Requirements: 11.1, 12.1
        """
        # Create applications
        original_apps = []
        for i in range(3):
            app_data = {
                "company_name": f"RoundTrip {i}",
                "position_title": f"Engineer {i}",
                "stage": "wishlist",
                "application_date": datetime.now().isoformat(),
                "notes": f"Round trip test {i}"
            }
            response = client.post("/api/applications", json=app_data)
            assert response.status_code == 201
            original_apps.append(response.json())
        
        # Export to CSV
        export_response = client.get("/api/applications/export?search=RoundTrip")
        assert export_response.status_code == 200
        csv_content = export_response.text
        
        # Delete original applications
        for app in original_apps:
            client.delete(f"/api/applications/{app['id']}")
        
        # Import the CSV back
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        import_response = client.post(
            "/api/applications/import",
            files={"file": ("round_trip.csv", csv_file, "text/csv")}
        )
        assert import_response.status_code == 201
        import_result = import_response.json()
        assert import_result["successful"] == 3
        
        # Verify imported data matches original
        list_response = client.get("/api/applications?search=RoundTrip")
        assert list_response.status_code == 200
        imported_apps = list_response.json()
        assert len(imported_apps) == 3
        
        imported_companies = {app["company_name"] for app in imported_apps}
        original_companies = {app["company_name"] for app in original_apps}
        assert imported_companies == original_companies
        
        # Cleanup
        for app in imported_apps:
            client.delete(f"/api/applications/{app['id']}")
    
    def test_csv_import_with_invalid_data(self, client):
        """
        Test CSV import with invalid data.
        
        Validates Requirements: 11.2
        """
        # Create CSV with some invalid rows
        csv_content = """company_name,position_title,stage,application_date,notes
ValidCorp,Engineer,wishlist,2024-01-15T10:00:00Z,Valid entry
,Missing Company,wishlist,2024-01-16T11:00:00Z,Invalid - no company
InvalidStage,Engineer,invalid_stage,2024-01-17T12:00:00Z,Invalid stage
MissingDate,Engineer,wishlist,,Invalid - no date
"""
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        
        # Import CSV
        import_response = client.post(
            "/api/applications/import",
            files={"file": ("invalid_import.csv", csv_file, "text/csv")}
        )
        assert import_response.status_code == 201
        import_result = import_response.json()
        
        # Should have 1 successful and 3 failed
        assert import_result["total_rows"] == 4
        assert import_result["successful"] >= 1
        assert import_result["failed"] >= 1
        assert len(import_result["errors"]) >= 1
        
        # Cleanup - delete any successfully imported applications
        list_response = client.get("/api/applications?search=ValidCorp")
        if list_response.status_code == 200:
            apps = list_response.json()
            for app in apps:
                if app["company_name"] == "ValidCorp":
                    client.delete(f"/api/applications/{app['id']}")


class TestErrorHandling:
    """Test error responses for invalid requests."""
    
    def test_create_application_with_missing_required_fields(self, client):
        """
        Test creating application with missing required fields.
        
        Validates Requirements: 8.4
        """
        # Missing company_name
        invalid_data = {
            "position_title": "Engineer",
            "stage": "wishlist",
            "application_date": datetime.now().isoformat()
        }
        
        response = client.post("/api/applications", json=invalid_data)
        assert response.status_code == 422  # Validation error
    
    def test_get_nonexistent_application(self, client):
        """
        Test retrieving non-existent application.
        
        Validates Requirements: 1.5
        """
        response = client.get("/api/applications/nonexistent-id-12345")
        assert response.status_code == 404
    
    def test_update_nonexistent_application(self, client):
        """
        Test updating non-existent application.
        
        Validates Requirements: 1.2
        """
        update_data = {
            "company_name": "Test Corp",
            "position_title": "Engineer"
        }
        
        response = client.put("/api/applications/nonexistent-id-12345", json=update_data)
        assert response.status_code == 404
    
    def test_delete_nonexistent_application(self, client):
        """
        Test deleting non-existent application.
        
        Validates Requirements: 1.5
        """
        response = client.delete("/api/applications/nonexistent-id-12345")
        assert response.status_code == 404
    
    def test_invalid_stage_value(self, client):
        """
        Test creating application with invalid stage value.
        
        Validates Requirements: 8.4
        """
        invalid_data = {
            "company_name": "Test Corp",
            "position_title": "Engineer",
            "stage": "invalid_stage",
            "application_date": datetime.now().isoformat()
        }
        
        response = client.post("/api/applications", json=invalid_data)
        assert response.status_code == 422  # Validation error
    
    def test_invalid_date_format(self, client):
        """
        Test creating application with invalid date format.
        
        Validates Requirements: 8.4
        """
        invalid_data = {
            "company_name": "Test Corp",
            "position_title": "Engineer",
            "stage": "wishlist",
            "application_date": "not-a-date"
        }
        
        response = client.post("/api/applications", json=invalid_data)
        assert response.status_code == 422  # Validation error
    
    def test_import_non_csv_file(self, client):
        """
        Test importing non-CSV file.
        
        Validates Requirements: 11.2
        """
        # Create a text file
        text_content = "This is not a CSV file"
        text_file = io.BytesIO(text_content.encode('utf-8'))
        
        response = client.post(
            "/api/applications/import",
            files={"file": ("test.txt", text_file, "text/plain")}
        )
        assert response.status_code == 400  # Bad request
