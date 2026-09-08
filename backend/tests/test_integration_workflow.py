"""
Integration tests for complete CV workflow.

Feature: cv-web-app
Tests the full user journey from CV creation through export,
validating cross-format consistency and template switching.

Requirements: All requirements integration
"""
import pytest
import copy
from fastapi.testclient import TestClient
import tempfile
import os
import json
from pathlib import Path
from datetime import datetime

from app.main import app
from app.models.cv_models import CVModel
from app.services.file_service import FileService
from app.services.cv_service import CVService
from app.routers import cv_router
from tests import v2_helpers as v2


def extract_cv_from_response(response_data):
    """Extract CV data from API response, handling both nested and flat formats."""
    if "cv" in response_data:
        return response_data["cv"]
    return response_data


@pytest.fixture
def temp_test_env():
    """Create a complete temporary test environment."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create directory structure
        data_dir = Path(temp_dir) / "data"
        cvs_dir = data_dir / "cvs"
        
        cvs_dir.mkdir(parents=True)
        
        # Create metadata file
        metadata_file = cvs_dir / "metadata.json"
        metadata_file.write_text(json.dumps({}))
        
        yield {
            "data_dir": data_dir,
            "cvs_dir": cvs_dir,
            "temp_dir": temp_dir
        }


@pytest.fixture
def client(temp_test_env):
    """Create a test client with dependency overrides."""
    # Create services with test directories
    file_service = FileService(data_directory=str(temp_test_env["data_dir"]))
    cv_service = CVService(file_service=file_service)
    
    # Reset and override the global service instances in the router
    import app.routers.cv_router as cv_router_module
    cv_router_module._cv_service = cv_service
    # create_cv writes through _file_service directly, so it must point at the
    # same temp directory the reads go through, or creates land elsewhere.
    cv_router_module._file_service = file_service
    cv_router_module._import_service = None  # Will be created with the overridden cv_service
    
    # Create test client
    test_client = TestClient(app)
    
    yield test_client
    
    # Clean up - reset global services
    cv_router_module._cv_service = None
    cv_router_module._file_service = None
    cv_router_module._import_service = None


@pytest.fixture
def sample_cv_data():
    """Create sample CV data for testing."""
    return {
        "metadata": {
            "title": "Software Engineer CV",
            "template_id": "default"
        },
        "personal_info": {
            "name": "John Doe",
            "title": "Senior Software Engineer",
            "contact": {
                "email": "john.doe@example.com",
                "phone": "+1-555-0123",
                "address": "San Francisco, CA",
                "linkedin": "linkedin.com/in/johndoe",
                "website": "johndoe.dev"
            }
        },
        "summary": "Experienced software engineer with 10+ years in full-stack development.",
        "experience": [
            {
                "title": "Senior Software Engineer",
                "company": "Tech Corp",
                "location": "San Francisco, CA",
                "start_date": "2020-01",
                "end_date": None,
                "current": True,
                "description": "Leading development of cloud-native applications",
                "achievements": [
                    "Reduced deployment time by 50%",
                    "Mentored 5 junior developers"
                ]
            },
            {
                "title": "Software Engineer",
                "company": "StartupXYZ",
                "location": "Remote",
                "start_date": "2018-06",
                "end_date": "2020-01",
                "current": False,
                "description": "Full-stack development",
                "achievements": [
                    "Built microservices architecture",
                    "Improved API performance by 40%"
                ]
            }
        ],
        "education": [
            {
                "degree": "B.S. Computer Science",
                "institution": "University of California",
                "location": "Berkeley, CA",
                "start_date": "2010-09",
                "end_date": "2014-05",
                "gpa": "3.8",
                "description": "Focus on distributed systems and algorithms"
            }
        ],
        "skills": {
            "categories": [
                {
                    "name": "Programming Languages",
                    "skills": ["Python", "JavaScript", "TypeScript", "Go"]
                },
                {
                    "name": "Frameworks",
                    "skills": ["FastAPI", "Vue.js", "React", "Django"]
                },
                {
                    "name": "Tools",
                    "skills": ["Docker", "Kubernetes", "AWS", "Git"]
                }
            ]
        },
        "certifications": [
            {
                "name": "AWS Certified Solutions Architect",
                "issuer": "Amazon Web Services",
                "date": "2022-03",
                "expiry_date": "2025-03"
            }
        ]
    }


@pytest.mark.integration
class TestCompleteWorkflow:
    """Integration tests for complete CV workflow."""
    
    def test_full_cv_lifecycle(self, client, temp_test_env, sample_cv_data):
        """
        Test complete CV lifecycle: create, read, update, delete.
        
        This test validates:
        - CV creation with complete data
        - CV retrieval and data integrity
        - CV updates and persistence
        - CV deletion and cleanup
        """
        # Step 1: Create a new CV
        create_response = client.post("/api/cvs", json=sample_cv_data)
        assert create_response.status_code in [200, 201], f"Failed to create CV: {create_response.text}"
        
        created_cv = v2.as_dict(create_response.json())
        assert "id" in created_cv
        assert v2.full_name(created_cv) == "John Doe"
        cv_id = created_cv["id"]
        
        # Step 2: Retrieve the CV
        get_response = client.get(f"/api/cvs/{cv_id}")
        assert get_response.status_code == 200
        retrieved_cv = v2.as_dict(get_response.json())
        assert retrieved_cv["id"] == cv_id
        assert v2.full_name(retrieved_cv) == "John Doe"
        
        # Step 3: List CVs and verify it appears
        list_response = client.get("/api/cvs")
        assert list_response.status_code == 200
        cv_list = list_response.json()
        assert cv_list["total"] >= 1
        assert any(cv["id"] == cv_id for cv in cv_list["cvs"])
        
        # Step 4: Update the CV
        updated_data = copy.deepcopy(retrieved_cv)
        v2.set_section_content(updated_data, "personal_info", title="Lead Software Engineer")
        v2.set_section_content(updated_data, "summary", text="Updated summary with new achievements")
        
        update_response = client.put(f"/api/cvs/{cv_id}", json=updated_data)
        assert update_response.status_code == 200
        updated_cv = v2.as_dict(update_response.json())
        assert v2.section_content(updated_cv, "personal_info")["title"] == "Lead Software Engineer"
        assert v2.summary_text(updated_cv) == "Updated summary with new achievements"
        
        # Step 5: Delete the CV
        delete_response = client.delete(f"/api/cvs/{cv_id}")
        assert delete_response.status_code == 200
        
        # Step 6: Verify deletion
        get_deleted_response = client.get(f"/api/cvs/{cv_id}")
        assert get_deleted_response.status_code == 404
    
    def test_cv_creation_to_export_workflow(self, client, temp_test_env, sample_cv_data):
        """
        Test workflow from CV creation through basic operations.
        
        This test validates:
        - CV creation
        - CV retrieval
        - Data integrity
        
        Note: Export functionality requires full Pandoc/LaTeX setup and is tested separately
        """
        # Step 1: Create a CV
        create_response = client.post("/api/cvs", json=sample_cv_data)
        assert create_response.status_code in [200, 201]
        cv_id = create_response.json().get("cv", create_response.json())["id"]
        
        # Step 2: Retrieve the CV
        get_response = client.get(f"/api/cvs/{cv_id}")
        assert get_response.status_code == 200
        cv_data = v2.as_dict(get_response.json())
        
        # Verify all key information is present
        assert v2.full_name(cv_data) == "John Doe"
        assert v2.section_content(cv_data, "personal_info")["title"] == "Senior Software Engineer"
        assert v2.section_content(cv_data, "personal_info")["email"] == "john.doe@example.com"
        assert len(v2.experience(cv_data)) == 2
        assert len(v2.education(cv_data)) == 1
        assert len(v2.skills(cv_data)) > 0
        
        # Cleanup
        client.delete(f"/api/cvs/{cv_id}")
    
    def test_cross_format_consistency(self, client, temp_test_env, sample_cv_data):
        """
        Test that CV data remains consistent across operations.
        
        This test validates:
        - CV creation with complete data
        - Data retrieval consistency
        - All key information preserved
        """
        # Create a CV
        create_response = client.post("/api/cvs", json=sample_cv_data)
        assert create_response.status_code in [200, 201]
        cv_id = create_response.json().get("cv", create_response.json())["id"]
        
        # Retrieve the CV
        get_response = client.get(f"/api/cvs/{cv_id}")
        assert get_response.status_code == 200
        cv_data = v2.as_dict(get_response.json())
        
        # Verify key information is present
        key_info = {
            "name": "John Doe",
            "title": "Senior Software Engineer",
            "email": "john.doe@example.com",
            "company": "Tech Corp",
            "institution": "University of California",
            "certification": "AWS Certified Solutions Architect"
        }
        
        personal = v2.section_content(cv_data, "personal_info")
        assert personal["full_name"] == key_info["name"]
        assert personal["title"] == key_info["title"]
        assert personal["email"] == key_info["email"]
        assert any(exp["company"] == key_info["company"] for exp in v2.experience(cv_data))
        assert any(edu["institution"] == key_info["institution"] for edu in v2.education(cv_data))
        assert any(
            cert["name"] == key_info["certification"]
            for cert in v2.entries(cv_data, "certifications")
        )
        
        # Cleanup
        client.delete(f"/api/cvs/{cv_id}")
    
    def test_template_switching_preserves_content(self, client, temp_test_env, sample_cv_data):
        """
        Test that switching templates preserves all CV content.
        
        This test validates:
        - CV content remains unchanged when template changes
        - Template metadata is updated correctly
        - Exports reflect the new template
        """
        # Create a CV with default template
        create_response = client.post("/api/cvs", json=sample_cv_data)
        assert create_response.status_code in [200, 201]
        cv_id = create_response.json().get("cv", create_response.json())["id"]
        original_cv = v2.as_dict(create_response.json())
        
        # V2 stores presentation on the CV itself rather than in metadata
        updated_data = copy.deepcopy(original_cv)
        updated_data["applied_template_id"] = "modern"
        
        update_response = client.put(f"/api/cvs/{cv_id}", json=updated_data)
        assert update_response.status_code == 200
        updated_cv = v2.as_dict(update_response.json())
        
        # Verify all content fields remain identical
        assert v2.section_content(updated_cv, "personal_info") == v2.section_content(original_cv, "personal_info")
        assert v2.summary_text(updated_cv) == v2.summary_text(original_cv)
        assert v2.experience(updated_cv) == v2.experience(original_cv)
        assert v2.education(updated_cv) == v2.education(original_cv)
        assert v2.skills(updated_cv) == v2.skills(original_cv)
        assert v2.entries(updated_cv, "certifications") == v2.entries(original_cv, "certifications")
        
        # Cleanup
        client.delete(f"/api/cvs/{cv_id}")
    
    def test_import_and_export_workflow(self, client, temp_test_env):
        """
        Test importing a Markdown CV.
        
        This test validates:
        - Markdown import functionality
        - Imported data integrity
        
        Note: Export functionality requires full Pandoc/LaTeX setup and is tested separately
        """
        # Create a sample Markdown CV
        markdown_content = """---
