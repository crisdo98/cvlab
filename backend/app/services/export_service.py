"""
Export Service

Pandoc wrapper service that integrates with the existing export pipeline.
Provides JSON to Markdown conversion functionality and manages export
operations using the existing export.sh script and Pandoc configuration.
"""

import json
import os
import subprocess
import tempfile
import shutil
import re
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import logging

from ..models.cv_models import CVModel, CVModelV2
from ..models.cv_section_models import (
    Section, SectionType, PersonalInfoContent, FreeTextSectionContent,
    ListSectionContent, StructuredSectionContent, ExperienceEntry,
    EducationEntry, CertificationEntry
)
from ..models.export_models import (
    ExportFormat, ExportRequest, ExportResponse, ExportStatus, 
    ExportError, ExportOptions, PandocConfig, ExportMetrics
)
from ..models.typography_models import TypographyConfig
from ..utils.pdf_engines import (
    get_pdf_engine_detector, PDFEngine, validate_pdf_engine_availability
)
from ..utils.latex_template_generator import generate_latex_template
from ..utils.docx_reference_generator import generate_docx_reference
from .markdown_blocks import normalise_markdown_block

logger = logging.getLogger(__name__)


class ExportServiceError(Exception):
    """Base exception for export service operations."""
    pass


class PandocError(ExportServiceError):
    """Raised when Pandoc operations fail."""
    pass


class LaTeXError(ExportServiceError):
    """Raised when LaTeX compilation fails."""
    pass


class PDFEngineError(ExportServiceError):
    """Raised when PDF engine operations fail."""
    pass


class ValidationError(ExportServiceError):
    """Raised when export validation fails."""
    pass


