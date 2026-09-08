"""
Plain-text CV normalisation

Many CVs are exported from Word/PDF as plain text: no YAML frontmatter, no
markdown headings, no bullet characters. The markdown import parser is
heading-driven, so such files parse to an empty CV.

This module converts that plain-text layout into the canonical markdown the
import parser already understands, so a single parsing path handles both.
"""

import re
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Section aliases -> canonical markdown heading used by ImportService
SECTION_ALIASES = {
    'summary': 'Summary',
    'professional summary': 'Summary',
    'executive summary': 'Summary',
    'profile': 'Summary',
    'personal profile': 'Summary',
    'about': 'Summary',
    'about me': 'Summary',

    'experience': 'Experience',
    'work experience': 'Experience',
    'professional experience': 'Experience',
    'leadership experience': 'Experience',
    'employment': 'Experience',
    'employment history': 'Experience',
    'career history': 'Experience',
    'work history': 'Experience',

    'skills': 'Skills',
    'core skills': 'Skills',
    'key skills': 'Skills',
    'technical skills': 'Skills',
    'core competencies': 'Skills',
    'competencies': 'Skills',
    'expertise': 'Skills',
    'skills and expertise': 'Skills',

    'education': 'Education',
    'education and qualifications': 'Education',
    'qualifications': 'Education',
    'academic background': 'Education',

    'certifications': 'Professional Memberships and Certificates',
    'certificates': 'Professional Memberships and Certificates',
    'professional certifications': 'Professional Memberships and Certificates',
    'professional memberships': 'Professional Memberships and Certificates',
    'professional memberships and certificates': 'Professional Memberships and Certificates',
    'certifications and memberships': 'Professional Memberships and Certificates',
    'licenses and certifications': 'Professional Memberships and Certificates',
}

_MONTH = (
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)'
    r'(?:uary|ruary|ch|il|e|y|ust|tember|ober|ember)?'
)
_DATE = rf'(?:{_MONTH}\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}})'
_OPEN_ENDED = r'(?:Present|Current|Now|Today|Ongoing|Date)'

DATE_RANGE_PATTERN = re.compile(
    rf'^\s*({_DATE})\s*[-–—]{{1,2}}\s*({_DATE}|{_OPEN_ENDED})\s*$',
    re.IGNORECASE
)
SINGLE_DATE_PATTERN = re.compile(rf'^\s*{_DATE}\s*$', re.IGNORECASE)
MARKDOWN_HEADING_PATTERN = re.compile(r'^#{1,6}\s+\S', re.MULTILINE)
PIPE_SEPARATOR_PATTERN = re.compile(r'\s*\|\s*')


def is_plain_text_cv(content: str) -> bool:
    """
    Return True when content has no markdown headings and no YAML frontmatter,
    i.e. the heading-driven markdown parser would find nothing to parse.
    """
    stripped = content.strip()
    if stripped.startswith('---'):
        return False
    return not MARKDOWN_HEADING_PATTERN.search(stripped)


def _canonical_heading(line: str) -> Optional[str]:
    """Map a bare section heading line to its canonical markdown heading."""
    key = line.strip().rstrip(':').strip().lower()
    key = re.sub(r'\s*&\s*', ' and ', key)
    key = re.sub(r'\s+', ' ', key)
    if len(key) > 60:
        return None
    return SECTION_ALIASES.get(key)


