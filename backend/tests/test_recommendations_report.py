"""The assessment appendix appended to a recommendations export."""

from datetime import datetime

from app.services.recommendations_report import build_report


ATS = {
    "summary": "Reads clearly for an ATS.",
    "compatibility_score": {
        "overall_score": 81.3,
        "keyword_score": 46.7,
        "formatting_score": 100.0,
        "structure_score": 90.0,
        "completeness_score": 100.0,
    },
    "present_keywords": ["airflow", "dbt"],
    "missing_keywords": ["sql", "snowflake"],
    "formatting_issues": ["Missing phone number"],
    "recommendations": [
        {
            "category": "Keywords",
            "issue": "Missing 19 industry-standard keywords",
            "suggestion": "Incorporate the relevant terms",
            "impact": "Improves ATS matching",
            "priority": "high",
        },
        {
            "category": "Polish",
            "issue": "Tighten the summary",
            "suggestion": "Cut to three sentences",
            "impact": "Reads faster",
            "priority": "low",
        },
    ],
}

GRAMMAR = {
    "overall_quality": 88,
    "issues": [
        {
            "type": "Passive voice",
            "location": "Experience",
            "issue_text": "was responsible for delivery",
            "correction": "delivered",
            "explanation": "Active voice reads stronger.",
            "severity": "medium",
        }
    ],
}

SUITABILITY = {
    "job_title": "Head of Data Engineering",
    "overall_score": 88.2,
    "recommendation": "Highly Suitable",
    "criteria_met": 22,
    "criteria_partial": 4,
    "criteria_not_met": 3,
    "key_strengths": ["Platform leadership"],
    "critical_gaps": ["No Snowflake experience stated"],
    "improvement_suggestions": ["Name the warehouse technologies used"],
    "categories": [
        {
            "category": "Required Skills",
            "category_score": 88.0,
            "criteria": [
                {
                    "criterion": "Cloud data warehouse",
                    "status": "partial",
                    "explanation": "AWS is evidenced, the warehouse is not.",
                }
            ],
        }
    ],
}


class TestEmptyInput:
    def test_nothing_to_report_yields_nothing(self):
        """An empty string lets the caller append unconditionally without
        producing a stray blank page."""
        assert build_report() == ""

    def test_all_none_yields_nothing(self):
        assert build_report(ats=None, grammar=None, suitability=None) == ""


class TestAts:
    def test_scores_are_tabulated(self):
        report = build_report(ats=ATS)
        assert "| Overall | 81 |" in report
        assert "| Keywords | 47 |" in report

    def test_keywords_are_split_into_found_and_missing(self):
        report = build_report(ats=ATS)
        assert "**Found (2):** airflow, dbt" in report
        assert "**Not found (2):** sql, snowflake" in report

    def test_formatting_issues_are_listed(self):
        assert "- Missing phone number" in build_report(ats=ATS)

    def test_recommendations_are_ordered_by_priority(self):
        report = build_report(ats=ATS)
        assert report.index("Missing 19 industry-standard keywords") < report.index(
            "Tighten the summary"
        )

    def test_a_recommendation_shows_its_fix_and_impact(self):
        report = build_report(ats=ATS)
        assert "Incorporate the relevant terms" in report
        assert "*Why it matters:* Improves ATS matching" in report


class TestGrammar:
    def test_issues_are_rendered_with_their_correction(self):
        report = build_report(grammar=GRAMMAR)
        assert "was responsible for delivery" in report
        assert "*Suggested:* delivered" in report

    def test_a_clean_check_says_so(self):
        report = build_report(grammar={"overall_quality": 100, "issues": []})
        assert "No issues found." in report


class TestSuitability:
    def test_the_match_and_verdict_appear(self):
        report = build_report(suitability=SUITABILITY)
        assert "**Match:** 88%" in report
        assert "Highly Suitable" in report

    def test_strengths_gaps_and_suggestions_are_listed(self):
        report = build_report(suitability=SUITABILITY)
        assert "- Platform leadership" in report
        assert "- No Snowflake experience stated" in report
        assert "- Name the warehouse technologies used" in report

    def test_criteria_status_is_readable(self):
        """"partial" is not a phrase anyone wants to read in a document."""
        report = build_report(suitability=SUITABILITY)
        assert "Partly met" in report


