"""Compatibility shim for legacy `generated_client` imports.

This module dynamically proxies the generated OpenAPI client that lives under
`mail_client_service_client`, exposing the same symbols while also registering
`generated_client.api` and `generated_client.models` submodules so existing
imports continue working.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys
from types import ModuleType

try:
    _root = importlib.import_module("mail_client_service_client")
    _api = importlib.import_module("mail_client_service_client.api")
    _models = importlib.import_module("mail_client_service_client.models")
except ModuleNotFoundError:
    from . import mail_client_service_client as _root  # type: ignore[assignment]
    from .mail_client_service_client import api as _api
    from .mail_client_service_client import models as _models

Client = _root.Client  # re-export main client class
mail_client_service_client = _root
api = _api
models = _models


def _register(name: str, module: ModuleType) -> None:
    sys.modules.setdefault(name, module)


def _alias_package_modules(package_name: str, alias_prefix: str) -> None:
    package = sys.modules[package_name]
    if not hasattr(package, "__path__"):
        return
    for finder in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        module = importlib.import_module(finder.name)
        alias = alias_prefix + finder.name[len(package_name) :]
        _register(alias, module)


_register(__name__ + ".mail_client_service_client", mail_client_service_client)
_register(__name__ + ".mail_client_service_client.api", api)
_register(__name__ + ".mail_client_service_client.models", models)
_register("mail_client_service_client", mail_client_service_client)
_register("mail_client_service_client.api", api)
_register("mail_client_service_client.models", models)
_register(__name__ + ".api", api)
_register(__name__ + ".models", models)
_alias_package_modules("mail_client_service_client", __name__ + ".mail_client_service_client")
_alias_package_modules("mail_client_service_client.api", __name__ + ".mail_client_service_client.api")
_alias_package_modules("mail_client_service_client.models", __name__ + ".mail_client_service_client.models")

__all__ = ["Client", "mail_client_service_client", "api", "models"]

