"""Unit tests for the v0.3 Visual Enhancement Pipeline (VEP).

All AI provider calls are mocked via httpx.post (Ollama path) so tests run
fully offline. The _cfg() helper constructs a MagicMock config that mirrors
the real Config structure used by make_provider() and enhance().
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from drop2md.converters import ConverterResult
from drop2md.enhance import (
    _apply_vep,
    _classify_images,
    _describe_chart,
    _describe_screenshot,
    _diagram_to_mermaid,
    _formula_to_latex,
    _table_image_to_gfm,
    enhance,
)

# ---------------------------------------------------------------------------
# Config factory
# ---------------------------------------------------------------------------


def _cfg(
    *,
    ollama_enabled: bool = True,
    visual_enabled: bool = True,
    classify: bool = True,
    chart_description: bool = True,
    diagram_to_mermaid: bool = True,
    formula_to_latex: bool = True,
    table_image_to_gfm: bool = True,
    screenshot_description: bool = True,
    provider: str = "ollama",
) -> MagicMock:
    cfg = MagicMock()
    cfg.ollama.enabled = ollama_enabled
    cfg.ollama.provider = provider
    cfg.ollama.model = "test-model"
    cfg.ollama.base_url = "http://localhost:11434"
    cfg.ollama.timeout_seconds = 5
    cfg.ollama.api_key = ""
    cfg.openai.model = "gpt-4o-mini"
    cfg.openai.base_url = "https://api.openai.com/v1"
    cfg.openai.timeout_seconds = 5
    cfg.claude.model = "claude-haiku-4-5-20251001"
    cfg.claude.timeout_seconds = 5
    cfg.visual.enabled = visual_enabled
    cfg.visual.classify = classify
    cfg.visual.chart_description = chart_description
    cfg.visual.diagram_to_mermaid = diagram_to_mermaid
    cfg.visual.formula_to_latex = formula_to_latex
    cfg.visual.table_image_to_gfm = table_image_to_gfm
    cfg.visual.screenshot_description = screenshot_description
    return cfg


def _mock_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"response": text}
    resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# VEP-1: Classifier
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_classify_images_returns_known_type(tmp_path):
    img = tmp_path / "fig.png"
    img.write_bytes(b"fake")
    with patch("httpx.post", return_value=_mock_response("chart")):
        result = _classify_images([img], _cfg())
    assert result[img] == "chart"


@pytest.mark.unit
@pytest.mark.parametrize(
    "label", ["chart", "diagram", "formula", "table-image", "screenshot", "photo"]
)
def test_classify_images_accepts_all_valid_types(tmp_path, label):
    img = tmp_path / "img.png"
    img.write_bytes(b"fake")
    with patch("httpx.post", return_value=_mock_response(label)):
        result = _classify_images([img], _cfg())
    assert result[img] == label


@pytest.mark.unit
def test_classify_images_falls_back_to_photo_for_unknown(tmp_path):
    img = tmp_path / "img.png"
    img.write_bytes(b"fake")
    with patch("httpx.post", return_value=_mock_response("widget")):
        result = _classify_images([img], _cfg())
    assert result[img] == "photo"


@pytest.mark.unit
def test_classify_images_falls_back_to_photo_on_error(tmp_path):
    import httpx

    img = tmp_path / "img.png"
    img.write_bytes(b"fake")
    with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
        result = _classify_images([img], _cfg())
    assert result[img] == "photo"


@pytest.mark.unit
def test_classify_missing_image_returns_photo(tmp_path):
    img = tmp_path / "nonexistent.png"
    # do NOT create the file
    with patch("httpx.post") as mock_post:
        result = _classify_images([img], _cfg())
    mock_post.assert_not_called()
    assert result[img] == "photo"


@pytest.mark.unit
def test_classify_strips_punctuation_from_model_output(tmp_path):
    img = tmp_path / "img.png"
    img.write_bytes(b"fake")
    # Model appends a period
    with patch("httpx.post", return_value=_mock_response("chart.")):
        result = _classify_images([img], _cfg())
    assert result[img] == "chart"


# ---------------------------------------------------------------------------
# VEP-2a: Chart description
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_describe_chart_returns_prose(tmp_path):
    img = tmp_path / "chart.png"
    img.write_bytes(b"fake")
    prose = "A bar chart showing monthly revenue. January was highest at $120k."
    with patch("httpx.post", return_value=_mock_response(prose)):
        result = _describe_chart(img, _cfg())
    assert result == prose


@pytest.mark.unit
def test_describe_chart_returns_empty_on_error(tmp_path):
    import httpx

    img = tmp_path / "chart.png"
    img.write_bytes(b"fake")
    with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
        result = _describe_chart(img, _cfg())
    assert result == ""


# ---------------------------------------------------------------------------
# VEP-2b: Diagram to Mermaid
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_diagram_to_mermaid_returns_mermaid_block(tmp_path):
    img = tmp_path / "flow.png"
    img.write_bytes(b"fake")
    mermaid = "```mermaid\nflowchart LR\n  A --> B --> C\n```"
    with patch("httpx.post", return_value=_mock_response(mermaid)):
        result = _diagram_to_mermaid(img, _cfg())
    assert "mermaid" in result


@pytest.mark.unit
def test_diagram_to_mermaid_returns_empty_on_error(tmp_path):
    import httpx

    img = tmp_path / "flow.png"
    img.write_bytes(b"fake")
    with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
        result = _diagram_to_mermaid(img, _cfg())
    assert result == ""


# ---------------------------------------------------------------------------
# VEP-2c: Formula to LaTeX
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_formula_to_latex_returns_latex_block(tmp_path):
    img = tmp_path / "eq.png"
    img.write_bytes(b"fake")
    latex = "$$E = mc^2$$"
    with patch("httpx.post", return_value=_mock_response(latex)):
        result = _formula_to_latex(img, _cfg())
    assert result == latex


@pytest.mark.unit
def test_formula_to_latex_returns_empty_on_error(tmp_path):
    import httpx

    img = tmp_path / "eq.png"
    img.write_bytes(b"fake")
    with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
        result = _formula_to_latex(img, _cfg())
    assert result == ""


# ---------------------------------------------------------------------------
# VEP-2d: Table image to GFM
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_table_image_to_gfm_returns_pipe_table(tmp_path):
    img = tmp_path / "tbl.png"
    img.write_bytes(b"fake")
    table = "| A | B |\n| --- | --- |\n| 1 | 2 |"
    with patch("httpx.post", return_value=_mock_response(table)):
        result = _table_image_to_gfm(img, _cfg())
    assert "|" in result and "---" in result


@pytest.mark.unit
def test_table_image_to_gfm_returns_empty_when_no_pipes(tmp_path):
    img = tmp_path / "tbl.png"
    img.write_bytes(b"fake")
    with patch("httpx.post", return_value=_mock_response("Sorry, cannot read.")):
        result = _table_image_to_gfm(img, _cfg())
    assert result == ""


@pytest.mark.unit
def test_table_image_to_gfm_returns_empty_on_error(tmp_path):
    import httpx

    img = tmp_path / "tbl.png"
    img.write_bytes(b"fake")
    with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
        result = _table_image_to_gfm(img, _cfg())
    assert result == ""


# ---------------------------------------------------------------------------
# VEP-2e: Screenshot description
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_describe_screenshot_returns_prose(tmp_path):
    img = tmp_path / "ss.png"
    img.write_bytes(b"fake")
    prose = "A screenshot of a terminal showing a Python traceback."
    with patch("httpx.post", return_value=_mock_response(prose)):
        result = _describe_screenshot(img, _cfg())
    assert result == prose


@pytest.mark.unit
def test_describe_screenshot_returns_empty_on_error(tmp_path):
    import httpx

    img = tmp_path / "ss.png"
    img.write_bytes(b"fake")
    with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
        result = _describe_screenshot(img, _cfg())
    assert result == ""


# ---------------------------------------------------------------------------
# _apply_vep — integration of classifier + dispatch
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_apply_vep_replaces_empty_alt_for_chart(tmp_path):
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    img = img_dir / "fig.png"
    img.write_bytes(b"fake")

    markdown = f"![](./{img.parent.name}/{img.name})"
    prose = "A line chart showing user growth over 12 months."

    def _post(url, **kwargs):
        payload = kwargs.get("json", {})
        prompt = payload.get("prompt", "")
        if "Classify" in prompt:
            return _mock_response("chart")
        return _mock_response(prose)

    with patch("httpx.post", side_effect=_post):
        result = _apply_vep(markdown, [img], _cfg())

    assert prose in result
    assert "![" in result


@pytest.mark.unit
def test_apply_vep_inserts_mermaid_for_diagram(tmp_path):
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    img = img_dir / "flow.png"
    img.write_bytes(b"fake")

    markdown = f"![](./{img.parent.name}/{img.name})"
    mermaid = "```mermaid\nflowchart LR\n  A --> B\n```"

    def _post(url, **kwargs):
        payload = kwargs.get("json", {})
        prompt = payload.get("prompt", "")
        if "Classify" in prompt:
            return _mock_response("diagram")
        return _mock_response(mermaid)

    with patch("httpx.post", side_effect=_post):
        result = _apply_vep(markdown, [img], _cfg())

    assert "mermaid" in result


@pytest.mark.unit
def test_apply_vep_inserts_latex_for_formula(tmp_path):
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    img = img_dir / "eq.png"
    img.write_bytes(b"fake")

    markdown = f"![](./{img.parent.name}/{img.name})"
    latex = "$$E = mc^2$$"

    def _post(url, **kwargs):
        payload = kwargs.get("json", {})
        prompt = payload.get("prompt", "")
        if "Classify" in prompt:
            return _mock_response("formula")
        return _mock_response(latex)

    with patch("httpx.post", side_effect=_post):
        result = _apply_vep(markdown, [img], _cfg())

    assert "$$" in result


@pytest.mark.unit
def test_apply_vep_inserts_gfm_table_for_table_image(tmp_path):
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    img = img_dir / "tbl.png"
    img.write_bytes(b"fake")

    markdown = f"![](./{img.parent.name}/{img.name})"
    table = "| X | Y |\n| --- | --- |\n| 1 | 2 |"

    def _post(url, **kwargs):
        payload = kwargs.get("json", {})
        prompt = payload.get("prompt", "")
        if "Classify" in prompt:
            return _mock_response("table-image")
        return _mock_response(table)

    with patch("httpx.post", side_effect=_post):
        result = _apply_vep(markdown, [img], _cfg())

    assert "| X | Y |" in result


@pytest.mark.unit
def test_apply_vep_skips_classify_when_disabled(tmp_path):
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    img = img_dir / "fig.png"
    img.write_bytes(b"fake")

    markdown = f"![](./{img.parent.name}/{img.name})"

    with patch("httpx.post", return_value=_mock_response("A photo.")):
        result = _apply_vep(markdown, [img], _cfg(classify=False))

    # With classify=False we fall back to _inject_image_captions (one-sentence)
    assert "A photo." in result


@pytest.mark.unit
def test_apply_vep_no_images_returns_unchanged():
    md = "# Just text\n\nNo images here."
    result = _apply_vep(md, [], _cfg())
    assert result == md


# ---------------------------------------------------------------------------
# enhance() — top-level integration
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_enhance_vep_disabled_uses_legacy_captions(tmp_path):
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    img = img_dir / "fig.png"
    img.write_bytes(b"fake")

    md = f"![](./{img.parent.name}/{img.name})"
    result = ConverterResult(markdown=md, images=[img], converter_used="marker")

    with patch("httpx.post", return_value=_mock_response("A photo of a cat.")):
        out = enhance(result, _cfg(visual_enabled=False))

    assert "A photo of a cat." in out.markdown


@pytest.mark.unit
def test_enhance_vep_enabled_classifies_and_dispatches(tmp_path):
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    img = img_dir / "chart.png"
    img.write_bytes(b"fake")

    md = f"![](./{img.parent.name}/{img.name})"
    result = ConverterResult(markdown=md, images=[img], converter_used="marker")
    description = "A bar chart showing monthly sales figures."

    def _post(url, **kwargs):
        payload = kwargs.get("json", {})
        prompt = payload.get("prompt", "")
        if "Classify" in prompt:
            return _mock_response("chart")
        return _mock_response(description)

    with patch("httpx.post", side_effect=_post):
        out = enhance(result, _cfg())

    assert description in out.markdown


@pytest.mark.unit
def test_enhance_ollama_disabled_skips_all_enhancement(tmp_path):
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    img = img_dir / "fig.png"
    img.write_bytes(b"fake")

    md = f"![](./{img.parent.name}/{img.name})"
    result = ConverterResult(markdown=md, images=[img], converter_used="marker")

    with patch("httpx.post") as mock_post:
        out = enhance(result, _cfg(ollama_enabled=False))

    mock_post.assert_not_called()
    assert out.markdown == md


@pytest.mark.unit
def test_enhance_preserves_result_metadata(tmp_path):
    result = ConverterResult(
        markdown="# Hello",
        converter_used="marker",
        metadata={"pages": 3},
        warnings=["warn1"],
    )
    with patch("httpx.post"):
        out = enhance(result, _cfg(ollama_enabled=False))

    assert out.converter_used == "marker"
    assert out.metadata == {"pages": 3}
    assert out.warnings == ["warn1"]


# ---------------------------------------------------------------------------
# VisualConfig loading
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_visual_config_defaults():
    from drop2md.config import VisualConfig

    vc = VisualConfig()
    assert vc.enabled is False
    assert vc.classify is True
    assert vc.chart_description is True
    assert vc.diagram_to_mermaid is False
    assert vc.formula_to_latex is False
    assert vc.table_image_to_gfm is True
    assert vc.screenshot_description is True


@pytest.mark.unit
def test_visual_config_loaded_from_toml(tmp_path):
    from drop2md.config import load_config

    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        "[visual]\nenabled = true\ndiagram_to_mermaid = true\nformula_to_latex = true\n",
        encoding="utf-8",
    )
    cfg = load_config(cfg_file)
    assert cfg.visual.enabled is True
    assert cfg.visual.diagram_to_mermaid is True
    assert cfg.visual.formula_to_latex is True
    assert cfg.visual.classify is True  # default preserved


@pytest.mark.unit
def test_visual_config_missing_section_uses_defaults(tmp_path):
    from drop2md.config import load_config

    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("[paths]\n", encoding="utf-8")
    cfg = load_config(cfg_file)
    assert cfg.visual.enabled is False


# ---------------------------------------------------------------------------
# Office image extraction
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_extract_docx_images_no_python_docx(tmp_path, monkeypatch):
    """When python-docx is absent, extraction returns [] without error."""
    import sys

    monkeypatch.setitem(sys.modules, "docx", None)
    from drop2md.converters.office import _extract_docx_images

    result = _extract_docx_images(tmp_path / "test.docx", tmp_path)
    assert result == []


@pytest.mark.unit
def test_extract_pptx_images_no_python_pptx(tmp_path, monkeypatch):
    """When python-pptx is absent, extraction returns [] without error."""
    import sys

    monkeypatch.setitem(sys.modules, "pptx", None)
    from drop2md.converters.office import _extract_pptx_images

    result = _extract_pptx_images(tmp_path / "test.pptx", tmp_path)
    assert result == []


@pytest.mark.unit
def test_extract_office_images_unsupported_suffix(tmp_path):
    from drop2md.converters.office import _extract_office_images

    result = _extract_office_images(tmp_path / "test.xlsx", tmp_path)
    assert result == []


# ---------------------------------------------------------------------------
# Legacy PDF image pass (VEP-5)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_legacy_pdf_image_pass_graceful_when_pymupdf_absent(tmp_path, monkeypatch):
    """pdfplumber converter succeeds even when PyMuPDF is not installed."""
    import sys

    monkeypatch.setitem(sys.modules, "fitz", None)

    # Create a minimal valid PDF (1 page, no text)

    # We can't easily create a real PDF without heavy deps, so mock pdfplumber
    mock_pdf = MagicMock()
    mock_pdf.__enter__ = lambda s: s
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = []

    with patch("pdfplumber.open", return_value=mock_pdf):
        from drop2md.converters.legacy_pdf import LegacyPdfConverter

        result = LegacyPdfConverter().convert(tmp_path / "test.pdf", tmp_path)

    assert result.converter_used == "pdfplumber"
    assert result.images == []


# ---------------------------------------------------------------------------
# Unreferenced image append (pdfplumber / MarkItDown case)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_apply_vep_appends_unreferenced_image(tmp_path):
    """Images not present in the markdown are appended at the end."""
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    img = img_dir / "chart.png"
    img.write_bytes(b"fake")

    # Markdown has NO image ref — simulates pdfplumber output
    md = "# Report\n\nSome text with no image refs.\n"

    def _post(url, **kwargs):
        payload = kwargs.get("json", {})
        prompt = payload.get("prompt", "")
        if "Classify" in prompt:
            return _mock_response("chart")
        return _mock_response("A bar chart showing quarterly revenue.")

    with patch("httpx.post", side_effect=_post):
        result = _apply_vep(md, [img], _cfg())

    assert "./images/chart.png" in result
    assert "A bar chart showing quarterly revenue." in result
    # Original text should still be there
    assert "Some text with no image refs." in result


@pytest.mark.unit
def test_inject_image_captions_appends_unreferenced_image(tmp_path):
    """_inject_image_captions appends images not already ref'd in the markdown."""
    from drop2md.enhance import _inject_image_captions

    img_dir = tmp_path / "images"
    img_dir.mkdir()
    img = img_dir / "fig.png"
    img.write_bytes(b"fake")

    md = "# Doc\n\nNo image refs here."

    with patch("httpx.post", return_value=_mock_response("A figure showing results.")):
        result = _inject_image_captions(md, [img], _cfg())

    assert "./images/fig.png" in result
    assert "A figure showing results." in result


