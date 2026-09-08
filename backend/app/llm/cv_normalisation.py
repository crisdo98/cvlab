"""Adapt a section-based CV into the flat shape the LLM analysers expect.

CVLab stores a CV as an ordered list of typed sections, each holding its own
content blob:

    {"sections": [{"type": "experience", "content": {"entries": [...]}}, ...]}

The analysers in this package were written against a different, flat shape —
``cv_data["experience"]``, ``cv_data["personal_info"]["contact"]["email"]`` and
so on — which nothing in the app actually produces. Reading a stored CV with
those lookups therefore found nothing and reported every section missing, no
matter how complete the CV was.

Normalising once, here, keeps that translation in a single place instead of
scattering ``sections`` handling through every analyser.
"""

from typing import Any, Dict, List

#: Section types whose content is a list of entries copied through as-is.
_ENTRY_SECTIONS = {"experience", "education", "certifications", "projects"}


def is_section_based(cv_data: Dict[str, Any]) -> bool:
    """Whether this looks like a stored CV rather than an already-flat one."""
    return isinstance(cv_data.get("sections"), list)


def _personal_info(content: Dict[str, Any]) -> Dict[str, Any]:
    """Map a personal-info blob onto the nested name/contact shape.

    The stored blob is flat (``email`` beside ``full_name``), while the
    analysers expect contact details grouped under ``contact``.
    """
    return {
        "name": content.get("full_name") or "",
        "title": content.get("title") or "",
        "contact": {
            "email": content.get("email") or "",
            "phone": content.get("phone") or "",
            "location": content.get("location") or "",
            "linkedin": content.get("linkedin") or "",
            "website": content.get("website") or "",
        },
    }


def _skills(content: Dict[str, Any]) -> Dict[str, Any]:
    """Map skills onto the ``{"categories": [{"name", "skills"}]}`` shape.

    Skills are stored as a flat list of ``{"text": ...}`` items with no
    categories. Rather than invent categories, everything goes into one, which
    keeps the "too many categories" heuristic from firing on a CV that has
    never expressed any.
    """
    items: List[str] = []
    for item in content.get("items") or []:
        if isinstance(item, dict):
            text = item.get("text")
        else:
            text = item
        if text:
            items.append(str(text))

    # Preserve real categories if a CV ever supplies them.
    categories = content.get("categories")
    if isinstance(categories, list) and categories:
        return {"categories": categories}

    return {"categories": [{"name": "Skills", "skills": items}] if items else []}


def flatten_cv(cv_data: Dict[str, Any]) -> Dict[str, Any]:
    """Return `cv_data` in the flat shape the analysers read.

    A CV that is already flat is returned unchanged, so this is safe to apply
    unconditionally at an entry point.
    """
    if not isinstance(cv_data, dict):
        return {}
    if not is_section_based(cv_data):
        return cv_data

    flat: Dict[str, Any] = {
        key: value for key, value in cv_data.items() if key != "sections"
    }

    for section in cv_data.get("sections") or []:
        if not isinstance(section, dict):
            continue
        # A hidden section is not on the exported CV, so an ATS would never
        # see it either.
        if section.get("visible") is False:
            continue

        section_type = section.get("type")
        content = section.get("content")
        if not section_type or not isinstance(content, dict):
            continue

        if section_type == "personal_info":
            flat["personal_info"] = _personal_info(content)
        elif section_type == "summary":
            flat["summary"] = content.get("text") or ""
        elif section_type == "skills":
            flat["skills"] = _skills(content)
        elif section_type in _ENTRY_SECTIONS:
            entries = content.get("entries")
            if isinstance(entries, list):
                flat[section_type] = entries

    return flat


def flatten_cv_model(cv: Any) -> Dict[str, Any]:
    """Flatten a CV given as a Pydantic model or a plain dict.

    Both CV versions end up in the same flat shape: a V1 ``CVModel`` already
    matches it and passes through, while a V2 ``CVModelV2`` is converted from
    its sections. Callers can then read one structure rather than branching on
    the model version.

    ``mode="json"`` is used so enums and dates come back as strings, which is
    what the text builders expect.
    """
    if hasattr(cv, "model_dump"):
        data = cv.model_dump(mode="json")
    elif isinstance(cv, dict):
        data = cv
    else:
        return {}
    return flatten_cv(data)
