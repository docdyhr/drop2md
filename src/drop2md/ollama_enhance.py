"""Backward-compatibility re-export shim.

All enhancement logic has moved to drop2md.enhance and drop2md.enhance_providers.
This module is kept so existing imports continue to work without change.
"""

from drop2md.enhance import describe_image, enhance, validate_table  # noqa: F401