# ---------------------------------------------------------------------------
# Branch coverage: _build_image_replacement fallback paths
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_apply_vep_diagram_mermaid_disabled(tmp_path):
    """When diagram_to_mermaid=False, diagram falls back to describe_image."""
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    img = img_dir / "flow.png"
    img.write_bytes(b"fake")

    markdown = f"![](./{img.parent.name}/{img.name})"

    def _post(url, **kwargs):
        payload = kwargs.get("json", {})
        if "Classify" in payload.get("prompt", ""):
            return _mock_response("diagram")
        return _mock_response("A flowchart with three nodes.")

    with patch("httpx.post", side_effect=_post):
        result = _apply_vep(markdown, [img], _cfg(diagram_to_mermaid=False))

    assert "A flowchart with three nodes." in result


@pytest.mark.unit
def test_apply_vep_formula_latex_disabled(tmp_path):
    """When formula_to_latex=False, formula falls back to describe_image."""
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    img = img_dir / "eq.png"
    img.write_bytes(b"fake")

    markdown = f"![](./{img.parent.name}/{img.name})"

    def _post(url, **kwargs):
        payload = kwargs.get("json", {})
        if "Classify" in payload.get("prompt", ""):
            return _mock_response("formula")
        return _mock_response("A mathematical equation.")

    with patch("httpx.post", side_effect=_post):
        result = _apply_vep(markdown, [img], _cfg(formula_to_latex=False))

    assert "A mathematical equation." in result


