"""Normalise free-text CV fields into well-formed Markdown blocks.

Descriptions are authored as Markdown and stored verbatim, then handed to
pandoc. Emitting them unchanged loses their structure, because Markdown does
not mean what a writer typing into a textarea assumes:

* A single newline is a *soft* break. Consecutive lines collapse into one
  paragraph, so a heading line runs into the sentence above it.
* A list needs a blank line before it. Without one, "lazy continuation" pulls
  the bullets into the preceding paragraph instead of starting a list.

Together those turned a structured description — intro, bold sub-heading,
bullets — into a single wall of text in the PDF and DOCX, while the same text
looked correct in the editor.

This inserts the block separation the author meant, and adds hard breaks so a
deliberate line break survives. It does not otherwise rewrite the Markdown:
existing blank lines, list markers and inline formatting are left alone.
"""

import re
from typing import List

#: Unordered "-", "*", "+" or ordered "1." / "1)" list markers.
_LIST_ITEM = re.compile(r"^\s{0,3}(?:[-*+]\s+|\d+[.)]\s+)")
#: ATX headings and blockquotes are block-level too.
_BLOCK_START = re.compile(r"^\s{0,3}(?:#{1,6}\s+|>)")


def _is_list_item(line: str) -> bool:
    return bool(_LIST_ITEM.match(line))


def _starts_block(line: str) -> bool:
    return _is_list_item(line) or bool(_BLOCK_START.match(line))


def normalise_markdown_block(text: str) -> str:
    """Return `text` with Markdown block structure made explicit.

    A blank line is inserted before a list or heading that follows body text,
    and a trailing backslash (pandoc's hard line break) is added to a text line
    whose newline should be preserved.
    """
    if not text or not text.strip():
        return ""

    # Normalise line endings so the rules below see one form.
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: List[str] = []

    for index, raw in enumerate(lines):
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            # Collapse runs of blank lines; one is enough to separate blocks.
            if out and out[-1] != "":
                out.append("")
            continue

        previous = out[-1] if out else ""
        starts_block = _starts_block(line)

        # A list or heading directly after body text needs a blank line, or
        # Markdown folds it into that paragraph.
        if starts_block and previous and not _starts_block(previous):
            out.append("")

        # The reverse: body text immediately after a list would otherwise be
        # read as a continuation of the last item.
        if not starts_block and previous and _is_list_item(previous):
            out.append("")
            out.append(line)
            continue

        # A plain line followed by another plain line is a deliberate break.
        # Pandoc reads a trailing backslash as a hard break; trailing spaces
        # are too easy to strip later to rely on.
        if not starts_block and index + 1 < len(lines):
            nxt = lines[index + 1].strip()
            if nxt and not _starts_block(lines[index + 1]):
                out.append(f"{line}\\")
                continue

        out.append(line)

    while out and out[-1] == "":
        out.pop()

    return "\n".join(out)