def _split_blocks(lines: List[str]) -> List[List[str]]:
    """Group consecutive non-blank lines into blocks."""
    blocks: List[List[str]] = []
    current: List[str] = []
    for line in lines:
        if line.strip():
            current.append(line.strip())
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def _split_company_location(line: str) -> Tuple[str, Optional[str]]:
    """Split 'Company - City, Country' into company and location."""
    parts = re.split(r'\s+[-–—]\s+', line, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return line.strip(), None


def _split_institution_location(line: str) -> Tuple[str, Optional[str]]:
    """
    Split an institution line into institution and location.

    Handles both 'University, City' and the separator-less
    'University City, Country' shape common in plain-text exports.
    """
    if ',' not in line:
        return line.strip(), None

    before, _, after = line.partition(',')
    before, after = before.strip(), after.strip()
    words = before.split()

    # 'Canterbury Christ Church University Canterbury, United Kingdom' -
    # the word before the comma is the city, not part of the institution
    if (len(words) >= 3
            and words[-1][:1].isupper()
            and words[-2].lower() not in {'of', 'the', 'and', 'for', 'at', 'in', '&'}):
        return ' '.join(words[:-1]), f'{words[-1]}, {after}'

    return before, after


def _normalise_header(lines: List[str]) -> List[str]:
    """
    Turn the leading name/title/contact block into markdown:
    '# Name' followed by title and contact lines.
    """
    out: List[str] = []
    if not lines:
        return out
    out.append(f'# {lines[0].strip()}')
    out.extend(line.strip() for line in lines[1:])
    out.append('')
    return out


def _normalise_experience(body: List[str]) -> List[str]:
    """
    Convert plain-text experience entries into markdown job entries.

    Expected plain-text shape per entry:
        March 2023 - Current
        Direct Line Group - London, United Kingdom
        Head of Data Engineering
        <description and bullet lines>
    """
    out: List[str] = []
    blocks = _split_blocks(body)

    entries: List[dict] = []
    current: Optional[dict] = None

    for block in blocks:
        first = block[0]
        if DATE_RANGE_PATTERN.match(first):
            current = {'dates': first.strip(), 'company': None, 'location': None,
                       'title': None, 'body': []}
            entries.append(current)
            remainder = block[1:]
        elif current is None:
            # Content before any dated entry - nothing reliable to attach it to
            continue
        else:
            remainder = block

        for line in remainder:
            if current['company'] is None:
                current['company'], current['location'] = _split_company_location(line)
            elif current['title'] is None:
                current['title'] = line.strip()
            else:
                current['body'].append(line)

    for entry in entries:
        if not entry['title'] and not entry['company']:
            continue
        title = entry['title'] or entry['company']
        out.append(f'### {title}')
        if entry['company'] and entry['title']:
            company_line = f"**{entry['company']}**"
            if entry['location']:
                company_line += f" | {entry['location']}"
            out.append(company_line)
        else:
            out.append('**N/A**')
        out.append(f"*{entry['dates']}*")
        for line in entry['body']:
            if line.endswith(':'):
                # Group heading inside the entry - keep as plain text
                out.append(line)
            elif re.match(r'^[-•*]\s+', line):
                out.append(re.sub(r'^[•*]\s+', '- ', line))
            else:
                out.append(f'- {line}')
        out.append('')

    return out


def _normalise_skills(body: List[str]) -> List[str]:
    """
    Convert 'Category' / 'skill | skill | skill' line pairs into
    'Category: skill; skill; skill'.
    """
    out: List[str] = []
    pending_category: Optional[str] = None

    for raw in body:
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r'^[-•*]\s+', '', line)

        if ':' in line:
            name, _, skills = line.partition(':')
            skill_list = PIPE_SEPARATOR_PATTERN.sub('; ', skills.strip())
            out.append(f"{name.strip()}: {skill_list}")
            pending_category = None
        elif '|' in line:
            category = pending_category or 'Skills'
            skill_list = PIPE_SEPARATOR_PATTERN.sub('; ', line)
            out.append(f"{category}: {skill_list}")
            pending_category = None
        elif pending_category:
            # Two consecutive plain lines: treat the previous as a lone skill list
            out.append(f'{pending_category}: {pending_category}')
            pending_category = line
        else:
            pending_category = line

    if pending_category:
        out.append(f'Skills: {pending_category}')

    out.append('')
    return out


def _normalise_education(body: List[str]) -> List[str]:
    """
    Convert plain-text education entries into markdown education entries.

    Expected plain-text shape per entry:
        September 2011 - June 2014
        Canterbury Christ Church University Canterbury, United Kingdom
        Bachelor of Science Computing - 1st Class Honours
        <extra lines>
    """
    out: List[str] = []
    blocks = _split_blocks(body)

    entries: List[dict] = []
    current: Optional[dict] = None

    for block in blocks:
        first = block[0]
        if DATE_RANGE_PATTERN.match(first) or SINGLE_DATE_PATTERN.match(first):
            current = {'dates': first.strip(), 'institution': None,
                       'degree': None, 'body': []}
            entries.append(current)
            remainder = block[1:]
        elif current is None:
            continue
        else:
            remainder = block

        for line in remainder:
            if current['institution'] is None:
                current['institution'] = line.strip()
            elif current['degree'] is None:
                current['degree'] = line.strip()
            else:
                current['body'].append(line)

    for entry in entries:
        degree = entry['degree'] or entry['institution']
        if not degree:
            continue
        out.append(f'### {degree}')
        if entry['degree'] and entry['institution']:
            institution, location = _split_institution_location(entry['institution'])
            institution_line = f'**{institution}**'
            if location:
                institution_line += f' | {location}'
        else:
            institution_line = '**N/A**'
        out.append(institution_line)
        out.append(f"*{entry['dates']}*")
        for line in entry['body']:
            out.append(re.sub(r'^[-•*]\s+', '', line))
        out.append('')

    return out


def _normalise_certifications(body: List[str]) -> List[str]:
    """
    Convert 'February 2025' / 'AWS Certified AI Practitioner' line pairs into
    '- February 2025 - AWS Certified AI Practitioner'.
    """
    out: List[str] = []
    pending_date: Optional[str] = None

    for raw in body:
        line = re.sub(r'^[-•*]\s+', '', raw.strip())
        if not line:
            continue

        if SINGLE_DATE_PATTERN.match(line) or DATE_RANGE_PATTERN.match(line):
            pending_date = line
        elif pending_date:
            out.append(f'- {pending_date} — {line}')
            pending_date = None
        else:
            out.append(f'- {line}')

    out.append('')
    return out


