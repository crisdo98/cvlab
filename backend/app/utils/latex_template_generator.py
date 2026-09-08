"""
LaTeX Template Generator

Generates dynamic LaTeX templates from typography configuration.
Converts typography settings to LaTeX commands for PDF generation.
"""

import logging
from typing import Dict, Any, Optional
from ..models.typography_models import (
    TypographyConfig,
    TypographyStyle,
    FontFamily,
    FontWeight,
    FontStyle,
    TextAlignment
)

logger = logging.getLogger(__name__)


class LaTeXTemplateGenerator:
    """
    Generates LaTeX templates from typography configuration.
    
    Converts typography settings including fonts, colors, sizes,
    alignment, and spacing into LaTeX commands.
    """
    
    # Font family mapping to LaTeX font names
    FONT_MAPPING = {
        FontFamily.LIBERATION_SANS: "Liberation Sans",
        FontFamily.LIBERATION_SERIF: "Liberation Serif",
        FontFamily.TIMES_NEW_ROMAN: "Times New Roman",
        FontFamily.ARIAL: "Arial",
        FontFamily.HELVETICA: "Nimbus Sans",  # Helvetica clone from URW fonts
        FontFamily.GEORGIA: "Georgia",
        FontFamily.PALATINO: "P052",  # Palatino clone from URW fonts
        FontFamily.COURIER: "Courier New"
    }
    
    def __init__(self, typography: Optional[TypographyConfig] = None):
        """
        Initialize generator with typography configuration.
        
        Args:
            typography: Typography configuration (uses defaults if None)
        """
        self.typography = typography or TypographyConfig()
    
    def generate_template(self) -> str:
        """
        Generate complete LaTeX template from typography configuration.
        
        Returns:
            LaTeX template string
        """
        logger.info("Generating LaTeX template from typography configuration")
        
        # Build template sections
        preamble = self._generate_preamble()
        color_definitions = self._generate_color_definitions()
        font_setup = self._generate_font_setup()
        spacing_setup = self._generate_spacing_setup()
        section_formatting = self._generate_section_formatting()
        list_formatting = self._generate_list_formatting()
        
        # Combine into complete template
        template = f"""\\documentclass[{self.typography.body_style.font_size}pt]{{article}}

{preamble}

{color_definitions}

{font_setup}

{spacing_setup}

{section_formatting}

{list_formatting}

% Disable page numbers
\\pagenumbering{{gobble}}

% Disable section numbering completely
\\setcounter{{secnumdepth}}{{0}}

\\begin{{document}}
{self._get_alignment_command(self.typography.body_style.alignment)}
% ragged2e restores the document's default first-line indent whenever it sets a
% justification mode, so the indent is cleared again here rather than only in
% the preamble. Without this the PDF indented paragraphs the preview did not.
\\setlength{{\\parindent}}{{0pt}}

% Body colour. It was defined but never selected, so body text always came out
% black however it was configured — while the preview and the DOCX honoured it.
\\color{{bodycolor}}
$body$
\\end{{document}}
"""
        
        logger.info("LaTeX template generated successfully")
        return template
    
    def _generate_preamble(self) -> str:
        """Generate LaTeX preamble with required packages."""
        margins = self.typography.page_margins
        
        return f"""% Packages
\\usepackage[margin={margins.get('top', 0.75)}in,top={margins.get('top', 0.75)}in,bottom={margins.get('bottom', 0.75)}in,left={margins.get('left', 0.75)}in,right={margins.get('right', 0.75)}in]{{geometry}}
\\usepackage{{titlesec}}
\\usepackage{{enumitem}}
\\usepackage{{hyperref}}
\\usepackage{{fontspec}}
\\usepackage{{setspace}}
\\usepackage{{amssymb}}
\\usepackage{{ragged2e}}
\\usepackage{{xcolor}}

% Tables. Pandoc renders any pipe table as a longtable with booktabs rules, so
% without these a CV — or an appended assessment — containing a single table
% fails the whole PDF build with "Environment longtable undefined".
\\usepackage{{longtable}}
\\usepackage{{booktabs}}
\\usepackage{{array}}
\\usepackage{{calc}}

% Define tightlist for Pandoc
\\providecommand{{\\tightlist}}{{%
  \\setlength{{\\itemsep}}{{0pt}}%
  \\setlength{{\\parskip}}{{0pt}}%
}}"""
    
    #: Bullet characters mapped to LaTeX that renders in any font.
    #:
    #: The text fonts CVs use are ordinary Latin faces: Liberation Sans has no
    #: U+25B8, so a template whose bullet was "▸" produced an empty box on
    #: every list item. These map to math symbols, which come from the maths
    #: font and are always present.
    #: `\ensuremath` rather than `$...$`: this file is a *pandoc* template,
    #: where `$` delimits a variable, so a maths dollar breaks the template
    #: parser before LaTeX ever sees it.
    BULLET_COMMANDS = {
        "•": r"\textbullet",
        "▪": r"\ensuremath{\blacksquare}",
        "■": r"\ensuremath{\blacksquare}",
        "▫": r"\ensuremath{\square}",
        "□": r"\ensuremath{\square}",
        "▸": r"\ensuremath{\blacktriangleright}",
        "►": r"\ensuremath{\blacktriangleright}",
        "▶": r"\ensuremath{\blacktriangleright}",
        "‣": r"\ensuremath{\blacktriangleright}",
        "◦": r"\ensuremath{\circ}",
        "○": r"\ensuremath{\circ}",
        "●": r"\ensuremath{\bullet}",
        "–": r"\textendash",
        "—": r"\textemdash",
        "-": "-",
        "*": r"\ensuremath{\ast}",
    }

    @classmethod
    def _latex_bullet(cls, bullet: str) -> str:
        """Return LaTeX for a bullet character.

        An unmapped character is passed through: it may well be in the font,
        and silently replacing it would be worse than letting the author see
        their own choice.
        """
        if not bullet:
            return cls.BULLET_COMMANDS["•"]
        return cls.BULLET_COMMANDS.get(bullet.strip(), bullet)

    def _generate_color_definitions(self) -> str:
        """Generate color definitions for all typography elements."""
        colors = []
        
        # Define colors for each element
        elements = [
            ('h1color', self.typography.h1_style.color),
            ('h2color', self.typography.h2_style.color),
            ('h3color', self.typography.h3_style.color),
            ('bodycolor', self.typography.body_style.color),
            ('contactcolor', self.typography.contact_style.color)
        ]
        
        for name, color in elements:
            rgb = color.to_latex_rgb()
            colors.append(f"\\definecolor{{{name}}}{{RGB}}{{{color.r},{color.g},{color.b}}}")
        
        return "% Color definitions\n" + "\n".join(colors)
    
    def _generate_font_setup(self) -> str:
        """Generate font setup commands."""
        main_font = self.FONT_MAPPING.get(
            self.typography.body_style.font_family,
            "Liberation Sans"
        )
        
        return f"""% Font setup
\\setmainfont{{{main_font}}}
\\setsansfont{{{main_font}}}
\\setmonofont{{Courier}}"""
    
    def _generate_spacing_setup(self) -> str:
        """Generate spacing setup commands."""
        line_height = self.typography.body_style.line_height
        para_spacing = self.typography.paragraph_spacing
        
        # Use the configured ratio directly rather than snapping to single,
        # onehalf or double spacing. Bucketing turned a 1.4 line height into
        # 1.5 and a 1.2 into 1.0, so the PDF never matched the preview, which
        # applies the number as given.
        #
        # LaTeX's baseline at \\setstretch{1} is already about 1.2x the font
        # size, which is what a CSS line-height of 1.2 means, so the ratio is
        # divided by 1.2 to express the same spacing.
        stretch = max(0.5, round(line_height / 1.2, 3))

        return f"""% Global spacing
\\setstretch{{{stretch}}}
\\setlength{{\\parskip}}{{{para_spacing}pt}}

% No first-line indent. This comes after the alignment setup because ragged2e
% restores the document default indent when it sets a justification mode.
\\setlength{{\\parindent}}{{0pt}}

% Never hyphenate. LaTeX breaks words to justify a line and CSS does not, so
% the same paragraph wrapped differently in the PDF and in the preview.
\\hyphenpenalty=10000
\\exhyphenpenalty=10000
\\tolerance=2000
\\emergencystretch=3em"""
    
    def _generate_section_formatting(self) -> str:
        """Generate section and heading formatting."""
        sections = []
        
        # Define helper macros for alignment
        sections.append(r"""% Helper macros for title alignment
\newcommand{\titlecenter}[1]{\centering#1}
\newcommand{\titleleft}[1]{\raggedright#1}
\newcommand{\titleright}[1]{\raggedleft#1}
\newcommand{\titlejustify}[1]{\justifying#1}""")
        
        # Define contact info command with contact style
        contact_align = self._get_alignment_command(self.typography.contact_style.alignment)
        contact_size = self.typography.contact_style.font_size
        sections.append(f"""
% Contact info command
\\newcommand{{\\contactinfo}}[1]{{{{
  {contact_align}
  \\fontsize{{{contact_size}}}{{{contact_size * 1.2}}}\\selectfont
  \\color{{contactcolor}}
  #1
  \\par
}}}}""")
        
        # H1 formatting (for name/title - using \section)
        h1_format = self._build_title_format(self.typography.h1_style, 'h1color')
        h1_align_macro = self._get_alignment_macro(self.typography.h1_style.alignment)
        h1_template = r"""\titleformat{\section}
  [block]
  {%s}
  {}
  {0pt}
  {%s}
\titlespacing*{\section}{0pt}{%spt}{4pt}""" % (h1_format, h1_align_macro, self.typography.section_spacing)
        sections.append(f"% H1 (Section) styling\n{h1_template}")
        
        # H2 formatting (for section headings - using \subsection)
        h2_format = self._build_title_format(self.typography.h2_style, 'h2color')
        h2_align_macro = self._get_alignment_macro(self.typography.h2_style.alignment)
        h2_template = r"""\titleformat{\subsection}
  [block]
  {%s}
  {}
  {0pt}
  {%s}
\titlespacing*{\subsection}{0pt}{6pt}{3pt}""" % (h2_format, h2_align_macro)
        sections.append(f"% H2 (Subsection) styling\n{h2_template}")
        
        # H3 formatting (for job titles, degrees - using \subsubsection)
        h3_format = self._build_title_format(self.typography.h3_style, 'h3color')
        h3_align_macro = self._get_alignment_macro(self.typography.h3_style.alignment)
        h3_template = r"""\titleformat{\subsubsection}
  [block]
  {%s}
  {}
  {0pt}
  {%s}
\titlespacing*{\subsubsection}{0pt}{4pt}{2pt}""" % (h3_format, h3_align_macro)
        sections.append(f"% H3 (Subsubsection) styling\n{h3_template}")
        
        return "\n\n".join(sections)
    
    def _get_alignment_macro(self, alignment: TextAlignment) -> str:
        """
        Get LaTeX macro name for alignment.
        
        Args:
            alignment: Text alignment
            
        Returns:
            LaTeX macro name (e.g., \\titlecenter)
        """
        alignment_map = {
            TextAlignment.LEFT: r"\titleleft",
            TextAlignment.CENTER: r"\titlecenter",
            TextAlignment.RIGHT: r"\titleright",
            TextAlignment.JUSTIFY: r"\titlejustify"
        }
        return alignment_map.get(alignment, r"\titleleft")
    
    def _build_title_format(self, style: TypographyStyle, color_name: str) -> str:
        """
        Build LaTeX title format string from typography style.
        
        Args:
            style: Typography style
            color_name: Name of defined color
            
        Returns:
            LaTeX format string
        """
        parts = []
        
        # Color
        parts.append(f"\\color{{{color_name}}}")
        
        # Font size
        parts.append(f"\\fontsize{{{style.font_size}}}{{{style.font_size * style.line_height}}}\\selectfont")
        
        # Font weight
        if style.font_weight == FontWeight.BOLD:
            parts.append("\\bfseries")
        elif style.font_weight == FontWeight.LIGHT:
            parts.append("\\mdseries")
        
        # Font style
        if style.font_style == FontStyle.ITALIC:
            parts.append("\\itshape")
        
        # Font family (if different from main)
        font_name = self.FONT_MAPPING.get(style.font_family)
        if font_name and font_name != self.FONT_MAPPING.get(self.typography.body_style.font_family):
            parts.append(f"\\fontspec{{{font_name}}}")
        
        return "".join(parts)
    
    def _generate_list_formatting(self) -> str:
        """Generate list formatting commands."""
        bullet = self._latex_bullet(self.typography.bullet_style)
        
        return f"""% List styling
\\setlist{{nosep}}
\\setlist[itemize]{{label={bullet}, leftmargin=*}}
\\setlist[enumerate]{{label={bullet}, leftmargin=*}}"""
    
    def _get_alignment_command(self, alignment: TextAlignment) -> str:
        """
        Get LaTeX alignment command.
        
        Args:
            alignment: Text alignment
            
        Returns:
            LaTeX alignment command
        """
        alignment_map = {
            TextAlignment.LEFT: "\\raggedright",
            TextAlignment.CENTER: "\\centering",
            TextAlignment.RIGHT: "\\raggedleft",
            TextAlignment.JUSTIFY: "\\justifying"
        }
        return alignment_map.get(alignment, "\\justifying")
    
    def save_template(self, output_path: str) -> None:
        """
        Generate and save template to file.
        
        Args:
            output_path: Path to save template file
        """
        template = self.generate_template()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(template)
        
        logger.info(f"LaTeX template saved to {output_path}")


def generate_latex_template(typography: Optional[TypographyConfig] = None) -> str:
    """
    Convenience function to generate LaTeX template.
    
    Args:
        typography: Typography configuration (uses defaults if None)
        
    Returns:
        LaTeX template string
    """
    generator = LaTeXTemplateGenerator(typography)
    return generator.generate_template()
