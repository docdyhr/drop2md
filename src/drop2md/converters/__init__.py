"""Converter base classes and result types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ConverterResult:
    """Result of a document conversion."""

    markdown: str
    images: list[Path] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    converter_used: str = ""
    warnings: list[str] = field(default_factory=list)


class ConversionError(Exception):
    """Raised when a conversion tier fails."""


class BaseConverter(ABC):
    """Abstract base class for all document converters."""

    name: str = "base"

    @classmethod
    def is_available(cls) -> bool:
        """Return True if this converter's dependencies are installed."""
        return True

    @abstractmethod
    def convert(self, path: Path, output_dir: Path) -> ConverterResult:
        """Convert a document at *path* to markdown.

        Args:
            path: Absolute path to the source document.
            output_dir: Directory where extracted images should be saved.

        Returns:
            ConverterResult with markdown text and list of extracted image paths.
        """
