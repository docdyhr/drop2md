#!/usr/bin/env bash
# install.sh — Bootstrap doc2md on macOS
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== doc2md installer ==="
echo "Project: $PROJECT_DIR"

# Check Python
PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" &>/dev/null; then
  echo "Error: python3 not found. Install via https://python.org or pyenv."
  exit 1
fi

PY_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python: $PY_VERSION"

# Check brew dependencies
echo ""
echo "Checking Homebrew dependencies..."
for pkg in pandoc tesseract libmagic; do
  if brew list "$pkg" &>/dev/null 2>&1; then
    echo "  ✓ $pkg"
  else
    echo "  Installing $pkg..."
    brew install "$pkg"
  fi
done

# Create venv if needed
VENV_DIR="$PROJECT_DIR/.venv"
if [[ ! -d "$VENV_DIR" ]]; then
  echo ""
  echo "Creating virtual environment..."
  "$PYTHON" -m venv "$VENV_DIR"
fi

# Activate and install
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
echo ""
echo "Installing doc2md (core + office + dev + test)..."
pip install --quiet --upgrade pip
pip install --quiet -e "$PROJECT_DIR[dev,test,office,ocr]"

# Config
if [[ ! -f "$PROJECT_DIR/config.toml" ]]; then
  echo ""
  echo "Creating config.toml from example..."
  cp "$PROJECT_DIR/config.toml.example" "$PROJECT_DIR/config.toml"
  echo "Edit $PROJECT_DIR/config.toml to set your watch and output directories."
fi

echo ""
echo "=== Installation complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit config.toml (watch_dir and output_dir)"
echo "  2. Run: doc2md watch              # foreground"
echo "  3. Run: doc2md install-service    # background service"
echo ""
echo "To install ML-based PDF support (large download):"
echo "  pip install -e '$PROJECT_DIR[pdf-ml]'"
