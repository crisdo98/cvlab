"""Base64 file extraction used by AI import.

The AI import dialog sends PDF and DOCX as base64 because reading those in the
browser with file.text() yields mojibake. These cover the routing that turns
those bytes back into text.
"""

import base64
import glob

import pytest

from app.utils.file_extraction import extract_text_from_base64, is_base64


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


class TestTextFormats:
    def test_plain_text_round_trips(self):
        assert "Hello CV" in extract_text_from_base64(_b64(b"Hello CV"), "txt")

    def test_markdown_is_treated_as_text(self):
        out = extract_text_from_base64(_b64(b"# Jane\n\n- bullet"), "md")
        assert "# Jane" in out
        assert "- bullet" in out

    def test_an_unknown_format_falls_back_to_text(self):
        assert "content" in extract_text_from_base64(_b64(b"content"), "rtf")


class TestPdf:
    """Exercised against a real PDF the app produced, when one is present."""

    @pytest.fixture
    def pdf_path(self):
        files = sorted(glob.glob("exports/pdf/*.pdf"))
        if not files:
            pytest.skip("no exported PDF available to test against")
        return files[-1]

    def test_text_is_extracted_from_a_real_pdf(self, pdf_path):
        """Asserted structurally rather than against a name: the fixture is
        whichever CV was exported last, so pinning one person's details made
        the test fail as soon as a different CV was exported."""
        text = extract_text_from_base64(_b64(open(pdf_path, "rb").read()), "pdf")
        assert len(text) > 500
        # Real prose, not a stream of control characters.
        assert sum(c.isalpha() for c in text) > len(text) * 0.5
        assert "\n" in text, "line structure should survive extraction"

    def test_a_corrupt_pdf_raises_rather_than_returning_junk(self):
        with pytest.raises(ValueError):
            extract_text_from_base64(_b64(b"not a pdf at all"), "pdf")


class TestBase64Detection:
    def test_detects_base64(self):
        assert is_base64(_b64(b"some file bytes")) is True

    def test_markdown_is_not_mistaken_for_base64(self):
        """Spaces, newlines and '#' fall outside the base64 alphabet, which is
        what keeps a pasted CV from being decoded as bytes."""
        assert is_base64("# Jane Doe\n\nHead of Data") is False

    def test_prose_with_punctuation_is_not_base64(self):
        assert is_base64("Led the team, delivered 40% growth.") is False
