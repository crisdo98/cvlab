"""
End-to-End Integration Tests for Job Application Tracker.

Feature: job-application-tracker
Tests complete application lifecycle including UI interactions, API calls,
and data persistence. These tests validate the entire system working together.

Task 13.1: Test complete application lifecycle
Requirements: 1.1, 1.2, 1.5, 3.1, 4.6
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


class TestCompleteApplicationLifecycle:
    """
    Task 13.1: Test complete application lifecycle
    
    Simulates a user's complete journey:
    1. Create application via UI (API call)
    2. Verify it appears on Kanban board (list API)
    3. Drag to different stages (stage change API)
    4. Edit details (update API)
    5. Delete application (delete API)
    6. Verify all operations persist correctly
    """
    
    def test_e2e_application_lifecycle_wishlist_to_offer(self, client):
        """
        Test complete lifecycle: Create → Applied → Interview → Offer
        
        Validates Requirements: 1.1, 1.2, 1.5, 3.1, 4.6
        """
        # Step 1: User creates a new application (via UI form)
        print("\n=== Step 1: Create Application ===")
        create_data = {
            "company_name": "Dream Tech Company",
            "position_title": "Senior Full Stack Developer",
            "stage": "wishlist",
            "application_date": datetime.now().isoformat(),
            "job_description_url": "https://dreamtech.com/careers/senior-fullstack",
            "notes": "Found through LinkedIn, looks like a great fit!"
        }
        
        create_response = client.post("/api/applications", json=create_data)
        assert create_response.status_code == 201
        application = create_response.json()
        app_id = application["id"]
        
        print(f"✓ Application created with ID: {app_id}")
        assert application["company_name"] == "Dream Tech Company"
        assert application["stage"] == "wishlist"
        assert "id" in application
        assert "created_at" in application
        
        # Step 2: User views Kanban board - application appears in Wishlist column
        print("\n=== Step 2: Verify on Kanban Board ===")
        list_response = client.get("/api/applications")
        assert list_response.status_code == 200
        all_apps = list_response.json()
        
        # Find our application
        our_app = next((app for app in all_apps if app["id"] == app_id), None)
        assert our_app is not None
        assert our_app["stage"] == "wishlist"
        print(f"✓ Application appears in Wishlist column")
        
        # Step 3: User drags card from Wishlist to Applied
        print("\n=== Step 3: Drag to Applied Stage ===")
        stage_change_1 = {
            "new_stage": "applied",
            "notes": "Submitted application through company website"
        }
        
        stage_response_1 = client.patch(f"/api/applications/{app_id}/stage", json=stage_change_1)
        assert stage_response_1.status_code == 200
        updated_app = stage_response_1.json()
        assert updated_app["stage"] == "applied"
        print(f"✓ Application moved to Applied stage")
        
        # Verify history entry was created
        history_response = client.get(f"/api/applications/{app_id}/history")
        assert history_response.status_code == 200
        history = history_response.json()
        assert len(history) >= 2  # Initial + first transition
        assert history[-1]["to_stage"] == "applied"
        assert history[-1]["from_stage"] == "wishlist"
        print(f"✓ History entry created for stage transition")
        
        # Step 4: User clicks on card to edit details (add interview)
        print("\n=== Step 4: Edit Application Details ===")
        get_response = client.get(f"/api/applications/{app_id}")
        assert get_response.status_code == 200
        app_data = get_response.json()
        
        # User adds interview details
        app_data["interviews"] = [{
            "date": (datetime.now() + timedelta(days=5)).isoformat(),
            "type": "phone",
            "meeting_link": "https://zoom.us/j/123456789",
            "notes": "Initial screening with HR",
            "interviewer_name": "Sarah Johnson"
        }]
        app_data["recruiter_name"] = "Sarah Johnson"
        app_data["recruiter_email"] = "sarah.johnson@dreamtech.com"
        app_data["notes"] = "Found through LinkedIn. Had initial call with recruiter."
        
        update_response = client.put(f"/api/applications/{app_id}", json=app_data)
        assert update_response.status_code == 200
        updated_app = update_response.json()
        assert len(updated_app["interviews"]) == 1
        assert updated_app["recruiter_name"] == "Sarah Johnson"
        print(f"✓ Application details updated with interview and recruiter info")
        
        # Step 5: User drags card from Applied to Interview
        print("\n=== Step 5: Drag to Interview Stage ===")
        stage_change_2 = {
            "new_stage": "interview",
            "notes": "Phone screening scheduled"
        }
        
        stage_response_2 = client.patch(f"/api/applications/{app_id}/stage", json=stage_change_2)
        assert stage_response_2.status_code == 200
        assert stage_response_2.json()["stage"] == "interview"
        print(f"✓ Application moved to Interview stage")
        
        # Step 6: User adds more interview rounds
        print("\n=== Step 6: Add Technical Interview ===")
        get_response = client.get(f"/api/applications/{app_id}")
        app_data = get_response.json()
        
        app_data["interviews"].append({
            "date": (datetime.now() + timedelta(days=10)).isoformat(),
            "type": "technical",
            "meeting_link": "https://meet.google.com/abc-defg-hij",
            "notes": "Technical coding interview with engineering team",
            "interviewer_name": "Mike Chen"
        })
        
        update_response = client.put(f"/api/applications/{app_id}", json=app_data)
        assert update_response.status_code == 200
        assert len(update_response.json()["interviews"]) == 2
        print(f"✓ Technical interview added")
        
        # Step 7: User drags card from Interview to Offer
        print("\n=== Step 7: Drag to Offer Stage ===")
        stage_change_3 = {
            "new_stage": "offer",
            "notes": "Received verbal offer!"
        }
        
        stage_response_3 = client.patch(f"/api/applications/{app_id}/stage", json=stage_change_3)
        assert stage_response_3.status_code == 200
        assert stage_response_3.json()["stage"] == "offer"
        print(f"✓ Application moved to Offer stage")
        
        # Step 8: User adds offer details
        print("\n=== Step 8: Add Offer Details ===")
        get_response = client.get(f"/api/applications/{app_id}")
        app_data = get_response.json()
        
        app_data["feedback"] = "Great cultural fit, strong technical skills"
        app_data["outcome"] = "Offer received: $150k base + equity"
        
        update_response = client.put(f"/api/applications/{app_id}", json=app_data)
        assert update_response.status_code == 200
        final_app = update_response.json()
        assert final_app["outcome"] is not None
        print(f"✓ Offer details added")
        
        # Step 9: Verify complete history
        print("\n=== Step 9: Verify Complete History ===")
        history_response = client.get(f"/api/applications/{app_id}/history")
        assert history_response.status_code == 200
        history = history_response.json()
        
        # Should have: initial (wishlist) → applied → interview → offer
        assert len(history) >= 4
        stages_progression = [entry["to_stage"] for entry in history]
        assert "wishlist" in stages_progression
        assert "applied" in stages_progression
        assert "interview" in stages_progression
        assert "offer" in stages_progression
        print(f"✓ Complete history verified: {' → '.join(stages_progression)}")
        
        # Step 10: Verify data persistence
        print("\n=== Step 10: Verify Data Persistence ===")
        get_response = client.get(f"/api/applications/{app_id}")
        assert get_response.status_code == 200
        persisted_app = get_response.json()
        
        assert persisted_app["company_name"] == "Dream Tech Company"
        assert persisted_app["stage"] == "offer"
        assert len(persisted_app["interviews"]) == 2
        assert persisted_app["recruiter_name"] == "Sarah Johnson"
        assert persisted_app["outcome"] is not None
        print(f"✓ All data persisted correctly")
        
        # Step 11: User deletes application (cleanup or mistake)
        print("\n=== Step 11: Delete Application ===")
        delete_response = client.delete(f"/api/applications/{app_id}")
        assert delete_response.status_code == 200
        print(f"✓ Application deleted")
        
        # Step 12: Verify deletion
        print("\n=== Step 12: Verify Deletion ===")
        get_deleted_response = client.get(f"/api/applications/{app_id}")
        assert get_deleted_response.status_code == 404
        print(f"✓ Application no longer exists")
        
        print("\n=== ✓ Complete Lifecycle Test Passed ===")
    
    def test_e2e_application_lifecycle_rejection_path(self, client):
        """
        Test rejection path: Create → Applied → Interview → Rejected
        
        Validates Requirements: 1.1, 1.2, 1.5, 3.1
        """
        print("\n=== Testing Rejection Path ===")
        
        # Create application
        create_data = {
            "company_name": "Another Company",
            "position_title": "Backend Developer",
            "stage": "wishlist",
            "application_date": datetime.now().isoformat()
        }
        
        create_response = client.post("/api/applications", json=create_data)
        assert create_response.status_code == 201
        app_id = create_response.json()["id"]
        
        # Move through stages: wishlist → applied → interview
        client.patch(f"/api/applications/{app_id}/stage", json={"new_stage": "applied"})
        client.patch(f"/api/applications/{app_id}/stage", json={"new_stage": "interview"})
        
        # Add interview
        get_response = client.get(f"/api/applications/{app_id}")
        app_data = get_response.json()
        app_data["interviews"] = [{
            "date": (datetime.now() + timedelta(days=3)).isoformat(),
            "type": "technical",
            "notes": "Technical interview"
        }]
        client.put(f"/api/applications/{app_id}", json=app_data)
        
        # Move to rejected
        stage_change = {
            "new_stage": "rejected",
            "notes": "Position filled by another candidate"
        }
        
        stage_response = client.patch(f"/api/applications/{app_id}/stage", json=stage_change)
        assert stage_response.status_code == 200
        assert stage_response.json()["stage"] == "rejected"
        
        # Add feedback
        get_response = client.get(f"/api/applications/{app_id}")
        app_data = get_response.json()
        app_data["feedback"] = "Strong candidate but position filled internally"
        app_data["outcome"] = "Rejected - position filled"
        
        update_response = client.put(f"/api/applications/{app_id}", json=app_data)
        assert update_response.status_code == 200
        
        # Verify history
        history_response = client.get(f"/api/applications/{app_id}/history")
        history = history_response.json()
        assert history[-1]["to_stage"] == "rejected"
        
        # Cleanup
        client.delete(f"/api/applications/{app_id}")
        
        print("✓ Rejection path test passed")
    
    def test_e2e_multiple_applications_on_board(self, client):
        """
        Test managing multiple applications simultaneously on Kanban board
        
        Validates Requirements: 2.1, 2.2, 2.5
        """
        print("\n=== Testing Multiple Applications ===")
        
        # Create multiple applications in different stages
        applications = [
            {"company": "Company A", "stage": "wishlist"},
            {"company": "Company B", "stage": "wishlist"},
            {"company": "Company C", "stage": "applied"},
            {"company": "Company D", "stage": "interview"},
            {"company": "Company E", "stage": "offer"},
        ]
        
        app_ids = []
        for app_info in applications:
            create_data = {
                "company_name": app_info["company"],
                "position_title": "Software Engineer",
                "stage": app_info["stage"],
                "application_date": datetime.now().isoformat()
            }
            response = client.post("/api/applications", json=create_data)
            assert response.status_code == 201
            app_ids.append(response.json()["id"])
        
        # Verify all appear on board
        list_response = client.get("/api/applications")
        assert list_response.status_code == 200
        all_apps = list_response.json()
        assert len(all_apps) >= 5
        
        # Verify stage organization
        for stage in ["wishlist", "applied", "interview", "offer"]:
            stage_apps = [app for app in all_apps if app["stage"] == stage]
            print(f"✓ {stage.capitalize()} column has {len(stage_apps)} application(s)")
        
        # Move one application through stages
        client.patch(f"/api/applications/{app_ids[0]}/stage", json={"new_stage": "applied"})
        client.patch(f"/api/applications/{app_ids[0]}/stage", json={"new_stage": "interview"})
        
        # Verify updated board state
        list_response = client.get("/api/applications")
        all_apps = list_response.json()
        moved_app = next(app for app in all_apps if app["id"] == app_ids[0])
        assert moved_app["stage"] == "interview"
        
        # Cleanup
        for app_id in app_ids:
            client.delete(f"/api/applications/{app_id}")
        
        print("✓ Multiple applications test passed")
    
    def test_e2e_application_with_all_fields(self, client):
        """
        Test application with all optional fields populated
        
        Validates Requirements: 1.3, 4.2, 4.3, 4.4, 4.5
        """
        print("\n=== Testing Application with All Fields ===")
        
        # Create application with all fields
        create_data = {
            "company_name": "Complete Data Corp",
            "position_title": "Principal Engineer",
            "stage": "wishlist",
            "application_date": datetime.now().isoformat(),
            "job_description_url": "https://example.com/job/123",
            "application_deadline": (datetime.now() + timedelta(days=14)).isoformat(),
            "recruiter_name": "Jane Recruiter",
            "recruiter_email": "jane@example.com",
            "recruiter_phone": "+1-555-0100",
            "hiring_manager_name": "Bob Manager",
            "interviews": [
                {
                    "date": (datetime.now() + timedelta(days=7)).isoformat(),
                    "type": "phone",
                    "meeting_link": "https://zoom.us/j/111",
                    "notes": "Initial screening",
                    "interviewer_name": "Jane Recruiter"
                },
                {
                    "date": (datetime.now() + timedelta(days=14)).isoformat(),
                    "type": "technical",
                    "meeting_link": "https://meet.google.com/xxx",
                    "notes": "Technical round",
                    "interviewer_name": "Tech Lead"
                }
            ],
            "notes": "Comprehensive notes about the opportunity",
            "tasks": ["Update resume", "Prepare portfolio", "Research company"],
            "feedback": "Initial feedback from recruiter",
            "outcome": "In progress",
            "follow_up_date": (datetime.now() + timedelta(days=3)).isoformat()
        }
        
        create_response = client.post("/api/applications", json=create_data)
        assert create_response.status_code == 201
        app_id = create_response.json()["id"]
        
        # Retrieve and verify all fields
        get_response = client.get(f"/api/applications/{app_id}")
        assert get_response.status_code == 200
        app = get_response.json()
        
        assert app["company_name"] == "Complete Data Corp"
        assert app["recruiter_name"] == "Jane Recruiter"
        assert app["recruiter_email"] == "jane@example.com"
        assert app["hiring_manager_name"] == "Bob Manager"
        assert len(app["interviews"]) == 2
        assert len(app["tasks"]) == 3
        assert app["notes"] == "Comprehensive notes about the opportunity"
        assert app["feedback"] == "Initial feedback from recruiter"
        assert app["follow_up_date"] is not None
        
        print("✓ All fields persisted correctly")
        
        # Update some fields
        app["notes"] = "Updated notes after follow-up"
        app["tasks"].append("Send thank you email")
        
        update_response = client.put(f"/api/applications/{app_id}", json=app)
        assert update_response.status_code == 200
        updated_app = update_response.json()
        assert len(updated_app["tasks"]) == 4
        assert "Updated notes" in updated_app["notes"]
        
        print("✓ Field updates work correctly")
        
        # Cleanup
        client.delete(f"/api/applications/{app_id}")
        
        print("✓ Complete fields test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
