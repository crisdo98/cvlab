"""Render CV assessments as a Markdown appendix.

An export of the CV alone answers "what does it say". This adds "and what
should change about it": the ATS assessment, the grammar findings, and — when a
job description is supplied — how the CV measures against that role.

The output is Markdown so it goes through the same pandoc pipeline as the CV
itself, which means the appendix inherits the document's typography rather than
looking like a separate artefact bolted on the end.

Everything here is a pure function of already-computed results. The analyses
are run by the caller, so this can be tested without a model.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

#: Order used when grouping recommendations, most urgent first.
_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _get(source: Any, name: str, default: Any = None) -> Any:
    """Read a field from a Pydantic model or a plain dict."""
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)


def _priority(value: Any) -> str:
    text = _get(value, "value", value)
    return str(text or "medium").lower()


def _score_line(label: str, value: Any) -> Optional[str]:
    if not isinstance(value, (int, float)):
        return None
    return f"| {label} | {round(float(value))} |"


def _ats_section(ats: Any) -> List[str]:
    """The ATS assessment: scores, keywords, formatting and what to do."""
    if ats is None:
        return []

    lines = ["## ATS assessment", ""]

    summary = _get(ats, "summary")
    if summary:
        lines += [str(summary), ""]

    score = _get(ats, "compatibility_score")
    rows = [
        _score_line("Overall", _get(score, "overall_score")),
        _score_line("Keywords", _get(score, "keyword_score")),
        _score_line("Formatting", _get(score, "formatting_score")),
        _score_line("Structure", _get(score, "structure_score")),
        _score_line("Completeness", _get(score, "completeness_score")),
    ]
    rows = [row for row in rows if row]
    if rows:
        lines += ["| Measure | Score |", "| --- | --- |", *rows, ""]

    present = _get(ats, "present_keywords") or []
    missing = _get(ats, "missing_keywords") or []
    if present or missing:
        lines += ["### Keywords", ""]
        if present:
            lines += [f"**Found ({len(present)}):** " + ", ".join(map(str, present)), ""]
        if missing:
            lines += [
                f"**Not found ({len(missing)}):** " + ", ".join(map(str, missing)),
                "",
                "These are terms an applicant tracking system is likely to screen "
                "for in this role. Add only those you can genuinely evidence.",
                "",
            ]

    issues = _get(ats, "formatting_issues") or []
    if issues:
        lines += ["### Formatting", ""]
        lines += [f"- {issue}" for issue in issues]
        lines.append("")

    lines += _recommendations(_get(ats, "recommendations") or [])
    return lines


def _recommendations(recommendations: List[Any]) -> List[str]:
    """Recommendations grouped by priority, most urgent first."""
    if not recommendations:
        return []

    ordered = sorted(
        recommendations,
        key=lambda r: _PRIORITY_ORDER.get(_priority(_get(r, "priority")), 1),
    )

    lines = ["### Recommendations", ""]
    for item in ordered:
        issue = _get(item, "issue") or _get(item, "suggestion") or "Recommendation"
        priority = _priority(_get(item, "priority"))
        category = _get(item, "category")

        heading = f"**{issue}**"
        tags = [t for t in (category, f"{priority} priority") if t]
        lines.append(f"{heading} — {' · '.join(map(str, tags))}" if tags else heading)
        lines.append("")

        suggestion = _get(item, "suggestion")
        if suggestion and suggestion != issue:
            lines += [str(suggestion), ""]

        impact = _get(item, "impact")
        if impact:
            lines += [f"*Why it matters:* {impact}", ""]

    return lines


def _grammar_section(grammar: Any) -> List[str]:
    """Language findings, worst first, with the correction alongside."""
    if grammar is None:
        return []

    issues = _get(grammar, "issues") or []
    lines = ["## Language", ""]

    # overall_quality is a sentence ("Very Good - 2 moderate issues"), not a
    # number. Treating it as numeric silently dropped the line entirely.
    quality = _get(grammar, "overall_quality")
    if isinstance(quality, (int, float)):
        lines += [f"Overall quality: **{round(float(quality))}**", ""]
    elif isinstance(quality, str) and quality.strip():
        lines += [f"**{quality.strip()}**", ""]

    if not issues:
        lines += ["No issues found.", ""]
        return lines

    severity_order = {"high": 0, "critical": 0, "medium": 1, "low": 2}
    ordered = sorted(
        issues, key=lambda i: severity_order.get(_priority(_get(i, "severity")), 1)
    )

    lines += [f"{len(issues)} issue{'' if len(issues) == 1 else 's'} found.", ""]
    for issue in ordered:
        text = _get(issue, "issue_text")
        correction = _get(issue, "correction")
        where = _get(issue, "location")
        severity = _priority(_get(issue, "severity"))

        header = f"**{_get(issue, 'type') or 'Issue'}** ({severity})"
        if where:
            header += f" — {where}"
        lines += [header, ""]
        if text:
            lines += [f"> {text}", ""]
        if correction:
            lines += [f"*Suggested:* {correction}", ""]
        explanation = _get(issue, "explanation")
        if explanation:
            lines += [str(explanation), ""]

    return lines


def _suitability_section(suitability: Any) -> List[str]:
    """How the CV measures against a specific role."""
    if suitability is None:
        return []

    lines = ["## Suitability for this role", ""]

    title = _get(suitability, "job_title")
    if title:
        lines += [f"**Role:** {title}", ""]

    score = _get(suitability, "overall_score")
    verdict = _get(suitability, "recommendation")
    if isinstance(score, (int, float)):
        lines.append(f"**Match:** {round(float(score))}%")
        if verdict:
            lines.append(f" — {verdict}")
        lines += ["", ""]

    met = _get(suitability, "criteria_met")
    partial = _get(suitability, "criteria_partial")
    unmet = _get(suitability, "criteria_not_met")
    if isinstance(met, int):
        lines += [
            f"Criteria met: **{met}**, partially met: **{partial or 0}**, "
            f"not met: **{unmet or 0}**",
            "",
        ]

    for heading, key in (
        ("### Strengths", "key_strengths"),
        ("### Gaps", "critical_gaps"),
        ("### Suggested changes", "improvement_suggestions"),
    ):
        values = _get(suitability, key) or []
        if values:
            lines += [heading, ""]
            lines += [f"- {value}" for value in values]
            lines.append("")

    for category in _get(suitability, "categories") or []:
        name = _get(category, "category") or "Category"
        cat_score = _get(category, "category_score")
        header = f"### {name}"
        if isinstance(cat_score, (int, float)):
            header += f" — {round(float(cat_score))}%"
        lines += [header, ""]

        for criterion in _get(category, "criteria") or []:
            status = str(_get(criterion, "status") or "").lower()
            mark = {"yes": "Met", "partial": "Partly met", "no": "Not met"}.get(
                _priority(status), status or "—"
            )
            lines.append(f"- **{_get(criterion, 'criterion')}** — {mark}")
            explanation = _get(criterion, "explanation")
            if explanation:
                lines.append(f"  {explanation}")
        lines.append("")

    return lines


def build_report(
    ats: Any = None,
    grammar: Any = None,
    suitability: Any = None,
    generated_at: Optional[datetime] = None,
) -> str:
    """Build the appendix.

    Returns an empty string when there is nothing to report, so a caller can
    append it unconditionally without producing a stray empty page.
    """
    body: List[str] = []
    body += _ats_section(ats)
    body += _grammar_section(grammar)
    body += _suitability_section(suitability)

    if not body:
        return ""

    stamp = (generated_at or datetime.now()).strftime("%d %B %Y")
    header = [
        # A page break keeps the assessment off the last page of the CV, which
        # matters when the CV is sent on: the recommendations are for the
        # author, not the reader.
        "\\newpage",
        "",
        "# Assessment and recommendations",
        "",
        f"*Generated {stamp}. This section is for your own use — remove it "
        "before sending the CV to anyone.*",
        "",
    ]

    return "\n".join(header + body).rstrip() + "\n"
