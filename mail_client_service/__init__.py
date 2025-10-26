"""Compatibility shim to expose the FastAPI app as ``mail_client_service.app``.

Some project layouts place the actual package under ``src/`` directories which
can make importing during pytest collection fail. This shim lazily loads the
real module by filepath and re-exports the `app` object (and helpers) so tests
and tooling can import ``from mail_client_service import app``.

This file intentionally keeps imports local and execution minimal to avoid
running side-effects at import time.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


def _load_main_module() -> ModuleType:
    """Load the real FastAPI module from its file location.

    Returns a loaded module object. This is done lazily to avoid import-time
    side-effects during pytest collection.
    """
    # Determine the expected path to the real main.py in the repo
    repo_root = Path(__file__).resolve().parent
    # repo_root is the newly created mail_client_service/ folder; real module is at
    # <repo_root>/../src/mail_client_service/src/main.py
    candidate = (repo_root.parent / "src" / "mail_client_service" / "src" / "main.py").resolve()

    if not candidate.exists():
        raise ImportError(f"Could not find mail_client_service main module at {candidate}")

    spec = importlib.util.spec_from_file_location("mail_client_service.main", str(candidate))
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    # Execute the module in its own namespace
    spec.loader.exec_module(module)  # type: ignore[arg-type]

    # Ensure importing 'mail_client_service.main' via the normal import system
    # works by registering the loaded module in sys.modules and attaching it
    # to this package's namespace.
    sys.modules.setdefault("mail_client_service.main", module)
    globals()["main"] = module
    return module


# Lazily load the module only when attributes are accessed.
_module: ModuleType | None = None


def _ensure_module() -> ModuleType:
    global _module
    if _module is None:
        _module = _load_main_module()
    return _module


def __getattr__(name: str) -> Any:  # Python 3.7+ module-level __getattr__ hook
    mod = _ensure_module()
    return getattr(mod, name)


def __dir__() -> list[str]:
    mod = _ensure_module()
    return sorted(list(globals().keys()) + [n for n in dir(mod) if not n.startswith("__")])


def _get_app():
    return getattr(_ensure_module(), "app")


# Provide a convenient top-level 'app' attribute for common import style
app = _get_app()
