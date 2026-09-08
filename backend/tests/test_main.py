"""
Basic tests for the FastAPI application.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    response_data = response.json()
    assert "status" in response_data
    assert "service" in response_data
    assert response_data["service"] == "cv-web-app"
    # Status can be "healthy" or "unhealthy" depending on environment
    assert response_data["status"] in ["healthy", "unhealthy"]

def test_api_root():
    """Test the API root endpoint."""
    response = client.get("/api")
    assert response.status_code == 200
    assert "message" in response.json()