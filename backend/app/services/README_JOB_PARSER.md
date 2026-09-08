# Job URL Parser Service

## Overview

The Job URL Parser service provides functionality to extract job descriptions from URLs of job postings. It supports common job boards with specialized parsers and falls back to generic HTML parsing for other sites.

## Features

- **Multi-Platform Support**: Specialized parsers for:
  - LinkedIn
  - Indeed
  - Glassdoor
  - Monster
  - ZipRecruiter

- **Generic Fallback**: Automatic fallback to generic HTML parsing for unsupported sites

- **Robust Error Handling**: 
  - URL validation
  - Network error handling
  - Content extraction validation

- **Extracted Information**:
  - Job title
  - Company name
  - Location
  - Full job description
  - Parser used (for debugging)

## Usage

### Basic Usage

```python
from app.services.job_parser import get_job_parser

# Get parser instance
parser = get_job_parser()

# Parse a job URL
result = await parser.parse_job_url("https://www.linkedin.com/jobs/view/123456")

# Access extracted data
print(f"Job Title: {result['job_title']}")
print(f"Company: {result['company']}")
print(f"Location: {result['location']}")
print(f"Description: {result['description']}")
print(f"Parser Used: {result['parser_used']}")
```

### API Endpoint

The service is exposed via the REST API:

```bash
POST /api/llm/parse-job-url
Content-Type: application/json

{
  "url": "https://www.linkedin.com/jobs/view/123456"
}
```

Response:

```json
{
  "url": "https://www.linkedin.com/jobs/view/123456",
  "job_title": "Senior Software Engineer",
  "company": "TechCorp",
  "location": "San Francisco, CA",
  "description": "We are seeking a talented Senior Software Engineer...",
  "parser_used": "linkedin.com",
  "success": true,
  "error": null
}
```

### Error Handling

The service raises specific exceptions for different error conditions:

```python
from app.services.job_parser import (
    get_job_parser,
    URLAccessError,
    ContentExtractionError
)

parser = get_job_parser()

try:
    result = await parser.parse_job_url(url)
except ValueError as e:
    # Invalid URL format
    print(f"Invalid URL: {e}")
except URLAccessError as e:
    # Cannot access URL (network error, timeout, etc.)
    print(f"Cannot access URL: {e}")
except ContentExtractionError as e:
    # Cannot extract job description from page
    print(f"Cannot extract content: {e}")
```

## Supported Job Boards

### LinkedIn

Extracts job information from LinkedIn job postings using specialized selectors for LinkedIn's HTML structure.

Example URL: `https://www.linkedin.com/jobs/view/123456`

### Indeed

Parses Indeed job postings with support for Indeed's specific HTML structure.

Example URL: `https://www.indeed.com/viewjob?jk=abc123`

### Glassdoor

Extracts job information from Glassdoor job listings.

Example URL: `https://www.glassdoor.com/job-listing/xyz`

### Monster

Parses Monster job postings.

Example URL: `https://www.monster.com/job-openings/xyz`

### ZipRecruiter

Extracts job information from ZipRecruiter postings.

Example URL: `https://www.ziprecruiter.com/jobs/xyz`

### Generic Sites

For job postings on company career pages or other sites, the parser uses generic HTML parsing with heuristics to extract:
- Job title from `<title>`, `<h1>`, or meta tags
- Company name from common patterns
- Location from common patterns
- Description from the largest text block

## Configuration

### Custom User Agent

```python
from app.services.job_parser import JobURLParser

parser = JobURLParser(
    timeout=15,  # Request timeout in seconds
    user_agent="CustomBot/1.0"  # Custom user agent string
)
```

### Timeout Configuration

The default timeout is 10 seconds. You can adjust it:

```python
parser = JobURLParser(timeout=20)
```

## Implementation Details

### Parser Selection

1. The service analyzes the URL domain
2. If a specialized parser exists for the domain, it's used first
3. If the specialized parser fails or doesn't extract a description, it falls back to generic parsing
4. The generic parser uses semantic HTML analysis and heuristics

### Text Cleaning

All extracted text is cleaned to:
- Normalize whitespace
- Remove extra newlines
- Remove common HTML artifacts
- Preserve paragraph structure

### Error Recovery

The service implements multiple levels of error recovery:
1. Specialized parser failure → Generic parser
2. Network errors → Specific error messages
3. Content extraction failure → Clear error reporting

## Testing

The service includes comprehensive tests:

```bash
# Run unit tests
pytest backend/tests/test_job_parser.py -v

# Run endpoint tests
pytest backend/tests/test_job_url_endpoint.py -v
```

## Dependencies

- `beautifulsoup4`: HTML parsing
- `requests`: HTTP requests
- `lxml`: Fast HTML parsing

## Limitations

1. **Dynamic Content**: The parser works with static HTML. Job boards that load content dynamically with JavaScript may not be fully supported.

2. **Rate Limiting**: Some job boards may rate-limit requests. The service doesn't implement rate limiting or retry logic for rate-limited requests.

3. **Authentication**: The parser doesn't support job postings that require authentication.

4. **Structure Changes**: Job board HTML structures may change over time, requiring parser updates.

## Future Enhancements

Potential improvements:
- Support for more job boards
- JavaScript rendering for dynamic content
- Rate limiting and retry logic
- Caching of parsed results
- Support for authenticated job postings
- Batch URL parsing

## Related Services

- **CVOptimizer**: Uses parsed job descriptions for CV tailoring
- **LLM Service**: Analyzes job descriptions for requirements and keywords
- **Job Tailoring**: Provides suggestions based on parsed job descriptions

## Troubleshooting

### "Cannot access URL" Error

- Check internet connectivity
- Verify the URL is accessible in a browser
- Check if the site requires authentication
- Verify the site isn't blocking automated requests

### "Cannot extract job description" Error

- The page may not contain a job description
- The HTML structure may be incompatible
- Try accessing the URL in a browser to verify content
- Check if the page requires JavaScript to load content

### Empty or Incomplete Extraction

- The generic parser may not work well with all HTML structures
- Consider adding a specialized parser for the site
- Check if the page uses non-standard HTML structure

## Contributing

To add support for a new job board:

1. Add a new parser method in `JobURLParser` class
2. Register the parser in the `self.parsers` dictionary
3. Add tests for the new parser
4. Update this documentation

Example:

```python
def _parse_newjobboard(self, html: str, url: str) -> Dict[str, Any]:
    """Parse NewJobBoard job posting."""
    soup = BeautifulSoup(html, 'lxml')
    
    result = {
        'job_title': None,
        'company': None,
        'location': None,
        'description': None,
    }
    
    # Add extraction logic here
    
    return result
```

Then register it:

```python
self.parsers = {
    'linkedin.com': self._parse_linkedin,
    'indeed.com': self._parse_indeed,
    'newjobboard.com': self._parse_newjobboard,  # Add here
    # ...
}
```
