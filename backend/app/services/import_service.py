"""
Import Service

Provides functionality for importing CV documents from Markdown files.
Handles YAML frontmatter parsing and conversion to CV data models with
comprehensive error handling and validation. Includes AI-powered fallback
parsing for non-standard formats.
"""

import re
import yaml
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import logging

from ..models.cv_models import (
    CVModel, 
    CVMetadata, 
    PersonalInfo, 
    ContactInfo,
    Experience, 
    Education, 
    Skills, 
    SkillCategory,
    Certification
)
from ..models.llm_models import AIParsingRequest, AIParsingResult
from ..llm.ai_parser import AIParser
from ..llm.providers.base import BaseLLMProvider
from .plaintext_cv import (
    is_plain_text_cv,
    normalize_plain_text_cv,
    canonical_section_name,
    parse_date_range,
    looks_like_date_range,
    split_on_dash,
    split_trailing_parenthetical,
    strip_markdown,
)

logger = logging.getLogger(__name__)

# Markdown horizontal rules used as visual separators between CV sections
HORIZONTAL_RULE_PATTERN = r'^\s*(?:-{3,}|\*{3,}|_{3,})\s*$'


class ImportServiceError(Exception):
    """Base exception for import service operations."""
    pass


class MarkdownParseError(ImportServiceError):
    """Raised when markdown parsing fails."""
    pass


class YAMLParseError(ImportServiceError):
    """Raised when YAML frontmatter parsing fails."""
    pass


class ContentParseError(ImportServiceError):
    """Raised when content section parsing fails."""
    pass


