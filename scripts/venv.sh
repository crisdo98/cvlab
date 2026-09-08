#!/usr/bin/env zsh
set -euo pipefail

# Create a local Python virtual environment under .venv using uv and install requirements.
ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
VENV_DIR="$ROOT_DIR/.venv"
REQS_FILE="$ROOT_DIR/requirements.txt"

# Ensure uv is installed
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. Installing via Homebrew (macOS)..."
  if command -v brew >/dev/null 2>&1; then
    brew install uv
  else
    echo "Homebrew is not available. Install uv manually: https://docs.astral.sh/uv/install/" >&2
    exit 1
  fi
fi

# Update uv itself
uv self update || true

# Create or recreate the venv using uv
if [[ -d "$VENV_DIR" ]]; then
  echo "Virtual environment already exists at $VENV_DIR"
else
  echo "Creating virtual environment at $VENV_DIR with uv"
  uv venv "$VENV_DIR"
fi

# Install requirements inside the venv using uv pip
if [[ -f "$REQS_FILE" ]]; then
  echo "Installing requirements into $VENV_DIR from $REQS_FILE"
  uv pip install -r "$REQS_FILE" --python "$VENV_DIR/bin/python"
else
  echo "No requirements.txt found at $REQS_FILE. Skipping package install."
fi

cat <<EOF

Done.
To activate the environment:
  source "$VENV_DIR/bin/activate"
To deactivate:
  deactivate
EOF

