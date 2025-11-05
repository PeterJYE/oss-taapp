"""Internal ai_adapter package marker for namespace resolution.

This package was added during HW2 exploration to house an HTTP adapter and
its tests. This file ensures the directory is treated as a regular package
instead of an implicit namespace. We intentionally avoid importing submodules
here to keep import side effects minimal.
"""

__all__: list[str] = []