class ImportService:
    """
    Service for importing CV documents from Markdown files.
    
    Handles parsing of YAML frontmatter and Markdown content sections,
    converting them to structured CV data models with validation.
    Includes AI-powered fallback parsing for non-standard formats.
    """
    
    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        """
        Initialize ImportService.
        
        Args:
            llm_provider: Optional LLM provider for AI-powered parsing fallback
        """
        self.llm_provider = llm_provider
        self.ai_parser = AIParser(llm_provider) if llm_provider else None
    
    def import_from_markdown(self, markdown_content: str, cv_title: Optional[str] = None) -> CVModel:
        """
        Import CV data from markdown content.
        
        Args:
            markdown_content: Raw markdown content with YAML frontmatter
            cv_title: Optional title override for the CV
            
        Returns:
            CVModel: Parsed and validated CV data
            
        Raises:
            MarkdownParseError: If markdown structure is invalid
            YAMLParseError: If YAML frontmatter is invalid
            ContentParseError: If content sections cannot be parsed
        """
        try:
            logger.info("Starting markdown import process")
            
            # Plain-text CVs (no frontmatter, no headings) are normalised into
            # the canonical markdown layout before parsing
            if is_plain_text_cv(markdown_content):
                logger.info("Content has no markdown headings, normalising as plain-text CV")
                markdown_content = normalize_plain_text_cv(markdown_content)
            
            # Split frontmatter and content
            frontmatter, content = self._split_frontmatter(markdown_content)
            
            # Parse YAML frontmatter
            yaml_data = self._parse_yaml_frontmatter(frontmatter)
            
            # Parse markdown content sections
            content_data = self._parse_content_sections(content)
            
            # An empty parse means the document layout was not recognised at
            # all - fail rather than silently creating a blank CV
            if not self._has_parsed_content(content_data):
                raise ContentParseError(
                    "No CV content could be parsed. Expected markdown headings "
                    "(# Name, ## Summary, ## Experience, ...) or a plain-text CV "
                    "with recognisable section headings."
                )
            
            # Convert to CV model
            cv_model = self._convert_to_cv_model(yaml_data, content_data, cv_title)
            
            logger.info(f"Successfully imported CV: {cv_model.metadata.title}")
            return cv_model
            
        except (MarkdownParseError, YAMLParseError, ContentParseError) as e:
            # If traditional parsing fails and AI parser is available, try AI fallback
            if self.ai_parser:
                logger.info("Traditional parsing failed, attempting AI-powered fallback")
                try:
                    return self._import_with_ai_fallback(markdown_content, cv_title, str(e))
                except Exception as ai_error:
                    logger.error(f"AI fallback also failed: {ai_error}")
                    # Re-raise original error
                    raise e
            else:
                raise
        except Exception as e:
            raise ImportServiceError(f"Unexpected error during import: {e}")
    
    @staticmethod
    def _has_parsed_content(content_data: Dict[str, Any]) -> bool:
        """Return True when parsing produced at least one usable CV element."""
        personal_info = content_data.get('personal_info') or {}
        if personal_info.get('name'):
            return True
        for key in ('summary', 'experience', 'education', 'certifications'):
            if content_data.get(key):
                return True
        skills = content_data.get('skills') or {}
        return bool(skills.get('categories'))

    def _split_frontmatter(self, markdown_content: str) -> Tuple[str, str]:
        """
        Split markdown content into YAML frontmatter and content sections.
        
        Args:
            markdown_content: Raw markdown content
            
        Returns:
            Tuple of (frontmatter, content)
            
        Raises:
            MarkdownParseError: If frontmatter structure is invalid
        """
        try:
            # Remove any leading whitespace
            content = markdown_content.strip()
            
            # YAML frontmatter is optional - plain Markdown CVs start with '# Name'
            if not content.startswith('---'):
                return '', content
            
            # Find the end of frontmatter
            lines = content.split('\n')
            frontmatter_end = -1
            
            for i, line in enumerate(lines[1:], 1):  # Skip first '---'
                if line.strip() == '---':
                    frontmatter_end = i
                    break
            
            if frontmatter_end == -1:
                raise MarkdownParseError("No closing '---' found for YAML frontmatter")
            
            # Extract frontmatter and content
            frontmatter_lines = lines[1:frontmatter_end]  # Skip opening '---'
            content_lines = lines[frontmatter_end + 1:]   # Skip closing '---'
            
            frontmatter = '\n'.join(frontmatter_lines)
            content = '\n'.join(content_lines)
            
            return frontmatter, content
            
        except MarkdownParseError:
            raise
        except Exception as e:
            raise MarkdownParseError(f"Failed to split frontmatter: {e}")
    
    def _parse_yaml_frontmatter(self, frontmatter: str) -> Dict[str, Any]:
        """
        Parse YAML frontmatter into dictionary.
        
        Args:
            frontmatter: YAML frontmatter content
            
        Returns:
            Dictionary with parsed YAML data
            
        Raises:
            YAMLParseError: If YAML parsing fails
        """
        try:
            if not frontmatter.strip():
                return {}
            
            yaml_data = yaml.safe_load(frontmatter)
            
            if yaml_data is None:
                return {}
            
            if not isinstance(yaml_data, dict):
                raise YAMLParseError("YAML frontmatter must be a dictionary")
            
            return yaml_data
            
        except yaml.YAMLError as e:
            raise YAMLParseError(f"Invalid YAML syntax: {e}")
        except Exception as e:
            raise YAMLParseError(f"Failed to parse YAML frontmatter: {e}")
    
    def _parse_content_sections(self, content: str) -> Dict[str, Any]:
        """
        Parse markdown content sections into structured data.
        
        Args:
            content: Markdown content without frontmatter
            
        Returns:
            Dictionary with parsed content sections
            
        Raises:
            ContentParseError: If content parsing fails
        """
        try:
            sections = {}
            
            # Split content by headers (# or ## Header)
            header_pattern = r'^(#{1,2})\s+(.+)$'
            lines = content.split('\n')
            
            current_section = None
            current_content = []
            current_level = 0
            
            for line in lines:
                header_match = re.match(header_pattern, line)
                if header_match:
                    level = len(header_match.group(1))  # Number of # characters
                    header_text = header_match.group(2).strip()
                    
                    # Save previous section
                    if current_section:
                        sections[current_section] = '\n'.join(current_content).strip()
                    
                    # Start new section
                    current_section = header_text
                    current_content = []
                    current_level = level
                elif not re.match(HORIZONTAL_RULE_PATTERN, line):
                    # Skip horizontal rules ('---', '***', '___') used as separators
                    current_content.append(line)
            
            # Save last section
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            
            # Parse specific sections
            parsed_sections = {}
            
            # Map each heading to a canonical section name so variations like
            # "Leadership Experience" or "Core Competencies" are recognised
            canonical_sections = {}
            personal_info_key = None
            
            for key, body in sections.items():
                canonical = canonical_section_name(key)
                if canonical:
                    # First heading of each kind wins
                    canonical_sections.setdefault(canonical, body)
                elif personal_info_key is None:
                    # The first unrecognised heading is the name header
                    personal_info_key = key
            
            if personal_info_key:
                parsed_sections['personal_info'] = self._parse_personal_info(
                    personal_info_key, sections[personal_info_key]
                )
            
            if 'Summary' in canonical_sections:
                parsed_sections['summary'] = canonical_sections['Summary'].strip()
            
            if 'Experience' in canonical_sections:
                parsed_sections['experience'] = self._parse_experience_section(
                    canonical_sections['Experience']
                )
            
            if 'Skills' in canonical_sections:
                parsed_sections['skills'] = self._parse_skills_section(
                    canonical_sections['Skills']
                )
            
            if 'Education' in canonical_sections:
                parsed_sections['education'] = self._parse_education_section(
                    canonical_sections['Education']
                )
            
            if 'Professional Memberships and Certificates' in canonical_sections:
                parsed_sections['certifications'] = self._parse_certifications_section(
                    canonical_sections['Professional Memberships and Certificates']
                )
            
            return parsed_sections
            
        except Exception as e:
            raise ContentParseError(f"Failed to parse content sections: {e}")
    
    def _parse_personal_info(self, name_line: str, contact_content: str) -> Dict[str, Any]:
        """
        Parse personal information from header and contact details.
        
        Args:
            name_line: First header line containing name and title
            contact_content: Content with contact information
            
        Returns:
            Dictionary with personal info data
        """
        try:
            personal_info = {}
            
            # Extract name (first line is the name)
            personal_info['name'] = name_line.strip()
            
            # Look for title in the next line
            lines = contact_content.split('\n')
            title_line = None
            contact_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if line contains contact info patterns
                if any(pattern in line.lower() for pattern in ['@', 'linkedin', 'phone', '+', 'http']):
                    contact_lines.append(line)
                elif line.startswith('-'):
                    contact_lines.append(line)
                elif not title_line and not any(char in line for char in ['@', '+', 'http']) and len(line) < 50:
                    # Likely a title line (short and no contact patterns)
                    # Strip any markdown formatting (*, _, etc.)
                    title_line = line.strip('*_')
                else:
                    contact_lines.append(line)
            
            if title_line:
                # Strip any markdown formatting and trailing whitespace
                personal_info['title'] = title_line.strip('*_ \t')
            
            # Parse contact information
            contact_info = {}
            
            for line in contact_lines:
                line = line.strip().lstrip('- ')
                
                # Extract email from markdown link format or plain text
                if '@' in line and 'linkedin' not in line.lower():
                    # Check if it's in markdown link format: [email](mailto:email)
                    email_match = re.search(r'\[([^\]]+@[^\]]+)\]', line)
                    if email_match:
                        contact_info['email'] = email_match.group(1)
                    else:
                        contact_info['email'] = line
                elif 'linkedin' in line.lower():
                    # Extract LinkedIn URL, preferring the target of a markdown link
                    link_match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', line)
                    if link_match:
                        contact_info['linkedin'] = link_match.group(2).strip()
                    elif ':' in line and not line.lower().startswith('http'):
                        contact_info['linkedin'] = line.split(':', 1)[1].strip()
                    else:
                        contact_info['linkedin'] = line
                elif 'http' in line.lower() and 'linkedin' not in line.lower():
                    contact_info['website'] = line
                elif ('+' in line and any(char.isdigit() for char in line)) or (line.replace('-', '').replace(' ', '').replace('(', '').replace(')', '').isdigit() and len(line) > 8):
                    # Phone number patterns: has + sign or is mostly digits
                    contact_info['phone'] = line
                elif ('st' in line.lower() or 'street' in line.lower() or 'ave' in line.lower() or 
                      'avenue' in line.lower() or 'rd' in line.lower() or 'road' in line.lower() or
                      (',' in line and any(char.isdigit() for char in line[:10]))):  # Address patterns
                    if 'address' not in contact_info:
                        contact_info['address'] = line
                elif not any(key in line.lower() for key in ['email', 'phone', 'linkedin', 'http']) and len(line) > 10:
                    # Likely an address (longer line without contact patterns)
                    if 'address' not in contact_info:  # Only take the first address-like line
                        contact_info['address'] = line
            
            personal_info['contact'] = contact_info
            
            return personal_info
            
        except Exception as e:
            logger.warning(f"Failed to parse personal info: {e}")
            return {'name': name_line.strip(), 'contact': {}}
    
    def _parse_experience_section(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse work experience section.
        
        Args:
            content: Work experience section content
            
        Returns:
            List of experience entries
        """
        try:
            experiences = []
            
            # Split by job entries (### headers)
            job_pattern = r'^### (.+)$'
            lines = content.split('\n')
            
            current_job = None
            current_content = []
            
            for line in lines:
                job_match = re.match(job_pattern, line)
                if job_match:
                    # Process previous job
                    if current_job:
                        exp_data = self._parse_single_experience(current_job, '\n'.join(current_content))
                        if exp_data:
                            experiences.append(exp_data)
                    
                    # Start new job
                    current_job = job_match.group(1).strip()
                    current_content = []
                else:
                    current_content.append(line)
            
            # Process last job
            if current_job:
                exp_data = self._parse_single_experience(current_job, '\n'.join(current_content))
                if exp_data:
                    experiences.append(exp_data)
            
            return experiences
            
        except Exception as e:
            logger.warning(f"Failed to parse experience section: {e}")
            return []
    
    def _parse_single_experience(self, header: str, content: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single work experience entry.

        Supports two common header/body layouts:
            ### Job Title                    ### Job Title - Company
            **Company** | Location           *Location | March 2023 - Present*
            *March 2023 - Present*

        Args:
            header: Job heading (from ### header), optionally "Title - Company"
            content: Job content with company, dates, and description

        Returns:
            Dictionary with experience data or None if parsing fails
        """
        try:
            title = strip_markdown(header)
            company = None
            location = None

            # Header may carry the company: "Head of Data Engineering - Direct Line Group"
            header_parts = split_on_dash(title)
            if header_parts:
                title, company = header_parts

            # Hand-written CVs often append the location: "TechCorp (London, UK)"
            if company:
                company, bracketed = split_trailing_parenthetical(company)
                if bracketed:
                    location = bracketed

            lines = [line.strip() for line in content.split('\n') if line.strip()]

            start_date = None
            end_date = None
            current = False
            description_lines = []

            for index, raw_line in enumerate(lines):
                line = strip_markdown(raw_line)

                # A line combining location and dates: "Location | March 2023 - Present"
                if start_date is None and '|' in line:
                    left, _, right = line.partition('|')
                    date_parts = parse_date_range(right)
                    if date_parts:
                        start_date, end_date, current = date_parts
                        if not location and left.strip():
                            location = left.strip()
                        continue
                    # Otherwise it is the "**Company** | Location" line
                    if company is None:
                        company = left.strip()
                        location = right.strip() or None
                        continue

                # A standalone date range line
                if start_date is None:
                    date_parts = parse_date_range(line)
                    if date_parts:
                        start_date, end_date, current = date_parts
                        continue

                # First plain line before any dates is the company
                if company is None and index == 0 and not re.match(r'^[-•]\s', raw_line):
                    company = line
                    continue

                description_lines.append(raw_line)

            # Split the remaining lines: bullets become achievements, and
            # everything else is the description.
            #
            # These used to overlap — every bullet was joined into the
            # description *and* extracted into achievements — so exports
            # printed the same text twice, once as a paragraph and again as a
            # bullet list.
            achievements = []
            prose_lines = []
            bullet_pattern = r'^\s*[-•]\s*(.+)$'

            for line in description_lines:
                bullet_match = re.match(bullet_pattern, line)
                if bullet_match:
                    achievements.append(bullet_match.group(1).strip())
                else:
                    prose_lines.append(line)

            description = '\n'.join(prose_lines).strip()

            if not title:
                return None

            return {
                'title': title,
                'company': company,
                'location': location,
                'start_date': start_date,
                'end_date': end_date,
                'current': current,
                'description': description,
                'achievements': achievements
            }

        except Exception as e:
            logger.warning(f"Failed to parse experience entry: {e}")
            return None

    def _parse_skills_section(self, content: str) -> Dict[str, Any]:
        """
        Parse skills section.

        Supports both layouts:
            Category: skill1; skill2          **Category**
                                              skill1 | skill2 | skill3

        Args:
            content: Skills section content

        Returns:
            Dictionary with skills data
        """
        try:
            categories = []
            pending_category = None

            lines = [line.strip() for line in content.split('\n') if line.strip()]

            for raw_line in lines:
                line = re.sub(r'^[-•]\s*', '', raw_line).strip()
                if not line:
                    continue

                # "Category: skill1; skill2" on one line
                if ':' in line and not line.lower().startswith('http'):
                    name, _, skills_part = line.partition(':')
                    skills = self._split_skill_list(skills_part)
                    if skills:
                        categories.append({'name': strip_markdown(name), 'skills': skills})
                        pending_category = None
                        continue

                # A bold heading line introduces the category for the next line
                if raw_line.startswith('**') and '|' not in line:
                    pending_category = strip_markdown(line)
                    continue

                skills = self._split_skill_list(line)
                if not skills:
                    continue

                if pending_category:
                    categories.append({'name': pending_category, 'skills': skills})
                    pending_category = None
                elif len(skills) > 1:
                    # A bare list with no category heading
                    categories.append({'name': 'Skills', 'skills': skills})
                else:
                    # Single value with nothing to attach it to - treat as heading
                    pending_category = strip_markdown(line)

            return {'categories': categories}

        except Exception as e:
            logger.warning(f"Failed to parse skills section: {e}")
            return {'categories': []}

    @staticmethod
    def _split_skill_list(text: str) -> List[str]:
        """Split a skills line on pipes, semicolons or commas."""
        return [
            strip_markdown(skill)
            for skill in re.split(r'[|;,]', text)
            if strip_markdown(skill)
        ]

    def _parse_education_section(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse education section.
        
        Args:
            content: Education section content
            
        Returns:
            List of education entries
        """
        try:
            education_entries = []
            
            # Split by education entries (### headers or bullet points)
            edu_pattern = r'^### (.+)$'
            lines = content.split('\n')
            
            # Check if using ### header format or bullet point format
            has_headers = any(re.match(edu_pattern, line) for line in lines)
            
            if has_headers:
                # Use header-based parsing
                current_degree = None
                current_content = []
                
                for line in lines:
                    edu_match = re.match(edu_pattern, line)
                    if edu_match:
                        # Process previous education entry
                        if current_degree:
                            edu_data = self._parse_single_education(current_degree, '\n'.join(current_content))
                            if edu_data:
                                education_entries.append(edu_data)
                        
                        # Start new education entry
                        current_degree = edu_match.group(1).strip()
                        current_content = []
                    else:
                        current_content.append(line)
                
                # Process last education entry
                if current_degree:
                    edu_data = self._parse_single_education(current_degree, '\n'.join(current_content))
                    if edu_data:
                        education_entries.append(edu_data)
            elif not any(re.match(r'^-\s+\S', line.strip()) for line in lines):
                # No headers and no bullets: blocks of
                # **Degree** / Institution, Location / *dates* / description
                education_entries = self._parse_block_education(lines)
            else:
                # Use bullet point format parsing
                # Format: - Date Range — Institution (Location)
                # - Degree — Grade
                # - Description
                bullet_pattern = r'^-\s+(.+)$'
                current_entry_lines = []
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    bullet_match = re.match(bullet_pattern, line)
                    if bullet_match:
                        # Process previous entry if exists
                        if current_entry_lines:
                            edu_data = self._parse_bullet_education(current_entry_lines)
                            if edu_data:
                                education_entries.append(edu_data)
                            current_entry_lines = []
                        
                        # Start new entry
                        current_entry_lines.append(bullet_match.group(1).strip())
                    elif current_entry_lines:
                        # Continuation of current entry
                        current_entry_lines.append(line.lstrip('- '))
                
                # Process last entry
                if current_entry_lines:
                    edu_data = self._parse_bullet_education(current_entry_lines)
                    if edu_data:
                        education_entries.append(edu_data)
            
            return education_entries
            
        except Exception as e:
            logger.warning(f"Failed to parse education section: {e}")
            return []
    
    def _parse_block_education(self, lines: List[str]) -> List[Dict[str, Any]]:
        """
        Parse education written as plain blocks:
            **BSc Computing - 1st Class Honours**
            Canterbury Christ Church University, Canterbury, United Kingdom
            *September 2011 - June 2014*
            Leadership Experience: ...
        """
        entries = []
        current = None

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            stripped = strip_markdown(line)
            date_parts = parse_date_range(stripped)

            # A bold line starts a new entry, unless it is a date range
            if raw_line.strip().startswith('**') and not date_parts:
                if current:
                    entries.append(current)
                current = {
                    'degree': stripped,
                    'institution': None,
                    'location': None,
                    'start_date': None,
                    'end_date': None,
                    'gpa': None,
                    'description': ''
                }
                continue

            if current is None:
                # Content before any degree heading - start an entry from it
                current = {
                    'degree': stripped,
                    'institution': None,
                    'location': None,
                    'start_date': None,
                    'end_date': None,
                    'gpa': None,
                    'description': ''
                }
                continue

            if date_parts and current['start_date'] is None:
                current['start_date'], current['end_date'], _ = date_parts
            elif current['institution'] is None:
                institution, location = self._split_institution_line(stripped)
                current['institution'] = institution
                current['location'] = location
            else:
                current['description'] = (
                    f"{current['description']}\n{stripped}".strip()
                )

        if current:
            entries.append(current)

        return [entry for entry in entries if entry['degree']]

    @staticmethod
    def _split_institution_line(line: str) -> Tuple[str, Optional[str]]:
        """Split 'University, City, Country' into institution and location."""
        parts = [part.strip() for part in line.split(',') if part.strip()]
        if len(parts) >= 2:
            return parts[0], ', '.join(parts[1:])
        return line.strip(), None

    def _parse_single_education(self, degree: str, content: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single education entry.
        
        Args:
            degree: Degree name (from ### header)
            content: Education content with institution, dates, and description
            
        Returns:
            Dictionary with education data or None if parsing fails
        """
        try:
            # Parse content lines
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            
            if not lines:
                return None
            
            # First line should be institution (possibly with location): **Institution** | Location
            institution_line = lines[0]
            institution = None
            location = None
            
            # Remove all markdown bold formatting (** at start and end)
            institution_line = institution_line.replace('**', '').strip()
            
            # Split by pipe for location
            if '|' in institution_line:
                parts = institution_line.split('|', 1)
                institution = parts[0].strip()
                location = parts[1].strip() if len(parts) > 1 else None
            else:
                institution = institution_line.strip()
            
            # Parse dates and GPA from subsequent lines
            start_date = None
            end_date = None
            gpa = None
            description_lines = []
            
            line_idx = 1
            while line_idx < len(lines):
                line = lines[line_idx].strip('*')  # Remove italic formatting
                
                # Check if it's a date line (contains " - " or looks like a date)
                if ' - ' in line and not line.startswith('GPA:'):
                    parts = line.split(' - ', 1)
                    start_date = parts[0].strip()
                    end_date = parts[1].strip() if len(parts) > 1 else None
                    line_idx += 1
                # Check if it's a GPA line
                elif line.startswith('GPA:'):
                    gpa = line.replace('GPA:', '').strip()
                    line_idx += 1
                else:
                    # Rest are description lines
                    description_lines = lines[line_idx:]
                    break
            
            description = '\n'.join(description_lines).strip() if description_lines else None
            
            return {
                'degree': degree,
                'institution': institution,
                'location': location,
                'start_date': start_date,
                'end_date': end_date,
                'gpa': gpa,
                'description': description
            }
            
        except Exception as e:
            logger.warning(f"Failed to parse education entry: {e}")
            return None
    
    def _parse_bullet_education(self, lines: List[str]) -> Optional[Dict[str, Any]]:
        """
        Parse a single education entry from bullet point format.
        
        Format:
        - Date Range — Institution (Location)
        - Degree — Grade
        - Description
        
        Args:
            lines: List of lines for this education entry
            
        Returns:
            Dictionary with education data or None if parsing fails
        """
        try:
            if not lines:
                return None
            
            # First line: Date Range — Institution (Location)
            first_line = lines[0]
            
            # Split by em dash or double hyphen
            if '—' in first_line:
                date_part, institution_part = first_line.split('—', 1)
            elif ' — ' in first_line:
                date_part, institution_part = first_line.split(' — ', 1)
            else:
                # Fallback: treat whole line as institution
                date_part = ""
                institution_part = first_line
            
            # Parse dates
            date_part = date_part.strip()
            start_date = None
            end_date = None
            
            if date_part and '—' in date_part:
                date_parts = date_part.split('—', 1)
                start_date = date_parts[0].strip()
                end_date = date_parts[1].strip()
            elif date_part:
                start_date = date_part
            
            # Parse institution and location
            institution_part = institution_part.strip()
            institution = None
            location = None
            
            if '(' in institution_part and ')' in institution_part:
                # Extract location from parentheses
                match = re.match(r'(.+?)\s*\((.+?)\)', institution_part)
                if match:
                    institution = match.group(1).strip()
                    location = match.group(2).strip()
                else:
                    institution = institution_part
            else:
                institution = institution_part
            
            # Second line (if exists): Degree — Grade
            degree = None
            gpa = None
            description_lines = []
            
            if len(lines) > 1:
                second_line = lines[1]
                
                if '—' in second_line:
                    degree_parts = second_line.split('—', 1)
                    degree = degree_parts[0].strip()
                    gpa = degree_parts[1].strip()
                else:
                    degree = second_line.strip()
                
                # Rest are description
                if len(lines) > 2:
                    description_lines = lines[2:]
            
            description = '\n'.join(description_lines).strip() if description_lines else None
            
            return {
                'degree': degree or institution,  # Fallback to institution if no degree
                'institution': institution,
                'location': location,
                'start_date': start_date,
                'end_date': end_date,
                'gpa': gpa,
                'description': description
            }
            
        except Exception as e:
            logger.warning(f"Failed to parse bullet education entry: {e}")
            return None
    
    def _parse_certifications_section(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse certifications/professional memberships section.

        Supports markdown tables (| Date | Certification |), "Date - Name"
        lines, and "**Name** - Issuer (Date - Expiry)" lines.

        Args:
            content: Certifications section content

        Returns:
            List of certification entries
        """
        try:
            certifications = []
            lines = [line.strip() for line in content.split('\n') if line.strip()]

            for raw_line in lines:
                line = re.sub(r'^[-•]\s*', '', raw_line).strip()

                # Markdown table row: | February 2025 | AWS Certified AI Practitioner |
                if line.startswith('|'):
                    cells = [cell.strip() for cell in line.strip('|').split('|')]
                    cells = [cell for cell in cells if cell]

                    # Skip separator rows (| --- | --- |) and header rows
                    if not cells or all(re.fullmatch(r':?-{2,}:?', cell) for cell in cells):
                        continue
                    if len(cells) >= 2 and cells[0].lower() in ('date', 'dates', 'year', 'awarded'):
                        continue

                    entry = self._certification_from_cells(cells)
                    if entry:
                        certifications.append(entry)
                    continue

                # "Date - Certification Name" (any dash style)
                dash_parts = split_on_dash(line)
                if dash_parts and looks_like_date_range(dash_parts[0]) is False and self._is_date_like(dash_parts[0]):
                    # The issuer is often bracketed after the name:
                    # "Certified Kubernetes Administrator (CNCF)"
                    name, issuer = split_trailing_parenthetical(strip_markdown(dash_parts[1]))
                    certifications.append({
                        'name': name,
                        'issuer': issuer or 'N/A',
                        'date': dash_parts[0].strip(),
                        'expiry_date': None
                    })
                    continue

                # "**Cert Name** - Issuer (Date - Expiry)"
                cert_match = re.match(r'\*\*(.+?)\*\*\s*[-–—]\s*(.+?)(?:\s*\((.+?)\))?$', line)
                if cert_match:
                    date_part = cert_match.group(3).strip() if cert_match.group(3) else None
                    date = None
                    expiry_date = None

                    if date_part:
                        date_range = re.split(r'\s+[-–—]\s+', date_part, maxsplit=1)
                        date = date_range[0].strip()
                        expiry_date = date_range[1].strip() if len(date_range) > 1 else None

                    certifications.append({
                        'name': cert_match.group(1).strip(),
                        'issuer': cert_match.group(2).strip(),
                        'date': date,
                        'expiry_date': expiry_date
                    })
                    continue

                # Bare certification name
                name = strip_markdown(line)
                if name and not self._is_date_like(name):
                    certifications.append({
                        'name': name,
                        'issuer': 'N/A',
                        'date': None,
                        'expiry_date': None
                    })

            logger.info(f"Parsed {len(certifications)} certifications")
            return certifications

        except Exception as e:
            logger.warning(f"Failed to parse certifications section: {e}")
            return []

    def _certification_from_cells(self, cells: List[str]) -> Optional[Dict[str, Any]]:
        """Build a certification entry from markdown table cells."""
        date = None
        issuer = 'N/A'
        name = None

        for cell in cells:
            value = strip_markdown(cell)
            if not value:
                continue
            if date is None and self._is_date_like(value):
                date = value
            elif name is None:
                name = value
            elif issuer == 'N/A':
                issuer = value

        if not name:
            return None

        return {'name': name, 'issuer': issuer, 'date': date, 'expiry_date': None}

    @staticmethod
    def _is_date_like(text: str) -> bool:
        """True when the text looks like a date or date range."""
        value = strip_markdown(text)
        if looks_like_date_range(value):
            return True
        return bool(re.fullmatch(
            r'(?:[A-Za-z]{3,9}\s+)?\d{4}|\d{1,2}/\d{4}|\d{1,2}-\d{4}',
            value
        ))

    def _convert_to_cv_model(self, yaml_data: Dict[str, Any], content_data: Dict[str, Any], cv_title: Optional[str] = None) -> CVModel:
        """
        Convert parsed data to CV model.
        
        Args:
            yaml_data: Parsed YAML frontmatter
            content_data: Parsed content sections
            cv_title: Optional title override
            
        Returns:
            CVModel instance
        """
        try:
            # Create metadata
            title = cv_title or yaml_data.get('title', 'Imported CV')
            metadata = CVMetadata(
                title=title,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                template_id='default'
            )
            
            # Create personal info
            personal_data = content_data.get('personal_info', {})
            contact_data = personal_data.get('contact', {})

            # Exports write contact details into the YAML frontmatter, so fall
            # back to it when the body carries no contact line. Without this a
            # CV exported to Markdown and re-imported loses its contact details.
            def _contact_field(name: str) -> Optional[str]:
                return contact_data.get(name) or yaml_data.get(name)

            contact_info = ContactInfo(
                address=_contact_field('address'),
                phone=_contact_field('phone'),
                email=_contact_field('email'),
                linkedin=_contact_field('linkedin'),
                website=_contact_field('website')
            )
            
            personal_info = PersonalInfo(
                name=personal_data.get('name', 'Unknown'),
                title=personal_data.get('title'),
                contact=contact_info
            )
            
            # Create experience entries
            experience_list = []
            for exp_data in content_data.get('experience', []):
                experience = Experience(
                    title=exp_data['title'],
                    company=exp_data['company'],
                    location=exp_data.get('location'),
                    start_date=exp_data.get('start_date', ''),
                    end_date=exp_data.get('end_date'),
                    current=exp_data.get('current', False),
                    description=exp_data.get('description'),
                    achievements=exp_data.get('achievements', [])
                )
                experience_list.append(experience)
            
            # Create education entries
            education_list = []
            for edu_data in content_data.get('education', []):
                education = Education(
                    degree=edu_data.get('degree', ''),
                    institution=edu_data.get('institution', ''),
                    location=edu_data.get('location'),
                    start_date=edu_data.get('start_date'),
                    end_date=edu_data.get('end_date'),
                    description=edu_data.get('description')
                )
                education_list.append(education)
            
            # Create skills
            skills_data = content_data.get('skills', {'categories': []})
            skill_categories = []
            for cat_data in skills_data.get('categories', []):
                category = SkillCategory(
                    name=cat_data['name'],
                    skills=cat_data['skills']
                )
                skill_categories.append(category)
            
            skills = Skills(categories=skill_categories)
            
            # Create certifications
            certification_list = []
            for cert_data in content_data.get('certifications', []):
                certification = Certification(
                    name=cert_data['name'],
                    issuer=cert_data['issuer'],
                    date=cert_data.get('date'),
                    expiry_date=cert_data.get('expiry_date')
                )
                certification_list.append(certification)
            
            # Create CV model
            cv_model = CVModel(
                metadata=metadata,
                personal_info=personal_info,
                summary=content_data.get('summary'),
                experience=experience_list,
                education=education_list,
                skills=skills,
                certifications=certification_list
            )
            
            return cv_model
            
        except Exception as e:
            raise ImportServiceError(f"Failed to convert to CV model: {e}")

    
    def _import_with_ai_fallback(
        self,
        content: str,
        cv_title: Optional[str],
        original_error: str
    ) -> CVModel:
        """
        Import CV using AI-powered parsing as fallback.
        
        Args:
            content: Raw content that failed traditional parsing
            cv_title: Optional title override
            original_error: Error message from traditional parsing
            
        Returns:
            CVModel: Parsed CV data from AI parsing
            
        Raises:
            ImportServiceError: If AI parsing also fails
        """
        try:
            logger.info(f"Attempting AI fallback after error: {original_error}")
            
            # Create AI parsing request
            request = AIParsingRequest(
                file_content=content,
                file_format='markdown',
                filename=cv_title
            )
            
            # Parse with AI (this is async, but we'll handle it synchronously for now)
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, we need to handle this differently
                # For now, raise an error indicating AI parsing requires async context
                raise ImportServiceError(
                    "AI parsing requires async context. Use import_from_file_async instead."
                )
            
            parsing_result: AIParsingResult = loop.run_until_complete(
                self.ai_parser.parse_cv(request)
            )
            
            # Check if parsing was successful
            if parsing_result.overall_confidence < 0.5:
                raise ImportServiceError(
                    f"AI parsing confidence too low ({parsing_result.overall_confidence:.2f}). "
                    f"Errors: {', '.join(parsing_result.errors)}"
                )
            
            if not parsing_result.cv_data:
                raise ImportServiceError(
                    "AI parsing did not produce CV data. "
                    f"Errors: {', '.join(parsing_result.errors)}"
                )
            
            # Convert AI-parsed data to CV model
            cv_model = self._convert_ai_parsed_data_to_cv_model(
                parsing_result.cv_data,
                cv_title
            )
            
            logger.info(
                f"Successfully imported CV using AI fallback "
                f"(confidence: {parsing_result.overall_confidence:.2f})"
            )
            
            return cv_model
            
        except Exception as e:
            raise ImportServiceError(f"AI fallback parsing failed: {e}")
    
    async def import_from_file_async(
        self,
        file_content: str,
        file_format: str,
        cv_title: Optional[str] = None,
        use_ai_parsing: bool = False
    ) -> Tuple[CVModel, Optional[AIParsingResult]]:
        """
        Import CV from various file formats with optional AI parsing.
        
        Args:
            file_content: Raw file content
            file_format: File format (markdown, pdf, docx, txt, html)
            cv_title: Optional title override
            use_ai_parsing: Whether to use AI parsing (required for non-markdown formats)
            
        Returns:
            Tuple of (CVModel, optional AIParsingResult with ambiguities)
            
        Raises:
            ImportServiceError: If import fails
            UnsupportedFormatError: If format requires AI parsing but it's not available
        """
        try:
            # For markdown, try traditional parsing first unless AI is explicitly requested
            if file_format.lower() in ['markdown', 'md'] and not use_ai_parsing:
                try:
                    cv_model = self.import_from_markdown(file_content, cv_title)
                    return cv_model, None
                except Exception as e:
                    logger.info(f"Traditional markdown parsing failed: {e}")
                    if not self.ai_parser:
                        raise
                    # Fall through to AI parsing
            
            # For other formats or if AI parsing is requested, use AI parser
            if not self.ai_parser:
                raise ImportServiceError(
                    f"AI parsing not available. Format '{file_format}' requires AI parsing. "
                    "Please configure an LLM provider."
                )
            
            logger.info(f"Using AI parsing for {file_format} format")
            
            # Create AI parsing request
            request = AIParsingRequest(
                file_content=file_content,
                file_format=file_format,
                filename=cv_title
            )
            
            # Parse with AI
            parsing_result: AIParsingResult = await self.ai_parser.parse_cv(request)
            
            # Check parsing quality
            if parsing_result.overall_confidence < 0.4:
                raise ImportServiceError(
                    f"AI parsing confidence too low ({parsing_result.overall_confidence:.2f}). "
                    f"Errors: {', '.join(parsing_result.errors)}"
                )
            
            if not parsing_result.cv_data:
                raise ImportServiceError(
                    "AI parsing did not produce CV data. "
                    f"Errors: {', '.join(parsing_result.errors)}"
                )
            
            # Convert to CV model
            cv_model = self._convert_ai_parsed_data_to_cv_model(
                parsing_result.cv_data,
                cv_title
            )
            
            logger.info(
                f"Successfully imported {file_format} file using AI parsing "
                f"(confidence: {parsing_result.overall_confidence:.2f}, "
                f"ambiguities: {len(parsing_result.ambiguities)})"
            )
            
            return cv_model, parsing_result
            
        except Exception as e:
            raise ImportServiceError(f"Failed to import {file_format} file: {e}")
    
    def _convert_ai_parsed_data_to_cv_model(
        self,
        ai_data: Dict[str, Any],
        cv_title: Optional[str] = None
    ) -> CVModel:
        """
        Convert AI-parsed data to CV model.
        
        Args:
            ai_data: Data from AI parsing
            cv_title: Optional title override
            
        Returns:
            CVModel instance
        """
        try:
            # Extract metadata
            metadata_data = ai_data.get('metadata', {})
            title = cv_title or metadata_data.get('title', 'AI Parsed CV')
            
            metadata = CVMetadata(
                title=title,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                template_id='default'
            )
            
            # Extract personal info
            personal_data = ai_data.get('personal_info', {})
            contact_data = personal_data.get('contact', {})
            
            contact_info = ContactInfo(
                address=contact_data.get('address'),
                phone=contact_data.get('phone'),
                email=contact_data.get('email'),
                linkedin=contact_data.get('linkedin'),
                website=contact_data.get('website')
            )
            
            personal_info = PersonalInfo(
                name=personal_data.get('name', 'Unknown'),
                title=personal_data.get('title'),
                contact=contact_info
            )
            
            # Extract experience
            experience_list = []
            for exp_data in ai_data.get('experience', []):
                experience = Experience(
                    title=exp_data.get('title', ''),
                    company=exp_data.get('company', ''),
                    location=exp_data.get('location'),
                    start_date=exp_data.get('start_date', ''),
                    end_date=exp_data.get('end_date'),
                    current=exp_data.get('current', False),
                    description=exp_data.get('description'),
                    achievements=exp_data.get('achievements', [])
                )
                experience_list.append(experience)
            
            # Extract education
            education_list = []
            for edu_data in ai_data.get('education', []):
                education = Education(
                    degree=edu_data.get('degree', ''),
                    institution=edu_data.get('institution', ''),
                    location=edu_data.get('location'),
                    start_date=edu_data.get('start_date'),
                    end_date=edu_data.get('end_date'),
                    description=edu_data.get('description')
                )
                education_list.append(education)
            
            # Extract skills
            skills_data = ai_data.get('skills', {'categories': []})
            skill_categories = []
            for cat_data in skills_data.get('categories', []):
                category = SkillCategory(
                    name=cat_data.get('name', 'Skills'),
                    skills=cat_data.get('skills', [])
                )
                skill_categories.append(category)
            
            skills = Skills(categories=skill_categories)
            
            # Extract certifications
            certification_list = []
            for cert_data in ai_data.get('certifications', []):
                certification = Certification(
                    name=cert_data.get('name', ''),
                    issuer=cert_data.get('issuer', 'N/A'),
                    date=cert_data.get('date'),
                    expiry_date=cert_data.get('expiry_date')
                )
                certification_list.append(certification)
            
            # Create CV model
            cv_model = CVModel(
                metadata=metadata,
                personal_info=personal_info,
                summary=ai_data.get('summary'),
                experience=experience_list,
                education=education_list,
                skills=skills,
                certifications=certification_list
            )
            
            return cv_model
            
        except Exception as e:
            raise ImportServiceError(f"Failed to convert AI-parsed data to CV model: {e}")
