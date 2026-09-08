"""
Helpers for reading V2 (sections-based) CVs in tests.

`FileService.load_cv` migrates legacy V1 files on read, so every CV reaching a
test is a `CVModelV2`: content lives inside typed sections rather than the flat
`summary`/`skills`/`experience` fields of V1. These helpers do the section
lookup once so tests can assert on content without repeating it.

Each helper accepts either a `CVModelV2` instance or the dict produced by
`model_dump()`, since services return both.
"""
from typing import Any, Dict, List, Optional


def _sections(cv: Any) -> List[Any]:
    """Return the section list from a CVModelV2 instance or its dict form."""
    if isinstance(cv, dict):
        return cv.get("sections", []) or []
    return getattr(cv, "sections", []) or []


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    """Read a field from a pydantic model or a plain dict."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _type_of(section: Any) -> str:
    """Return a section's type as a plain string."""
    value = _attr(section, "type")
    return getattr(value, "value", value)


def find_section(cv: Any, section_type: str) -> Optional[Any]:
    """Return the first section of the given type, or None."""
    for section in _sections(cv):
        if _type_of(section) == section_type:
            return section
    return None


def section_content(cv: Any, section_type: str) -> Optional[Any]:
    """Return the content of the first section of the given type, or None."""
    section = find_section(cv, section_type)
    return _attr(section, "content") if section is not None else None


def cv_title(cv: Any) -> Optional[str]:
    """The CV's title, which V2 stores on the personal_info section."""
    content = section_content(cv, "personal_info")
    return _attr(content, "cv_title") if content is not None else None


def full_name(cv: Any) -> Optional[str]:
    """The person's name from the personal_info section."""
    content = section_content(cv, "personal_info")
    return _attr(content, "full_name") if content is not None else None


def summary_text(cv: Any) -> Optional[str]:
    """The summary section's free text, or None when there is no summary."""
    content = section_content(cv, "summary")
    return _attr(content, "text") if content is not None else None


def list_items(cv: Any, section_type: str) -> List[str]:
    """The item texts of a list section (skills, languages, interests, ...)."""
    content = section_content(cv, section_type)
    if content is None:
        return []
    return [_attr(item, "text") for item in _attr(content, "items", []) or []]


def skills(cv: Any) -> List[str]:
    """All skill names on the CV."""
    return list_items(cv, "skills")


def entries(cv: Any, section_type: str) -> List[Any]:
    """The entries of a structured section (experience, education, ...)."""
    content = section_content(cv, section_type)
    if content is None:
        return []
    return _attr(content, "entries", []) or []


def experience(cv: Any) -> List[Any]:
    """The CV's experience entries."""
    return entries(cv, "experience")


def education(cv: Any) -> List[Any]:
    """The CV's education entries."""
    return entries(cv, "education")


def section_types(cv: Any) -> List[str]:
    """Every section type present, in order."""
    return [_type_of(section) for section in _sections(cv)]


def as_dict(response: Any) -> Dict[str, Any]:
    """
    Unwrap an API response body to the CV dict.

    CV endpoints return `{"cv": {...}, "message": ...}`; older tests expected the
    CV at the top level.
    """
    if isinstance(response, dict) and "cv" in response:
        return response["cv"]
    return response


def set_section_content(cv: Dict[str, Any], section_type: str, **fields: Any) -> Dict[str, Any]:
    """
    Update fields on a section's content in a CV dict, in place.

    Used to build a V2 update payload: `PUT /api/cvs/{id}` accepts a body
    carrying `sections`, so tests fetch a CV, change the section they care
    about, and send the whole thing back.

    Returns the same dict so calls can be chained into a request.
    """
    for section in cv.get("sections", []):
        if _type_of(section) == section_type:
            section.setdefault("content", {}).update(fields)
            break
    return cv
