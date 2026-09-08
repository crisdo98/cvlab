"""Markdown import: bullets must not land in two fields.

The importer joined every remaining line into `description` and *also*
extracted the bullet lines into `achievements`, so each bullet was stored
twice. Exports then printed the same text as a paragraph and again as a list.
"""

from app.services.import_service import ImportService


JOB = """### Head of Data Engineering
**Direct Line Group** | London
*March 2023 - Present*
Strategic leader responsible for enterprise data architecture.
**Strategic Impact**
- Orchestrated a transformation of data engineering practices
- Established the Data Engineering Community of Practice
"""


def _parse():
    service = ImportService.__new__(ImportService)
    header, _, body = JOB.partition("\n")
    return service._parse_single_experience(header.lstrip("# ").strip(), body)


class TestNoDuplication:
    def test_bullets_become_achievements(self):
        entry = _parse()
        assert len(entry["achievements"]) == 2
        assert "Orchestrated a transformation" in entry["achievements"][0]

    def test_bullets_are_absent_from_the_description(self):
        entry = _parse()
        for achievement in entry["achievements"]:
            assert achievement not in entry["description"]

    def test_the_description_keeps_its_prose(self):
        entry = _parse()
        assert "Strategic leader responsible" in entry["description"]

    def test_the_description_keeps_non_bullet_formatting(self):
        """A bold sub-heading is prose, not a bullet, so it stays."""
        assert "**Strategic Impact**" in _parse()["description"]

    def test_no_line_is_lost_between_the_two_fields(self):
        """Two prose lines plus two bullets: every body line lands somewhere."""
        entry = _parse()
        kept = len([l for l in entry["description"].split("\n") if l.strip()])
        assert kept == 2
        assert kept + len(entry["achievements"]) == 4

    def test_dates_and_company_are_still_read(self):
        entry = _parse()
        assert entry["company"] == "Direct Line Group"
        assert entry["location"] == "London"
        assert entry["current"] is True
