"""Keyword selection for ATS analysis.

Keywords used to come from four hardcoded INDUSTRY_KEYWORDS buckets chosen by
substring match, which sent any title containing "engineer" to the software
list. They are now derived from the role being targeted, with the buckets kept
only as an offline fallback.
"""

import pytest

from app.llm.ats_analyzer import ATSAnalyzer


@pytest.fixture
def analyzer():
    return ATSAnalyzer.__new__(ATSAnalyzer)


class TestCurrentRole:
    def test_prefers_the_role_flagged_current(self, analyzer):
        cv = {
            "experience": [
                {"title": "Old Job", "company": "Past", "start_date": "2015"},
                {"title": "Head of Data", "company": "Acme", "current": True},
            ]
        }
        assert analyzer._current_role(cv) == "Head of Data at Acme"

    def test_falls_back_to_the_latest_start_date(self, analyzer):
        cv = {
            "experience": [
                {"title": "Older", "company": "A", "start_date": "2015-01"},
                {"title": "Newer", "company": "B", "start_date": "2021-06"},
            ]
        }
        assert analyzer._current_role(cv) == "Newer at B"

    def test_omits_the_company_when_absent(self, analyzer):
        cv = {"experience": [{"title": "Consultant", "current": True}]}
        assert analyzer._current_role(cv) == "Consultant"

    def test_falls_back_to_the_headline_title(self, analyzer):
        cv = {"personal_info": {"title": "Data Leader"}}
        assert analyzer._current_role(cv) == "Data Leader"

    def test_returns_none_for_an_empty_cv(self, analyzer):
        assert analyzer._current_role({}) is None

    def test_ignores_entries_with_no_title(self, analyzer):
        cv = {"experience": [{"company": "Acme"}], "personal_info": {"title": "Lead"}}
        assert analyzer._current_role(cv) == "Lead"


class TestStaticFallbackDeterminism:
    """The fallback returned raw set order, so the keywords shown to the user
    changed on every run for an unchanged CV."""

    def test_the_same_inputs_give_the_same_order(self, analyzer):
        cv = {"summary": "data engineering leadership"}
        first = analyzer._identify_industry_keywords(cv, "Data", "Head of Data")
        second = analyzer._identify_industry_keywords(cv, "Data", "Head of Data")
        assert first == second
        assert first == sorted(first)


class TestKeywordDerivation:
    """Keywords must describe the target role, not echo the CV back at itself."""

    @pytest.mark.asyncio
    async def test_uses_the_role_and_not_the_cv_text(self, analyzer):
        captured = {}

        class FakeProvider:
            async def generate_structured_output(self, prompt, schema, **kwargs):
                captured["prompt"] = prompt

                class R:
                    data = {"keywords": ["Airflow", "dbt", "airflow", "  "]}

                return R()

        analyzer.llm_provider = FakeProvider()
        keywords = await analyzer._keywords_for_role("Head of Data Engineering", "Insurance")

        assert "Head of Data Engineering" in captured["prompt"]
        assert "Insurance" in captured["prompt"]
        # Normalised, de-duplicated, blanks dropped.
        assert keywords == ["airflow", "dbt"]

    @pytest.mark.asyncio
    async def test_caps_the_list(self, analyzer):
        class FakeProvider:
            async def generate_structured_output(self, prompt, schema, **kwargs):
                class R:
                    data = {"keywords": [f"kw{i}" for i in range(50)]}

                return R()

        analyzer.llm_provider = FakeProvider()
        assert len(await analyzer._keywords_for_role("Anything", None)) == 30

    @pytest.mark.asyncio
    async def test_a_junk_response_yields_nothing_rather_than_raising(self, analyzer):
        class FakeProvider:
            async def generate_structured_output(self, prompt, schema, **kwargs):
                class R:
                    data = {}

                return R()

        analyzer.llm_provider = FakeProvider()
        assert await analyzer._keywords_for_role("Anything", None) == []