@pytest.mark.unit
def test_apply_vep_table_image_falls_back_when_no_gfm(tmp_path):
    """table-image falls back to describe_image when model returns no pipe table."""
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    img = img_dir / "tbl.png"
    img.write_bytes(b"fake")

    markdown = f"![](./{img.parent.name}/{img.name})"

    def _post(url, **kwargs):
        payload = kwargs.get("json", {})
        if "Classify" in payload.get("prompt", ""):
            return _mock_response("table-image")
        return _mock_response("A table of quarterly sales figures.")

    with patch("httpx.post", side_effect=_post):
        result = _apply_vep(markdown, [img], _cfg(table_image_to_gfm=True))

    # Model returned prose (no pipes) → fell back to describe_image caption
    assert "A table of quarterly sales figures." in result


@pytest.mark.unit
def test_apply_vep_screenshot_type(tmp_path):
    """screenshot type is handled by _describe_screenshot."""
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    img = img_dir / "ss.png"
    img.write_bytes(b"fake")

    markdown = f"![](./{img.parent.name}/{img.name})"

    def _post(url, **kwargs):
        payload = kwargs.get("json", {})
        if "Classify" in payload.get("prompt", ""):
            return _mock_response("screenshot")
        return _mock_response("A terminal window showing a Python error.")

    with patch("httpx.post", side_effect=_post):
        result = _apply_vep(markdown, [img], _cfg(screenshot_description=True))

    assert "A terminal window showing a Python error." in result


