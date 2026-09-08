"""Section-based CV to flat-schema adaptation.

The ATS analyser reads a flat schema that nothing in the app produces, so a
complete CV was reported as missing every section. These pin the mapping.
"""

from app.llm.ats_analyzer import ATSAnalyzer
from app.llm.cv_normalisation import flatten_cv, is_section_based


def _cv(*sections):
    return {"id": "cv-1", "sections": list(sections)}


def _section(section_type, content, visible=True):
    return {"type": section_type, "content": content, "visible": visible}


PERSONAL = _section(
    "personal_info",
    {
        "full_name": "Ada Lovelace",
        "title": "Head of Data",
        "email": "ada@example.com",
        "phone": "0700 000 0000",
        "location": "London",
    },
)
EXPERIENCE = _section(
    "experience",
    {"entries": [{"title": "Lead", "company": "Acme", "achievements": ["Shipped it"]}]},
)
EDUCATION = _section("education", {"entries": [{"degree": "BSc", "institution": "UCL"}]})
SKILLS = _section("skills", {"items": [{"text": "Python"}, {"text": "SQL"}]})


class TestFlatten:
    def test_contact_details_are_nested_where_the_analyser_looks(self):
        flat = flatten_cv(_cv(PERSONAL))
        assert flat["personal_info"]["name"] == "Ada Lovelace"
        assert flat["personal_info"]["contact"]["email"] == "ada@example.com"
        assert flat["personal_info"]["contact"]["phone"] == "0700 000 0000"

    def test_entry_sections_are_lifted_to_top_level(self):
        flat = flatten_cv(_cv(EXPERIENCE, EDUCATION))
        assert flat["experience"][0]["company"] == "Acme"
        assert flat["education"][0]["degree"] == "BSc"

    def test_summary_becomes_a_string(self):
        flat = flatten_cv(_cv(_section("summary", {"text": "A leader."})))
        assert flat["summary"] == "A leader."

    def test_skills_become_one_category(self):
        """Skills are stored uncategorised; inventing categories would trip the
        'too many categories' heuristic."""
        flat = flatten_cv(_cv(SKILLS))
        assert flat["skills"]["categories"][0]["skills"] == ["Python", "SQL"]

    def test_hidden_sections_are_left_out(self):
        """A hidden section is not exported, so an ATS would never see it."""
        hidden = _section("experience", {"entries": [{"title": "Secret"}]}, visible=False)
        assert "experience" not in flatten_cv(_cv(hidden))

    def test_an_already_flat_cv_passes_through(self):
        flat_input = {"personal_info": {"name": "Ada"}, "experience": []}
        assert flatten_cv(flat_input) == flat_input

    def test_is_section_based_distinguishes_the_two(self):
        assert is_section_based(_cv(PERSONAL)) is True
        assert is_section_based({"personal_info": {}}) is False

    def test_malformed_input_does_not_explode(self):
        assert flatten_cv({}) == {}
        assert flatten_cv({"sections": [None, "junk", {}]}) == {}


class TestFormattingIssuesRegression:
    """The reported bug: a complete CV flagged as missing everything."""

    def test_a_complete_cv_reports_no_missing_sections(self):
        analyzer = ATSAnalyzer.__new__(ATSAnalyzer)
        flat = flatten_cv(_cv(PERSONAL, EXPERIENCE, EDUCATION, SKILLS))
        assert analyzer._check_formatting_issues(flat) == []

    def test_without_flattening_everything_looks_missing(self):
        """Guards the regression itself: the raw CV is what used to be passed."""
        analyzer = ATSAnalyzer.__new__(ATSAnalyzer)
        issues = analyzer._check_formatting_issues(_cv(PERSONAL, EXPERIENCE))
        assert "Missing work experience section" in issues

    def test_a_genuinely_empty_cv_still_reports_missing_sections(self):
        analyzer = ATSAnalyzer.__new__(ATSAnalyzer)
        issues = analyzer._check_formatting_issues(flatten_cv(_cv()))
        assert "Missing work experience section" in issues
        assert "Missing email address" in issues

    def test_cv_text_extraction_sees_the_content(self):
        analyzer = ATSAnalyzer.__new__(ATSAnalyzer)
        text = analyzer._extract_cv_text(flatten_cv(_cv(PERSONAL, EXPERIENCE, SKILLS)))
        assert "Ada Lovelace" in text
        assert "Shipped it" in text
        assert "Python" in text


class TestJobSuitabilitySummary:
    """The reported bug: 'CVModelV2' object has no attribute 'personal_info'."""

    def _analyzer(self):
        from app.llm.job_suitability_analyzer import JobSuitabilityAnalyzer

        return JobSuitabilityAnalyzer.__new__(JobSuitabilityAnalyzer)

    def test_a_v2_model_no_longer_raises(self):
        from app.models.cv_models import CVModelV2

        cv = CVModelV2(
            sections=[
                {
                    "type": "personal_info",
                    "title": "Personal Information",
                    "order": 0,
                    "content": {
                        "content_type": "personal",
                        "full_name": "Ada Lovelace",
                        "title": "Head of Data",
                        "email": "ada@example.com",
                    },
                },
                {
                    "type": "experience",
                    "title": "Experience",
                    "order": 1,
                    "content": {
                        "content_type": "structured",
                        "entries": [
                            {
                                "title": "Lead",
                                "company": "Acme",
                                "achievements": ["Shipped it"],
                            }
                        ],
                    },
                },
            ]
        )

        summary = self._analyzer()._build_cv_summary(cv)
        assert "Ada Lovelace" in summary
        assert "Lead" in summary
        assert "Acme" in summary
        assert "Shipped it" in summary

    def test_a_plain_dict_still_works(self):
        summary = self._analyzer()._build_cv_summary(
            {"personal_info": {"name": "Ada", "contact": {}}, "summary": "A leader."}
        )
        assert "Ada" in summary
        assert "A leader." in summary

    def test_an_empty_cv_produces_empty_text_rather_than_raising(self):
        assert self._analyzer()._build_cv_summary({"sections": []}) == ""
