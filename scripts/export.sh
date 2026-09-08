#!/usr/bin/env zsh
set -euo pipefail

# Export Markdown resumes in cv to PDF and DOCX using Pandoc.
# Usage:
#   ./scripts/export.sh all
#   ./scripts/export.sh <basename>  # e.g., head-of-data-engineering

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
CV_DIR="$ROOT_DIR/cv"
EXPORT_PDF_DIR="$ROOT_DIR/exports/pdf"
EXPORT_DOCX_DIR="$ROOT_DIR/exports/docx"
EXPORT_TXT_DIR="$ROOT_DIR/exports/txt"
PANDOC_DIR="$ROOT_DIR/pandoc"
TEMPLATES_DIR="$ROOT_DIR/templates"

mkdir -p "$EXPORT_PDF_DIR" "$EXPORT_DOCX_DIR" "$EXPORT_TXT_DIR" "$PANDOC_DIR" "$TEMPLATES_DIR"

command -v pandoc >/dev/null 2>&1 || {
  echo "Error: pandoc is not installed. Install via 'brew install pandoc'" >&2
  exit 1
}

# Detect a working PDF engine: prefer xelatex, fallback to tectonic
PREFERRED_ENGINE=${PDF_ENGINE:-}
PDF_ENGINE=""

function detect_engine() {
  local want="$PREFERRED_ENGINE"
  if [[ -n "$want" ]]; then
    case "$want" in
      xelatex)
        if command -v xelatex >/dev/null 2>&1; then PDF_ENGINE="xelatex"; return 0; fi
        ;;
      tectonic)
        if command -v tectonic >/dev/null 2>&1; then PDF_ENGINE="tectonic"; return 0; fi
        ;;
      *)
        echo "Warning: unknown PDF engine '$want' requested; will auto-detect." >&2
        ;;
    esac
  fi
  # Auto-detect
  if command -v xelatex >/dev/null 2>&1; then PDF_ENGINE="xelatex"; return 0; fi
  if command -v tectonic >/dev/null 2>&1; then PDF_ENGINE="tectonic"; return 0; fi
  return 1
}

detect_engine || {
  echo "Error: No PDF engine found (xelatex or tectonic)." >&2
  echo "Install one of the following:" >&2
  echo "  brew install --cask mactex         # provides xelatex (large)" >&2
  echo "  brew install basictex && tlmgr ...  # xelatex via minimal TeX + packages" >&2
  echo "  brew install tectonic              # modern TeX engine" >&2
  echo "Or set PDF_ENGINE=tectonic when running the script once installed." >&2
  exit 1
}

echo "Using PDF engine: $PDF_ENGINE"

COMMON_OPTS=(
  --from=markdown+yaml_metadata_block+smart
)

# Defaults file for consistent metadata and options
DEFAULTS_YAML="$PANDOC_DIR/defaults.yaml"

# Determine which template to use (custom or default)
LATEX_TEMPLATE="${CUSTOM_TEMPLATE:-${TEMPLATES_DIR}/cv.latex}"

# Determine which DOCX reference to use (custom or default)
DOCX_REFERENCE="${CUSTOM_DOCX_REFERENCE:-${ROOT_DIR}/scripts/reference.docx}"

# Debug: Log which reference is being used
echo "Using DOCX reference: $DOCX_REFERENCE" >&2

# PDF options vary by engine
PDF_OPTS=()
case "$PDF_ENGINE" in
  xelatex|tectonic)
    PDF_OPTS=(
      --pdf-engine=${PDF_ENGINE}
      --template="${LATEX_TEMPLATE}"
    )
    ;;
  *)
    PDF_OPTS=(--pdf-engine=${PDF_ENGINE})
    ;;
esac

DOCX_OPTS=(
  --reference-doc="${DOCX_REFERENCE}"
  --metadata title=
  --metadata author=
  --metadata date=
)

# Plain text options for ATS-friendly output
TXT_OPTS=(
  --to=plain
  --wrap=none
)

# Ensure defaults.yaml exists
if [[ ! -f "$DEFAULTS_YAML" ]]; then
  cat > "$DEFAULTS_YAML" <<'YAML'
from: markdown+yaml_metadata_block+smart
number-sections: false
toc: false
variables:
  geometry: margin=0.8in
  mainfont: Helvetica Neue
  monofont: Menlo
  fontsize: 11pt
metadata:
  lang: en-US
  colorlinks: true
YAML
fi

# Ensure a LaTeX template exists (used for xelatex/tectonic)
if [[ ! -f "${TEMPLATES_DIR}/cv.latex" ]]; then
  cat > "${TEMPLATES_DIR}/cv.latex" <<'TEX'
\documentclass[11pt]{article}
\usepackage[margin=0.8in]{geometry}
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage{hyperref}
\usepackage{fontspec}
\usepackage{ragged2e} % enable \justifying for full justification even in lists
\setmainfont{Helvetica Neue}
\setsansfont{Helvetica Neue}
\setmonofont{Menlo}

