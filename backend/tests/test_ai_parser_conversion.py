"""Turning parsed sections into CV data.

An import reported four parsed sections — personal_info, summary, skills and
experience — but produced a CV containing only personal info and skills. Two
faults in the conversion threw the rest away without saying so.
"""

import asyncio

import pytest

from app.llm.ai_parser import AIParser
from app.models.llm_models import ParsedSection


def _section(section_type, content, confidence=0.9):
    return ParsedSection(
        section_type=section_type, content=content, confidence=confidence, raw_text=""
    )


def _convert(sections):
    parser = AIParser.__new__(AIParser)
    parser._conversion_notes = []
    return asyncio.run(parser._convert_to_cv_data(sections)), parser._conversion_notes


class TestSummary:
    def test_the_summary_key_is_read(self):
        """The parser returns the text under 'summary'; only 'text' and 'raw'
        were read, so the summary silently vanished."""
        data, _ = _convert([_section("summary", {"summary": "A data leader.", "title": "x"})])
        assert data["summary"] == "A data leader."

    def test_the_older_text_key_still_works(self):
        data, _ = _convert([_section("summary", {"text": "From text."})])
        assert data["summary"] == "From text."

    def test_an_empty_summary_is_not_an_error(self):
        data, _ = _convert([_section("summary", {})])
        assert data["summary"] == ""


class TestExperience:
    def test_an_entry_without_dates_is_kept(self):
        """Requiring company and start_date discarded whole jobs whenever the
        model could not read a date — routine for a PDF."""
        data, _ = _convert([_section("experience", {"entries": [{"title": "Head of Data"}]})])
        assert len(data["experience"]) == 1
        assert data["experience"][0]["title"] == "Head of Data"

    def test_an_entry_without_a_company_is_kept(self):
        data, _ = _convert(
            [_section("experience", {"entries": [{"title": "Consultant", "start_date": "2020"}]})]
        )
        assert len(data["experience"]) == 1

    def test_an_entry_with_no_title_is_dropped_and_reported(self):
        data, notes = _convert(
            [_section("experience", {"entries": [{"company": "Acme"}, {"title": "Lead"}]})]
        )
        assert len(data["experience"]) == 1
        assert notes and "title" in notes[0]

    def test_a_full_entry_survives_intact(self):
        entry = {
            "title": "Lead",
            "company": "Acme",
            "start_date": "2020",
            "achievements": ["Shipped it"],
        }
        data, _ = _convert([_section("experience", {"entries": [entry]})])
        assert data["experience"][0]["achievements"] == ["Shipped it"]


class TestEducation:
    def test_a_complete_entry_is_kept(self):
        data, _ = _convert(
            [_section("education", {"entries": [{"degree": "BSc", "institution": "UCL"}]})]
        )
        assert len(data["education"]) == 1

    def test_an_incomplete_entry_is_reported(self):
        """Education genuinely requires both fields on the model, so dropping
        is correct here — but it must be visible."""
        data, notes = _convert([_section("education", {"entries": [{"degree": "BSc"}]})])
        assert data["education"] == []
        assert notes and "education" in notes[0]


class TestTheReportedCase:
    def test_all_four_sections_survive_conversion(self):
        data, _ = _convert(
            [
                _section("personal_info", {"name": "Antony", "email": "a@example.com"}),
                _section("summary", {"summary": "Experienced engineer."}),
                _section("skills", {"categories": [{"name": "Tech", "skills": ["SQL"]}]}),
                _section("experience", {"entries": [{"title": "Engineer"}]}, confidence=0.3),
            ]
        )
        assert data["personal_info"]["name"] == "Antony"
        assert data["summary"] == "Experienced engineer."
        assert data["experience"], "work history must not be dropped"
        assert data["skills"]["categories"]


class TestContentLimits:
    """Both prompts truncated the document far below CV length.

    Identification saw 3000 characters, which on a real CV ends around the
    first job — so education, skills and certifications, which sit at the end,
    were never identified. Section parsing saw 1500, so a work history with
    four roles yielded one.
    """

    def test_identification_covers_a_whole_cv(self):
        assert AIParser.MAX_IDENTIFICATION_CHARS >= 20_000

    def test_a_section_is_not_cut_to_a_single_entry(self):
        assert AIParser.MAX_SECTION_CHARS >= 8_000

    def test_a_long_cv_is_not_truncated_by_identification(self):
        parser = AIParser.__new__(AIParser)
        # A 10k CV with its skills section at the very end.
        document = ("Experience filler line.\n" * 400) + "\nSkills\nSQL, Python\n"
        assert len(document) > 3_000
        prompt = parser._create_section_identification_prompt(document)
        assert "Skills" in prompt, "the end of the CV must reach the model"

    def test_a_long_section_keeps_its_later_entries(self):
        parser = AIParser.__new__(AIParser)
        section = ("Role line filler.\n" * 300) + "\nFinal Job Title\n"
        assert len(section) > 1_500
        prompt = parser._create_section_parsing_prompt("experience", section)
        assert "Final Job Title" in prompt
