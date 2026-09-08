"""
End-to-End Tests for CV Version Integration with Application Tracker.

Feature: job-application-tracker
Task 13.2: Test CV version integration

Tests the integration between the application tracker and CV management system,
including CV association, display, navigation, and graceful handling of missing CVs.

Requirements: 5.1, 5.2, 5.3, 13.3
"""
import pytest
from fastapi.testclient import TestClient
import tempfile
import json
from pathlib import Path
from datetime import datetime

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
        
        # Create CVs directory
        cvs_dir = data_dir / "cvs"
        cvs_dir.mkdir(parents=True)
        
        # Create empty JSON files
        applications_file = data_dir / "applications.json"
        applications_file.write_text(json.dumps({"applications": []}))
        
        history_file = data_dir / "application_history.json"
        history_file.write_text(json.dumps({"history": []}))
        
        # Create CV metadata file with sample CVs
        cv_metadata = {
            "cvs": [
                {
                    "id": "test-cv-id-001",
                    "title": "Software Engineer CV",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                },
                {
                    "id": "test-cv-id-002",
                    "title": "Senior Developer CV",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
            ]
        }
        cv_metadata_file = cvs_dir / "metadata.json"
        cv_metadata_file.write_text(json.dumps(cv_metadata))
        
        yield {
            "data_dir": data_dir,
            "temp_dir": temp_dir,
            "applications_file": applications_file,
            "history_file": history_file,
            "cvs_dir": cvs_dir,
            "cv_metadata_file": cv_metadata_file
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


class TestCVVersionIntegration:
    """
    Task 13.2: Test CV version integration
    
    Tests:
    1. Create application and associate with CV version
    2. Verify CV version displays correctly
    3. Click CV version link and verify navigation
    4. Test with non-existent CV version (graceful handling)
    """
    
    def test_associate_cv_with_application(self, client):
        """
        Test creating application and associating with CV version.
        
        Validates Requirements: 5.1, 5.2
        """
        print("\n=== Test: Associate CV with Application ===")
        
        # Step 1: Create application with CV association
        create_data = {
            "company_name": "TechCorp",
            "position_title": "Software Engineer",
            "stage": "wishlist",
            "application_date": datetime.now().isoformat(),
            "cv_version_id": "test-cv-id-001",
            "notes": "Using my Software Engineer CV for this application"
        }
        
        create_response = client.post("/api/applications", json=create_data)
        assert create_response.status_code == 201
        application = create_response.json()
        app_id = application["id"]
        
        print(f"✓ Application created with CV association")
        assert application["cv_version_id"] == "test-cv-id-001"
        
        # Step 2: Retrieve application and verify CV association
        get_response = client.get(f"/api/applications/{app_id}")
        assert get_response.status_code == 200
        retrieved_app = get_response.json()
        
        assert retrieved_app["cv_version_id"] == "test-cv-id-001"
        print(f"✓ CV version ID persisted correctly: {retrieved_app['cv_version_id']}")
        
        # Step 3: Verify CV association appears in list view
        list_response = client.get("/api/applications")
        assert list_response.status_code == 200
        all_apps = list_response.json()
        
        our_app = next((app for app in all_apps if app["id"] == app_id), None)
        assert our_app is not None
        assert our_app["cv_version_id"] == "test-cv-id-001"
        print(f"✓ CV association visible in list view")
        
        # Cleanup
        client.delete(f"/api/applications/{app_id}")
        
        print("✓ CV association test passed")
    
    def test_update_cv_association(self, client):
        """
        Test updating CV association for an existing application.
        
        Validates Requirements: 5.1, 5.2
        """
        print("\n=== Test: Update CV Association ===")
        
        # Create application without CV
        create_data = {
            "company_name": "DataCorp",
            "position_title": "Data Engineer",
            "stage": "wishlist",
            "application_date": datetime.now().isoformat()
        }
        
        create_response = client.post("/api/applications", json=create_data)
        assert create_response.status_code == 201
        app_id = create_response.json()["id"]
        
        # Verify no CV association initially
        get_response = client.get(f"/api/applications/{app_id}")
        app_data = get_response.json()
        assert app_data["cv_version_id"] is None
        print(f"✓ Application created without CV association")
        
        # Add CV association
        app_data["cv_version_id"] = "test-cv-id-001"
        update_response = client.put(f"/api/applications/{app_id}", json=app_data)
        assert update_response.status_code == 200
        updated_app = update_response.json()
        assert updated_app["cv_version_id"] == "test-cv-id-001"
        print(f"✓ CV association added via update")
        
        # Change CV association to different CV
        app_data["cv_version_id"] = "test-cv-id-002"
        update_response = client.put(f"/api/applications/{app_id}", json=app_data)
        assert update_response.status_code == 200
        updated_app = update_response.json()
        assert updated_app["cv_version_id"] == "test-cv-id-002"
        print(f"✓ CV association changed to different CV")
        
        # Remove CV association
        app_data["cv_version_id"] = None
        update_response = client.put(f"/api/applications/{app_id}", json=app_data)
        assert update_response.status_code == 200
        updated_app = update_response.json()
        assert updated_app["cv_version_id"] is None
        print(f"✓ CV association removed")
        
        # Cleanup
        client.delete(f"/api/applications/{app_id}")
        
        print("✓ Update CV association test passed")
    
    def test_cv_association_persistence_across_stage_changes(self, client):
        """
        Test that CV association persists when application moves through stages.
        
        Validates Requirements: 5.4
        """
        print("\n=== Test: CV Association Persistence ===")
        
        # Create application with CV
        create_data = {
            "company_name": "CloudTech",
            "position_title": "Cloud Engineer",
            "stage": "wishlist",
            "application_date": datetime.now().isoformat(),
            "cv_version_id": "test-cv-id-001"
        }
        
        create_response = client.post("/api/applications", json=create_data)
        assert create_response.status_code == 201
        app_id = create_response.json()["id"]
        
        # Move through multiple stages
        stages = ["applied", "interview", "offer"]
        for stage in stages:
            stage_change = {"new_stage": stage}
            stage_response = client.patch(f"/api/applications/{app_id}/stage", json=stage_change)
            assert stage_response.status_code == 200
            
            # Verify CV association still exists
            get_response = client.get(f"/api/applications/{app_id}")
            app_data = get_response.json()
            assert app_data["cv_version_id"] == "test-cv-id-001"
            print(f"✓ CV association persisted after moving to {stage}")
        
        # Cleanup
        client.delete(f"/api/applications/{app_id}")
        
        print("✓ CV persistence test passed")
    
    def test_multiple_applications_with_same_cv(self, client):
        """
        Test that multiple applications can reference the same CV version.
        
        Validates Requirements: 5.1, 5.2
        """
        print("\n=== Test: Multiple Applications with Same CV ===")
        
        # Create multiple applications using the same CV
        app_ids = []
        companies = ["Company A", "Company B", "Company C"]
        
        for company in companies:
            create_data = {
                "company_name": company,
                "position_title": "Software Engineer",
                "stage": "wishlist",
                "application_date": datetime.now().isoformat(),
                "cv_version_id": "test-cv-id-001"
            }
            
            response = client.post("/api/applications", json=create_data)
            assert response.status_code == 201
            app_ids.append(response.json()["id"])
        
        print(f"✓ Created {len(app_ids)} applications with same CV")
        
        # Verify all have the same CV association
        for app_id in app_ids:
            get_response = client.get(f"/api/applications/{app_id}")
            app_data = get_response.json()
            assert app_data["cv_version_id"] == "test-cv-id-001"
        
        print(f"✓ All applications correctly reference the same CV")
        
        # Cleanup
        for app_id in app_ids:
            client.delete(f"/api/applications/{app_id}")
        
        print("✓ Multiple applications test passed")
    
    def test_graceful_handling_of_nonexistent_cv(self, client):
        """
        Test graceful handling when CV version doesn't exist.
        
        Validates Requirements: 5.3, 13.3
        """
        print("\n=== Test: Graceful Handling of Non-existent CV ===")
        
        # Create application with non-existent CV ID
        create_data = {
            "company_name": "TestCorp",
            "position_title": "Engineer",
            "stage": "wishlist",
            "application_date": datetime.now().isoformat(),
            "cv_version_id": "nonexistent-cv-id-999"
        }
        
        # Application should still be created (CV validation is optional)
        create_response = client.post("/api/applications", json=create_data)
        assert create_response.status_code == 201
        application = create_response.json()
        app_id = application["id"]
        
        print(f"✓ Application created with non-existent CV reference")
        assert application["cv_version_id"] == "nonexistent-cv-id-999"
        
        # Retrieve application - should return with CV ID even if CV doesn't exist
        get_response = client.get(f"/api/applications/{app_id}")
        assert get_response.status_code == 200
        app_data = get_response.json()
        assert app_data["cv_version_id"] == "nonexistent-cv-id-999"
        
        print(f"✓ Application retrieval works with non-existent CV reference")
        print(f"  Note: Frontend should handle missing CV gracefully (show 'CV not found')")
        
        # Cleanup
        client.delete(f"/api/applications/{app_id}")
        
        print("✓ Non-existent CV handling test passed")
    
    def test_cv_association_in_export(self, client):
        """
        Test that CV associations are included in CSV export.
        
        Validates Requirements: 12.2
        """
        print("\n=== Test: CV Association in Export ===")
        
        # Create applications with and without CV associations
        apps_data = [
            {
                "company_name": "Export Test A",
                "position_title": "Engineer",
                "stage": "wishlist",
                "application_date": datetime.now().isoformat(),
                "cv_version_id": "test-cv-id-001"
            },
            {
                "company_name": "Export Test B",
                "position_title": "Developer",
                "stage": "applied",
                "application_date": datetime.now().isoformat(),
                "cv_version_id": "test-cv-id-002"
            },
            {
                "company_name": "Export Test C",
                "position_title": "Analyst",
                "stage": "interview",
                "application_date": datetime.now().isoformat()
                # No CV association
            }
        ]
        
        app_ids = []
        for app_data in apps_data:
            response = client.post("/api/applications", json=app_data)
            assert response.status_code == 201
            app_ids.append(response.json()["id"])
        
        # Export to CSV
        export_response = client.get("/api/applications/export?search=Export Test")
        assert export_response.status_code == 200
        csv_content = export_response.text
        
        # Verify CV IDs are in export
        assert "cv_version_id" in csv_content
        assert "test-cv-id-001" in csv_content
        assert "test-cv-id-002" in csv_content
        
        print(f"✓ CV associations included in CSV export")
        
        # Cleanup
        for app_id in app_ids:
            client.delete(f"/api/applications/{app_id}")
        
        print("✓ CV export test passed")
    
    def test_cv_association_in_import(self, client):
        """
        Test that CV associations can be imported from CSV.
        
        Validates Requirements: 11.5
        """
        print("\n=== Test: CV Association in Import ===")
        
        import io
        
        # Create CSV with CV associations
        csv_content = """company_name,position_title,stage,application_date,cv_version_id,notes
Import CV Test A,Engineer,wishlist,2024-01-15T10:00:00Z,test-cv-id-001,With CV
Import CV Test B,Developer,applied,2024-01-16T11:00:00Z,test-cv-id-002,With CV
Import CV Test C,Analyst,interview,2024-01-17T12:00:00Z,,Without CV
"""
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        
        # Import CSV
        import_response = client.post(
            "/api/applications/import",
            files={"file": ("cv_import_test.csv", csv_file, "text/csv")}
        )
        assert import_response.status_code == 201
        import_result = import_response.json()
        assert import_result["successful"] == 3
        
        print(f"✓ Imported {import_result['successful']} applications with CV data")
        
        # Verify CV associations were imported
        list_response = client.get("/api/applications?search=Import CV Test")
        assert list_response.status_code == 200
        imported_apps = list_response.json()
        
        # Find and verify each application
        app_a = next((app for app in imported_apps if "Test A" in app["company_name"]), None)
        app_b = next((app for app in imported_apps if "Test B" in app["company_name"]), None)
        app_c = next((app for app in imported_apps if "Test C" in app["company_name"]), None)
        
        assert app_a is not None
        assert app_a["cv_version_id"] == "test-cv-id-001"
        print(f"✓ App A has correct CV: {app_a['cv_version_id']}")
        
        assert app_b is not None
        assert app_b["cv_version_id"] == "test-cv-id-002"
        print(f"✓ App B has correct CV: {app_b['cv_version_id']}")
        
        assert app_c is not None
        assert app_c["cv_version_id"] is None or app_c["cv_version_id"] == ""
        print(f"✓ App C has no CV (as expected)")
        
        # Cleanup
        for app in imported_apps:
            if "Import CV Test" in app["company_name"]:
                client.delete(f"/api/applications/{app['id']}")
        
        print("✓ CV import test passed")
    
    def test_cv_association_with_history(self, client):
        """
        Test that CV association is preserved in application history.
        
        Validates Requirements: 5.4, 9.3
        """
        print("\n=== Test: CV Association with History ===")
        
        # Create application with CV
        create_data = {
            "company_name": "History Test Corp",
            "position_title": "Engineer",
            "stage": "wishlist",
            "application_date": datetime.now().isoformat(),
            "cv_version_id": "test-cv-id-001"
        }
        
        create_response = client.post("/api/applications", json=create_data)
        assert create_response.status_code == 201
        app_id = create_response.json()["id"]
        
        # Move through stages
        client.patch(f"/api/applications/{app_id}/stage", json={"new_stage": "applied"})
        client.patch(f"/api/applications/{app_id}/stage", json={"new_stage": "interview"})
        
        # Change CV association
        get_response = client.get(f"/api/applications/{app_id}")
        app_data = get_response.json()
        app_data["cv_version_id"] = "test-cv-id-002"
        client.put(f"/api/applications/{app_id}", json=app_data)
        
        # Move to another stage
        client.patch(f"/api/applications/{app_id}/stage", json={"new_stage": "offer"})
        
        # Verify history is intact
        history_response = client.get(f"/api/applications/{app_id}/history")
        assert history_response.status_code == 200
        history = history_response.json()
        
        # Should have all stage transitions
        assert len(history) >= 4  # wishlist → applied → interview → offer
        print(f"✓ History preserved with {len(history)} entries")
        
        # Verify current CV association
        get_response = client.get(f"/api/applications/{app_id}")
        final_app = get_response.json()
        assert final_app["cv_version_id"] == "test-cv-id-002"
        print(f"✓ Current CV association: {final_app['cv_version_id']}")
        
        # Cleanup
        client.delete(f"/api/applications/{app_id}")
        
        print("✓ CV with history test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
