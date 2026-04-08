# drop2md.spec — PyInstaller build spec
#
# Builds a self-contained macOS CLI binary (onedir bundle) containing:
#   - drop2md CLI (typer/click)
#   - pdf-light tier (pymupdf4llm / PyMuPDF)
#   - office converters (markitdown)
#   - OCR support (pytesseract + Pillow) — tesseract binary is NOT bundled;
#     it is declared as a Homebrew dependency
#   - libmagic.1.dylib + magic database (bundled from Homebrew prefix)
#
# NOT included: marker-pdf, docling, torch (~2 GB). Users who want ML-quality
# PDF conversion should install via pip: pip install 'drop2md[pdf-ml]'
#
# Build:
#   pyinstaller drop2md.spec --clean --noconfirm
# Or:
#   ./scripts/build_macos.sh

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

_homebrew_prefix = os.environ.get("HOMEBREW_PREFIX", "/opt/homebrew")

# ── Data files ────────────────────────────────────────────────────────────────

datas = []

# Package service templates (loaded via importlib.resources in cli.py)
datas += [
    ("src/drop2md/services/Info.plist.template",      "drop2md/services"),
    ("src/drop2md/services/document.wflow.template",  "drop2md/services"),
]

# launchd plist template (loaded via sys._MEIPASS path in install_service)
datas += [
    ("launchd/com.thomasdyhr.drop2md.plist.template", "launchd"),
]

# libmagic dylib + magic database
_libmagic = f"{_homebrew_prefix}/lib/libmagic.1.dylib"
_magic_db  = f"{_homebrew_prefix}/share/misc"
if Path(_libmagic).exists():
    datas += [(_libmagic, ".")]
if Path(f"{_magic_db}/magic.mgc").exists():
    datas += [
        (f"{_magic_db}/magic",     "magic_db"),
        (f"{_magic_db}/magic.mgc", "magic_db"),
    ]

# PyMuPDF, pdfplumber, markitdown data files
datas += collect_data_files("pymupdf")
datas += collect_data_files("pymupdf4llm")
datas += collect_data_files("markitdown")
datas += collect_data_files("pdfplumber")
datas += collect_data_files("pdfminer")
datas += collect_data_files("magic")

# ── Hidden imports ────────────────────────────────────────────────────────────

hiddenimports = [
    # typer / click
    "typer",
    "typer.main",
    "click",
    "click.core",
    "click.decorators",
    "click.exceptions",
    # watchdog macOS FSEvents backend
    "watchdog.observers.fsevents",
    "watchdog.observers.fsevents2",
    "_watchdog_fsevents",
    # mcp server
    "mcp",
    "mcp.server",
    "mcp.server.fastmcp",
    "starlette",
    "starlette.applications",
    "starlette.routing",
    "anyio",
    "anyio._backends._asyncio",
    # pdfplumber / pdfminer
    "pdfminer",
    "pdfminer.high_level",
    "pdfminer.layout",
    "pdfminer.converter",
    "pdfminer.pdfpage",
    "pdfminer.pdfinterp",
    "pdfminer.pdfdocument",
    # markitdown converters (lazy imports)
    "markitdown",
    # pytesseract + Pillow
    "pytesseract",
    "PIL",
    "PIL.Image",
    # httpx, psutil, html2text
    "httpx",
    "psutil",
    "psutil._psutil_osx",
    "html2text",
    # tomllib (stdlib 3.11+)
    "tomllib",
    # python-docx / python-pptx for embedded image extraction
    "docx",
    "pptx",
    "pptx.util",
]

hiddenimports += collect_submodules("mcp")
hiddenimports += collect_submodules("watchdog")
hiddenimports += collect_submodules("pdfminer")

# ── Binaries ──────────────────────────────────────────────────────────────────

# PyMuPDF ships libmupdf.dylib inside the wheel; treat it as a binary so
# PyInstaller fixes up the @rpath references with install_name_tool.
_site = Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
_pymupdf_lib = _site / "pymupdf" / "libmupdf.dylib"
_pymupdf_cpp = _site / "pymupdf" / "libmupdfcpp.so"

binaries = []
if _pymupdf_lib.exists():
    binaries.append((str(_pymupdf_lib), "pymupdf"))
if _pymupdf_cpp.exists():
    binaries.append((str(_pymupdf_cpp), "pymupdf"))

# ── Analysis ──────────────────────────────────────────────────────────────────

a = Analysis(
    ["src/drop2md/cli.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=["scripts/pyinstaller_hooks"],
    runtime_hooks=["scripts/pyinstaller_hooks/rthook_magic.py"],
    excludes=[
        "torch", "torchvision", "torchaudio",
        "transformers", "tokenizers",
        "marker", "docling",
        "tkinter", "wx", "PyQt5", "PyQt6", "PySide2", "PySide6",
        "pytest", "mypy", "ruff",
        "IPython", "jupyter",
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="drop2md",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,       # UPX corrupts Apple Silicon binaries — never enable
    console=True,
    target_arch=None,        # inherits from the running Python (arm64 on macos-14)
    codesign_identity=None,  # signed externally after collecting
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="drop2md",
)
