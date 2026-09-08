"""
AI-Powered CV Parser

Provides intelligent CV parsing using LLM services to extract structured data
from various file formats (PDF, DOCX, TXT) with robust section identification,
entity extraction, and ambiguity handling.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from ..models.llm_models import (
    AIParsingRequest,
    AIParsingResult,
    ParsedSection,
    ParsingAmbiguity
)
from ..models.cv_models import CVModel, CVMetadata, PersonalInfo, ContactInfo
from .providers.base import BaseLLMProvider, StructuredLLMResponse, LLMResponse

logger = logging.getLogger(__name__)


class AIParserError(Exception):
    """Base exception for AI parser operations."""
    pass


class UnsupportedFormatError(AIParserError):
    """Raised when file format is not supported."""
    pass


class AIParser:
    """
    AI-powered CV parser that extracts structured data from various formats.
    
    Uses LLM services to intelligently parse CVs with non-standard formatting,
    identify sections, extract entities, and handle ambiguities.
    """
    
    SUPPORTED_FORMATS = ['pdf', 'docx', 'txt', 'html', 'md', 'markdown']
    
    # Section types we expect to find in CVs
    SECTION_TYPES = [
        'personal_info',
        'summary',
        'experience',
        'education',
        'skills',
        'certifications',
        'projects',
        'publications',
        'awards'
    ]
    
    def __init__(self, llm_provider: BaseLLMProvider):
        """
        Initialize AI parser with LLM provider.
        
        Args:
            llm_provider: LLM provider instance for AI parsing
        """
        self.llm_provider = llm_provider
    
    async def parse_cv(self, request: AIParsingRequest) -> AIParsingResult:
        """
        Parse CV from file content using AI.
        
        Args:
            request: Parsing request with file content and format
            
        Returns:
            AIParsingResult with parsed sections and ambiguities
            
        Raises:
            UnsupportedFormatError: If file format is not supported
            AIParserError: If parsing fails
        """
        try:
            # Validate format
            if request.file_format.lower() not in self.SUPPORTED_FORMATS:
                raise UnsupportedFormatError(
                    f"Format '{request.file_format}' not supported. "
                    f"Supported formats: {', '.join(self.SUPPORTED_FORMATS)}"
                )
            
            logger.info(f"Starting AI parsing for {request.file_format} file")
            
            # Check if content is Base64-encoded and extract text if needed
            file_content = request.file_content
            
            # Import here to avoid circular dependency
            from ..utils.file_extraction import is_base64, extract_text_from_base64
            
            if is_base64(file_content):
                logger.info("Detected Base64-encoded content, extracting text...")
                try:
                    file_content = extract_text_from_base64(file_content, request.file_format)
                    logger.info(f"Successfully extracted {len(file_content)} characters from Base64 content")
                except Exception as e:
                    logger.error(f"Failed to extract text from Base64: {e}")
                    raise AIParserError(f"Failed to extract text from file: {str(e)}")
            
            # Step 1: Identify sections in the document
            sections = await self._identify_sections(file_content)
            logger.info(f"Identified {len(sections)} sections")
            
            # Step 2: Parse each section with entity extraction
            parsed_sections = []
            all_ambiguities = []
            
            for section in sections:
                parsed, ambiguities = await self._parse_section(
                    section['type'],
                    section['content'],
                    section['raw_text']
                )
                parsed_sections.append(parsed)
                all_ambiguities.extend(ambiguities)
            
            # Step 3: Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(parsed_sections)
            
            # Step 4: Convert to CV data structure if confidence is high enough
            cv_data = None
            errors = []
            
            if overall_confidence >= 0.6:  # Threshold for attempting conversion
                try:
                    # Anything the conversion has to leave out is reported
                    # rather than dropped in silence: a CV that arrives without
                    # its work history should say so.
                    self._conversion_notes = []
                    cv_data = await self._convert_to_cv_data(parsed_sections)
                    errors.extend(self._conversion_notes)
                except Exception as e:
                    logger.warning(f"Failed to convert to CV data: {e}")
                    errors.append(f"Conversion error: {str(e)}")
            else:
                errors.append(
                    f"Overall confidence ({overall_confidence:.2f}) too low for automatic conversion"
                )
            
            result = AIParsingResult(
                parsed_sections=parsed_sections,
                ambiguities=all_ambiguities,
                overall_confidence=overall_confidence,
                cv_data=cv_data,
                errors=errors,
                model=self.llm_provider.config.model,
                provider=self.llm_provider.config.provider
            )
            
            logger.info(
                f"Parsing complete: {len(parsed_sections)} sections, "
                f"{len(all_ambiguities)} ambiguities, "
                f"confidence: {overall_confidence:.2f}"
            )
            
            return result
            
        except (UnsupportedFormatError, AIParserError):
            raise
        except Exception as e:
            raise AIParserError(f"Unexpected error during AI parsing: {e}")
    
    async def _identify_sections(self, content: str) -> List[Dict[str, Any]]:
        """
        Identify CV sections in the document using AI.
        
        Args:
            content: Raw document content
            
        Returns:
            List of identified sections with type and content
        """
        try:
            # Create prompt for section identification
            prompt = self._create_section_identification_prompt(content)
            
            # Use simple completion instead of structured output to avoid JSON parsing issues
            system_prompt = """You are an expert CV/resume parser. Analyze documents and identify their sections accurately.
