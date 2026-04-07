"""AI enhancement pipeline for drop2md — v0.3 Visual Enhancement Pipeline (VEP).

Two-stage enhancement:
  1. VEP — classify each extracted image and apply a per-class handler:
       chart        → prose description (type, axes, trend, key data points)
       diagram      → Mermaid code (prose fallback if model fails)
       formula      → $$LaTeX$$ block
       table-image  → GFM pipe table
       screenshot   → descriptive prose paragraph
       photo        → one-sentence alt-text (original behaviour)
  2. Table validation — scan markdown for GFM tables and ask the AI to fix
     any that are malformed.

All AI calls are wrapped in try/except — a provider being offline or returning
garbage never blocks conversion. Every handler degrades gracefully to the
previous behaviour (one-sentence caption) or a no-op.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from drop2md.config import Config
from drop2md.converters import ConverterResult
from drop2md.enhance_providers import make_provider

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Visual element types
# ---------------------------------------------------------------------------

_VISUAL_TYPES = frozenset(
    {"chart", "diagram", "formula", "table-image", "screenshot", "photo"}
)


# ---------------------------------------------------------------------------
# VEP-1: Classifier
# ---------------------------------------------------------------------------

def _classify_images(images: list[Path], config: Config) -> dict[Path, str]:
    """Classify each image into a visual element type.

    Makes a single batch API call with all image paths listed in the prompt,
    followed by individual image calls so the model can see each image.
    Falls back to "photo" for any image that cannot be classified.
    """
    classifications: dict[Path, str] = {}

    try:
        provider = make_provider(config)
        for img_path in images:
            if not img_path.exists():
                classifications[img_path] = "photo"
                continue
            prompt = (
                "Classify this image extracted from a document. "
                "Reply with exactly one word from this list: "
                "chart, diagram, formula, table-image, screenshot, photo.\n"
                "- chart: bar chart, line chart, pie chart, scatter plot, or any data visualisation\n"
                "- diagram: flowchart, sequence diagram, architecture diagram, network diagram, ER diagram\n"
                "- formula: mathematical or chemical equation, formula block\n"
                "- table-image: a table rendered as an image (rows and columns of data)\n"
                "- screenshot: a screenshot of software, a UI, a terminal, or a web page\n"
                "- photo: a photograph, illustration, logo, icon, or anything else\n"
                "Reply with exactly one word, nothing else."
            )
            raw = provider.generate(prompt, img_path).strip().lower()
            # Accept only known types; strip punctuation from model output
            cleaned = re.sub(r"[^a-z\-]", "", raw)
            classifications[img_path] = cleaned if cleaned in _VISUAL_TYPES else "photo"
            log.debug("VEP classify %s → %s", img_path.name, classifications[img_path])
    except Exception as exc:
        log.debug("VEP classification failed: %s — defaulting all to 'photo'", exc)
        for img in images:
            classifications.setdefault(img, "photo")

    # Fill any gaps
    for img in images:
        classifications.setdefault(img, "photo")

    return classifications


# ---------------------------------------------------------------------------
# VEP-2: Per-class handlers
# ---------------------------------------------------------------------------

def _describe_chart(image_path: Path, config: Config) -> str:
    """Extract chart type, axes, trend, and key data points as prose."""
    try:
        provider = make_provider(config)
        prompt = (
            "This image is a chart or data visualisation extracted from a document. "
            "Describe it concisely for inclusion as Markdown alt-text and a caption paragraph. "
            "Include: chart type (e.g. bar, line, pie), axis labels if visible, "
            "the main trend or finding, and up to three specific data points or values. "
            "Write 2–4 sentences. Be factual — do not invent values you cannot see."
        )
        return str(provider.generate(prompt, image_path)).strip()
    except Exception as exc:
        log.debug("chart description failed for %s: %s", image_path.name, exc)
        return ""


def _diagram_to_mermaid(image_path: Path, config: Config) -> str:
    """Attempt to convert a diagram to Mermaid code; fall back to prose."""
    try:
        provider = make_provider(config)
        prompt = (
            "This image is a diagram (flowchart, sequence diagram, architecture diagram, "
            "or similar) extracted from a document. "
            "Convert it to valid Mermaid diagram syntax if possible. "
            "Start your response with the Mermaid code block:\n"
            "```mermaid\n...\n```\n"
            "If you cannot produce valid Mermaid, instead write a structured prose "
            "description: list the nodes/boxes and the relationships between them "
            "(e.g. 'Box A → Box B → Box C'). Do not mix Mermaid and prose."
        )
        return str(provider.generate(prompt, image_path)).strip()
    except Exception as exc:
        log.debug("diagram-to-mermaid failed for %s: %s", image_path.name, exc)
        return ""


def _formula_to_latex(image_path: Path, config: Config) -> str:
    """Convert a formula image to a LaTeX block."""
    try:
        provider = make_provider(config)
        prompt = (
            "This image contains a mathematical or chemical formula extracted from a document. "
            "Convert it to LaTeX notation wrapped in a display math block: $$...$$. "
            "Return ONLY the LaTeX block, nothing else. "
            "If you cannot read the formula clearly, return a best-effort attempt."
        )
        return str(provider.generate(prompt, image_path)).strip()
    except Exception as exc:
        log.debug("formula-to-latex failed for %s: %s", image_path.name, exc)
        return ""


def _table_image_to_gfm(image_path: Path, config: Config) -> str:
    """Convert a table rendered as an image to a GFM pipe table."""
    try:
        provider = make_provider(config)
        prompt = (
            "This image contains a table extracted from a document. "
            "Convert it to a valid GitHub Flavored Markdown pipe table. "
            "Include a header row and a separator row (| --- | --- | ...). "
            "Return ONLY the markdown table, nothing else. "
            "If you cannot read all cells clearly, use '?' for unreadable values."
        )
        result: str = str(provider.generate(prompt, image_path)).strip()
        # Only return if the response looks like a real table
        if "|" in result and "---" in result:
            return result
        return ""
    except Exception as exc:
        log.debug("table-image-to-gfm failed for %s: %s", image_path.name, exc)
        return ""


def _describe_screenshot(image_path: Path, config: Config) -> str:
    """Describe a screenshot in a prose paragraph."""
    try:
        provider = make_provider(config)
        prompt = (
            "This image is a screenshot of software, a user interface, a terminal, "
            "or a web page extracted from a document. "
            "Describe what is shown: what application or interface is visible, "
            "what content or data is displayed, and what the screenshot is illustrating "
            "in the context of a document. Write 2–3 sentences."
        )
        return str(provider.generate(prompt, image_path)).strip()
    except Exception as exc:
        log.debug("screenshot description failed for %s: %s", image_path.name, exc)
        return ""


def describe_image(image_path: Path, config: Config) -> str:
    """Generate a concise alt-text description for an image (photo / fallback).

    Returns empty string on failure.
    """
    try:
        provider = make_provider(config)
        prompt = (
            "Describe this image from a document in one concise sentence "
            "suitable for use as Markdown alt-text. Be specific and factual."
        )
        return str(provider.generate(prompt, image_path)).strip()
    except Exception as exc:
        log.debug("Image description failed for %s: %s", image_path.name, exc)
        return ""


# ---------------------------------------------------------------------------
# VEP dispatch
# ---------------------------------------------------------------------------

def _build_image_replacement(
    img_path: Path,
    visual_type: str,
    config: Config,
) -> tuple[str, str]:
    """Return (alt_text, extra_markdown) for *img_path* based on *visual_type*.

    *alt_text* replaces the empty alt in the image reference.
    *extra_markdown* is inserted after the image reference (e.g. a table or
    Mermaid block). Both may be empty strings.
    """
    vcfg = config.visual
    alt = ""
    extra = ""

    if visual_type == "chart" and vcfg.chart_description:
        alt = _describe_chart(img_path, config)

    elif visual_type == "diagram":
        if vcfg.diagram_to_mermaid:
            result = _diagram_to_mermaid(img_path, config)
            if result:
                alt = f"Diagram: {img_path.stem}"
                extra = f"\n\n{result}"
        else:
            alt = describe_image(img_path, config)

    elif visual_type == "formula":
        if vcfg.formula_to_latex:
            latex = _formula_to_latex(img_path, config)
            if latex:
                alt = "Mathematical formula"
                extra = f"\n\n{latex}"
        else:
            alt = describe_image(img_path, config)

    elif visual_type == "table-image" and vcfg.table_image_to_gfm:
        gfm_table = _table_image_to_gfm(img_path, config)
        if gfm_table:
            alt = "Table"
            extra = f"\n\n{gfm_table}"
        else:
            alt = describe_image(img_path, config)

    elif visual_type == "screenshot" and vcfg.screenshot_description:
        alt = _describe_screenshot(img_path, config)

    else:
        # photo or unhandled — original one-sentence caption
        alt = describe_image(img_path, config)

    return alt, extra


def _apply_vep(markdown: str, images: list[Path], config: Config) -> str:
    """Classify all images and apply per-class enhancements to the markdown.

    Two cases are handled:
    - Image ref already present as ``![](./{subdir}/{name})``: replaced in-place.
    - Image has no ref in the markdown (e.g. pdfplumber text, MarkItDown office
      output with its own ref format): appended at the end of the document so
      the visual content is not silently lost.
    """
    if not images:
        return markdown

    vcfg = config.visual
    if not vcfg.classify:
        # Classify disabled — fall back to legacy one-sentence captions for all
        return _inject_image_captions(markdown, images, config)

    classifications = _classify_images(images, config)
    appended: list[str] = []

    for img_path in images:
        visual_type = classifications.get(img_path, "photo")
        alt, extra = _build_image_replacement(img_path, visual_type, config)

        ref_base = f"./{img_path.parent.name}/{img_path.name}"
        old_ref = f"![]({ref_base})"

        if ref_base in markdown:
            # Ref exists — replace in-place (bare or already captioned)
            if alt or extra:
                new_ref = f"![{alt}]({ref_base})"
                if extra:
                    new_ref = new_ref + extra
                markdown = markdown.replace(old_ref, new_ref)
        else:
            # No ref in markdown — append so the visual content isn't lost
            new_ref = f"![{alt}]({ref_base})" if alt else f"![]({ref_base})"
            if extra:
                new_ref = new_ref + extra
            appended.append(new_ref)
            log.debug("VEP appended unreferenced image: %s", img_path.name)

    if appended:
        markdown = markdown.rstrip() + "\n\n" + "\n\n".join(appended) + "\n"

    return markdown


# ---------------------------------------------------------------------------
# Legacy helpers (kept for backward compatibility and direct use)
# ---------------------------------------------------------------------------

def validate_table(table_md: str, config: Config) -> str:
    """Ask the AI provider to validate and fix a GFM table.

    Returns the original table if provider is unavailable or returns nonsense.
    """
    try:
        provider = make_provider(config)
        prompt = (
            "Fix this GitHub Flavored Markdown table so it is valid GFM. "
            "Return ONLY the corrected table, no explanation:\n\n"
            f"{table_md}"
        )
        fixed: str = str(provider.generate(prompt))
        if "|" in fixed:
            return fixed
        return table_md
    except Exception as exc:
        log.debug("Table validation failed: %s", exc)
        return table_md


def _inject_image_captions(markdown: str, images: list[Path], config: Config) -> str:
    """Replace bare image refs with AI-generated alt-text (legacy one-sentence path).

    Images with no existing ref in the markdown are appended at the end.
    """
    appended: list[str] = []
    for img_path in images:
        ref_base = f"./{img_path.parent.name}/{img_path.name}"
        alt = describe_image(img_path, config)
        if ref_base in markdown:
            old_ref = f"![]({ref_base})"
            if alt:
                new_ref = f"![{alt}]({ref_base})"
                markdown = markdown.replace(old_ref, new_ref)
        else:
            # No existing ref — append so the image isn't silently lost
            appended.append(f"![{alt}]({ref_base})" if alt else f"![]({ref_base})")
    if appended:
        markdown = markdown.rstrip() + "\n\n" + "\n\n".join(appended) + "\n"
    return markdown


def _enhance_tables(markdown: str, config: Config) -> str:
    """Find and validate GFM tables in markdown."""
    table_pattern = re.compile(
        r"(\|[^\n]+\|\n)(\|[-:| ]+\|\n)((?:\|[^\n]+\|\n)+)",
        re.MULTILINE,
    )

    def _fix_match(m: re.Match) -> str:
        return validate_table(m.group(0), config)

    return table_pattern.sub(_fix_match, markdown)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def enhance(result: ConverterResult, config: Config) -> ConverterResult:
    """Apply AI enhancement to a ConverterResult.

    When ``config.visual.enabled`` is True (and ``config.ollama.enabled`` is
    True), runs the full Visual Enhancement Pipeline before table validation.
    Otherwise falls back to the v0.2 behaviour: one-sentence image captions
    and GFM table repair.

    All failures degrade gracefully — the original markdown is always returned.
    """
    if not config.ollama.enabled:
        return result

    md = result.markdown

    if result.images:
        if config.visual.enabled:
            md = _apply_vep(md, result.images, config)
        else:
            md = _inject_image_captions(md, result.images, config)

    if "|" in md and getattr(config.ollama, "validate_tables", True):
        md = _enhance_tables(md, config)

    return ConverterResult(
        markdown=md,
        images=result.images,
        metadata=result.metadata,
        converter_used=result.converter_used,
        warnings=result.warnings,
    )