def normalize_plain_text_cv(content: str) -> str:
    """
    Convert a plain-text CV into the canonical markdown layout expected by
    ImportService. Returns the original content when no known section headings
    are found, so nothing is silently mangled.
    """
    lines = content.replace('\r\n', '\n').split('\n')

    # Locate section headings first - everything before the first one is the
    # name/title/contact header block
    heading_positions: List[Tuple[int, str]] = []
    for idx, line in enumerate(lines):
        canonical = _canonical_heading(line)
        if canonical:
            heading_positions.append((idx, canonical))

    if not heading_positions:
        logger.info("Plain-text CV normalisation skipped: no known section headings found")
        return content

    header_lines = [line for line in lines[:heading_positions[0][0]] if line.strip()]
    out: List[str] = _normalise_header(header_lines)

    for position, (idx, canonical) in enumerate(heading_positions):
        end = heading_positions[position + 1][0] if position + 1 < len(heading_positions) else len(lines)
        body = lines[idx + 1:end]

        out.append(f'## {canonical}')
        if canonical == 'Experience':
            out.extend(_normalise_experience(body))
        elif canonical == 'Skills':
            out.extend(_normalise_skills(body))
        elif canonical == 'Education':
            out.extend(_normalise_education(body))
        elif canonical == 'Professional Memberships and Certificates':
            out.extend(_normalise_certifications(body))
        else:
            out.extend(line.rstrip() for line in body)
            out.append('')

    normalised = '\n'.join(out).strip() + '\n'
    logger.info(
        f"Normalised plain-text CV into markdown with sections: "
        f"{[canonical for _, canonical in heading_positions]}"
    )
    return normalised


# Section keywords used to canonicalise headings that are not exact aliases,
# e.g. "Leadership Experience", "Core Technical Skills"
SECTION_KEYWORDS = [
    (('certification', 'certificate', 'membership', 'accreditation'),
     'Professional Memberships and Certificates'),
    (('education', 'academic', 'qualification'), 'Education'),
    (('skill', 'competenc', 'expertise'), 'Skills'),
    (('experience', 'employment', 'career history', 'work history'), 'Experience'),
    (('summary', 'profile', 'about'), 'Summary'),
]


def canonical_section_name(heading: str) -> Optional[str]:
    """
    Map a section heading to its canonical name, tolerating variations such as
    'Leadership Experience', 'Core Competencies' or 'Licenses & Certifications'.
    Returns None when the heading is not a recognised CV section.
    """
    exact = _canonical_heading(heading)
    if exact:
        return exact

    key = heading.strip().rstrip(':').strip().lower()
    key = re.sub(r'\s*&\s*', ' and ', key)
    key = re.sub(r'[*_#]', '', key).strip()
    if not key or len(key) > 60:
        return None

    for keywords, canonical in SECTION_KEYWORDS:
        if any(keyword in key for keyword in keywords):
            return canonical
    return None


def parse_date_range(text: str) -> Optional[Tuple[str, Optional[str], bool]]:
    """
    Parse 'March 2023 - Present' / 'Nov 2019 – March 2023' into
    (start_date, end_date, is_current). Returns None when not a date range.
    """
    candidate = text.strip().strip('*_ ')
    match = DATE_RANGE_PATTERN.match(candidate)
    if not match:
        return None

    start = match.group(1).strip()
    end = match.group(2).strip()
    if re.fullmatch(_OPEN_ENDED, end, re.IGNORECASE):
        return start, None, True
    return start, end, False


def looks_like_date_range(text: str) -> bool:
    """True when the text is a standalone date range."""
    return parse_date_range(text) is not None


def split_on_dash(text: str) -> Optional[Tuple[str, str]]:
    """Split 'Title - Company' on a spaced hyphen, en dash or em dash."""
    parts = re.split(r'\s+[-–—]\s+', text.strip(), maxsplit=1)
    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
        return parts[0].strip(), parts[1].strip()
    return None


def split_trailing_parenthetical(text: str) -> Tuple[str, Optional[str]]:
    """
    Split "Company (San Francisco, CA)" into ("Company", "San Francisco, CA").

    Hand-written CVs commonly put the location after the employer, and the
    issuer after a certification name, in brackets. Returns the text unchanged
    with None when there is no trailing parenthetical.
    """
    match = re.match(r'^(.*?)\s*\(([^()]*)\)\s*$', text.strip())
    if match and match.group(1).strip() and match.group(2).strip():
        return match.group(1).strip(), match.group(2).strip()
    return text.strip(), None


def strip_markdown(text: str) -> str:
    """Remove common inline markdown emphasis from a line."""
    return text.replace('**', '').strip().strip('*_ ').strip()

