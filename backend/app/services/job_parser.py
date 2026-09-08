"""
Job URL Parser Service

This service handles parsing job descriptions from URLs, including:
- Web scraping for common job boards (LinkedIn, Indeed, Glassdoor, etc.)
- Fallback to generic HTML parsing
- Error handling for inaccessible URLs
- Content extraction and cleaning

Validates: Requirements 12.2
"""

import re
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class JobParserError(Exception):
    """Base exception for job parser errors."""
    pass


class URLAccessError(JobParserError):
    """Raised when URL cannot be accessed."""
    pass


class ContentExtractionError(JobParserError):
    """Raised when content cannot be extracted from page."""
    pass


class JobURLParser:
    """
    Service for parsing job descriptions from URLs.
    
    Supports:
    - LinkedIn job postings
    - Indeed job postings
    - Glassdoor job postings
    - Generic HTML pages with fallback parsing
    """
    
    def __init__(self, timeout: int = 10, user_agent: Optional[str] = None):
        """
        Initialize job URL parser.
        
        Args:
            timeout: Request timeout in seconds (default: 10)
            user_agent: Custom user agent string (optional)
        """
        self.timeout = timeout
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        
        # Job board specific parsers
        self.parsers = {
            'linkedin.com': self._parse_linkedin,
            'indeed.com': self._parse_indeed,
            'glassdoor.com': self._parse_glassdoor,
            'monster.com': self._parse_monster,
            'ziprecruiter.com': self._parse_ziprecruiter,
        }
    
    async def parse_job_url(self, url: str) -> Dict[str, Any]:
        """
        Parse job description from URL.
        
        Args:
            url: URL of the job posting
            
        Returns:
            Dictionary containing:
                - url: Original URL
                - job_title: Extracted job title
                - company: Company name
                - location: Job location
                - description: Full job description text
                - raw_html: Raw HTML content (for debugging)
                - parser_used: Which parser was used
                
        Raises:
            URLAccessError: If URL cannot be accessed
            ContentExtractionError: If content cannot be extracted
            ValueError: If URL is invalid
        """
        # Validate URL
        if not url or not isinstance(url, str):
            raise ValueError("URL must be a non-empty string")
        
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            raise ValueError("URL must start with http:// or https://")
        
        # Parse URL to determine job board
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        # Remove 'www.' prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]
        
        logger.info(f"Parsing job URL: {url} (domain: {domain})")
        
        # Fetch page content
        try:
            html_content = await self._fetch_url(url)
        except Exception as e:
            logger.error(f"Failed to fetch URL {url}: {str(e)}")
            raise URLAccessError(f"Cannot access URL: {str(e)}")
        
        # Parse with appropriate parser
        parser_used = "generic"
        result = None
        
        # Try domain-specific parser first
        for job_board, parser_func in self.parsers.items():
            if job_board in domain:
                logger.info(f"Using {job_board} parser")
                try:
                    result = parser_func(html_content, url)
                    # Check if result has description
                    if result and result.get('description'):
                        parser_used = job_board
                        break
                    else:
                        # Parser succeeded but didn't extract description
                        logger.warning(
                            f"{job_board} parser did not extract description, "
                            "falling back to generic parser"
                        )
                        result = None
                except Exception as e:
                    logger.warning(
                        f"{job_board} parser failed: {str(e)}, "
                        "falling back to generic parser"
                    )
                    result = None
        
        # Fallback to generic parser
        if not result or not result.get('description'):
            logger.info("Using generic HTML parser")
            parser_used = "generic"
            result = self._parse_generic(html_content, url)
        
        # Validate result
        if not result or not result.get('description'):
            raise ContentExtractionError(
                "Could not extract job description from page"
            )
        
        # Add metadata
        result['url'] = url
        result['parser_used'] = parser_used
        
        logger.info(
            f"Successfully parsed job: {result.get('job_title', 'Unknown')} "
            f"at {result.get('company', 'Unknown')}"
        )
        
        return result
    
    async def _fetch_url(self, url: str) -> str:
        """
        Fetch HTML content from URL.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content as string
            
        Raises:
            URLAccessError: If request fails
        """
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            response.raise_for_status()
            return response.text
        except requests.exceptions.Timeout:
            raise URLAccessError(f"Request timed out after {self.timeout} seconds")
        except requests.exceptions.ConnectionError:
            raise URLAccessError("Connection error - check your internet connection")
        except requests.exceptions.HTTPError as e:
            raise URLAccessError(f"HTTP error {e.response.status_code}: {str(e)}")
        except Exception as e:
            raise URLAccessError(f"Failed to fetch URL: {str(e)}")
    
    def _parse_linkedin(self, html: str, url: str) -> Dict[str, Any]:
        """
        Parse LinkedIn job posting.
        
        LinkedIn job postings typically have:
        - Job title in <h1> or <h2> with class containing 'job-title'
        - Company name in elements with class containing 'company'
        - Location in elements with class containing 'location'
        - Description in div with class containing 'description'
        """
        soup = BeautifulSoup(html, 'lxml')
        
        result = {
            'job_title': None,
            'company': None,
            'location': None,
            'description': None,
        }
        
        # Extract job title
        title_selectors = [
            'h1.job-title',
            'h1[class*="job-title"]',
            'h2.job-title',
            'h2[class*="job-title"]',
            'h1.topcard__title',
            'h1[class*="topcard"]',
        ]
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                result['job_title'] = self._clean_text(title_elem.get_text())
                break
        
        # Extract company name
        company_selectors = [
            'a.topcard__org-name-link',
            'a[class*="company"]',
            'span[class*="company"]',
            'div[class*="company"]',
        ]
        for selector in company_selectors:
            company_elem = soup.select_one(selector)
            if company_elem:
                result['company'] = self._clean_text(company_elem.get_text())
                break
        
        # Extract location
        location_selectors = [
            'span.topcard__flavor--bullet',
            'span[class*="location"]',
            'div[class*="location"]',
        ]
        for selector in location_selectors:
            location_elem = soup.select_one(selector)
            if location_elem:
                result['location'] = self._clean_text(location_elem.get_text())
                break
        
        # Extract description
        desc_selectors = [
            'div.description__text',
            'div[class*="description"]',
            'section[class*="description"]',
            'div.show-more-less-html__markup',
        ]
        for selector in desc_selectors:
            desc_elem = soup.select_one(selector)
            if desc_elem:
                result['description'] = self._clean_text(desc_elem.get_text())
                break
        
        return result
    
    def _parse_indeed(self, html: str, url: str) -> Dict[str, Any]:
        """
        Parse Indeed job posting.
        
        Indeed job postings typically have:
        - Job title in <h1> with class containing 'jobsearch-JobInfoHeader-title'
        - Company name in div with class containing 'company'
        - Location in div with class containing 'location'
        - Description in div with id 'jobDescriptionText'
        """
        soup = BeautifulSoup(html, 'lxml')
        
        result = {
            'job_title': None,
            'company': None,
            'location': None,
            'description': None,
        }
        
        # Extract job title
        title_selectors = [
            'h1.jobsearch-JobInfoHeader-title',
            'h1[class*="JobInfoHeader-title"]',
            'h1[class*="job-title"]',
            'span.jobsearch-JobInfoHeader-title',
        ]
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                result['job_title'] = self._clean_text(title_elem.get_text())
                break
        
        # Extract company name
        company_selectors = [
            'div[class*="jobsearch-InlineCompanyRating"] a',
            'div[class*="company"] a',
            'span[class*="company"]',
            'a[data-tn-element="companyName"]',
        ]
        for selector in company_selectors:
            company_elem = soup.select_one(selector)
            if company_elem:
                result['company'] = self._clean_text(company_elem.get_text())
                break
        
        # Extract location
        location_selectors = [
            'div[class*="jobsearch-JobInfoHeader-subtitle"] div',
            'div[class*="location"]',
            'span[class*="location"]',
        ]
        for selector in location_selectors:
            location_elem = soup.select_one(selector)
            if location_elem:
                location_text = self._clean_text(location_elem.get_text())
                # Filter out non-location text
                if location_text and not location_text.lower().startswith('$'):
                    result['location'] = location_text
                    break
        
        # Extract description
        desc_selectors = [
            'div#jobDescriptionText',
            'div[id*="jobDescription"]',
            'div[class*="jobDescription"]',
        ]
        for selector in desc_selectors:
            desc_elem = soup.select_one(selector)
            if desc_elem:
                result['description'] = self._clean_text(desc_elem.get_text())
                break
        
        return result
    
    def _parse_glassdoor(self, html: str, url: str) -> Dict[str, Any]:
        """
        Parse Glassdoor job posting.
        
        Glassdoor job postings typically have:
        - Job title in <h1> or div with class containing 'job-title'
        - Company name in div with class containing 'employer'
        - Location in div with class containing 'location'
        - Description in div with class containing 'desc'
        """
        soup = BeautifulSoup(html, 'lxml')
        
        result = {
            'job_title': None,
            'company': None,
            'location': None,
            'description': None,
        }
        
        # Extract job title
        title_selectors = [
            'h1[class*="job-title"]',
            'div[class*="job-title"]',
            'h1[data-test="job-title"]',
            'div[data-test="job-title"]',
        ]
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                result['job_title'] = self._clean_text(title_elem.get_text())
                break
        
        # Extract company name
        company_selectors = [
            'div[class*="employer"] a',
            'div[data-test="employer-name"]',
            'span[class*="employer"]',
        ]
        for selector in company_selectors:
            company_elem = soup.select_one(selector)
            if company_elem:
                result['company'] = self._clean_text(company_elem.get_text())
                break
        
        # Extract location
        location_selectors = [
            'div[class*="location"]',
            'span[class*="location"]',
            'div[data-test="location"]',
        ]
        for selector in location_selectors:
            location_elem = soup.select_one(selector)
            if location_elem:
                result['location'] = self._clean_text(location_elem.get_text())
                break
        
        # Extract description
        desc_selectors = [
            'div[class*="jobDescriptionContent"]',
            'div[class*="desc"]',
            'div[data-test="description"]',
            'section[class*="description"]',
        ]
        for selector in desc_selectors:
            desc_elem = soup.select_one(selector)
            if desc_elem:
                result['description'] = self._clean_text(desc_elem.get_text())
                break
        
        return result
    
    def _parse_monster(self, html: str, url: str) -> Dict[str, Any]:
        """
        Parse Monster job posting.
        """
        soup = BeautifulSoup(html, 'lxml')
        
        result = {
            'job_title': None,
            'company': None,
            'location': None,
            'description': None,
        }
        
        # Extract job title
        title_elem = soup.select_one('h1[class*="job-title"]') or soup.select_one('h1')
        if title_elem:
            result['job_title'] = self._clean_text(title_elem.get_text())
        
        # Extract company name
        company_elem = soup.select_one('span[class*="company"]') or soup.select_one('div[class*="company"]')
        if company_elem:
            result['company'] = self._clean_text(company_elem.get_text())
        
        # Extract location
        location_elem = soup.select_one('span[class*="location"]') or soup.select_one('div[class*="location"]')
        if location_elem:
            result['location'] = self._clean_text(location_elem.get_text())
        
        # Extract description
        desc_elem = soup.select_one('div[class*="job-description"]') or soup.select_one('div[id*="JobDescription"]')
        if desc_elem:
            result['description'] = self._clean_text(desc_elem.get_text())
        
        return result
    
    def _parse_ziprecruiter(self, html: str, url: str) -> Dict[str, Any]:
        """
        Parse ZipRecruiter job posting.
        """
        soup = BeautifulSoup(html, 'lxml')
        
        result = {
            'job_title': None,
            'company': None,
            'location': None,
            'description': None,
        }
        
        # Extract job title
        title_elem = soup.select_one('h1[class*="job_title"]') or soup.select_one('h1')
        if title_elem:
            result['job_title'] = self._clean_text(title_elem.get_text())
        
        # Extract company name
        company_elem = soup.select_one('a[class*="company"]') or soup.select_one('span[class*="company"]')
        if company_elem:
            result['company'] = self._clean_text(company_elem.get_text())
        
        # Extract location
        location_elem = soup.select_one('a[class*="location"]') or soup.select_one('span[class*="location"]')
        if location_elem:
            result['location'] = self._clean_text(location_elem.get_text())
        
        # Extract description
        desc_elem = soup.select_one('div[class*="job_description"]') or soup.select_one('div[class*="jobDescriptionSection"]')
        if desc_elem:
            result['description'] = self._clean_text(desc_elem.get_text())
        
        return result
    
    def _parse_generic(self, html: str, url: str) -> Dict[str, Any]:
        """
        Generic HTML parser as fallback.
        
        Uses heuristics to extract job information from any HTML page:
        - Looks for common patterns in headings, meta tags, and content
        - Extracts the largest text block as description
        - Uses semantic HTML analysis
        """
        soup = BeautifulSoup(html, 'lxml')
        
        result = {
            'job_title': None,
            'company': None,
            'location': None,
            'description': None,
        }
        
        # Extract job title - try multiple strategies
        # 1. Look for <title> tag
        title_tag = soup.find('title')
        if title_tag:
            title_text = self._clean_text(title_tag.get_text())
            # Remove common suffixes
            title_text = re.sub(r'\s*[-|]\s*(Jobs?|Careers?|Indeed|LinkedIn|Glassdoor).*$', '', title_text, flags=re.IGNORECASE)
            result['job_title'] = title_text
        
        # 2. Look for <h1> tag (often contains job title)
        if not result['job_title']:
            h1_tag = soup.find('h1')
            if h1_tag:
                result['job_title'] = self._clean_text(h1_tag.get_text())
        
        # 3. Look for meta tags
        if not result['job_title']:
            meta_title = soup.find('meta', property='og:title') or soup.find('meta', attrs={'name': 'title'})
            if meta_title and meta_title.get('content'):
                result['job_title'] = self._clean_text(meta_title['content'])
        
        # Extract company - look for common patterns
        company_patterns = [
            r'(?:at|@)\s+([A-Z][A-Za-z0-9\s&.,]+?)(?:\s*[-|]|\s*$)',
            r'Company:\s*([A-Za-z0-9\s&.,]+)',
        ]
        page_text = soup.get_text()
        for pattern in company_patterns:
            match = re.search(pattern, page_text)
            if match:
                result['company'] = self._clean_text(match.group(1))
                break
        
        # Extract location - look for common patterns
        location_patterns = [
            r'Location:\s*([A-Za-z\s,]+)',
            r'(?:in|at)\s+([A-Z][a-z]+,\s*[A-Z]{2})',  # City, ST format
            r'([A-Z][a-z]+,\s*[A-Z][a-z]+)',  # City, State format
        ]
        for pattern in location_patterns:
            match = re.search(pattern, page_text)
            if match:
                result['location'] = self._clean_text(match.group(1))
                break
        
        # Extract description - find the largest text block
        # Look for common description containers
        desc_candidates = []
        
        # Try semantic tags first
        for tag in ['article', 'main', 'section']:
            elements = soup.find_all(tag)
            for elem in elements:
                text = self._clean_text(elem.get_text())
                if len(text) > 200:  # Minimum length for description
                    desc_candidates.append(text)
        
        # Try divs with common class names
        for class_pattern in ['description', 'content', 'job', 'posting', 'details']:
            elements = soup.find_all('div', class_=re.compile(class_pattern, re.IGNORECASE))
            for elem in elements:
                text = self._clean_text(elem.get_text())
                if len(text) > 200:
                    desc_candidates.append(text)
        
        # If no candidates found, use body text
        if not desc_candidates:
            body = soup.find('body')
            if body:
                # Remove script and style elements
                for script in body(['script', 'style', 'nav', 'header', 'footer']):
                    script.decompose()
                text = self._clean_text(body.get_text())
                if len(text) > 200:
                    desc_candidates.append(text)
        
        # Select the longest candidate as description
        if desc_candidates:
            result['description'] = max(desc_candidates, key=len)
        
        return result
    
    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove tabs and replace with spaces
        text = re.sub(r'\t+', ' ', text)
        
        # Normalize multiple newlines to single newline
        text = re.sub(r'\n\n+', '\n', text)
        
        # Remove extra spaces (but preserve newlines)
        lines = text.split('\n')
        lines = [re.sub(r'\s+', ' ', line).strip() for line in lines]
        text = '\n'.join(line for line in lines if line)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text


# Singleton instance
_parser_instance: Optional[JobURLParser] = None


def get_job_parser() -> JobURLParser:
    """
    Get singleton instance of JobURLParser.
    
    Returns:
        JobURLParser instance
    """
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = JobURLParser()
    return _parser_instance