Always respond with valid JSON only - no markdown formatting, no explanations, no extra text."""
            
            response: LLMResponse = await self.llm_provider.generate_completion(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.0,  # Zero temperature for maximum consistency
                max_tokens=3000
            )
            
            # Log the raw response for debugging
            logger.info(f"Section identification raw response length: {len(response.content)}")
            logger.info(f"Section identification raw response (first 500 chars): {response.content[:500]}")
            logger.info(f"Section identification raw response (last 200 chars): {response.content[-200:]}")
            
            # Log the input content for debugging
            logger.info(f"Input content length: {len(content)} chars")
            logger.info(f"Input content (first 300 chars): {content[:300]}")
            
            # Parse JSON response
            try:
                # Try to extract JSON if there's extra text
                content_str = response.content.strip()
                
                logger.info(f"Attempting to parse JSON, content starts with: {content_str[:100]}")
                
                # Remove markdown code blocks if present
                if '```' in content_str:
                    logger.info("Detected markdown code block, extracting JSON")
                    # Find the actual JSON content between code blocks
                    start_idx = content_str.find('```')
                    if start_idx != -1:
                        # Skip the opening ``` and optional language identifier
                        start_idx = content_str.find('\n', start_idx) + 1
                        end_idx = content_str.find('```', start_idx)
                        if end_idx != -1:
                            content_str = content_str[start_idx:end_idx].strip()
                    logger.info(f"Extracted JSON (first 200 chars): {content_str[:200]}")
                
                # Try to find JSON object boundaries if there's extra text
                if not content_str.startswith('{'):
                    logger.info("Content doesn't start with {, searching for JSON object")
                    start_idx = content_str.find('{')
                    if start_idx != -1:
                        content_str = content_str[start_idx:]
                        logger.info(f"Found JSON starting at position {start_idx}")
                
                if not content_str.endswith('}'):
                    logger.info("Content doesn't end with }, searching for JSON object end")
                    # Find the last closing brace
                    end_idx = content_str.rfind('}')
                    if end_idx != -1:
                        content_str = content_str[:end_idx + 1]
                        logger.info(f"Truncated to position {end_idx}")
                
                data = json.loads(content_str)
                logger.info(f"Successfully parsed JSON with {len(data.get('sections', []))} sections")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Content that failed to parse (first 1000 chars): {content_str[:1000]}")
                logger.error(f"Content that failed to parse (last 500 chars): {content_str[-500:]}")
                raise
            
            # Extract sections and add content
            sections = []
            lines = content.split('\n')
            
            for section_data in data.get('sections', []):
                # Extract content based on line numbers or title matching
                section_content = self._extract_section_content(
                    lines,
                    section_data.get('title', ''),
                    section_data.get('start_line'),
                    section_data.get('end_line')
                )
                
                logger.info(f"Section '{section_data['type']}' - Title: '{section_data['title']}' - Content length: {len(section_content)} chars")
                
                sections.append({
                    'type': section_data['type'],
                    'title': section_data['title'],
                    'content': section_content,
                    'raw_text': section_content,
                    'confidence': section_data['confidence']
                })
            
            logger.info(f"Successfully identified {len(sections)} sections")
            return sections
            
        except Exception as e:
            logger.error(f"Section identification failed: {e}", exc_info=True)
            # Fallback: return entire content as unknown section
            return [{
                'type': 'unknown',
                'title': 'Full Document',
                'content': content,
                'raw_text': content,
                'confidence': 0.3
            }]
    
    def _create_section_identification_prompt(self, content: str) -> str:
        """Create prompt for section identification."""
        # Identification must see the whole document. At 3000 characters a
        # typical CV was cut off around the end of the first job, so education,
        # skills and certifications — which live at the end — could never be
        # identified and were silently missing from every import.
        truncated_content = (
            content[:self.MAX_IDENTIFICATION_CHARS]
            if len(content) > self.MAX_IDENTIFICATION_CHARS
            else content
        )
        
        return f"""Analyze this CV/resume document and identify all sections present.

CRITICAL: Identify sections from the DOCUMENT CONTENT below. Do NOT use example data.

DOCUMENT CONTENT:
{truncated_content}

VALID SECTION TYPES:
- personal_info: Name, contact details, location (usually at the top)
- summary: Professional summary, objective, or profile statement
- experience: Work history, employment, job positions
- education: Degrees, schools, universities, academic background
- skills: Technical skills, competencies, tools, technologies
- certifications: Certifications, licenses, credentials
- projects: Personal or professional projects
- publications: Research papers, articles, books
- awards: Awards, honors, achievements, recognition

