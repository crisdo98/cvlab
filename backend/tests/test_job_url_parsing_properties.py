"""
Property-Based Tests for Job URL Parsing

Feature: cv-web-app, Property 32: Job URL Parsing
Validates: Requirements 12.2

Property 32: Job URL Parsing
For any valid URL to a job posting, the system should successfully fetch
and extract the job description content.

This test validates that URL parsing correctly handles different job boards,
URL formats, and HTML structures while providing appropriate error handling.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck, assume
from typing import Dict, Any
from unittest.mock import patch, Mock
import requests

from app.services.job_parser import (
    JobURLParser,
    URLAccessError,
    ContentExtractionError,
    get_job_parser
)


# Hypothesis strategies for generating test data
@st.composite
def valid_url_strategy(draw):
    """Generate valid job posting URLs for different job boards."""
    # Job boards
    job_boards = [
        "linkedin.com",
        "indeed.com",
        "glassdoor.com",
        "monster.com",
        "ziprecruiter.com",
        "careers.example.com",  # Generic company career page
    ]
    
    # URL patterns
    protocols = ["https://", "http://"]
    www_prefix = draw(st.sampled_from(["www.", ""]))
    protocol = draw(st.sampled_from(protocols))
    job_board = draw(st.sampled_from(job_boards))
    
    # Generate path based on job board
    if "linkedin" in job_board:
        job_id = draw(st.integers(min_value=1000000, max_value=9999999999))
        path = f"/jobs/view/{job_id}"
    elif "indeed" in job_board:
        job_key = draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Nd')),
            min_size=10,
            max_size=20
        ))
        path = f"/viewjob?jk={job_key}"
    elif "glassdoor" in job_board:
        job_id = draw(st.integers(min_value=100000, max_value=999999))
        path = f"/job-listing/{job_id}"
    elif "monster" in job_board:
        job_id = draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Nd', 'Pd')),
            min_size=10,
            max_size=30
        ))
        path = f"/job-openings/{job_id}"
    elif "ziprecruiter" in job_board:
        job_id = draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Nd')),
            min_size=15,
            max_size=25
        ))
        path = f"/jobs/{job_id}"
    else:  # Generic
        job_slug = draw(st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Pd')),
            min_size=10,
            max_size=40
        ))
        path = f"/careers/{job_slug}"
    
    url = f"{protocol}{www_prefix}{job_board}{path}"
    
    return url, job_board


@st.composite
def job_html_strategy(draw, job_board: str):
    """Generate realistic HTML content for job postings."""
    # Job titles
    job_titles = [
        "Senior Software Engineer",
        "Full Stack Developer",
        "Backend Engineer",
        "Frontend Developer",
        "DevOps Engineer",
        "Data Scientist",
        "Product Manager",
        "Engineering Manager"
    ]
    
    # Companies
    companies = [
        "TechCorp",
        "StartupXYZ",
        "InnovateCo",
        "BigTech Inc",
        "CloudCompany"
    ]
    
    # Locations
    locations = [
        "San Francisco, CA",
        "New York, NY",
        "Seattle, WA",
        "Austin, TX",
        "Boston, MA",
        "Remote"
    ]
    
    # Skills
    all_skills = [
        "Python", "Java", "JavaScript", "TypeScript", "React", "Vue",
        "Node.js", "Django", "Flask", "Spring Boot", "PostgreSQL",
        "MongoDB", "AWS", "Azure", "Docker", "Kubernetes", "CI/CD"
    ]
    
    job_title = draw(st.sampled_from(job_titles))
    company = draw(st.sampled_from(companies))
    location = draw(st.sampled_from(locations))
    
    # Select 3-6 skills
    num_skills = draw(st.integers(min_value=3, max_value=6))
    skills = draw(st.lists(
        st.sampled_from(all_skills),
        min_size=num_skills,
        max_size=num_skills,
        unique=True
    ))
    
    # Generate description
    description_parts = [
        f"We are seeking a talented {job_title} to join our team.",
        f"This is an exciting opportunity to work with {', '.join(skills[:3])}.",
        "Requirements:",
        "- 3+ years of professional experience",
        f"- Strong proficiency in {skills[0]} and {skills[1]}",
        f"- Experience with {', '.join(skills[2:])}",
        "- Bachelor's degree in Computer Science or related field",
        "- Excellent communication and problem-solving skills",
        "",
        "Responsibilities:",
        "- Design and develop scalable applications",
        "- Collaborate with cross-functional teams",
        "- Participate in code reviews and technical discussions",
        "- Mentor junior developers",
        "",
        "Benefits:",
        "- Competitive salary and equity",
        "- Health insurance",
        "- Flexible work arrangements",
        "- Professional development opportunities"
    ]
    
    description_text = "\n".join(description_parts)
    
    # Generate HTML based on job board
    if "linkedin" in job_board:
        html = f"""
        <!DOCTYPE html>
        <html>
            <head>
                <title>{job_title} - {company} - LinkedIn</title>
            </head>
            <body>
                <div class="topcard">
                    <h1 class="topcard__title">{job_title}</h1>
                    <a class="topcard__org-name-link">{company}</a>
                    <span class="topcard__flavor--bullet">{location}</span>
                </div>
                <div class="description">
                    <div class="description__text">
                        <p>{description_text.replace(chr(10), '</p><p>')}</p>
                    </div>
                </div>
            </body>
        </html>
        """
    elif "indeed" in job_board:
        html = f"""
        <!DOCTYPE html>
        <html>
            <head>
                <title>{job_title} - {company} - Indeed</title>
            </head>
            <body>
                <h1 class="jobsearch-JobInfoHeader-title">{job_title}</h1>
                <div class="jobsearch-InlineCompanyRating">
                    <a>{company}</a>
                </div>
                <div class="jobsearch-JobInfoHeader-subtitle">
                    <div>{location}</div>
                </div>
                <div id="jobDescriptionText">
                    <p>{description_text.replace(chr(10), '</p><p>')}</p>
                </div>
            </body>
        </html>
        """
    elif "glassdoor" in job_board:
        html = f"""
        <!DOCTYPE html>
        <html>
            <head>
                <title>{job_title} - {company} - Glassdoor</title>
            </head>
            <body>
                <h1 data-test="job-title">{job_title}</h1>
                <div data-test="employer-name">{company}</div>
                <div data-test="location">{location}</div>
                <div class="jobDescriptionContent">
                    <p>{description_text.replace(chr(10), '</p><p>')}</p>
                </div>
            </body>
        </html>
        """
    else:  # Generic or other job boards
        html = f"""
        <!DOCTYPE html>
        <html>
            <head>
                <title>{job_title} at {company}</title>
            </head>
            <body>
                <h1>{job_title}</h1>
                <article>
                    <p><strong>Company:</strong> {company}</p>
                    <p><strong>Location:</strong> {location}</p>
                    <div class="job-description">
                        <p>{description_text.replace(chr(10), '</p><p>')}</p>
                    </div>
                </article>
            </body>
        </html>
        """
    
    expected_data = {
        "job_title": job_title,
        "company": company,
        "location": location,
        "skills": skills,
        "description_length": len(description_text)
    }
    
    return html, expected_data


@st.composite
def invalid_url_strategy(draw):
    """Generate invalid URLs for error testing."""
    invalid_patterns = [
        "",  # Empty string
        "   ",  # Whitespace only
        "not-a-url",  # No protocol
        "ftp://example.com/job",  # Wrong protocol
        "linkedin.com/jobs/123",  # Missing protocol
        "http://",  # Incomplete URL
        "https://",  # Incomplete URL
    ]
    
    return draw(st.sampled_from(invalid_patterns))


# Property Tests
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    url_and_board=valid_url_strategy(),
    data=st.data()
)
@pytest.mark.asyncio
async def test_property_job_url_parsing_success(url_and_board, data):
    """
    Property 32: Job URL Parsing - Successful Extraction
    
    For any valid URL to a job posting, the system should successfully
    fetch and extract the job description content.
    
    Validates: Requirements 12.2
    """
    url, job_board = url_and_board
    
    # Generate HTML content for this job board using data.draw()
    html_content, expected_data = data.draw(job_html_strategy(job_board))
    
    # Create parser
    parser = JobURLParser()
    
    # Mock the fetch to return our generated HTML
    with patch.object(parser, '_fetch_url', return_value=html_content):
        result = await parser.parse_job_url(url)
    
    # Property assertions
    # 1. Result should not be None and should be a dictionary
    assert result is not None, "Parse result should not be None"
    assert isinstance(result, dict), "Parse result should be a dictionary"
    
    # 2. URL should be preserved in result
    assert 'url' in result, "Result should contain original URL"
    assert result['url'] == url, "Original URL should be preserved"
    
    # 3. Parser used should be identified
    assert 'parser_used' in result, "Result should indicate which parser was used"
    assert isinstance(result['parser_used'], str), "Parser name should be a string"
    assert len(result['parser_used']) > 0, "Parser name should not be empty"
    
    # 4. Job title should be extracted
    assert 'job_title' in result, "Result should contain job title"
    if result['job_title']:  # May be None for some parsers
        assert isinstance(result['job_title'], str), "Job title should be a string"
        assert len(result['job_title'].strip()) > 0, "Job title should not be empty"
        assert len(result['job_title']) < 200, "Job title should be reasonable length"
    
    # 5. Description should be extracted and non-empty
    assert 'description' in result, "Result should contain description"
    assert result['description'] is not None, "Description should not be None"
    assert isinstance(result['description'], str), "Description should be a string"
    assert len(result['description'].strip()) > 0, "Description should not be empty"
    assert len(result['description']) >= 100, \
        "Description should have substantial content (>= 100 chars)"
    
    # 6. Company should be present (may be None for some parsers)
    assert 'company' in result, "Result should have company field"
    if result['company']:
        assert isinstance(result['company'], str), "Company should be a string"
        assert len(result['company'].strip()) > 0, "Company should not be empty"
        assert len(result['company']) < 200, "Company should be reasonable length"
    
    # 7. Location should be present (may be None for some parsers)
    assert 'location' in result, "Result should have location field"
    if result['location']:
        assert isinstance(result['location'], str), "Location should be a string"
        assert len(result['location'].strip()) > 0, "Location should not be empty"
        assert len(result['location']) < 200, "Location should be reasonable length"
    
    # 8. Description should contain relevant content
    description_lower = result['description'].lower()
    
    # Should contain some job-related keywords
    job_keywords = [
        'experience', 'requirements', 'responsibilities', 'skills',
        'qualifications', 'position', 'role', 'team', 'work'
    ]
    found_keywords = sum(1 for keyword in job_keywords if keyword in description_lower)
    assert found_keywords >= 2, \
        f"Description should contain job-related keywords (found {found_keywords})"
    
    # 9. Description should not contain excessive HTML artifacts
    html_artifacts = ['<div>', '<p>', '<span>', '<script>', '<style>']
    artifacts_found = sum(1 for artifact in html_artifacts if artifact in result['description'])
    assert artifacts_found == 0, \
        "Description should not contain HTML tags (should be cleaned)"
    
    # 10. Text should be properly cleaned (no excessive whitespace)
    assert '  ' not in result['description'] or result['description'].count('  ') < 5, \
        "Description should not have excessive double spaces"
    assert '\n\n\n' not in result['description'], \
        "Description should not have excessive newlines"
    assert '\t' not in result['description'], \
        "Description should not contain tab characters"


@settings(
    max_examples=15,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    url_and_board=valid_url_strategy(),
    data=st.data()
)
@pytest.mark.asyncio
async def test_property_job_url_parsing_parser_selection(url_and_board, data):
    """
    Property 32: Job URL Parsing - Parser Selection
    
    For any job board URL, the system should select the appropriate
    parser based on the domain.
    
    Validates: Requirements 12.2
    """
    url, job_board = url_and_board
    
    # Generate HTML content using data.draw()
    html_content, expected_data = data.draw(job_html_strategy(job_board))
    
    # Create parser
    parser = JobURLParser()
    
    # Mock the fetch
    with patch.object(parser, '_fetch_url', return_value=html_content):
        result = await parser.parse_job_url(url)
    
    # Property assertions
    # 1. Parser should be selected based on domain
    parser_used = result['parser_used']
    
    # Known job boards should use specific parsers
    if 'linkedin' in job_board:
        assert parser_used == 'linkedin.com' or parser_used == 'generic', \
            "LinkedIn URLs should use LinkedIn parser or fall back to generic"
    elif 'indeed' in job_board:
        assert parser_used == 'indeed.com' or parser_used == 'generic', \
            "Indeed URLs should use Indeed parser or fall back to generic"
    elif 'glassdoor' in job_board:
        assert parser_used == 'glassdoor.com' or parser_used == 'generic', \
            "Glassdoor URLs should use Glassdoor parser or fall back to generic"
    elif 'monster' in job_board:
        assert parser_used == 'monster.com' or parser_used == 'generic', \
            "Monster URLs should use Monster parser or fall back to generic"
    elif 'ziprecruiter' in job_board:
        assert parser_used == 'ziprecruiter.com' or parser_used == 'generic', \
            "ZipRecruiter URLs should use ZipRecruiter parser or fall back to generic"
    else:
        # Unknown job boards should use generic parser
        assert parser_used == 'generic', \
            "Unknown job boards should use generic parser"
    
    # 2. Parser should successfully extract content
    assert result['description'] is not None, \
        f"Parser '{parser_used}' should extract description"
    assert len(result['description']) > 0, \
        f"Parser '{parser_used}' should extract non-empty description"


@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    invalid_url=invalid_url_strategy()
)
@pytest.mark.asyncio
async def test_property_job_url_parsing_invalid_urls(invalid_url):
    """
    Property 32: Job URL Parsing - Invalid URL Handling
    
    For any invalid URL, the system should raise appropriate errors
    with clear error messages.
    
    Validates: Requirements 12.2
    """
    # Create parser
    parser = JobURLParser()
    
    # Property assertions
    # Invalid URLs should raise ValueError or URLAccessError
    with pytest.raises((ValueError, URLAccessError)) as exc_info:
        await parser.parse_job_url(invalid_url)
    
    # Error message should be informative
    error_message = str(exc_info.value).lower()
    assert len(error_message) > 0, "Error message should not be empty"
    
    # Error message should indicate the problem
    assert any(keyword in error_message for keyword in [
        'url', 'string', 'http', 'https', 'empty', 'invalid', 'access', 'host'
    ]), "Error message should indicate URL validation issue"


@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    url_and_board=valid_url_strategy()
)
@pytest.mark.asyncio
async def test_property_job_url_parsing_network_errors(url_and_board):
    """
    Property 32: Job URL Parsing - Network Error Handling
    
    For any URL, when network errors occur, the system should raise
    URLAccessError with appropriate error messages.
    
    Validates: Requirements 12.2
    """
    url, job_board = url_and_board
    
    # Create parser
    parser = JobURLParser()
    
    # Test different network error scenarios
    network_errors = [
        (requests.exceptions.Timeout(), "timeout"),
        (requests.exceptions.ConnectionError(), "connection"),
        (Exception("Network error"), "access"),
    ]
    
    for error, expected_keyword in network_errors:
        # Mock fetch to raise error
        with patch.object(parser, '_fetch_url', side_effect=error):
            # Should raise URLAccessError
            with pytest.raises(URLAccessError) as exc_info:
                await parser.parse_job_url(url)
            
            # Error message should be informative
            error_message = str(exc_info.value).lower()
            assert len(error_message) > 0, "Error message should not be empty"
            assert expected_keyword in error_message or 'cannot access' in error_message, \
                f"Error message should indicate {expected_keyword} issue"


@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    url_and_board=valid_url_strategy()
)
@pytest.mark.asyncio
async def test_property_job_url_parsing_empty_content(url_and_board):
    """
    Property 32: Job URL Parsing - Empty Content Handling
    
    For any URL that returns HTML without extractable job content,
    the system should raise ContentExtractionError.
    
    Validates: Requirements 12.2
    """
    url, job_board = url_and_board
    
    # Create parser
    parser = JobURLParser()
    
    # HTML with no job content
    empty_html_variants = [
        "<html><body></body></html>",
        "<html><body><p>Short</p></body></html>",
        "<html><head><title>Page</title></head><body><div>Text</div></body></html>",
    ]
    
    for empty_html in empty_html_variants:
        # Mock fetch to return empty HTML
        with patch.object(parser, '_fetch_url', return_value=empty_html):
            # Should raise ContentExtractionError
            with pytest.raises(ContentExtractionError) as exc_info:
                await parser.parse_job_url(url)
            
            # Error message should be informative
            error_message = str(exc_info.value).lower()
            assert len(error_message) > 0, "Error message should not be empty"
            assert 'extract' in error_message or 'description' in error_message, \
                "Error message should indicate extraction failure"


@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    url_and_board=valid_url_strategy()
)
@pytest.mark.asyncio
async def test_property_job_url_parsing_fallback_behavior(url_and_board):
    """
    Property 32: Job URL Parsing - Fallback to Generic Parser
    
    For any URL, when the specific parser fails, the system should
    fall back to the generic parser.
    
    Validates: Requirements 12.2
    """
    url, job_board = url_and_board
    
    # Generate HTML that will work with generic parser
    generic_html = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>Software Engineer at TechCorp</title>
        </head>
        <body>
            <article>
                <h1>Software Engineer</h1>
                <p>We are seeking a talented Software Engineer to join our team.</p>
                <p>Requirements: 3+ years of experience in software development,
                strong proficiency in Python and JavaScript, experience with React
                and Node.js, knowledge of AWS and Docker, Bachelor's degree in
                Computer Science or related field, excellent communication and
                problem-solving skills.</p>
                <p>Responsibilities: Design and develop scalable applications,
                collaborate with cross-functional teams, participate in code reviews
                and technical discussions, mentor junior developers.</p>
                <p>Benefits: Competitive salary and equity, health insurance,
                flexible work arrangements, professional development opportunities.</p>
            </article>
        </body>
    </html>
    """
    
    # Create parser
    parser = JobURLParser()
    
    # Mock fetch to return generic HTML
    with patch.object(parser, '_fetch_url', return_value=generic_html):
        # If this is a known job board, mock its specific parser to fail
        if 'linkedin' in job_board:
            with patch.object(parser, '_parse_linkedin', side_effect=Exception("Parser error")):
                result = await parser.parse_job_url(url)
        elif 'indeed' in job_board:
            with patch.object(parser, '_parse_indeed', side_effect=Exception("Parser error")):
                result = await parser.parse_job_url(url)
        elif 'glassdoor' in job_board:
            with patch.object(parser, '_parse_glassdoor', side_effect=Exception("Parser error")):
                result = await parser.parse_job_url(url)
        else:
            # For unknown job boards, just parse normally
            result = await parser.parse_job_url(url)
    
    # Property assertions
    # 1. Should successfully parse with fallback
    assert result is not None, "Should successfully parse with fallback"
    assert result['description'] is not None, "Should extract description with fallback"
    assert len(result['description']) > 100, "Should extract substantial content"
    
    # 2. For known job boards with mocked failures, should use generic parser
    if any(board in job_board for board in ['linkedin', 'indeed', 'glassdoor']):
        assert result['parser_used'] == 'generic', \
            "Should fall back to generic parser when specific parser fails"


