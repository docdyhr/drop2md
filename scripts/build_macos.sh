#!/usr/bin/env bash
# scripts/build_macos.sh — Local macOS binary build helper
#
# Usage:
#   ./scripts/build_macos.sh              # build only
#   ./scripts/build_macos.sh --sign       # build + sign locally
#   CODESIGN_IDENTITY="Developer ID Application: ..." ./scripts/build_macos.sh --sign
#
# Prerequisites:
#   brew install libmagic tesseract create-dmg
#   pip install pyinstaller==6.11.1

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SIGN=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --sign) SIGN=true; shift ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

echo "=== drop2md macOS Binary Builder ==="
echo "Repo:   $REPO_ROOT"
echo "Sign:   $SIGN"
echo ""

# ── Prerequisites ────────────────────────────────────────────────────────────
for cmd in python3.11 pyinstaller; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "ERROR: $cmd not found"
    [[ "$cmd" == "pyinstaller" ]] && echo "  Install: pip install pyinstaller==6.11.1"
    exit 1
  fi
done

for pkg in libmagic tesseract; do
  if ! brew list "$pkg" &>/dev/null; then
    echo "Installing $pkg..."
    brew install "$pkg"
  fi
done

# ── Build ────────────────────────────────────────────────────────────────────
cd "$REPO_ROOT"
pyinstaller drop2md.spec --clean --noconfirm --log-level WARN

# ── Smoke test ───────────────────────────────────────────────────────────────
echo "Smoke testing..."
"$REPO_ROOT/dist/drop2md/drop2md" --version
"$REPO_ROOT/dist/drop2md/drop2md" --help > /dev/null
echo "  OK"

BUNDLE_SIZE=$(du -sh "$REPO_ROOT/dist/drop2md" | cut -f1)
echo "Bundle size: $BUNDLE_SIZE"

# ── Optional signing ─────────────────────────────────────────────────────────
if [[ "$SIGN" == "true" ]]; then
  : "${CODESIGN_IDENTITY:?Set CODESIGN_IDENTITY env var for --sign}"
  echo "Signing..."
  find dist/drop2md -name "*.so" -o -name "*.dylib" | while read -r f; do
    codesign --force --verify --timestamp \
      --options runtime \
      --entitlements "$REPO_ROOT/scripts/entitlements.plist" \
      --sign "$CODESIGN_IDENTITY" "$f"
  done
  codesign --force --verify --timestamp \
    --options runtime \
    --entitlements "$REPO_ROOT/scripts/entitlements.plist" \
    --sign "$CODESIGN_IDENTITY" \
    "dist/drop2md/drop2md"
  codesign --verify --deep --strict --verbose=2 "dist/drop2md/drop2md"
  echo "  Signing OK"
fi

echo ""
echo "Binary: $REPO_ROOT/dist/drop2md/drop2md"
echo ""
echo "To create a .dmg:"
echo "  create-dmg --volname 'drop2md' drop2md-local.dmg dist/drop2md/"
