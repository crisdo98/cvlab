#!/usr/bin/env zsh
set -euo pipefail

# Setup Python dependencies using Astral's uv without a traditional venv.
# This installs packages into uv's cache/environment and lets you run tools via `uvx`.
# Usage:
#   ./scripts/uv.sh

# Check for uv
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. Installing via Homebrew (macOS)..."
  if command -v brew >/dev/null 2>&1; then
    brew install uv
  else
    echo "Homebrew is not available. Install uv manually: https://docs.astral.sh/uv/install/" >&2
    exit 1
  fi
fi

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
REQS_FILE="$ROOT_DIR/requirements.txt"

# Update uv itself (correct subcommand)
uv self update || true

# Install requirements via uv pip
if [[ -f "$REQS_FILE" ]]; then
  echo "Installing Python requirements via uv from $REQS_FILE"
  uv pip install -r "$REQS_FILE"
else
  echo "No requirements.txt found at $REQS_FILE. Skipping package install."
fi

cat <<EOF

Done.
You can run Python tools using uvx, for example:
  uvx weasyprint --version
  uvx python -c "import pypandoc, pandocfilters; print('OK')"

Note: pandoc is a non-Python dependency; install it via Homebrew:
  brew install pandoc
EOF

