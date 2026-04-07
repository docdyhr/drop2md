"""Integration smoke tests for the Visual Enhancement Pipeline (VEP).

Tests three providers (Ollama, OpenAI, Gemini) against real fixture documents:
  - /Users/thomas/Desktop/Cliq Digital test.pdf        (PDF with charts)
  - /Users/thomas/Desktop/How to Use LLMs to Detect macOS Malware - Training.pptx

Run selectively:
    pytest tests/integration/test_vep_smoke.py -v -m vep
    pytest tests/integration/test_vep_smoke.py -v -m "vep and ollama"
    pytest tests/integration/test_vep_smoke.py -v -m "vep and openai"
    pytest tests/integration/test_vep_smoke.py -v -m "vep and gemini"

All tests are skipped automatically if the required provider or fixture is
unavailable — nothing blocks CI.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

PDF_FIXTURE = Path("/Users/thomas/Desktop/Cliq Digital test.pdf")
PPTX_FIXTURE = Path(
    "/Users/thomas/Desktop/How to Use LLMs to Detect macOS Malware - Training.pptx"
)

# ---------------------------------------------------------------------------
# Provider availability helpers
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3-vl:8b"

OPENAI_MODEL = "gpt-4o-mini"
OPENAI_BASE_URL = "https://api.openai.com/v1"

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def _ollama_model_available() -> bool:
    try:
        import httpx
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        tags = r.json().get("models", [])
        return any(OLLAMA_MODEL in t.get("name", "") for t in tags)
    except Exception:
        return False


def _openai_available() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def _gemini_available() -> bool:
    return bool(
        os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    )


skip_no_pdf = pytest.mark.skipif(
    not PDF_FIXTURE.exists(), reason=f"PDF fixture not found: {PDF_FIXTURE}"
)
skip_no_pptx = pytest.mark.skipif(
    not PPTX_FIXTURE.exists(), reason=f"PPTX fixture not found: {PPTX_FIXTURE}"
)
skip_no_ollama = pytest.mark.skipif(
    not _ollama_model_available(),
    reason=f"Ollama model {OLLAMA_MODEL!r} not available",
)
skip_no_openai = pytest.mark.skipif(
    not _openai_available(), reason="OPENAI_API_KEY not set"
)
skip_no_gemini = pytest.mark.skipif(
    not _gemini_available(), reason="GEMINI_API_KEY / GOOGLE_API_KEY not set"
)


# ---------------------------------------------------------------------------
# Config builders — real Config dataclasses (not MagicMock)
# ---------------------------------------------------------------------------

def _ollama_config() -> object:
    from drop2md.config import (
        ClaudeConfig, Config, LoggingConfig, OcrConfig, OfficeConfig,
        OllamaConfig, OpenAIConfig, OutputConfig, PathsConfig, PdfConfig,
        VisualConfig,
    )
    return Config(
        paths=PathsConfig(),
        pdf=PdfConfig(use_marker=False, use_docling=False),
        office=OfficeConfig(),
        ocr=OcrConfig(enabled=False),
        ollama=OllamaConfig(
            enabled=True,
            base_url=OLLAMA_BASE_URL,
            model=OLLAMA_MODEL,
            timeout_seconds=300,
            provider="ollama",
            validate_tables=False,  # qwen3-vl:8b is slow; table tests covered separately
        ),
        openai=OpenAIConfig(),
        claude=ClaudeConfig(),
        output=OutputConfig(add_frontmatter=False),
        logging=LoggingConfig(level="WARNING"),
        visual=VisualConfig(
            enabled=True,
            classify=True,
            chart_description=True,
            diagram_to_mermaid=True,
            formula_to_latex=True,
            table_image_to_gfm=True,
            screenshot_description=True,
        ),
    )


def _openai_config() -> object:
    from drop2md.config import (
        ClaudeConfig, Config, LoggingConfig, OcrConfig, OfficeConfig,
        OllamaConfig, OpenAIConfig, OutputConfig, PathsConfig, PdfConfig,
        VisualConfig,
    )
    return Config(
        paths=PathsConfig(),
        pdf=PdfConfig(use_marker=False, use_docling=False),
        office=OfficeConfig(),
        ocr=OcrConfig(enabled=False),
        ollama=OllamaConfig(
            enabled=True,
            provider="openai",
            api_key=os.environ.get("OPENAI_API_KEY", ""),
        ),
        openai=OpenAIConfig(
            model=OPENAI_MODEL,
            base_url=OPENAI_BASE_URL,
            timeout_seconds=60,
        ),
        claude=ClaudeConfig(),
        output=OutputConfig(add_frontmatter=False),
        logging=LoggingConfig(level="WARNING"),
        visual=VisualConfig(
            enabled=True,
            classify=True,
            chart_description=True,
            diagram_to_mermaid=True,
            formula_to_latex=True,
            table_image_to_gfm=True,
            screenshot_description=True,
        ),
    )


def _gemini_config() -> object:
    from drop2md.config import (
        ClaudeConfig, Config, LoggingConfig, OcrConfig, OfficeConfig,
        OllamaConfig, OpenAIConfig, OutputConfig, PathsConfig, PdfConfig,
        VisualConfig,
    )
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
    return Config(
        paths=PathsConfig(),
        pdf=PdfConfig(use_marker=False, use_docling=False),
        office=OfficeConfig(),
        ocr=OcrConfig(enabled=False),
        ollama=OllamaConfig(
            enabled=True,
            provider="gemini",
            api_key=api_key,
        ),
        openai=OpenAIConfig(
            model=GEMINI_MODEL,
            base_url=GEMINI_BASE_URL,
            timeout_seconds=60,
        ),
        claude=ClaudeConfig(),
        output=OutputConfig(add_frontmatter=False),
        logging=LoggingConfig(level="WARNING"),
        visual=VisualConfig(
            enabled=True,
            classify=True,
            chart_description=True,
            diagram_to_mermaid=True,
            formula_to_latex=True,
            table_image_to_gfm=True,
            screenshot_description=True,
        ),
    )


# ---------------------------------------------------------------------------
# Shared assertion helpers
# ---------------------------------------------------------------------------

def _assert_vep_applied(markdown: str, images: list[Path], label: str) -> None:
    """Assert that VEP produced non-empty alt-text for at least one image.

    Checks both in-place replacements and appended image blocks (for converters
    like pdfplumber/MarkItDown that do not embed image refs in their markdown).
    """
    found_meaningful = False
    for img in images:
        base = f"./{img.parent.name}/{img.name}"
        if base not in markdown:
            continue  # image not referenced at all — skip
        # Find the alt-text: between ![ and ]( base)
        idx = markdown.find(base)
        start = markdown.rfind("![", 0, idx)
        if start == -1:
            continue
        ref_text = markdown[start + 2:idx - 2]  # between ![ and ](
        if len(ref_text.strip()) > 5:
            found_meaningful = True
            break

    assert found_meaningful, (
        f"[{label}] VEP did not produce meaningful alt-text (>5 chars) for any image.\n"
        f"Images: {[i.name for i in images]}\n"
        f"Markdown snippet: {markdown[:500]}"
    )


# ===========================================================================
# PDF smoke tests
# ===========================================================================

@pytest.mark.vep
@pytest.mark.ollama
@pytest.mark.timeout(600)
@skip_no_pdf
@skip_no_ollama
def test_vep_pdf_ollama(tmp_path: Path) -> None:
    """PDF → LegacyPdfConverter (pdfplumber + PyMuPDF image pass) → VEP (Ollama).

    Limited to the first 3 images — local 8B vision models are slow and a
    full-document run can exceed 10 minutes on CPU-only hardware.
    """
    _run_pdf_smoke(PDF_FIXTURE, tmp_path, _ollama_config(), "ollama", max_images=3)


@pytest.mark.vep
@pytest.mark.openai
@pytest.mark.timeout(120)
@skip_no_pdf
@skip_no_openai
def test_vep_pdf_openai(tmp_path: Path) -> None:
    """PDF → LegacyPdfConverter → VEP (OpenAI gpt-4o-mini)."""
    _run_pdf_smoke(PDF_FIXTURE, tmp_path, _openai_config(), "openai")


@pytest.mark.vep
@pytest.mark.gemini
@pytest.mark.timeout(360)
@skip_no_pdf
@skip_no_gemini
def test_vep_pdf_gemini(tmp_path: Path) -> None:
    """PDF → LegacyPdfConverter → VEP (Gemini gemini-2.5-flash)."""
    _run_pdf_smoke(PDF_FIXTURE, tmp_path, _gemini_config(), "gemini")


def _run_pdf_smoke(
    pdf_path: Path,
    tmp_path: Path,
    config: object,
    label: str,
    max_images: int | None = None,
) -> None:
    from drop2md.converters import ConverterResult
    from drop2md.converters.legacy_pdf import LegacyPdfConverter
    from drop2md.enhance import enhance

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    converter = LegacyPdfConverter()
    result = converter.convert(pdf_path, output_dir)

    assert result.markdown.strip(), f"[{label}] PDF converter produced empty markdown"
    assert len(result.markdown) > 100, f"[{label}] PDF markdown suspiciously short"

    print(f"\n[{label}] PDF: extracted {len(result.images)} image(s) via PyMuPDF")

    if not result.images:
        pytest.skip(f"[{label}] PDF fixture has no extractable images — VEP not exercised")

    # Optionally cap images to keep slow local models within test timeout
    images = result.images[:max_images] if max_images else result.images
    if max_images and len(result.images) > max_images:
        print(f"[{label}] Capping to first {max_images} of {len(result.images)} images")
    capped = ConverterResult(
        markdown=result.markdown,
        images=images,
        converter_used=result.converter_used,
        metadata=result.metadata,
        warnings=result.warnings,
    )

    enhanced = enhance(capped, config)

    assert enhanced.markdown.strip(), f"[{label}] VEP returned empty markdown"
    _assert_vep_applied(enhanced.markdown, images, label)

    sample = enhanced.markdown[:800]
    print(f"\n[{label}] VEP output sample:\n{sample}\n")


# ===========================================================================
# PPTX smoke tests
# ===========================================================================

@pytest.mark.vep
@pytest.mark.ollama
@pytest.mark.timeout(600)
@skip_no_pptx
@skip_no_ollama
def test_vep_pptx_ollama(tmp_path: Path) -> None:
    """PPTX → OfficeConverter (embedded image extraction) → VEP (Ollama).

    Limited to the first 3 images — local 8B vision models are slow.
    """
    _run_pptx_smoke(PPTX_FIXTURE, tmp_path, _ollama_config(), "ollama", max_images=3)


@pytest.mark.vep
@pytest.mark.openai
@pytest.mark.timeout(120)
@skip_no_pptx
@skip_no_openai
def test_vep_pptx_openai(tmp_path: Path) -> None:
    """PPTX → OfficeConverter → VEP (OpenAI gpt-4o-mini)."""
    _run_pptx_smoke(PPTX_FIXTURE, tmp_path, _openai_config(), "openai")


@pytest.mark.vep
@pytest.mark.gemini
@pytest.mark.timeout(120)
@skip_no_pptx
@skip_no_gemini
def test_vep_pptx_gemini(tmp_path: Path) -> None:
    """PPTX → OfficeConverter → VEP (Gemini gemini-2.5-flash)."""
    _run_pptx_smoke(PPTX_FIXTURE, tmp_path, _gemini_config(), "gemini")


def _run_pptx_smoke(
    pptx_path: Path,
    tmp_path: Path,
    config: object,
    label: str,
    max_images: int | None = None,
) -> None:
    from drop2md.converters import ConverterResult
    from drop2md.converters.office import OfficeConverter
    from drop2md.enhance import enhance

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    converter = OfficeConverter()
    result = converter.convert(pptx_path, output_dir)

    assert result.markdown.strip(), f"[{label}] PPTX converter produced empty markdown"

    print(f"\n[{label}] PPTX: extracted {len(result.images)} embedded image(s)")

    if not result.images:
        pytest.skip(
            f"[{label}] PPTX has no extractable embedded images — "
            "ensure python-pptx is installed (pip install 'drop2md[office-images]')"
        )

    images = result.images[:max_images] if max_images else result.images
    if max_images and len(result.images) > max_images:
        print(f"[{label}] Capping to first {max_images} of {len(result.images)} images")
    capped = ConverterResult(
        markdown=result.markdown,
        images=images,
        converter_used=result.converter_used,
        metadata=result.metadata,
        warnings=result.warnings,
    )

    enhanced = enhance(capped, config)

    assert enhanced.markdown.strip(), f"[{label}] VEP returned empty markdown"
    _assert_vep_applied(enhanced.markdown, images, label)

    print(f"[{label}] Extracted images: {[i.name for i in images]}")
    sample = enhanced.markdown[:1200]
    print(f"\n[{label}] VEP output sample:\n{sample}\n")


# ===========================================================================
# Provider-level visual classification tests (fast, no full conversion)
# ===========================================================================

@pytest.mark.vep
@pytest.mark.ollama
@pytest.mark.timeout(120)
@skip_no_ollama
def test_vep_classifier_ollama(tmp_path: Path) -> None:
    """Classifier assigns a valid visual type to a real image (Ollama)."""
    _run_classifier_smoke(tmp_path, _ollama_config(), "ollama")


@pytest.mark.vep
@pytest.mark.openai
@pytest.mark.timeout(60)
@skip_no_openai
def test_vep_classifier_openai(tmp_path: Path) -> None:
    """Classifier assigns a valid visual type to a real image (OpenAI)."""
    _run_classifier_smoke(tmp_path, _openai_config(), "openai")


@pytest.mark.vep
@pytest.mark.gemini
@pytest.mark.timeout(60)
@skip_no_gemini
def test_vep_classifier_gemini(tmp_path: Path) -> None:
    """Classifier assigns a valid visual type to a real image (Gemini)."""
    _run_classifier_smoke(tmp_path, _gemini_config(), "gemini")


def _run_classifier_smoke(tmp_path: Path, config: object, label: str) -> None:
    """Extract one image from the PPTX (if available) and classify it."""
    from drop2md.enhance import _classify_images  # type: ignore[attr-defined]

    # Use PPTX fixture if available, else fall back to PDF
    if PPTX_FIXTURE.exists():
        from drop2md.converters.office import _extract_pptx_images
        img_dir = tmp_path / "images"
        img_dir.mkdir()
        images = _extract_pptx_images(PPTX_FIXTURE, tmp_path)
    elif PDF_FIXTURE.exists():
        from drop2md.utils.image_extractor import extract_pdf_images
        images = extract_pdf_images(PDF_FIXTURE, tmp_path)
    else:
        pytest.skip("No fixture files available for classifier test")

    if not images:
        pytest.skip(f"[{label}] No images extracted from fixture for classifier test")

    # Classify just the first image to keep the test fast
    test_images = images[:1]
    classifications = _classify_images(test_images, config)

    valid_types = {"chart", "diagram", "formula", "table-image", "screenshot", "photo"}
    for img, vtype in classifications.items():
        assert vtype in valid_types, (
            f"[{label}] Unexpected classification {vtype!r} for {img.name}"
        )
        print(f"\n[{label}] {img.name} → {vtype}")