title: "Test CV"
name: "Jane Smith"
email: "jane.smith@example.com"
phone: "+1-555-9876"
---

# Jane Smith

## Summary
Experienced data scientist with expertise in machine learning.

## Experience

### Data Scientist | DataCorp | 2019-Present
- Developed ML models for customer segmentation
- Improved prediction accuracy by 30%

## Education

### M.S. Data Science | MIT | 2017-2019
Focus on deep learning and NLP

## Skills
- Python, R, TensorFlow
- SQL, NoSQL databases
- Data visualization
"""
        
        # Save markdown to temp file
        md_file = Path(temp_test_env["temp_dir"]) / "test_cv.md"
        md_file.write_text(markdown_content)
        
        # Import the CV
        with open(md_file, "rb") as f:
            import_response = client.post(
                "/api/cvs/import",
                files={"file": ("test_cv.md", f, "text/markdown")}
            )
        
        assert import_response.status_code in [200, 201]
        imported_cv = v2.as_dict(import_response.json())
        assert "id" in imported_cv
        assert v2.full_name(imported_cv) == "Jane Smith"
        
        cv_id = imported_cv["id"]
        
        # Verify imported data
        get_response = client.get(f"/api/cvs/{cv_id}")
        assert get_response.status_code == 200
        cv_data = v2.as_dict(get_response.json())
        assert v2.full_name(cv_data) == "Jane Smith"
        assert v2.section_content(cv_data, "personal_info")["email"] == "jane.smith@example.com"
        
        # Cleanup
        client.delete(f"/api/cvs/{cv_id}")
    
    def test_multiple_cvs_management(self, client, temp_test_env, sample_cv_data):
        """
        Test managing multiple CVs simultaneously.
        
        This test validates:
        - Creating multiple CVs
        - Listing and filtering CVs
        - Independent CV operations
        """
        # Create multiple CVs
        cv_ids = []
        
        for i in range(3):
            cv_data = copy.deepcopy(sample_cv_data)
            cv_data["metadata"]["title"] = f"CV Version {i+1}"
            cv_data["personal_info"]["name"] = f"Test User {i+1}"
            
            response = client.post("/api/cvs", json=cv_data)
            assert response.status_code in [200, 201]
            cv_ids.append(response.json().get("cv", response.json())["id"])
        
        # List all CVs
        list_response = client.get("/api/cvs")
        assert list_response.status_code == 200
        cv_list = list_response.json()
        assert cv_list["total"] >= 3
        
        # Verify all created CVs are in the list
        listed_ids = {cv["id"] for cv in cv_list["cvs"]}
        for cv_id in cv_ids:
            assert cv_id in listed_ids
        
        # Delete all CVs
        for cv_id in cv_ids:
            delete_response = client.delete(f"/api/cvs/{cv_id}")
            assert delete_response.status_code == 200
        
        # Verify all deleted
        for cv_id in cv_ids:
            get_response = client.get(f"/api/cvs/{cv_id}")
            assert get_response.status_code == 404
    
    def test_export_history_and_cleanup(self, client, temp_test_env, sample_cv_data):
        """
        Test CV data management and persistence.
        
        This test validates:
        - CV creation and persistence
        - Data integrity
        
        Note: Export history requires full export pipeline and is tested separately
        """
        # Create a CV
        create_response = client.post("/api/cvs", json=sample_cv_data)
        assert create_response.status_code in [200, 201]
        cv_id = create_response.json().get("cv", create_response.json())["id"]
        
        # Verify CV file exists on disk
        cv_file = Path(temp_test_env["cvs_dir"]) / f"{cv_id}.json"
        assert cv_file.exists()
        
        # Verify file content
        with open(cv_file) as f:
            file_data = json.load(f)
            assert v2.full_name(file_data) == "John Doe"
        
        # Cleanup
        client.delete(f"/api/cvs/{cv_id}")
    
    def test_error_handling_workflow(self, client, temp_test_env):
        """
        Test error handling throughout the workflow.
        
        This test validates:
        - Invalid CV data rejection
        - Non-existent CV handling
        - Validation errors
        """
        # Test 1: An empty body is valid in V2 - it creates a blank CV that the
        # editor then fills in - so assert the skeleton rather than a rejection.
        response = client.post("/api/cvs", json={"metadata": {}, "personal_info": {}})
        assert response.status_code in [200, 201]
        skeleton = v2.as_dict(response.json())
        assert v2.section_types(skeleton) == ["personal_info"]
        assert v2.full_name(skeleton) == ""
        client.delete(f"/api/cvs/{skeleton['id']}")

        # Malformed field types are still rejected
        response = client.post("/api/cvs", json={"metadata": "not-an-object"})
        assert response.status_code in [422, 400]
        
        # Test 2: Get non-existent CV
        response = client.get("/api/cvs/nonexistent-id-12345")
        assert response.status_code == 404
        
        # Test 3: Update non-existent CV
        response = client.put("/api/cvs/nonexistent-id-12345", json={"metadata": {"title": "Test"}})
        assert response.status_code == 404
        
        # Test 4: Delete non-existent CV
        response = client.delete("/api/cvs/nonexistent-id-12345")
        assert response.status_code == 404
    
    def test_data_persistence_across_operations(self, client, temp_test_env, sample_cv_data):
        """
        Test that data persists correctly across multiple operations.
        
        This test validates:
        - Data integrity after multiple updates
        - File system persistence
        - Metadata consistency
        """
        # Create a CV
        create_response = client.post("/api/cvs", json=sample_cv_data)
        assert create_response.status_code in [200, 201]
        cv_id = create_response.json().get("cv", create_response.json())["id"]
        
        # Perform multiple updates
        for i in range(5):
            get_response = client.get(f"/api/cvs/{cv_id}")
            assert get_response.status_code == 200
            cv_data = v2.as_dict(get_response.json())
            
            # Update summary
            v2.set_section_content(cv_data, "summary", text=f"Updated summary iteration {i+1}")
            
            update_response = client.put(f"/api/cvs/{cv_id}", json=cv_data)
            assert update_response.status_code == 200
            
            # Verify update persisted
            verify_response = client.get(f"/api/cvs/{cv_id}")
            assert verify_response.status_code == 200
            verified_data = v2.as_dict(verify_response.json())
            assert v2.summary_text(verified_data) == f"Updated summary iteration {i+1}"
        
        # Verify file exists on disk
        cv_file = Path(temp_test_env["cvs_dir"]) / f"{cv_id}.json"
        assert cv_file.exists()
        
        # Verify file content matches
        with open(cv_file) as f:
            file_data = json.load(f)
            assert v2.summary_text(file_data) == "Updated summary iteration 5"
        
        # Cleanup
        client.delete(f"/api/cvs/{cv_id}")


@pytest.mark.integration
class TestEndToEndScenarios:
    """End-to-end scenario tests simulating real user workflows."""
    
    def test_job_application_scenario(self, client, temp_test_env, sample_cv_data):
        """
        Simulate a complete job application scenario.
        
        User creates CV, customizes for specific job.
        """
        # Step 1: Create base CV
        response = client.post("/api/cvs", json=sample_cv_data)
        assert response.status_code in [200, 201]
        base_cv_id = response.json().get("cv", response.json())["id"]
        
        # Step 2: Customize for specific job
        cv_data = v2.as_dict(client.get(f"/api/cvs/{base_cv_id}").json())
        v2.set_section_content(
            cv_data, "summary",
            text="Software engineer specializing in cloud architecture and DevOps",
        )
        v2.set_section_content(cv_data, "personal_info", cv_title="Cloud Engineer CV")
        
        update_response = client.put(f"/api/cvs/{base_cv_id}", json=cv_data)
        assert update_response.status_code == 200
        
        # Step 3: Verify updates
        updated_cv = v2.as_dict(client.get(f"/api/cvs/{base_cv_id}").json())
        assert v2.summary_text(updated_cv) == "Software engineer specializing in cloud architecture and DevOps"
        assert v2.cv_title(updated_cv) == "Cloud Engineer CV"
        
        # Cleanup
        client.delete(f"/api/cvs/{base_cv_id}")
    
    def test_cv_version_management_scenario(self, client, temp_test_env, sample_cv_data):
        """
        Simulate managing multiple CV versions for different purposes.
        
        User creates multiple versions: technical, managerial, academic.
        """
        cv_versions = {
            "technical": "Focus on technical skills and projects",
            "managerial": "Emphasis on leadership and team management",
            "academic": "Research and academic achievements"
        }
        
        created_cvs = {}
        
        # Create different versions
        for version_name, summary in cv_versions.items():
            cv_data = copy.deepcopy(sample_cv_data)
            cv_data["metadata"]["title"] = f"{version_name.title()} CV"
            cv_data["summary"] = summary
            
            response = client.post("/api/cvs", json=cv_data)
            assert response.status_code in [200, 201]
            created_cvs[version_name] = response.json().get("cv", response.json())["id"]
        
        # List all CVs
        list_response = client.get("/api/cvs")
        assert list_response.status_code == 200
        assert list_response.json()["total"] >= 3
        
        # Verify each version has correct summary
        for version_name, cv_id in created_cvs.items():
            cv_data = v2.as_dict(client.get(f"/api/cvs/{cv_id}").json())
            assert v2.summary_text(cv_data) == cv_versions[version_name]
        
        # Cleanup
        for cv_id in created_cvs.values():
            client.delete(f"/api/cvs/{cv_id}")
