#!/usr/bin/env bash
# Normalize plain text CV for ATS compatibility
# - Convert UTF-8 punctuation to ASCII (iconv transliteration)
# - Normalize bullets to '- '
# - Collapse multiple spaces
# - Normalize UK mobile number to E.164
# Usage: normalize_txt.sh <input_txt> <output_txt>
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <input_txt> <output_txt>" >&2
  exit 2
fi

in="$1"
out="$2"

tmp1=$(mktemp)
cp "$in" "$tmp1"

# 1) Convert to ASCII with transliteration
tmp2=$(mktemp)
if iconv -f UTF-8 -t ASCII//TRANSLIT "$tmp1" > "$tmp2" 2>/dev/null; then
  mv "$tmp2" "$tmp1"
else
  rm -f "$tmp2"
fi

# 2) Normalize bullets and collapse spaces
sed -i \
  -e 's/^\s*[•\*]\s\{0,\}/- /g' \
  -e 's/^\s*-\s/- /g' \
  -e 's/[[:space:]]\{2,\}/ /g' \
  "$tmp1"

# 3) Normalize UK mobile phone numbers to E.164 format
# This is a generic pattern - update for your specific phone number format
# sed -i \
#   -e 's/0\?77[[:space:]]*\([0-9][0-9]\)[[:space:]]*\([0-9][0-9]\)[[:space:]]*\([0-9][0-9]\)[[:space:]]*\([0-9][0-9]\)/+447\1\2\3\4/g' \
#   "$tmp1"

# 4) Convert any remaining Unicode em/en dashes to simple hyphen
sed -i -e 's/—/-/g' -e 's/–/-/g' "$tmp1"

mv "$tmp1" "$out"
