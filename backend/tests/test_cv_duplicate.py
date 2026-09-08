"""Duplicating a CV.

A copy must be fully independent: editing it cannot reach back into the
original, which means every id — the document's, each section's, and each
entry's — has to be regenerated rather than shared.
"""

import pytest

from app.models.cv_models import CVModelV2
from app.services.cv_service import CVService


def _cv():
    return CVModelV2(
        sections=[
            {
                "type": "personal_info",
                "title": "Personal Information",
                "order": 0,
                "content": {
                    "content_type": "personal",
                    "cv_title": "Data Leader CV",
                    "full_name": "Ada Lovelace",
                },
            },
            {
                "type": "experience",
                "title": "Experience",
                "order": 1,
                "content": {
                    "content_type": "structured",
                    "entries": [{"title": "Lead", "company": "Acme"}],
                },
            },
        ]
    )


class FakeFiles:
    def __init__(self, cv):
        self.cv = cv
        self.saved = []

    def load_cv(self, cv_id):
        return self.cv

    def save_cv(self, cv):
        self.saved.append(cv)


@pytest.fixture
def service():
    svc = CVService.__new__(CVService)
    svc.file_service = FakeFiles(_cv())
    return svc


class TestIndependence:
    def test_the_copy_gets_a_new_document_id(self, service):
        original = service.file_service.cv
        copy = service.duplicate_cv(original.id).cv
        assert copy.id != original.id

    def test_section_ids_are_regenerated(self, service):
        original = service.file_service.cv
        original_ids = {s.id for s in original.sections}
        copy = service.duplicate_cv(original.id).cv
        assert {s.id for s in copy.sections}.isdisjoint(original_ids)

    def test_entry_ids_are_regenerated(self, service):
        """Entries carry ids too; sharing them would link the two documents."""
        original = service.file_service.cv
        before = original.sections[1].content.entries[0].id
        copy = service.duplicate_cv(original.id).cv
        assert copy.sections[1].content.entries[0].id != before

    def test_editing_the_copy_leaves_the_original_alone(self, service):
        original = service.file_service.cv
        copy = service.duplicate_cv(original.id).cv
        copy.sections[1].content.entries[0].title = "Changed"
        assert original.sections[1].content.entries[0].title == "Lead"


class TestContent:
    def test_content_is_carried_over(self, service):
        copy = service.duplicate_cv(service.file_service.cv.id).cv
        assert len(copy.sections) == 2
        assert copy.sections[1].content.entries[0].company == "Acme"

    def test_the_title_is_marked_as_a_copy(self, service):
        copy = service.duplicate_cv(service.file_service.cv.id).cv
        assert copy.sections[0].content.cv_title == "Data Leader CV (copy)"

    def test_an_explicit_title_wins(self, service):
        copy = service.duplicate_cv(service.file_service.cv.id, "Tailored for Acme").cv
        assert copy.sections[0].content.cv_title == "Tailored for Acme"

    def test_the_copy_is_saved(self, service):
        service.duplicate_cv(service.file_service.cv.id)
        assert len(service.file_service.saved) == 1
