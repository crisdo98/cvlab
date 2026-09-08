"""
Tests for CV Router endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import tempfile
import os

from app.main import app
from app.models.cv_models import CVModel, CVMetadata, PersonalInfo, ContactInfo
from app.services.cv_service import CVService, CVNotFoundError, CVValidationError

client = TestClient(app)


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def mock_cv_service():
    """Mock CV service for testing."""
    with patch('app.routers.cv_router.get_cv_service') as mock:
        yield mock.return_value


def test_cv_router_endpoints_exist():
    """Test that CV router endpoints are properly registered."""
    # A missing CV legitimately answers 404, so route registration is checked
    # against the app's route table rather than by status code.
    routes = {
        (path, method)
        for route in app.routes
        for path in [getattr(route, "path", None)]
        for method in getattr(route, "methods", set()) or set()
        if path
    }

    assert ("/api/cvs", "GET") in routes
    assert ("/api/cvs", "POST") in routes
    assert ("/api/cvs/{cv_id}", "GET") in routes
    assert ("/api/cvs/{cv_id}", "PUT") in routes
    assert ("/api/cvs/{cv_id}", "DELETE") in routes


def test_list_cvs_success(mock_cv_service):
    """Test successful CV listing."""
    # Mock the service response
    mock_cv_service.list_cvs.return_value = MagicMock(
        cvs=[],
        total=0
    )
    
    response = client.get("/api/cvs")
    assert response.status_code == 200
    data = response.json()
    assert "cvs" in data
    assert "total" in data
    assert data["total"] == 0


def test_get_cv_not_found(mock_cv_service):
    """Test CV not found error handling."""
    mock_cv_service.get_cv.side_effect = CVNotFoundError("CV not found")
    
    response = client.get("/api/cvs/nonexistent-id")
    assert response.status_code == 404
    assert "CV not found" in response.json()["detail"]


def test_create_cv_validation_error(mock_cv_service):
    """Test CV creation validation error handling."""
    # create_cv builds the V2 document in the router rather than going through
    # CVService, so validation is enforced by the request model: a field of the
    # wrong type is rejected before any service call.
    response = client.post("/api/cvs", json={"metadata": "not-an-object"})
    assert response.status_code == 422


def test_update_cv_not_found(mock_cv_service):
    """Test CV update with non-existent CV."""
    mock_cv_service.update_cv.side_effect = CVNotFoundError("CV not found")
    
    response = client.put("/api/cvs/nonexistent-id", json={
        "metadata": {"title": "Updated CV"}
    })
    assert response.status_code == 404
    assert "CV not found" in response.json()["detail"]


def test_delete_cv_not_found(mock_cv_service):
    """Test CV deletion with non-existent CV."""
    mock_cv_service.delete_cv.side_effect = CVNotFoundError("CV not found")
    
    response = client.delete("/api/cvs/nonexistent-id")
    assert response.status_code == 404
    assert "CV not found" in response.json()["detail"]