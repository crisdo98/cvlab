"""Markdown block normalisation for exports.

Descriptions are authored as Markdown but stored as typed. Emitted verbatim,
a single newline is a soft break and a list with no blank line before it is
absorbed into the preceding paragraph — which turned a structured description
into one wall of text in the PDF and DOCX.
"""

from app.services.markdown_blocks import normalise_markdown_block as norm


class TestListSeparation:
    def test_a_list_after_body_text_gets_a_blank_line(self):
        assert norm("Intro line\n- first\n- second") == "Intro line\n\n- first\n- second"

    def test_an_existing_blank_line_is_kept_as_one(self):
        assert norm("Intro\n\n\n- first") == "Intro\n\n- first"

    def test_consecutive_items_stay_together(self):
        assert norm("- one\n- two\n- three") == "- one\n- two\n- three"

    def test_numbered_lists_are_recognised(self):
        assert norm("Intro\n1. first\n2. second") == "Intro\n\n1. first\n2. second"

    def test_text_after_a_list_is_separated(self):
        """Without the blank line this reads as a continuation of the item."""
        assert norm("- item\nAfterwards") == "- item\n\nAfterwards"


class TestHardBreaks:
    def test_consecutive_text_lines_keep_their_break(self):
        # The reported case: a bold sub-heading ran into the sentence above it.
        assert norm("Sentence.\n**Heading**\n- bullet") == "Sentence.\\\n**Heading**\n\n- bullet"

    def test_a_single_line_gets_no_trailing_break(self):
        assert norm("Just one line") == "Just one line"

    def test_the_last_line_never_gets_a_break(self):
        assert norm("One\nTwo").endswith("Two")


class TestEdges:
    def test_empty_input(self):
        assert norm("") == ""
        assert norm("   \n  \n") == ""

    def test_windows_line_endings(self):
        assert norm("Intro\r\n- item") == "Intro\n\n- item"

    def test_headings_are_treated_as_blocks(self):
        assert norm("Intro\n## Heading") == "Intro\n\n## Heading"

    def test_inline_formatting_is_untouched(self):
        assert "**bold**" in norm("Text with **bold** in it")


class TestSummaryParagraphs:
    """The reported case: a Professional Summary written as several paragraphs
    exported as one block, because free-text sections were emitted verbatim
    while every other free text was normalised."""

    def test_blank_separated_paragraphs_survive(self):
        text = "First paragraph.\n\nSecond paragraph."
        assert norm(text) == "First paragraph.\n\nSecond paragraph."

    def test_single_newlines_become_hard_breaks(self):
        assert norm("Line one\nLine two") == "Line one\\\nLine two"

    def test_a_summary_with_a_list_keeps_both(self):
        text = "I lead data teams.\n\nHighlights:\n- Built a platform\n- Cut cost"
        out = norm(text)
        assert "I lead data teams." in out
        assert "\n\n- Built a platform" in out