@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    url_and_board=valid_url_strategy()
)
@pytest.mark.asyncio
async def test_property_job_url_parsing_text_cleaning(url_and_board):
    """
    Property 32: Job URL Parsing - Text Cleaning
    
    For any extracted content, the system should properly clean and
    normalize the text.
    
    Validates: Requirements 12.2
    """
    url, job_board = url_and_board
    
    # Generate HTML with messy formatting
    messy_html = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>Software Engineer</title>
        </head>
        <body>
            <h1>  Software   Engineer  </h1>
            <article>
                <p>We are seeking    a talented   Software Engineer.</p>
                <p>Requirements:
                
                
                - 3+ years of experience
                
                - Strong proficiency in Python
                
                
                - Knowledge of AWS</p>
                <p>Responsibilities:	Design	and	develop	applications</p>
            </article>
        </body>
    </html>
    """
    
    # Create parser
    parser = JobURLParser()
    
    # Mock fetch to return messy HTML
    with patch.object(parser, '_fetch_url', return_value=messy_html):
        result = await parser.parse_job_url(url)
    
    # Property assertions
    # 1. Job title should be cleaned
    if result['job_title']:
        assert result['job_title'] == result['job_title'].strip(), \
            "Job title should not have leading/trailing whitespace"
        assert '  ' not in result['job_title'], \
            "Job title should not have multiple consecutive spaces"
    
    # 2. Company should be cleaned
    if result['company']:
        assert result['company'] == result['company'].strip(), \
            "Company should not have leading/trailing whitespace"
        assert '  ' not in result['company'], \
            "Company should not have multiple consecutive spaces"
    
    # 3. Location should be cleaned
    if result['location']:
        assert result['location'] == result['location'].strip(), \
            "Location should not have leading/trailing whitespace"
        assert '  ' not in result['location'], \
            "Location should not have multiple consecutive spaces"
    
    # 4. Description should be cleaned
    assert result['description'] == result['description'].strip(), \
        "Description should not have leading/trailing whitespace"
    
    # Should not have excessive whitespace
    assert result['description'].count('  ') < 5, \
        "Description should not have many double spaces"
    
    # Should not have excessive newlines
    assert '\n\n\n' not in result['description'], \
        "Description should not have triple newlines"
    
    # Should not have tabs
    assert '\t' not in result['description'], \
        "Description should not contain tabs"


@pytest.mark.asyncio
async def test_property_job_url_parsing_singleton_consistency():
    """
    Property 32: Job URL Parsing - Singleton Consistency
    
    The get_job_parser function should always return the same instance.
    
    Validates: Requirements 12.2
    """
    # Get parser instances
    parser1 = get_job_parser()
    parser2 = get_job_parser()
    parser3 = get_job_parser()
    
    # Property assertions
    # 1. All instances should be the same object
    assert parser1 is parser2, "get_job_parser should return singleton"
    assert parser2 is parser3, "get_job_parser should return singleton"
    assert parser1 is parser3, "get_job_parser should return singleton"
    
    # 2. Should be JobURLParser instance
    assert isinstance(parser1, JobURLParser), \
        "Singleton should be JobURLParser instance"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