% Section styling
\titleformat{\section}{\bfseries\Large}{}{0pt}{}
\titlespacing*{\section}{0pt}{10pt}{6pt}
\titleformat{\subsection}{\bfseries\normalsize}{}{0pt}{}
\titlespacing*{\subsection}{0pt}{8pt}{4pt}

% List spacing
\setlist{nosep}

% Disable page numbers
\pagenumbering{gobble}

% Pandoc variables
$if(title)$\title{$title$}$endif$
$if(author)$\author{$for(author)$$author$$sep$\\$endfor$}$endif$
$if(date)$\date{$date$}$endif$

\begin{document}
$if(title)$\maketitle$endif$
\justifying
$body$
\end{document}
TEX
fi

# Ensure a richer DOCX reference document exists
if [[ ! -f "${ROOT_DIR}/scripts/reference.docx" ]]; then
  echo "Creating default DOCX reference..."
  pandoc -o "${ROOT_DIR}/scripts/reference.docx" <<'MD'
---
title: Resume
---

# Heading 1 Sample

Normal paragraph text.

## Heading 2 Sample

- Bullet
- Points

**Bold** and _italic_ styles.
MD
  # Tune the reference to set styles including justification
  if command -v python3 >/dev/null 2>&1; then
    python3 "${ROOT_DIR}/scripts/tune_docx.py" "${ROOT_DIR}/scripts/reference.docx" || true
  fi
fi

PANDOC_FILTER="$PANDOC_DIR/no_em_dash.lua"
CONTACT_FILTER="$PANDOC_DIR/contact_info.lua"

function export_one() {
  local base
  base="$1"
  # Optional second argument limits output to one format (pdf|docx|txt);
  # omitted or "all" produces every format
  local only
  only="${2:-all}"
  local src
  src="$CV_DIR/${base}.md"
  if [[ ! -f "$src" ]]; then
    echo "Skip: source not found $src" >&2
    return 1
  fi
  local ts
  ts=$(date +%Y%m%d-%H%M%S)
  local pdf_out
  pdf_out="$EXPORT_PDF_DIR/${base}-${ts}.pdf"
  local docx_out
  docx_out="$EXPORT_DOCX_DIR/${base}-${ts}.docx"
  local txt_out
  txt_out="$EXPORT_TXT_DIR/${base}-${ts}.txt"

  if [[ "$only" == "all" || "$only" == "pdf" ]]; then
    echo "Exporting $src -> $pdf_out"
    pandoc "$src" "${COMMON_OPTS[@]}" --defaults "$DEFAULTS_YAML" --lua-filter "$PANDOC_FILTER" --lua-filter "$CONTACT_FILTER" "${PDF_OPTS[@]}" -o "$pdf_out"
  fi

  if [[ "$only" == "all" || "$only" == "docx" ]]; then
    echo "Exporting $src -> $docx_out"
    pandoc "$src" "${COMMON_OPTS[@]}" --defaults "$DEFAULTS_YAML" --lua-filter "$PANDOC_FILTER" --lua-filter "$CONTACT_FILTER" "${DOCX_OPTS[@]}" -o "$docx_out"
  fi

  if [[ "$only" == "all" || "$only" == "txt" ]]; then
    echo "Exporting $src -> $txt_out"
    local tmp_txt
    tmp_txt=$(mktemp)
    pandoc "$src" "${COMMON_OPTS[@]}" --defaults "$DEFAULTS_YAML" --lua-filter "$CONTACT_FILTER" "${TXT_OPTS[@]}" -o "$tmp_txt"
    if [[ -x "$ROOT_DIR/scripts/normalize_txt.sh" ]]; then
      "$ROOT_DIR/scripts/normalize_txt.sh" "$tmp_txt" "$txt_out"
      rm -f "$tmp_txt"
    else
      mv "$tmp_txt" "$txt_out"
    fi
  fi
}

function export_all() {
  local -a md_files
  md_files=()
  # Safely gather markdown basenames
  while IFS= read -r -d '' f; do
    md_files+=("${f:t}")
  done < <(find "$CV_DIR" -maxdepth 1 -type f -name '*.md' -print0)

  if [[ ${#md_files[@]} -eq 0 ]]; then
    echo "No Markdown files found in $CV_DIR" >&2
    exit 1
  fi
  local f
  for f in "${md_files[@]}"; do
    export_one "${f%.md}" "${1:-all}"
  done
}

case "${1:-}" in
  all)
    export_all
    ;;
  "")
    echo "Usage: $0 all | <basename> [pdf|docx|txt]" >&2
    exit 2
    ;;
  *)
    export_one "$1" "${2:-all}"
    ;;
esac

echo "Done. Outputs in: $EXPORT_PDF_DIR, $EXPORT_DOCX_DIR and $EXPORT_TXT_DIR"