@pytest.mark.unit
def test_apply_vep_photo_type_uses_describe_image(tmp_path):
    """photo type (else branch) calls describe_image."""
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    img = img_dir / "photo.png"
    img.write_bytes(b"fake")

    markdown = f"![](./{img.parent.name}/{img.name})"

    def _post(url, **kwargs):
        payload = kwargs.get("json", {})
        if "Classify" in payload.get("prompt", ""):
            return _mock_response("photo")
        return _mock_response("A photograph of a mountain landscape.")

    with patch("httpx.post", side_effect=_post):
        result = _apply_vep(markdown, [img], _cfg())

    assert "A photograph of a mountain landscape." in result


@pytest.mark.unit
def test_apply_vep_unreferenced_diagram_appends_with_mermaid(tmp_path):
    """Unreferenced diagram with mermaid result is appended (covers extra append path)."""
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    img = img_dir / "flow.png"
    img.write_bytes(b"fake")

    # No image ref in markdown
    md = "# Report\n\nSome text.\n"
    mermaid = "```mermaid\nflowchart LR\n  A --> B\n```"

    def _post(url, **kwargs):
        payload = kwargs.get("json", {})
        if "Classify" in payload.get("prompt", ""):
            return _mock_response("diagram")
        return _mock_response(mermaid)

    with patch("httpx.post", side_effect=_post):
        result = _apply_vep(md, [img], _cfg(diagram_to_mermaid=True))

    assert "mermaid" in result
    assert "flow.png" in result


