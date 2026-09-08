"""
Integration tests for Section Management API endpoints.

Tests the REST API endpoints for managing CV sections including:
- Adding predefined sections
- Adding custom sections
- Removing sections
- Reordering sections
- Toggling section visibility
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime
import tempfile
from pathlib import Path
from unittest.mock import patch

from app.main import app
from app.models.cv_section_models import (
    SectionType,
    PersonalInfoContent,
    FreeTextSectionContent,
    Section
)
from app.models.cv_models import CVModelV2
from app.services.file_service import FileService


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def file_service(temp_data_dir):
    """Create file service instance with temporary directory."""
    # Create file service with temp directory
    service = FileService(data_directory=temp_data_dir)
    return service


@pytest.fixture
def client(file_service):
    """Create test client with mocked file service."""
    with patch('app.routers.cv_router.get_file_service', return_value=file_service):
        yield TestClient(app)


@pytest.fixture
def sample_cv_v2(file_service):
    """Create a sample V2 CV for testing."""
    cv = CVModelV2(
        id=file_service.generate_cv_id(),
        user_id="test_user",
        sections=[
            Section(
                id="section-1",
                type=SectionType.PERSONAL_INFO,
                title="Personal Information",
                content=PersonalInfoContent(
                    full_name="John Doe",
                    email="john@example.com"
                ),
                order=0,
                visible=True
            ),
            Section(
                id="section-2",
                type=SectionType.SUMMARY,
                title="Professional Summary",
                content=FreeTextSectionContent(text="Experienced professional"),
                order=1,
                visible=True
            )
        ],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        version=2
    )
    
    # Save CV
    file_service.save_cv(cv)
    
    yield cv
    
    # Cleanup
    try:
        file_service.delete_cv(cv.id)
    except:
        pass


class TestAddPredefinedSection:
    """Tests for POST /api/cvs/{cv_id}/sections/predefined endpoint."""
    
    def test_add_predefined_section_success(self, client, sample_cv_v2):
        """Test successfully adding a predefined section."""
        response = client.post(
            f"/api/cvs/{sample_cv_v2.id}/sections/predefined",
            json={"section_type": "skills"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "section" in data
        assert data["section"]["type"] == "skills"
        assert data["section"]["title"] == "Skills"
        assert data["section"]["visible"] is True
        assert data["section"]["order"] == 2  # Should be placed at end
        assert "message" in data
    
    def test_add_duplicate_predefined_section(self, client, sample_cv_v2):
        """Test that adding a duplicate predefined section fails."""
        # Add skills section first
        response1 = client.post(
            f"/api/cvs/{sample_cv_v2.id}/sections/predefined",
            json={"section_type": "skills"}
        )
        assert response1.status_code == 201
        
        # Try to add skills section again
        response2 = client.post(
            f"/api/cvs/{sample_cv_v2.id}/sections/predefined",
            json={"section_type": "skills"}
        )
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"].lower()
    
    def test_add_predefined_section_cv_not_found(self, client):
        """Test adding section to non-existent CV."""
        response = client.post(
            "/api/cvs/nonexistent-cv-id/sections/predefined",
            json={"section_type": "skills"}
        )
        assert response.status_code == 404
    
    def test_add_predefined_section_persistence(self, client, sample_cv_v2, file_service):
        """Test that added section is persisted."""
        # Add section
        response = client.post(
            f"/api/cvs/{sample_cv_v2.id}/sections/predefined",
            json={"section_type": "languages"}
        )
        assert response.status_code == 201
        section_id = response.json()["section"]["id"]
        
        # Reload CV and verify section exists
        cv = file_service.load_cv(sample_cv_v2.id)
        assert isinstance(cv, CVModelV2)
        section = cv.get_section_by_id(section_id)
        assert section is not None
        assert section.type == SectionType.LANGUAGES


class TestAddCustomSection:
    """Tests for POST /api/cvs/{cv_id}/sections/custom endpoint."""
    
    def test_add_custom_section_success(self, client, sample_cv_v2):
        """Test successfully adding a custom section."""
        response = client.post(
            f"/api/cvs/{sample_cv_v2.id}/sections/custom",
            json={"title": "Publications"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "section" in data
        assert data["section"]["type"] == "custom"
        assert data["section"]["title"] == "Publications"
        assert data["section"]["visible"] is True
        assert data["section"]["order"] == 2
        assert "message" in data
    
    def test_add_custom_section_empty_title(self, client, sample_cv_v2):
        """Test that empty title is rejected."""
        response = client.post(
            f"/api/cvs/{sample_cv_v2.id}/sections/custom",
            json={"title": ""}
        )
        assert response.status_code == 422  # Validation error
    
    def test_add_custom_section_whitespace_title(self, client, sample_cv_v2):
        """Test that whitespace-only title is rejected."""
        response = client.post(
            f"/api/cvs/{sample_cv_v2.id}/sections/custom",
            json={"title": "   "}
        )
        assert response.status_code == 422  # Validation error
    
    def test_add_multiple_custom_sections(self, client, sample_cv_v2):
        """Test adding multiple custom sections with different titles."""
        response1 = client.post(
            f"/api/cvs/{sample_cv_v2.id}/sections/custom",
            json={"title": "Publications"}
        )
        assert response1.status_code == 201
        
        response2 = client.post(
            f"/api/cvs/{sample_cv_v2.id}/sections/custom",
            json={"title": "Awards"}
        )
        assert response2.status_code == 201
        
        # Both should succeed
        assert response1.json()["section"]["title"] == "Publications"
        assert response2.json()["section"]["title"] == "Awards"
    
    def test_add_custom_section_persistence(self, client, sample_cv_v2, file_service):
        """Test that custom section is persisted."""
        response = client.post(
            f"/api/cvs/{sample_cv_v2.id}/sections/custom",
            json={"title": "Volunteer Work"}
        )
        assert response.status_code == 201
        section_id = response.json()["section"]["id"]
        
        # Reload CV and verify section exists
        cv = file_service.load_cv(sample_cv_v2.id)
        section = cv.get_section_by_id(section_id)
        assert section is not None
        assert section.type == SectionType.CUSTOM
        assert section.title == "Volunteer Work"


class TestRemoveSection:
    """Tests for DELETE /api/cvs/{cv_id}/sections/{section_id} endpoint."""
    
    def test_remove_optional_section_success(self, client, sample_cv_v2):
        """Test successfully removing an optional section."""
        # The summary section is optional
        section_id = "section-2"
        
        response = client.delete(
            f"/api/cvs/{sample_cv_v2.id}/sections/{section_id}"
        )
        
        assert response.status_code == 200
        assert "message" in response.json()
    
    def test_remove_core_section_fails(self, client, sample_cv_v2):
        """Test that removing a core section fails."""
        # Personal info is a core section
        section_id = "section-1"
        
        response = client.delete(
            f"/api/cvs/{sample_cv_v2.id}/sections/{section_id}"
        )
        
        assert response.status_code == 400
        assert "core" in response.json()["detail"].lower()
    
    def test_remove_nonexistent_section(self, client, sample_cv_v2):
        """Test removing a section that doesn't exist."""
        response = client.delete(
            f"/api/cvs/{sample_cv_v2.id}/sections/nonexistent-section"
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()
    
    def test_remove_section_persistence(self, client, sample_cv_v2, file_service):
        """Test that section removal is persisted."""
        section_id = "section-2"
        
        # Remove section
        response = client.delete(
            f"/api/cvs/{sample_cv_v2.id}/sections/{section_id}"
        )
        assert response.status_code == 200
        
        # Reload CV and verify section is gone
        cv = file_service.load_cv(sample_cv_v2.id)
        section = cv.get_section_by_id(section_id)
        assert section is None
    
    def test_remove_section_reindexes_order(self, client, sample_cv_v2, file_service):
        """Test that removing a section reindexes remaining sections."""
        # Add a third section
        response = client.post(
            f"/api/cvs/{sample_cv_v2.id}/sections/predefined",
            json={"section_type": "skills"}
        )
        assert response.status_code == 201
        
        # Remove middle section
        response = client.delete(
            f"/api/cvs/{sample_cv_v2.id}/sections/section-2"
        )
        assert response.status_code == 200
        
        # Reload and verify order is consecutive
        cv = file_service.load_cv(sample_cv_v2.id)
        orders = [s.order for s in cv.sections]
        assert orders == [0, 1]  # Should be consecutive


class TestReorderSections:
    """Tests for PUT /api/cvs/{cv_id}/sections/order endpoint."""
    
    def test_reorder_sections_success(self, client, sample_cv_v2, file_service):
        """Test successfully reordering sections."""
        # Reverse the order
        response = client.put(
            f"/api/cvs/{sample_cv_v2.id}/sections/order",
            json={"section_ids": ["section-2", "section-1"]}
        )
        
        assert response.status_code == 200
        
        # Reload and verify new order
        cv = file_service.load_cv(sample_cv_v2.id)
        section_1 = cv.get_section_by_id("section-1")
        section_2 = cv.get_section_by_id("section-2")
        assert section_2.order == 0
        assert section_1.order == 1
    
    def test_reorder_sections_invalid_ids(self, client, sample_cv_v2):
        """Test that invalid section IDs are rejected."""
        response = client.put(
            f"/api/cvs/{sample_cv_v2.id}/sections/order",
            json={"section_ids": ["section-1", "nonexistent"]}
        )
        assert response.status_code == 400
        assert "do not match" in response.json()["detail"].lower()
    
    def test_reorder_sections_missing_ids(self, client, sample_cv_v2):
        """Test that missing section IDs are rejected."""
        response = client.put(
            f"/api/cvs/{sample_cv_v2.id}/sections/order",
            json={"section_ids": ["section-1"]}  # Missing section-2
        )
        assert response.status_code == 400
    
    def test_reorder_sections_preserves_content(self, client, sample_cv_v2, file_service):
        """Test that reordering preserves section content."""
        # Get original content
        original_cv = file_service.load_cv(sample_cv_v2.id)
        original_section_1 = original_cv.get_section_by_id("section-1")
        original_content = original_section_1.content.model_dump()
        
        # Reorder
        response = client.put(
            f"/api/cvs/{sample_cv_v2.id}/sections/order",
            json={"section_ids": ["section-2", "section-1"]}
        )
        assert response.status_code == 200
        
        # Verify content unchanged
        cv = file_service.load_cv(sample_cv_v2.id)
        section_1 = cv.get_section_by_id("section-1")
        assert section_1.content.model_dump() == original_content
    
    def test_reorder_sections_persistence(self, client, sample_cv_v2, file_service):
        """Test that reordering is persisted."""
        response = client.put(
            f"/api/cvs/{sample_cv_v2.id}/sections/order",
            json={"section_ids": ["section-2", "section-1"]}
        )
        assert response.status_code == 200
        
        # Reload and verify order persisted
        cv = file_service.load_cv(sample_cv_v2.id)
        section_1 = cv.get_section_by_id("section-1")
        section_2 = cv.get_section_by_id("section-2")
        assert section_2.order < section_1.order


class TestToggleSectionVisibility:
    """Tests for PATCH /api/cvs/{cv_id}/sections/{section_id}/visibility endpoint."""
    
    def test_toggle_visibility_to_hidden(self, client, sample_cv_v2, file_service):
        """Test hiding a section."""
        response = client.patch(
            f"/api/cvs/{sample_cv_v2.id}/sections/section-2/visibility",
            json={"visible": False}
        )
        
        assert response.status_code == 200
        
        # Verify section is hidden
        cv = file_service.load_cv(sample_cv_v2.id)
        section = cv.get_section_by_id("section-2")
        assert section.visible is False
    
    def test_toggle_visibility_to_visible(self, client, sample_cv_v2, file_service):
        """Test showing a hidden section."""
        # First hide it
        client.patch(
            f"/api/cvs/{sample_cv_v2.id}/sections/section-2/visibility",
            json={"visible": False}
        )
        
        # Then show it
        response = client.patch(
            f"/api/cvs/{sample_cv_v2.id}/sections/section-2/visibility",
            json={"visible": True}
        )
        
        assert response.status_code == 200
        
        # Verify section is visible
        cv = file_service.load_cv(sample_cv_v2.id)
        section = cv.get_section_by_id("section-2")
        assert section.visible is True
    
    def test_toggle_visibility_nonexistent_section(self, client, sample_cv_v2):
        """Test toggling visibility of non-existent section."""
        response = client.patch(
            f"/api/cvs/{sample_cv_v2.id}/sections/nonexistent/visibility",
            json={"visible": False}
        )
        assert response.status_code == 400
    
    def test_toggle_visibility_preserves_content(self, client, sample_cv_v2, file_service):
        """Test that toggling visibility preserves content."""
        # Get original content
        original_cv = file_service.load_cv(sample_cv_v2.id)
        original_section = original_cv.get_section_by_id("section-2")
        original_content = original_section.content.model_dump()
        
        # Hide section
        response = client.patch(
            f"/api/cvs/{sample_cv_v2.id}/sections/section-2/visibility",
            json={"visible": False}
        )
        assert response.status_code == 200
        
        # Verify content unchanged
        cv = file_service.load_cv(sample_cv_v2.id)
        section = cv.get_section_by_id("section-2")
        assert section.content.model_dump() == original_content
    
    def test_toggle_visibility_persistence(self, client, sample_cv_v2, file_service):
        """Test that visibility changes are persisted."""
        response = client.patch(
            f"/api/cvs/{sample_cv_v2.id}/sections/section-2/visibility",
            json={"visible": False}
        )
        assert response.status_code == 200
        
        # Reload and verify visibility persisted
        cv = file_service.load_cv(sample_cv_v2.id)
        section = cv.get_section_by_id("section-2")
        assert section.visible is False
    
    def test_toggle_core_section_visibility(self, client, sample_cv_v2, file_service):
        """Test that core sections can be hidden (edge case from requirements)."""
        # Personal info is core but can be hidden
        response = client.patch(
            f"/api/cvs/{sample_cv_v2.id}/sections/section-1/visibility",
            json={"visible": False}
        )
        
        assert response.status_code == 200
        
        # Verify core section is hidden
        cv = file_service.load_cv(sample_cv_v2.id)
        section = cv.get_section_by_id("section-1")
        assert section.visible is False
        assert section.is_core is True  # Still core, just hidden