class ExportService:
    """
    Service for handling CV export operations using Pandoc.
    
    Integrates with the existing export pipeline by converting CV JSON data
    to Markdown format and invoking the existing export.sh script with
    appropriate parameters.
    """
    
    def __init__(self, 
                 root_dir: Optional[str] = None,
                 export_script_path: Optional[str] = None):
        """
        Initialize ExportService.
        
        Args:
            root_dir: Root directory of the application (defaults to project root)
            export_script_path: Path to export.sh script (defaults to scripts/export.sh)
        """
        # Set up paths
        self.root_dir = Path(root_dir) if root_dir else Path(__file__).parent.parent.parent.parent
        self.export_script_path = Path(export_script_path) if export_script_path else self.root_dir / "scripts" / "export.sh"
        
        # Directory paths
        self.cv_dir = self.root_dir / "cv"
        self.exports_dir = self.root_dir / "exports"
        self.templates_dir = self.root_dir / "templates"
        self.pandoc_dir = self.root_dir / "pandoc"
        
        # Initialize PDF engine detector
        self.pdf_detector = get_pdf_engine_detector()
        
        # Ensure directories exist
        self._ensure_directories()
        
        # Validate dependencies
        self._validate_dependencies()
    
    def _ensure_directories(self):
        """Ensure required directories exist."""
        directories = [
            self.cv_dir,
            self.exports_dir / "pdf",
            self.exports_dir / "docx", 
            self.exports_dir / "txt",
            self.templates_dir,
            self.pandoc_dir
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _validate_dependencies(self):
        """Validate that required dependencies are available."""
        validation_errors = []
        
        # Check if pandoc is available
        try:
            result = subprocess.run(
                ["pandoc", "--version"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            if result.returncode != 0:
                validation_errors.append("Pandoc is not properly installed")
            else:
                logger.info(f"Pandoc version: {result.stdout.split()[1] if result.stdout else 'unknown'}")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            validation_errors.append("Pandoc is not installed or not accessible")
        
        # Check if export script exists and is executable
        if not self.export_script_path.exists():
            validation_errors.append(f"Export script not found: {self.export_script_path}")
        elif not os.access(self.export_script_path, os.X_OK):
            validation_errors.append(f"Export script is not executable: {self.export_script_path}")
        
        # Validate PDF engines for PDF export capability
        pdf_valid, pdf_issues = validate_pdf_engine_availability()
        if not pdf_valid:
            logger.warning("No PDF engines available - PDF export will be disabled")
            logger.warning(f"PDF engine issues: {pdf_issues}")
        else:
            available_engines = self.pdf_detector.get_available_engines()
            logger.info(f"Available PDF engines: {[e.value for e in available_engines]}")
        
        # Check template files
        required_templates = ["cv.latex"]
        for template in required_templates:
            template_path = self.templates_dir / template
            if not template_path.exists():
                validation_errors.append(f"Required template not found: {template_path}")
        
        # Raise error if critical dependencies are missing
        if validation_errors:
            error_msg = "Critical dependencies missing:\n" + "\n".join(f"- {error}" for error in validation_errors)
            raise ExportServiceError(error_msg)
    
    def _generate_custom_template(self, typography: TypographyConfig) -> Optional[str]:
        """
        Generate custom LaTeX template from typography configuration.
        
        Args:
            typography: Typography configuration
            
        Returns:
            Path to generated template file, or None if generation fails
        """
        try:
            logger.info("Generating custom LaTeX template from typography configuration")
            
            # Generate template content
            template_content = generate_latex_template(typography)
            
            # Create temporary template file in /tmp instead of /app/templates (read-only in container)
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.latex',
                delete=False,
                encoding='utf-8',
                dir='/tmp'  # Use /tmp which is writable in containers
            )
            temp_file.write(template_content)
            temp_file.close()
            template_path = temp_file.name
            
            logger.info(f"Custom template generated: {template_path}")
            return template_path
            
        except Exception as e:
            logger.error(f"Failed to generate custom template: {e}")
            return None
    
    def _generate_custom_docx_reference(self, typography: TypographyConfig) -> Optional[str]:
        """
        Generate custom DOCX reference file from typography configuration.
        
        Args:
            typography: Typography configuration
            
        Returns:
            Path to generated reference file, or None if generation fails
        """
        try:
            logger.info("Generating custom DOCX reference from typography configuration")
            
            # Generate reference file in /tmp
            reference_path = generate_docx_reference(typography)
            
            logger.info(f"Custom DOCX reference generated: {reference_path}")
            return reference_path
            
        except Exception as e:
            logger.error(f"Failed to generate custom DOCX reference: {e}", exc_info=True)
            return None
    
    def _sanitize_yaml_value(self, value: str) -> str:
        """
        Sanitize a string value for safe YAML serialization.
        
        Removes control characters and ensures the value is safe for YAML.
        
        Args:
            value: String value to sanitize
            
        Returns:
            Sanitized string safe for YAML
        """
        if not value:
            return value
        
        # Remove control characters (except newlines and tabs which are valid)
        sanitized = ''.join(char for char in value if ord(char) >= 32 or char in '\n\t')
        
        return sanitized
    
    def json_to_markdown(self, cv_data) -> str:
        """
        Convert CV JSON data to Markdown format compatible with existing templates.
        
        Supports both legacy CVModel (version 1) and CVModelV2 (version 2 with sections).
        
        Args:
            cv_data: CV data model to convert (CVModel or CVModelV2)
            
        Returns:
            Markdown string with YAML frontmatter
        """
        # Detect which version and route to appropriate handler
        if isinstance(cv_data, CVModelV2) or (hasattr(cv_data, 'version') and cv_data.version == 2):
            return self._json_to_markdown_v2(cv_data)
        else:
            return self._json_to_markdown_v1(cv_data)
    
    def _json_to_markdown_v1(self, cv_data: CVModel) -> str:
        """
        Convert legacy CV JSON data (version 1) to Markdown format.
        
        Args:
            cv_data: Legacy CV data model to convert
            
        Returns:
            Markdown string with YAML frontmatter
        """
        try:
            # Build YAML frontmatter with sanitized values
            # See the note in the V2 generator: title/author/date become a
            # title block in DOCX that the LaTeX template does not render.
            frontmatter_dict = {
                "lang": "en-US",
                "colorlinks": True  # Use boolean for proper YAML
            }
            
            # Add contact information to frontmatter if available (with sanitization)
            if cv_data.personal_info.contact.email:
                frontmatter_dict["email"] = self._sanitize_yaml_value(cv_data.personal_info.contact.email)
            if cv_data.personal_info.contact.phone:
                frontmatter_dict["phone"] = self._sanitize_yaml_value(cv_data.personal_info.contact.phone)
            if cv_data.personal_info.contact.website:
                frontmatter_dict["website"] = self._sanitize_yaml_value(cv_data.personal_info.contact.website)
            if cv_data.personal_info.contact.linkedin:
                frontmatter_dict["linkedin"] = self._sanitize_yaml_value(cv_data.personal_info.contact.linkedin)
            
            # Build markdown content
            markdown_lines = []
            
            # Add YAML frontmatter using yaml.dump for proper escaping
            markdown_lines.append("---")
            frontmatter_yaml = yaml.dump(frontmatter_dict, default_flow_style=False, allow_unicode=True, sort_keys=False)
            # Remove the trailing newline that yaml.dump adds
            markdown_lines.append(frontmatter_yaml.rstrip('\n'))
            markdown_lines.append("---")
            markdown_lines.append("")
            
            # Add name as main heading
            markdown_lines.append(f"# {cv_data.personal_info.name}")
            
            # Add professional title if available (without italic formatting)
            if cv_data.personal_info.title:
                markdown_lines.append(f"{cv_data.personal_info.title}")
                markdown_lines.append("")
            
            # Add contact information
            contact_lines = []
            contact = cv_data.personal_info.contact
            if contact.address:
                contact_lines.append(contact.address)
            if contact.phone:
                contact_lines.append(contact.phone)
            if contact.email:
                contact_lines.append(f"[{contact.email}](mailto:{contact.email})")
            if contact.linkedin:
                linkedin_url = contact.linkedin if contact.linkedin.startswith("http") else f"https://{contact.linkedin}"
                contact_lines.append(f"[LinkedIn]({linkedin_url})")
            if contact.website:
                website_url = contact.website if contact.website.startswith("http") else f"https://{contact.website}"
                contact_lines.append(f"[Website]({website_url})")
            
            if contact_lines:
                markdown_lines.extend(contact_lines)
                markdown_lines.append("")
            
            # Add summary if available
            if cv_data.summary:
                markdown_lines.append("## Summary")
                markdown_lines.append("")
                markdown_lines.append(cv_data.summary)
                markdown_lines.append("")
            
            # Add experience section
            if cv_data.experience:
                markdown_lines.append("## Experience")
                markdown_lines.append("")
                
                for exp in cv_data.experience:
                    # Job title and company
                    markdown_lines.append(f"### {exp.title}")
                    company_line = f"**{exp.company}**"
                    if exp.location:
                        company_line += f" | {exp.location}"
                    markdown_lines.append(company_line)
                    
                    # Date range
                    date_range = exp.start_date
                    if exp.current:
                        date_range += " - Present"
                    elif exp.end_date:
                        date_range += f" - {exp.end_date}"
                    markdown_lines.append(f"*{date_range}*")
                    markdown_lines.append("")
                    
                    # Description. Normalised so its headings and bullets stay
                    # separate blocks rather than collapsing into one paragraph.
                    if exp.description:
                        markdown_lines.append(normalise_markdown_block(exp.description))
                        markdown_lines.append("")
                    
                    # Achievements
                    if exp.achievements:
                        for achievement in exp.achievements:
                            markdown_lines.append(f"- {achievement}")
                        markdown_lines.append("")
            
            # Add education section
            if cv_data.education:
                markdown_lines.append("## Education")
                markdown_lines.append("")
                
                for edu in cv_data.education:
                    # Degree and institution
                    markdown_lines.append(f"### {edu.degree}")
                    institution_line = f"**{edu.institution}**"
                    if edu.location:
                        institution_line += f" | {edu.location}"
                    markdown_lines.append(institution_line)
                    
                    # Date range
                    if edu.start_date or edu.end_date:
                        date_parts = []
                        if edu.start_date:
                            date_parts.append(edu.start_date)
                        if edu.end_date:
                            if edu.start_date:
                                date_parts.append(f" - {edu.end_date}")
                            else:
                                date_parts.append(edu.end_date)
                        markdown_lines.append(f"*{''.join(date_parts)}*")
                    
                    # GPA
                    if edu.gpa:
                        markdown_lines.append(f"*GPA: {edu.gpa}*")
                    
                    markdown_lines.append("")
                    
                    # Description
                    if edu.description:
                        markdown_lines.append(normalise_markdown_block(edu.description))
                        markdown_lines.append("")
            
            # Add skills section
            if cv_data.skills.categories:
                # Only create section if there are categories with actual skills
                categories_with_skills = [cat for cat in cv_data.skills.categories if cat.skills]
                if categories_with_skills:
                    markdown_lines.append("## Skills")
                    markdown_lines.append("")
                    
                    for category in categories_with_skills:
                        markdown_lines.append(f"**{category.name}:** {', '.join(category.skills)}")
                        markdown_lines.append("")
            
            # Add certifications section
            if cv_data.certifications:
                markdown_lines.append("## Certifications")
                markdown_lines.append("")
                
                for cert in cv_data.certifications:
                    cert_line = f"- **{cert.name}** - {cert.issuer}"
                    if cert.date:
                        cert_line += f" ({cert.date}"
                        if cert.expiry_date:
                            cert_line += f" - {cert.expiry_date}"
                        cert_line += ")"
                    markdown_lines.append(cert_line)
                
                markdown_lines.append("")
            
            return "\n".join(markdown_lines)
            
        except Exception as e:
            raise ExportServiceError(f"Failed to convert CV to Markdown: {e}")
    
    def _json_to_markdown_v2(self, cv_data: CVModelV2) -> str:
        """
        Convert CV JSON data with flexible sections (version 2) to Markdown format.
        
        Uses get_visible_sections() to respect section order and visibility settings.
        
        Args:
            cv_data: CV data model with sections to convert
            
        Returns:
            Markdown string with YAML frontmatter
        """
        try:
            # Get visible sections in order
            visible_sections = cv_data.get_visible_sections()
            
            # Build YAML frontmatter.
            #
            # No title, author or date: pandoc renders those as a title block
            # in DOCX — a large gap, the name repeated, and the Title style's
            # bottom border as a stray horizontal rule. The LaTeX template
            # ignores them, which is why the PDF never showed it. The body
            # already carries the name and contact line, so the metadata was
            # only ever duplication.
            frontmatter_dict = {
                "lang": "en-US",
                "colorlinks": True
            }
            
            # Extract personal info from sections if available
            personal_section = cv_data.get_section_by_type(SectionType.PERSONAL_INFO)
            if personal_section and isinstance(personal_section.content, PersonalInfoContent):
                personal_info = personal_section.content
                if personal_info.email:
                    frontmatter_dict["email"] = self._sanitize_yaml_value(personal_info.email)
                if personal_info.phone:
                    frontmatter_dict["phone"] = self._sanitize_yaml_value(personal_info.phone)
                if personal_info.website:
                    frontmatter_dict["website"] = self._sanitize_yaml_value(personal_info.website)
                if personal_info.linkedin:
                    frontmatter_dict["linkedin"] = self._sanitize_yaml_value(personal_info.linkedin)
            
            # Build markdown content
            markdown_lines = []
            
            # Add YAML frontmatter
            markdown_lines.append("---")
            frontmatter_yaml = yaml.dump(frontmatter_dict, default_flow_style=False, allow_unicode=True, sort_keys=False)
            markdown_lines.append(frontmatter_yaml.rstrip('\n'))
            markdown_lines.append("---")
            markdown_lines.append("")
            
            # Render each visible section in order
            for section in visible_sections:
                section_markdown = self._render_section_to_markdown(section)
                if section_markdown:
                    markdown_lines.append(section_markdown)
                    markdown_lines.append("")
            
            return "\n".join(markdown_lines)
            
        except Exception as e:
            raise ExportServiceError(f"Failed to convert CV to Markdown: {e}")
    
    def _render_section_to_markdown(self, section: Section) -> str:
        """
        Render a single section to Markdown format based on its type.
        
        Args:
            section: Section to render
            
        Returns:
            Markdown string for the section
        """
        try:
            logger.debug(f"Rendering section: {section.id} ({section.type})")
            lines = []
            
            # Handle different section types
            if section.type == SectionType.PERSONAL_INFO:
                lines.extend(self._render_personal_info_section(section))
            elif section.type == SectionType.SUMMARY:
                lines.extend(self._render_free_text_section(section))
            elif section.type == SectionType.EXPERIENCE:
                lines.extend(self._render_experience_section(section))
            elif section.type == SectionType.EDUCATION:
                lines.extend(self._render_education_section(section))
            elif section.type == SectionType.SKILLS:
                lines.extend(self._render_list_section(section))
            elif section.type == SectionType.LANGUAGES:
                lines.extend(self._render_list_section(section))
            elif section.type == SectionType.SOFTWARE:
                lines.extend(self._render_list_section(section))
            elif section.type == SectionType.CERTIFICATIONS:
                lines.extend(self._render_certification_section(section))
            elif section.type == SectionType.ACCOMPLISHMENTS:
                lines.extend(self._render_list_section(section))
            elif section.type == SectionType.AFFILIATIONS:
                lines.extend(self._render_list_section(section))
            elif section.type == SectionType.INTERESTS:
                lines.extend(self._render_list_section(section))
            elif section.type == SectionType.WEBSITES:
                lines.extend(self._render_list_section(section))
            elif section.type == SectionType.CUSTOM:
                lines.extend(self._render_free_text_section(section))
            else:
                logger.warning(f"Unknown section type: {section.type}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Failed to render section {section.id} ({section.type}): {e}", exc_info=True)
            # Return a comment instead of failing the entire export
            return f"<!-- Section '{section.title}' could not be rendered: {str(e)} -->"
    
    def _render_personal_info_section(self, section: Section) -> List[str]:
        """Render personal information section."""
        lines = []
        
        try:
            if not isinstance(section.content, PersonalInfoContent):
                logger.warning(f"Personal info section has wrong content type: {type(section.content)}")
                return lines
            
            content = section.content
            
            # Add name as main heading
            if content.full_name:
                lines.append(f"# {content.full_name}")
                lines.append("")  # Blank line after name
            
            # Add professional title if available
            if content.title:
                lines.append(f"{content.title}")
                lines.append("")
            
            # Add contact information
            contact_parts = []
            if content.email:
                contact_parts.append(content.email)
            if content.phone:
                contact_parts.append(content.phone)
            if content.location:
                contact_parts.append(content.location)
            if content.linkedin:
                contact_parts.append("LinkedIn")
            if content.website:
                contact_parts.append("Website")
            
            if contact_parts:
                contact_line = " | ".join(contact_parts)
                # A single Pandoc div serves every output format: the
                # contact_info Lua filter turns it into \contactinfo{...} for
                # LaTeX, the custom-style applies the Subtitle style in DOCX,
                # and plain text renders the line as-is
                lines.append("::: {.contact-info custom-style=\"Subtitle\"}")
                lines.append(contact_line)
                lines.append(":::")
                lines.append("")
            
        except Exception as e:
            logger.error(f"Error rendering personal info section: {e}", exc_info=True)
        
        return lines
    
    def _render_free_text_section(self, section: Section) -> List[str]:
        """Render free-text section (Summary, Custom)."""
        lines = []
        
        try:
            if not isinstance(section.content, FreeTextSectionContent):
                logger.warning(f"Free text section has wrong content type: {type(section.content)}")
                return lines
            
            # Add section heading
            lines.append(f"## {section.title}")
            lines.append("")
            
            # Add content. Normalised like every other free text: a single
            # newline is a soft break in Markdown, so a summary written as
            # several paragraphs collapsed into one on export.
            if section.content.text:
                lines.append(normalise_markdown_block(section.content.text))
                
        except Exception as e:
            logger.error(f"Error rendering free text section: {e}", exc_info=True)
        
        return lines
    
    #: List sections written as a comma-separated run rather than one bullet
    #: per item. Skills are a vocabulary, not a set of accomplishments.
    COMMA_SEPARATED_SECTIONS = {SectionType.SKILLS}

    def _render_list_section(self, section: Section) -> List[str]:
        """Render list-based section (Skills, Languages, Software, etc.)."""
        lines = []
        
        try:
            if not isinstance(section.content, ListSectionContent):
                logger.warning(f"List section has wrong content type: {type(section.content)}")
                return lines
            
            # Add section heading
            lines.append(f"## {section.title}")
            lines.append("")
            
            # Add list items.
            #
            # Skills read better as a run of comma-separated terms than as one
            # bullet per skill: a bullet per line turns twenty skills into most
            # of a page, and ATS parsers read either form equally well.
            items = [
                item.text for item in (section.content.items or [])
                if getattr(item, 'text', None)
            ]

            if items:
                if section.type in self.COMMA_SEPARATED_SECTIONS:
                    lines.append(", ".join(items))
                else:
                    for text in items:
                        lines.append(f"- {text}")
                        
        except Exception as e:
            logger.error(f"Error rendering list section: {e}", exc_info=True)
        
        return lines
    
    def _render_experience_section(self, section: Section) -> List[str]:
        """Render experience section with structured entries."""
        lines = []
        
        if not isinstance(section.content, StructuredSectionContent):
            return lines
        
        # Add section heading
        lines.append(f"## {section.title}")
        lines.append("")
        
        # Render each experience entry
        for entry in section.content.entries:
            if isinstance(entry, ExperienceEntry):
                # Job title
                lines.append(f"### {entry.title}")
                
                # Company and location
                company_line = f"**{entry.company}**" if entry.company else ""
                if entry.location:
                    company_line += f" | {entry.location}" if company_line else entry.location
                if company_line:
                    lines.append(company_line)
                
                # Date range
                if entry.start_date:
                    date_range = entry.start_date
                    if entry.current:
                        date_range += " - Present"
                    elif entry.end_date:
                        date_range += f" - {entry.end_date}"
                    lines.append(f"*{date_range}*")
                
                lines.append("")
                
                # Description. See the note in the V1 exporter above.
                if entry.description:
                    lines.append(normalise_markdown_block(entry.description))
                    lines.append("")
                
                # Achievements
                if entry.achievements:
                    for achievement in entry.achievements:
                        lines.append(f"- {achievement}")
                    lines.append("")
        
        return lines
    
    def _render_education_section(self, section: Section) -> List[str]:
        """Render education section with structured entries."""
        lines = []
        
        if not isinstance(section.content, StructuredSectionContent):
            return lines
        
        # Add section heading
        lines.append(f"## {section.title}")
        lines.append("")
        
        # Render each education entry
        for entry in section.content.entries:
            if isinstance(entry, EducationEntry):
                # Degree
                lines.append(f"### {entry.degree}")
                
                # Institution and location
                institution_line = f"**{entry.institution}**"
                if entry.location:
                    institution_line += f" | {entry.location}"
                lines.append(institution_line)
                
                # Date range
                if entry.start_date or entry.end_date:
                    date_parts = []
                    if entry.start_date:
                        date_parts.append(entry.start_date)
                    if entry.end_date:
                        if entry.start_date:
                            date_parts.append(f" - {entry.end_date}")
                        else:
                            date_parts.append(entry.end_date)
                    lines.append(f"*{''.join(date_parts)}*")
                
                # GPA
                if entry.gpa:
                    lines.append(f"*GPA: {entry.gpa}*")
                
                lines.append("")
                
                # Description. See the note in the V1 exporter above.
                if entry.description:
                    lines.append(normalise_markdown_block(entry.description))
                    lines.append("")
        
        return lines
    
    def _render_certification_section(self, section: Section) -> List[str]:
        """Render certification section with structured entries."""
        lines = []
        
        if not isinstance(section.content, StructuredSectionContent):
            return lines
        
        # Add section heading
        lines.append(f"## {section.title}")
        lines.append("")
        
        # Render each certification entry
        for entry in section.content.entries:
            if isinstance(entry, CertificationEntry):
                cert_line = f"- **{entry.name}** - {entry.issuer}"
                if entry.date:
                    cert_line += f" ({entry.date}"
                    if entry.expiry_date:
                        cert_line += f" - {entry.expiry_date}"
                    cert_line += ")"
                lines.append(cert_line)
        
        return lines
    
    #: Styles pandoc reserves for the metadata title block.
    _TITLE_BLOCK_STYLES = ("Title", "Author", "Date")

    def _strip_docx_title_block(self, path: str) -> None:
        """Remove pandoc's empty title-block paragraphs from a DOCX.

        pandoc emits a Title, Author and Date paragraph whether or not the
        document has that metadata. With none they come out empty, which in
        Word is a large gap at the top of the CV plus a stray horizontal rule —
        the Title style carries a bottom border. The LaTeX template renders no
        title block at all, so the PDF never showed any of it.

        Only paragraphs that are both styled as part of the title block *and*
        empty are removed, so a document that genuinely has a title keeps it.
        """
        import re
        import shutil
        import zipfile

        document = 'word/document.xml'

        try:
            with zipfile.ZipFile(path) as archive:
                if document not in archive.namelist():
                    return
                parts = {name: archive.read(name) for name in archive.namelist()}

            xml = parts[document].decode('utf-8')

            def drop(match: 're.Match[str]') -> str:
                paragraph = match.group(0)
                style = re.search(r'<w:pStyle w:val="([^"]+)"', paragraph)
                if not style or style.group(1) not in self._TITLE_BLOCK_STYLES:
                    return paragraph
                text = ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', paragraph))
                return '' if not text.strip() else paragraph

            cleaned = re.sub(r'<w:p\b.*?</w:p>', drop, xml, flags=re.S)
            if cleaned == xml:
                return

            parts[document] = cleaned.encode('utf-8')
            temp_path = f"{path}.tmp"
            with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as archive:
                for name, data in parts.items():
                    archive.writestr(name, data)
            shutil.move(temp_path, path)
            logger.info("Removed empty title-block paragraphs from %s", path)

        except Exception as exc:
            # Cosmetic: never let this cost the export.
            logger.warning(f"Could not tidy the DOCX title block: {exc}")

    def export_cv(
        self,
        cv_data,
        export_request: ExportRequest,
        appendix_markdown: Optional[str] = None
    ) -> ExportResponse:
        """
        Export CV to specified format using the existing export pipeline.
        
        Args:
            cv_data: CV data to export
            export_request: Export configuration
            appendix_markdown: Optional Markdown appended after the CV. Used by
                the recommendations export so the assessment runs through the
                same pandoc pipeline, and therefore inherits the CV's
                typography rather than looking like a separate document.
            
        Returns:
            ExportResponse with export results
        """
        export_response = ExportResponse(
            cv_id=export_request.cv_id,
            format=export_request.format,
            status=ExportStatus.IN_PROGRESS
        )
        
        temp_md_file = None
        
        try:
            logger.info(f"Starting export for CV {export_request.cv_id}, format: {export_request.format}")
            logger.info(f"CV data type: {type(cv_data)}, version: {getattr(cv_data, 'version', 'unknown')}")
            
            # Validate export request
            validation_error = self.validate_export_request(export_request)
            if validation_error:
                export_response.status = ExportStatus.FAILED
                export_response.error_message = self._format_error_with_suggestions(
                    validation_error.message,
                    validation_error.suggestions or []
                )
                return export_response
            
            # Validate self-contained operation requirements
            self._validate_self_contained_operation(export_request.format)
            
            # Generate custom LaTeX template if typography is configured
            custom_template_path = None
            custom_docx_reference = None
            
            # A CV created by import carries no typography, and the export
            # then fell back to the static template in /app/templates, which
            # looks nothing like the preview — different fonts, justification
            # and indentation. Falling back to the same defaults the preview
            # uses keeps the two in agreement whether or not a template has
            # ever been applied.
            typography = cv_data.typography or TypographyConfig()

            if typography:
                if export_request.format == ExportFormat.PDF:
                    logger.info("Generating custom LaTeX template from typography")
                    custom_template_path = self._generate_custom_template(typography)
                    if custom_template_path:
                        logger.info(f"Custom template generated at: {custom_template_path}")
                        # Log first 500 chars of template for debugging
                        try:
                            with open(custom_template_path, 'r') as f:
                                template_preview = f.read(500)
                                logger.info(f"Template preview: {template_preview}...")
                        except Exception as e:
                            logger.warning(f"Could not read template for logging: {e}")
                    else:
                        logger.warning("Custom template generation returned None")
                
                elif export_request.format == ExportFormat.DOCX:
                    logger.info("Generating custom DOCX reference from typography")
                    custom_docx_reference = self._generate_custom_docx_reference(typography)
                    if custom_docx_reference:
                        logger.info(f"Custom DOCX reference generated at: {custom_docx_reference}")
                    else:
                        logger.warning("Custom DOCX reference generation returned None")
            
            # Convert CV to Markdown
            logger.info("Converting CV to Markdown")
            try:
                markdown_content = self.json_to_markdown(cv_data)
                if appendix_markdown:
                    markdown_content = f"{markdown_content.rstrip()}\n\n{appendix_markdown}"
                    logger.info(
                        f"Appended {len(appendix_markdown)} characters of assessment"
                    )
                logger.info(f"Markdown generated, length: {len(markdown_content)} characters")
            except Exception as e:
                logger.error(f"Failed to generate markdown: {e}", exc_info=True)
                raise ExportServiceError(f"Failed to generate markdown: {e}")
            
            # Create temporary markdown file
            with tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.md', 
                delete=False,
                encoding='utf-8'
            ) as temp_file:
                temp_file.write(markdown_content)
                temp_md_file = temp_file.name
            
            # Generate output filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            
            # Get title - handle both V1 (metadata.title) and V2 (no metadata)
            try:
                if hasattr(cv_data, 'metadata') and cv_data.metadata:
                    title = cv_data.metadata.title
                else:
                    # For V2, try to get name from personal info section
                    from ..models.cv_section_models import SectionType
                    personal_section = cv_data.get_section_by_type(SectionType.PERSONAL_INFO) if hasattr(cv_data, 'get_section_by_type') else None
                    if personal_section and hasattr(personal_section.content, 'full_name'):
                        title = personal_section.content.full_name or f"cv-{cv_data.id[:8]}"
                    else:
                        title = f"cv-{cv_data.id[:8]}"
            except Exception as e:
                logger.warning(f"Failed to get CV title: {e}, using default")
                title = f"cv-{cv_data.id[:8]}"
            
            # Sanitize title for filename
            title = title.lower().replace(' ', '-').replace('/', '-').replace('\\', '-')
            base_name = f"{title}-{timestamp}"
            
            logger.info(f"Generated base name for export: {base_name}")
            
            # Execute export script with enhanced error handling
            result = self._execute_export_script_with_fallback(
                temp_md_file, 
                base_name, 
                export_request.format,
                custom_template_path,
                custom_docx_reference
            )
            
            if result["success"]:
                if export_request.format == ExportFormat.DOCX:
                    self._strip_docx_title_block(result["file_path"])

                export_response.status = ExportStatus.COMPLETED
                export_response.file_path = result["file_path"]
                
                # Extract filename from file_path for download URL
                file_path = Path(result["file_path"])
                filename = file_path.name
                export_response.download_url = f"/api/export/download/{filename}"
                
                export_response.completed_at = datetime.now()
                export_response.file_size = result.get("file_size", 0)
                
                logger.info(f"Successfully exported CV {export_request.cv_id} to {export_request.format}")
            else:
                export_response.status = ExportStatus.FAILED
                export_response.error_message = self._format_user_friendly_error(
                    result.get("error", "Export failed"),
                    result.get("stderr", ""),
                    export_request.format
                )
                
                logger.error(f"Failed to export CV {export_request.cv_id}: {export_response.error_message}")
            
            return export_response
            
        except ValidationError as e:
            export_response.status = ExportStatus.FAILED
            export_response.error_message = str(e)
            logger.error(f"Validation error for CV {export_request.cv_id}: {e}")
            return export_response
            
        except Exception as e:
            export_response.status = ExportStatus.FAILED
            export_response.error_message = self._format_user_friendly_error(str(e), "", export_request.format)
            logger.error(f"Export service error for CV {export_request.cv_id}: {e}")
            return export_response
            
        finally:
            # Clean up temporary file
            if temp_md_file and os.path.exists(temp_md_file):
                try:
                    os.unlink(temp_md_file)
                except OSError as e:
                    logger.warning(f"Failed to clean up temporary file {temp_md_file}: {e}")
    
    def _execute_export_script_with_fallback(self, markdown_file: str, base_name: str, format: ExportFormat, custom_template_path: Optional[str] = None, custom_docx_reference: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute export script with PDF engine fallback for PDF exports.
        
        Args:
            markdown_file: Path to temporary markdown file
            base_name: Base name for output files
            format: Export format
            custom_template_path: Optional path to custom LaTeX template
            custom_docx_reference: Optional path to custom DOCX reference file
            
        Returns:
            Dictionary with execution results
        """
        # For non-PDF formats, use standard execution
        if format != ExportFormat.PDF:
            return self._execute_export_script(markdown_file, base_name, format, custom_template_path, custom_docx_reference)
        
        # For PDF format, try with fallback engines
        available_engines = self.pdf_detector.get_available_engines()
        
        if not available_engines:
            return {
                "success": False,
                "error": "No PDF engines available for PDF export",
                "suggestions": [
                    "Install XeLaTeX: apt-get install texlive-xetex (Ubuntu/Debian) or brew install --cask mactex (macOS)",
                    "Install Tectonic: cargo install tectonic or download from https://tectonic-typesetting.github.io/"
                ]
            }
        
        last_error = None
        last_stderr = None
        
        for engine in available_engines:
            logger.info(f"Attempting PDF export with {engine.value}")
            
            try:
                result = self._execute_export_script_with_engine(markdown_file, base_name, format, engine, custom_template_path, custom_docx_reference)
                
                if result["success"]:
                    logger.info(f"PDF export successful with {engine.value}")
                    return result
                else:
                    last_error = result.get("error", f"Export failed with {engine.value}")
                    last_stderr = result.get("stderr", "")
                    logger.warning(f"PDF export failed with {engine.value}: {last_error}")
                    
            except Exception as e:
                last_error = f"Exception with {engine.value}: {str(e)}"
                logger.warning(f"PDF export exception with {engine.value}: {e}")
        
        # All engines failed
        return {
            "success": False,
            "error": f"PDF export failed with all available engines. Last error: {last_error}",
            "stderr": last_stderr,
            "suggestions": self._get_pdf_troubleshooting_suggestions(last_stderr or "")
        }
    
    def _execute_export_script_with_engine(self, markdown_file: str, base_name: str, format: ExportFormat, engine: PDFEngine, custom_template_path: Optional[str] = None, custom_docx_reference: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute export script with a specific PDF engine.
        
        Args:
            markdown_file: Path to temporary markdown file
            base_name: Base name for output files
            format: Export format
            engine: PDF engine to use
            custom_template_path: Optional path to custom LaTeX template
            custom_docx_reference: Optional path to custom DOCX reference file
            
        Returns:
            Dictionary with execution results
        """
        try:
            # Copy markdown file to cv directory with proper name
            cv_file_path = self.cv_dir / f"{base_name}.md"
            logger.info(f"Copying markdown from {markdown_file} to {cv_file_path}")
            shutil.copy2(markdown_file, cv_file_path)
            logger.info(f"Markdown file copied successfully, size: {cv_file_path.stat().st_size} bytes")
            
            # Set up environment variables
            env = os.environ.copy()
            env["ROOT_DIR"] = str(self.root_dir)
            env["PDF_ENGINE"] = engine.value  # Pass preferred engine to script
            
            # If custom template is provided, set it in environment
            if custom_template_path:
                env["CUSTOM_TEMPLATE"] = custom_template_path
                logger.info(f"Using custom LaTeX template: {custom_template_path}")
            
            # If custom DOCX reference is provided, set it in environment
            if custom_docx_reference:
                env["CUSTOM_DOCX_REFERENCE"] = custom_docx_reference
                logger.info(f"Using custom DOCX reference: {custom_docx_reference}")
            
            # Execute export script
            # Only build the requested format so one export produces one file
            cmd = [str(self.export_script_path), base_name, format.value]
            
            logger.info(f"Executing export command with {engine.value}: {' '.join(cmd)}")
            logger.info(f"Working directory: {self.root_dir}")
            env_log = f"ROOT_DIR={env['ROOT_DIR']}, PDF_ENGINE={env['PDF_ENGINE']}"
            if custom_template_path:
                env_log += f", CUSTOM_TEMPLATE={env.get('CUSTOM_TEMPLATE', 'not set')}"
            if custom_docx_reference:
                env_log += f", CUSTOM_DOCX_REFERENCE={env.get('CUSTOM_DOCX_REFERENCE', 'not set')}"
            logger.info(f"Environment: {env_log}")
            
            result = subprocess.run(
                cmd,
                cwd=str(self.root_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            logger.info(f"Export script completed with return code: {result.returncode}")
            if result.stdout:
                logger.info(f"Script stdout: {result.stdout[:500]}")
            if result.stderr:
                logger.warning(f"Script stderr: {result.stderr[:500]}")
            
            # Clean up temporary CV file
            if cv_file_path.exists():
                cv_file_path.unlink()
            
            if result.returncode == 0:
                # Find the generated file
                output_file = self._find_output_file(base_name, format)
                
                if output_file and output_file.exists():
                    file_size = output_file.stat().st_size
                    return {
                        "success": True,
                        "file_path": str(output_file),
                        "file_size": file_size,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "engine_used": engine.value
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Output file not found for format {format} with engine {engine.value}",
                        "stdout": result.stdout,
                        "stderr": result.stderr
                    }
            else:
                return {
                    "success": False,
                    "error": f"Export script failed with code {result.returncode} using {engine.value}",
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Export operation timed out with {engine.value}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to execute export script with {engine.value}: {e}"
            }
    def _execute_export_script(self, markdown_file: str, base_name: str, format: ExportFormat, custom_template_path: Optional[str] = None, custom_docx_reference: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the existing export.sh script with the provided markdown file.
        
        Args:
            markdown_file: Path to temporary markdown file
            base_name: Base name for output files
            format: Export format
            custom_template_path: Optional path to custom LaTeX template
            custom_docx_reference: Optional path to custom DOCX reference file
            
        Returns:
            Dictionary with execution results
        """
        try:
            logger.info(f"_execute_export_script called with markdown_file={markdown_file}, base_name={base_name}, format={format}")
            
            # Copy markdown file to cv directory with proper name
            cv_file_path = self.cv_dir / f"{base_name}.md"
            logger.info(f"Copying markdown from {markdown_file} to {cv_file_path}")
            logger.info(f"Source file exists: {os.path.exists(markdown_file)}")
            logger.info(f"Target directory exists: {self.cv_dir.exists()}")
            logger.info(f"Target directory writable: {os.access(self.cv_dir, os.W_OK)}")
            
            shutil.copy2(markdown_file, cv_file_path)
            logger.info(f"Markdown file copied successfully, size: {cv_file_path.stat().st_size} bytes")
            
            # Set up environment variables
            env = os.environ.copy()
            env["ROOT_DIR"] = str(self.root_dir)
            
            # If custom template is provided, set it in environment
            if custom_template_path:
                env["CUSTOM_TEMPLATE"] = custom_template_path
                logger.info(f"Using custom LaTeX template: {custom_template_path}")
            
            # If custom DOCX reference is provided, set it in environment
            if custom_docx_reference:
                env["CUSTOM_DOCX_REFERENCE"] = custom_docx_reference
                logger.info(f"Using custom DOCX reference: {custom_docx_reference}")
            
            # Execute export script
            # Only build the requested format so one export produces one file
            cmd = [str(self.export_script_path), base_name, format.value]
            
            logger.info(f"Executing export command: {' '.join(cmd)}")
            logger.info(f"Working directory: {self.root_dir}")
            
            # Log all custom environment variables
            custom_env_vars = []
            if 'CUSTOM_TEMPLATE' in env:
                custom_env_vars.append(f"CUSTOM_TEMPLATE={env['CUSTOM_TEMPLATE']}")
            if 'CUSTOM_DOCX_REFERENCE' in env:
                custom_env_vars.append(f"CUSTOM_DOCX_REFERENCE={env['CUSTOM_DOCX_REFERENCE']}")
            if custom_env_vars:
                logger.info(f"Custom environment variables: {', '.join(custom_env_vars)}")
            else:
                logger.info("No custom environment variables set")
            
            result = subprocess.run(
                cmd,
                cwd=str(self.root_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            logger.info(f"Export script completed with return code: {result.returncode}")
            if result.stdout:
                logger.info(f"Script stdout: {result.stdout[:500]}")
            if result.stderr:
                logger.warning(f"Script stderr: {result.stderr[:500]}")
            
            # Clean up temporary CV file
            if cv_file_path.exists():
                cv_file_path.unlink()
                logger.info(f"Cleaned up temporary CV file: {cv_file_path}")
            
            if result.returncode == 0:
                # Find the generated file
                output_file = self._find_output_file(base_name, format)
                
                if output_file and output_file.exists():
                    file_size = output_file.stat().st_size
                    logger.info(f"Export successful, output file: {output_file}, size: {file_size}")
                    return {
                        "success": True,
                        "file_path": str(output_file),
                        "file_size": file_size,
                        "stdout": result.stdout,
                        "stderr": result.stderr
                    }
                else:
                    logger.error(f"Output file not found for format {format}, expected at: {self.exports_dir / format.value}")
                    return {
                        "success": False,
                        "error": f"Output file not found for format {format}",
                        "stdout": result.stdout,
                        "stderr": result.stderr
                    }
            else:
                logger.error(f"Export script failed with code {result.returncode}")
                return {
                    "success": False,
                    "error": f"Export script failed with code {result.returncode}",
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
                
        except subprocess.TimeoutExpired:
            logger.error("Export operation timed out")
            return {
                "success": False,
                "error": "Export operation timed out"
            }
        except Exception as e:
            logger.error(f"Exception in _execute_export_script: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to execute export script: {e}"
            }
            return {
                "success": False,
                "error": f"Failed to execute export script: {e}"
            }
    
    def _validate_self_contained_operation(self, format: ExportFormat):
        """
        Validate that the export operation can run self-contained without external dependencies.
        
        Args:
            format: Export format to validate
            
        Raises:
            ValidationError: If self-contained operation requirements are not met
        """
        validation_errors = []
        
        # Check Pandoc availability
        try:
            subprocess.run(["pandoc", "--version"], capture_output=True, timeout=5)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            validation_errors.append("Pandoc is not available for self-contained operation")
        
        # For PDF exports, validate LaTeX engines
        if format == ExportFormat.PDF:
            available_engines = self.pdf_detector.get_available_engines()
            if not available_engines:
                validation_errors.append("No PDF engines available for self-contained PDF generation")
        
        # Check template availability
        if format == ExportFormat.PDF:
            latex_template = self.templates_dir / "cv.latex"
            if not latex_template.exists():
                validation_errors.append(f"LaTeX template not found: {latex_template}")
        
        # Check export script
        if not self.export_script_path.exists():
            validation_errors.append(f"Export script not found: {self.export_script_path}")
        
        if validation_errors:
            raise ValidationError(
                f"Self-contained operation validation failed: {'; '.join(validation_errors)}"
            )
    
    def _format_user_friendly_error(self, error_message: str, stderr_output: str, format: ExportFormat) -> str:
        """
        Format error messages in a user-friendly way with suggested fixes.
        
        Args:
            error_message: Raw error message
            stderr_output: Standard error output from the process
            format: Export format that failed
            
        Returns:
            User-friendly error message with suggestions
        """
        # Common LaTeX error patterns and their user-friendly explanations
        latex_error_patterns = {
            r"! LaTeX Error: File `.*\.sty' not found": {
                "message": "Missing LaTeX package",
                "suggestions": [
                    "Install the missing LaTeX package using your TeX distribution's package manager",
                    "For TeX Live: tlmgr install <package-name>",
                    "For MiKTeX: use the MiKTeX Package Manager"
                ]
            },
            r"! Undefined control sequence": {
                "message": "LaTeX command not recognized",
                "suggestions": [
                    "Check if all required LaTeX packages are loaded",
                    "Verify the LaTeX template syntax",
                    "Ensure the CV data doesn't contain unsupported LaTeX commands"
                ]
            },
            r"! Package fontspec Error": {
                "message": "Font loading error",
                "suggestions": [
                    "Install the required fonts on your system",
                    "Check if XeLaTeX is properly configured",
                    "Verify font names in the template are correct"
                ]
            },
            r"Runaway argument": {
                "message": "LaTeX parsing error",
                "suggestions": [
                    "Check for unmatched braces or brackets in your CV content",
                    "Ensure special characters are properly escaped",
                    "Review recent changes to CV content for syntax issues"
                ]
            }
        }
        
        # Check for specific LaTeX errors
        if format == ExportFormat.PDF and stderr_output:
            for pattern, error_info in latex_error_patterns.items():
                if re.search(pattern, stderr_output, re.IGNORECASE):
                    suggestions_text = "\n".join(f"• {suggestion}" for suggestion in error_info["suggestions"])
                    return f"{error_info['message']}\n\nSuggested fixes:\n{suggestions_text}"
        
        # Generic error handling
        if "timeout" in error_message.lower():
            return ("Export operation timed out. This usually indicates a complex document or system resource constraints.\n\n"
                   "Suggested fixes:\n"
                   "• Try exporting again\n"
                   "• Simplify the CV content temporarily\n"
                   "• Check system resources (CPU, memory)")
        
        if "not found" in error_message.lower():
            return ("Required file or command not found.\n\n"
                   "Suggested fixes:\n"
                   "• Ensure all dependencies are properly installed\n"
                   "• Check that the export script and templates are in place\n"
                   "• Verify the container has all required tools")
        
        if format == ExportFormat.PDF:
            suggestions = self._get_pdf_troubleshooting_suggestions(stderr_output)
            if suggestions:
                suggestions_text = "\n".join(f"• {suggestion}" for suggestion in suggestions)
                return f"PDF export failed: {error_message}\n\nSuggested fixes:\n{suggestions_text}"
        
        return f"Export failed: {error_message}"
    
    def _format_error_with_suggestions(self, message: str, suggestions: list[str]) -> str:
        """
        Format an error message with actionable suggestions.
        
        Args:
            message: Error message
            suggestions: List of suggested fixes
            
        Returns:
            Formatted error message with suggestions
        """
        if not suggestions:
            return message
        
        suggestions_text = "\n".join(f"• {suggestion}" for suggestion in suggestions)
        return f"{message}\n\nSuggested fixes:\n{suggestions_text}"
    
    def _get_pdf_troubleshooting_suggestions(self, stderr_output: str) -> List[str]:
        """
        Get troubleshooting suggestions for PDF export failures.
        
        Args:
            stderr_output: Standard error output from failed export
            
        Returns:
            List of troubleshooting suggestions
        """
        suggestions = []
        
        # Check PDF engine availability
        available_engines = self.pdf_detector.get_available_engines()
        if not available_engines:
            suggestions.extend([
                "Install XeLaTeX: apt-get install texlive-xetex (Ubuntu/Debian)",
                "Install Tectonic: cargo install tectonic",
                "Ensure LaTeX distribution is properly installed"
            ])
        
        # Analyze stderr for specific issues
        if stderr_output:
            if "font" in stderr_output.lower():
                suggestions.append("Install required fonts or check font configuration")
            
            if "package" in stderr_output.lower():
                suggestions.append("Install missing LaTeX packages using your TeX package manager")
            
            if "memory" in stderr_output.lower() or "capacity exceeded" in stderr_output.lower():
                suggestions.extend([
                    "Increase LaTeX memory limits",
                    "Simplify the CV content to reduce complexity"
                ])
        
        # General PDF troubleshooting
        if not suggestions:
            suggestions.extend([
                "Check that LaTeX templates are properly formatted",
                "Verify CV content doesn't contain problematic characters",
                "Try a different PDF engine if available",
                "Check container logs for more detailed error information"
            ])
        
        return suggestions
    
    def _find_output_file(self, base_name: str, format: ExportFormat) -> Optional[Path]:
        """
        Find the output file generated by the export script.
        
        Args:
            base_name: Base name used for the export
            format: Export format
            
        Returns:
            Path to the output file if found, None otherwise
        """
        format_dir = self.exports_dir / format.value
        
        # Look for files with the base name and timestamp pattern
        pattern = f"{base_name}-*.{format.value}"
        
        matching_files = list(format_dir.glob(pattern))
        
        if matching_files:
            # Return the most recent file
            return max(matching_files, key=lambda f: f.stat().st_mtime)
        
        return None
    
    def get_available_templates(self) -> List[Dict[str, Any]]:
        """
        Get list of available export templates.
        
        Returns:
            List of template information dictionaries
        """
        templates = []
        
        # Default template (always available)
        templates.append({
            "template_id": "default",
            "name": "Default CV Template",
            "description": "Standard professional CV template",
            "supported_formats": [ExportFormat.PDF, ExportFormat.DOCX, ExportFormat.TXT],
            "preview_available": False
        })
        
        return templates
    
    def validate_export_request(self, export_request: ExportRequest) -> Optional[ExportError]:
        """
        Validate an export request with comprehensive checks.
        
        Args:
            export_request: Export request to validate
            
        Returns:
            ExportError if validation fails, None if valid
        """
        # Validate CV ID
        if not export_request.cv_id or len(export_request.cv_id.strip()) == 0:
            return ExportError(
                error_type="validation_error",
                message="CV ID is required",
                suggestions=["Provide a valid CV ID"]
            )
        
        # Validate format
        if export_request.format not in ExportFormat:
            return ExportError(
                error_type="validation_error", 
                message=f"Unsupported export format: {export_request.format}",
                suggestions=[f"Use one of: {', '.join([f.value for f in ExportFormat])}"]
            )
        
        # Special validation for PDF format
        if export_request.format == ExportFormat.PDF:
            pdf_valid, pdf_issues = validate_pdf_engine_availability()
            if not pdf_valid:
                return ExportError(
                    error_type="dependency_error",
                    message="PDF export is not available - no PDF engines found",
                    suggestions=[
                        "Install XeLaTeX: apt-get install texlive-xetex (Ubuntu/Debian)",
                        "Install Tectonic: cargo install tectonic",
                        "Ensure LaTeX distribution is properly configured"
                    ]
                )
        
        # Validate template
        available_templates = [t["template_id"] for t in self.get_available_templates()]
        if export_request.template_id and export_request.template_id not in available_templates:
            return ExportError(
                error_type="validation_error",
                message=f"Unknown template: {export_request.template_id}",
                suggestions=[f"Use one of: {', '.join(available_templates)}"]
            )
        
        # Validate export directory permissions
        format_dir = self.exports_dir / export_request.format.value
        if not format_dir.exists():
            try:
                format_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                return ExportError(
                    error_type="permission_error",
                    message=f"Cannot create export directory: {format_dir}",
                    suggestions=[
                        "Check directory permissions",
                        "Ensure the application has write access to the export directory"
                    ]
                )
        
        if not os.access(format_dir, os.W_OK):
            return ExportError(
                error_type="permission_error",
                message=f"No write permission to export directory: {format_dir}",
                suggestions=[
                    "Check directory permissions",
                    "Ensure the application has write access to the export directory"
                ]
            )
        
        return None
    
    def get_export_metrics(self, export_response: ExportResponse) -> ExportMetrics:
        """
        Generate metrics for an export operation.
        
        Args:
            export_response: Completed export response
            
        Returns:
            ExportMetrics with operation statistics
        """
        processing_time = 0.0
        if export_response.completed_at and export_response.created_at:
            processing_time = (export_response.completed_at - export_response.created_at).total_seconds()
        
        return ExportMetrics(
            export_id=export_response.export_id,
            processing_time=processing_time,
            file_size=export_response.file_size or 0,
            template_used="default",  # TODO: Get from export_request
            success=export_response.status == ExportStatus.COMPLETED,
            error_details=ExportError(
                error_type="export_error",
                message=export_response.error_message or "Unknown error"
            ) if export_response.status == ExportStatus.FAILED else None
        )
    
    def get_system_diagnostics(self) -> Dict[str, Any]:
        """
        Get comprehensive system diagnostics for troubleshooting.
        
        Returns:
            Dictionary with system diagnostic information
        """
        diagnostics = {
            "timestamp": datetime.now().isoformat(),
            "dependencies": {},
            "pdf_engines": {},
            "directories": {},
            "templates": {}
        }
        
        # Check Pandoc
        try:
            result = subprocess.run(["pandoc", "--version"], capture_output=True, text=True, timeout=10)
            diagnostics["dependencies"]["pandoc"] = {
                "available": result.returncode == 0,
                "version": result.stdout.split('\n')[0] if result.returncode == 0 else None,
                "error": result.stderr if result.returncode != 0 else None
            }
        except Exception as e:
            diagnostics["dependencies"]["pandoc"] = {
                "available": False,
                "error": str(e)
            }
        
        # Check PDF engines
        engine_info = self.pdf_detector.detect_engines(force_refresh=True)
        for engine, info in engine_info.items():
            diagnostics["pdf_engines"][engine.value] = {
                "available": info.available,
                "version": info.version,
                "path": info.path,
                "error": info.error_message
            }
        
        # Check directories
        directories_to_check = [
            ("root", self.root_dir),
            ("cv", self.cv_dir),
            ("exports", self.exports_dir),
            ("templates", self.templates_dir),
            ("pandoc", self.pandoc_dir)
        ]
        
        for name, path in directories_to_check:
            diagnostics["directories"][name] = {
                "path": str(path),
                "exists": path.exists(),
                "writable": os.access(path, os.W_OK) if path.exists() else False,
                "readable": os.access(path, os.R_OK) if path.exists() else False
            }
        
        # Check templates
        template_files = ["cv.latex", "defaults.yaml"]
        for template in template_files:
            template_path = self.templates_dir / template if template != "defaults.yaml" else self.pandoc_dir / template
            diagnostics["templates"][template] = {
                "path": str(template_path),
                "exists": template_path.exists(),
                "readable": os.access(template_path, os.R_OK) if template_path.exists() else False
            }
        
        # Check export script
        diagnostics["export_script"] = {
            "path": str(self.export_script_path),
            "exists": self.export_script_path.exists(),
            "executable": os.access(self.export_script_path, os.X_OK) if self.export_script_path.exists() else False
        }
        
        return diagnostics