@pytest.mark.unit
def test_enhance_tables_calls_validate_table(tmp_path):
    """_enhance_tables finds a GFM table and calls validate_table on it."""
    from drop2md.enhance import _enhance_tables

    table_md = "| Col A | Col B |\n|---|---|\n| 1 | 2 |\n"

    with patch(
        "httpx.post",
        return_value=_mock_response("| Col A | Col B |\n|---|---|\n| 1 | 2 |"),
    ):
        result = _enhance_tables(table_md, _cfg())

    assert "|" in result


@pytest.mark.unit
def test_ollama_enhance_shim_importable():
    """ollama_enhance backward-compat shim can be imported without errors."""
    import drop2md.ollama_enhance  # noqa: F401


@pytest.mark.unit
def test_make_provider_gemini():
    """make_provider returns an OpenAICompatProvider for the gemini provider."""
    from drop2md.enhance_providers import OpenAICompatProvider, make_provider

    cfg = _cfg(provider="gemini")
    cfg.ollama.api_key = ""
    provider = make_provider(cfg)
    assert isinstance(provider, OpenAICompatProvider)


@pytest.mark.unit
def test_openai_compat_provider_reasoning_effort(tmp_path):
    """OpenAICompatProvider adds reasoning_effort to kwargs when set."""
    from unittest.mock import MagicMock, patch

    from drop2md.enhance_providers import OpenAICompatProvider

    provider = OpenAICompatProvider(
        model="o1-mini",
        base_url="https://api.openai.com/v1",
        api_key="test-key",
        timeout=5,
        reasoning_effort="medium",
    )

    mock_response = MagicMock()
    mock_response.choices[0].message.content = "The answer is 42."

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        result = provider.generate("What is 6 × 7?")

    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert call_kwargs.get("reasoning_effort") == "medium"
    assert result == "The answer is 42."