class TestDocument:
    def test_it_starts_on_a_new_page(self):
        """The assessment is for the author, not the reader of the CV."""
        assert build_report(ats=ATS).startswith("\\newpage")

    def test_it_warns_that_the_section_is_private(self):
        assert "remove it before sending" in build_report(ats=ATS)

    def test_the_date_is_shown(self):
        report = build_report(ats=ATS, generated_at=datetime(2026, 9, 7))
        assert "07 September 2026" in report

    def test_all_three_assessments_combine(self):
        report = build_report(ats=ATS, grammar=GRAMMAR, suitability=SUITABILITY)
        assert "## ATS assessment" in report
        assert "## Language" in report
        assert "## Suitability for this role" in report

    def test_models_are_accepted_as_well_as_dicts(self):
        """The caller passes Pydantic results, tests pass dicts."""

        class Score:
            overall_score = 70.0
            keyword_score = None
            formatting_score = None
            structure_score = None
            completeness_score = None

        class Result:
            summary = "From a model."
            compatibility_score = Score()
            present_keywords = []
            missing_keywords = []
            formatting_issues = []
            recommendations = []

        report = build_report(ats=Result())
        assert "From a model." in report
        assert "| Overall | 70 |" in report


class TestRealModelShapes:
    """The report reads results produced by the analysers, not hand-written
    dicts. These use the actual Pydantic models so a field rename on either
    side fails here rather than silently emptying a section of the document.
    """

    def test_a_real_ats_result_renders(self):
        from datetime import datetime as dt

        from app.models.llm_models import (
            ATSAnalysisResult,
            ATSCompatibilityScore,
            ATSRecommendation,
            RecommendationPriority,
        )

        result = ATSAnalysisResult(
            cv_id="cv-1",
            compatibility_score=ATSCompatibilityScore(
                overall_score=81.3,
                keyword_score=46.7,
                formatting_score=100.0,
                structure_score=90.0,
                completeness_score=100.0,
            ),
            recommendations=[
                ATSRecommendation(
                    category="Keywords",
                    issue="Missing 19 keywords",
                    suggestion="Add the terms you can evidence",
                    impact="Improves ATS matching",
                    priority=RecommendationPriority.HIGH,
                )
            ],
            industry_keywords=["sql"],
            present_keywords=["dbt"],
            missing_keywords=["sql"],
            keyword_density={},
            formatting_issues=["Missing phone number"],
            summary="Reads well.",
            analyzed_at=dt.now(),
            model="m",
            provider="p",
        )

        report = build_report(ats=result)
        assert "Reads well." in report
        assert "| Overall | 81 |" in report
        assert "**Found (1):** dbt" in report
        assert "Missing phone number" in report
        assert "Missing 19 keywords" in report
        # The enum must render as its value, not "RecommendationPriority.HIGH".
        assert "high priority" in report
        assert "RecommendationPriority" not in report

    def test_a_real_grammar_result_renders(self):
        from datetime import datetime as dt

        from app.models.llm_models import GrammarCheckResult, GrammarIssue

        result = GrammarCheckResult(
            cv_id="cv-1",
            issues=[
                GrammarIssue(
                    id="1",
                    type="passive_voice",
                    location="Experience",
                    issue_text="was responsible for delivery",
                    correction="delivered",
                    explanation="Active voice reads stronger.",
                    severity="medium",
                )
            ],
            overall_quality="Very Good - 1 moderate issue",
            checked_at=dt.now(),
            model="m",
            provider="p",
        )

        report = build_report(grammar=result)
        assert "was responsible for delivery" in report
        assert "*Suggested:* delivered" in report
        # overall_quality is a sentence, not a score; treating it as numeric
        # dropped the line without anyone noticing.
        assert "Very Good - 1 moderate issue" in report
