"""Runtime hook: make bundled libmagic and magic.mgc visible inside a frozen binary.

PyInstaller runs this before any application code. We patch magic.loader so that
the bundled libmagic.1.dylib is tried first, before ctypes.util.find_library
searches the host system (where libmagic is almost certainly not installed).
"""
import os
import sys

_base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))


def _patch_magic_loader() -> None:
    try:
        import ctypes
        import magic.loader as _ml

        _bundled_lib = os.path.join(_base, "libmagic.1.dylib")
        if os.path.exists(_bundled_lib):
            _original_load = _ml.load_lib

            def _patched_load_lib():  # type: ignore[no-untyped-def]
                try:
                    return ctypes.CDLL(_bundled_lib)
                except OSError:
                    return _original_load()

            _ml.load_lib = _patched_load_lib

        _magic_db = os.path.join(_base, "magic_db", "magic.mgc")
        if os.path.exists(_magic_db):
            os.environ.setdefault("MAGIC", _magic_db)
    except ImportError:
        pass


_patch_magic_loader()
