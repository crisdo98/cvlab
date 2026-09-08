"""YAML frontmatter written ahead of the CV markdown.

pandoc turns title/author/date metadata into a title block. In DOCX that is a
large gap, the name repeated, and the Title style's bottom border showing as a
stray horizontal rule. The LaTeX template ignores the same metadata, which is
why the PDF never showed it and the two formats disagreed.
"""

import re

import pytest

from app.models.cv_models import CVModelV2
from app.services.export_service import ExportService


def _cv():
    return CVModelV2(
        sections=[
            {
                "type": "personal_info",
                "title": "Personal Information",
                "order": 0,
                "content": {
                    "content_type": "personal",
                    "full_name": "Ada Lovelace",
                    "email": "ada@example.com",
                    "phone": "07000 000000",
                },
            },
            {
                "type": "summary",
                "title": "Professional Summary",
                "order": 1,
                "content": {"content_type": "free_text", "text": "A data leader."},
            },
        ]
    )


@pytest.fixture
def markdown():
    # __new__ because the constructor checks for pandoc, which the markdown
    # generation under test does not use.
    service = ExportService.__new__(ExportService)
    return service._json_to_markdown_v2(_cv())


def _frontmatter(markdown: str) -> str:
    match = re.match(r"^---\n(.*?)\n---", markdown, re.S)
    return match.group(1) if match else ""


class TestNoTitleBlock:
    def test_no_title_metadata(self, markdown):
        assert "title:" not in _frontmatter(markdown)

    def test_no_author_metadata(self, markdown):
        assert "author:" not in _frontmatter(markdown)

    def test_no_date_metadata(self, markdown):
        """A date in the metadata prints above the CV in Word."""
        assert "date:" not in _frontmatter(markdown)


class TestContentIsUnaffected:
    def test_the_name_is_still_in_the_body(self, markdown):
        assert "Ada Lovelace" in markdown

    def test_contact_details_survive(self, markdown):
        frontmatter = _frontmatter(markdown)
        assert "ada@example.com" in frontmatter or "ada@example.com" in markdown

    def test_language_is_kept(self, markdown):
        assert "lang: en-US" in _frontmatter(markdown)

    def test_sections_are_rendered(self, markdown):
        assert "Professional Summary" in markdown
        assert "A data leader." in markdown


class TestDocxTitleBlockStripping:
    """pandoc emits Title, Author and Date paragraphs whether or not the
    document has that metadata. Empty, they are a large gap at the top of the
    CV in Word plus a stray horizontal rule from the Title style's border.
    """

    def _service(self):
        return ExportService.__new__(ExportService)

    def _docx(self, tmp_path, document_xml: str):
        import zipfile

        path = tmp_path / "cv.docx"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("word/document.xml", document_xml)
            archive.writestr("word/styles.xml", "<styles/>")
        return str(path)

    def _read(self, path):
        import zipfile

        return zipfile.ZipFile(path).read("word/document.xml").decode()

    def test_empty_title_paragraphs_are_removed(self, tmp_path):
        xml = (
            '<w:document><w:body>'
            '<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr></w:p>'
            '<w:p><w:pPr><w:pStyle w:val="Author"/></w:pPr></w:p>'
            '<w:p><w:pPr><w:pStyle w:val="Date"/></w:pPr></w:p>'
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Ada</w:t></w:r></w:p>'
            '</w:body></w:document>'
        )
        path = self._docx(tmp_path, xml)
        self._service()._strip_docx_title_block(path)

        out = self._read(path)
        assert 'w:val="Title"' not in out
        assert 'w:val="Author"' not in out
        assert 'w:val="Date"' not in out
        assert "Ada" in out

    def test_a_title_with_text_is_kept(self, tmp_path):
        """Only empty title-block paragraphs go: a real title stays."""
        xml = (
            '<w:document><w:body>'
            '<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr><w:r><w:t>My CV</w:t></w:r></w:p>'
            '</w:body></w:document>'
        )
        path = self._docx(tmp_path, xml)
        self._service()._strip_docx_title_block(path)
        assert "My CV" in self._read(path)

    def test_body_paragraphs_are_untouched(self, tmp_path):
        xml = (
            '<w:document><w:body>'
            '<w:p><w:pPr><w:pStyle w:val="FirstParagraph"/></w:pPr><w:r><w:t>Body</w:t></w:r></w:p>'
            '<w:p></w:p>'
            '</w:body></w:document>'
        )
        path = self._docx(tmp_path, xml)
        self._service()._strip_docx_title_block(path)
        out = self._read(path)
        assert "Body" in out
        assert "<w:p></w:p>" in out, "an unstyled empty paragraph is not ours to remove"

    def test_a_missing_document_part_is_survivable(self, tmp_path):
        import zipfile

        path = tmp_path / "odd.docx"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("word/styles.xml", "<styles/>")
        # Must not raise: a cosmetic tidy-up cannot cost the export.
        self._service()._strip_docx_title_block(str(path))
