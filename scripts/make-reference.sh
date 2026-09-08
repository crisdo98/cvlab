#!/usr/bin/env zsh
set -euo pipefail

# Generate a clean Pandoc reference DOCX to control Word styles for exports.
# This avoids inheriting title/author and sets up headings and bullet lists.
# Usage:
#   ./scripts/make-reference.sh

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
OUT_REF="$ROOT_DIR/scripts/reference.docx"
TMP_MD="$ROOT_DIR/scripts/_reference_seed.md"

command -v pandoc >/dev/null 2>&1 || {
  echo "Error: pandoc is not installed. Install via 'brew install pandoc'" >&2
  exit 1
}

cat > "$TMP_MD" <<'MD'
---
title:
author:
---

# Heading 1

Normal paragraph text. This document seeds Word styles for Pandoc.

## Heading 2

- Bullet item one
- Bullet item two
- Bullet item three

### Heading 3

Another paragraph.

MD

# Create the reference DOCX
pandoc "$TMP_MD" --standalone -o "$OUT_REF"
rm -f "$TMP_MD"

echo "Created reference: $OUT_REF"

