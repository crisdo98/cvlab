"""
Unit Tests for Job URL Parser Service

Tests the job URL parser functionality including:
- URL validation
- Web scraping for different job boards
- Generic HTML parsing fallback
- Error handling
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.job_parser import (
    JobURLParser,
    JobParserError,
    URLAccessError,
    ContentExtractionError,
    get_job_parser
)


class TestJobURLParser:
    """Test suite for JobURLParser class."""
    
    def test_init_default_params(self):
        """Test parser initialization with default parameters."""
        parser = JobURLParser()
        assert parser.timeout == 10
        assert parser.user_agent is not None
        assert 'Mozilla' in parser.user_agent
        assert len(parser.parsers) > 0
    
    def test_init_custom_params(self):
        """Test parser initialization with custom parameters."""
        custom_agent = "CustomBot/1.0"
        parser = JobURLParser(timeout=20, user_agent=custom_agent)
        assert parser.timeout == 20
        assert parser.user_agent == custom_agent
    
    @pytest.mark.asyncio
    async def test_parse_job_url_invalid_url(self):
        """Test that invalid URLs raise ValueError."""
        parser = JobURLParser()
        
        # Empty URL
        with pytest.raises(ValueError, match="non-empty string"):
            await parser.parse_job_url("")
        
        # Non-string URL
        with pytest.raises(ValueError, match="non-empty string"):
            await parser.parse_job_url(None)
        
        # URL without protocol
        with pytest.raises(ValueError, match="http://"):
            await parser.parse_job_url("linkedin.com/jobs/123")
    
    @pytest.mark.asyncio
    async def test_parse_job_url_fetch_failure(self):
        """Test handling of URL fetch failures."""
        parser = JobURLParser()
        
        with patch.object(parser, '_fetch_url', side_effect=Exception("Network error")):
            with pytest.raises(URLAccessError, match="Cannot access URL"):
                await parser.parse_job_url("https://example.com/job")
    
    @pytest.mark.asyncio
    async def test_parse_linkedin_job(self):
        """Test parsing LinkedIn job posting."""
        parser = JobURLParser()
        
        # Mock HTML content for LinkedIn
        linkedin_html = """
        <html>
            <head><title>Software Engineer - LinkedIn</title></head>
            <body>
                <h1 class="topcard__title">Senior Software Engineer</h1>
                <a class="topcard__org-name-link">TechCorp</a>
                <span class="topcard__flavor--bullet">San Francisco, CA</span>
                <div class="description__text">
                    <p>We are looking for a talented Senior Software Engineer...</p>
                    <p>Requirements: 5+ years of experience in Python and JavaScript</p>
                </div>
            </body>
        </html>
        """
        
        with patch.object(parser, '_fetch_url', return_value=linkedin_html):
            result = await parser.parse_job_url("https://www.linkedin.com/jobs/view/123456")
        
        assert result['url'] == "https://www.linkedin.com/jobs/view/123456"
        assert result['parser_used'] == 'linkedin.com'
        assert result['job_title'] == 'Senior Software Engineer'
        assert result['company'] == 'TechCorp'
        assert result['location'] == 'San Francisco, CA'
        assert 'talented Senior Software Engineer' in result['description']
    
    @pytest.mark.asyncio
    async def test_parse_indeed_job(self):
        """Test parsing Indeed job posting."""
        parser = JobURLParser()
        
        # Mock HTML content for Indeed
        indeed_html = """
        <html>
            <head><title>Backend Developer - Indeed</title></head>
            <body>
                <h1 class="jobsearch-JobInfoHeader-title">Backend Developer</h1>
                <div class="jobsearch-InlineCompanyRating">
                    <a>StartupXYZ</a>
                </div>
                <div class="jobsearch-JobInfoHeader-subtitle">
                    <div>New York, NY</div>
                </div>
                <div id="jobDescriptionText">
                    <p>Join our team as a Backend Developer...</p>
                    <p>Skills: Python, Django, PostgreSQL, AWS</p>
                </div>
            </body>
        </html>
        """
        
        with patch.object(parser, '_fetch_url', return_value=indeed_html):
            result = await parser.parse_job_url("https://www.indeed.com/viewjob?jk=abc123")
        
        assert result['url'] == "https://www.indeed.com/viewjob?jk=abc123"
        assert result['parser_used'] == 'indeed.com'
        assert result['job_title'] == 'Backend Developer'
        assert result['company'] == 'StartupXYZ'
        assert result['location'] == 'New York, NY'
        assert 'Backend Developer' in result['description']
    
    @pytest.mark.asyncio
    async def test_parse_glassdoor_job(self):
        """Test parsing Glassdoor job posting."""
        parser = JobURLParser()
        
        # Mock HTML content for Glassdoor
        glassdoor_html = """
        <html>
            <head><title>Full Stack Engineer - Glassdoor</title></head>
            <body>
                <h1 data-test="job-title">Full Stack Engineer</h1>
                <div data-test="employer-name">InnovateCo</div>
                <div data-test="location">Austin, TX</div>
                <div class="jobDescriptionContent">
                    <p>We're hiring a Full Stack Engineer...</p>
                    <p>Tech stack: React, Node.js, MongoDB</p>
                </div>
            </body>
        </html>
        """
        
        with patch.object(parser, '_fetch_url', return_value=glassdoor_html):
            result = await parser.parse_job_url("https://www.glassdoor.com/job-listing/xyz")
        
        assert result['url'] == "https://www.glassdoor.com/job-listing/xyz"
        assert result['parser_used'] == 'glassdoor.com'
        assert result['job_title'] == 'Full Stack Engineer'
        assert result['company'] == 'InnovateCo'
        assert result['location'] == 'Austin, TX'
        assert 'Full Stack Engineer' in result['description']
    
    @pytest.mark.asyncio
    async def test_parse_generic_job(self):
        """Test generic HTML parsing fallback."""
        parser = JobURLParser()
        
        # Mock HTML content for generic site
        generic_html = """
        <html>
            <head><title>DevOps Engineer at CloudCompany</title></head>
            <body>
                <h1>DevOps Engineer</h1>
                <article>
                    <p>CloudCompany is seeking a DevOps Engineer to join our team.</p>
                    <p>Location: Seattle, WA</p>
                    <p>Requirements:</p>
                    <ul>
                        <li>Experience with Docker and Kubernetes</li>
                        <li>Knowledge of AWS and CI/CD pipelines</li>
                        <li>Strong scripting skills in Python or Bash</li>
                    </ul>
                    <p>Responsibilities:</p>
                    <ul>
                        <li>Manage cloud infrastructure</li>
                        <li>Implement automation solutions</li>
                        <li>Monitor system performance</li>
                    </ul>
                </article>
            </body>
        </html>
        """
        
        with patch.object(parser, '_fetch_url', return_value=generic_html):
            result = await parser.parse_job_url("https://cloudcompany.com/careers/devops")
        
        assert result['url'] == "https://cloudcompany.com/careers/devops"
        assert result['parser_used'] == 'generic'
        assert 'DevOps Engineer' in result['job_title']
        assert result['description'] is not None
        assert len(result['description']) > 100
        assert 'Docker and Kubernetes' in result['description']
    
    @pytest.mark.asyncio
    async def test_parse_job_no_description(self):
        """Test handling of pages with no extractable description."""
        parser = JobURLParser()
        
        # Mock HTML with minimal content
        minimal_html = """
        <html>
            <head><title>Job</title></head>
            <body>
                <h1>Job Title</h1>
                <p>Short text</p>
            </body>
        </html>
        """
        
        with patch.object(parser, '_fetch_url', return_value=minimal_html):
            with pytest.raises(ContentExtractionError, match="Could not extract"):
                await parser.parse_job_url("https://example.com/job")
    
    @pytest.mark.asyncio
    async def test_parse_job_fallback_on_parser_failure(self):
        """Test fallback to generic parser when specific parser fails."""
        parser = JobURLParser()
        
        # Mock HTML that will fail LinkedIn parser but work with generic
        html_content = """
        <html>
            <head><title>Software Engineer</title></head>
            <body>
                <article>
                    <h1>Software Engineer</h1>
                    <p>This is a detailed job description with enough content to be extracted
                    by the generic parser. It includes requirements, responsibilities, and
                    other relevant information about the position. The description is long
                    enough to meet the minimum length requirement for extraction. We are looking
                    for a talented software engineer to join our team and work on exciting projects.
                    You will be responsible for designing, developing, and maintaining software
                    applications. This role requires strong problem-solving skills and the ability
                    to work collaboratively with cross-functional teams.</p>
                </article>
            </body>
        </html>
        """
        
        # Mock _parse_linkedin to raise an exception
        with patch.object(parser, '_fetch_url', return_value=html_content):
            with patch.object(parser, '_parse_linkedin', side_effect=Exception("Parser error")):
                result = await parser.parse_job_url("https://www.linkedin.com/jobs/view/123")
        
        # Should fall back to generic parser
        assert result['parser_used'] == 'generic'
        assert result['description'] is not None
        assert len(result['description']) > 200
    
    def test_clean_text(self):
        """Test text cleaning functionality."""
        parser = JobURLParser()
        
        # Test whitespace normalization
        assert parser._clean_text("  multiple   spaces  ") == "multiple spaces"
        
        # Test newline handling
        assert parser._clean_text("line1\n\n\nline2") == "line1\nline2"
        
        # Test tab handling
        assert parser._clean_text("text\t\twith\ttabs") == "text with tabs"
        
        # Test empty string
        assert parser._clean_text("") == ""
        
        # Test None
        assert parser._clean_text(None) == ""
    
    @pytest.mark.asyncio
    async def test_fetch_url_timeout(self):
        """Test URL fetch timeout handling."""
        parser = JobURLParser(timeout=1)
        
        with patch('requests.get', side_effect=Exception("Timeout")):
            with pytest.raises(URLAccessError):
                await parser._fetch_url("https://example.com")
    
    @pytest.mark.asyncio
    async def test_fetch_url_connection_error(self):
        """Test URL fetch connection error handling."""
        parser = JobURLParser()
        
        import requests
        with patch('requests.get', side_effect=requests.exceptions.ConnectionError()):
            with pytest.raises(URLAccessError, match="Connection error"):
                await parser._fetch_url("https://example.com")
    
    @pytest.mark.asyncio
    async def test_fetch_url_http_error(self):
        """Test URL fetch HTTP error handling."""
        parser = JobURLParser()
        
        import requests
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        
        with patch('requests.get', return_value=mock_response):
            with pytest.raises(URLAccessError, match="HTTP error 404"):
                await parser._fetch_url("https://example.com")
    
    @pytest.mark.asyncio
    async def test_fetch_url_success(self):
        """Test successful URL fetch."""
        parser = JobURLParser()
        
        mock_response = Mock()
        mock_response.text = "<html><body>Test content</body></html>"
        mock_response.raise_for_status = Mock()
        
        with patch('requests.get', return_value=mock_response):
            result = await parser._fetch_url("https://example.com")
        
        assert result == "<html><body>Test content</body></html>"
    
    def test_get_job_parser_singleton(self):
        """Test that get_job_parser returns singleton instance."""
        parser1 = get_job_parser()
        parser2 = get_job_parser()
        
        assert parser1 is parser2
        assert isinstance(parser1, JobURLParser)


class TestJobParserIntegration:
    """Integration tests for job parser with realistic scenarios."""
    
    @pytest.mark.asyncio
    async def test_parse_complete_linkedin_job(self):
        """Test parsing a complete LinkedIn job posting."""
        parser = JobURLParser()
        
        linkedin_html = """
        <!DOCTYPE html>
        <html>
            <head>
                <title>Senior Python Developer - TechCorp - LinkedIn</title>
                <meta property="og:title" content="Senior Python Developer at TechCorp">
            </head>
            <body>
                <div class="topcard">
                    <h1 class="topcard__title">Senior Python Developer</h1>
                    <a class="topcard__org-name-link" href="/company/techcorp">TechCorp</a>
                    <span class="topcard__flavor--bullet">San Francisco Bay Area</span>
                </div>
                <div class="description">
                    <div class="description__text">
                        <strong>About the Role</strong>
                        <p>We are seeking an experienced Senior Python Developer to join our growing team.</p>
                        
                        <strong>Requirements:</strong>
                        <ul>
                            <li>5+ years of professional Python development experience</li>
                            <li>Strong knowledge of Django or Flask frameworks</li>
                            <li>Experience with PostgreSQL and Redis</li>
                            <li>Familiarity with AWS services</li>
                            <li>Bachelor's degree in Computer Science or related field</li>
                        </ul>
                        
                        <strong>Responsibilities:</strong>
                        <ul>
                            <li>Design and implement scalable backend services</li>
                            <li>Collaborate with frontend developers and product team</li>
                            <li>Write clean, maintainable, and well-tested code</li>
                            <li>Participate in code reviews and technical discussions</li>
                        </ul>
                        
                        <strong>Benefits:</strong>
                        <ul>
                            <li>Competitive salary and equity</li>
                            <li>Health, dental, and vision insurance</li>
                            <li>Flexible work arrangements</li>
                            <li>Professional development budget</li>
                        </ul>
                    </div>
                </div>
            </body>
        </html>
        """
        
        with patch.object(parser, '_fetch_url', return_value=linkedin_html):
            result = await parser.parse_job_url("https://www.linkedin.com/jobs/view/123456789")
        
        # Verify all fields are extracted
        assert result['job_title'] == 'Senior Python Developer'
        assert result['company'] == 'TechCorp'
        assert result['location'] == 'San Francisco Bay Area'
        assert result['parser_used'] == 'linkedin.com'
        
        # Verify description content
        description = result['description']
        assert 'experienced Senior Python Developer' in description
        assert '5+ years' in description
        assert 'Django or Flask' in description
        assert 'PostgreSQL' in description
        assert 'scalable backend services' in description
        
        # Verify metadata
        assert result['url'] == "https://www.linkedin.com/jobs/view/123456789"
    
    @pytest.mark.asyncio
    async def test_parse_complete_indeed_job(self):
        """Test parsing a complete Indeed job posting."""
        parser = JobURLParser()
        
        indeed_html = """
        <!DOCTYPE html>
        <html>
            <head>
                <title>Full Stack Engineer - StartupXYZ - Indeed.com</title>
            </head>
            <body>
                <div class="jobsearch-JobComponent">
                    <h1 class="jobsearch-JobInfoHeader-title">Full Stack Engineer</h1>
                    <div class="jobsearch-InlineCompanyRating">
                        <div>
                            <a href="/cmp/StartupXYZ">StartupXYZ</a>
                        </div>
                    </div>
                    <div class="jobsearch-JobInfoHeader-subtitle">
                        <div>New York, NY 10001</div>
                    </div>
                </div>
                <div id="jobDescriptionText">
                    <div>
                        <p><b>About Us:</b></p>
                        <p>StartupXYZ is revolutionizing the tech industry with innovative solutions.</p>
                        
                        <p><b>Job Description:</b></p>
                        <p>We're looking for a talented Full Stack Engineer to help build our platform.</p>
                        
                        <p><b>Required Skills:</b></p>
                        <ul>
                            <li>3+ years of experience with React and Node.js</li>
                            <li>Strong understanding of JavaScript/TypeScript</li>
                            <li>Experience with MongoDB or PostgreSQL</li>
                            <li>Knowledge of RESTful API design</li>
                            <li>Familiarity with Docker and Kubernetes</li>
                        </ul>
                        
                        <p><b>What We Offer:</b></p>
                        <ul>
                            <li>Competitive salary ($120k-$160k)</li>
                            <li>Equity package</li>
                            <li>Remote-friendly culture</li>
                            <li>Learning and development opportunities</li>
                        </ul>
                    </div>
                </div>
            </body>
        </html>
        """
        
        with patch.object(parser, '_fetch_url', return_value=indeed_html):
            result = await parser.parse_job_url("https://www.indeed.com/viewjob?jk=abc123def456")
        
        # Verify extraction
        assert result['job_title'] == 'Full Stack Engineer'
        assert result['company'] == 'StartupXYZ'
        assert result['location'] == 'New York, NY 10001'
        assert result['parser_used'] == 'indeed.com'
        
        # Verify description
        description = result['description']
        assert 'Full Stack Engineer' in description
        assert 'React and Node.js' in description
        assert 'MongoDB or PostgreSQL' in description
        assert 'Docker and Kubernetes' in description


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