TASK:
Identify each distinct section in the DOCUMENT CONTENT above. For each section found:
- type: Choose from the valid section types above
- title: The EXACT section heading as it appears in the DOCUMENT CONTENT
- confidence: Your confidence level (0.0 to 1.0) that this is the correct section type

IMPORTANT: Use the ACTUAL section titles from the DOCUMENT CONTENT, not generic examples.

OUTPUT FORMAT:
Return ONLY a JSON object with this exact structure (no markdown, no explanations):
{{
  "sections": [
    {{"type": "personal_info", "title": "<actual name from document>", "confidence": 0.95}},
    {{"type": "summary", "title": "<actual section title from document>", "confidence": 0.9}}
  ]
}}

If no clear sections are found, return: {{"sections": []}}

JSON OUTPUT:"""
    
    def _extract_section_content(
        self,
        lines: List[str],
        title: str,
        start_line: Optional[int],
        end_line: Optional[int]
    ) -> str:
        """
        Extract section content from document lines.
        
        Args:
            lines: Document lines
            title: Section title to search for
            start_line: Optional start line number
            end_line: Optional end line number
            
        Returns:
            Extracted section content
        """
        # Line numbers from the model are a hint, not the answer: it has
        # returned ranges covering only the heading, which left the section
        # with 18 characters and nothing to parse. They are used to locate the
        # heading; the extent is worked out from the document itself.
        heading_idx = self._find_heading(lines, title, start_line)

        if heading_idx is None:
            # Fall back to the model's range if it gave one, else the whole
            # document — better to over-supply than to parse an empty string.
            if start_line is not None and end_line is not None and start_line < end_line:
                section = lines[start_line:end_line]
                if len('\n'.join(section).strip()) > len(title) + 8:
                    return '\n'.join(section)
            logger.warning(f"Section title '{title}' not found in document, using full content")
            return '\n'.join(lines)

        return '\n'.join(lines[heading_idx:self._section_end(lines, heading_idx)])

    @staticmethod
    def _heading_level(line: str) -> Optional[int]:
        """Markdown heading level, or None when the line is not a heading."""
        match = re.match(r'^(#{1,6})\s+', line.strip())
        return len(match.group(1)) if match else None

    def _find_heading(
        self,
        lines: List[str],
        title: str,
        start_line: Optional[int]
    ) -> Optional[int]:
        """Locate the line holding `title`, preferring one near `start_line`.

        A CV repeats words like "Experience", so the model's line number is
        used to disambiguate rather than taking the first textual match.
        """
        if not title:
            return None

        pattern = re.compile(re.escape(title.strip()), re.IGNORECASE)
        matches = [i for i, line in enumerate(lines) if pattern.search(line)]
        if not matches:
            return None
        if start_line is None:
            return matches[0]
        return min(matches, key=lambda i: abs(i - start_line))

    def _section_end(self, lines: List[str], heading_idx: int) -> int:
        """Where the section starting at `heading_idx` ends.

        A section runs until the next heading at the same or a higher level.
        Stopping at *any* heading truncated "## Work Experience" at its first
        "### Job Title", so every job was dropped before parsing.
        """
        level = self._heading_level(lines[heading_idx])

        for i in range(heading_idx + 1, len(lines)):
            candidate = self._heading_level(lines[i])
            if candidate is not None:
                if level is None or candidate <= level:
                    return i
                continue
            # In text extracted from a PDF there are no markdown headings, so
            # the end of a section has to be recognised by wording. Treating
            # any title-case line as a heading ended "Work Experience" at its
            # first job title, leaving 15 characters to parse.
            if level is None and self._looks_like_section_heading(lines[i]):
                return i

        return len(lines)

    #: Words that begin a CV section. Used only for documents with no markdown
    #: headings, where wording is the only signal available.
    SECTION_HEADING_WORDS = (
        'summary', 'profile', 'objective', 'experience', 'employment',
        'work history', 'career', 'education', 'qualifications', 'skills',
        'competencies', 'expertise', 'certification', 'accreditation',
        'projects', 'publications', 'awards', 'interests', 'references',
        'achievements', 'affiliations', 'languages',
    )

    @classmethod
    def _looks_like_section_heading(cls, line: str) -> bool:
        """Whether a heading-less line reads as the start of a new section.

        Deliberately conservative: a job title is also a short title-case line,
        and mistaking one for a heading truncates the section that contains it.
        """
        stripped = line.strip().rstrip(':').strip()
        if not stripped or len(stripped) > 40:
            return False
        # A heading is a handful of words, not a sentence.
        if len(stripped.split()) > 4 or stripped.endswith('.'):
            return False

        lowered = stripped.lower()
        return any(word in lowered for word in cls.SECTION_HEADING_WORDS)

    async def _parse_section(
        self,
        section_type: str,
        content: str,
        raw_text: str
    ) -> Tuple[ParsedSection, List[ParsingAmbiguity]]:
        """
        Parse a specific section with entity extraction.
        
        Args:
            section_type: Type of section
            content: Section content
            raw_text: Original raw text
            
        Returns:
            Tuple of (ParsedSection, list of ambiguities)
        """
        try:
            # Create section-specific parsing prompt
            prompt = self._create_section_parsing_prompt(section_type, content)
            
            logger.info(f"Parsing section '{section_type}' with content length: {len(content)} chars")
            if len(content) < 50:
                logger.warning(f"Section '{section_type}' has very short content ({len(content)} chars): {content[:100]}")
            
            # Use simple completion instead of structured output
            system_prompt = """You are an expert CV/resume parser. Extract structured data accurately from CV sections.
