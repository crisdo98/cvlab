"""
DOCX Reference Generator

Generates custom reference.docx files from typography configuration.
These reference files are used by Pandoc to style DOCX exports.
"""

import logging
import tempfile
from pathlib import Path
from typing import Optional
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE

from ..models.typography_models import (
    TypographyConfig,
    TypographyStyle,
    FontFamily,
    FontWeight,
    FontStyle,
    TextAlignment
)

logger = logging.getLogger(__name__)


class DOCXReferenceGenerator:
    """
    Generates DOCX reference files from typography configuration.
    
    Creates a properly styled reference.docx that Pandoc uses as a template
    for DOCX exports, ensuring typography settings are applied.
    """
    
    # Font family mapping to DOCX font names
    FONT_MAPPING = {
        FontFamily.LIBERATION_SANS: "Liberation Sans",
        FontFamily.LIBERATION_SERIF: "Liberation Serif",
        FontFamily.TIMES_NEW_ROMAN: "Times New Roman",
        FontFamily.ARIAL: "Arial",
        FontFamily.HELVETICA: "Arial",  # Helvetica → Arial for DOCX
        FontFamily.GEORGIA: "Georgia",
        FontFamily.PALATINO: "Book Antiqua",  # Palatino → Book Antiqua for DOCX
        FontFamily.COURIER: "Courier New"
    }
    
    def __init__(self, typography: Optional[TypographyConfig] = None):
        """
        Initialize generator with typography configuration.
        
        Args:
            typography: Typography configuration (uses defaults if None)
        """
        self.typography = typography or TypographyConfig()
    
    def generate_reference(self, output_path: Optional[str] = None) -> str:
        """
        Generate reference.docx file from typography configuration.
        
        Args:
            output_path: Path to save reference file (creates temp file if None)
            
        Returns:
            Path to generated reference.docx file
        """
        logger.info("Generating DOCX reference file from typography configuration")
        
        # Create new document
        doc = Document()
        
        # Configure document-level settings
        self._configure_document_settings(doc)
        
        # Configure styles
        self._configure_heading_styles(doc)
        self._configure_body_styles(doc)
        self._configure_list_styles(doc)
        
        # Add sample content to establish styles
        self._add_sample_content(doc)
        
        # Save to file
        if output_path:
            doc.save(output_path)
            self._fix_bullet_font(output_path)
            logger.info(f"DOCX reference saved to {output_path}")
            return output_path
        else:
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(
                mode='wb',
                suffix='.docx',
                delete=False
            )
            doc.save(temp_file.name)
            temp_file.close()
            self._fix_bullet_font(temp_file.name)
            logger.info(f"DOCX reference saved to temporary file: {temp_file.name}")
            return temp_file.name

    def _fix_bullet_font(self, path: str) -> None:
        """Make list bullets render outside Microsoft Word.

        python-docx writes bullet levels as U+F0B7 in the "Symbol" font. That
        codepoint is in the Private Use Area — it means nothing without that
        specific font, which is absent from most machines that are not running
        Word on Windows. Everywhere else the bullets came out as empty boxes.

        pandoc copies numbering from the reference document, so rewriting it
        here fixes every exported CV. The bullet becomes a real U+2022 in the
        document's own body font.
        """
        import re
        import shutil
        import zipfile

        numbering = 'word/numbering.xml'
        body_font = self.typography.body_style.font_family
        body_font = getattr(body_font, 'value', body_font)

        try:
            with zipfile.ZipFile(path) as archive:
                if numbering not in archive.namelist():
                    return
                parts = {name: archive.read(name) for name in archive.namelist()}

            xml = parts[numbering].decode('utf-8')
            # The PUA codepoint, and any other Symbol-font bullet character.
            xml = xml.replace('w:val="\uf0b7"', 'w:val="\u2022"')
            xml = re.sub(
                r'<w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"([^/]*)/>',
                f'<w:rFonts w:ascii="{body_font}" w:hAnsi="{body_font}"\\1/>',
                xml,
            )
            parts[numbering] = xml.encode('utf-8')

            temp_path = f"{path}.tmp"
            with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as archive:
                for name, data in parts.items():
                    archive.writestr(name, data)
            shutil.move(temp_path, path)
            logger.info("Rewrote DOCX bullet numbering to use %s", body_font)

        except Exception as exc:
            # A cosmetic fix must never cost the export.
            logger.warning(f"Could not rewrite DOCX bullet numbering: {exc}")
    
    def _configure_document_settings(self, doc: Document):
        """Configure document-level settings like margins."""
        sections = doc.sections
        for section in sections:
            # Set margins from typography config
            margins = self.typography.page_margins
            section.top_margin = Inches(margins.get('top', 0.75))
            section.bottom_margin = Inches(margins.get('bottom', 0.75))
            section.left_margin = Inches(margins.get('left', 0.75))
            section.right_margin = Inches(margins.get('right', 0.75))
    
    def _configure_heading_styles(self, doc: Document):
        """Configure heading styles (H1, H2, H3)."""
        styles = doc.styles
        
        # Pandoc maps markdown headings as follows:
        # # Heading → Heading 1
        # ## Heading → Heading 2  
        # ### Heading → Heading 3
        
        # Configure Heading 1 style (used for # - the name)
        self._configure_style(
            styles['Heading 1'],
            self.typography.h1_style,
            'h1_style'
        )
        
        # Configure Heading 2 style (used for ## - section headings)
        self._configure_style(
            styles['Heading 2'],
            self.typography.h2_style,
            'h2_style'
        )
        
        # Configure Heading 3 style (used for ### - subsection headings)
        self._configure_style(
            styles['Heading 3'],
            self.typography.h3_style,
            'h3_style'
        )
    
    def _configure_body_styles(self, doc: Document):
        """Configure body text styles."""
        styles = doc.styles
        
        # Configure Normal style (body text)
        self._configure_style(
            styles['Normal'],
            self.typography.body_style,
            'body_style'
        )
        
        # Configure paragraph spacing
        normal_style = styles['Normal']
        normal_style.paragraph_format.space_after = Pt(self.typography.paragraph_spacing)
        normal_style.paragraph_format.space_before = Pt(0)
        
        # Configure Subtitle style for contact information
        # This will be used for the line right after the name
        try:
            subtitle_style = styles['Subtitle']
            self._configure_style(
                subtitle_style,
                self.typography.contact_style,
                'contact_style'
            )
        except KeyError:
            logger.warning("Subtitle style not found, contact info will use Normal style")
    
    def _configure_list_styles(self, doc: Document):
        """Configure list styles."""
        styles = doc.styles
        
        # Configure List Paragraph style
        try:
            list_style = styles['List Paragraph']
            self._configure_style(
                list_style,
                self.typography.body_style,
                'body_style'
            )
        except KeyError:
            logger.warning("List Paragraph style not found, skipping")
    
    def _configure_style(self, style, typography_style: TypographyStyle, style_name: str):
        """
        Apply typography settings to a DOCX style.
        
        Args:
            style: DOCX style object
            typography_style: Typography style configuration
            style_name: Name of the style for logging
        """
        try:
            # Font settings
            font = style.font
            font_name = self.FONT_MAPPING.get(
                typography_style.font_family,
                "Arial"
            )
            font.name = font_name
            font.size = Pt(typography_style.font_size)
            
            # Font weight
            if typography_style.font_weight == FontWeight.BOLD:
                font.bold = True
            else:
                font.bold = False
            
            # Font style
            if typography_style.font_style == FontStyle.ITALIC:
                font.italic = True
            else:
                font.italic = False
            
            # Color
            color = typography_style.color
            font.color.rgb = RGBColor(color.r, color.g, color.b)
            
            # Paragraph alignment
            paragraph_format = style.paragraph_format
            alignment_map = {
                TextAlignment.LEFT: WD_ALIGN_PARAGRAPH.LEFT,
                TextAlignment.CENTER: WD_ALIGN_PARAGRAPH.CENTER,
                TextAlignment.RIGHT: WD_ALIGN_PARAGRAPH.RIGHT,
                TextAlignment.JUSTIFY: WD_ALIGN_PARAGRAPH.JUSTIFY
            }
            paragraph_format.alignment = alignment_map.get(
                typography_style.alignment,
                WD_ALIGN_PARAGRAPH.LEFT
            )
            
            # Line spacing
            paragraph_format.line_spacing = typography_style.line_height
            
            logger.debug(f"Configured style {style_name}: {font_name}, {typography_style.font_size}pt")
            
        except Exception as e:
            logger.error(f"Failed to configure style {style_name}: {e}")
    
    def _add_sample_content(self, doc: Document):
        """
        Add sample content to establish styles in the reference document.
        
        Pandoc uses the styles from the reference document, so we need
        to have at least one instance of each style.
        """
        # Add title (H1)
        doc.add_heading('Sample Name', level=0)  # Level 0 = Title style
        
        # Add contact info as normal paragraph
        contact = doc.add_paragraph('email@example.com | (555) 123-4567 | City, State')
        contact.style = 'Normal'
        
        # Add section heading (H2)
        doc.add_heading('Experience', level=1)
        
        # Add subsection heading (H3)
        doc.add_heading('Job Title', level=2)
        
        # Add body text
        doc.add_paragraph('Company Name | Location')
        doc.add_paragraph('January 2020 - Present')
        
        # Add bullet list
        doc.add_paragraph('Achievement or responsibility', style='List Bullet')
        doc.add_paragraph('Another achievement', style='List Bullet')
        
        # Add another section
        doc.add_heading('Education', level=1)
        doc.add_heading('Degree Name', level=2)
        doc.add_paragraph('University Name | Location')
        
        # Add skills section
        doc.add_heading('Skills', level=1)
        doc.add_paragraph('Skill 1, Skill 2, Skill 3')


def generate_docx_reference(typography: Optional[TypographyConfig] = None, output_path: Optional[str] = None) -> str:
    """
    Convenience function to generate DOCX reference file.
    
    Args:
        typography: Typography configuration (uses defaults if None)
        output_path: Path to save reference file (creates temp file if None)
        
    Returns:
        Path to generated reference.docx file
    """
    generator = DOCXReferenceGenerator(typography)
    return generator.generate_reference(output_path)
