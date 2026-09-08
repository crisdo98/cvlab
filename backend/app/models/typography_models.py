"""
Typography Models

Models for CV typography configuration including fonts, colors, styles, and templates.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class FontFamily(str, Enum):
    """Available font families for CV."""
    LIBERATION_SANS = "Liberation Sans"
    LIBERATION_SERIF = "Liberation Serif"
    TIMES_NEW_ROMAN = "Times New Roman"
    ARIAL = "Arial"
    HELVETICA = "Helvetica"
    GEORGIA = "Georgia"
    PALATINO = "Palatino"
    COURIER = "Courier"


class TextAlignment(str, Enum):
    """Text alignment options."""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"


class FontWeight(str, Enum):
    """Font weight options."""
    NORMAL = "normal"
    BOLD = "bold"
    LIGHT = "light"


class FontStyle(str, Enum):
    """Font style options."""
    NORMAL = "normal"
    ITALIC = "italic"


class ColorFormat(BaseModel):
    """RGB color format."""
    r: int = Field(..., ge=0, le=255, description="Red component (0-255)")
    g: int = Field(..., ge=0, le=255, description="Green component (0-255)")
    b: int = Field(..., ge=0, le=255, description="Blue component (0-255)")
    
    def to_hex(self) -> str:
        """Convert to hex color string."""
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"
    
    def to_latex_rgb(self) -> str:
        """Convert to LaTeX RGB format (0-1 range)."""
        return f"{self.r/255:.3f},{self.g/255:.3f},{self.b/255:.3f}"
    
    @classmethod
    def from_hex(cls, hex_color: str) -> "ColorFormat":
        """Create from hex color string."""
        hex_color = hex_color.lstrip('#')
        return cls(
            r=int(hex_color[0:2], 16),
            g=int(hex_color[2:4], 16),
            b=int(hex_color[4:6], 16)
        )


class TypographyStyle(BaseModel):
    """Typography style for a specific element."""
    font_family: FontFamily = Field(default=FontFamily.LIBERATION_SANS)
    font_size: int = Field(default=11, ge=8, le=32, description="Font size in points")
    font_weight: FontWeight = Field(default=FontWeight.NORMAL)
    font_style: FontStyle = Field(default=FontStyle.NORMAL)
    color: ColorFormat = Field(default_factory=lambda: ColorFormat(r=0, g=0, b=0))
    line_height: float = Field(default=1.5, ge=1.0, le=3.0, description="Line height multiplier")
    alignment: TextAlignment = Field(default=TextAlignment.JUSTIFY)


class TypographyConfig(BaseModel):
    """Complete typography configuration for a CV."""
    # Document-level settings
    page_margins: Dict[str, float] = Field(
        default_factory=lambda: {"top": 0.75, "bottom": 0.75, "left": 0.75, "right": 0.75},
        description="Page margins in inches"
    )
    
    # Element-specific typography
    h1_style: TypographyStyle = Field(
        default_factory=lambda: TypographyStyle(
            font_size=24,
            font_weight=FontWeight.BOLD,
            alignment=TextAlignment.CENTER
        ),
        description="Style for main heading (name)"
    )
    
    h2_style: TypographyStyle = Field(
        default_factory=lambda: TypographyStyle(
            font_size=18,
            font_weight=FontWeight.BOLD,
            alignment=TextAlignment.LEFT
        ),
        description="Style for section headings"
    )
    
    h3_style: TypographyStyle = Field(
        default_factory=lambda: TypographyStyle(
            font_size=14,
            font_weight=FontWeight.BOLD,
            alignment=TextAlignment.LEFT
        ),
        description="Style for subsection headings (job titles, degrees)"
    )
    
    body_style: TypographyStyle = Field(
        default_factory=lambda: TypographyStyle(
            font_size=11,
            font_weight=FontWeight.NORMAL,
            alignment=TextAlignment.JUSTIFY
        ),
        description="Style for body text"
    )
    
    contact_style: TypographyStyle = Field(
        default_factory=lambda: TypographyStyle(
            font_size=10,
            font_weight=FontWeight.NORMAL,
            alignment=TextAlignment.CENTER,
            color=ColorFormat(r=60, g=60, b=60)
        ),
        description="Style for contact information"
    )
    
    # Additional settings
    section_spacing: float = Field(default=8.0, ge=0, le=24, description="Spacing before sections (pt)")
    paragraph_spacing: float = Field(default=6.0, ge=0, le=12, description="Spacing between paragraphs (pt)")
    bullet_style: str = Field(default="•", description="Bullet point character")


class TypographyTemplate(BaseModel):
    """Predefined typography template."""
    id: str = Field(..., description="Unique template identifier")
    name: str = Field(..., description="Template display name")
    description: str = Field(..., description="Template description")
    preview_image: Optional[str] = Field(None, description="URL to preview image")
    typography: TypographyConfig = Field(..., description="Typography configuration")
    tags: List[str] = Field(default_factory=list, description="Template tags for filtering")


class TypographyTemplateListResponse(BaseModel):
    """Response for listing typography templates."""
    templates: List[TypographyTemplate]
    total: int


class TypographyUpdateRequest(BaseModel):
    """Request to update CV typography."""
    cv_id: str = Field(..., description="CV ID to update")
    typography: TypographyConfig = Field(..., description="New typography configuration")


class TypographyResponse(BaseModel):
    """Response for typography operations."""
    cv_id: str
    typography: TypographyConfig
    message: Optional[str] = None


# Predefined templates
TYPOGRAPHY_TEMPLATES = {
    "classic": TypographyTemplate(
        id="classic",
        name="Classic Professional",
        description="Traditional serif font with formal styling",
        typography=TypographyConfig(
            h1_style=TypographyStyle(
                font_family=FontFamily.TIMES_NEW_ROMAN,
                font_size=24,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.CENTER
            ),
            h2_style=TypographyStyle(
                font_family=FontFamily.TIMES_NEW_ROMAN,
                font_size=16,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.LEFT
            ),
            h3_style=TypographyStyle(
                font_family=FontFamily.TIMES_NEW_ROMAN,
                font_size=12,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.LEFT
            ),
            body_style=TypographyStyle(
                font_family=FontFamily.TIMES_NEW_ROMAN,
                font_size=11,
                alignment=TextAlignment.JUSTIFY
            ),
            contact_style=TypographyStyle(
                font_family=FontFamily.TIMES_NEW_ROMAN,
                font_size=10,
                alignment=TextAlignment.CENTER
            )
        ),
        tags=["professional", "traditional", "serif"]
    ),
    "modern": TypographyTemplate(
        id="modern",
        name="Modern Clean",
        description="Clean sans-serif design with contemporary feel",
        typography=TypographyConfig(
            h1_style=TypographyStyle(
                font_family=FontFamily.HELVETICA,
                font_size=26,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.LEFT,
                color=ColorFormat(r=30, g=30, b=30)
            ),
            h2_style=TypographyStyle(
                font_family=FontFamily.HELVETICA,
                font_size=18,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.LEFT,
                color=ColorFormat(r=0, g=102, b=204)
            ),
            h3_style=TypographyStyle(
                font_family=FontFamily.HELVETICA,
                font_size=13,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.LEFT
            ),
            body_style=TypographyStyle(
                font_family=FontFamily.HELVETICA,
                font_size=11,
                alignment=TextAlignment.LEFT,
                line_height=1.4
            ),
            contact_style=TypographyStyle(
                font_family=FontFamily.HELVETICA,
                font_size=10,
                alignment=TextAlignment.LEFT,
                color=ColorFormat(r=80, g=80, b=80)
            )
        ),
        tags=["modern", "clean", "sans-serif", "colorful"]
    ),
    "minimal": TypographyTemplate(
        id="minimal",
        name="Minimal Elegant",
        description="Minimalist design with subtle elegance",
        typography=TypographyConfig(
            page_margins={"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},
            h1_style=TypographyStyle(
                font_family=FontFamily.GEORGIA,
                font_size=22,
                font_weight=FontWeight.NORMAL,
                alignment=TextAlignment.LEFT,
                line_height=1.2
            ),
            h2_style=TypographyStyle(
                font_family=FontFamily.GEORGIA,
                font_size=14,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.LEFT,
                font_style=FontStyle.ITALIC
            ),
            h3_style=TypographyStyle(
                font_family=FontFamily.GEORGIA,
                font_size=12,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.LEFT
            ),
            body_style=TypographyStyle(
                font_family=FontFamily.GEORGIA,
                font_size=10,
                alignment=TextAlignment.LEFT,
                line_height=1.6
            ),
            contact_style=TypographyStyle(
                font_family=FontFamily.GEORGIA,
                font_size=9,
                alignment=TextAlignment.LEFT,
                color=ColorFormat(r=100, g=100, b=100)
            ),
            section_spacing=12.0,
            paragraph_spacing=4.0
        ),
        tags=["minimal", "elegant", "serif", "spacious"]
    ),
    "tech": TypographyTemplate(
        id="tech",
        name="Tech Industry",
        description="Modern design optimized for tech roles",
        typography=TypographyConfig(
            h1_style=TypographyStyle(
                font_family=FontFamily.LIBERATION_SANS,
                font_size=28,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.LEFT,
                color=ColorFormat(r=0, g=0, b=0)
            ),
            h2_style=TypographyStyle(
                font_family=FontFamily.LIBERATION_SANS,
                font_size=16,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.LEFT,
                color=ColorFormat(r=51, g=51, b=51)
            ),
            h3_style=TypographyStyle(
                font_family=FontFamily.LIBERATION_SANS,
                font_size=12,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.LEFT
            ),
            body_style=TypographyStyle(
                font_family=FontFamily.LIBERATION_SANS,
                font_size=10,
                alignment=TextAlignment.LEFT,
                line_height=1.5
            ),
            contact_style=TypographyStyle(
                font_family=FontFamily.COURIER,
                font_size=9,
                alignment=TextAlignment.LEFT,
                color=ColorFormat(r=70, g=70, b=70)
            ),
            # A round bullet, like every other template. "▸" is not in the
            # Liberation faces these templates use, so it exported as an empty
            # box until the exporter learned to substitute a maths symbol —
            # and even then it was a triangle nobody had chosen.
            bullet_style="•"
        ),
        tags=["tech", "modern", "sans-serif", "developer"]
    )
}