Always respond with valid JSON only - no markdown formatting, no explanations, no extra text."""
            
            response: LLMResponse = await self.llm_provider.generate_completion(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.1,  # Low temperature for factual extraction
                max_tokens=2000
            )
            
            # Parse JSON response
            try:
                # Try to extract JSON if there's extra text
                content_str = response.content.strip()
                
                # Remove markdown code blocks if present
                if '```' in content_str:
                    logger.info("Detected markdown code block in section parsing, extracting JSON")
                    start_idx = content_str.find('```')
                    if start_idx != -1:
                        start_idx = content_str.find('\n', start_idx) + 1
                        end_idx = content_str.find('```', start_idx)
                        if end_idx != -1:
                            content_str = content_str[start_idx:end_idx].strip()
                
                # Try to find JSON object boundaries
                if not content_str.startswith('{'):
                    start_idx = content_str.find('{')
                    if start_idx != -1:
                        content_str = content_str[start_idx:]
                
                if not content_str.endswith('}'):
                    end_idx = content_str.rfind('}')
                    if end_idx != -1:
                        content_str = content_str[:end_idx + 1]
                
                data = json.loads(content_str)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from LLM response for section '{section_type}': {e}")
                logger.error(f"Content that failed to parse: {response.content[:500]}")
                data = {"data": {}, "confidence": 0.3, "ambiguities": []}
            
            # Apply regex-based fallback extraction for personal_info
            if section_type == 'personal_info':
                data = self._enhance_personal_info_with_regex(data, content)
            
            # Apply post-processing validation for experience
            if section_type == 'experience':
                data = self._validate_and_fix_experience_data(data, content)
            
            # Extract parsed data
            parsed_data = data.get('data', {})
            confidence = data.get('confidence', 0.5)
            ambiguities_data = data.get('ambiguities', [])
            
            # Convert ambiguities to ParsingAmbiguity objects.
            #
            # The model is asked for objects but often returns plain strings.
            # Assuming a dict raised AttributeError here, and because that threw
            # out of the whole method it discarded the *parsed section too* —
            # so a section that had been read correctly came back empty with
            # 0.3 confidence. A note about an ambiguity must never cost the
            # data it annotates.
            ambiguities = []
            for amb in ambiguities_data or []:
                if isinstance(amb, str):
                    ambiguities.append(ParsingAmbiguity(
                        field='', options=[], context=amb, recommendation=''
                    ))
                elif isinstance(amb, dict):
                    options = amb.get('options') or []
                    ambiguities.append(ParsingAmbiguity(
                        field=str(amb.get('field') or ''),
                        options=[str(o) for o in options] if isinstance(options, list) else [],
                        context=str(amb.get('context') or ''),
                        recommendation=str(amb.get('recommendation') or '')
                    ))
            
            # Create ParsedSection with correct field names
            parsed_section = ParsedSection(
                section_type=section_type,  # Use section_type, not type
                content=parsed_data,
                confidence=confidence,
                raw_text=raw_text  # Include raw_text
            )
            
            logger.info(f"Successfully parsed section '{section_type}' with confidence {confidence}")
            
            return parsed_section, ambiguities
            
        except Exception as e:
            logger.error(f"Failed to parse section '{section_type}': {e}", exc_info=True)
            # Return empty section with low confidence
            return ParsedSection(
                section_type=section_type,  # Use section_type, not type
                content={},
                confidence=0.3,
                raw_text=raw_text  # Include raw_text
            ), []
    
    def _enhance_personal_info_with_regex(self, data: Dict[str, Any], content: str) -> Dict[str, Any]:
        """
        Enhance personal info extraction with regex patterns as fallback.
        
        Args:
            data: LLM-extracted data
            content: Original content
            
        Returns:
            Enhanced data with regex-extracted fields
        """
        parsed_data = data.get('data', {})
        
        # Email regex pattern
        if not parsed_data.get('email'):
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            email_match = re.search(email_pattern, content)
            if email_match:
                parsed_data['email'] = email_match.group(0)
                logger.info(f"Extracted email via regex: {parsed_data['email']}")
        
        # Phone regex patterns (various formats)
        if not parsed_data.get('phone'):
            phone_patterns = [
                r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',  # International
                r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # US format
                r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',  # Simple format
                r'\d{3}[-.\s]?\d{4}[-.\s]?\d{4}',  # UK format
            ]
            for pattern in phone_patterns:
                phone_match = re.search(pattern, content)
                if phone_match:
                    parsed_data['phone'] = phone_match.group(0).strip()
                    logger.info(f"Extracted phone via regex: {parsed_data['phone']}")
                    break
        
        # LinkedIn URL
        if not parsed_data.get('linkedin'):
            linkedin_pattern = r'(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+'
            linkedin_match = re.search(linkedin_pattern, content, re.IGNORECASE)
            if linkedin_match:
                parsed_data['linkedin'] = linkedin_match.group(0)
                logger.info(f"Extracted LinkedIn via regex: {parsed_data['linkedin']}")
        
        # Website URL (excluding LinkedIn)
        if not parsed_data.get('website'):
            website_pattern = r'(?:https?://)?(?:www\.)?(?!linkedin\.com)[\w.-]+\.[\w]{2,}(?:/[\w.-]*)*'
            website_match = re.search(website_pattern, content, re.IGNORECASE)
            if website_match:
                url = website_match.group(0)
                # Filter out email domains
                if '@' not in url:
                    parsed_data['website'] = url
                    logger.info(f"Extracted website via regex: {parsed_data['website']}")
        
        data['data'] = parsed_data
        return data
    
    def _validate_and_fix_experience_data(self, data: Dict[str, Any], content: str) -> Dict[str, Any]:
        """
        Validate and fix common experience data mapping errors.
        
        Args:
            data: LLM-extracted data
            content: Original content
            
        Returns:
            Validated and fixed data
        """
        parsed_data = data.get('data', {})
        entries = parsed_data.get('entries', [])
        
        fixed_entries = []
        for entry in entries:
            # Check if fields are incorrectly mapped
            title = entry.get('title', '')
            company = entry.get('company', '')
            start_date = entry.get('start_date', '')
            
            # Detect if title contains full job header (company name, location, dates)
            if title and ('—' in title or '|' in title or ',' in title) and len(title) > 50:
                logger.warning(f"Detected malformed title field: {title[:100]}")
                # Try to parse it correctly
                fixed_entry = self._parse_experience_header(title, entry)
                if fixed_entry:
                    fixed_entries.append(fixed_entry)
                    continue
            
            # Detect if company contains date range
            if company and any(month in company for month in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December', 'Present', '20']):
                logger.warning(f"Detected date in company field: {company}")
                # Try to fix
                fixed_entry = self._fix_swapped_fields(entry)
                if fixed_entry:
                    fixed_entries.append(fixed_entry)
                    continue
            
            # Detect if start_date contains description text
            if start_date and len(start_date) > 50:
                logger.warning(f"Detected description in start_date field: {start_date[:100]}")
                # Try to fix
                fixed_entry = self._fix_swapped_fields(entry)
                if fixed_entry:
                    fixed_entries.append(fixed_entry)
                    continue
            
            # Entry seems okay, keep it
            fixed_entries.append(entry)
        
        parsed_data['entries'] = fixed_entries
        data['data'] = parsed_data
        return data
    
    def _parse_experience_header(self, header: str, original_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse a malformed experience header to extract correct fields.
        
        Args:
            header: Malformed header string
            original_entry: Original entry dict
            
        Returns:
            Fixed entry dict or None
        """
        try:
            # Pattern: "Job Title — Company (Location) | Date Range"
            # or: "Job Title at Company (Location) | Date Range"
            
            # Try to split by common delimiters
            parts = re.split(r'[—|]', header)
            
            if len(parts) >= 2:
                # First part is likely title and company
                title_company = parts[0].strip()
                
                # Extract title and company
                if ' at ' in title_company:
                    title, company_loc = title_company.split(' at ', 1)
                elif '—' in title_company:
                    title, company_loc = title_company.split('—', 1)
                else:
                    title = title_company
                    company_loc = ''
                
                # Extract company and location from parentheses
                company = company_loc
                location = ''
                if '(' in company_loc and ')' in company_loc:
                    company = company_loc[:company_loc.index('(')].strip()
                    location = company_loc[company_loc.index('(')+1:company_loc.index(')')].strip()
                
                # Extract dates from remaining parts
                date_part = parts[1].strip() if len(parts) > 1 else ''
                start_date, end_date, current = self._parse_date_range(date_part)
                
                return {
                    'title': title.strip(),
                    'company': company.strip(),
                    'location': location,
                    'start_date': start_date,
                    'end_date': end_date,
                    'current': current,
                    'description': original_entry.get('description', ''),
                    'achievements': original_entry.get('achievements', [])
                }
        except Exception as e:
            logger.error(f"Failed to parse experience header: {e}")
        
        return None
    
    def _fix_swapped_fields(self, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fix entry where fields are swapped.
        
        Args:
            entry: Entry with swapped fields
            
        Returns:
            Fixed entry or None
        """
        # If company looks like a date, swap with start_date
        company = entry.get('company', '')
        start_date = entry.get('start_date', '')
        
        if company and any(month in company for month in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December', 'Present']):
            # Swap company and start_date
            entry['start_date'], entry['company'] = company, start_date
            logger.info("Swapped company and start_date fields")
        
        return entry
    
    def _parse_date_range(self, date_str: str) -> Tuple[str, Optional[str], bool]:
        """
        Parse date range string.
        
        Args:
            date_str: Date range string (e.g., "Jan 2020 - Present")
            
        Returns:
            Tuple of (start_date, end_date, is_current)
        """
        current = 'present' in date_str.lower() or 'current' in date_str.lower()
        
        # Split by common separators
        parts = re.split(r'[-–—to]', date_str, maxsplit=1)
        
        start_date = parts[0].strip() if parts else ''
        end_date = parts[1].strip() if len(parts) > 1 else None
        
        if current:
            end_date = None
        
        return start_date, end_date, current
    
    def _create_section_parsing_prompt(self, section_type: str, content: str) -> str:
        """Create section-specific parsing prompt."""
        # A work-history section runs to several thousand characters. At 1500
        # only the first job survived, so a CV with four roles imported with
        # one.
        max_content_length = self.MAX_SECTION_CHARS
        truncated_content = content[:max_content_length] if len(content) > max_content_length else content
        
        base_prompt = f"""CRITICAL INSTRUCTION: Extract data ONLY from the CONTENT section below. Do NOT invent, assume, or use example data.

SECTION TYPE: {section_type}

CONTENT TO EXTRACT FROM:
{truncated_content}

EXTRACTION RULES:
1. Extract ONLY information that appears in the CONTENT above
2. If a field is not present in the CONTENT, use null or empty string ""
3. Do NOT use placeholder data, examples, or made-up information
4. Do NOT copy from these instructions - extract from CONTENT only
5. If the CONTENT is empty or unclear, return low confidence (0.3)
6. IMPORTANT: Map fields correctly - do not put data in wrong fields

"""
        
        if section_type == 'personal_info':
            return base_prompt + """Extract these fields from the CONTENT (use null or "" if not found):
- name: Full name ONLY (e.g., "John Smith")
- title: Job title/role ONLY (e.g., "Senior Software Engineer")
- email: Email address ONLY (e.g., "john@example.com")
- phone: Phone number ONLY (e.g., "+1 234 567 8900")
- location: City and country ONLY (e.g., "London, UK")
- linkedin: LinkedIn URL ONLY (e.g., "https://linkedin.com/in/johnsmith")
- website: Website URL ONLY (e.g., "https://example.com")

IMPORTANT: Each field should contain ONLY what it's labeled for. Do not mix fields.

Respond with JSON only (no markdown, no explanations):
{
  "data": {"name": "...", "title": "...", "email": "...", "phone": "...", "location": "...", "linkedin": "...", "website": "..."},
  "confidence": 0.9,
  "ambiguities": []
}"""
        
        elif section_type == 'experience':
            return base_prompt + """Extract work experience entries from the CONTENT.

CRITICAL FIELD MAPPING RULES:
- title: Job title ONLY (e.g., "Senior Engineer", "Head of Data")
- company: Company name ONLY (e.g., "Google", "Microsoft")
- location: City/country ONLY (e.g., "London, UK", "New York, USA")
- start_date: Start date ONLY (e.g., "January 2020", "2020-01")
- end_date: End date ONLY (e.g., "December 2022", "Present", "2022-12") or null if current
- current: true if currently working there, false otherwise
- description: Brief role description (1-2 sentences)
- achievements: Array of bullet points describing accomplishments

EXAMPLE OF CORRECT EXTRACTION:
If content says: "Head of Engineering at TechCorp (London, UK) | March 2020 - Present"
Extract as:
{
  "title": "Head of Engineering",
  "company": "TechCorp",
  "location": "London, UK",
  "start_date": "March 2020",
  "end_date": null,
  "current": true,
  "description": "",
  "achievements": []
}

DO NOT put the full job header in the title field!
DO NOT put dates in the company field!
DO NOT put descriptions in the start_date field!

Respond with JSON only (no markdown, no explanations):
{
  "data": {"entries": [{"title": "...", "company": "...", "location": "...", "start_date": "...", "end_date": "...", "current": false, "description": "...", "achievements": [...]}]},
  "confidence": 0.9,
  "ambiguities": []
}"""
        
        elif section_type == 'education':
            return base_prompt + """Extract education entries from the CONTENT:
For each education entry found in the CONTENT:
- degree: Degree name (from CONTENT)
- institution: School/university (from CONTENT)
- location: Location (from CONTENT)
- start_date: Start date (from CONTENT)
- end_date: End date (from CONTENT)
- gpa: GPA if mentioned (from CONTENT)
- description: Additional details (from CONTENT)

Respond with JSON only (no markdown, no explanations):
{
  "data": {"entries": [...]},
  "confidence": 0.9,
  "ambiguities": []
}"""
        
        elif section_type == 'skills':
            return base_prompt + """Extract skills from the CONTENT organized by categories:
- categories: List with name and skills array (from CONTENT only)

Respond with JSON only (no markdown, no explanations):
{
  "data": {"categories": [{"name": "...", "skills": [...]}]},
  "confidence": 0.9,
  "ambiguities": []
}"""
        
        elif section_type == 'certifications':
            return base_prompt + """Extract certifications from the CONTENT:
For each certification found in the CONTENT:
- name: Certification name (from CONTENT)
- issuer: Issuing organization (from CONTENT)
- date: Issue date (from CONTENT)
- expiry_date: Expiration date (from CONTENT)

Respond with JSON only (no markdown, no explanations):
{
  "data": {"entries": [...]},
  "confidence": 0.9,
  "ambiguities": []
}"""
        
        else:
            return base_prompt + """Extract relevant information from the CONTENT in a structured format.

Respond with JSON only (no markdown, no explanations):
{
  "data": {...},
  "confidence": 0.7,
  "ambiguities": []
}"""
    
    def _get_section_schema(self, section_type: str) -> Dict[str, Any]:
        """Get JSON schema for section type."""
        base_schema = {
            "type": "object",
            "properties": {
                "data": {"type": "object"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "ambiguities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string"},
                            "options": {"type": "array", "items": {"type": "string"}},
                            "context": {"type": "string"},
                            "recommendation": {"type": "string"}
                        },
                        "required": ["field", "options", "context"]
                    }
                }
            },
            "required": ["data", "confidence"]
        }
        
        # Customize data schema based on section type
        if section_type == 'personal_info':
            base_schema["properties"]["data"] = {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "title": {"type": "string"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                    "location": {"type": "string"},
                    "linkedin": {"type": "string"},
                    "website": {"type": "string"}
                }
            }
        elif section_type == 'experience':
            base_schema["properties"]["data"] = {
                "type": "object",
                "properties": {
                    "entries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "company": {"type": "string"},
                                "location": {"type": "string"},
                                "start_date": {"type": "string"},
                                "end_date": {"type": "string"},
                                "current": {"type": "boolean"},
                                "description": {"type": "string"},
                                "achievements": {"type": "array", "items": {"type": "string"}}
                            }
                        }
                    }
                }
            }
        elif section_type == 'education':
            base_schema["properties"]["data"] = {
                "type": "object",
                "properties": {
                    "entries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "degree": {"type": "string"},
                                "institution": {"type": "string"},
                                "location": {"type": "string"},
                                "start_date": {"type": "string"},
                                "end_date": {"type": "string"},
                                "gpa": {"type": "string"},
                                "description": {"type": "string"}
                            }
                        }
                    }
                }
            }
        elif section_type == 'skills':
            base_schema["properties"]["data"] = {
                "type": "object",
                "properties": {
                    "categories": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "skills": {"type": "array", "items": {"type": "string"}}
                            }
                        }
                    }
                }
            }
        elif section_type == 'certifications':
            base_schema["properties"]["data"] = {
                "type": "object",
                "properties": {
                    "entries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "issuer": {"type": "string"},
                                "date": {"type": "string"},
                                "expiry_date": {"type": "string"}
                            }
                        }
                    }
                }
            }
        
        return base_schema
    
    def _calculate_overall_confidence(self, parsed_sections: List[ParsedSection]) -> float:
        """
        Calculate overall parsing confidence.
        
        Args:
            parsed_sections: List of parsed sections
            
        Returns:
            Overall confidence score (0-1)
        """
        if not parsed_sections:
            return 0.0
        
        # Weight sections by importance
        weights = {
            'personal_info': 2.0,  # Most important
            'experience': 1.5,
            'education': 1.5,
            'skills': 1.0,
            'summary': 1.0,
            'certifications': 0.8,
            'projects': 0.5,
            'publications': 0.5,
            'awards': 0.5
        }
        
        total_weighted_confidence = 0.0
        total_weight = 0.0
        
        for section in parsed_sections:
            weight = weights.get(section.section_type, 0.5)
            total_weighted_confidence += section.confidence * weight
            total_weight += weight
        
        return total_weighted_confidence / total_weight if total_weight > 0 else 0.0
    
    #: How much of the document the model sees when identifying sections.
    #: Comfortably longer than any CV; the cap only guards against a runaway
    #: file, not a normal document.
    MAX_IDENTIFICATION_CHARS = 30_000

    #: How much of one section the model sees when extracting its entities.
    MAX_SECTION_CHARS = 12_000

    #: Notes about data the conversion could not keep, surfaced as errors.
    _conversion_notes: List[str] = []

    async def _convert_to_cv_data(self, parsed_sections: List[ParsedSection]) -> Dict[str, Any]:
        """
        Convert parsed sections to CV data structure.
        
        Args:
            parsed_sections: List of parsed sections
            
        Returns:
            Dictionary with CV data
        """
        cv_data = {
            'metadata': {
                'title': 'AI Parsed CV',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'template_id': 'default'
            },
            'personal_info': {
                'name': 'Unknown',  # Default required field
                'title': '',
                'contact': {
                    'email': '',
                    'phone': '',
                    'address': '',
                    'linkedin': '',
                    'website': ''
                }
            },
            'summary': '',
            'experience': [],
            'education': [],
            'skills': {
                'categories': []
            },
            'certifications': []
        }
        
        # Process each section
        for section in parsed_sections:
            section_type = section.section_type
            content = section.content
            
            if section_type == 'personal_info':
                # Ensure name is never null or empty (required field)
                cv_data['personal_info']['name'] = content.get('name') or 'Unknown'
                cv_data['personal_info']['title'] = content.get('title') or ''
                cv_data['personal_info']['contact'] = {
                    'email': content.get('email') or '',
                    'phone': content.get('phone') or '',
                    'address': content.get('location') or '',
                    'linkedin': content.get('linkedin') or '',
                    'website': content.get('website') or ''
                }
            
            elif section_type == 'summary':
                # The section parser returns this under 'summary'; only 'text'
                # and 'raw' were read, so the summary was always discarded.
                cv_data['summary'] = (
                    content.get('summary')
                    or content.get('text')
                    or content.get('content')
                    or content.get('raw')
                    or ''
                )
            
            elif section_type == 'experience':
                # Keep anything the Experience model accepts, which needs only
                # a title. Requiring company and start_date as well threw away
                # whole jobs whenever a date was not recognised — common from a
                # PDF, which has no headings to anchor the parse — and the CV
                # arrived with no work history at all.
                entries = content.get('entries', [])
                valid_entries = []
                for entry in entries:
                    if isinstance(entry, dict) and entry.get('title'):
                        valid_entries.append(entry)
                    else:
                        logger.warning(f"Skipping experience entry with no title: {entry}")
                dropped = len(entries) - len(valid_entries)
                if dropped:
                    self._conversion_notes.append(
                        f"{dropped} work entr{'y' if dropped == 1 else 'ies'} had no job "
                        "title and were left out"
                    )
                cv_data['experience'] = valid_entries
            
            elif section_type == 'education':
                # Filter out invalid education entries (missing required fields)
                entries = content.get('entries', [])
                valid_entries = []
                for entry in entries:
                    # Education requires: degree, institution
                    if (entry.get('degree') and 
                        entry.get('institution')):
                        valid_entries.append(entry)
                    else:
                        logger.warning(f"Skipping invalid education entry: {entry}")
                dropped = len(entries) - len(valid_entries)
                if dropped:
                    self._conversion_notes.append(
                        f"{dropped} education entr{'y' if dropped == 1 else 'ies'} were "
                        "missing a degree or institution and were left out"
                    )
                cv_data['education'] = valid_entries
            
            elif section_type == 'skills':
                cv_data['skills'] = {
                    'categories': content.get('categories', [])
                }
            
            elif section_type == 'certifications':
                # Filter out invalid certification entries (missing required fields)
                entries = content.get('entries', [])
                valid_entries = []
                for entry in entries:
                    # Certification requires: name, issuer
                    if (entry.get('name') and 
                        entry.get('issuer')):
                        valid_entries.append(entry)
                    else:
                        logger.warning(f"Skipping invalid certification entry: {entry}")
                cv_data['certifications'] = valid_entries
        
        return cv_data
    
    def resolve_ambiguity(
        self,
        parsing_result: AIParsingResult,
        ambiguity_index: int,
        selected_option: str
    ) -> AIParsingResult:
        """
        Resolve an ambiguity by selecting one of the options.
        
        Args:
            parsing_result: Original parsing result
            ambiguity_index: Index of ambiguity to resolve
            selected_option: Selected option from the ambiguity
            
        Returns:
            Updated parsing result with ambiguity resolved
        """
        if ambiguity_index >= len(parsing_result.ambiguities):
            raise ValueError(f"Invalid ambiguity index: {ambiguity_index}")
        
        ambiguity = parsing_result.ambiguities[ambiguity_index]
        
        if selected_option not in ambiguity.options:
            raise ValueError(f"Selected option not in available options: {selected_option}")
        
        # Update the corresponding section with the resolved value
        # This is a simplified implementation - in practice, you'd need to
        # track which section each ambiguity belongs to
        logger.info(
            f"Resolved ambiguity for field '{ambiguity.field}': "
            f"selected '{selected_option}'"
        )
        
        # Remove the resolved ambiguity
        updated_ambiguities = [
            amb for i, amb in enumerate(parsing_result.ambiguities)
            if i != ambiguity_index
        ]
        
        # Create updated result
        updated_result = parsing_result.copy(deep=True)
        updated_result.ambiguities = updated_ambiguities
        
        return updated_result
