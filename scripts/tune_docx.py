#!/usr/bin/env python3
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_LINE_SPACING, WD_ALIGN_PARAGRAPH
import sys

# Usage: python scripts/tune_docx.py scripts/reference.docx

def set_font(style, name: str, size_pt: int):
    try:
        font = style.font
        font.name = name
        font.size = Pt(size_pt)
    except Exception:
        pass


def tune_docx(path: str):
    doc = Document(path)
    # Margins
    for section in doc.sections:
        section.top_margin = Inches(0.5)
        section.bottom_margin = Inches(0.5)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # Styles: Heading 1/2/3 and Normal
    style_specs = {
        "Heading 1": {"size": 18, "space_after": 6},
        "Heading 2": {"size": 14, "space_after": 4},
        "Heading 3": {"size": 12, "space_after": 3},
        "Normal": {"size": 11, "space_after": 6},
    }

    for style_name, spec in style_specs.items():
        try:
            style = doc.styles[style_name]
            # Font
            set_font(style, "Helvetica Neue", spec["size"])
            # Paragraph formatting
            pf = style.paragraph_format
            pf.space_before = Pt(0)
            pf.space_after = Pt(spec["space_after"])
            pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
            if style_name == "Normal":
                pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        except Exception:
            pass

    # Bullet indentation for List Paragraph
    try:
        lp = doc.styles["List Paragraph"]
        pf = lp.paragraph_format
        pf.left_indent = Inches(0.25)
        pf.space_before = Pt(0)
        pf.space_after = Pt(3)
        pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        set_font(lp, "Helvetica Neue", 11)
    except Exception:
        pass

    doc.save(path)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/tune_docx.py <path-to-docx>")
        sys.exit(1)
    tune_docx(sys.argv[1])
