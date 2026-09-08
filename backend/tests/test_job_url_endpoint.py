"""
Integration Tests for Job URL Parsing Endpoint

Tests the /api/llm/parse-job-url endpoint.
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.job_parser import URLAccessError, ContentExtractionError


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestJobURLParsingEndpoint:
    """Test suite for job URL parsing endpoint."""
    
    def test_parse_job_url_success(self, client):
        """Test successful job URL parsing."""
        # Mock the parser
        mock_result = {
            'url': 'https://www.linkedin.com/jobs/view/123',
            'job_title': 'Senior Software Engineer',
            'company': 'TechCorp',
            'location': 'San Francisco, CA',
            'description': 'We are seeking a talented Senior Software Engineer...',
            'parser_used': 'linkedin.com'
        }
        
        with patch('app.routers.llm_router.get_job_parser') as mock_get_parser:
            mock_parser = AsyncMock()
            mock_parser.parse_job_url.return_value = mock_result
            mock_get_parser.return_value = mock_parser
            
            response = client.post(
                "/api/llm/parse-job-url",
                json={"url": "https://www.linkedin.com/jobs/view/123"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data['url'] == 'https://www.linkedin.com/jobs/view/123'
        assert data['job_title'] == 'Senior Software Engineer'
        assert data['company'] == 'TechCorp'
        assert data['location'] == 'San Francisco, CA'
        assert 'Senior Software Engineer' in data['description']
        assert data['parser_used'] == 'linkedin.com'
        assert data['success'] is True
        assert data['error'] is None
    
    def test_parse_job_url_invalid_url(self, client):
        """Test parsing with invalid URL format."""
        with patch('app.routers.llm_router.get_job_parser') as mock_get_parser:
            mock_parser = AsyncMock()
            mock_parser.parse_job_url.side_effect = ValueError("URL must start with http://")
            mock_get_parser.return_value = mock_parser
            
            response = client.post(
                "/api/llm/parse-job-url",
                json={"url": "invalid-url"}
            )
        
        assert response.status_code == 400
        assert "Invalid URL" in response.json()['detail']
    
    def test_parse_job_url_access_error(self, client):
        """Test parsing with URL access error."""
        with patch('app.routers.llm_router.get_job_parser') as mock_get_parser:
            mock_parser = AsyncMock()
            mock_parser.parse_job_url.side_effect = URLAccessError("Cannot access URL")
            mock_get_parser.return_value = mock_parser
            
            response = client.post(
                "/api/llm/parse-job-url",
                json={"url": "https://example.com/job"}
            )
        
        assert response.status_code == 502
        assert "Cannot access URL" in response.json()['detail']
    
    def test_parse_job_url_extraction_error(self, client):
        """Test parsing with content extraction error."""
        with patch('app.routers.llm_router.get_job_parser') as mock_get_parser:
            mock_parser = AsyncMock()
            mock_parser.parse_job_url.side_effect = ContentExtractionError(
                "Could not extract job description"
            )
            mock_get_parser.return_value = mock_parser
            
            response = client.post(
                "/api/llm/parse-job-url",
                json={"url": "https://example.com/job"}
            )
        
        assert response.status_code == 422
        assert "Cannot extract job description" in response.json()['detail']
    
    def test_parse_job_url_generic_parser(self, client):
        """Test parsing with generic parser fallback."""
        mock_result = {
            'url': 'https://company.com/careers/engineer',
            'job_title': 'Software Engineer',
            'company': None,
            'location': None,
            'description': 'Join our team as a Software Engineer. We are looking for...',
            'parser_used': 'generic'
        }
        
        with patch('app.routers.llm_router.get_job_parser') as mock_get_parser:
            mock_parser = AsyncMock()
            mock_parser.parse_job_url.return_value = mock_result
            mock_get_parser.return_value = mock_parser
            
            response = client.post(
                "/api/llm/parse-job-url",
                json={"url": "https://company.com/careers/engineer"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data['parser_used'] == 'generic'
        assert data['job_title'] == 'Software Engineer'
        assert data['company'] is None
        assert data['location'] is None
        assert len(data['description']) > 0
    
    def test_parse_job_url_indeed(self, client):
        """Test parsing Indeed job posting."""
        mock_result = {
            'url': 'https://www.indeed.com/viewjob?jk=abc123',
            'job_title': 'Backend Developer',
            'company': 'StartupXYZ',
            'location': 'New York, NY',
            'description': 'We are hiring a Backend Developer with Python experience...',
            'parser_used': 'indeed.com'
        }
        
        with patch('app.routers.llm_router.get_job_parser') as mock_get_parser:
            mock_parser = AsyncMock()
            mock_parser.parse_job_url.return_value = mock_result
            mock_get_parser.return_value = mock_parser
            
            response = client.post(
                "/api/llm/parse-job-url",
                json={"url": "https://www.indeed.com/viewjob?jk=abc123"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data['parser_used'] == 'indeed.com'
        assert data['job_title'] == 'Backend Developer'
        assert data['company'] == 'StartupXYZ'
        assert data['location'] == 'New York, NY'
    
    def test_parse_job_url_missing_url(self, client):
        """Test parsing without URL in request."""
        response = client.post(
            "/api/llm/parse-job-url",
            json={}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_parse_job_url_empty_url(self, client):
        """Test parsing with empty URL."""
        response = client.post(
            "/api/llm/parse-job-url",
            json={"url": ""}
        )
        
        # Pydantic validation catches empty string
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
